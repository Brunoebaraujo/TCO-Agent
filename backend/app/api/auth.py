"""
Router: Auth — autenticação de vendedores
"""
from fastapi import APIRouter

router = APIRouter()


@router.post("/login")
async def login():
    """Login com email/senha ou Google SSO."""
    return {"message": "Auth em desenvolvimento"}


@router.get("/me")
async def me():
    """Retorna dados do usuário autenticado."""
    return {"message": "Auth em desenvolvimento"}
