"""
Logger de auditoria estruturado.

RNF-04: registra cada decisão da IA e o motivo para auditoria.
RC-01..03: sem dados pessoais — sem texto da mensagem, nome, CPF ou número de conta.
           Usa apenas IDs pseudonimizados e metadados de análise.

Formato: JSON Lines (.jsonl) — uma linha por evento.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.guardiao.state import AgentState

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "audit.jsonl"


def _ensure_log_dir() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _write_event(event: dict) -> None:
    _ensure_log_dir()
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def build_audit_event(state: AgentState) -> dict:
    """
    Constrói um evento de auditoria a partir do estado final do agente.

    GARANTIAS DE PRIVACIDADE (RC-03):
    - NÃO inclui: raw_input, sanitized_input, nome do usuário, CPF, número de conta.
    - INCLUI: user_id (pseudônimo sintético), sinais detectados (rótulos apenas),
              score, regras disparadas, decisão, timestamp.
    """
    l1 = state.get("level1_result", {})
    l2 = state.get("level2_result", {})
    context = state.get("context_result", {})

    return {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "schema_version": "1.0",

        # Identificação pseudonimizada — sem PII
        "user_id_pseudo": state.get("user_id", "unknown"),
        "input_channel": state.get("input_channel", "unknown"),
        "transaction_id": state.get("transaction_id"),

        # Nível 1 — apenas rótulos de sinais (sem texto da mensagem)
        "level1": {
            "signal_ids": [s["signal_id"] for s in l1.get("signals", [])],
            "signal_labels": [s["label"] for s in l1.get("signals", [])],
            "risk_score": l1.get("risk_score"),
            "risk_label": l1.get("risk_label"),
        },

        # Nível 2 — anomalias de perfil (sem dados do perfil)
        "level2": {
            "anomaly_ids": [a["anomaly_id"] for a in l2.get("anomalies", [])],
            "score_delta": l2.get("score_delta"),
            "adjusted_risk_score": l2.get("adjusted_risk_score"),
            "adjusted_risk_label": l2.get("adjusted_risk_label"),
            "profile_found": l2.get("profile_found"),
        },

        # Cruzamento de contexto
        "context": {
            "transaction_found": context.get("transaction_found"),
            "amount_matches_message": context.get("amount_matches_message"),
            "context_score_boost": context.get("context_score_boost"),
        },

        # Decisão final
        "decision": {
            "final_risk_score": state.get("final_risk_score"),
            "final_risk_label": state.get("final_risk_label"),
            "requires_intervention": state.get("requires_intervention"),
            "requires_human_review": state.get("requires_human_review"),
            "rules_triggered": [
                {"rule_id": r["rule_id"], "triggered": r["triggered"]}
                for r in state.get("decision_rules_triggered", [])
            ],
        },

        # Intervenção
        "intervention": {
            "paused": state.get("intervention_data", {}).get("paused", False),
            "scam_type": state.get("intervention_data", {}).get("scam_type"),
            "language_profile": state.get("intervention_profile"),
        },

        # Erros
        "error": state.get("error"),
        "aborted": state.get("aborted", False),
    }


def audit_log_node(state: AgentState) -> AgentState:
    """
    Nó de auditoria — último nó do grafo.
    Registra o evento e marca state["audit_logged"] = True.
    """
    event = build_audit_event(state)
    _write_event(event)
    state["audit_logged"] = True
    return state
