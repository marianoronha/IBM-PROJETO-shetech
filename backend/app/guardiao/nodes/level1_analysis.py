"""
Nó 2 do agente Guardião: Análise de Nível 1.

RF-G-02, RF-G-07: identifica sinais de engenharia social na mensagem.
RF-G-13: pontuação de risco em porcentagem.
RNF-03: pontuação acompanhada de lista de sinais e justificativa.
"""

from __future__ import annotations

from app.guardiao.risk_scorer import analyze_level1
from app.guardiao.state import AgentState


def level1_analysis_node(state: AgentState) -> AgentState:
    """
    Executa a análise determinística de Nível 1 sobre o input sanitizado.
    Popula state["level1_result"].
    """
    if state.get("aborted"):
        return state

    sanitized = state.get("sanitized_input", "")
    result = analyze_level1(sanitized)

    state["level1_result"] = {
        "signals": [
            {
                "signal_id": s.signal_id,
                "label": s.label,
                "description": s.description,
                "weight": s.weight,
                "evidence": s.evidence,
            }
            for s in result.signals
        ],
        "risk_score": result.risk_score,
        "risk_label": result.risk_label,
        "summary": result.summary,
    }
    return state
