"""
Nó de cruzamento de contexto (Etapa 3+4 do fluxo do PDF).

RF-G-03: correlaciona comunicação recebida com tentativa de transação.
RF-G-04: cruza mensagem + contexto + transação pendente.
"""

from __future__ import annotations

from app.guardiao.risk_scorer import _classify_risk
from app.guardiao.state import AgentState
from app.guardiao.user_repository import get_pending_transaction


def context_cross_node(state: AgentState) -> AgentState:
    """
    Cruza o risco calculado com o contexto de transação pendente.

    Se há transação pendente cujo valor é compatível com o valor mencionado
    na mensagem, aumenta o score e registra a correlação.
    """
    if state.get("aborted"):
        return state

    l2 = state.get("level2_result", {})
    base_score = l2.get("adjusted_risk_score") or state.get("level1_result", {}).get("risk_score", 0.0)
    base_label = l2.get("adjusted_risk_label", "baixo")

    transaction_id = state.get("transaction_id")
    context_result: dict = {
        "transaction_found": False,
        "transaction_amount": None,
        "amount_matches_message": False,
        "context_score_boost": 0.0,
        "note": "Nenhuma transação pendente informada.",
    }

    if transaction_id:
        tx = get_pending_transaction(transaction_id)
        if tx:
            context_result["transaction_found"] = True
            context_result["transaction_amount"] = tx["amount"]

            # Verifica compatibilidade: transação pendente com valor próximo ao citado
            # (±20% de tolerância)
            from app.guardiao.level2_analyzer import _extract_amount_from_sanitized
            msg_amount = _extract_amount_from_sanitized(state.get("sanitized_input", ""))

            if msg_amount is not None and tx["amount"] > 0:
                ratio = abs(msg_amount - tx["amount"]) / tx["amount"]
                if ratio <= 0.20:
                    context_result["amount_matches_message"] = True
                    context_result["context_score_boost"] = 15.0
                    context_result["note"] = (
                        f"Valor na mensagem (~R$ {msg_amount:.2f}) é compatível "
                        f"com transação pendente (R$ {tx['amount']:.2f}). "
                        "Alta probabilidade de correlação com golpe."
                    )
                else:
                    context_result["note"] = (
                        f"Transação pendente encontrada (R$ {tx['amount']:.2f}), "
                        "mas valor não é compatível com a mensagem."
                    )
            else:
                context_result["note"] = "Transação pendente encontrada, valor não mencionado na mensagem."
        else:
            context_result["note"] = f"Transação {transaction_id} não encontrada."

    # Score final combinado
    boost = context_result["context_score_boost"]
    final_score = min(base_score + boost, 100.0)

    state["context_result"] = context_result
    state["final_risk_score"] = round(final_score, 1)
    state["final_risk_label"] = _classify_risk(final_score)
    return state
