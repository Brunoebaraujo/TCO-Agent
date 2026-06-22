"""
express_resolver.py — Resolução determinística dos dados do TCO Express.

Substitui as 4-6 tool calls que o agente faria (get_packaging_specs × 2,
get_packaging_accessories × 2, get_product_density, get_handling_benchmarks)
por lookups diretos em Python antes de chamar o LLM.

O LLM recebe um único prompt com todos os dados já resolvidos e só precisa:
  1. Gerar a narrativa (customer_name, product_name, assumptions em texto)
  2. Formatar o TCO_RESULT_SCHEMA com os valores calculados

Eliminação esperada: 4-6 tool calls ≈ 2.000-4.000 tokens por TCO Express.
"""
from __future__ import annotations
import math
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    GoodpackSKU, CompetitorUnit, PackagingAccessory, AccessoryType,
    ProductType, Product, HandlingParameterType, HandlingBenchmark,
)
from app.calculator.engine import calculate_tco


async def _get_packaging_specs(db: AsyncSession, packaging_type: str, name: str) -> dict | None:
    if packaging_type == "goodpack":
        obj = (await db.execute(select(GoodpackSKU).where(GoodpackSKU.sku_code == name))).scalar_one_or_none()
    else:
        obj = (await db.execute(select(CompetitorUnit).where(CompetitorUnit.unit_name == name))).scalar_one_or_none()
    if not obj:
        return None
    return {
        "volume_liters": float(obj.volume_liters) if obj.volume_liters else None,
        "max_payload_kg": float(obj.max_payload_kg) if obj.max_payload_kg else None,
        "tare_weight_kg": float(obj.tare_weight_kg) if obj.tare_weight_kg else None,
        "stack_full_warehouse": getattr(obj, "stack_full_warehouse", None),
        "stack_full_transit": getattr(obj, "stack_full_transit", None),
        "qty_20ft_dry": getattr(obj, "qty_20ft_dry", None),
        "qty_40ft_dry": getattr(obj, "qty_40ft_dry", None),
        "qty_40ft_hc_dry": getattr(obj, "qty_40ft_hc_dry", None),
    }


async def _get_accessories(
    db: AsyncSession, packaging_type: str, name: str,
    product_name: str | None, type_name: str | None, region: str
) -> list[dict]:
    if packaging_type == "goodpack":
        obj = (await db.execute(select(GoodpackSKU).where(GoodpackSKU.sku_code == name))).scalar_one_or_none()
        pkg_filter = PackagingAccessory.goodpack_sku_id == obj.id if obj else None
    else:
        obj = (await db.execute(select(CompetitorUnit).where(CompetitorUnit.unit_name == name))).scalar_one_or_none()
        pkg_filter = PackagingAccessory.competitor_unit_id == obj.id if obj else None

    if not obj or pkg_filter is None:
        return []

    items = (await db.execute(
        select(PackagingAccessory)
        .where(PackagingAccessory.is_current == True)
        .where(pkg_filter)
    )).scalars().all()

    acc_names = {a.id: a.accessory_name for a in (await db.execute(select(AccessoryType))).scalars().all()}
    product_types = {t.id: t for t in (await db.execute(select(ProductType))).scalars().all()}
    products = {p.id: p for p in (await db.execute(select(Product))).scalars().all()}

    # Resolve product_type_id alvo para filtrar acessórios específicos
    target_pt_id = None
    if product_name and type_name:
        for t in product_types.values():
            p = products.get(t.product_id)
            if (p and p.product_name.lower() == product_name.lower()
                    and t.type_name.lower() == type_name.lower()):
                target_pt_id = t.id
                break

    # Filtra: acessórios genéricos (product_type_id=None) +
    #         acessórios específicos para este produto/tipo (se existirem)
    relevant = [i for i in items if i.product_type_id is None or i.product_type_id == target_pt_id]

    # Regional fallback por (accessory_type_id, product_type_id)
    region_upper = (region or "GLOBAL").upper()
    grouped: dict[tuple, list] = defaultdict(list)
    for item in relevant:
        grouped[(item.accessory_type_id, item.product_type_id)].append(item)

    result = []
    for (acc_type_id, pt_id), candidates in grouped.items():
        chosen = (
            next((c for c in candidates if (c.region or "GLOBAL").upper() == region_upper), None)
            or next((c for c in candidates if (c.region or "GLOBAL").upper() == "GLOBAL"), None)
            or candidates[0]
        )
        result.append({
            "label": acc_names.get(acc_type_id, "?"),
            "value": float(chosen.default_unit_price) if chosen.default_unit_price else None,
            "confidence_level": chosen.confidence_level,
            "region": chosen.region or "GLOBAL",
        })
    return result


async def _get_density(db: AsyncSession, product_name: str, type_name: str | None) -> dict | None:
    query = (
        select(ProductType)
        .join(Product, ProductType.product_id == Product.id)
        .where(Product.product_name.ilike(product_name))
    )
    if type_name:
        query = query.where(ProductType.type_name.ilike(type_name))
    rows = (await db.execute(query)).scalars().all()
    if not rows:
        return None
    # Se há um único resultado, usa direto; se múltiplos e sem type_name, usa o primeiro
    row = rows[0]
    return {
        "density_kg_per_liter": float(row.density_kg_per_liter) if row.density_kg_per_liter else None,
        "type_name": row.type_name,
        "confidence_level": row.density_confidence,
    }


