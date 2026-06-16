"""
Router: Agent — chat com o agente TCO (Claude API)
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.agent.client import ask_agent

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
    """
    try:
        # Filtra a mensagem de boas-vindas inicial do frontend (não faz parte do histórico real da API)
        history = [
            {"role": m.role, "content": m.content}
            for m in request.messages
            if m.role in ("user", "assistant")
        ]

        if not history or history[0]["role"] != "user":
            # A API exige que a conversa comece com role="user"
            history = [m for m in history if m["role"] == "user"] or history

        reply_text = await ask_agent(history)
        return {"role": "assistant", "content": reply_text}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao chamar o agente: {str(e)}")
