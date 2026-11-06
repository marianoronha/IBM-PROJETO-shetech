"""
API REST de autenticação e perfil de usuários — SheTech Guardião.

Endpoints:
  POST /api/auth/register          — Cadastro de novo usuário
  POST /api/auth/login             — Login, retorna JWT Bearer token
  GET  /api/auth/me                — Lê perfil do usuário autenticado
  PATCH /api/auth/me               — Atualiza nome e/ou telefone
  POST /api/auth/me/change-password — Altera senha (exige senha atual)
  DELETE /api/auth/me              — Exclui própria conta

Segurança:
  - Senhas armazenadas como Argon2id (passlib).
  - Autenticação por JWT Bearer token (python-jose).
  - Nenhum campo sensível (senha_hash, cpf_hash) é exposto ao frontend.
  - Rate-limiting de tentativas de login por e-mail (in-process, 5 tentativas/5 min).
  - Validações de entrada (Pydantic) com mensagens de erro genéricas.
  - Nenhuma informação sobre existência de conta em erros de login.
"""

from __future__ import annotations

import re
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, field_validator
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.users.repository import (
    create_user,
    get_user_by_id,
    get_user_with_password,
    update_user_profile,
    update_user_password,
    delete_user,
)
from app.cloudant import CloudantNotFound, CloudantError

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hashing de senha — Argon2id com configuração segura
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=True)

_JWT_SUBJECT = "shetech-user"


