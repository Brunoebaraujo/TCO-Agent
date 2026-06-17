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
    ProductCatalog, AccessoryType, PackagingAccessory,
)

router = APIRouter()


# -------------------------------------------------------------
# SKUs Goodpack (somente leitura por agora — specs vêm dos TDS oficiais)
# -------------------------------------------------------------

@router.get("/skus")
async def list_skus(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GoodpackSKU).where(GoodpackSKU.active == True))
    skus = result.scalars().all()
    return {"skus": [
        {
            "id": s.id, "sku_code": s.sku_code, "description": s.description,
            "volume_liters": float(s.volume_liters), "max_payload_kg": float(s.max_payload_kg),
        }
        for s in skus
    ]}


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
# Catálogo de produtos
# -------------------------------------------------------------

class ProductIn(BaseModel):
    product_name: str
    category_code: str | None = None
    category_name: str | None = None
    notes: str | None = None


@router.get("/products")
async def list_products(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProductCatalog).where(ProductCatalog.active == True))
    products = result.scalars().all()
    return {"products": [
        {"id": p.id, "product_name": p.product_name, "category_code": p.category_code,
         "category_name": p.category_name}
        for p in products
    ]}


@router.post("/products")
async def create_product(payload: ProductIn, db: AsyncSession = Depends(get_db)):
    product = ProductCatalog(**payload.model_dump())
    db.add(product)
    await db.flush()
    return {"id": product.id}


@router.delete("/products/{product_id}")
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(ProductCatalog, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    product.active = False
    return {"deleted": True}


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
    product_id: int | None = None  # None = default genérico da embalagem
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
    products = {p.id: p.product_name for p in (await db.execute(select(ProductCatalog))).scalars().all()}

    return {"packaging_accessories": [
        {
            "id": pa.id,
            "packaging_type": pa.packaging_type,
            "goodpack_sku_id": pa.goodpack_sku_id,
            "competitor_unit_id": pa.competitor_unit_id,
            "product_id": pa.product_id,
            "product_name": products.get(pa.product_id) if pa.product_id else None,
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
