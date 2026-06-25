"""
Router: Agent — chat com o agente TCO (Claude API)
"""
import json
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.agent.client import ask_agent
from app.agent.tco_parser import extract_tco_result

router = APIRouter()

# Número de mensagens de refinamento a manter após o TCO ter sido calculado.
# O bloco de overrides e o TCO estruturado são preservados separadamente —
# esse número se refere às trocas user/assistant de refinamento posteriores.
_HISTORY_TAIL = 6


class ChatMessage(BaseModel):
    role: str           # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    opportunity_context: dict = {}


def _has_tco(messages: list[dict]) -> bool:
    """Verifica se alguma mensagem do histórico contém um TCO_RESULT calculado."""
    for m in messages:
        if m["role"] == "assistant" and "TCO_RESULT" in m.get("content", ""):
            return True
    return False


def _truncate_history(messages: list[dict]) -> list[dict]:
    """
    Se o TCO já foi calculado, comprime o histórico para reduzir tokens:

    - Mantém a primeira mensagem do usuário (contexto inicial da oportunidade,
      incluindo os dados do Express Form ou a descrição original).
    - Mantém a última mensagem do assistente que contém TCO_RESULT (ponto de
      partida do refinamento atual).
    - Mantém as últimas _HISTORY_TAIL mensagens de refinamento após o TCO.

    Sem TCO calculado ainda: retorna intacto (entrevista em andamento).
    """
    if not _has_tco(messages):
        return messages

    # Primeira mensagem do user (contexto da oportunidade)
    first_user = next((m for m in messages if m["role"] == "user"), None)

    # Última mensagem do assistente com TCO_RESULT
    last_tco_msg = None
    last_tco_idx = -1
    for i, m in enumerate(messages):
        if m["role"] == "assistant" and "TCO_RESULT" in m.get("content", ""):
            last_tco_msg = m
            last_tco_idx = i

    # Tail de refinamento: mensagens após o último TCO
    tail = messages[last_tco_idx + 1:] if last_tco_idx >= 0 else []
    tail = tail[-_HISTORY_TAIL:] if len(tail) > _HISTORY_TAIL else tail

    compressed = []
    if first_user:
        compressed.append(first_user)
    if last_tco_msg and last_tco_msg != first_user:
        compressed.append(last_tco_msg)
    compressed.extend(tail)

    # Garante que começa sempre com user
    if compressed and compressed[0]["role"] != "user":
        compressed = [m for m in compressed if m["role"] == "user"][:1] + compressed

    return compressed or messages


