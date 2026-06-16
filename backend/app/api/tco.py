"""
Router: TCO — endpoints para gerar e consultar análises TCO
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db

router = APIRouter()


@router.get("/")
async def list_analyses(db: AsyncSession = Depends(get_db)):
    """Lista os TCOs gerados pelo usuário autenticado."""
    return {"analyses": [], "message": "Em desenvolvimento"}


@router.post("/generate")
async def generate_tco(db: AsyncSession = Depends(get_db)):
    """
    Gera um TCO completo a partir dos inputs da oportunidade.
    Usado quando o vendedor já tem todos os dados e quer calcular diretamente.
    """
    return {"message": "Motor de cálculo — em desenvolvimento"}
