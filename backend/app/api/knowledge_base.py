"""
Router: Knowledge Base — CRUD para benchmarks, SKUs, concorrentes,
produtos e acessórios por embalagem.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import (
    GoodpackSKU, CompetitorUnit, CompetitorPricing,
    ProductCategory, Product, ProductType, AccessoryType, PackagingAccessory,
)

router = APIRouter()


# -------------------------------------------------------------
# SKUs Goodpack
# -------------------------------------------------------------

class GoodpackSKUIn(BaseModel):
    sku_code: str
    description: str | None = None
    volume_liters: float | None = None
    max_payload_kg: float | None = None
    tare_weight_kg: float | None = None


@router.get("/skus")
async def list_skus(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GoodpackSKU).where(GoodpackSKU.active == True))
    skus = result.scalars().all()
    return {"skus": [
        {
            "id": s.id, "sku_code": s.sku_code, "description": s.description,
            "volume_liters": float(s.volume_liters) if s.volume_liters else None,
            "max_payload_kg": float(s.max_payload_kg) if s.max_payload_kg else None,
        }
        for s in skus
    ]}


@router.post("/skus")
async def create_sku(payload: GoodpackSKUIn, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(GoodpackSKU).where(GoodpackSKU.sku_code == payload.sku_code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Já existe uma SKU com o código '{payload.sku_code}'")
    sku = GoodpackSKU(**payload.model_dump())
    db.add(sku)
    await db.flush()
    return {"id": sku.id}


@router.put("/skus/{sku_id}")
async def update_sku(sku_id: int, payload: GoodpackSKUIn, db: AsyncSession = Depends(get_db)):
    sku = await db.get(GoodpackSKU, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU não encontrada")
    for k, v in payload.model_dump().items():
        setattr(sku, k, v)
    return {"updated": True}


@router.delete("/skus/{sku_id}")
async def delete_sku(sku_id: int, db: AsyncSession = Depends(get_db)):
    sku = await db.get(GoodpackSKU, sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU não encontrada")
    sku.active = False
    return {"deleted": True}


# -------------------------------------------------------------
# Embalagens concorrentes
# -------------------------------------------------------------

class CompetitorUnitIn(BaseModel):
    unit_name: str
    unit_type: str | None = None
    volume_liters: float | None = None
    max_payload_kg: float | None = None
    tare_weight_kg: float | None = None


@router.get("/competitors")
async def list_competitors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CompetitorUnit).where(CompetitorUnit.active == True))
    units = result.scalars().all()
    return {"competitors": [
        {
            "id": u.id, "unit_name": u.unit_name, "unit_type": u.unit_type,
            "volume_liters": float(u.volume_liters) if u.volume_liters else None,
            "max_payload_kg": float(u.max_payload_kg) if u.max_payload_kg else None,
        }
        for u in units
    ]}


@router.post("/competitors")
async def create_competitor(payload: CompetitorUnitIn, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(CompetitorUnit).where(CompetitorUnit.unit_name == payload.unit_name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Já existe uma embalagem com o nome '{payload.unit_name}'")
    unit = CompetitorUnit(**payload.model_dump())
    db.add(unit)
    await db.flush()
    return {"id": unit.id}


@router.put("/competitors/{competitor_id}")
async def update_competitor(competitor_id: int, payload: CompetitorUnitIn, db: AsyncSession = Depends(get_db)):
    unit = await db.get(CompetitorUnit, competitor_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Embalagem concorrente não encontrada")
    for k, v in payload.model_dump().items():
        setattr(unit, k, v)
    return {"updated": True}


@router.delete("/competitors/{competitor_id}")
async def delete_competitor(competitor_id: int, db: AsyncSession = Depends(get_db)):
    unit = await db.get(CompetitorUnit, competitor_id)
    if not unit:
        raise HTTPException(status_code=404, detail="Embalagem concorrente não encontrada")
    unit.active = False  # soft delete — preserva histórico de pricing/acessórios vinculados
    return {"deleted": True}


# -------------------------------------------------------------
# Preços de embalagens concorrentes (histórico rastreável)
# -------------------------------------------------------------

class CompetitorPricingIn(BaseModel):
    unit_price: float
    currency: str = "USD"
    source_type: str
    source_detail: str | None = None
    confidence_level: str = "validation_required"
    region: str | None = None


@router.get("/competitors/{competitor_id}/pricing")
async def get_competitor_pricing(competitor_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CompetitorPricing)
        .where(CompetitorPricing.competitor_unit_id == competitor_id)
        .where(CompetitorPricing.is_current == True)
        .order_by(CompetitorPricing.collected_at.desc())
    )
    pricing = result.scalars().all()
    return {"pricing": [
        {
            "id": p.id, "unit_price": float(p.unit_price), "currency": p.currency,
            "collected_at": p.collected_at.isoformat(), "source_type": p.source_type,
            "source_detail": p.source_detail, "confidence_level": p.confidence_level,
            "region": p.region,
        }
        for p in pricing
    ]}


@router.post("/competitors/{competitor_id}/pricing")
async def add_competitor_pricing(
    competitor_id: int, payload: CompetitorPricingIn, db: AsyncSession = Depends(get_db)
):
    """
    Adiciona novo preço para um concorrente. Marca quaisquer preços anteriores
    da mesma região como is_current=False — preserva histórico, mas só um
    preço "ativo" por região a qualquer momento.
    """
    result = await db.execute(
        select(CompetitorPricing)
        .where(CompetitorPricing.competitor_unit_id == competitor_id)
        .where(CompetitorPricing.region == payload.region)
        .where(CompetitorPricing.is_current == True)
    )
    for old in result.scalars().all():
        old.is_current = False

    new_pricing = CompetitorPricing(
        competitor_unit_id=competitor_id,
        unit_price=payload.unit_price,
        currency=payload.currency,
        collected_at=date.today(),
        source_type=payload.source_type,
        source_detail=payload.source_detail,
        confidence_level=payload.confidence_level,
        region=payload.region,
        is_current=True,
    )
    db.add(new_pricing)
    await db.flush()
    return {"id": new_pricing.id}


# -------------------------------------------------------------
# Hierarquia de produtos: Categoria > Produto > Tipo
# -------------------------------------------------------------

class ProductCategoryIn(BaseModel):
    category_name: str
    notes: str | None = None


class ProductIn(BaseModel):
    category_id: int
    product_name: str
    notes: str | None = None


class ProductTypeIn(BaseModel):
    product_id: int
    type_name: str
    notes: str | None = None


@router.get("/product-categories")
async def list_product_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductCategory).where(ProductCategory.active == True))
    categories = result.scalars().all()
    return {"categories": [{"id": c.id, "category_name": c.category_name} for c in categories]}


@router.post("/product-categories")
async def create_product_category(payload: ProductCategoryIn, db: AsyncSession = Depends(get_db)):
    category = ProductCategory(**payload.model_dump())
    db.add(category)
    await db.flush()
    return {"id": category.id}


@router.delete("/product-categories/{category_id}")
async def delete_product_category(category_id: int, db: AsyncSession = Depends(get_db)):
    category = await db.get(ProductCategory, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    category.active = False
    return {"deleted": True}


@router.get("/products")
async def list_products(category_id: int | None = None, db: AsyncSession = Depends(get_db)):
    query = select(Product).where(Product.active == True)
    if category_id:
        query = query.where(Product.category_id == category_id)
    result = await db.execute(query)
    products = result.scalars().all()
    return {"products": [
        {"id": p.id, "category_id": p.category_id, "product_name": p.product_name}
        for p in products
    ]}


@router.post("/products")
async def create_product(payload: ProductIn, db: AsyncSession = Depends(get_db)):
    product = Product(**payload.model_dump())
    db.add(product)
    await db.flush()
    return {"id": product.id}


@router.delete("/products/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    product.active = False
    return {"deleted": True}


@router.get("/product-types")
async def list_product_types(product_id: int | None = None, db: AsyncSession = Depends(get_db)):
    query = select(ProductType).where(ProductType.active == True)
    if product_id:
        query = query.where(ProductType.product_id == product_id)
    result = await db.execute(query)
    types = result.scalars().all()
    return {"product_types": [
        {"id": t.id, "product_id": t.product_id, "type_name": t.type_name}
        for t in types
    ]}


@router.post("/product-types")
async def create_product_type(payload: ProductTypeIn, db: AsyncSession = Depends(get_db)):
    ptype = ProductType(**payload.model_dump())
    db.add(ptype)
    await db.flush()
    return {"id": ptype.id}


@router.delete("/product-types/{type_id}")
async def delete_product_type(type_id: int, db: AsyncSession = Depends(get_db)):
    ptype = await db.get(ProductType, type_id)
    if not ptype:
        raise HTTPException(status_code=404, detail="Tipo de produto não encontrado")
    ptype.active = False
    return {"deleted": True}


@router.get("/products/full-tree")
async def get_full_product_tree(db: AsyncSession = Depends(get_db)):
    """
    Retorna a hierarquia completa (categoria -> produtos -> tipos) numa
    única chamada — usado pela tela de Knowledge Base para montar os
    seletores em cascata sem precisar de 3 requisições separadas.
    """
    categories = (await db.execute(select(ProductCategory).where(ProductCategory.active == True))).scalars().all()
    products = (await db.execute(select(Product).where(Product.active == True))).scalars().all()
    types = (await db.execute(select(ProductType).where(ProductType.active == True))).scalars().all()

    tree = []
    for cat in categories:
        cat_products = []
        for p in [p for p in products if p.category_id == cat.id]:
            p_types = [{"id": t.id, "type_name": t.type_name} for t in types if t.product_id == p.id]
            cat_products.append({"id": p.id, "product_name": p.product_name, "types": p_types})
        tree.append({"id": cat.id, "category_name": cat.category_name, "products": cat_products})

    return {"tree": tree}


# -------------------------------------------------------------
# Catálogo de tipos de acessório
# -------------------------------------------------------------

@router.get("/accessory-types")
async def list_accessory_types(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AccessoryType).where(AccessoryType.active == True))
    types = result.scalars().all()
    return {"accessory_types": [{"id": t.id, "accessory_name": t.accessory_name} for t in types]}


class AccessoryTypeIn(BaseModel):
    accessory_name: str
    description: str | None = None


@router.post("/accessory-types")
async def create_accessory_type(payload: AccessoryTypeIn, db: AsyncSession = Depends(get_db)):
    acc_type = AccessoryType(**payload.model_dump())
    db.add(acc_type)
    await db.flush()
    return {"id": acc_type.id}


# -------------------------------------------------------------
# Vínculo embalagem (+ produto opcional) ↔ acessórios
# -------------------------------------------------------------

class PackagingAccessoryIn(BaseModel):
    packaging_type: str  # 'goodpack' | 'competitor'
    goodpack_sku_id: int | None = None
    competitor_unit_id: int | None = None
    product_type_id: int | None = None  # None = default genérico da embalagem
    accessory_type_id: int
    default_unit_price: float | None = None
    currency: str = "USD"
    region: str = "GLOBAL"
    confidence_level: str = "validation_required"
    source_type: str | None = None
    source_detail: str | None = None


@router.get("/packaging-accessories")
async def list_packaging_accessories(
    goodpack_sku_id: int | None = None,
    competitor_unit_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Lista os vínculos embalagem→acessório. Filtra por SKU Goodpack ou
    unidade concorrente quando informado — usado pela tela de Knowledge
    Base para mostrar "o que esta embalagem usa".
    """
    query = select(PackagingAccessory).where(PackagingAccessory.is_current == True)
    if goodpack_sku_id:
        query = query.where(PackagingAccessory.goodpack_sku_id == goodpack_sku_id)
    if competitor_unit_id:
        query = query.where(PackagingAccessory.competitor_unit_id == competitor_unit_id)

    result = await db.execute(query)
    items = result.scalars().all()

    accessory_types = {t.id: t.accessory_name for t in (await db.execute(select(AccessoryType))).scalars().all()}
    product_types = {t.id: t for t in (await db.execute(select(ProductType))).scalars().all()}
    products = {p.id: p for p in (await db.execute(select(Product))).scalars().all()}

    def _product_type_label(product_type_id):
        if not product_type_id or product_type_id not in product_types:
            return None
        pt = product_types[product_type_id]
        product = products.get(pt.product_id)
        product_name = product.product_name if product else "?"
        return f"{product_name} / {pt.type_name}"

    return {"packaging_accessories": [
        {
            "id": pa.id,
            "packaging_type": pa.packaging_type,
            "goodpack_sku_id": pa.goodpack_sku_id,
            "competitor_unit_id": pa.competitor_unit_id,
            "product_type_id": pa.product_type_id,
            "product_type_label": _product_type_label(pa.product_type_id),
            "accessory_type_id": pa.accessory_type_id,
            "accessory_name": accessory_types.get(pa.accessory_type_id, "—"),
            "default_unit_price": float(pa.default_unit_price) if pa.default_unit_price else None,
            "currency": pa.currency,
            "region": pa.region,
            "confidence_level": pa.confidence_level,
            "source_detail": pa.source_detail,
        }
        for pa in items
    ]}


