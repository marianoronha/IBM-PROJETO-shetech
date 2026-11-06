"""
Testes dos endpoints de autenticação e perfil de usuário.

Estratégia:
  - Todos os testes são feitos contra o app FastAPI via TestClient.
  - O repositório Cloudant é mockado — sem chamadas reais ao banco.
  - Usuários sintéticos são identificados pelo e-mail "test_auth_*@shetech.test".
  - Os testes reais de integração com Cloudant estão em test_cloudant_crud.py.

Cobertura:
  - Cadastro válido, e-mail duplicado, CPF duplicado, senha fraca, aceite obrigatório.
  - Login correto, senha errada, rate limiting.
  - GET /me autenticado e não autenticado.
  - PATCH /me — atualização de nome/telefone.
  - POST /me/change-password — senha atual errada, nova senha fraca.
  - DELETE /me — exclusão da própria conta.
  - Isolamento: nenhum endpoint permite operar em conta alheia.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_VALID_REGISTER = {
    "nome": "Maria Teste",
    "email": "test_auth_maria@shetech.test",
    "cpf": "12345678901",
    "nascimento": "1990-05-15",
    "telefone": "(11) 98888-7777",
    "perfil": "usuario",
    "senha": "Senha@Forte1",
    "aceite_termos": True,
}

_CREATED_USER_DOC = {
    "_id": "user_abc123",
    "_rev": "1-xyz",
    "tipo": "user",
    "email": "test_auth_maria@shetech.test",
    "nome": "Maria Teste",
    "telefone": "(11) 98888-7777",
    "perfil": "usuario",
    "nascimento": "1990-05-15",
    "criado_em": "2026-01-01T00:00:00+00:00",
    "atualizado_em": "2026-01-01T00:00:00+00:00",
    # stripped fields (nunca expostos ao cliente):
    # senha_hash, cpf_hash
}


def _make_token(user_id: str = "user_abc123") -> str:
    """Gera um token JWT válido para testes."""
    from app.api.auth import _create_token
    return _create_token(user_id)


# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------

class TestRegister:

    def test_register_success(self):
        with patch("app.api.auth.create_user", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = _CREATED_USER_DOC
            resp = client.post("/api/auth/register", json=_VALID_REGISTER)

        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "test_auth_maria@shetech.test"
        assert data["nome"] == "Maria Teste"
        assert "senha_hash" not in data
        assert "cpf_hash" not in data

    def test_register_duplicate_email(self):
        from app.users.repository import CloudantError
        with patch("app.api.auth.create_user", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = ValueError("E-mail já cadastrado.")
            resp = client.post("/api/auth/register", json=_VALID_REGISTER)

        assert resp.status_code == 409
        assert "E-mail" in resp.json()["detail"]["error"]

    def test_register_duplicate_cpf(self):
        with patch("app.api.auth.create_user", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = ValueError("CPF já cadastrado.")
            resp = client.post("/api/auth/register", json=_VALID_REGISTER)

        assert resp.status_code == 409

    def test_register_weak_password(self):
        payload = {**_VALID_REGISTER, "senha": "fraca"}
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422

    def test_register_missing_aceite(self):
        payload = {**_VALID_REGISTER, "aceite_termos": False}
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422

    def test_register_invalid_email(self):
        payload = {**_VALID_REGISTER, "email": "nao-e-email"}
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422

    def test_register_invalid_perfil(self):
        payload = {**_VALID_REGISTER, "perfil": "admin"}
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422

    def test_register_invalid_cpf_too_short(self):
        payload = {**_VALID_REGISTER, "cpf": "123"}
        resp = client.post("/api/auth/register", json=payload)
        assert resp.status_code == 422

    def test_register_cloudant_unavailable(self):
        from app.cloudant import CloudantError
        with patch("app.api.auth.create_user", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = CloudantError("timeout", 0)
            resp = client.post("/api/auth/register", json=_VALID_REGISTER)

        assert resp.status_code == 503

    def test_register_does_not_return_password_hash(self):
        doc_with_hash = {**_CREATED_USER_DOC, "senha_hash": "HASH_SHOULD_NOT_APPEAR"}
        with patch("app.api.auth.create_user", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = doc_with_hash
            resp = client.post("/api/auth/register", json=_VALID_REGISTER)

        assert resp.status_code == 201
        assert "senha_hash" not in str(resp.json())
        assert "HASH_SHOULD_NOT_APPEAR" not in str(resp.json())


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

_DOC_WITH_HASH = {
    **_CREATED_USER_DOC,
    "senha_hash": None,  # will be set per test
    "cpf_hash": "irrelevant",
}


class TestLogin:

    def test_login_success(self):
        from app.api.auth import hash_password
        doc = {**_DOC_WITH_HASH, "senha_hash": hash_password("Senha@Forte1")}

        with patch("app.api.auth.get_user_with_password", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = doc
            resp = client.post("/api/auth/login", json={
                "email": "test_auth_maria@shetech.test",
                "senha": "Senha@Forte1",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test_auth_maria@shetech.test"
        assert "senha_hash" not in str(data)

    def test_login_wrong_password(self):
        from app.api.auth import hash_password
        doc = {**_DOC_WITH_HASH, "senha_hash": hash_password("SenhaCorreta@1")}

        with patch("app.api.auth.get_user_with_password", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = doc
            resp = client.post("/api/auth/login", json={
                "email": "test_auth_maria@shetech.test",
                "senha": "SenhaErrada@1",
            })

        assert resp.status_code == 401
        assert "E-mail ou senha incorretos" in resp.json()["detail"]["error"]

    def test_login_unknown_email(self):
        with patch("app.api.auth.get_user_with_password", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            resp = client.post("/api/auth/login", json={
                "email": "inexistente@shetech.test",
                "senha": "Qualquer@1",
            })

        assert resp.status_code == 401
        # Mensagem genérica — não revela que o e-mail não existe
        assert "E-mail ou senha incorretos" in resp.json()["detail"]["error"]

    def test_login_rate_limit(self):
        """Após 5 tentativas falhadas, deve retornar 429."""
        from app.api.auth import _login_attempts
        email = "test_rate_limit@shetech.test"
        # Limpa tentativas anteriores
        _login_attempts.pop(email, None)

        with patch("app.api.auth.get_user_with_password", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            for _ in range(5):
                client.post("/api/auth/login", json={"email": email, "senha": "X"})
            resp = client.post("/api/auth/login", json={"email": email, "senha": "X"})

        assert resp.status_code == 429
        _login_attempts.pop(email, None)  # cleanup


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------

class TestGetMe:

    def test_get_me_authenticated(self):
        token = _make_token("user_abc123")

        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _CREATED_USER_DOC
            resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 200
        assert resp.json()["email"] == "test_auth_maria@shetech.test"

    def test_get_me_no_token(self):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer token.invalido.aqui"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /me
# ---------------------------------------------------------------------------

class TestUpdateMe:

    def test_update_nome(self):
        token = _make_token()
        updated_doc = {**_CREATED_USER_DOC, "nome": "Maria Atualizada"}

        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.auth.update_user_profile", new_callable=AsyncMock) as mock_upd:
            mock_get.return_value = _CREATED_USER_DOC
            mock_upd.return_value = updated_doc

            resp = client.patch(
                "/api/auth/me",
                json={"nome": "Maria Atualizada"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        assert resp.json()["nome"] == "Maria Atualizada"

    def test_update_no_fields_rejected(self):
        token = _make_token()

        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _CREATED_USER_DOC
            resp = client.patch(
                "/api/auth/me",
                json={},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 422

    def test_update_requires_auth(self):
        resp = client.patch("/api/auth/me", json={"nome": "Sem token"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /me/change-password
# ---------------------------------------------------------------------------

class TestChangePassword:

    def test_change_password_success(self):
        from app.api.auth import hash_password
        token = _make_token()
        full_doc = {**_CREATED_USER_DOC, "senha_hash": hash_password("SenhaAntiga@1")}

        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.auth.get_user_with_password", new_callable=AsyncMock) as mock_full, \
             patch("app.api.auth.update_user_password", new_callable=AsyncMock):
            mock_get.return_value = _CREATED_USER_DOC
            mock_full.return_value = full_doc

            resp = client.post(
                "/api/auth/me/change-password",
                json={"senha_atual": "SenhaAntiga@1", "nova_senha": "NovaSenha@2"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 204

    def test_change_password_wrong_current(self):
        from app.api.auth import hash_password
        token = _make_token()
        full_doc = {**_CREATED_USER_DOC, "senha_hash": hash_password("SenhaCorreta@1")}

        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.auth.get_user_with_password", new_callable=AsyncMock) as mock_full:
            mock_get.return_value = _CREATED_USER_DOC
            mock_full.return_value = full_doc

            resp = client.post(
                "/api/auth/me/change-password",
                json={"senha_atual": "SenhaErrada@1", "nova_senha": "NovaSenha@2"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 401

    def test_change_password_weak_new(self):
        token = _make_token()

        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _CREATED_USER_DOC
            resp = client.post(
                "/api/auth/me/change-password",
                json={"senha_atual": "SenhaAntiga@1", "nova_senha": "fraca"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /me
# ---------------------------------------------------------------------------

class TestDeleteMe:

    def test_delete_me_success(self):
        token = _make_token()

        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.auth.delete_user", new_callable=AsyncMock):
            mock_get.return_value = _CREATED_USER_DOC
            resp = client.delete("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert resp.status_code == 204

    def test_delete_me_requires_auth(self):
        resp = client.delete("/api/auth/me")
        assert resp.status_code == 401

    def test_delete_me_cannot_delete_other_user(self):
        """O token de user_abc123 não pode deletar user_outro."""
        token_a = _make_token("user_abc123")
        token_b = _make_token("user_outro")

        # Cada token só enxerga o seu próprio usuário via get_current_user
        # Não há endpoint que aceite um user_id arbitrário — isolamento garantido por design.
        # Este teste confirma que DELETE /me usa SEMPRE o user_id do token.
        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get, \
             patch("app.api.auth.delete_user", new_callable=AsyncMock) as mock_del:
            mock_get.return_value = _CREATED_USER_DOC

            resp = client.delete("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"})
            assert resp.status_code == 204

            deleted_id = mock_del.call_args[0][0]
            assert deleted_id == "user_abc123"   # não "user_outro"


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------

class TestLogout:

    def test_logout_authenticated(self):
        token = _make_token()
        with patch("app.api.auth.get_user_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _CREATED_USER_DOC
            resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 204

    def test_logout_no_token(self):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_logout_invalid_token(self):
        resp = client.post("/api/auth/logout", headers={"Authorization": "Bearer token.invalido"})
        assert resp.status_code == 401
