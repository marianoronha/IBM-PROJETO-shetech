"""
Repositório de usuários no IBM Cloudant.

Responsabilidades:
  - Criar, ler, atualizar e excluir documentos de usuário em shetech_db.
  - Verificar unicidade de e-mail antes do cadastro.
  - Nunca expor hash de senha fora deste módulo.
  - Nunca armazenar mensagens, imagens ou dados do Guardião.

Estrutura do documento Cloudant (tipo "user"):
{
    "_id":          str  (UUID gerado automaticamente),
    "_rev":         str  (controle de revisão do Cloudant),
    "tipo":         "user",
    "email":        str  (normalizado para lowercase, único),
    "nome":         str,
    "telefone":     str  (opcional),
    "perfil":       str  ("usuario" | "gerente" | "analista"),
    "nascimento":   str  (YYYY-MM-DD),
    "cpf_hash":     str  (hash SHA-256 do CPF sem formatação — para detecção
                          de duplicatas sem armazenar o CPF em texto puro),
    "senha_hash":   str  (Argon2id via passlib),
    "criado_em":    str  (ISO-8601 UTC),
    "atualizado_em": str (ISO-8601 UTC),
}
"""

from __future__ import annotations

import hashlib
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from app.cloudant import (
    create_document,
    get_document,
    update_document,
    delete_document,
    list_documents,
    CloudantError,
    CloudantNotFound,
    _db_url,
    _auth_headers,
    _get_iam_token_async,
    _raise_for_status,
)

import httpx

logger = logging.getLogger(__name__)

# Prefixo interno nos _id de usuário — facilita consultas e evita colisões
_USER_ID_PREFIX = "user_"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_cpf(cpf_raw: str) -> str:
    """Hash SHA-256 do CPF (somente dígitos) para detecção de duplicatas."""
    digits = "".join(c for c in cpf_raw if c.isdigit())
    return hashlib.sha256(digits.encode()).hexdigest()


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _user_doc_id() -> str:
    return f"{_USER_ID_PREFIX}{uuid.uuid4()}"


def _strip_sensitive(doc: dict[str, Any]) -> dict[str, Any]:
    """Remove campos que nunca devem sair do repositório."""
    return {k: v for k, v in doc.items() if k not in ("senha_hash", "cpf_hash")}


# ---------------------------------------------------------------------------
# Consulta por e-mail — usa _all_docs com filtro manual (banco pequeno no MVP)
# Em produção, criar índice Cloudant ou usar Mango Query.
# ---------------------------------------------------------------------------

async def _find_by_email(email: str) -> Optional[dict[str, Any]]:
    """Retorna o documento de usuário (completo, com senha_hash) ou None."""
    normalized = _normalize_email(email)
    try:
        result = await list_documents(limit=100, include_docs=True)
        for row in result.get("rows", []):
            doc = row.get("doc", {})
            if doc.get("tipo") == "user" and doc.get("email") == normalized:
                return doc
    except CloudantError:
        pass
    return None


async def _find_by_cpf_hash(cpf_hash: str) -> Optional[dict[str, Any]]:
    """Verifica se o CPF já está cadastrado."""
    try:
        result = await list_documents(limit=100, include_docs=True)
        for row in result.get("rows", []):
            doc = row.get("doc", {})
            if doc.get("tipo") == "user" and doc.get("cpf_hash") == cpf_hash:
                return doc
    except CloudantError:
        pass
    return None


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

async def create_user(
    nome: str,
    email: str,
    senha_hash: str,
    cpf_raw: str,
    nascimento: str,
    telefone: str = "",
    perfil: str = "usuario",
) -> dict[str, Any]:
    """
    Cria um novo usuário.

    Returns:
        Documento público (sem senha_hash nem cpf_hash).

    Raises:
        ValueError: e-mail ou CPF já cadastrado.
        CloudantError: falha de banco.
    """
    email_norm = _normalize_email(email)
    cpf_h = _hash_cpf(cpf_raw)

    if await _find_by_email(email_norm):
        raise ValueError("E-mail já cadastrado.")
    if await _find_by_cpf_hash(cpf_h):
        raise ValueError("CPF já cadastrado.")

    now = _now_iso()
    doc: dict[str, Any] = {
        "tipo": "user",
        "email": email_norm,
        "nome": nome.strip(),
        "telefone": telefone.strip(),
        "perfil": perfil,
        "nascimento": nascimento,
        "cpf_hash": cpf_h,
        "senha_hash": senha_hash,
        "criado_em": now,
        "atualizado_em": now,
    }
    result = await create_document(doc, doc_id=_user_doc_id())
    doc["_id"] = result["id"]
    doc["_rev"] = result["rev"]
    return _strip_sensitive(doc)


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

async def get_user_by_id(user_id: str) -> dict[str, Any]:
    """
    Lê documento de usuário por _id.

    Returns:
        Documento público.

    Raises:
        CloudantNotFound: usuário não existe.
    """
    doc = await get_document(user_id)
    if doc.get("tipo") != "user":
        raise CloudantNotFound(f"Usuário não encontrado: {user_id}")
    return _strip_sensitive(doc)


async def get_user_with_password(email: str) -> Optional[dict[str, Any]]:
    """
    Retorna documento COMPLETO (incluindo senha_hash) para verificação de login.

    Nunca usar para retornar dados ao cliente.
    """
    return await _find_by_email(email)


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

async def update_user_profile(
    user_id: str,
    nome: Optional[str] = None,
    telefone: Optional[str] = None,
) -> dict[str, Any]:
    """
    Atualiza nome e/ou telefone do usuário.

    Returns:
        Documento público atualizado.
    """
    doc = await get_document(user_id)
    if doc.get("tipo") != "user":
        raise CloudantNotFound(f"Usuário não encontrado: {user_id}")

    if nome is not None:
        doc["nome"] = nome.strip()
    if telefone is not None:
        doc["telefone"] = telefone.strip()
    doc["atualizado_em"] = _now_iso()

    result = await update_document(user_id, rev=doc["_rev"], data=doc)
    doc["_rev"] = result["rev"]
    return _strip_sensitive(doc)


async def update_user_password(user_id: str, new_senha_hash: str) -> None:
    """Substitui o hash de senha do usuário."""
    doc = await get_document(user_id)
    if doc.get("tipo") != "user":
        raise CloudantNotFound(f"Usuário não encontrado: {user_id}")

    doc["senha_hash"] = new_senha_hash
    doc["atualizado_em"] = _now_iso()
    await update_document(user_id, rev=doc["_rev"], data=doc)


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

async def delete_user(user_id: str) -> None:
    """
    Exclui permanentemente a conta do usuário.

    Raises:
        CloudantNotFound: usuário não existe.
    """
    doc = await get_document(user_id)
    if doc.get("tipo") != "user":
        raise CloudantNotFound(f"Usuário não encontrado: {user_id}")
    await delete_document(user_id, rev=doc["_rev"])
