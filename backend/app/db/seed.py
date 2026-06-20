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
    AccessoryType, PackagingAccessory, Region, TransportType,
    HandlingParameterType, HandlingBenchmark,
)

GOODPACK_SKUS = [
    dict(sku_code="MB3", description="Stackable steel container — 1.40 m³",
         volume_liters=1400, max_payload_kg=1550, tare_weight_kg=124,
         stack_full_warehouse=4, stack_empty_warehouse=80, stack_full_transit=2,
         qty_20ft_dry=16, qty_40ft_dry=32, qty_40ft_hc_dry=32,
         special_features="Stacking flaps for stacking",
         tds_document_ref="GP TDS MB3 May02/2021"),
    dict(sku_code="MB4", description="Stackable steel container — 1.40 m³",
         volume_liters=1400, max_payload_kg=1550, tare_weight_kg=120,
         stack_full_warehouse=4, stack_empty_warehouse=72, stack_full_transit=2,
         qty_20ft_dry=16, qty_40ft_dry=32, qty_40ft_hc_dry=32,
         special_features="Single-sided bottom discharge hole, stacking flaps for stacking",
         tds_document_ref="GP TDS MB4 Mar24/2022"),
    dict(sku_code="MB5", description="Stackable steel container — 1.60 m³",
         volume_liters=1600, max_payload_kg=1650, tare_weight_kg=132,
         stack_full_warehouse=5, stack_empty_warehouse=96, stack_full_transit=2,
         qty_20ft_dry=16, qty_40ft_dry=32,
         is_collapsible=True, special_features="Removable sidewall",
         tds_document_ref="GP TDS MB5 May02/2021"),
    dict(sku_code="MB5H", description="Stackable steel container — 1.60 m³ — automotive components",
         volume_liters=1600, max_payload_kg=1400, tare_weight_kg=133,
         stack_full_warehouse=5, stack_empty_warehouse=96, stack_full_transit=2,
         qty_20ft_dry=16, qty_40ft_dry=32,
         is_collapsible=True, special_features="Removable sidewall, foldable half-sidewall",
         tds_document_ref="GP TDS MB5H May03/2021"),
    dict(sku_code="MB6", description="Stackable steel container — 1.25 m³",
         volume_liters=1250, max_payload_kg=1650, tare_weight_kg=115,
         stack_full_warehouse=5, stack_empty_warehouse=80, stack_full_transit=2,
         qty_20ft_dry=16, qty_40ft_dry=36, qty_40ft_hc_dry=198,
         is_collapsible=True, special_features="Integrated lid, removable sidewalls (all four)",
         tds_document_ref="GP TDS MB6 Feb27/2023"),
    dict(sku_code="MB12", description="Stackable steel container — 728 L — automotive industry",
         volume_liters=728, max_payload_kg=900, tare_weight_kg=65,
         stack_full_warehouse=6, stack_empty_warehouse=90, stack_full_transit=3,
         qty_20ft_dry=20, qty_40ft_dry=48, qty_40ft_hc_dry=72,
         is_collapsible=True,
         special_features="Two removable sidewalls (one foldable), 2-part folding lid, two document pouches. Limited availability.",
         tds_document_ref="GP TDS MB12 May03/2021"),
]

