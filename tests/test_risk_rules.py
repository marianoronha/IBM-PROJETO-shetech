"""
Testes unitários das regras de alto risco.

Cobre:
  RN-01: regras claras, versionadas, testáveis — decisão NÃO depende do LLM.
  T-07: falso positivo (mensagem legítima não pode ser pausada).
  T-07: falso negativo (golpe claro deve ser pausado).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from app.guardiao.risk_rules import (
    evaluate_risk_rules,
    requires_human_review,
    rule_score_threshold,
    rule_credential_request,
    rule_suspicious_link,
    rule_number_change_plus_pix,
    HIGH_RISK_SCORE_THRESHOLD,
    HUMAN_REVIEW_SCORE_THRESHOLD,
    RULES_VERSION,
)


def _make_state(
    score: float = 0.0,
    signals: list[dict] | None = None,
) -> dict:
    return {
        "final_risk_score": score,
        "level1_result": {"signals": signals or []},
        "level2_result": {},
    }


class TestRulesVersioned:
    def test_rules_version_exists(self):
        """Regras devem ter versão explícita (RN-01: versionadas)."""
        assert RULES_VERSION is not None
        assert len(RULES_VERSION) > 0


class TestRuleScoreThreshold:
    def test_score_abaixo_limiar_nao_dispara(self):
        state = _make_state(score=59.9)
        r = rule_score_threshold(state)
        assert not r.triggered

    def test_score_no_limiar_dispara(self):
        state = _make_state(score=60.0)
        r = rule_score_threshold(state)
        assert r.triggered

    def test_score_acima_limiar_dispara(self):
        state = _make_state(score=85.0)
        r = rule_score_threshold(state)
        assert r.triggered


class TestRuleCredential:
    def test_sem_credencial_nao_dispara(self):
        state = _make_state(signals=[{"signal_id": "urgencia"}])
        r = rule_credential_request(state)
        assert not r.triggered

    def test_com_credencial_dispara(self):
        state = _make_state(signals=[{"signal_id": "pedido_de_credencial"}])
        r = rule_credential_request(state)
        assert r.triggered


class TestRuleLink:
    def test_sem_link_nao_dispara(self):
        state = _make_state(signals=[{"signal_id": "urgencia"}])
        r = rule_suspicious_link(state)
        assert not r.triggered

    def test_com_link_dispara(self):
        state = _make_state(signals=[{"signal_id": "link_suspeito"}])
        r = rule_suspicious_link(state)
        assert r.triggered


class TestRuleNumeroNovo:
    def test_so_numero_nao_dispara(self):
        state = _make_state(signals=[{"signal_id": "mudanca_de_numero"}])
        r = rule_number_change_plus_pix(state)
        assert not r.triggered

    def test_so_pix_nao_dispara(self):
        state = _make_state(signals=[{"signal_id": "pedido_de_dinheiro"}])
        r = rule_number_change_plus_pix(state)
        assert not r.triggered

    def test_numero_mais_pix_dispara(self):
        state = _make_state(signals=[
            {"signal_id": "mudanca_de_numero"},
            {"signal_id": "pedido_de_dinheiro"},
        ])
        r = rule_number_change_plus_pix(state)
        assert r.triggered


class TestEvaluateRiskRules:
    def test_sem_sinais_sem_intervencao(self):
        """Falso positivo: mensagem sem sinais não deve gerar intervenção."""
        state = _make_state(score=0.0, signals=[])
        requires, results = evaluate_risk_rules(state)
        assert not requires, "Falso positivo: mensagem limpa não deve intervir"

    def test_score_baixo_sem_sinais_nao_intervem(self):
        """Falso positivo: score baixo, sem sinais críticos."""
        state = _make_state(score=25.0, signals=[{"signal_id": "urgencia"}])
        requires, results = evaluate_risk_rules(state)
        assert not requires

    def test_score_alto_intervem(self):
        """Falso negativo: score alto deve sempre gerar intervenção."""
        state = _make_state(score=75.0, signals=[{"signal_id": "urgencia"}])
        requires, results = evaluate_risk_rules(state)
        assert requires

    def test_credencial_sempre_intervem_independente_score(self):
        """R-002: credencial dispara intervenção mesmo com score baixo."""
        state = _make_state(score=10.0, signals=[{"signal_id": "pedido_de_credencial"}])
        requires, results = evaluate_risk_rules(state)
        assert requires, "R-002: pedido de credencial deve sempre intervir"

    def test_numero_novo_pix_intervem(self):
        """R-004: golpe do número novo deve sempre gerar intervenção."""
        state = _make_state(score=50.0, signals=[
            {"signal_id": "mudanca_de_numero"},
            {"signal_id": "pedido_de_dinheiro"},
        ])
        requires, results = evaluate_risk_rules(state)
        assert requires

    def test_link_suspeito_intervem(self):
        """R-003: link suspeito deve gerar intervenção."""
        state = _make_state(score=30.0, signals=[{"signal_id": "link_suspeito"}])
        requires, results = evaluate_risk_rules(state)
        assert requires

    def test_todos_resultados_tem_rule_id(self):
        """Todos os resultados devem ter rule_id para auditoria (RN-01)."""
        state = _make_state(score=80.0, signals=[{"signal_id": "link_suspeito"}])
        _, results = evaluate_risk_rules(state)
        for r in results:
            assert r.rule_id, f"Regra sem rule_id: {r}"


class TestHumanReview:
    def test_score_baixo_nao_requer_revisao(self):
        assert not requires_human_review(50.0)

    def test_score_no_limiar_requer_revisao(self):
        assert requires_human_review(HUMAN_REVIEW_SCORE_THRESHOLD)

    def test_score_100_requer_revisao(self):
        assert requires_human_review(100.0)
