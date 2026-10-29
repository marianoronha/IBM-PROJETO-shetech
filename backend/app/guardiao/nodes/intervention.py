"""
Nó de Intervenção do Guardião (Etapa 5 do fluxo do PDF).

RF-G-05: pausa temporária, explicação do motivo, confirmação mais segura, orientação.
RF-G-14..17: tipo do golpe, como é aplicado, sinais de alerta, próximo passo.
RF-G-18: explicação em pelo menos dois perfis de linguagem.
RN-02: cliente mantém o controle — decide o que fazer após a explicação.
RN-03: toda resposta com motivo transparente.
RC-04: flag de revisão humana quando aplicável.

DOIS FLUXOS DISTINTOS:
  (a) Mensagem isolada (sem transaction_id) — gera ALERTA + orientação.
      Não menciona "pausa"; não há transação para pausar.
  (b) Pix em andamento (com transaction_id) — gera PAUSA temporária +
      botão de atendente + confirmação segura.

ARQUITETURA DE SEGURANÇA:
  - A DECISÃO de intervir é 100% determinística (risk_rules.py).
  - O LLM é chamado APENAS para redigir a explicação em linguagem natural.
  - O LLM recebe SOMENTE metadados de análise (sinais, score, tipo de golpe).
  - A mensagem original do usuário NÃO é passada diretamente ao LLM.
"""

from __future__ import annotations

from app.guardiao.profiles import get_profile_instruction, get_profile_label
from app.guardiao.state import AgentState

# ---------------------------------------------------------------------------
# Catálogo de tipos de golpe — 7 categorias + fallback genérico
# ---------------------------------------------------------------------------

_SCAM_TYPE_MAP: dict[str, dict] = {
    "golpe_numero_novo": {
        "name": "Golpe do Número Novo",
        "how_it_works": (
            "O golpista finge ser um familiar ou amigo que trocou de número. "
            "Cria urgência (ex.: precisa de dinheiro agora) para que a vítima "
            "faça um Pix sem verificar a identidade pelo número original."
        ),
        "how_applied": (
            "1. Golpista envia mensagem de número desconhecido dizendo ser familiar.\n"
            "2. Alega ter trocado de chip ou celular.\n"
            "3. Pede Pix urgente antes que a vítima possa ligar para confirmar."
        ),
    },
    "falso_suporte_tecnico": {
        "name": "Falsa Suspensão de Conta / Suporte Falso",
        "how_it_works": (
            "O golpista se passa por funcionário do banco ou suporte técnico, "
            "alegando acesso suspeito ou bloqueio na conta. "
            "Envia link falso e pede credenciais ou token para 'resolver'."
        ),
        "how_applied": (
            "1. Golpista envia SMS/e-mail com alerta de 'acesso suspeito'.\n"
            "2. Inclui link falso que imita o site do banco.\n"
            "3. Na página falsa, coleta senha, token e dados pessoais."
        ),
    },
    "phishing_credencial": {
        "name": "Phishing de Credenciais",
        "how_it_works": (
            "O golpista finge ser do atendimento do banco e solicita dados "
            "pessoais ou bancários sob pretexto de estorno ou regularização. "
            "Bancos legítimos nunca pedem senha ou token por mensagem."
        ),
        "how_applied": (
            "1. Golpista contata a vítima fingindo ser do suporte.\n"
            "2. Alega cobrança indevida ou problema na conta.\n"
            "3. Solicita CPF, senha ou token para 'resolver' o problema."
        ),
    },
    "falso_premio": {
        "name": "Golpe do Falso Prêmio",
        "how_it_works": (
            "O golpista informa que a vítima ganhou um prêmio e exige "
            "um Pix como 'taxa de liberação' — o prêmio nunca existe."
        ),
        "how_applied": (
            "1. Golpista envia mensagem de 'parabéns, você foi sorteado'.\n"
            "2. Exige pagamento de taxa para liberar o prêmio.\n"
            "3. Após receber o Pix, some sem entregar nada."
        ),
    },
    "falso_boleto_qr": {
        "name": "Falso Boleto ou QR Code",
        "how_it_works": (
            "O golpista envia boleto ou QR Code adulterado com dados bancários falsos. "
            "O pagamento vai para a conta do golpista em vez do destinatário legítimo."
        ),
        "how_applied": (
            "1. Golpista intercepta ou falsifica boleto/QR Code.\n"
            "2. Envia à vítima como se fosse a cobrança real.\n"
            "3. A vítima paga sem perceber que os dados foram alterados."
        ),
    },
    "falso_sequestro": {
        "name": "Falso Sequestro / Extorsão",
        "how_it_works": (
            "O golpista liga ou manda mensagem afirmando ter sequestrado um familiar, "
            "exigindo dinheiro imediatamente. A vítima é pressionada a não desligar "
            "nem contatar ninguém enquanto faz o Pix."
        ),
        "how_applied": (
            "1. Golpista liga fingindo ter a vítima ou um familiar em seu poder.\n"
            "2. Mantém a linha aberta para criar pânico e impedir verificação.\n"
            "3. Exige Pix imediato como 'resgate'."
        ),
    },
    "falsa_central_cartao": {
        "name": "Falsa Central de Cartão",
        "how_it_works": (
            "O golpista liga fingindo ser da central do cartão de crédito/débito, "
            "informando compras suspeitas. Pede que a vítima destrua o cartão e "
            "entregue-o a um 'motoboy' ou informe a senha para 'cancelamento'."
        ),
        "how_applied": (
            "1. Golpista liga informando fraude no cartão da vítima.\n"
            "2. Pede que a vítima confirme senha ou entregue o cartão físico.\n"
            "3. Usa os dados para compras fraudulentas ou clona o cartão."
        ),
    },
    "desconhecido": {
        "name": "Alerta de Engenharia Social",
        "how_it_works": (
            "A mensagem apresenta padrões associados a golpes digitais, "
            "como criação de urgência, pedido de dinheiro ou link suspeito. "
            "O tipo específico não foi identificado com certeza."
        ),
        "how_applied": (
            "Golpistas adaptam suas abordagens constantemente. "
            "Os sinais detectados seguem padrões conhecidos de engenharia social."
        ),
    },
}

