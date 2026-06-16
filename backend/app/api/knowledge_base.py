"""
Router: Knowledge Base — CRUD para benchmarks, SKUs e concorrentes
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db

router = APIRouter()


@router.get("/skus")
async def list_skus(db: AsyncSession = Depends(get_db)):
    """Lista todos os SKUs Goodpack ativos."""
    return {"skus": [], "message": "Em desenvolvimento"}


@router.get("/competitors")
async def list_competitors(db: AsyncSession = Depends(get_db)):
    """Lista embalagens concorrentes cadastradas."""
    return {"competitors": [], "message": "Em desenvolvimento"}


@router.get("/handling")
async def get_handling_benchmarks(
    region: str = "GLOBAL",
    applies_to: str = "goodpack",
    db: AsyncSession = Depends(get_db)
):
    """
    Busca benchmarks de handling com fallback regional.
    Se não encontrar dados para a região específica, retorna GLOBAL.
    """
    return {"benchmarks": [], "region_used": region, "message": "Em desenvolvimento"}


@router.post("/competitors/{competitor_id}/pricing")
async def add_competitor_pricing(
    competitor_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Adiciona novo preço para um concorrente.
    Automaticamente marca o registro anterior como is_current=False.
    """
    return {"message": "Em desenvolvimento"}
