"""
Motor de cálculo determinístico do TCO.

Antes desse módulo, todo o cálculo (Handling, Logistics, Packaging, totais)
era feito pelo próprio modelo de linguagem em texto livre, sem nenhuma
verificação — risco real de erro de aritmética em fórmulas compostas de
vários passos. Este módulo faz a conta de verdade em Python; o agente só
decide QUAIS valores usar (benchmark vs. informado pelo vendedor) e chama
calculate_tco() com eles.

Todas as funções são puras (sem I/O, sem banco) — fáceis de testar.
"""
import math
from typing import Optional


def _num(value, default=0.0):
    """Converte para float com segurança, tratando None/ausente como default."""
    return float(value) if value is not None else default


def compute_handling_packer(benchmarks: dict, stack_full_warehouse: Optional[int]) -> float:
    """Handling Packer = Storage + Assembly + Stacking + Loading, por unidade."""
    g = lambda key: _num(benchmarks.get(f"packer_{key}"))

    storage = (g("storage_cost_per_month_stack") * g("storage_time_months")) / stack_full_warehouse if stack_full_warehouse else 0.0
    assembly_rate = g("assembly_units_per_hour")
    assembly = (g("assembly_manpower") * g("labor_cost_per_hour")) / assembly_rate if assembly_rate else 0.0
    stacking = g("stacking_manpower") * g("labor_cost_per_hour") * g("stacking_time_minutes") / 60
    loading = g("loading_manpower") * g("labor_cost_per_hour") * g("loading_time_minutes") / 60

    return storage + assembly + stacking + loading


def compute_handling_enduser(benchmarks: dict, stack_full_warehouse: Optional[int]) -> float:
    """
    Handling Enduser = Storage + Disassembly + Remove Trash + Stacking Full +
    Stacking Empty + Unloading, por unidade.

    NOTA: 'remove_trash' não tem parâmetro de manpower cadastrado
    (handling_parameter_types só tem enduser_remove_trash_minutes) — assume
    1 pessoa nessa etapa. Se um manpower dedicado for cadastrado no futuro,
    ajustar aqui.
    """
    g = lambda key: _num(benchmarks.get(f"enduser_{key}"))

    storage = (g("storage_cost_per_month_stack") * g("storage_time_months")) / stack_full_warehouse if stack_full_warehouse else 0.0
    disassembly_rate = g("disassembly_units_per_hour")
    disassembly = (g("disassembly_manpower") * g("labor_cost_per_hour")) / disassembly_rate if disassembly_rate else 0.0
    remove_trash = 1 * g("labor_cost_per_hour") * g("remove_trash_minutes") / 60
    stacking_full = g("stacking_full_manpower") * g("labor_cost_per_hour") * g("stacking_full_minutes") / 60
    stacking_empty = g("stacking_empty_manpower") * g("labor_cost_per_hour") * g("stacking_empty_minutes") / 60
    unloading = g("unloading_manpower") * g("labor_cost_per_hour") * g("unloading_minutes") / 60

    return storage + disassembly + remove_trash + stacking_full + stacking_empty + unloading


def compute_qty_real_per_unit_kg(max_payload_kg: Optional[float], density_kg_per_liter: Optional[float],
                                  volume_liters: Optional[float]) -> Optional[float]:
    """
    Carga real por unidade = MIN(peso nominal da embalagem, densidade × volume).
    Produto de baixa densidade enche o volume antes de bater no peso nominal —
    usar só max_payload_kg superestima quanto cabe por unidade.
    """
    candidates = []
    if max_payload_kg is not None:
        candidates.append(float(max_payload_kg))
    if density_kg_per_liter is not None and volume_liters is not None:
        candidates.append(float(density_kg_per_liter) * float(volume_liters))
    return min(candidates) if candidates else None


