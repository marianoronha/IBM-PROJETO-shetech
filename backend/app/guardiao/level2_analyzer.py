"""
Análise de Nível 2 do Guardião: análise personalizada pelo perfil do usuário.

RF-G-08: verifica os 4 critérios do PDF:
  1. Quem está enviando (remetente conhecido ou desconhecido?)
  2. É comum para este usuário? (frequência, valor, contato habitual)
  3. A forma de comunicação mudou? (mudança de número/canal)
  4. O pedido combina com o perfil financeiro? (valor vs. histórico)

RF-G-20: aprende o padrão de comunicação e comportamento financeiro.
RN-04: equilíbrio FP/FN — ajuste bidirecional do score.

O ajuste é DETERMINÍSTICO: delta baseado em regras explícitas.
O LLM NÃO participa do cálculo de score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from app.guardiao.user_repository import get_user_profile, get_user_transactions


@dataclass
class PersonalAnomalySignal:
    """Um sinal de anomalia em relação ao perfil do usuário."""
    anomaly_id: str
    label: str
    description: str
    score_delta: float    # positivo = aumenta risco | negativo = reduz risco
    criterion: str        # qual dos 4 critérios do PDF foi aplicado


@dataclass
class Level2Result:
    """Resultado da análise de Nível 2."""
    anomalies: list[PersonalAnomalySignal] = field(default_factory=list)
    score_delta: float = 0.0          # ajuste a aplicar sobre o score do Nível 1
    adjusted_risk_score: float = 0.0  # score final após ajuste
    adjusted_risk_label: str = "baixo"
    profile_found: bool = False
    summary: str = ""


def _classify_risk(score: float) -> str:
    if score >= 60:
        return "alto"
    if score >= 30:
        return "médio"
    return "baixo"


def _extract_amount_from_sanitized(sanitized_input: str) -> Optional[float]:
    """Tenta extrair valor monetário mencionado na mensagem."""
    clean = re.sub(r"</?conteudo_usuario>", "", sanitized_input)
    # Padrão: R$ 800, R$800, 800 reais, 1.200,00
    pattern = r"R\$\s*([\d.,]+)|(\d[\d.,]*)\s*reais"
    m = re.search(pattern, clean, re.IGNORECASE)
    if m:
        raw = (m.group(1) or m.group(2)).replace(".", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _extract_contact_mention(sanitized_input: str) -> str:
    """Extrai menção de remetente/contato na mensagem (sem PII — apenas como referência de análise)."""
    clean = re.sub(r"</?conteudo_usuario>", "", sanitized_input).strip()
    # Retorna os primeiros 50 chars como contexto de remetente (sem expor PII em log)
    return clean[:50] if clean else ""


def analyze_level2(
    sanitized_input: str,
    user_id: str,
    level1_risk_score: float,
    level1_signals: list[dict],
) -> Level2Result:
    """
    Executa a análise personalizada de Nível 2.

    Aplica os 4 critérios do PDF contra o perfil sintético do usuário.
    Retorna anomalias e o score ajustado.

    Args:
        sanitized_input: texto sanitizado pelo prompt_guard.
        user_id: ID sintético do usuário.
        level1_risk_score: score calculado pelo Nível 1.
        level1_signals: lista de sinais do Nível 1 (signal_id, label, ...).

    Returns:
        Level2Result com anomalias e score ajustado.
    """
    profile = get_user_profile(user_id)
    if not profile:
        # Sem perfil: mantém score do Nível 1, registra ausência
        return Level2Result(
            score_delta=0.0,
            adjusted_risk_score=level1_risk_score,
            adjusted_risk_label=_classify_risk(level1_risk_score),
            profile_found=False,
            summary="Perfil do usuário não encontrado. Score mantido do Nível 1.",
        )

    anomalies: list[PersonalAnomalySignal] = []
    transactions = get_user_transactions(user_id)
    l1_signal_ids = {s["signal_id"] for s in level1_signals}

    # ------------------------------------------------------------------
    # CRITÉRIO 1: Quem está enviando?
    # Verifica se o remetente mencionado é um contato habitual.
    # ------------------------------------------------------------------
    known_contacts: list[str] = [c.lower() for c in profile.get("known_contacts", [])]
    mention = _extract_contact_mention(sanitized_input).lower()

    if "mudanca_de_numero" in l1_signal_ids or "se_passar_por_conhecido" in l1_signal_ids:
        # Sinal de troca de número → o remetente real é desconhecido
        anomalies.append(PersonalAnomalySignal(
            anomaly_id="remetente_nao_verificavel",
            label="Remetente não verificável",
            description=(
                "A mensagem afirma ser de um contato conhecido, mas o número/canal "
                "é diferente do habitual. Não é possível confirmar a identidade."
            ),
            score_delta=+15.0,
            criterion="critério_1_quem_envia",
        ))
    else:
        # Verifica se algum contato conhecido aparece na mensagem
        contact_matched = any(c in mention for c in known_contacts if len(c) > 3)
        if contact_matched:
            anomalies.append(PersonalAnomalySignal(
                anomaly_id="remetente_contato_habitual",
                label="Remetente parece ser contato habitual",
                description="O remetente aparenta ser um contato conhecido do usuário.",
                score_delta=-10.0,
                criterion="critério_1_quem_envia",
            ))

    # ------------------------------------------------------------------
    # CRITÉRIO 2: É comum para este usuário?
    # Frequência e valor do Pix comparado ao histórico.
    # ------------------------------------------------------------------
    requested_amount = _extract_amount_from_sanitized(sanitized_input)
    avg_pix = profile.get("avg_pix_amount", 0.0)

    if requested_amount is not None and avg_pix > 0:
        ratio = requested_amount / avg_pix
        if ratio > 3.0:
            anomalies.append(PersonalAnomalySignal(
                anomaly_id="valor_muito_acima_media",
                label="Valor muito acima da média do usuário",
                description=(
                    f"O valor solicitado é {ratio:.1f}x maior que o Pix médio "
                    f"histórico deste usuário (média: R$ {avg_pix:.2f})."
                ),
                score_delta=+20.0,
                criterion="critério_2_comum_para_usuario",
            ))
        elif ratio > 1.5:
            anomalies.append(PersonalAnomalySignal(
                anomaly_id="valor_acima_media",
                label="Valor acima da média do usuário",
                description=(
                    f"O valor solicitado é {ratio:.1f}x maior que o Pix médio "
                    f"histórico (média: R$ {avg_pix:.2f})."
                ),
                score_delta=+8.0,
                criterion="critério_2_comum_para_usuario",
            ))
        elif ratio <= 0.5:
            # Valor muito abaixo — reduz suspeita
            anomalies.append(PersonalAnomalySignal(
                anomaly_id="valor_abaixo_media",
                label="Valor abaixo da média habitual",
                description="O valor solicitado está dentro ou abaixo do padrão do usuário.",
                score_delta=-5.0,
                criterion="critério_2_comum_para_usuario",
            ))

    # Verifica se o recipient da transação pendente é contato habitual
    usual_recipients = [r.lower() for r in profile.get("usual_pix_contacts", [])]
    recent_recipients = [t["recipient"].lower() for t in transactions[-5:]] if transactions else []
    all_known = usual_recipients + recent_recipients

    # ------------------------------------------------------------------
    # CRITÉRIO 3: A forma de comunicação mudou?
    # ------------------------------------------------------------------
    if "mudanca_de_numero" in l1_signal_ids:
        anomalies.append(PersonalAnomalySignal(
            anomaly_id="mudanca_canal_comunicacao",
            label="Mudança incomum no canal/número",
            description=(
                "A mensagem chegou por um número ou canal diferente do habitual. "
                "Mudança brusca de contato é um sinal clássico de golpe."
            ),
            score_delta=+15.0,
            criterion="critério_3_comunicacao_mudou",
        ))

    # ------------------------------------------------------------------
    # CRITÉRIO 4: Compatibilidade com perfil financeiro
    # ------------------------------------------------------------------
    monthly_income = profile.get("monthly_income", 0.0)
    if requested_amount is not None and monthly_income > 0:
        income_ratio = requested_amount / monthly_income
        if income_ratio > 0.3:
            anomalies.append(PersonalAnomalySignal(
                anomaly_id="valor_alto_vs_renda",
                label="Valor representa parcela significativa da renda",
                description=(
                    f"O valor solicitado representa {income_ratio*100:.1f}% "
                    f"da renda mensal estimada do usuário."
                ),
                score_delta=+10.0,
                criterion="critério_4_perfil_financeiro",
            ))

    # Calcula delta total e score ajustado
    total_delta = sum(a.score_delta for a in anomalies)
    adjusted = min(max(level1_risk_score + total_delta, 0.0), 100.0)

    return Level2Result(
        anomalies=anomalies,
        score_delta=round(total_delta, 1),
        adjusted_risk_score=round(adjusted, 1),
        adjusted_risk_label=_classify_risk(adjusted),
        profile_found=True,
        summary=_build_summary(anomalies, level1_risk_score, adjusted),
    )


def _build_summary(
    anomalies: list[PersonalAnomalySignal],
    l1_score: float,
    adjusted: float,
) -> str:
    if not anomalies:
        return f"Sem anomalias de perfil detectadas. Score mantido: {l1_score:.1f}%."
    labels = "; ".join(f"{a.label} ({'+' if a.score_delta >= 0 else ''}{a.score_delta:.0f}pts)" for a in anomalies)
    direction = "aumentado" if adjusted > l1_score else "reduzido"
    return (
        f"Nível 1: {l1_score:.1f}% → Nível 2: {adjusted:.1f}% ({direction}). "
        f"Fatores: {labels}."
    )