@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint principal de conversa com o agente TCO.
    Recebe o histórico de mensagens, comprime se já há TCO calculado,
    e retorna a resposta do agente.
    """
    try:
        history = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role in ("user", "assistant")
        ]

        if not history or history[0]["role"] != "user":
            history = [m for m in history if m["role"] == "user"] or history

        history = _truncate_history(history)

        raw_reply = await ask_agent(history, db)
        clean_text, tco_result, pending_text = extract_tco_result(raw_reply)

        return {
            "role": "assistant",
            "content": clean_text,
            "tco_result": tco_result,
            "pending_text": pending_text,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao chamar o agente: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint Express — sem tool calls
# ─────────────────────────────────────────────────────────────────────────────

class ExpressRequest(BaseModel):
    goodpack_sku: str
    competitor_name: str
    product_name: str
    type_name: str | None = None
    origin: str
    destination: str
    goodpack_unit_price: float
    competitor_unit_price: float
    freight_per_container: float
    volume_mt: float
    lease_days: int = 180
    region: str = "GLOBAL"
    customer_name: str | None = None


@router.post("/chat-express")
async def chat_express(request: ExpressRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint TCO Express — resolve todos os dados do DB em Python e chama
    o LLM apenas para narrativa e formatação do TCO_RESULT.

    Elimina 4-6 tool calls por TCO Express (~2.000-4.000 tokens economizados).
    O resultado é idêntico ao fluxo normal — apenas mais rápido e mais barato.
    """
    from app.agent.express_resolver import resolve_express
    from app.agent.prompts import EXPRESS_NARRATOR_PROMPT, TCO_RESULT_SCHEMA
    from app.agent.client import client as anthropic_client
    from app.config import settings
    import json as _json

    try:
        # 1. Resolve tudo deterministicamente
        resolved = await resolve_express(
            db,
            goodpack_sku=request.goodpack_sku,
            competitor_name=request.competitor_name,
            product_name=request.product_name,
            type_name=request.type_name,
            origin=request.origin,
            destination=request.destination,
            goodpack_unit_price=request.goodpack_unit_price,
            competitor_unit_price=request.competitor_unit_price,
            freight_per_container=request.freight_per_container,
            volume_mt=request.volume_mt,
            lease_days=request.lease_days,
            region=request.region,
        )

        engine = resolved["tco_engine_result"]
        r = resolved["resolved"]
        warnings = resolved["warnings"]

        # 2. Monta o prompt para o LLM — só narrativa, sem tool calls
        user_prompt = f"""Oportunidade:
- Cliente: {request.customer_name or 'A definir'}
- Goodpack: {r['goodpack_sku']}  vs  Concorrente: {r['competitor_name']}
- Produto: {r['product_name']}{' — ' + r['type_name'] if r['type_name'] else ''}
- Origem: {r['origin']}  →  Destino: {r['destination']}
- Volume: {r['volume_mt']} MT  |  Lease: {r['lease_days']} dias  |  Regional: {r['region']}
- Preço Goodpack: ${r['goodpack_unit_price']}/un  |  Preço concorrente: ${r['competitor_unit_price']}/un
- Frete por container: ${r['freight_per_container']}
- Densidade: {r['density']} kg/L {'(estimativa)' if r['density'] else '(não encontrada)'}
- Qty/container Goodpack: {r['gp_qty_transport']}  |  Concorrente: {r['comp_qty_transport']}

Acessórios Goodpack: {_json.dumps(r['gp_accessories'], ensure_ascii=False)}
Acessórios Concorrente: {_json.dumps(r['comp_accessories'], ensure_ascii=False)}

Resultado calculado pelo engine:
{_json.dumps(engine, ensure_ascii=False, indent=2)}

Avisos (transformar em assumptions validation_required):
{_json.dumps(warnings, ensure_ascii=False)}

{TCO_RESULT_SCHEMA}

Gere a resposta agora."""

        # 3. Chama o LLM sem tools — só narrativa
        response = await anthropic_client.messages.create(
            model=settings.claude_model,
            max_tokens=8192,
            system=EXPRESS_NARRATOR_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_reply = "\n".join(
            block.text for block in response.content if block.type == "text"
        )

        clean_text, tco_result, pending_text = extract_tco_result(raw_reply)

        # Injeta campos que o engine calculou mas o LLM pode ter omitido
        if tco_result:
            # Campos narrativos: setdefault — o LLM gera esses, o engine não tem.
            tco_result.setdefault("goodpack_sku", request.goodpack_sku)
            tco_result.setdefault("competitor_name", request.competitor_name)
            tco_result.setdefault("product_name", request.product_name)
            tco_result.setdefault("simulated_metric_tonnes", request.volume_mt)
            tco_result.setdefault("logistics", engine.get("logistics"))

            # Campos numéricos críticos: SEMPRE do engine (update sobrescreve o LLM).
            # O LLM pode gerar valores ligeiramente diferentes por arredondamento ou
            # alucinação — o engine é a fonte da verdade para todos estes campos.
            tco_result.update({
                "goodpack_total_per_mt":        engine.get("goodpack_total_per_mt"),
                "competitor_total_per_mt":       engine.get("competitor_total_per_mt"),
                "total_saving":                  engine.get("total_saving"),
                "saving_percentage":             engine.get("saving_percentage"),
                "subtotals":                     engine.get("subtotals"),
                "categories":                    engine.get("categories"),
                "packaging_breakdown":           engine.get("packaging_breakdown"),
                "competitor_packaging_breakdown": engine.get("competitor_packaging_breakdown"),
                "goodpack_qty_per_unit_kg":      engine.get("goodpack_qty_per_unit_kg"),
                "competitor_qty_per_unit_kg":    engine.get("competitor_qty_per_unit_kg"),
                "goodpack_tare_weight_kg":       r.get("gp_tare_weight_kg"),
                "competitor_tare_weight_kg":     r.get("comp_tare_weight_kg"),
            })

        return {
            "role": "assistant",
            "content": clean_text,
            "tco_result": tco_result,
            "pending_text": pending_text,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no Express resolver: {str(e)}")