async def _get_handling_benchmarks(db: AsyncSession, region: str) -> dict:
    params = (await db.execute(
        select(HandlingParameterType).where(HandlingParameterType.active == True)
    )).scalars().all()

    benchmarks: dict[str, float] = {}
    region_upper = (region or "GLOBAL").upper()

    for p in params:
        value = None
        for candidate in filter(None, [region_upper, "GLOBAL"]):
            bq = select(HandlingBenchmark).where(
                HandlingBenchmark.param_key == p.param_key,
                HandlingBenchmark.region_code == candidate,
                HandlingBenchmark.competitor_unit_id.is_(None),
                HandlingBenchmark.is_current == True,
            )
            bm = (await db.execute(bq)).scalar_one_or_none()
            if bm:
                value = float(bm.value)
                break
        if value is not None:
            benchmarks[p.param_key] = value

    return benchmarks


def _infer_transport_qty(specs: dict, transport_type: str) -> int | None:
    """Infere qty por container a partir das specs físicas e do tipo de transporte."""
    if not specs:
        return None
    t = (transport_type or "").lower()
    if "20" in t:
        return specs.get("qty_20ft_dry")
    elif "40hc" in t or "40 hc" in t or "high" in t:
        return specs.get("qty_40ft_hc_dry")
    elif "40" in t:
        return specs.get("qty_40ft_dry")
    # Fallback: maior dos valores disponíveis (assume container padrão)
    candidates = [specs.get("qty_40ft_dry"), specs.get("qty_20ft_dry"), specs.get("qty_40ft_hc_dry")]
    return next((v for v in candidates if v), None)


async def resolve_express(
    db: AsyncSession,
    *,
    goodpack_sku: str,
    competitor_name: str,
    product_name: str,
    type_name: str | None,
    origin: str,
    destination: str,
    goodpack_unit_price: float,
    competitor_unit_price: float,
    freight_per_container: float,
    volume_mt: float,
    lease_days: int,
    region: str = "GLOBAL",
) -> dict:
    """
    Resolve todos os dados necessários para o TCO Express diretamente do DB,
    calcula o TCO deterministicamente, e retorna um dict com:
      - tco_result: resultado calculado pelo engine
      - resolved_data: dados intermediários para o LLM montar a narrativa
      - warnings: campos ausentes ou com baixa confiança
    """
    warnings = []

    # 1. Specs das embalagens
    gp_specs = await _get_packaging_specs(db, "goodpack", goodpack_sku)
    comp_specs = await _get_packaging_specs(db, "competitor", competitor_name)

    if not gp_specs:
        warnings.append(f"Specs do {goodpack_sku} não encontradas na base — campos físicos ausentes.")
        gp_specs = {}
    if not comp_specs:
        warnings.append(f"Specs de '{competitor_name}' não encontradas na base — campos físicos ausentes.")
        comp_specs = {}

    # 2. Densidade do produto
    density_data = await _get_density(db, product_name, type_name)
    density = density_data["density_kg_per_liter"] if density_data else None
    if density is None:
        warnings.append(f"Densidade de '{product_name}' não encontrada — cálculo de units_needed pode estar impreciso.")
    if density_data and density_data.get("confidence_level") == "validation_required":
        warnings.append(f"Densidade de '{product_name}' é estimativa — confirmar com o cliente.")

    # 3. Acessórios
    gp_accessories = await _get_accessories(db, "goodpack", goodpack_sku, product_name, type_name, region)
    comp_accessories = await _get_accessories(db, "competitor", competitor_name, product_name, type_name, region)

    for acc in gp_accessories + comp_accessories:
        if acc["value"] is None:
            warnings.append(f"Preço do acessório '{acc['label']}' não cadastrado — validar com o cliente.")
        elif acc.get("confidence_level") == "validation_required":
            warnings.append(f"Preço do acessório '{acc['label']}' é estimativa ({acc['region']}) — confirmar com o cliente.")

    # 4. Handling benchmarks
    handling = await _get_handling_benchmarks(db, region)

    # 5. Qty por container (inferido das specs + tipo de transporte)
    # O tipo de transporte não vem no Express Form — usa qty_40ft_dry como padrão
    gp_qty_transport = _infer_transport_qty(gp_specs, "40ft")
    comp_qty_transport = _infer_transport_qty(comp_specs, "40ft")

    # 6. Calcula TCO
    engine_accessories_gp = [{"label": a["label"], "value": a["value"]} for a in gp_accessories]
    engine_accessories_comp = [{"label": a["label"], "value": a["value"]} for a in comp_accessories]

    tco_result = calculate_tco(
        goodpack_specs=gp_specs,
        competitor_specs=comp_specs,
        density_kg_per_liter=density,
        goodpack_unit_cost=goodpack_unit_price,
        competitor_unit_cost=competitor_unit_price,
        goodpack_accessories=engine_accessories_gp,
        competitor_accessories=engine_accessories_comp,
        handling_benchmarks=handling,
        transport_cost_per_container=freight_per_container,
        transport_qty_per_container_goodpack=gp_qty_transport,
        transport_qty_per_container_competitor=comp_qty_transport,
        simulated_metric_tonnes=volume_mt,
    )

    return {
        "tco_engine_result": tco_result,
        "resolved": {
            "goodpack_sku": goodpack_sku,
            "competitor_name": competitor_name,
            "product_name": product_name,
            "type_name": type_name,
            "origin": origin,
            "destination": destination,
            "volume_mt": volume_mt,
            "lease_days": lease_days,
            "region": region,
            "goodpack_unit_price": goodpack_unit_price,
            "competitor_unit_price": competitor_unit_price,
            "freight_per_container": freight_per_container,
            "density": density,
            "gp_accessories": gp_accessories,
            "comp_accessories": comp_accessories,
            "gp_qty_transport": gp_qty_transport,
            "comp_qty_transport": comp_qty_transport,
        },
        "warnings": warnings,
    }
