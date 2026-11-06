"""
Testes de persistência de auditoria no IBM Cloudant.

Verifica que:
  1. audit_log_node persiste no Cloudant de forma SÍNCRONA (não fire-and-forget).
  2. O documento gravado pode ser lido de volta imediatamente após o nó retornar.
  3. state["audit_cloudant_persisted"] = True apenas quando a gravação confirmou.
  4. state["audit_logged"] = True independente do resultado do Cloudant.
  5. Falhas do Cloudant (timeout, bad URL, erro de rede) são tratadas sem propagar exceção.
  6. Nenhum PII (raw_input, sanitized_input) é incluído no documento gravado.
  7. _persist_audit_to_cloudant_sync retorna False quando Cloudant não está configurado.

Execução:
    cd backend
    python -m pytest tests/test_audit_persistence.py -v

Os documentos têm prefixo "test_audit_" no event_id e são excluídos no cleanup.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from unittest.mock import patch

import pytest

from app.config import settings
from app.audit.logger import (
    build_audit_event,
    _persist_audit_to_cloudant_sync,
    audit_log_node,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _has_cloudant_credentials() -> bool:
    return bool(settings.ibm_cloudant_url and settings.ibm_cloudant_apikey)


def _make_state(user_id: str = "U_TEST_AUDIT") -> dict:
    """Estado mínimo sintético para os testes."""
    return {
        "raw_input": "MENSAGEM_SENSÍVEL_NÃO_DEVE_APARECER_NO_BANCO",
        "sanitized_input": "SANITIZED_NÃO_DEVE_APARECER_NO_BANCO",
        "user_id": user_id,
        "input_channel": "text",
        "transaction_id": None,
        "intervention_profile": "standard",
        "aborted": False,
        "audit_logged": False,
        "audit_cloudant_persisted": False,
        "level1_result": {
            "signals": [{"signal_id": "SIG_01", "label": "urgência", "description": "teste", "evidence": "x"}],
            "risk_score": 55.0,
            "risk_label": "médio",
        },
        "level2_result": {
            "anomalies": [],
            "score_delta": 0.0,
            "adjusted_risk_score": 55.0,
            "adjusted_risk_label": "médio",
            "profile_found": False,
        },
        "context_result": {
            "transaction_found": False,
            "amount_matches_message": False,
            "context_score_boost": 0.0,
        },
        "decision_rules_triggered": [{"rule_id": "R_01", "triggered": True, "reason": "teste"}],
        "final_risk_score": 55.0,
        "final_risk_label": "médio",
        "requires_intervention": False,
        "requires_human_review": False,
        "intervention_data": {},
        "intervention_message": "",
        "followup_message": "Fique atento.",
        "error": None,
    }


# ── Testes de build_audit_event (sem rede) ────────────────────────────────────

class TestBuildAuditEvent:
    """Verifica que build_audit_event nunca inclui dados sensíveis."""

    def test_event_has_required_fields(self):
        event = build_audit_event(_make_state())
        assert "event_id" in event
        assert "timestamp" in event
        assert "schema_version" in event
        assert "level1" in event
        assert "decision" in event

    def test_event_excludes_raw_input(self):
        event = build_audit_event(_make_state())
        event_str = str(event)
        assert "MENSAGEM_SENSÍVEL" not in event_str
        assert "SANITIZED" not in event_str

    def test_event_has_pseudonymized_user_id(self):
        event = build_audit_event(_make_state(user_id="U_PSEUDO_123"))
        assert event["user_id_pseudo"] == "U_PSEUDO_123"

    def test_event_id_is_uuid(self):
        event = build_audit_event(_make_state())
        parsed = uuid.UUID(event["event_id"])
        assert str(parsed) == event["event_id"]


# ── Testes de _persist_audit_to_cloudant_sync sem credenciais ────────────────

class TestPersistWithoutCredentials:
    """Verifica comportamento quando Cloudant não está configurado."""

    def test_returns_false_when_no_credentials(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.ibm_cloudant_url", "")
        monkeypatch.setattr("app.config.settings.ibm_cloudant_apikey", "")
        event = build_audit_event(_make_state())
        result = _persist_audit_to_cloudant_sync(event)
        assert result is False

    def test_returns_false_when_url_missing(self, monkeypatch):
        monkeypatch.setattr("app.config.settings.ibm_cloudant_url", "")
        monkeypatch.setattr("app.config.settings.ibm_cloudant_apikey", "some_key")
        event = build_audit_event(_make_state())
        result = _persist_audit_to_cloudant_sync(event)
        assert result is False


# ── Testes de falhas tratadas (sem rede real) ─────────────────────────────────

class TestPersistFailureHandling:
    """Verifica que falhas nunca propagam exceção e retornam False."""

    def test_network_error_returns_false_not_exception(self, monkeypatch):
        """Simula timeout de rede — deve retornar False, não levantar."""
        import httpx
        monkeypatch.setattr("app.config.settings.ibm_cloudant_url", "https://fake.example.com")
        monkeypatch.setattr("app.config.settings.ibm_cloudant_apikey", "fake_key")

        with patch("httpx.Client.post", side_effect=httpx.ConnectError("Simulated network failure")):
            event = build_audit_event(_make_state())
            result = _persist_audit_to_cloudant_sync(event)

        assert result is False

    def test_audit_log_node_never_raises_on_cloudant_failure(self, monkeypatch, tmp_path):
        """audit_log_node não deve propagar exceções do Cloudant."""
        import httpx
        monkeypatch.setattr("app.config.settings.ibm_cloudant_url", "https://fake.example.com")
        monkeypatch.setattr("app.config.settings.ibm_cloudant_apikey", "fake_key")
        monkeypatch.setattr("app.audit.logger._LOG_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr("app.audit.logger._LOG_DIR", tmp_path)

        with patch("httpx.Client.post", side_effect=httpx.ConnectError("fail")):
            result_state = audit_log_node(_make_state())

        # Deve retornar normalmente — nunca levantar exceção
        assert result_state["audit_logged"] is True
        assert result_state["audit_cloudant_persisted"] is False

    def test_local_file_written_even_when_cloudant_fails(self, monkeypatch, tmp_path):
        """O arquivo local deve ser gravado mesmo com Cloudant indisponível."""
        log_file = tmp_path / "audit.jsonl"
        monkeypatch.setattr("app.audit.logger._LOG_FILE", log_file)
        monkeypatch.setattr("app.audit.logger._LOG_DIR", tmp_path)

        with patch("app.audit.logger._persist_audit_to_cloudant_sync", return_value=False):
            audit_log_node(_make_state())

        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert "event_id" in event
        # Confirma que raw_input não aparece
        assert "MENSAGEM_SENSÍVEL" not in lines[0]

    def test_audit_cloudant_persisted_false_when_cloudant_offline(self, monkeypatch, tmp_path):
        """state['audit_cloudant_persisted'] deve ser False quando gravação falha."""
        monkeypatch.setattr("app.audit.logger._LOG_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr("app.audit.logger._LOG_DIR", tmp_path)

        with patch("app.audit.logger._persist_audit_to_cloudant_sync", return_value=False):
            result_state = audit_log_node(_make_state())

        assert result_state["audit_cloudant_persisted"] is False
        assert result_state["audit_logged"] is True

    def test_audit_cloudant_persisted_true_when_cloudant_succeeds(self, monkeypatch, tmp_path):
        """state['audit_cloudant_persisted'] deve ser True quando gravação confirma."""
        monkeypatch.setattr("app.audit.logger._LOG_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr("app.audit.logger._LOG_DIR", tmp_path)

        with patch("app.audit.logger._persist_audit_to_cloudant_sync", return_value=True):
            result_state = audit_log_node(_make_state())

        assert result_state["audit_cloudant_persisted"] is True
        assert result_state["audit_logged"] is True


# ── Testes de integração real (exigem credenciais) ────────────────────────────

@pytest.mark.skipif(
    not _has_cloudant_credentials(),
    reason="IBM_CLOUDANT_URL ou IBM_CLOUDANT_APIKEY não configurados — teste ignorado.",
)
class TestAuditPersistenceReal:
    """
    Testes de integração contra o Cloudant real.

    Verificam que a gravação é síncrona: o documento pode ser lido de volta
    imediatamente após audit_log_node() retornar, sem nenhuma espera adicional.
    """

    def test_persist_audit_sync_returns_true(self):
        """_persist_audit_to_cloudant_sync retorna True quando grava com sucesso."""
        event = build_audit_event(_make_state())
        event["event_id"] = f"test_audit_{uuid.uuid4()}"

        result = _persist_audit_to_cloudant_sync(event)
        assert result is True

        self._delete_test_doc(event["event_id"])

    def test_audit_log_node_persists_synchronously(self, tmp_path, monkeypatch):
        """
        Prova que a persistência é síncrona:
        o documento existe no Cloudant imediatamente após audit_log_node() retornar,
        sem nenhum asyncio.sleep ou espera adicional.
        """
        monkeypatch.setattr("app.audit.logger._LOG_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr("app.audit.logger._LOG_DIR", tmp_path)

        from app.cloudant import get_document

        result_state = audit_log_node(_make_state())

        assert result_state["audit_logged"] is True
        assert result_state["audit_cloudant_persisted"] is True

        # Recupera o event_id do arquivo local (escrito antes da chamada ao Cloudant)
        lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
        actual_id = json.loads(lines[0])["event_id"]

        # Leitura imediata — sem espera — prova que não é fire-and-forget
        doc = asyncio.run(get_document(actual_id))
        assert doc["_id"] == actual_id
        assert doc["tipo"] == "audit_event"

        # Confirma que PII não foi gravado no Cloudant
        doc_str = str(doc)
        assert "MENSAGEM_SENSÍVEL" not in doc_str
        assert "SANITIZED" not in doc_str

        self._delete_test_doc(actual_id)

    def test_document_has_correct_audit_schema(self, tmp_path, monkeypatch):
        """Verifica que o documento gravado tem todos os campos de auditoria."""
        monkeypatch.setattr("app.audit.logger._LOG_FILE", tmp_path / "audit.jsonl")
        monkeypatch.setattr("app.audit.logger._LOG_DIR", tmp_path)

        from app.cloudant import get_document

        audit_log_node(_make_state())

        lines = (tmp_path / "audit.jsonl").read_text().strip().splitlines()
        actual_id = json.loads(lines[0])["event_id"]

        doc = asyncio.run(get_document(actual_id))
        assert "event_id" in doc
        assert "timestamp" in doc
        assert "schema_version" in doc
        assert "level1" in doc
        assert "decision" in doc
        assert doc["tipo"] == "audit_event"

        self._delete_test_doc(actual_id)

    @staticmethod
    def _delete_test_doc(doc_id: str) -> None:
        """Remove documento de teste do Cloudant (cleanup)."""
        try:
            from app.cloudant import get_document, delete_document
            doc = asyncio.run(get_document(doc_id))
            asyncio.run(delete_document(doc_id, doc["_rev"]))
        except Exception:
            pass