# ---------------------------------------------------------------------------
# Contatos oficiais — CONFIRMAR ANTES DE PUBLICAR EM PRODUÇÃO
# ---------------------------------------------------------------------------

_OFFICIAL_CONTACTS = {
    "telefone_capitais": "4004-0001",
    "telefone_demais": "0800-729-0001",
    "site_oficial": "bb.com.br",
    "nota": "Confirmar canais oficiais antes de publicar em produção.",
}

_NEXT_STEP_OFFICIAL = (
    "Em caso de dúvida, NÃO realize a transação. "
    "Entre em contato pelos canais OFICIAIS que você já conhece: "
    f"ligue para o número salvo no seu celular, acesse {_OFFICIAL_CONTACTS['site_oficial']} "
    "diretamente no navegador, ou vá a uma agência do Banco do Brasil. "
    f"Central de atendimento: {_OFFICIAL_CONTACTS['telefone_capitais']} (capitais) / "
    f"{_OFFICIAL_CONTACTS['telefone_demais']} (demais localidades). "
    f"({_OFFICIAL_CONTACTS['nota']})"
)


def _infer_scam_type(l1_signals: list[dict]) -> str:
    """Infere o tipo de golpe mais provável com base nos sinais do Nível 1."""
    signal_ids = {s["signal_id"] for s in l1_signals}

    # Sequência de prioridade: tipos mais específicos primeiro
    if "mudanca_de_numero" in signal_ids and "pedido_de_dinheiro" in signal_ids:
        return "golpe_numero_novo"
    if "link_suspeito" in signal_ids and "pedido_de_credencial" in signal_ids:
        return "falso_suporte_tecnico"
    if "pedido_de_credencial" in signal_ids and "impersonation_banco" in signal_ids:
        return "phishing_credencial"
    if "oferta_suspeita" in signal_ids and "pedido_de_dinheiro" in signal_ids:
        return "falso_premio"
    if "link_suspeito" in signal_ids and "oferta_suspeita" in signal_ids:
        return "falso_boleto_qr"
    if "urgencia" in signal_ids and "pedido_de_dinheiro" in signal_ids and "se_passar_por_conhecido" in signal_ids:
        return "falso_sequestro"
    if "impersonation_banco" in signal_ids and "pedido_de_credencial" not in signal_ids:
        return "falsa_central_cartao"
    return "desconhecido"


