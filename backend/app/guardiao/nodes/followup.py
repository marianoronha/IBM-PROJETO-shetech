"""
Nó de Acompanhamento do Guardião (Etapa 6 do fluxo do PDF).

RF-G-06: o agente acompanha o caso e orienta os próximos passos.
"""

from __future__ import annotations

from app.guardiao.state import AgentState


# Mensagens de acompanhamento por faixa de risco
# Faixas: baixo (0-29) | médio (30-59) | alto (60-84) | crítico (85-100)
_FOLLOWUP_RISK_MESSAGES = {
    "crítico": (
        "Risco CRÍTICO. Recomendamos ação imediata:\n"
        "1. NÃO realize nenhuma transação relacionada a esta mensagem.\n"
        "2. Ligue agora para a pessoa pelo número que você já tem salvo "
        "(não use o número que veio na mensagem suspeita).\n"
        "3. Se já realizou o Pix, contate o Banco do Brasil imediatamente: "
        "4004-0001 (capitais) ou 0800-729-0001 (demais) — confirmar canais oficiais antes de publicar.\n"
        "4. Registre Boletim de Ocorrência se confirmar o golpe."
    ),
    "alto": (
        "Risco ALTO detectado. Recomendamos:\n"
        "1. Não realize a transação até confirmar a identidade por canal oficial.\n"
        "2. Ligue para o número que você já tem salvo para o suposto remetente.\n"
        "3. Se já fez a transferência, contate o Banco do Brasil: "
        "4004-0001 (capitais) ou 0800-729-0001 (demais) — confirmar canais oficiais antes de publicar.\n"
        "4. Registre Boletim de Ocorrência se confirmar o golpe."
    ),
    "médio": (
        "Risco MÉDIO detectado. Atenção:\n"
        "1. Verifique a identidade do remetente antes de agir.\n"
        "2. Não clique em links suspeitos.\n"
        "3. Em caso de dúvida, entre em contato com o BB pelos canais oficiais."
    ),
    "baixo": (
        "Risco BAIXO. A mensagem não apresentou padrões de golpe conhecidos.\n"
        "Continue atento: golpistas adaptam suas abordagens constantemente."
    ),
}


def followup_node(state: AgentState) -> AgentState:
    """
    Nó 6: Acompanhamento.
    Gera orientação final baseada no nível de risco.
    """
    if state.get("aborted"):
        state["followup_message"] = "Análise não concluída devido a erro no processamento."
        return state

    risk_label = state.get("final_risk_label", "baixo")
    followup = _FOLLOWUP_RISK_MESSAGES.get(risk_label, _FOLLOWUP_RISK_MESSAGES["baixo"])

    state["followup_message"] = followup
    return state
