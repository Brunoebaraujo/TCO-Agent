"""
Popula o banco com dados de referência iniciais — SKUs Goodpack, embalagens
concorrentes, hierarquia de produtos (categoria > produto > tipo), e a
estrutura conhecida de acessórios por embalagem.

Idempotente: verifica se já existe dado antes de inserir, então pode ser
chamado a cada inicialização do servidor sem duplicar registros.
"""
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import (
    GoodpackSKU, CompetitorUnit, ProductCategory, Product, ProductType,
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

# Hierarquia: categoria -> {produto -> [tipos]}
PRODUCT_HIERARCHY = {
    "Citrus": {
        "Orange": ["NFC", "FCOJ", "Concentrate"],
        "Lemon": ["NFC", "Concentrate"],
    },
    "Fat and Oils": {
        "Omega 3": ["Crude", "Refined"],
        "Palm Oil": ["Crude", "Refined"],
    },
    "Fruit/Vegetable Derivatives": {
        "Tomato": ["Purée", "Paste"],
    },
}

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

# Estrutura de acessórios: (packaging_type, sku_or_unit_name, (produto, tipo)|None, [acessórios])
# (produto, tipo) = None significa default genérico, válido para qualquer produto/tipo.
PACKAGING_ACCESSORY_RULES = [
    ("goodpack", "MB4", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB5", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB6", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB6", ("Orange", "FCOJ"), ["Poly Liner"]),
    ("goodpack", "MB6", ("Orange", "NFC"), ["Aseptic Bag"]),
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

    # Product hierarchy: category -> product -> type
    existing_categories = {
        c.category_name: c.id for c in (await db.execute(select(ProductCategory))).scalars().all()
    }
    for category_name in PRODUCT_HIERARCHY:
        if category_name not in existing_categories:
            cat = ProductCategory(category_name=category_name)
            db.add(cat)
            await db.flush()
            existing_categories[category_name] = cat.id

    existing_products = {
        (p.category_id, p.product_name): p.id for p in (await db.execute(select(Product))).scalars().all()
    }
    for category_name, products in PRODUCT_HIERARCHY.items():
        category_id = existing_categories[category_name]
        for product_name in products:
            key = (category_id, product_name)
            if key not in existing_products:
                prod = Product(category_id=category_id, product_name=product_name)
                db.add(prod)
                await db.flush()
                existing_products[key] = prod.id

    existing_types = {
        (t.product_id, t.type_name): t.id for t in (await db.execute(select(ProductType))).scalars().all()
    }
    for category_name, products in PRODUCT_HIERARCHY.items():
        category_id = existing_categories[category_name]
        for product_name, types in products.items():
            product_id = existing_products[(category_id, product_name)]
            for type_name in types:
                key = (product_id, type_name)
                if key not in existing_types:
                    pt = ProductType(product_id=product_id, type_name=type_name)
                    db.add(pt)
                    await db.flush()
                    existing_types[key] = pt.id

    # Accessory types
    existing_acc_types = (await db.execute(select(AccessoryType.accessory_name))).scalars().all()
    for name in ACCESSORY_TYPES:
        if name not in existing_acc_types:
            db.add(AccessoryType(accessory_name=name))
    await db.flush()

    # Packaging <-> accessory links — só roda se ainda não há nenhum vínculo
    existing_links_count = len((await db.execute(select(PackagingAccessory.id))).scalars().all())
    if existing_links_count == 0:
        skus_by_code = {s.sku_code: s.id for s in (await db.execute(select(GoodpackSKU))).scalars().all()}
        units_by_name = {u.unit_name: u.id for u in (await db.execute(select(CompetitorUnit))).scalars().all()}
        acc_types_by_name = {a.accessory_name: a.id for a in (await db.execute(select(AccessoryType))).scalars().all()}

        # Lookup reverso: (produto, tipo) -> product_type_id (busca em qualquer categoria)
        type_lookup = {}
        all_products = {p.id: p for p in (await db.execute(select(Product))).scalars().all()}
        all_types = (await db.execute(select(ProductType))).scalars().all()
        for t in all_types:
            product_name = all_products[t.product_id].product_name
            type_lookup[(product_name, t.type_name)] = t.id

        for packaging_type, name, product_type_key, accessories in PACKAGING_ACCESSORY_RULES:
            goodpack_sku_id = skus_by_code.get(name) if packaging_type == "goodpack" else None
            competitor_unit_id = units_by_name.get(name) if packaging_type == "competitor" else None
            product_type_id = type_lookup.get(product_type_key) if product_type_key else None

            for accessory_name in accessories:
                accessory_type_id = acc_types_by_name.get(accessory_name)
                if not accessory_type_id:
                    continue
                db.add(PackagingAccessory(
                    packaging_type=packaging_type,
                    goodpack_sku_id=goodpack_sku_id,
                    competitor_unit_id=competitor_unit_id,
                    product_type_id=product_type_id,
                    accessory_type_id=accessory_type_id,
                    confidence_level="validation_required",
                    source_type="interno",
                    source_detail="Estrutura inicial — preço pendente de confirmação",
                    collected_at=date.today(),
                ))
    await db.flush()
