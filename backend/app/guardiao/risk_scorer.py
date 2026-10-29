"""
Motor de pontuação de risco explicável do Guardião — Nível 1.

RF-G-07: análise da mensagem (sinais de engenharia social).
RF-G-13: pontuação de risco em porcentagem + classificação qualitativa.
RNF-03: toda pontuação acompanhada de lista de sinais e justificativa.

Princípio: pontuação 100% DETERMINÍSTICA baseada em regras explícitas.
O LLM é usado APENAS para redigir a explicação narrativa — nunca para calcular o score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class RiskSignal:
    """Um sinal de risco identificado na mensagem."""
    signal_id: str
    label: str
    description: str
    weight: float          # contribuição para o score (0.0 – 1.0)
    evidence: str          # trecho da mensagem que ativou o sinal


@dataclass
class Level1Result:
    """Resultado da análise de Nível 1."""
    signals: list[RiskSignal] = field(default_factory=list)
    risk_score: float = 0.0        # 0–100  (sempre float, mesmo sem sinais)
    risk_label: str = "baixo"      # baixo | médio | alto
    summary: str = ""


# ---------------------------------------------------------------------------
# Definição das regras de Nível 1
# Cada regra tem: id, label, padrões regex, peso, descrição
# ---------------------------------------------------------------------------

_RULES: list[dict] = [
    {
        "signal_id": "pedido_de_dinheiro",
        "label": "Pedido de dinheiro/Pix",
        "patterns": [
            # Pix apenas quando acompanhado de verbo de solicitação (evita FP em perguntas/contextos neutros)
            r"\bfa[cç]a\s+(um\s+)?pix\b",
            r"\bmanda\s+(um\s+)?pix\b",
            r"\benvia\s+(um\s+)?pix\b",
            r"\bpix\s+de\s+R\$",
            r"\bme\s+(manda|envia|passa)\b.{0,50}\b(dinheiro|real|reais|r\$)\b",
            r"\bpreciso\s+que\s+voc[eê]\s+(fa[cç]a|mande|envie)\b",
            r"\btransfer[eê]ncia\b.{0,40}\b(para\s+mim|urgente|agora)\b",
            r"\bdep[oó]sito\b.{0,40}\b(para\s+mim|urgente|agora)\b",
            r"\bme\s+paga\b",
        ],
        "weight": 25.0,
        "description": "A mensagem contém pedido explícito de transferência de dinheiro ou Pix.",
    },
    {
        "signal_id": "urgencia",
        "label": "Criação de urgência",
        "patterns": [
            r"\bagora\b",
            r"\burgente\b",
            r"\br[aá]pido\b",
            r"\bhoje\b",
            r"\bpreciso\s+muito\b",
            r"\bemerg[eê]ncia\b",
            r"\bnem espera\b",
            r"\bpra\s+ontem\b",
        ],
        "weight": 20.0,
        "description": "A mensagem usa linguagem de urgência para pressionar a vítima a agir sem reflexão.",
    },
    {
        "signal_id": "mudanca_de_numero",
        "label": "Troca de número/contato",
        "patterns": [
            r"\bnovo\s+(n[uú]mero|whatsapp|contato|chip)\b",
            r"\btroquei\s+o\s+(n[uú]mero|chip|celular)\b",
            r"\bmudei\s+(de\s+)?(n[uú]mero|chip|celular|whatsapp)\b",
            r"\beste\s+[eé]\s+(meu\s+)?novo",
            r"\bmeu\s+(n[uú]mero|chip|celular|whatsapp)\s+mudou\b",
            r"\bn[uú]mero\s+mudou\b",
        ],
        "weight": 25.0,
        "description": "A mensagem informa troca de número ou contato, técnica clássica do 'golpe do número novo'.",
    },
    {
        "signal_id": "se_passar_por_conhecido",
        "label": "Tentativa de se passar por alguém",
        "patterns": [
            r"\bsou\s+(eu|a\s+sua|o\s+seu|teu|tua)\b",
            r"\b[eé]\s+(a\s+sua|o\s+seu)\s+\w+\b",
            r"\baqui\s+[eé]\b",
            r"\bme\s+reconhece\b",
            # golpe do número novo: saudação familiar COM pedido de dinheiro/número novo na mesma mensagem
            # (apenas a saudação não dispara — deve haver combinação com outro sinal)
            r"\b(oi|ol[aá])\s*,?\s*(m[aã]e|pai|filho|filha|v[oó]|v[oó]v[oó])\b.{0,100}(n[uú]mero|pix|transfer|dinheiro)\b",
        ],
        "weight": 20.0,
        "description": "A mensagem tenta afirmar identidade de familiar ou conhecido sem mecanismo de verificação.",
    },
    {
        "signal_id": "link_suspeito",
        "label": "Link suspeito",
        "patterns": [
            r"https?://(?!(?:www\.)?(?:bb\.com\.br|bancodobrasil\.com\.br))[^\s]+",
            r"\bclique\s+aqui\b",
            r"\bacesse\s+(agora|o\s+link)\b",
            r"\bverificar\b.{0,30}\blink\b",
        ],
        "weight": 30.0,
        "description": "A mensagem contém link externo que não pertence ao domínio oficial do Banco do Brasil.",
    },
    {
        "signal_id": "pedido_de_credencial",
        "label": "Pedido de senha, token ou dado pessoal",
        "patterns": [
            r"\bsenha\b",
            r"\btoken\b",
            r"\bcpf\b",
            r"\bc[oó]digo\s+(de\s+)?verifica[cç][aã]o\b",
            r"\bdados\s+(pessoais|banc[aá]rios)\b",
            r"\bnúmero\s+(do\s+)?cart[aã]o\b",
        ],
        "weight": 35.0,
        "description": "A mensagem solicita senha, token ou dado pessoal sensível — bancos legítimos nunca pedem isso por mensagem.",
    },
    {
        "signal_id": "impersonation_banco",
        "label": "Falsa identidade de banco ou suporte",
        "patterns": [
            r"\b(banco\s+do\s+brasil|bb|suporte\s+(t[eé]cnico|bb)|central\s+de\s+atendimento)\b.{0,80}\b(suspeito|bloquei|irregular|verific)\b",
            r"\bdetectamos\b",
            r"\bidentificamos\s+(acesso|movimento)\b",
            r"\bseu\s+(acesso|conta)\s+(foi|est[aá])\s+(bloqueado|irregular|suspeito)\b",
            # "sou do suporte BB", "sou da central de atendimento"
            r"\bsou\s+(do|da)\s+(suporte|central|atendimento|equipe)\b",
            r"\bsou\s+(do\s+)?(banco|bb)\b",
        ],
        "weight": 30.0,
        "description": "A mensagem se passa por comunicação oficial de banco ou suporte técnico para criar alarme falso.",
    },
    {
        "signal_id": "oferta_suspeita",
        "label": "Oferta ou prêmio suspeito",
        "patterns": [
            r"\bparab[eé]ns\b.{0,50}\b(ganhou|selecionado|contemplado)\b",
            r"\bpremia[cç][aã]o\b",
            r"\bliber[ae]r\b.{0,30}\bpix\b",
            r"\btaxa\s+de\s+(confirma[cç][aã]o|libera[cç][aã]o|cadastro)\b",
        ],
        "weight": 30.0,
        "description": "A mensagem oferece prêmio ou benefício condicionado a pagamento ou dado pessoal.",
    },
]


# ---------------------------------------------------------------------------
# Faixas de risco únicas (documentadas e aplicadas em todo o sistema)
# 0–29   → baixo   — nenhuma ação imediata
# 30–59  → médio   — atenção, verificar remetente
# 60–84  → alto    — intervenção recomendada
# 85–100 → crítico — intervenção obrigatória + revisão humana
# ---------------------------------------------------------------------------

RISK_THRESHOLDS = {
    "crítico":  85.0,
    "alto":     60.0,
    "médio":    30.0,
}


def _classify_risk(score: float) -> str:
    if score >= RISK_THRESHOLDS["crítico"]:
        return "crítico"
    if score >= RISK_THRESHOLDS["alto"]:
        return "alto"
    if score >= RISK_THRESHOLDS["médio"]:
        return "médio"
    return "baixo"


def analyze_level1(message: str) -> Level1Result:
    """
    Executa a análise de Nível 1 sobre a mensagem sanitizada.

    A pontuação é determinística: soma dos pesos dos sinais detectados,
    com cap em 100. O LLM NÃO participa deste cálculo.

    Args:
        message: texto já sanitizado pelo prompt_guard (pode conter
                 os delimitadores <conteudo_usuario>...</conteudo_usuario>).

    Returns:
        Level1Result com sinais detectados, score e classificação.
    """
    # Remove delimitadores de segurança para análise de padrões
    clean = re.sub(r"</?conteudo_usuario>", "", message).strip()
    msg_lower = clean.lower()

    signals: list[RiskSignal] = []

    for rule in _RULES:
        matched_evidence = ""
        for pattern_str in rule["patterns"]:
            m = re.search(pattern_str, msg_lower)
            if m:
                # captura até 60 chars ao redor do match como evidência
                start = max(0, m.start() - 20)
                end = min(len(clean), m.end() + 20)
                matched_evidence = clean[start:end].strip()
                break

        if matched_evidence:
            signals.append(
                RiskSignal(
                    signal_id=rule["signal_id"],
                    label=rule["label"],
                    description=rule["description"],
                    weight=rule["weight"],
                    evidence=f"...{matched_evidence}...",
                )
            )

    # Score = soma dos pesos, limitado a 100 (float garantido mesmo sem sinais)
    raw_score = sum(s.weight for s in signals)
    score = float(min(raw_score, 100.0))

    result = Level1Result(
        signals=signals,
        risk_score=round(score, 1),
        risk_label=_classify_risk(score),
        summary=_build_summary(signals, score),
    )
    return result


def _build_summary(signals: list[RiskSignal], score: float) -> str:
    """Gera resumo textual determinístico (sem LLM) para o log de auditoria."""
    if not signals:
        return "Nenhum sinal de risco identificado na mensagem."
    labels = ", ".join(s.label for s in signals)
    return (
        f"Detectados {len(signals)} sinal(is) de risco: {labels}. "
        f"Score de risco calculado: {score:.1f}%."
    )
