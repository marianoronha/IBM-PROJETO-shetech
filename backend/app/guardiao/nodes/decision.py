"""
Nó de decisão do agente Guardião.

Aplica as regras de alto risco (risk_rules.py) e decide se há intervenção.
RN-01: a decisão NÃO depende apenas do LLM — é baseada em regras explícitas.
RC-04: marca flag de revisão humana quando necessário.
"""

from __future__ import annotations

from app.guardiao.risk_rules import evaluate_risk_rules, requires_human_review
from app.guardiao.state import AgentState


def decision_node(state: AgentState) -> AgentState:
    """
    Avalia as regras de risco e popula:
      - requires_intervention: bool
      - requires_human_review: bool
      - decision_rules_triggered: lista de regras disparadas (para auditoria)
    """
    if state.get("aborted"):
        return state

    requires_intervention, rule_results = evaluate_risk_rules(state)
    final_score = state.get("final_risk_score", 0.0)

    state["requires_intervention"] = requires_intervention
    state["requires_human_review"] = requires_human_review(final_score)
    state["decision_rules_triggered"] = [
        {
            "rule_id": r.rule_id,
            "triggered": r.triggered,
            "reason": r.reason,
        }
        for r in rule_results
    ]
    return state
