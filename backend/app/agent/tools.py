"""
Tools (function calling) que o agente TCO pode usar para consultar dados
reais da base de conhecimento — specs de embalagens, acessórios, preços —
em vez de inferir ou inventar esses valores a partir do texto da conversa.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import (
    GoodpackSKU, CompetitorUnit, CompetitorPricing,
    PackagingAccessory, AccessoryType, Product, ProductType,
    TransportType, HandlingParameterType, HandlingBenchmark,
    CustomerCompetitorPrice,
)

TOOLS = [
    {
        "name": "get_packaging_specs",
        "description": (
            "Retorna as especificações físicas reais de uma embalagem Goodpack (SKU) ou "
            "concorrente: volume, peso máximo (max_payload_kg), peso tara, quantidade que cabe "
            "em diferentes tipos de container/transporte, e capacidade de empilhamento. "
            "Use esta ferramenta SEMPRE antes de calcular estatísticas logísticas (Units Needed, "
            "Transports Needed, QTY Pallet Places, QTY Full Stacks) — nunca estime esses valores "
            "de memória."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "packaging_type": {
                    "type": "string",
                    "enum": ["goodpack", "competitor"],
                    "description": "Se é uma SKU Goodpack ou uma embalagem concorrente",
                },
                "name": {
                    "type": "string",
                    "description": "Código da SKU (ex: 'MB6') ou nome da embalagem concorrente (ex: 'Octabin', 'Drum 200L')",
                },
            },
            "required": ["packaging_type", "name"],
        },
    },
    {
        "name": "get_packaging_accessories",
        "description": (
            "Retorna a lista de acessórios cadastrados para uma embalagem (Goodpack ou "
            "concorrente), incluindo os específicos por produto+tipo quando existirem, com "
            "preço default e nível de confiança. Use esta ferramenta para saber QUAIS acessórios "
            "perguntar ao vendedor, em vez de assumir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "packaging_type": {"type": "string", "enum": ["goodpack", "competitor"]},
                "name": {"type": "string", "description": "Código da SKU ou nome da embalagem concorrente"},
                "product_name": {"type": "string", "description": "Nome do produto, se conhecido (ex: 'Orange')"},
                "type_name": {"type": "string", "description": "Tipo de processamento, se conhecido (ex: 'FCOJ')"},
            },
            "required": ["packaging_type", "name"],
        },
    },
    {
        "name": "get_competitor_pricing",
        "description": (
            "Retorna o histórico de preços conhecidos de uma embalagem concorrente, com região, "
            "data de coleta, fonte e nível de confiança. Use antes de perguntar ao vendedor o "
            "preço de uma embalagem concorrente — pode já existir um valor confiável na base."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome da embalagem concorrente"},
                "region": {"type": "string", "description": "Região da oportunidade, se conhecida (ex: 'LATAM')"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_handling_benchmarks",
        "description": (
            "Retorna os benchmarks default (fallback) de todos os parâmetros operacionais de "
            "Handling — custo de mão de obra por hora, manpower e tempo para cada etapa "
            "(armazenagem, montagem/desmontagem, empilhamento, carga/descarga) — separados por "
            "papel (packer ou enduser). Use esta ferramenta SEMPRE antes de calcular custo de "
            "Handling Packer ou Handling Enduser, para saber quais etapas existem e qual o valor "
            "default de cada uma quando o vendedor não informar um valor real do cliente."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "enum": ["packer", "enduser", "both"],
                    "description": "Filtra por papel; 'both' retorna todos os parâmetros de ambos",
                },
                "region": {"type": "string", "description": "Região da oportunidade, se conhecida — usa GLOBAL como fallback se não houver benchmark regional"},
            },
            "required": [],
        },
    },
    {
        "name": "get_transport_specs",
        "description": (
            "Retorna os limites de peso bruto (gross weight) de um tipo de transporte (ex: '20ft "
            "Dry', '40ft Reefer'). Use antes de calcular Transports Needed para validar se a carga "
            "por unidade de embalagem respeita o limite de peso do transporte escolhido."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transport_name": {"type": "string", "description": "Nome do tipo de transporte, ex: '40ft Reefer'"},
            },
            "required": ["transport_name"],
        },
    },
    {
        "name": "get_competitor_price_intelligence",
        "description": (
            "Consulta o histórico de preços reais de embalagens concorrentes registrados em TCOs "
            "anteriores — preços confirmados por clientes reais, não benchmarks de mercado. "
            "Retorna estatísticas (média, mínimo, máximo) e a lista de clientes com seus preços, "
            "permitindo responder perguntas como 'quem paga mais caro pelo Octabin?' ou 'qual o "
            "preço médio do Drum 200L em oportunidades passadas?'. Use quando o vendedor perguntar "
            "sobre preços históricos ou precisar de referência para negociar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "competitor_name": {
                    "type": "string",
                    "description": "Nome da embalagem concorrente (ex: 'Octabin', 'Drum 200L'). Omitir para ver todos.",
                },
                "goodpack_sku": {
                    "type": "string",
                    "description": "Filtrar por SKU Goodpack comparada (ex: 'MB6'). Omitir para ver todos.",
                },
                "product_name": {
                    "type": "string",
                    "description": "Filtrar por produto (ex: 'Orange'). Omitir para ver todos.",
                },
            },
            "required": [],
        },
    },
]


async def _resolve_packaging_id(db: AsyncSession, packaging_type: str, name: str):
    if packaging_type == "goodpack":
        result = await db.execute(select(GoodpackSKU).where(GoodpackSKU.sku_code == name))
        return result.scalar_one_or_none()
    else:
        result = await db.execute(select(CompetitorUnit).where(CompetitorUnit.unit_name == name))
        return result.scalar_one_or_none()


async def execute_tool(db: AsyncSession, tool_name: str, tool_input: dict) -> dict:
    """
    Executa a tool solicitada pelo agente contra o banco real e retorna o
    resultado como dict (será serializado como JSON na tool_result).
    """
    if tool_name == "get_packaging_specs":
        obj = await _resolve_packaging_id(db, tool_input["packaging_type"], tool_input["name"])
        if not obj:
            return {"error": f"Embalagem '{tool_input['name']}' não encontrada na base."}
        return {
            "sku_or_name": getattr(obj, "sku_code", None) or getattr(obj, "unit_name", None),
            "volume_liters": float(obj.volume_liters) if obj.volume_liters else None,
            "max_payload_kg": float(obj.max_payload_kg) if obj.max_payload_kg else None,
            "tare_weight_kg": float(obj.tare_weight_kg) if obj.tare_weight_kg else None,
            "stack_full_warehouse": getattr(obj, "stack_full_warehouse", None),
            "stack_full_transit": getattr(obj, "stack_full_transit", None),
            "qty_20ft_dry": getattr(obj, "qty_20ft_dry", None),
            "qty_40ft_dry": getattr(obj, "qty_40ft_dry", None),
            "qty_40ft_hc_dry": getattr(obj, "qty_40ft_hc_dry", None),
            "note": "Se algum campo vier null, esse dado não está cadastrado — não estime, pergunte ao vendedor ou avise que a estatística não pode ser calculada.",
        }

    elif tool_name == "get_packaging_accessories":
        obj = await _resolve_packaging_id(db, tool_input["packaging_type"], tool_input["name"])
        if not obj:
            return {"error": f"Embalagem '{tool_input['name']}' não encontrada na base."}

        is_goodpack = tool_input["packaging_type"] == "goodpack"
        query = select(PackagingAccessory).where(PackagingAccessory.is_current == True)
        query = query.where(
            PackagingAccessory.goodpack_sku_id == obj.id if is_goodpack
            else PackagingAccessory.competitor_unit_id == obj.id
        )
        items = (await db.execute(query)).scalars().all()

        accessory_names = {a.id: a.accessory_name for a in (await db.execute(select(AccessoryType))).scalars().all()}
        product_types = {t.id: t for t in (await db.execute(select(ProductType))).scalars().all()}
        products = {p.id: p for p in (await db.execute(select(Product))).scalars().all()}

        results = []
        for item in items:
            label = None
            if item.product_type_id and item.product_type_id in product_types:
                pt = product_types[item.product_type_id]
                product = products.get(pt.product_id)
                label = f"{product.product_name if product else '?'} / {pt.type_name}"
            results.append({
                "accessory_name": accessory_names.get(item.accessory_type_id, "?"),
                "specific_to_product_type": label,
                "default_unit_price": float(item.default_unit_price) if item.default_unit_price else None,
                "confidence_level": item.confidence_level,
                "currency": item.currency,
            })
        return {"accessories": results}

    elif tool_name == "get_competitor_pricing":
        result = await db.execute(select(CompetitorUnit).where(CompetitorUnit.unit_name == tool_input["name"]))
        unit = result.scalar_one_or_none()
        if not unit:
            return {"error": f"Embalagem '{tool_input['name']}' não encontrada na base."}

        query = select(CompetitorPricing).where(CompetitorPricing.competitor_unit_id == unit.id)
        query = query.where(CompetitorPricing.is_current == True)
        if tool_input.get("region"):
            query = query.where(CompetitorPricing.region == tool_input["region"])
        pricing = (await db.execute(query)).scalars().all()

        return {"pricing": [
            {
                "unit_price": float(p.unit_price), "currency": p.currency, "region": p.region,
                "collected_at": p.collected_at.isoformat() if p.collected_at else None,
                "confidence_level": p.confidence_level, "source_detail": p.source_detail,
            }
            for p in pricing
        ]}

    elif tool_name == "get_handling_benchmarks":
        role = tool_input.get("role", "both")
        region = tool_input.get("region")

        query = select(HandlingParameterType).where(HandlingParameterType.active == True)
        if role != "both":
            query = query.where(HandlingParameterType.role == role)
        params = (await db.execute(query)).scalars().all()

        results = []
        for p in params:
            # Tenta benchmark regional primeiro, cai para GLOBAL se não existir
            value = None
            confidence = None
            for candidate_region in filter(None, [region, "GLOBAL"]):
                bq = select(HandlingBenchmark).where(
                    HandlingBenchmark.param_key == p.param_key,
                    HandlingBenchmark.region_code == candidate_region,
                    HandlingBenchmark.competitor_unit_id.is_(None),
                    HandlingBenchmark.is_current == True,
                )
                benchmark = (await db.execute(bq)).scalar_one_or_none()
                if benchmark:
                    value = float(benchmark.value)
                    confidence = benchmark.confidence_level
                    break
            results.append({
                "param_key": p.param_key,
                "label": p.param_label,
                "role": p.role,
                "unit": p.unit,
                "default_value": value,
                "confidence_level": confidence,
            })
        return {
            "parameters": results,
            "note": "default_value é o benchmark interno (fallback). Se o vendedor informar o valor real do cliente, use o valor real e marque como 'verified'.",
        }

    elif tool_name == "get_transport_specs":
        result = await db.execute(select(TransportType).where(TransportType.transport_name == tool_input["transport_name"]))
        t = result.scalar_one_or_none()
        if not t:
            return {"error": f"Tipo de transporte '{tool_input['transport_name']}' não encontrado na base."}
        return {
            "transport_name": t.transport_name,
            "standard_gross_weight_limit_kg": float(t.standard_gross_weight_limit_kg) if t.standard_gross_weight_limit_kg else None,
            "gross_weight_limit_kg": float(t.gross_weight_limit_kg) if t.gross_weight_limit_kg else None,
        }

    elif tool_name == "get_competitor_price_intelligence":
        from sqlalchemy import func as sqlfunc
        query = select(CustomerCompetitorPrice).where(CustomerCompetitorPrice.unit_price > 0)

        if tool_input.get("competitor_name"):
            query = query.where(
                CustomerCompetitorPrice.competitor_name_raw.ilike(f"%{tool_input['competitor_name']}%")
            )
        if tool_input.get("goodpack_sku"):
            query = query.where(CustomerCompetitorPrice.goodpack_sku == tool_input["goodpack_sku"])
        if tool_input.get("product_name"):
            query = query.where(
                CustomerCompetitorPrice.product_name.ilike(f"%{tool_input['product_name']}%")
            )

        records = (await db.execute(query.order_by(CustomerCompetitorPrice.unit_price.desc()))).scalars().all()

        if not records:
            return {"message": "Nenhum registro encontrado para os filtros informados. Os preços são registrados automaticamente ao finalizar um TCO."}

        prices = [float(r.unit_price) for r in records]
        avg_price = sum(prices) / len(prices)

        entries = [
            {
                "customer_name": r.customer_name,
                "competitor_name": r.competitor_name_raw,
                "goodpack_sku": r.goodpack_sku,
                "product_name": r.product_name,
                "unit_price": float(r.unit_price),
                "currency": r.currency,
                "simulated_mt": float(r.simulated_metric_tonnes) if r.simulated_metric_tonnes else None,
                "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
            }
            for r in records
        ]

        return {
            "total_records": len(records),
            "statistics": {
                "average_price": round(avg_price, 2),
                "min_price": min(prices),
                "max_price": max(prices),
                "currency": records[0].currency if records else "USD",
            },
            "highest_paying_customer": entries[0] if entries else None,
            "lowest_paying_customer": entries[-1] if entries else None,
            "all_records": entries,
        }

    return {"error": f"Tool desconhecida: {tool_name}"}
