"""
Nó 1 do agente Guardião: Intake.

RF-G-01: receber input do usuário (canal + mensagem) e iniciar o estado do agente.
RNF-05: sanitiza o input antes de qualquer processamento.
"""

from __future__ import annotations

from app.guardiao.prompt_guard import sanitize_user_input, InputValidationError
from app.guardiao.state import AgentState


def intake_node(state: AgentState) -> AgentState:
    """
    Valida e sanitiza o input do usuário.
    Popula state["sanitized_input"] ou state["error"].
    """
    raw = state.get("raw_input", "")
    try:
        sanitized = sanitize_user_input(raw)
        state["sanitized_input"] = sanitized
        state["error"] = None
    except InputValidationError as exc:
        state["sanitized_input"] = ""
        state["error"] = str(exc)
        state["aborted"] = True
    return state
