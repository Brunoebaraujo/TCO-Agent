"""
Popula o banco com dados de referência iniciais — SKUs Goodpack, embalagens
concorrentes, produtos e a estrutura conhecida de acessórios por embalagem.

Idempotente: verifica se já existe dado antes de inserir, então pode ser
chamado a cada inicialização do servidor sem duplicar registros.
"""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import (
    GoodpackSKU, CompetitorUnit, ProductCatalog,
    AccessoryType, PackagingAccessory, Region,
)

GOODPACK_SKUS = [
    dict(sku_code="MB4", description="Stackable steel container — 1.40 m³",
         volume_liters=1400, max_payload_kg=1550, tare_weight_kg=120,
         stack_full_warehouse=4, stack_empty_warehouse=72, stack_full_transit=2,
         qty_20ft_dry=16, qty_40ft_dry=32, tds_document_ref="GP TDS MB4 Mar24/2022"),
    dict(sku_code="MB5", description="Stackable steel container — 1.60 m³",
         volume_liters=1600, max_payload_kg=1650, tare_weight_kg=132,
         stack_full_warehouse=5, stack_empty_warehouse=96, stack_full_transit=2,
         qty_20ft_dry=16, qty_40ft_dry=32, tds_document_ref="GP TDS MB5 May02/2021"),
    dict(sku_code="MB6", description="Stackable steel container — 1.25 m³",
         volume_liters=1250, max_payload_kg=1650, tare_weight_kg=115,
         stack_full_warehouse=5, stack_empty_warehouse=80, stack_full_transit=2,
         qty_20ft_dry=16, qty_40ft_dry=36, tds_document_ref="GP TDS MB6 Feb27/2023"),
]

COMPETITOR_UNITS = [
    dict(unit_name="Octabin", unit_type="bin"),
    dict(unit_name="Drum 200L", unit_type="drum", volume_liters=200),
]

PRODUCTS = [
    dict(product_name="FCOJ", category_code="CIT", category_name="Citrus Juice Concentrate"),
    dict(product_name="NFC", category_code="CIT", category_name="Not From Concentrate Juice"),
    dict(product_name="Omega 3", category_code="FAO", category_name="Fat and Oils"),
    dict(product_name="Palm Oil", category_code="FAO", category_name="Fat and Oils"),
    dict(product_name="Purê de tomate", category_code="DAY", category_name="Fruit/Vegetable Derivatives"),
]

ACCESSORY_TYPES = [
    "Pallet", "Poly Liner", "Base Pad", "Aseptic Bag",
    "Strapping Cost", "Lid", "Dunnage", "Top Sheet", "FIBC",
]

REGIONS = [
    ("GLOBAL", "Global — fallback quando região específica não existe"),
    ("LATAM", "Latin America"),
    ("EUROPE", "Europe"),
    ("ASIA", "Asia Pacific"),
    ("NAMERICA", "North America"),
    ("MEA", "Middle East & Africa"),
]

# Estrutura de acessórios: (packaging_type, sku_or_unit_name, product_name|None, [acessórios])
PACKAGING_ACCESSORY_RULES = [
    ("goodpack", "MB4", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB5", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB6", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB6", "FCOJ", ["Poly Liner"]),
    ("goodpack", "MB6", "NFC", ["Aseptic Bag"]),
    ("competitor", "Drum 200L", None, ["Poly Liner", "Aseptic Bag", "Strapping Cost"]),
    ("competitor", "Octabin", None, ["Pallet", "Poly Liner", "Aseptic Bag", "Strapping Cost", "Dunnage"]),
]


async def seed_initial_data(db: AsyncSession) -> None:
    # Regions
    existing_regions = (await db.execute(select(Region.region_code))).scalars().all()
    for code, name in REGIONS:
        if code not in existing_regions:
            db.add(Region(region_code=code, region_name=name))
    await db.flush()

    # Goodpack SKUs
    existing_skus = (await db.execute(select(GoodpackSKU.sku_code))).scalars().all()
    for sku_data in GOODPACK_SKUS:
        if sku_data["sku_code"] not in existing_skus:
            db.add(GoodpackSKU(**sku_data))
    await db.flush()

    # Competitor units
    existing_units = (await db.execute(select(CompetitorUnit.unit_name))).scalars().all()
    for unit_data in COMPETITOR_UNITS:
        if unit_data["unit_name"] not in existing_units:
            db.add(CompetitorUnit(**unit_data))
    await db.flush()

    # Products
    existing_products = (await db.execute(select(ProductCatalog.product_name))).scalars().all()
    for product_data in PRODUCTS:
        if product_data["product_name"] not in existing_products:
            db.add(ProductCatalog(**product_data))
    await db.flush()

    # Accessory types
    existing_acc_types = (await db.execute(select(AccessoryType.accessory_name))).scalars().all()
    for name in ACCESSORY_TYPES:
        if name not in existing_acc_types:
            db.add(AccessoryType(accessory_name=name))
    await db.flush()

    # Packaging <-> accessory links — só roda se ainda não há nenhum vínculo
    # (evita duplicar a cada boot; edições manuais do usuário ficam preservadas)
    existing_links_count = len((await db.execute(select(PackagingAccessory.id))).scalars().all())
    if existing_links_count == 0:
        skus_by_code = {s.sku_code: s.id for s in (await db.execute(select(GoodpackSKU))).scalars().all()}
        units_by_name = {u.unit_name: u.id for u in (await db.execute(select(CompetitorUnit))).scalars().all()}
        products_by_name = {p.product_name: p.id for p in (await db.execute(select(ProductCatalog))).scalars().all()}
        acc_types_by_name = {a.accessory_name: a.id for a in (await db.execute(select(AccessoryType))).scalars().all()}

        for packaging_type, name, product_name, accessories in PACKAGING_ACCESSORY_RULES:
            goodpack_sku_id = skus_by_code.get(name) if packaging_type == "goodpack" else None
            competitor_unit_id = units_by_name.get(name) if packaging_type == "competitor" else None
            product_id = products_by_name.get(product_name) if product_name else None

            for accessory_name in accessories:
                accessory_type_id = acc_types_by_name.get(accessory_name)
                if not accessory_type_id:
                    continue
                db.add(PackagingAccessory(
                    packaging_type=packaging_type,
                    goodpack_sku_id=goodpack_sku_id,
                    competitor_unit_id=competitor_unit_id,
                    product_id=product_id,
                    accessory_type_id=accessory_type_id,
                    confidence_level="validation_required",
                    source_type="interno",
                    source_detail="Estrutura inicial — preço pendente de confirmação",
                    collected_at=date.today(),
                ))
    await db.flush()