COMPETITOR_UNITS = [
    dict(unit_name="Octabin", unit_type="bin",
         volume_liters=1000, max_payload_kg=1200, tare_weight_kg=29,
         qty_20ft_dry=20, qty_40ft_dry=40, qty_20ft_reefer=20, qty_40ft_reefer=40,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026)", specs_confidence="high_confidence"),
    # Drum 200L é o mesmo container físico que "Cylindrical Drum" (200L, mesma
    # fonte) sob um nome legado anterior ao levantamento de specs — specs e
    # confiança copiadas de lá como proxy até confirmar se vale unificar os
    # dois cadastros num só.
    dict(unit_name="Drum 200L", unit_type="drum",
         volume_liters=200, max_payload_kg=275, tare_weight_kg=16,
         qty_20ft_dry=78, qty_40ft_dry=152, qty_20ft_reefer=70, qty_40ft_reefer=150,
         specs_source="Proxy de 'Cylindrical Drum' (mesmo container, 200L) — Info_Packages.xlsx", specs_confidence="validation_required"),
    dict(unit_name="Blue Ocean Container 1000",
         volume_liters=1000, max_payload_kg=1250, tare_weight_kg=20,
         qty_20ft_dry=20, qty_40ft_dry=40, qty_20ft_reefer=20, qty_40ft_reefer=40,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026)", specs_confidence="high_confidence"),
    dict(unit_name="Blue Ocean Container 1250",
         volume_liters=1250, max_payload_kg=1500, tare_weight_kg=24,
         qty_20ft_dry=20, qty_40ft_dry=40, qty_20ft_reefer=20, qty_40ft_reefer=40,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026)", specs_confidence="high_confidence"),
    dict(unit_name="Bottle in cage",
         volume_liters=1250, max_payload_kg=1500, tare_weight_kg=70,
         qty_20ft_dry=16, qty_40ft_dry=38, qty_20ft_reefer=16, qty_40ft_reefer=38,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026) — variante 'Large'", specs_confidence="high_confidence"),
    dict(unit_name="Conical Drum",
         volume_liters=227, max_payload_kg=275, tare_weight_kg=17,
         qty_20ft_dry=78, qty_40ft_dry=156, qty_20ft_reefer=70, qty_40ft_reefer=150,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026)", specs_confidence="high_confidence"),
    dict(unit_name="Cylindrical Drum",
         volume_liters=200, max_payload_kg=275, tare_weight_kg=16,
         qty_20ft_dry=78, qty_40ft_dry=152, qty_20ft_reefer=70, qty_40ft_reefer=150,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026)", specs_confidence="high_confidence"),
    dict(unit_name="GPS Container",
         volume_liters=1500, max_payload_kg=1500, tare_weight_kg=115,
         qty_20ft_dry=16, qty_40ft_dry=32, qty_20ft_reefer=16, qty_40ft_reefer=32,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026)", specs_confidence="high_confidence"),
    dict(unit_name="Schoeller Arca bin",
         volume_liters=1044, max_payload_kg=1250, tare_weight_kg=90,
         qty_20ft_dry=20, qty_40ft_dry=40, qty_20ft_reefer=20, qty_40ft_reefer=40,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026)", specs_confidence="high_confidence"),
    dict(unit_name="Wooden Pallet",
         volume_liters=1260, max_payload_kg=1260, tare_weight_kg=15,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026) — sem qty/container cadastrada na fonte", specs_confidence="high_confidence"),
    dict(unit_name="Plastic Pallet",
         volume_liters=1260, max_payload_kg=1260, tare_weight_kg=25,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026) — sem qty/container cadastrada na fonte", specs_confidence="high_confidence"),
    dict(unit_name="Wooden Bin",
         volume_liters=1150, max_payload_kg=1540, tare_weight_kg=126,
         qty_20ft_dry=16, qty_40ft_dry=36, qty_20ft_reefer=16, qty_40ft_reefer=36,
         specs_source="Info_Packages.xlsx (upload Bruno, 19/06/2026) — variante 126KG", specs_confidence="high_confidence"),
]