@router.post("/packaging-accessories")
async def create_packaging_accessory(payload: PackagingAccessoryIn, db: AsyncSession = Depends(get_db)):
    if payload.packaging_type == "goodpack" and not payload.goodpack_sku_id:
        raise HTTPException(status_code=400, detail="goodpack_sku_id é obrigatório para packaging_type=goodpack")
    if payload.packaging_type == "competitor" and not payload.competitor_unit_id:
        raise HTTPException(status_code=400, detail="competitor_unit_id é obrigatório para packaging_type=competitor")

    item = PackagingAccessory(**payload.model_dump(), collected_at=date.today())
    db.add(item)
    await db.flush()
    return {"id": item.id}


@router.put("/packaging-accessories/{item_id}")
async def update_packaging_accessory(
    item_id: int, payload: PackagingAccessoryIn, db: AsyncSession = Depends(get_db)
):
    item = await db.get(PackagingAccessory, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")
    for k, v in payload.model_dump().items():
        setattr(item, k, v)
    item.collected_at = date.today()
    return {"updated": True}


@router.delete("/packaging-accessories/{item_id}")
async def delete_packaging_accessory(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(PackagingAccessory, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")
    item.is_current = False
    return {"deleted": True}

# ---------------------------------------------------------------------------
# KB Apply Offer — salva os itens confirmados pelo vendedor no painel KB_OFFER
# ---------------------------------------------------------------------------
from pydantic import BaseModel as _BaseModel
from typing import List as _List, Optional as _Optional

class KBOfferItem(_BaseModel):
    type: str                          # "accessory_price" | "qty" | "remove_accessory"
    label: str                         # nome exibido ao vendedor
    packaging_type: str                # "goodpack" | "competitor"
    goodpack_sku_id: _Optional[int] = None
    competitor_unit_id: _Optional[int] = None
    accessory_type_id: _Optional[int] = None
    value: _Optional[float] = None     # novo preço (None para remove_accessory)
    qty_field: _Optional[str] = None   # "qty_40ft_dry" etc (para type=qty)
    currency: str = "USD"
    region: str = "GLOBAL"

class KBApplyOfferPayload(_BaseModel):
    items: _List[KBOfferItem]


@router.post("/apply-offer")
async def apply_kb_offer(payload: KBApplyOfferPayload, db: AsyncSession = Depends(get_db)):
    """
    Recebe os itens que o vendedor confirmou no painel KB_OFFER e persiste
    cada um na base de conhecimento, seguindo o mesmo padrão de update
    dos endpoints de KB existentes.
    """
    from app.db.models import GoodpackSku, CompetitorUnit
    saved = []
    skipped = []

    for item in payload.items:

        # --- Atualiza qty de container (GoodpackSku ou CompetitorUnit) ---
        if item.type == "qty" and item.qty_field and item.value is not None:
            if item.packaging_type == "goodpack" and item.goodpack_sku_id:
                sku = await db.get(GoodpackSku, item.goodpack_sku_id)
                if sku and hasattr(sku, item.qty_field):
                    setattr(sku, item.qty_field, int(item.value))
                    saved.append(item.label)
                else:
                    skipped.append(item.label)
            elif item.packaging_type == "competitor" and item.competitor_unit_id:
                unit = await db.get(CompetitorUnit, item.competitor_unit_id)
                if unit and hasattr(unit, item.qty_field):
                    setattr(unit, item.qty_field, int(item.value))
                    saved.append(item.label)
                else:
                    skipped.append(item.label)
            continue

        # --- Remove acessório da estrutura padrão ---
        if item.type == "remove_accessory" and item.accessory_type_id:
            q = select(PackagingAccessory).where(
                PackagingAccessory.is_current == True,
                PackagingAccessory.accessory_type_id == item.accessory_type_id,
            )
            if item.goodpack_sku_id:
                q = q.where(PackagingAccessory.goodpack_sku_id == item.goodpack_sku_id)
            if item.competitor_unit_id:
                q = q.where(PackagingAccessory.competitor_unit_id == item.competitor_unit_id)
            rows = (await db.execute(q)).scalars().all()
            for row in rows:
                row.is_current = False
            saved.append(f"Removido: {item.label}")
            continue

        # --- Atualiza preço de acessório ---
        if item.type == "accessory_price" and item.accessory_type_id and item.value is not None:
            q = select(PackagingAccessory).where(
                PackagingAccessory.is_current == True,
                PackagingAccessory.accessory_type_id == item.accessory_type_id,
            )
            if item.goodpack_sku_id:
                q = q.where(PackagingAccessory.goodpack_sku_id == item.goodpack_sku_id)
            if item.competitor_unit_id:
                q = q.where(PackagingAccessory.competitor_unit_id == item.competitor_unit_id)
            rows = (await db.execute(q)).scalars().all()
            if rows:
                for row in rows:
                    row.default_unit_price = item.value
                    row.confidence_level = "high"
                    row.collected_at = date.today()
                saved.append(item.label)
            else:
                skipped.append(item.label)
            continue

        skipped.append(item.label)

    await db.commit()
    return {"saved": saved, "skipped": skipped}
