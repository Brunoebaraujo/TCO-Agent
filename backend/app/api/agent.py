"""
Router: Agent — chat com o agente TCO (Claude API)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.agent.client import ask_agent
from app.agent.tco_parser import extract_tco_result

router = APIRouter()


class ChatMessage(BaseModel):
    role: str           # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    opportunity_context: dict = {}  # Dados do Salesforce (fase 2) ou preenchidos pelo vendedor


@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Endpoint principal de conversa com o agente TCO.
    Recebe o histórico de mensagens e retorna a resposta do agente.

    Se o agente gerou um resultado de TCO estruturado (bloco TCO_RESULT),
    ele é extraído e retornado separadamente em `tco_result`, para que o
    frontend renderize a tabela/gráfico em vez de texto cru.
    """
    try:
        history = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role in ("user", "assistant")
        ]

        if not history or history[0]["role"] != "user":
            history = [m for m in history if m["role"] == "user"] or history

        raw_reply = await ask_agent(history)
        clean_text, tco_result = extract_tco_result(raw_reply)

        return {
            "role": "assistant",
            "content": clean_text,
            "tco_result": tco_result,  # None se o agente não gerou um resultado nesta resposta
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao chamar o agente: {str(e)}")
