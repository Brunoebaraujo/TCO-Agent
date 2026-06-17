"""
Router: TCO — endpoints para gerar e consultar análises TCO
"""
import json
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import ChatSession
from app.integrations.pptx_export import generate_tco_pptx

router = APIRouter()


class MessageIn(BaseModel):
    role: str
    content: str
    tco_result: dict | None = None


class SessionSaveRequest(BaseModel):
    session_id: int | None = None  # None = criar nova sessão
    messages: list[MessageIn]


def _derive_title(messages: list[MessageIn]) -> str:
    """Usa a primeira mensagem do usuário (truncada) como título da sessão."""
    for m in messages:
        if m.role == "user" and m.content.strip():
            text = m.content.strip()
            return text[:60] + ("..." if len(text) > 60 else "")
    return "Nova conversa"


def _latest_tco_result(messages: list[MessageIn]) -> dict | None:
    """Retorna o tco_result mais recente presente no histórico, se houver."""
    for m in reversed(messages):
        if m.tco_result:
            return m.tco_result
    return None


@router.get("/")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    """Lista as sessões salvas, mais recentes primeiro — usado pela tela de History."""
    result = await db.execute(select(ChatSession).order_by(ChatSession.updated_at.desc()))
    sessions = result.scalars().all()
    return {
        "sessions": [
            {
                "id": s.id,
                "title": s.title,
                "updated_at": s.updated_at.isoformat(),
                "tco_result": json.loads(s.last_tco_result_json) if s.last_tco_result_json else None,
            }
            for s in sessions
        ]
    }


@router.get("/{session_id}")
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """Retorna o histórico completo de mensagens de uma sessão — usado para retomar a conversa."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return {
        "id": session.id,
        "title": session.title,
        "messages": json.loads(session.messages_json),
    }


@router.post("/save")
async def save_session(request: SessionSaveRequest, db: AsyncSession = Depends(get_db)):
    """
    Salva (cria ou atualiza) uma sessão de chat completa.
    Chamado pelo frontend após cada troca de mensagem com o agente,
    para que nada se perca ao navegar entre páginas ou recarregar.
    """
    messages_data = [m.model_dump() for m in request.messages]
    title = _derive_title(request.messages)
    latest_result = _latest_tco_result(request.messages)

    if request.session_id:
        session = await db.get(ChatSession, request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Sessão não encontrada")
        session.messages_json = json.dumps(messages_data, ensure_ascii=False)
        session.title = title
        session.last_tco_result_json = json.dumps(latest_result, ensure_ascii=False) if latest_result else None
        session.updated_at = datetime.utcnow()
    else:
        session = ChatSession(
            title=title,
            messages_json=json.dumps(messages_data, ensure_ascii=False),
            last_tco_result_json=json.dumps(latest_result, ensure_ascii=False) if latest_result else None,
        )
        db.add(session)

    await db.flush()
    return {"session_id": session.id}


@router.delete("/{session_id}")
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    """Remove uma sessão salva."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    await db.delete(session)
    return {"deleted": True}


def _safe_filename(name: str) -> str:
    """Remove caracteres problemáticos para nome de arquivo."""
    cleaned = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[\s]+", "_", cleaned) or "TCO"


@router.get("/{session_id}/export/pptx")
async def export_pptx(
    session_id: int,
    include_assumptions: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    Gera e retorna um arquivo .pptx com o resultado de TCO mais recente
    desta sessão. include_assumptions=false gera apenas o slide resumo.
    """
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    if not session.last_tco_result_json:
        raise HTTPException(status_code=400, detail="Esta sessão ainda não tem um TCO calculado")

    tco_result = json.loads(session.last_tco_result_json)
    pptx_bytes = generate_tco_pptx(tco_result, include_assumptions=include_assumptions)

    customer = tco_result.get("customer_name", "TCO")
    filename = f"TCO_{_safe_filename(customer)}_{datetime.now().strftime('%Y%m%d')}.pptx"

    return Response(
        content=pptx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
