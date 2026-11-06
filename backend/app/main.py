"""
BB IA MVP — FastAPI entry point.
Inicializa a aplicação, registra routers e configura middleware.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import guardiao, bbdecision, auth, chat
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

# ---------------------------------------------------------------------------
# CORS
#
# Origens permitidas (em ordem de prioridade):
#   1. frontend_url do .env (URL de produção no Vercel, ex: https://shetech.vercel.app)
#   2. Origens fixas de desenvolvimento local
#
# Em produção, defina FRONTEND_URL no painel do Render para restringir ao
# domínio Vercel correto. Sem ela, apenas localhost é aceito.
# ---------------------------------------------------------------------------

_LOCAL_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

_allowed_origins: list[str] = list(_LOCAL_ORIGINS)
if settings.frontend_url:
    _allowed_origins.append(settings.frontend_url.rstrip("/"))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(guardiao.router, prefix="/api/guardiao", tags=["Guardião"])
app.include_router(bbdecision.router, prefix="/api/bbdecision", tags=["BB Decision"])
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticação"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])


@app.get("/health", tags=["Infraestrutura"])
def health_check() -> dict:
    """Verifica se a API está no ar."""
    return {"status": "ok", "version": "0.1.0"}
