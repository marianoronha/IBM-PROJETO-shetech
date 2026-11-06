"""
Camada de acesso ao IBM Cloudant via API REST (HTTPS + IBM IAM).

Características:
  - Autenticação IAM com cache e renovação automática.
  - CRUD completo: create, read, update, delete, list.
  - Tratamento explícito de HTTP 400/401/403/404/409/5xx.
  - Operações assíncronas (httpx.AsyncClient) para não bloquear o event-loop do FastAPI.
  - Versão síncrona (verificar_cloudant) mantida para o endpoint de health.
  - Nenhuma chamada de rede acontece ao importar o módulo.
  - Credenciais lidas apenas de settings — nunca em código ou logs.
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

DATABASE_NAME = "shetech_db"
IAM_URL = "https://iam.cloud.ibm.com/identity/token"

# Margem de segurança: renova o token 60 s antes do vencimento
_TOKEN_MARGIN_S = 60

# ---------------------------------------------------------------------------
# Cache de token IAM (in-process; suficiente para single-worker no Render)
# ---------------------------------------------------------------------------

_cached_token: Optional[str] = None
_token_expires_at: float = 0.0          # epoch seconds


def _is_token_valid() -> bool:
    return bool(_cached_token) and time.monotonic() < _token_expires_at


async def _get_iam_token_async() -> str:
    """Obtém ou renova o token IAM de forma assíncrona."""
    global _cached_token, _token_expires_at

    if _is_token_valid() and _cached_token is not None:
        return _cached_token

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            IAM_URL,
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": settings.ibm_cloudant_apikey,
            },
        )
        resp.raise_for_status()

    data = resp.json()
    _cached_token = str(data["access_token"])
    # IBM IAM retorna expires_in em segundos a partir de agora
    expires_in: int = data.get("expires_in", 3600)
    _token_expires_at = time.monotonic() + expires_in - _TOKEN_MARGIN_S
    return _cached_token


def _get_iam_token_sync() -> str:
    """Versão síncrona — usada apenas em verificar_cloudant()."""
    global _cached_token, _token_expires_at

    if _is_token_valid() and _cached_token is not None:
        return _cached_token

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            IAM_URL,
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": settings.ibm_cloudant_apikey,
            },
        )
        resp.raise_for_status()

    data = resp.json()
    _cached_token = str(data["access_token"])
    expires_in: int = data.get("expires_in", 3600)
    _token_expires_at = time.monotonic() + expires_in - _TOKEN_MARGIN_S
    return _cached_token


def _db_url(path: str = "") -> str:
    """Monta a URL base do banco, opcionalmente com sub-caminho."""
    base = f"{settings.ibm_cloudant_url.rstrip('/')}/{DATABASE_NAME}"
    if path:
        return f"{base}/{path.lstrip('/')}"
    return base


def _auth_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# Exceções tipadas
# ---------------------------------------------------------------------------

class CloudantError(Exception):
    """Erro base do Cloudant."""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class CloudantNotFound(CloudantError):
    """Documento não encontrado (HTTP 404)."""


class CloudantConflict(CloudantError):
    """Conflito de revisão (HTTP 409)."""


class CloudantUnauthorized(CloudantError):
    """Credenciais inválidas (HTTP 401/403)."""


def _raise_for_status(resp: httpx.Response) -> None:
    """Traduz erros HTTP do Cloudant em exceções tipadas."""
    if resp.is_success:
        return
    sc = resp.status_code
    # Tenta extrair mensagem do Cloudant sem expor detalhes internos
    try:
        body = resp.json()
        reason = body.get("reason", "")
    except Exception:
        reason = ""

    if sc == 404:
        raise CloudantNotFound(f"Documento não encontrado. {reason}", status_code=sc)
    if sc == 409:
        raise CloudantConflict(f"Conflito de revisão. {reason}", status_code=sc)
    if sc in (401, 403):
        # Não logar o token nem a API key
        logger.error("Cloudant: falha de autenticação (HTTP %s).", sc)
        raise CloudantUnauthorized("Falha de autenticação no Cloudant.", status_code=sc)
    if sc >= 500:
        logger.error("Cloudant: erro interno do servidor (HTTP %s).", sc)
        raise CloudantError(f"Servidor Cloudant indisponível (HTTP {sc}).", status_code=sc)
    raise CloudantError(f"Erro inesperado do Cloudant (HTTP {sc}): {reason}", status_code=sc)


# ---------------------------------------------------------------------------
# CRUD assíncrono
# ---------------------------------------------------------------------------

async def create_document(data: dict[str, Any], doc_id: Optional[str] = None) -> dict[str, Any]:
    """
    Cria um documento no banco.

    Args:
        data:   Campos do documento (não deve conter _id nem _rev).
        doc_id: ID desejado. Se omitido, o Cloudant gera um UUID.

    Returns:
        {"id": str, "rev": str, "ok": True}
    """
    if not settings.ibm_cloudant_url or not settings.ibm_cloudant_apikey:
        raise CloudantError("Credenciais do Cloudant não configuradas.")

    doc = dict(data)
    if doc_id:
        doc["_id"] = doc_id
    elif "_id" not in doc:
        doc["_id"] = str(uuid.uuid4())

    token = await _get_iam_token_async()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(_db_url(), headers=_auth_headers(token), json=doc)
    _raise_for_status(resp)
    return resp.json()


async def get_document(doc_id: str) -> dict[str, Any]:
    """
    Lê um documento por ID.

    Returns:
        Documento completo com _id e _rev.

    Raises:
        CloudantNotFound: se o documento não existir.
    """
    if not settings.ibm_cloudant_url or not settings.ibm_cloudant_apikey:
        raise CloudantError("Credenciais do Cloudant não configuradas.")

    token = await _get_iam_token_async()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(_db_url(doc_id), headers=_auth_headers(token))
    _raise_for_status(resp)
    return resp.json()


async def update_document(doc_id: str, rev: str, data: dict[str, Any]) -> dict[str, Any]:
    """
    Atualiza um documento existente.

    O campo _rev deve ser fornecido explicitamente para evitar conflitos.

    Returns:
        {"id": str, "rev": str (nova revisão), "ok": True}

    Raises:
        CloudantConflict: se a revisão fornecida não for a mais recente.
        CloudantNotFound: se o documento não existir.
    """
    if not settings.ibm_cloudant_url or not settings.ibm_cloudant_apikey:
        raise CloudantError("Credenciais do Cloudant não configuradas.")

    doc = dict(data)
    doc["_id"] = doc_id
    doc["_rev"] = rev

    token = await _get_iam_token_async()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(_db_url(doc_id), headers=_auth_headers(token), json=doc)
    _raise_for_status(resp)
    return resp.json()


async def delete_document(doc_id: str, rev: str) -> dict[str, Any]:
    """
    Exclui um documento por ID e revisão.

    Returns:
        {"id": str, "rev": str, "ok": True}

    Raises:
        CloudantConflict: se a revisão fornecida não for a mais recente.
        CloudantNotFound: se o documento não existir.
    """
    if not settings.ibm_cloudant_url or not settings.ibm_cloudant_apikey:
        raise CloudantError("Credenciais do Cloudant não configuradas.")

    token = await _get_iam_token_async()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            _db_url(doc_id),
            headers=_auth_headers(token),
            params={"rev": rev},
        )
    _raise_for_status(resp)
    return resp.json()


async def list_documents(
    limit: int = 20,
    skip: int = 0,
    include_docs: bool = True,
) -> dict[str, Any]:
    """
    Lista documentos do banco usando _all_docs.

    Args:
        limit:        Máximo de documentos retornados (padrão 20, máximo 100).
        skip:         Quantos documentos pular (paginação).
        include_docs: Se True, inclui o corpo de cada documento.

    Returns:
        Resposta do Cloudant: {"total_rows": int, "rows": [...]}
    """
    if not settings.ibm_cloudant_url or not settings.ibm_cloudant_apikey:
        raise CloudantError("Credenciais do Cloudant não configuradas.")

    limit = min(max(1, limit), 100)

    token = await _get_iam_token_async()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            _db_url("_all_docs"),
            headers=_auth_headers(token),
            params={
                "limit": limit,
                "skip": skip,
                "include_docs": str(include_docs).lower(),
            },
        )
    _raise_for_status(resp)
    return resp.json()


# ---------------------------------------------------------------------------
# CRUD síncrono — para nós síncronos do LangGraph (audit_log_node)
# ---------------------------------------------------------------------------

def create_document_sync(
    data: dict[str, Any],
    doc_id: Optional[str] = None,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """
    Cria um documento no banco de forma síncrona.

    Usada pelo audit_log_node (nó síncrono do LangGraph) para garantir que
    a persistência ocorra *antes* do retorno do nó — sem tarefas soltas.

    Args:
        data:    Campos do documento.
        doc_id:  ID desejado; se omitido, gera um UUID local.
        timeout: Timeout total da requisição em segundos (padrão 5 s).
                 Limita o impacto na latência do pipeline de análise.

    Returns:
        {"id": str, "rev": str, "ok": True}

    Raises:
        CloudantError e subclasses em caso de falha.
    """
    if not settings.ibm_cloudant_url or not settings.ibm_cloudant_apikey:
        raise CloudantError("Credenciais do Cloudant não configuradas.")

    doc = dict(data)
    if doc_id:
        doc["_id"] = doc_id
    elif "_id" not in doc:
        doc["_id"] = str(uuid.uuid4())

    token = _get_iam_token_sync()
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(_db_url(), headers=_auth_headers(token), json=doc)
    _raise_for_status(resp)
    return resp.json()


# ---------------------------------------------------------------------------
# Verificação síncrona (health check — mantida para compatibilidade)
# ---------------------------------------------------------------------------

def verificar_cloudant() -> dict:
    """Verifica se o banco Cloudant está acessível. Versão síncrona."""

    if not settings.ibm_cloudant_url or not settings.ibm_cloudant_apikey:
        raise RuntimeError("Credenciais do Cloudant não configuradas.")

    token = _get_iam_token_sync()

    with httpx.Client(timeout=30) as client:
        resp = client.get(
            _db_url(),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()

    dados = resp.json()
    return {
        "conectado": True,
        "banco": dados.get("db_name"),
        "documentos": dados.get("doc_count"),
    }
