"""
TCO Engine — Backend API
Entry point FastAPI
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.db.database import init_db
from app.api import tco, agent, knowledge_base, auth
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicialização e encerramento da aplicação."""
    await init_db()
    yield


app = FastAPI(
    title="TCO Engine API",
    description="AI-powered Total Cost of Ownership platform for Goodpack",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — permite frontend conectar ao backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rotas
app.include_router(auth.router,           prefix="/api/auth",     tags=["auth"])
app.include_router(tco.router,            prefix="/api/tco",      tags=["tco"])
app.include_router(agent.router,          prefix="/api/agent",    tags=["agent"])
app.include_router(knowledge_base.router, prefix="/api/kb",       tags=["knowledge-base"])


@app.get("/health")
async def health():
    """Health check para Railway."""
    return {"status": "ok", "version": "0.1.0"}
