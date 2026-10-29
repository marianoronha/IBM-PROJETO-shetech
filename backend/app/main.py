"""
BB IA MVP — FastAPI entry point.
Inicializa a aplicação, registra routers e configura middleware.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import guardiao, bbdecision
from app.config import settings

app = FastAPI(
    title="BB IA MVP — Guardião + BB Decision",
    description=(
        "Protótipo funcional das soluções Guardião (IA contra golpes de "
        "engenharia social) e BB Decision (simulador de decisões financeiras). "
        "Todos os dados são sintéticos. As simulações são estimativas, "
        "não constituem garantia nem recomendação de investimento."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — em produção, restringir a origens conhecidas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(guardiao.router, prefix="/api/guardiao", tags=["Guardião"])
app.include_router(bbdecision.router, prefix="/api/bbdecision", tags=["BB Decision"])


@app.get("/health", tags=["Infraestrutura"])
def health_check() -> dict:
    """Verifica se a API está no ar."""
    return {"status": "ok", "version": "0.1.0"}