# Hierarquia: categoria -> {produto -> [tipos]}
PRODUCT_HIERARCHY = {
    "AJC": {
        "Apple": {
            "NFC": dict(density=1.05, confidence="validation_required",
                        notes="Single strength, ~11-12°Brix"),
            "Concentrate": dict(density=1.35, confidence="validation_required",
                                 notes="Padrão comercial ~70°Brix"),
            "Puree": dict(density=1.05, confidence="validation_required",
                          notes="Sem padrão de Brix tão fechado quanto suco"),
        },
    },
    "BNA": {
        "Banana": {
            "Puree": dict(density=1.07, confidence="validation_required",
                          notes="Mais denso por conteúdo de amido"),
        },
    },
    "CIT": {
        "Orange": {
            "NFC": dict(density=1.05, confidence="validation_required", notes="~11-12°Brix"),
            "FCOJ": dict(density=1.32, confidence="high_confidence",
                         notes="SG verificada a 65°Brix (padrão industrial)"),
            "Concentrate": dict(density=1.32, confidence="high_confidence",
                                 notes="Mesma referência de FCOJ (~65°Brix)"),
        },
        "Lemon": {
            "NFC": dict(density=1.03, confidence="validation_required",
                        notes="Single strength, Brix mais baixo que laranja"),
        },
        "Lime": {
            "NFC": dict(density=1.03, confidence="high_confidence",
                        notes="SG verificada a 8°Brix (1,0318)"),
        },
        "Grapefruit": {
            "NFC": dict(density=1.04, confidence="validation_required", notes="~10°Brix"),
        },
    },
    "GJC": {
        "Grape": {
            "Concentrate": dict(density=1.34, confidence="validation_required",
                                 notes="Padrão comercial ~68°Brix"),
        },
    },
    "KFJ": {
        "Aloe Vera": {
            "Juice": dict(density=1.01, confidence="validation_required",
                          notes="Baixo teor de sólidos, pouco padronizado"),
        },
        "Coconut": {
            "Water": dict(density=1.02, confidence="validation_required", notes="Brix baixo, ~5-6"),
        },
        "Guava": {
            "Puree": dict(density=1.05, confidence="validation_required", notes="Faixa típica de food science"),
        },
        "Kiwi": {
            "Puree": dict(density=1.05, confidence="validation_required", notes="Faixa típica de food science"),
        },
        "Peach": {
            "Puree": dict(density=1.04, confidence="validation_required", notes="Faixa típica de food science"),
        },
    },
    "MNG": {
        "Mango": {
            "Puree": dict(density=1.05, confidence="validation_required", notes="Faixa típica de food science"),
        },
    },
    "PNA": {
        "Pineapple": {
            "NFC": dict(density=1.05, confidence="validation_required", notes="~12-13°Brix"),
            "Concentrate": dict(density=1.30, confidence="validation_required",
                                 notes="Padrão comercial ~60-61°Brix"),
        },
    },
    "TJC": {
        "Tomato": {
            "Puree": dict(density=1.07, confidence="high_confidence", notes="SG verificada a 8,5°Brix"),
            "Paste": dict(density=1.12, confidence="high_confidence",
                          notes="Padrão comercial 28-30°Brix"),
            "Sauce": dict(density=1.03, confidence="validation_required",
                          notes="Produto formulado — mais variável"),
            "Diced": dict(density=1.04, confidence="validation_required",
                          notes="Pedaços sólidos + líquido — heterogêneo"),
        },
    },
    "DAY": {
        "Milk Fat": {
            "AMF": dict(density=0.91, confidence="high_confidence",
                        notes="Gordura láctea ~99,8% pura, valor bem documentado"),
        },
        "Butter": {
            "Standard": dict(density=0.94, confidence="validation_required",
                              notes="~80% gordura + água/sólidos do leite — mais variável que AMF"),
        },
        "Cheese": {
            "Block": dict(density=1.09, confidence="high_confidence",
                          notes="Densidade aparente — Cheddar industrial medido ~1,09-1,094 kg/L"),
        },
    },
    "FAO": {
        "Palm": {
            "Oil": dict(density=0.90, confidence="high_confidence", notes="Óleo vegetal — faixa bem documentada (FAO/INFOODS)"),
        },
        "Soy": {
            "Oil": dict(density=0.92, confidence="high_confidence", notes="Óleo vegetal — faixa bem documentada (FAO/INFOODS)"),
        },
        "Sunflower": {
            "Oil": dict(density=0.92, confidence="high_confidence", notes="Óleo vegetal — faixa bem documentada (FAO/INFOODS)"),
        },
        "Omega 3": {
            "Oil": dict(density=0.92, confidence="validation_required",
                        notes="Óleo de peixe — mesma ordem de grandeza dos vegetais"),
        },
        "Lecithin": {
            "Standard": dict(density=0.98, confidence="validation_required",
                              notes="Mais viscosa/densa que óleo puro"),
        },
    },
    "MSP": {
        "Water": {
            "Standard": dict(density=1.00, confidence="high_confidence", notes="Trivial"),
        },
        "Tobacco": {
            "Baled": dict(density=0.27, confidence="high_confidence",
                          notes="Densidade aparente de fardo (folha curada compactada), faixa industrial 200-330 kg/m³"),
        },
        "Olives": {
            "In Brine": dict(density=1.02, confidence="validation_required",
                             notes="Densidade aparente estimada (azeitona+salmoura, sem fonte direta medida — validar com QA)"),
        },
        "Gherkins": {
            "In Brine": dict(density=1.02, confidence="validation_required",
                             notes="Densidade aparente estimada por analogia a azeitonas — sem fonte direta medida"),
        },
    },
}