def compute_logistics(simulated_metric_tonnes: float, qty_real_per_unit_kg: Optional[float],
                       qty_per_transport: Optional[int], stack_full_warehouse: Optional[int],
                       tare_weight_kg: Optional[float]) -> dict:
    """Retorna units_needed, transports_needed, pallet_places, full_stacks, weight_per_container_kg."""
    if not qty_real_per_unit_kg or qty_real_per_unit_kg <= 0:
        return {"units_needed": None, "transports_needed": None, "pallet_places": None,
                "full_stacks": None, "weight_per_container_kg": None}

    total_kg = float(simulated_metric_tonnes) * 1000
    units_needed = math.ceil(total_kg / qty_real_per_unit_kg)

    transports_needed = math.ceil(units_needed / qty_per_transport) if qty_per_transport else None
    full_stacks = math.ceil(units_needed / stack_full_warehouse) if stack_full_warehouse else None
    pallet_places = units_needed

    weight_per_container_kg = None
    if qty_per_transport and tare_weight_kg is not None:
        weight_per_container_kg = round((qty_real_per_unit_kg + float(tare_weight_kg)) * qty_per_transport, 1)

    return {
        "units_needed": units_needed,
        "transports_needed": transports_needed,
        "pallet_places": pallet_places,
        "full_stacks": full_stacks,
        "weight_per_container_kg": weight_per_container_kg,
    }


def compute_packaging_breakdown(unit_cost: float, accessories: list[dict]) -> tuple[list[dict], float]:
    """
    accessories: [{"label": str, "value": number|None}]. None vira 0 (sem
    default cadastrado, assumido pendente de confirmação pelo chamador).
    Retorna (breakdown completo com Unit cost incluído, soma total por unidade).
    """
    breakdown = [{"label": "Unit cost", "value": round(_num(unit_cost), 2)}]
    for acc in accessories:
        breakdown.append({"label": acc["label"], "value": round(_num(acc.get("value")), 2)})
    total = sum(item["value"] for item in breakdown)
    return breakdown, round(total, 2)


def per_mt(value_per_unit: float, qty_real_per_unit_kg: Optional[float]) -> float:
    """Converte custo por unidade em custo por MT, usando a carga real por unidade."""
    if not qty_real_per_unit_kg or qty_real_per_unit_kg <= 0:
        return 0.0
    return round(value_per_unit * 1000 / qty_real_per_unit_kg, 4)


