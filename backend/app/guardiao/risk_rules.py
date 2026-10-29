"""
Regras de alto risco do Guardião.

RN-01: decisões de alto risco devem ter regras claras, versionadas e testáveis.
       A decisão de pausar/intervir NÃO pode depender apenas do LLM.

Cada regra é uma função pura: recebe o estado e retorna (triggered: bool, reason: str).
O motor de decisão aplica as regras em ordem e para na primeira que acionar.

VERSÃO DAS REGRAS: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

RULES_VERSION = "1.1.0"

# Faixas de risco — alinhadas com risk_scorer.RISK_THRESHOLDS
# 0–29 baixo | 30–59 médio | 60–84 alto | 85–100 crítico
HIGH_RISK_SCORE_THRESHOLD = 60.0    # intervenção obrigatória a partir daqui
CRITICAL_RISK_SCORE_THRESHOLD = 85.0  # crítico — revisão humana automática

# Limiar para flag de revisão humana (= limiar crítico)
HUMAN_REVIEW_SCORE_THRESHOLD = CRITICAL_RISK_SCORE_THRESHOLD


@dataclass(frozen=True)
class RuleResult:
    triggered: bool
    rule_id: str
    reason: str


# ---------------------------------------------------------------------------
# Definição das regras (puras, sem estado)
# ---------------------------------------------------------------------------

def rule_score_threshold(state: dict) -> RuleResult:
    """
    R-001: Score final ≥ HIGH_RISK_SCORE_THRESHOLD → intervenção obrigatória.
    """
    score = state.get("final_risk_score", 0.0)
    triggered = score >= HIGH_RISK_SCORE_THRESHOLD
    return RuleResult(
        triggered=triggered,
        rule_id="R-001",
        reason=(
            f"Score de risco {score:.1f}% atingiu o limiar de intervenção "
            f"({HIGH_RISK_SCORE_THRESHOLD}%)."
        ) if triggered else f"Score {score:.1f}% abaixo do limiar de intervenção.",
    )


def rule_credential_request(state: dict) -> RuleResult:
    """
    R-002: Pedido de senha/token/CPF → intervenção independente do score.
    Bancos legítimos NUNCA solicitam credenciais por mensagem.
    """
    l1_signals = state.get("level1_result", {}).get("signals", [])
    triggered = any(s["signal_id"] == "pedido_de_credencial" for s in l1_signals)
    return RuleResult(
        triggered=triggered,
        rule_id="R-002",
        reason=(
            "A mensagem solicita senha, token ou dado pessoal. "
            "Instituições legítimas nunca fazem isso por mensagem."
        ) if triggered else "Sem pedido de credencial detectado.",
    )


def rule_suspicious_link(state: dict) -> RuleResult:
    """
    R-003: Link suspeito (fora dos domínios oficiais) → intervenção.
    """
    l1_signals = state.get("level1_result", {}).get("signals", [])
    triggered = any(s["signal_id"] == "link_suspeito" for s in l1_signals)
    return RuleResult(
        triggered=triggered,
        rule_id="R-003",
        reason=(
            "A mensagem contém link que não pertence ao domínio oficial do banco."
        ) if triggered else "Nenhum link suspeito detectado.",
    )


def rule_number_change_plus_pix(state: dict) -> RuleResult:
    """
    R-004: Combinação de troca de número + pedido de Pix → intervenção
    (clássico do 'golpe do número novo').
    """
    l1_signals = {s["signal_id"] for s in state.get("level1_result", {}).get("signals", [])}
    triggered = "mudanca_de_numero" in l1_signals and "pedido_de_dinheiro" in l1_signals
    return RuleResult(
        triggered=triggered,
        rule_id="R-004",
        reason=(
            "Combinação de troca de número com pedido de Pix — padrão do golpe do número novo."
        ) if triggered else "Combinação número novo + Pix não detectada.",
    )


# Registro ordenado das regras — a ordem importa
HIGH_RISK_RULES: list[Callable[[dict], RuleResult]] = [
    rule_credential_request,   # R-002: credencial → sempre intervém
    rule_number_change_plus_pix,  # R-004: golpe clássico
    rule_suspicious_link,      # R-003: link suspeito
    rule_score_threshold,      # R-001: limiar genérico (última verificação)
]


def evaluate_risk_rules(state: dict) -> tuple[bool, list[RuleResult]]:
    """
    Avalia todas as regras e retorna:
      - requires_intervention: True se qualquer regra disparar.
      - results: lista de RuleResult para auditoria.
    """
    results = [rule(state) for rule in HIGH_RISK_RULES]
    requires_intervention = any(r.triggered for r in results)
    return requires_intervention, results


def requires_human_review(final_score: float) -> bool:
    """
    Casos com score ≥ HUMAN_REVIEW_SCORE_THRESHOLD são marcados para
    revisão humana (RC-04, RN-01).
    """
    return final_score >= HUMAN_REVIEW_SCORE_THRESHOLD