ACCESSORY_TYPES = [
    "Pallet", "Poly Liner", "Base Pad", "Aseptic Bag",
    "Strapping Cost", "Lid", "Dunnage", "Top Sheet", "FIBC", "Liquid Liner",
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
#
# Listas de MB5/MB6/Conical Drum/Cylindrical Drum/Wooden Bin expandidas em
# 20/06/2026 a partir do uso real observado em 107 TCOs históricos extraídos
# (Poly Liner, Lid, Top Sheet, Dunnage e Liquid Liner apareciam de fato nesses
# negócios mas não estavam cadastrados como vínculo — só os preços estavam
# faltando, a estrutura em si também estava incompleta).
PACKAGING_ACCESSORY_RULES = [
    ("goodpack", "MB3", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB4", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB5", None, ["Aseptic Bag", "Base Pad", "Strapping Cost", "Poly Liner", "Dunnage", "Lid", "Top Sheet"]),
    ("goodpack", "MB5H", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB6", None, ["Aseptic Bag", "Base Pad", "Strapping Cost", "Poly Liner", "Lid", "Top Sheet", "Liquid Liner"]),
    ("goodpack", "MB12", None, ["Aseptic Bag", "Base Pad", "Strapping Cost"]),
    ("goodpack", "MB6", ("Orange", "FCOJ"), ["Poly Liner"]),
    ("goodpack", "MB6", ("Orange", "NFC"), ["Aseptic Bag"]),
    ("competitor", "Drum 200L", None, ["Poly Liner", "Aseptic Bag", "Strapping Cost"]),
    ("competitor", "Octabin", None, ["Pallet", "Poly Liner", "Aseptic Bag", "Strapping Cost", "Dunnage"]),
    ("competitor", "Conical Drum", None, ["Poly Liner", "Pallet", "Strapping Cost", "Aseptic Bag"]),
    ("competitor", "Cylindrical Drum", None, ["Poly Liner", "Pallet", "Strapping Cost", "Aseptic Bag"]),
    ("competitor", "Wooden Bin", None, ["Poly Liner"]),
]

# Preço de referência (mediana, USD) por (packaging_type, sku_or_unit_name,
# accessory_name), derivado de 107 TCOs históricos reais extraídos das
# planilhas legadas (20/06/2026) — só inclui combinações com >= 5 registros
# para evitar virar "benchmark" a partir de 1-2 negócios isolados. Aplica-se
# apenas às linhas de acessório SEM produto+tipo específico (genéricas) —
# overrides por produto+tipo continuam sem preço default por design (mais
# variáveis ainda, devem ser perguntados).
# valor: (mediana_usd, contagem_amostras)
ACCESSORY_PRICE_BENCHMARKS = {
    ("goodpack", "MB5", "Aseptic Bag"): (23.00, 21),
    ("goodpack", "MB5", "Poly Liner"): (3.00, 20),
    ("goodpack", "MB5", "Base Pad"): (2.42, 16),
    ("goodpack", "MB5", "Dunnage"): (9.40, 15),
    ("goodpack", "MB5", "Strapping Cost"): (1.00, 15),
    ("goodpack", "MB5", "Lid"): (2.95, 12),
    ("goodpack", "MB5", "Top Sheet"): (2.00, 9),
    ("goodpack", "MB6", "Poly Liner"): (3.90, 65),
    ("goodpack", "MB6", "Base Pad"): (2.63, 41),
    ("goodpack", "MB6", "Strapping Cost"): (0.50, 39),
    ("goodpack", "MB6", "Lid"): (1.50, 31),
    ("goodpack", "MB6", "Aseptic Bag"): (15.00, 17),
    ("goodpack", "MB6", "Top Sheet"): (4.00, 9),
    ("goodpack", "MB6", "Liquid Liner"): (35.00, 5),
    ("competitor", "Conical Drum", "Poly Liner"): (0.50, 21),
    ("competitor", "Conical Drum", "Pallet"): (10.75, 18),
    ("competitor", "Conical Drum", "Strapping Cost"): (0.50, 18),
    ("competitor", "Conical Drum", "Aseptic Bag"): (4.00, 13),
    ("competitor", "Cylindrical Drum", "Poly Liner"): (0.75, 49),
    ("competitor", "Cylindrical Drum", "Pallet"): (10.00, 23),
    ("competitor", "Cylindrical Drum", "Strapping Cost"): (0.50, 22),
    ("competitor", "Cylindrical Drum", "Aseptic Bag"): (4.19, 14),
    ("competitor", "Octabin", "Pallet"): (12.00, 11),
    ("competitor", "Octabin", "Aseptic Bag"): (16.50, 8),
    ("competitor", "Octabin", "Strapping Cost"): (1.50, 8),
    ("competitor", "Octabin", "Poly Liner"): (3.00, 7),
    ("competitor", "Wooden Bin", "Poly Liner"): (3.55, 5),
}


TRANSPORT_TYPES = [
    dict(transport_name="20ft Dry", standard_gross_weight_limit_kg=24000, gross_weight_limit_kg=21770),
    dict(transport_name="40ft Dry", standard_gross_weight_limit_kg=30480, gross_weight_limit_kg=26000),
    dict(transport_name="40ft Reefer", standard_gross_weight_limit_kg=29260, gross_weight_limit_kg=26000),
    dict(transport_name="40ft HC Dry", standard_gross_weight_limit_kg=30480, gross_weight_limit_kg=26000),
]

# Etapas fixas de Handling, confirmadas pelo usuário (17/06/2026) como
# universais para qualquer embalagem/produto — não variam por SKU.
# role: 'packer' | 'enduser'. applies_to: 'both' (mesmo parâmetro vale para
# Goodpack e concorrente, mas com valores possivelmente diferentes — o
# benchmark é que diferencia, não o parâmetro em si).
HANDLING_PARAMETERS = [
    # --- Packer ---
    dict(param_key="packer_storage_cost_per_month_stack", param_label="Storage cost per month / stack",
         unit="USD", value_type="cost", role="packer", applies_to="both"),
    dict(param_key="packer_storage_time_months", param_label="Storage time",
         unit="months", value_type="duration", role="packer", applies_to="both"),
    dict(param_key="packer_labor_cost_per_hour", param_label="Labor cost per hour",
         unit="USD", value_type="cost", role="packer", applies_to="both"),
    dict(param_key="packer_assembly_manpower", param_label="Assembly manpower",
         unit="employees", value_type="count", role="packer", applies_to="both"),
    dict(param_key="packer_assembly_units_per_hour", param_label="Fill & assemble qty of units per hour",
         unit="units/hour", value_type="rate", role="packer", applies_to="both"),
    dict(param_key="packer_stacking_manpower", param_label="Stacking manpower",
         unit="employees", value_type="count", role="packer", applies_to="both"),
    dict(param_key="packer_stacking_time_minutes", param_label="Stacking time",
         unit="minutes", value_type="duration", role="packer", applies_to="both"),
    dict(param_key="packer_loading_manpower", param_label="Loading manpower",
         unit="employees", value_type="count", role="packer", applies_to="both"),
    dict(param_key="packer_loading_time_minutes", param_label="Loading a truck — time",
         unit="minutes", value_type="duration", role="packer", applies_to="both"),
    # --- Enduser ---
    dict(param_key="enduser_storage_cost_per_month_stack", param_label="Storage cost per month / stack",
         unit="USD", value_type="cost", role="enduser", applies_to="both"),
    dict(param_key="enduser_storage_time_months", param_label="Storage time",
         unit="months", value_type="duration", role="enduser", applies_to="both"),
    dict(param_key="enduser_labor_cost_per_hour", param_label="Labor cost per hour",
         unit="USD", value_type="cost", role="enduser", applies_to="both"),
    dict(param_key="enduser_disassembly_manpower", param_label="Disassembly manpower",
         unit="employees", value_type="count", role="enduser", applies_to="both"),
    dict(param_key="enduser_disassembly_units_per_hour", param_label="Empty & disassemble qty of units per hour",
         unit="units/hour", value_type="rate", role="enduser", applies_to="both"),
    dict(param_key="enduser_remove_trash_minutes", param_label="Remove trash — time",
         unit="minutes", value_type="duration", role="enduser", applies_to="both"),
    dict(param_key="enduser_stacking_full_manpower", param_label="Stacking full units manpower",
         unit="employees", value_type="count", role="enduser", applies_to="both"),
    dict(param_key="enduser_stacking_full_minutes", param_label="Stacking full units — time",
         unit="minutes", value_type="duration", role="enduser", applies_to="both"),
    dict(param_key="enduser_stacking_empty_manpower", param_label="Stacking empty units manpower",
         unit="employees", value_type="count", role="enduser", applies_to="both"),
    dict(param_key="enduser_stacking_empty_minutes", param_label="Stacking empty units — time",
         unit="minutes", value_type="duration", role="enduser", applies_to="both"),
    dict(param_key="enduser_unloading_manpower", param_label="Unloading manpower",
         unit="employees", value_type="count", role="enduser", applies_to="both"),
    dict(param_key="enduser_unloading_minutes", param_label="Unloading a truck — time",
         unit="minutes", value_type="duration", role="enduser", applies_to="both"),
]

# Benchmarks default (fallback) — valores da coluna "Estimation" da planilha
# de referência do usuário, aplicados globalmente (region_code GLOBAL) até
# que existam benchmarks regionais mais específicos. confidence_level
# "validation_required" porque são estimativas internas, não confirmadas
# pelo cliente — mesma lógica usada em PackagingAccessory.
HANDLING_BENCHMARKS_GLOBAL = {
    "packer_storage_cost_per_month_stack": 10.00,
    "packer_storage_time_months": 1,
    "packer_labor_cost_per_hour": 11.00,
    "packer_assembly_manpower": 1,
    "packer_assembly_units_per_hour": 10,
    "packer_stacking_manpower": 1,
    "packer_stacking_time_minutes": 20,
    "packer_loading_manpower": 1,
    "packer_loading_time_minutes": 30,
    "enduser_storage_cost_per_month_stack": 10.00,
    "enduser_storage_time_months": 2,
    "enduser_labor_cost_per_hour": 11.00,
    "enduser_disassembly_manpower": 1,
    "enduser_disassembly_units_per_hour": 4,
    "enduser_remove_trash_minutes": 2,
    "enduser_stacking_full_manpower": 1,
    "enduser_stacking_full_minutes": 20,
    "enduser_stacking_empty_manpower": 1,
    "enduser_stacking_empty_minutes": 10,
    "enduser_unloading_manpower": 1,
    "enduser_unloading_minutes": 30,
}


async def seed_initial_data(db: AsyncSession) -> None:
    # Regions
    existing_regions = (await db.execute(select(Region.region_code))).scalars().all()
    for code, name in REGIONS:
        if code not in existing_regions:
            db.add(Region(region_code=code, region_name=name))
    await db.flush()

    # Transport types
    existing_transport = (await db.execute(select(TransportType.transport_name))).scalars().all()
    for t in TRANSPORT_TYPES:
        if t["transport_name"] not in existing_transport:
            db.add(TransportType(**t))
    await db.flush()

    # Handling parameter types
    existing_params = (await db.execute(select(HandlingParameterType.param_key))).scalars().all()
    for p in HANDLING_PARAMETERS:
        if p["param_key"] not in existing_params:
            db.add(HandlingParameterType(**p))
    await db.flush()

    # Handling benchmarks — default global (fallback), um por param_key.
    # Upsert por (param_key, applies_to='both', region_code='GLOBAL',
    # competitor_unit_id=None) para permitir corrigir os valores default
    # em sessões futuras sem duplicar.
    existing_benchmarks = {
        b.param_key: b for b in (
            await db.execute(
                select(HandlingBenchmark)
                .where(HandlingBenchmark.region_code == "GLOBAL")
                .where(HandlingBenchmark.competitor_unit_id.is_(None))
            )
        ).scalars().all()
    }
    for param_key, value in HANDLING_BENCHMARKS_GLOBAL.items():
        if param_key in existing_benchmarks:
            existing_benchmarks[param_key].value = value
        else:
            db.add(HandlingBenchmark(
                param_key=param_key,
                applies_to="both",
                region_code="GLOBAL",
                value=value,
                confidence_level="validation_required",
                source_type="interno",
                source_detail="Benchmark inicial — referência de planilha interna (17/06/2026)",
                collected_at=date.today(),
            ))
    await db.flush()

    # Goodpack SKUs — upsert: atualiza specs se a SKU já existe (mantendo o
    # mesmo id, para não quebrar vínculos em packaging_accessories), cria se
    # não existir. SKUs criadas manualmente pelo usuário via UI (fora desta
    # lista) nunca são tocadas.
    existing_skus = {s.sku_code: s for s in (await db.execute(select(GoodpackSKU))).scalars().all()}
    for sku_data in GOODPACK_SKUS:
        code = sku_data["sku_code"]
        if code in existing_skus:
            sku = existing_skus[code]
            for field, value in sku_data.items():
                setattr(sku, field, value)
        else:
            db.add(GoodpackSKU(**sku_data))
    await db.flush()

    # Competitor units — upsert: mesma lógica do GoodpackSKU acima (atualiza
    # specs se já existe, mantendo id; nunca toca unidades criadas manualmente
    # fora desta lista).
    existing_units = {u.unit_name: u for u in (await db.execute(select(CompetitorUnit))).scalars().all()}
    for unit_data in COMPETITOR_UNITS:
        name = unit_data["unit_name"]
        if name in existing_units:
            unit = existing_units[name]
            for field, value in unit_data.items():
                setattr(unit, field, value)
        else:
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

    existing_type_rows = {
        (t.product_id, t.type_name): t for t in (await db.execute(select(ProductType))).scalars().all()
    }
    for category_name, products in PRODUCT_HIERARCHY.items():
        category_id = existing_categories[category_name]
        for product_name, types in products.items():
            product_id = existing_products[(category_id, product_name)]
            for type_name, info in types.items():
                key = (product_id, type_name)
                if key in existing_type_rows:
                    row = existing_type_rows[key]
                    row.density_kg_per_liter = info["density"]
                    row.density_confidence = info["confidence"]
                    row.notes = info["notes"]
                else:
                    db.add(ProductType(
                        product_id=product_id, type_name=type_name,
                        density_kg_per_liter=info["density"],
                        density_confidence=info["confidence"],
                        notes=info["notes"],
                    ))
            await db.flush()

    # Accessory types
    existing_acc_types = (await db.execute(select(AccessoryType.accessory_name))).scalars().all()
    for name in ACCESSORY_TYPES:
        if name not in existing_acc_types:
            db.add(AccessoryType(accessory_name=name))
    await db.flush()

    # Packaging <-> accessory links — verificado por embalagem específica
    # (não pela tabela inteira), para que adicionar uma SKU nova ao código
    # (ex: MB3, MB5H, MB12) continue populando seus defaults mesmo que
    # outras embalagens já tenham vínculos cadastrados/editados manualmente.
    skus_by_code = {s.sku_code: s.id for s in (await db.execute(select(GoodpackSKU))).scalars().all()}
    units_by_name = {u.unit_name: u.id for u in (await db.execute(select(CompetitorUnit))).scalars().all()}
    acc_types_by_name = {a.accessory_name: a.id for a in (await db.execute(select(AccessoryType))).scalars().all()}

    type_lookup = {}
    all_products = {p.id: p for p in (await db.execute(select(Product))).scalars().all()}
    all_types = (await db.execute(select(ProductType))).scalars().all()
    for t in all_types:
        product_name = all_products[t.product_id].product_name
        type_lookup[(product_name, t.type_name)] = t.id

    existing_pa_by_combo = {
        (pa.packaging_type, pa.goodpack_sku_id, pa.competitor_unit_id, pa.product_type_id, pa.accessory_type_id): pa
        for pa in (await db.execute(select(PackagingAccessory))).scalars().all()
    }

    for packaging_type, name, product_type_key, accessories in PACKAGING_ACCESSORY_RULES:
        goodpack_sku_id = skus_by_code.get(name) if packaging_type == "goodpack" else None
        competitor_unit_id = units_by_name.get(name) if packaging_type == "competitor" else None
        product_type_id = type_lookup.get(product_type_key) if product_type_key else None

        for accessory_name in accessories:
            accessory_type_id = acc_types_by_name.get(accessory_name)
            if not accessory_type_id:
                continue

            combo = (packaging_type, goodpack_sku_id, competitor_unit_id, product_type_id, accessory_type_id)

            # Preço de referência só se aplica a linhas genéricas (sem produto+tipo
            # específico) — overrides por produto+tipo continuam sem default por design.
            benchmark = None if product_type_key else ACCESSORY_PRICE_BENCHMARKS.get((packaging_type, name, accessory_name))

            if combo in existing_pa_by_combo:
                if benchmark:
                    row = existing_pa_by_combo[combo]
                    price, count = benchmark
                    row.default_unit_price = price
                    row.currency = "USD"
                    row.confidence_level = "high_confidence"
                    row.source_detail = f"Mediana de {count} TCOs históricos reais (extração 20/06/2026, apenas registros em USD)"
                continue  # combinação já existia — preço atualizado acima se havia benchmark, resto não se mexe

            kwargs = dict(
                packaging_type=packaging_type,
                goodpack_sku_id=goodpack_sku_id,
                competitor_unit_id=competitor_unit_id,
                product_type_id=product_type_id,
                accessory_type_id=accessory_type_id,
                collected_at=date.today(),
            )
            if benchmark:
                price, count = benchmark
                kwargs.update(
                    default_unit_price=price,
                    currency="USD",
                    confidence_level="high_confidence",
                    source_detail=f"Mediana de {count} TCOs históricos reais (extração 20/06/2026, apenas registros em USD)",
                )
            else:
                kwargs.update(
                    confidence_level="validation_required",
                    source_type="interno",
                    source_detail="Estrutura inicial — preço pendente de confirmação",
                )
            db.add(PackagingAccessory(**kwargs))
    await db.flush()
