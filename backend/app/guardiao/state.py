"""
Estado compartilhado do agente Guardião (LangGraph TypedDict).

Cada nó lê e escreve neste dicionário tipado.
Nenhuma chave deve conter dados pessoais identificáveis — apenas IDs sintéticos.
"""

from __future__ import annotations

from typing import Any, Optional
from typing_extensions import TypedDict


class AgentState(TypedDict, total=False):
    # --- Entrada ---
    raw_input: str                  # input bruto do usuário (não confiável)
    input_channel: str              # "whatsapp_text" | "sms_text" | "email_text" | etc.
    user_id: str                    # ID sintético do usuário
    transaction_id: Optional[str]   # ID da transação pendente, se houver

    # --- Intake ---
    sanitized_input: str            # input após sanitização anti-injection
    error: Optional[str]            # mensagem de erro, se ocorreu
    aborted: bool                   # True se o fluxo foi abortado por erro

    # --- Nível 1 ---
    level1_result: dict[str, Any]   # sinais, risk_score, risk_label, summary

    # --- Nível 2 ---
    level2_result: dict[str, Any]   # anomalias de perfil, score ajustado

    # --- Cruzamento de contexto ---
    context_result: dict[str, Any]  # transação pendente, compatibilidade

    # --- Decisão ---
    final_risk_score: float         # score final combinado (0–100)
    final_risk_label: str           # "baixo" | "médio" | "alto"
    requires_intervention: bool     # True se score ≥ limiar de alto risco
    requires_human_review: bool     # True se decisão de alto risco (RN-01)
    decision_rules_triggered: list  # resultados de cada regra (para auditoria)

    # --- Intervenção ---
    intervention_message: str       # mensagem ao usuário (perfil-aware)
    intervention_profile: str       # "standard" | "low"
    intervention_data: dict         # payload completo da intervenção
    next_step: str                  # orientação de próximo passo

    # --- Acompanhamento ---
    followup_message: str

    # --- Auditoria ---
    audit_logged: bool
