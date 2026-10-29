"""
Nó 2b do agente Guardião: Análise de Nível 2.

RF-G-03, RF-G-04, RF-G-08, RF-G-20.
"""

from __future__ import annotations

from app.guardiao.level2_analyzer import analyze_level2
from app.guardiao.state import AgentState


def level2_analysis_node(state: AgentState) -> AgentState:
    """
    Executa a análise personalizada de Nível 2.
    Ajusta o score do Nível 1 com base no perfil sintético do usuário.
    """
    if state.get("aborted"):
        return state

    l1 = state.get("level1_result", {})
    result = analyze_level2(
        sanitized_input=state.get("sanitized_input", ""),
        user_id=state.get("user_id", ""),
        level1_risk_score=l1.get("risk_score", 0.0),
        level1_signals=l1.get("signals", []),
    )

    state["level2_result"] = {
        "anomalies": [
            {
                "anomaly_id": a.anomaly_id,
                "label": a.label,
                "description": a.description,
                "score_delta": a.score_delta,
                "criterion": a.criterion,
            }
            for a in result.anomalies
        ],
        "score_delta": result.score_delta,
        "adjusted_risk_score": result.adjusted_risk_score,
        "adjusted_risk_label": result.adjusted_risk_label,
        "profile_found": result.profile_found,
        "summary": result.summary,
    }
    return state
