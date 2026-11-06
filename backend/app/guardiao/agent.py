
"""
Grafo LangGraph do agente Guardião.

RF-G-01..06, RF-G-19: fluxo agêntico de 6 etapas conforme o PDF:
  1. intake           → receber e sanitizar input
  2. level1_analysis  → análise da mensagem (sinais de engenharia social)
  3. level2_analysis  → análise personalizada (perfil do usuário)
  4. context_cross    → cruzamento com transação pendente
  5. decision         → aplicar regras de alto risco
  6. intervention     → intervir OU prosseguir (dois caminhos)
  7. followup         → acompanhamento e orientação final
  8. audit_log        → registrar decisão (sem dados pessoais)

NOTA: O nó de auditoria é sempre o último, independente do caminho.
"""

from __future__ import annotations

from typing import cast

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.guardiao.state import AgentState
from app.guardiao.nodes.intake import intake_node
from app.guardiao.nodes.level1_analysis import level1_analysis_node
from app.guardiao.nodes.level2_analysis import level2_analysis_node
from app.guardiao.nodes.context_cross import context_cross_node
from app.guardiao.nodes.decision import decision_node
from app.guardiao.nodes.intervention import intervention_node
from app.guardiao.nodes.followup import followup_node
from app.audit.logger import audit_log_node


def _route_after_decision(state: AgentState) -> str:
    """
    Roteamento condicional após a decisão.

    - Se abortado por erro: followup
    - Se requer intervenção: intervention
    - Caso contrário: followup direto
    """
    if state.get("aborted"):
        return "followup"

    if state.get("requires_intervention"):
        return "intervention"

    return "followup"


def build_guardiao_graph() -> CompiledStateGraph:
    """Constrói e compila o grafo do agente Guardião."""

    graph = StateGraph(AgentState)

    # Registra todos os nós.
    graph.add_node("intake", intake_node)
    graph.add_node("level1_analysis", level1_analysis_node)
    graph.add_node("level2_analysis", level2_analysis_node)
    graph.add_node("context_cross", context_cross_node)
    graph.add_node("decision", decision_node)
    graph.add_node("intervention", intervention_node)
    graph.add_node("followup", followup_node)
    graph.add_node("audit_log", audit_log_node)

    # Define o nó inicial.
    graph.set_entry_point("intake")

    # Etapas sequenciais.
    graph.add_edge("intake", "level1_analysis")
    graph.add_edge("level1_analysis", "level2_analysis")
    graph.add_edge("level2_analysis", "context_cross")
    graph.add_edge("context_cross", "decision")

    # Roteamento após a decisão.
    graph.add_conditional_edges(
        "decision",
        _route_after_decision,
        {
            "intervention": "intervention",
            "followup": "followup",
        },
    )

    # Intervenção, acompanhamento e auditoria.
    graph.add_edge("intervention", "followup")
    graph.add_edge("followup", "audit_log")
    graph.add_edge("audit_log", END)

    return graph.compile()


# Instância compilada reutilizada entre requisições.
guardiao_graph = build_guardiao_graph()


def run_guardiao(
    raw_input: str,
    user_id: str = "",
    input_channel: str = "text",
    transaction_id: str | None = None,
    language_profile: str = "standard",
) -> AgentState:
    """
    Executa a análise completa do Guardião.

    Args:
        raw_input: texto bruto do usuário.
        user_id: ID sintético do usuário.
        input_channel: canal de origem.
        transaction_id: transação pendente, se houver.
        language_profile: "standard" ou "low".

    Returns:
        AgentState final com os resultados da análise.
    """

    initial_state: AgentState = {
        "raw_input": raw_input,
        "user_id": user_id,
        "input_channel": input_channel,
        "transaction_id": transaction_id,
        "intervention_profile": language_profile,
        "aborted": False,
        "audit_logged": False,

        # Inicializa as estruturas utilizadas pelos nós.
        "level1_result": {},
        "level2_result": {},
        "context_result": {},
        "decision_rules_triggered": [],
        "intervention_data": {},
        "requires_intervention": False,
        "requires_human_review": False,
        "final_risk_score": 0.0,
        "final_risk_label": "baixo",
    }

    result = guardiao_graph.invoke(initial_state)

    return cast(AgentState, result)