def calculate_tco(
    *,
    goodpack_specs: dict,
    competitor_specs: dict,
    density_kg_per_liter: Optional[float],
    goodpack_unit_cost: float,
    competitor_unit_cost: float,
    goodpack_accessories: list[dict],
    competitor_accessories: list[dict],
    handling_benchmarks: dict,
    transport_cost_per_container: float,
    transport_qty_per_container_goodpack: Optional[int],
    transport_qty_per_container_competitor: Optional[int],
    simulated_metric_tonnes: float,
    goodpack_empty_mgmt_per_mt: float = 0.0,
    competitor_empty_mgmt_per_mt: float = 0.0,
    investment_goodpack: Optional[float] = None,
    investment_competitor: Optional[float] = None,
) -> dict:
    """
    Calcula o TCO completo de forma determinística. Todos os valores de
    entrada já devem estar resolvidos pelo agente (benchmark ou informado
    pelo vendedor) — esta função só faz a conta, não decide qual fonte usar.

    handling_benchmarks: dict {param_key: value} cobrindo packer_* e
    enduser_* — mesmo valor aplicado aos dois lados (Goodpack e
    concorrente), que é como o benchmark está modelado hoje (não há
    parâmetro de handling diferente por lado, só por região/produto).

    Retorna a estrutura pronta para popular o TCO_RESULT (exceto campos
    narrativos como customer_name, product_name e assumptions, que ficam
    a cargo do agente).
    """
    gp_qty_kg = compute_qty_real_per_unit_kg(
        goodpack_specs.get("max_payload_kg"), density_kg_per_liter, goodpack_specs.get("volume_liters")
    )
    comp_qty_kg = compute_qty_real_per_unit_kg(
        competitor_specs.get("max_payload_kg"), density_kg_per_liter, competitor_specs.get("volume_liters")
    )

    gp_breakdown, gp_packaging_per_unit = compute_packaging_breakdown(goodpack_unit_cost, goodpack_accessories)
    comp_breakdown, comp_packaging_per_unit = compute_packaging_breakdown(competitor_unit_cost, competitor_accessories)

    handling_packer_per_unit = compute_handling_packer(handling_benchmarks, goodpack_specs.get("stack_full_warehouse"))
    handling_enduser_per_unit = compute_handling_enduser(handling_benchmarks, goodpack_specs.get("stack_full_warehouse"))
    # Mesma fórmula de handling pro lado concorrente, mas com o stack_full_warehouse DELE
    # (a embalagem física determina quantas cabem por stack, o resto do benchmark é igual).
    comp_handling_packer_per_unit = compute_handling_packer(handling_benchmarks, competitor_specs.get("stack_full_warehouse"))
    comp_handling_enduser_per_unit = compute_handling_enduser(handling_benchmarks, competitor_specs.get("stack_full_warehouse"))

    gp_transport_per_unit = (
        transport_cost_per_container / transport_qty_per_container_goodpack
        if transport_qty_per_container_goodpack else 0.0
    )
    comp_transport_per_unit = (
        transport_cost_per_container / transport_qty_per_container_competitor
        if transport_qty_per_container_competitor else 0.0
    )

    categories = [
        {
            "label": "Packaging",
            "goodpack": per_mt(gp_packaging_per_unit, gp_qty_kg),
            "competitor": per_mt(comp_packaging_per_unit, comp_qty_kg),
            "goodpack_per_unit": gp_packaging_per_unit,
            "competitor_per_unit": comp_packaging_per_unit,
        },
        {
            "label": "Handling packer",
            "goodpack": per_mt(handling_packer_per_unit, gp_qty_kg),
            "competitor": per_mt(comp_handling_packer_per_unit, comp_qty_kg),
            "goodpack_per_unit": round(handling_packer_per_unit, 2),
            "competitor_per_unit": round(comp_handling_packer_per_unit, 2),
        },
        {
            "label": "Transport",
            "goodpack": per_mt(gp_transport_per_unit, gp_qty_kg),
            "competitor": per_mt(comp_transport_per_unit, comp_qty_kg),
            "goodpack_per_unit": round(gp_transport_per_unit, 2),
            "competitor_per_unit": round(comp_transport_per_unit, 2),
        },
        {
            "label": "Handling enduser",
            "goodpack": per_mt(handling_enduser_per_unit, gp_qty_kg),
            "competitor": per_mt(comp_handling_enduser_per_unit, comp_qty_kg),
            "goodpack_per_unit": round(handling_enduser_per_unit, 2),
            "competitor_per_unit": round(comp_handling_enduser_per_unit, 2),
        },
        {
            "label": "Empty container mgmt",
            "goodpack": round(goodpack_empty_mgmt_per_mt, 4),
            "competitor": round(competitor_empty_mgmt_per_mt, 4),
            "goodpack_per_unit": 0,
            "competitor_per_unit": 0,
        },
    ]

    goodpack_total_per_mt = round(sum(c["goodpack"] for c in categories), 4)
    competitor_total_per_mt = round(sum(c["competitor"] for c in categories), 4)
    goodpack_total_per_unit = round(sum(c["goodpack_per_unit"] for c in categories), 2)
    competitor_total_per_unit = round(sum(c["competitor_per_unit"] for c in categories), 2)

    saving_per_mt = competitor_total_per_mt - goodpack_total_per_mt
    total_saving = round(saving_per_mt * float(simulated_metric_tonnes), 2)
    saving_percentage = round((saving_per_mt / competitor_total_per_mt) * 100, 2) if competitor_total_per_mt else 0.0

    logistics_goodpack = compute_logistics(
        simulated_metric_tonnes, gp_qty_kg, transport_qty_per_container_goodpack,
        goodpack_specs.get("stack_full_warehouse"), goodpack_specs.get("tare_weight_kg"),
    )
    logistics_competitor = compute_logistics(
        simulated_metric_tonnes, comp_qty_kg, transport_qty_per_container_competitor,
        competitor_specs.get("stack_full_warehouse"), competitor_specs.get("tare_weight_kg"),
    )

    # Subtotals: separa embalagem+frete do handling para uso no gráfico e PPTX.
    # Handling diferenciado por SKU está previsto para onda futura; por ora o
    # mesmo benchmark é aplicado aos dois lados.
    gp_packaging_freight_per_mt = round(
        per_mt(gp_packaging_per_unit, gp_qty_kg) + per_mt(gp_transport_per_unit, gp_qty_kg), 4
    )
    comp_packaging_freight_per_mt = round(
        per_mt(comp_packaging_per_unit, comp_qty_kg) + per_mt(comp_transport_per_unit, comp_qty_kg), 4
    )
    gp_handling_per_mt = round(
        per_mt(handling_packer_per_unit, gp_qty_kg) + per_mt(handling_enduser_per_unit, gp_qty_kg), 4
    )
    comp_handling_per_mt = round(
        per_mt(comp_handling_packer_per_unit, comp_qty_kg) + per_mt(comp_handling_enduser_per_unit, comp_qty_kg), 4
    )

    subtotals = {
        "goodpack": {
            "packaging_and_freight": gp_packaging_freight_per_mt,
            "handling": gp_handling_per_mt,
        },
        "competitor": {
            "packaging_and_freight": comp_packaging_freight_per_mt,
            "handling": comp_handling_per_mt,
        },
    }

    result = {
        "subtotals": subtotals,
        "categories": categories,
        "packaging_breakdown": gp_breakdown,
        "competitor_packaging_breakdown": comp_breakdown,
        "handling_benchmarks": handling_benchmarks,
        "goodpack_qty_per_unit_kg": gp_qty_kg,
        "goodpack_qty_per_transport": transport_qty_per_container_goodpack,
        "goodpack_stack_full_warehouse": goodpack_specs.get("stack_full_warehouse"),
        "goodpack_transport_cost_per_container": transport_cost_per_container,
        "goodpack_volume_liters": goodpack_specs.get("volume_liters"),
        "goodpack_max_payload_kg": goodpack_specs.get("max_payload_kg"),
        "goodpack_tare_weight_kg": goodpack_specs.get("tare_weight_kg"),
        "competitor_qty_per_unit_kg": comp_qty_kg,
        "competitor_qty_per_transport": transport_qty_per_container_competitor,
        "competitor_stack_full_warehouse": competitor_specs.get("stack_full_warehouse"),
        "competitor_volume_liters": competitor_specs.get("volume_liters"),
        "competitor_max_payload_kg": competitor_specs.get("max_payload_kg"),
        "competitor_tare_weight_kg": competitor_specs.get("tare_weight_kg"),
        "goodpack_total_per_mt": goodpack_total_per_mt,
        "competitor_total_per_mt": competitor_total_per_mt,
        "goodpack_total_per_unit": goodpack_total_per_unit,
        "competitor_total_per_unit": competitor_total_per_unit,
        "total_saving": total_saving,
        "saving_percentage": saving_percentage,
        "logistics": {"goodpack": logistics_goodpack, "competitor": logistics_competitor},
    }

    if investment_goodpack is not None or investment_competitor is not None:
        result["investment"] = {
            "goodpack_investment_required": investment_goodpack,
            "competitor_investment_required": investment_competitor,
            "goodpack_payback_cycles": (
                round(investment_goodpack / total_saving, 2)
                if investment_goodpack is not None and total_saving else None
            ),
            "competitor_payback_cycles": (
                round(investment_competitor / total_saving, 2)
                if investment_competitor is not None and total_saving else None
            ),
        }

    return result