def _create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": user_id,
        "iss": _JWT_SUBJECT,
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> str:
    """Retorna user_id ou levanta HTTPException 401."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=_JWT_SUBJECT,
        )
        user_id: str = payload["sub"]
        return user_id
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Token inválido ou expirado.", "code": "UNAUTHORIZED"},
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    """Dependency — valida o Bearer token e retorna o documento público do usuário."""
    user_id = _decode_token(credentials.credentials)
    try:
        return await get_user_by_id(user_id)
    except CloudantNotFound:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Conta não encontrada.", "code": "UNAUTHORIZED"},
        )
    except CloudantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Serviço temporariamente indisponível.", "code": "SERVICE_UNAVAILABLE"},
        )


# ---------------------------------------------------------------------------
# Rate limiting de login (in-process — simples e sem dependências extras)
# Janela deslizante: 5 tentativas falhadas em 5 minutos por e-mail.
# ---------------------------------------------------------------------------

_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_S = 5 * 60  # 5 minutos


def _check_rate_limit(email: str) -> None:
    now = time.monotonic()
    attempts = [t for t in _login_attempts[email] if now - t < _WINDOW_S]
    _login_attempts[email] = attempts
    if len(attempts) >= _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "Muitas tentativas de login. Aguarde alguns minutos.", "code": "RATE_LIMITED"},
        )


def _record_failed_attempt(email: str) -> None:
    _login_attempts[email].append(time.monotonic())


def _clear_attempts(email: str) -> None:
    _login_attempts.pop(email, None)


# ---------------------------------------------------------------------------
# Validações de senha (regra mínima: 8 chars, maiúscula, número, símbolo)
# ---------------------------------------------------------------------------

_MIN_PWD_LEN = 8


def _validate_password_strength(v: str) -> str:
    errors = []
    if len(v) < _MIN_PWD_LEN:
        errors.append(f"mínimo {_MIN_PWD_LEN} caracteres")
    if not re.search(r"[A-Z]", v):
        errors.append("uma letra maiúscula")
    if not re.search(r"[0-9]", v):
        errors.append("um número")
    if not re.search(r"[^A-Za-z0-9]", v):
        errors.append("um símbolo")
    if errors:
        raise ValueError(f"Senha fraca: exige {', '.join(errors)}.")
    return v


# ---------------------------------------------------------------------------
# Schemas de entrada e saída
# ---------------------------------------------------------------------------

_PERFIL_VALUES = {"usuario", "gerente", "analista"}


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", re.IGNORECASE)


def _validate_email(v: str) -> str:
    v = v.strip().lower()
    if not _EMAIL_RE.match(v):
        raise ValueError("E-mail inválido.")
    return v


class RegisterRequest(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120)
    email: str = Field(..., max_length=254)

    @field_validator("email")
    @classmethod
    def _email_valido(cls, v: str) -> str:
        return _validate_email(v)

    cpf: str = Field(..., min_length=11, max_length=14, description="CPF com ou sem formatação.")
    nascimento: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="YYYY-MM-DD")
    telefone: str = Field(default="", max_length=20)
    perfil: str = Field(default="usuario")
    senha: str = Field(..., min_length=8, max_length=128)
    aceite_termos: bool = Field(..., description="Deve ser true para prosseguir.")

    @field_validator("perfil")
    @classmethod
    def _perfil_valido(cls, v: str) -> str:
        if v not in _PERFIL_VALUES:
            raise ValueError(f"Perfil inválido. Use: {', '.join(_PERFIL_VALUES)}")
        return v

    @field_validator("senha")
    @classmethod
    def _senha_forte(cls, v: str) -> str:
        return _validate_password_strength(v)

    @field_validator("aceite_termos")
    @classmethod
    def _aceite_obrigatorio(cls, v: bool) -> bool:
        if not v:
            raise ValueError("É necessário aceitar os termos de uso.")
        return v

    @field_validator("cpf")
    @classmethod
    def _cpf_apenas_digitos(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) != 11:
            raise ValueError("CPF inválido.")
        return digits  # armazena apenas dígitos


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=254)
    senha: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email_valido(cls, v: str) -> str:
        return _validate_email(v)



class UserResponse(BaseModel):
    """Dados públicos do usuário — nunca inclui senha_hash nem cpf_hash."""
    id: str
    nome: str
    email: str
    telefone: str
    perfil: str
    nascimento: str
    criado_em: str

    @classmethod
    def from_doc(cls, doc: dict) -> "UserResponse":
        return cls(
            id=doc["_id"],
            nome=doc.get("nome", ""),
            email=doc.get("email", ""),
            telefone=doc.get("telefone", ""),
            perfil=doc.get("perfil", "usuario"),
            nascimento=doc.get("nascimento", ""),
            criado_em=doc.get("criado_em", ""),
        )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UpdateProfileRequest(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=2, max_length=120)
    telefone: Optional[str] = Field(default=None, max_length=20)


class ChangePasswordRequest(BaseModel):
    senha_atual: str = Field(..., min_length=1, max_length=128)
    nova_senha: str = Field(..., min_length=8, max_length=128)

    @field_validator("nova_senha")
    @classmethod
    def _nova_senha_forte(cls, v: str) -> str:
        return _validate_password_strength(v)


class ErrorResponse(BaseModel):
    error: str
    code: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse, "description": "E-mail ou CPF já cadastrado"},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Cadastra um novo usuário",
)
async def register(req: RegisterRequest) -> UserResponse:
    """
    Cria uma conta nova.

    - Normaliza o e-mail para lowercase.
    - Verifica unicidade de e-mail e CPF (via hash).
    - Armazena a senha como Argon2id — nunca em texto puro.
    - Retorna os dados públicos do usuário (sem senha nem CPF).
    """
    try:
        doc = await create_user(
            nome=req.nome,
            email=str(req.email),
            senha_hash=hash_password(req.senha),
            cpf_raw=req.cpf,
            nascimento=req.nascimento,
            telefone=req.telefone,
            perfil=req.perfil,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": str(exc), "code": "CONFLICT"},
        )
    except CloudantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Serviço temporariamente indisponível.", "code": "SERVICE_UNAVAILABLE"},
        )

    return UserResponse.from_doc(doc)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Autentica e retorna um JWT Bearer token",
)
async def login(req: LoginRequest) -> LoginResponse:
    """
    Autentica o usuário por e-mail + senha.

    - Rate limiting: bloqueia após 5 tentativas falhadas em 5 minutos.
    - Mensagens de erro genéricas — não revela se o e-mail existe.
    - Retorna JWT Bearer token com validade de 7 dias (configurável).
    """
    email_norm = req.email.strip().lower()
    _check_rate_limit(email_norm)

    try:
        doc = await get_user_with_password(email_norm)
    except CloudantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Serviço temporariamente indisponível.", "code": "SERVICE_UNAVAILABLE"},
        )

    # Verificação de credenciais com mensagem genérica (não revela existência de conta)
    _INVALID_CREDS = {
        "error": "E-mail ou senha incorretos.",
        "code": "INVALID_CREDENTIALS",
    }

    if not doc:
        _record_failed_attempt(email_norm)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDS)

    if not verify_password(req.senha, doc.get("senha_hash", "")):
        _record_failed_attempt(email_norm)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID_CREDS)

    _clear_attempts(email_norm)

    token = _create_token(doc["_id"])
    return LoginResponse(
        access_token=token,
        user=UserResponse.from_doc(doc),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Retorna o perfil do usuário autenticado",
)
async def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse.from_doc(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Atualiza nome e/ou telefone do usuário autenticado",
)
async def update_me(
    req: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    if req.nome is None and req.telefone is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "Informe ao menos um campo para atualizar.", "code": "NO_FIELDS"},
        )
    try:
        doc = await update_user_profile(
            current_user["_id"],
            nome=req.nome,
            telefone=req.telefone,
        )
    except CloudantNotFound:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Conta não encontrada.", "code": "UNAUTHORIZED"},
        )
    except CloudantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Serviço temporariamente indisponível.", "code": "SERVICE_UNAVAILABLE"},
        )
    return UserResponse.from_doc(doc)


@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Altera a senha do usuário autenticado",
)
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
) -> None:
    # Re-lê o documento completo (com senha_hash) para verificação
    try:
        full_doc = await get_user_with_password(current_user["email"])
    except CloudantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Serviço temporariamente indisponível.", "code": "SERVICE_UNAVAILABLE"},
        )

    if not full_doc or not verify_password(req.senha_atual, full_doc.get("senha_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "Senha atual incorreta.", "code": "INVALID_CREDENTIALS"},
        )

    try:
        await update_user_password(current_user["_id"], hash_password(req.nova_senha))
    except CloudantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Serviço temporariamente indisponível.", "code": "SERVICE_UNAVAILABLE"},
        )


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
    summary="Exclui permanentemente a própria conta",
)
async def delete_me(current_user: dict = Depends(get_current_user)) -> None:
    """
    Exclui a conta do usuário autenticado.

    Operação permanente e irreversível.
    O token continua tecnicamente válido até expirar, mas a conta não existirá.
    """
    try:
        await delete_user(current_user["_id"])
    except CloudantNotFound:
        # Conta já inexistente — trata como sucesso
        pass
    except CloudantError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "Serviço temporariamente indisponível.", "code": "SERVICE_UNAVAILABLE"},
        )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
    summary="Encerra a sessão (instrui o cliente a descartar o token)",
)
async def logout(current_user: dict = Depends(get_current_user)) -> None:
    """
    Endpoint de logout.

    JWT é stateless — não há revogação server-side nesta implementação.
    O endpoint valida o token, confirma a autenticação e sinaliza ao cliente
    que deve descartar o token localmente.

    Em uma implementação futura, o token pode ser adicionado a uma blocklist
    persistida no Cloudant até sua expiração natural.
    """
    # No-op server-side: o cliente deve remover gd_token do localStorage.
