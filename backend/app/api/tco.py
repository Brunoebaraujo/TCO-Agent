"""
Router: TCO — endpoints para gerar e consultar análises TCO
"""
import json
import re
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models import ChatSession, CompetitorUnit, CustomerCompetitorPrice
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


async def _record_competitor_price(db: AsyncSession, session_id: int, tco: dict) -> None:
    """
    Extrai o preço do concorrente do TCO_RESULT e grava em
    CustomerCompetitorPrice para alimentar a inteligência competitiva.

    Chamado apenas quando um TCO_RESULT novo é detectado no save_session.
    Silenciosamente ignora falhas — nunca deve bloquear o save da sessão.
    """
    try:
        customer = tco.get("customer_name", "").strip()
        competitor_name = tco.get("competitor_name", "").strip()
        if not customer or not competitor_name:
            return

        # Custo por unidade do concorrente vem da categoria Packaging
        categories = tco.get("categories", [])
        pkg = next((c for c in categories if c.get("label") == "Packaging"), None)
        competitor_per_unit = pkg.get("competitor_per_unit") if pkg else None
        if competitor_per_unit is None:
            return

        # Tenta resolver a FK do concorrente pelo nome
        res = await db.execute(
            select(CompetitorUnit).where(CompetitorUnit.unit_name == competitor_name)
        )
        unit = res.scalar_one_or_none()

        record = CustomerCompetitorPrice(
            chat_session_id=session_id,
            customer_name=customer,
            competitor_unit_id=unit.id if unit else None,
            competitor_name_raw=competitor_name,
            goodpack_sku=tco.get("goodpack_sku"),
            product_name=tco.get("product_name"),
            unit_price=float(competitor_per_unit),
            currency=tco.get("currency", "USD"),
            simulated_metric_tonnes=tco.get("simulated_metric_tonnes"),
            lease_days=tco.get("lease_days"),
            recorded_at=date.today(),
        )
        db.add(record)
    except Exception:
        pass  # Nunca bloqueia o save da sessão


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

        # Detecta se chegou um TCO_RESULT novo neste save (não estava antes)
        old_result = json.loads(session.last_tco_result_json) if session.last_tco_result_json else None
        is_new_result = latest_result and (
            not old_result
            or old_result.get("customer_name") != latest_result.get("customer_name")
            or old_result.get("competitor_name") != latest_result.get("competitor_name")
        )

        session.messages_json = json.dumps(messages_data, ensure_ascii=False)
        session.title = title
        session.last_tco_result_json = json.dumps(latest_result, ensure_ascii=False) if latest_result else None
        session.updated_at = datetime.utcnow()
        await db.flush()

        if is_new_result:
            await _record_competitor_price(db, session.id, latest_result)
    else:
        session = ChatSession(
            title=title,
            messages_json=json.dumps(messages_data, ensure_ascii=False),
            last_tco_result_json=json.dumps(latest_result, ensure_ascii=False) if latest_result else None,
        )
        db.add(session)
        await db.flush()

        if latest_result:
            await _record_competitor_price(db, session.id, latest_result)

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