def _build_intervention_payload(
    scam_type: str,
    final_score: float,
    risk_label: str,
    signals: list[dict],
    anomalies: list[dict],
    rules_triggered: list[dict],
    language_profile: str,
    requires_human_review: bool,
    pix_flow: bool,
) -> dict:
    """
    Constrói o payload de intervenção de forma DETERMINÍSTICA.

    pix_flow=True  → fluxo (b): Pix em andamento, inclui 'paused': True
    pix_flow=False → fluxo (a): mensagem isolada, alerta sem mencionar pausa
    """
    scam_info = _SCAM_TYPE_MAP.get(scam_type, _SCAM_TYPE_MAP["desconhecido"])
    triggered_rules = [r for r in rules_triggered if r.get("triggered")]
    alert_signals = [s["label"] for s in signals]
    anomaly_labels = [a["label"] for a in anomalies if a.get("score_delta", 0) > 0]

    if language_profile == "low":
        if pix_flow:
            main_message = (
                f"CUIDADO! Esta mensagem pode ser um golpe ({scam_info['name']}).\n\n"
                f"Encontramos {len(signals)} sinal(is) suspeito(s). "
                "Por isso pausamos este Pix para você confirmar com segurança.\n\n"
                "Ligue para a pessoa pelo número que você já tem salvo "
                "antes de prosseguir."
            )
        else:
            main_message = (
                f"CUIDADO! Esta mensagem pode ser um golpe ({scam_info['name']}).\n\n"
                f"Encontramos {len(signals)} sinal(is) suspeito(s):\n"
                + "\n".join(f"• {label}" for label in alert_signals)
                + "\n\nNão faça nenhum pagamento ou informe dados. "
                "Confirme pelo número que você já tem salvo."
            )
    else:
        rules_desc = "; ".join(r["reason"] for r in triggered_rules) or "Score de risco elevado."
        if pix_flow:
            main_message = (
                f"Esta transação Pix foi pausada temporariamente. "
                f"Tipo identificado: {scam_info['name']}.\n\n"
                f"Motivo: {rules_desc}\n"
                + (f"Anomalias de perfil: {', '.join(anomaly_labels)}.\n" if anomaly_labels else "")
                + "\nVerifique a identidade do destinatário por outro canal antes de prosseguir."
            )
        else:
            main_message = (
                f"Alerta: a mensagem apresenta {len(signals)} sinal(is) de risco "
                f"(tipo identificado: {scam_info['name']}).\n\n"
                f"Motivo: {rules_desc}\n"
                + (f"Anomalias de perfil: {', '.join(anomaly_labels)}.\n" if anomaly_labels else "")
                + "\nNão realize nenhuma transferência sem confirmar a identidade "
                "do remetente por canal oficial."
            )

    return {
        # Fluxo
        "pix_flow": pix_flow,
        "paused": pix_flow,           # pausa real só no fluxo (b)
        "pause_is_temporary": pix_flow,

        # Mensagem adaptada ao perfil
        "main_message": main_message,

        # Tipo de golpe
        "scam_type": scam_type,
        "scam_name": scam_info["name"],
        "how_it_works": scam_info["how_it_works"],
        "how_applied": scam_info["how_applied"],

        # Sinais e próximo passo
        "alert_signals": alert_signals,
        "next_step": _NEXT_STEP_OFFICIAL,

        # Perfil de linguagem
        "language_profile": language_profile,
        "language_profile_label": get_profile_label(language_profile),

        # Risco
        "risk_score": final_score,
        "risk_label": risk_label,

        # Revisão humana
        "requires_human_review": requires_human_review,
        "human_review_note": (
            "Este caso está marcado para revisão humana pelo nível crítico de risco."
            if requires_human_review else None
        ),

        # Controle do cliente
        "user_control_note": (
            "Você mantém o controle total. "
            + (
                "Esta é uma pausa temporária para sua proteção. "
                "Após verificar a identidade pelos canais oficiais, "
                "você decide se prossegue ou cancela."
                if pix_flow
                else
                "Esta análise é uma recomendação de segurança. "
                "A decisão final é sempre sua."
            )
        ),
    }


def intervention_node(state: AgentState) -> AgentState:
    """
    Nó 5: Intervenção.

    Determina o fluxo (a) ou (b) e gera o payload determinístico.
    """
    if state.get("aborted"):
        return state

    if not state.get("requires_intervention", False):
        score = state.get("final_risk_score", 0.0)
        label = state.get("final_risk_label", "baixo")
        state["intervention_message"] = (
            f"Nenhum padrão de alto risco detectado. "
            f"Nível de risco: {label} ({score:.0f}%). "
            "Continue atento a mensagens suspeitas."
        )
        state["intervention_data"] = {
            "paused": False,
            "pix_flow": False,
            "risk_score": score,
            "risk_label": label,
        }
        return state

    l1 = state.get("level1_result", {})
    l2 = state.get("level2_result", {})
    signals = l1.get("signals", [])
    anomalies = l2.get("anomalies", [])
    rules_triggered = state.get("decision_rules_triggered", [])
    final_score = state.get("final_risk_score", 0.0)
    risk_label = state.get("final_risk_label", "baixo")
    language_profile = state.get("intervention_profile", "standard")
    human_review = state.get("requires_human_review", False)

    # Fluxo (b) apenas quando há transação Pix correlacionada
    pix_flow: bool = bool(state.get("transaction_id"))

    scam_type = _infer_scam_type(signals)

    payload = _build_intervention_payload(
        scam_type=scam_type,
        final_score=final_score,
        risk_label=risk_label,
        signals=signals,
        anomalies=anomalies,
        rules_triggered=rules_triggered,
        language_profile=language_profile,
        requires_human_review=human_review,
        pix_flow=pix_flow,
    )

    state["intervention_data"] = payload
    state["intervention_message"] = payload["main_message"]
    return state
