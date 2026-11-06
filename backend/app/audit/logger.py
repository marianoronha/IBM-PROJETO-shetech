"""
Logger de auditoria estruturado.

RNF-04: registra cada decisão da IA e o motivo para auditoria.
RC-01..03: sem dados pessoais — sem texto da mensagem, nome, CPF ou número de conta.
           Usa apenas IDs pseudonimizados e metadados de análise.

Formato local: JSON Lines (.jsonl) — uma linha por evento.
  Registrado sempre, independente de conectividade.
  No Render (efêmero), serve como fallback de curta duração entre deploys.

Persistência remota (IBM Cloudant):
  Quando as credenciais IBM_CLOUDANT_URL / IBM_CLOUDANT_APIKEY estão configuradas,
  cada evento é gravado de forma SÍNCRONA antes de audit_log_node() retornar.
  Timeout: 5 s. Falhas são logadas mas nunca propagadas — o pipeline de análise
  nunca é interrompido por indisponibilidade do banco.

  O campo state["audit_cloudant_persisted"] reflete com precisão se a gravação
  remota concluiu (True) ou não (False). state["audit_logged"] = True indica
  apenas que o registro local foi feito.

Decisão de design — por que síncrono e não fire-and-forget:
  audit_log_node é um nó SÍNCRONO do LangGraph. FastAPI executa nós síncronos
  em um threadpool (run_in_executor). Nesse contexto, asyncio.create_task() agenda
  tarefas no event-loop principal, mas o retorno do nó não aguarda a conclusão —
  criando uma janela em que o processo pode ser encerrado (SIGTERM no Render)
  antes da gravação. A abordagem síncrona com timeout elimina essa janela.
"""

from __future__ import annotations

import json
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.guardiao.state import AgentState

_LOG_DIR = Path(__file__).parent.parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "audit.jsonl"

logger = logging.getLogger(__name__)

# Timeout para a chamada síncrona ao Cloudant (segundos).
# Limita o impacto na cauda de latência do pipeline de análise.
_CLOUDANT_TIMEOUT_S: float = 5.0


def _ensure_log_dir() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _write_event(event: dict[str, Any]) -> None:
    _ensure_log_dir()
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def build_audit_event(state: AgentState) -> dict[str, Any]:
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


def _persist_audit_to_cloudant_sync(event: dict[str, Any]) -> bool:
    """
    Persiste o evento no Cloudant de forma síncrona com timeout controlado.

    Returns:
        True  — gravação confirmada pelo Cloudant.
        False — Cloudant indisponível, não configurado, ou timeout atingido.

    Nunca propaga exceções — o pipeline nunca é interrompido por falha de banco.
    Credenciais e tokens nunca são incluídos em logs.
    """
    from app.config import settings
    if not settings.ibm_cloudant_url or not settings.ibm_cloudant_apikey:
        return False  # Cloudant não configurado — skip silencioso

    try:
        from app.cloudant import create_document_sync, CloudantError
        doc = dict(event)
        doc["tipo"] = "audit_event"
        create_document_sync(doc, doc_id=event["event_id"], timeout=_CLOUDANT_TIMEOUT_S)
        return True
    except Exception as exc:
        # Loga apenas o tipo da exceção — sem credenciais, tokens ou detalhes internos
        logger.warning(
            "Falha ao persistir evento de auditoria no Cloudant (%s). "
            "Registro local preservado.",
            type(exc).__name__,
        )
        return False


def audit_log_node(state: AgentState) -> AgentState:
    """
    Nó de auditoria — último nó do grafo.

    Fluxo:
      1. Constrói o evento (sem PII).
      2. Grava localmente no audit.jsonl (sempre, sem dependência de rede).
      3. Tenta gravar no Cloudant de forma SÍNCRONA com timeout de 5 s.
      4. Atualiza dois campos do estado:
         - audit_logged             = True  (registro local concluído)
         - audit_cloudant_persisted = True/False (gravação remota confirmada/não)

    O retorno da função só ocorre APÓS a tentativa de persistência remota.
    Isso garante que, quando o endpoint retorna a resposta ao frontend,
    o evento já foi (ou não pôde ser) gravado no Cloudant.
    """
    event = build_audit_event(state)

    # 1. Persiste localmente — não depende de rede, não falha silenciosamente
    _write_event(event)

    # 2. Persiste remotamente — síncrono, com timeout, resultado refletido no estado
    cloudant_ok = _persist_audit_to_cloudant_sync(event)

    state["audit_logged"] = True
    state["audit_cloudant_persisted"] = cloudant_ok
    return state
