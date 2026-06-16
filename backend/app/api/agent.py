"""
Router: Agent — chat com o agente TCO (Claude API)
Suporta streaming para resposta em tempo real na interface.
"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db

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
    Em produção: usar /chat/stream para streaming.
    """
    # TODO: implementar chamada Claude API + lógica de contexto
    return {
        "role": "assistant",
        "content": "Agente TCO em desenvolvimento. Motor de IA será conectado na Fase 1."
    }


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Versão com streaming — resposta aparece token a token na interface.
    Usar Server-Sent Events (SSE).
    """
    async def generate():
        # TODO: implementar streaming Claude API
        yield "data: {\"content\": \"Streaming em desenvolvimento\"}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
