"""
Testes do CRUD no IBM Cloudant com documentos sintéticos.

Esses testes exigem as variáveis de ambiente IBM_CLOUDANT_URL e IBM_CLOUDANT_APIKEY.
Se as variáveis não estiverem configuradas, os testes são ignorados automaticamente.

Execução:
    cd backend
    python -m pytest tests/test_cloudant_crud.py -v

Os documentos criados neste teste têm prefixo "test_crud_" no _id e são
excluídos ao final de cada execução (cleanup). Nunca tocam em documentos reais.
"""

from __future__ import annotations

import pytest

from app.config import settings


# ── Skip condicional: sem credenciais não há banco real para testar ──────────

def _has_cloudant_credentials() -> bool:
    return bool(settings.ibm_cloudant_url and settings.ibm_cloudant_apikey)


pytestmark = pytest.mark.skipif(
    not _has_cloudant_credentials(),
    reason="IBM_CLOUDANT_URL ou IBM_CLOUDANT_APIKEY não configurados — teste ignorado.",
)


# ── Importação do módulo apenas quando as credenciais existem ────────────────

from app.cloudant import (
    create_document,
    get_document,
    update_document,
    delete_document,
    list_documents,
    verificar_cloudant,
    CloudantNotFound,
    CloudantConflict,
)


# ── Constantes do documento de teste ────────────────────────────────────────

TEST_DOC_ID = "test_crud_shetech_synthetic_001"


# ── Limpeza antes e após os testes ──────────────────────────────────────────

async def _cleanup_doc():
    """Remove o documento de teste se existir."""
    try:
        doc = await get_document(TEST_DOC_ID)
        await delete_document(TEST_DOC_ID, doc["_rev"])
    except CloudantNotFound:
        pass  # OK — já não existe
    except Exception:
        pass  # Conexão indisponível, continua sem erro


@pytest.fixture(scope="module", autouse=True)
async def cleanup_before_and_after():
    """Remove o documento de teste antes e após todos os testes do módulo."""
    await _cleanup_doc()
    yield
    await _cleanup_doc()


# ── Testes de health check ───────────────────────────────────────────────────

class TestCloudantHealthCheck:
    """Verifica se o banco está acessível antes dos testes CRUD."""

    def test_verificar_cloudant(self):
        resultado = verificar_cloudant()
        assert resultado["conectado"] is True
        assert resultado["banco"] == "shetech_db"
        assert isinstance(resultado["documentos"], int)


# ── Testes de CREATE ─────────────────────────────────────────────────────────

class TestCloudantCreate:
    """CREATE — cria um documento sintético de teste."""

    async def test_create_document_with_explicit_id(self):
        data = {
            "tipo": "teste_sintetico",
            "descricao": "Documento criado pelo teste de CRUD automatizado.",
            "versao": 1,
            "ativo": True,
        }
        result = await create_document(data, doc_id=TEST_DOC_ID)
        assert result.get("ok") is True
        assert result.get("id") == TEST_DOC_ID
        assert "rev" in result

    async def test_create_fails_duplicate_id(self):
        """Tentar criar com mesmo ID deve falhar com CloudantConflict."""
        data = {"tipo": "duplicado"}
        with pytest.raises(CloudantConflict):
            await create_document(data, doc_id=TEST_DOC_ID)


# ── Testes de READ ───────────────────────────────────────────────────────────

class TestCloudantRead:
    """READ — lê o documento criado pelo teste anterior."""

    async def test_get_document_exists(self):
        doc = await get_document(TEST_DOC_ID)
        assert doc["_id"] == TEST_DOC_ID
        assert doc["tipo"] == "teste_sintetico"
        assert doc["versao"] == 1

    async def test_get_document_not_found(self):
        with pytest.raises(CloudantNotFound):
            await get_document("id_inexistente_xyz_12345")

    async def test_list_documents_returns_data(self):
        result = await list_documents(limit=5, include_docs=True)
        assert "rows" in result
        assert isinstance(result["rows"], list)
        assert "total_rows" in result


# ── Testes de UPDATE ─────────────────────────────────────────────────────────

class TestCloudantUpdate:
    """UPDATE — atualiza o documento de teste respeitando _rev."""

    async def test_update_document(self):
        # Lê a revisão atual
        doc = await get_document(TEST_DOC_ID)
        current_rev = doc["_rev"]

        updated = await update_document(
            TEST_DOC_ID,
            rev=current_rev,
            data={
                "tipo": "teste_sintetico",
                "descricao": "Documento atualizado pelo teste de CRUD.",
                "versao": 2,
                "ativo": True,
            },
        )
        assert updated.get("ok") is True
        assert updated.get("id") == TEST_DOC_ID
        # Revisão deve ter mudado
        assert updated.get("rev") != current_rev

    async def test_update_with_wrong_rev_raises_conflict(self):
        """Fornecer uma revisão obsoleta deve gerar CloudantConflict."""
        with pytest.raises(CloudantConflict):
            await update_document(
                TEST_DOC_ID,
                rev="1-abcdef123456789_revisao_errada",
                data={"tipo": "conflito"},
            )

    async def test_get_updated_document(self):
        """Verifica que a atualização foi persistida."""
        doc = await get_document(TEST_DOC_ID)
        assert doc["versao"] == 2
        assert doc["descricao"] == "Documento atualizado pelo teste de CRUD."


# ── Testes de DELETE ─────────────────────────────────────────────────────────

class TestCloudantDelete:
    """DELETE — exclui o documento de teste."""

    async def test_delete_with_wrong_rev_raises_conflict(self):
        """Excluir com revisão errada deve gerar CloudantConflict."""
        with pytest.raises(CloudantConflict):
            await delete_document(TEST_DOC_ID, rev="1-revisao_errada_xyzabc")

    async def test_delete_document(self):
        doc = await get_document(TEST_DOC_ID)
        result = await delete_document(TEST_DOC_ID, rev=doc["_rev"])
        assert result.get("ok") is True

    async def test_get_deleted_document_not_found(self):
        with pytest.raises(CloudantNotFound):
            await get_document(TEST_DOC_ID)

    async def test_delete_non_existent_raises_not_found(self):
        with pytest.raises(CloudantNotFound):
            await delete_document("id_inexistente_deletar_xyz", rev="1-abc")
