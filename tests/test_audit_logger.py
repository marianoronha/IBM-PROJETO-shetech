"""
Testes unitários do audit logger.

Cobre T-08:
  - JSON estruturado.
  - SEM dados pessoais: sem raw_input, nome, CPF, número de conta.
  - COM: decision, signals (IDs apenas), pontuação, regras, timestamp.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from app.audit.logger import build_audit_event


def _make_full_state() -> dict:
    return {
        "user_id": "U001",
        "input_channel": "whatsapp_text",
        "transaction_id": "TX003",
        "raw_input": "Oi, mãe. Troquei o número. Preciso que você faça um Pix de R$ 800 agora.",
        "sanitized_input": "<conteudo_usuario>Oi, mãe...</conteudo_usuario>",
        "level1_result": {
            "signals": [
                {"signal_id": "pedido_de_dinheiro", "label": "Pedido de dinheiro/Pix"},
                {"signal_id": "urgencia", "label": "Criação de urgência"},
                {"signal_id": "mudanca_de_numero", "label": "Troca de número/contato"},
            ],
            "risk_score": 90.0,
            "risk_label": "alto",
        },
        "level2_result": {
            "anomalies": [
                {"anomaly_id": "valor_muito_acima_media", "label": "Valor muito acima da média", "score_delta": 20.0},
            ],
            "score_delta": 20.0,
            "adjusted_risk_score": 100.0,
            "adjusted_risk_label": "alto",
            "profile_found": True,
        },
        "context_result": {
            "transaction_found": True,
            "amount_matches_message": True,
            "context_score_boost": 15.0,
        },
        "final_risk_score": 100.0,
        "final_risk_label": "alto",
        "requires_intervention": True,
        "requires_human_review": True,
        "decision_rules_triggered": [
            {"rule_id": "R-004", "triggered": True, "reason": "Golpe do número novo"},
            {"rule_id": "R-001", "triggered": True, "reason": "Score ≥ 60%"},
        ],
        "intervention_data": {
            "paused": True,
            "scam_type": "golpe_numero_novo",
        },
        "intervention_profile": "standard",
        "followup_message": "Risco alto detectado...",
        "audit_logged": False,
        "aborted": False,
        "error": None,
    }


class TestBuildAuditEvent:
    def test_tem_campos_obrigatorios(self):
        """Evento de auditoria deve ter todos os campos obrigatórios."""
        event = build_audit_event(_make_full_state())
        for campo in ["event_id", "timestamp", "schema_version", "user_id_pseudo",
                       "level1", "level2", "context", "decision"]:
            assert campo in event, f"Campo obrigatório ausente: {campo}"

    def test_nao_tem_raw_input(self):
        """T-08: evento NÃO deve conter o texto bruto da mensagem."""
        event = build_audit_event(_make_full_state())
        event_str = str(event)
        assert "Troquei o número" not in event_str, "raw_input vazou para o log de auditoria!"
        assert "R$ 800" not in event_str, "Valor da mensagem vazou para o log de auditoria!"

    def test_nao_tem_sanitized_input(self):
        """T-08: evento NÃO deve conter o input sanitizado."""
        event = build_audit_event(_make_full_state())
        assert "sanitized_input" not in event
        assert "conteudo_usuario" not in str(event)

    def test_sinais_apenas_ids_e_labels(self):
        """Sinais devem ser registrados como IDs e rótulos — sem evidência textual."""
        event = build_audit_event(_make_full_state())
        signal_ids = event["level1"]["signal_ids"]
        assert "pedido_de_dinheiro" in signal_ids
        assert "mudanca_de_numero" in signal_ids
        # Sem campo 'evidence' no log
        assert "evidence" not in str(event["level1"])

    def test_decisao_registrada(self):
        """Decisão deve estar registrada no evento."""
        event = build_audit_event(_make_full_state())
        assert event["decision"]["requires_intervention"] is True
        assert event["decision"]["requires_human_review"] is True
        assert len(event["decision"]["rules_triggered"]) == 2

    def test_tem_timestamp_iso(self):
        """Timestamp deve estar em formato ISO 8601."""
        from datetime import datetime
        event = build_audit_event(_make_full_state())
        ts = event["timestamp"]
        parsed = datetime.fromisoformat(ts)
        assert parsed is not None

    def test_event_id_unico(self):
        """Cada evento deve ter ID único."""
        state = _make_full_state()
        e1 = build_audit_event(state)
        e2 = build_audit_event(state)
        assert e1["event_id"] != e2["event_id"]

    def test_estado_abortado_registrado(self):
        """Fluxo abortado deve ser registrado como tal."""
        state = _make_full_state()
        state["aborted"] = True
        state["error"] = "Input contém padrões não permitidos."
        event = build_audit_event(state)
        assert event["aborted"] is True
        assert event["error"] is not None
