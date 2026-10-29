"""
Testes unitários do Nível 2 — análise personalizada.

Cobre:
  RF-G-08: 4 critérios do PDF (quem envia, comum, comunicação, perfil financeiro).
  RF-G-20: aprendizado de padrão do usuário.
  RN-04: equilíbrio FP/FN.

Demonstra a diferença de pontuação entre Nível 1 e Nível 2 para o caso
"número novo" (R$ 800) com dois perfis de usuário diferentes.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from app.guardiao.level2_analyzer import analyze_level2, Level2Result


# Sinais do Nível 1 para o golpe do número novo
_NUMERO_NOVO_SIGNALS = [
    {"signal_id": "pedido_de_dinheiro", "label": "Pedido de dinheiro/Pix", "weight": 25.0},
    {"signal_id": "urgencia", "label": "Criação de urgência", "weight": 20.0},
    {"signal_id": "mudanca_de_numero", "label": "Troca de número/contato", "weight": 25.0},
    {"signal_id": "se_passar_por_conhecido", "label": "Tentativa de se passar por alguém", "weight": 20.0},
]
_NUMERO_NOVO_L1_SCORE = 90.0  # score já alto com 4 sinais

_NUMERO_NOVO_MSG = (
    "<conteudo_usuario>\n"
    "Oi, mãe. Troquei o número. Preciso que você faça um Pix de R$ 800 para mim agora.\n"
    "</conteudo_usuario>"
)


class TestNivelDoisCriterios:
    """RF-G-08: os 4 critérios do PDF devem ser aplicados."""

    def test_criterio1_remetente_nao_verificavel(self):
        """Critério 1: mudança de número → remetente não verificável → aumenta score."""
        result = analyze_level2(
            sanitized_input=_NUMERO_NOVO_MSG,
            user_id="U001",
            level1_risk_score=_NUMERO_NOVO_L1_SCORE,
            level1_signals=_NUMERO_NOVO_SIGNALS,
        )
        anomaly_ids = {a.anomaly_id for a in result.anomalies}
        assert "remetente_nao_verificavel" in anomaly_ids, (
            "Critério 1 não detectado: remetente não verificável ausente"
        )

    def test_criterio2_valor_acima_media_u001(self):
        """
        Critério 2: R$ 800 para U001 (média R$ 150) → razão 5.3x → anomalia de valor.
        """
        result = analyze_level2(
            sanitized_input=_NUMERO_NOVO_MSG,
            user_id="U001",
            level1_risk_score=_NUMERO_NOVO_L1_SCORE,
            level1_signals=_NUMERO_NOVO_SIGNALS,
        )
        anomaly_ids = {a.anomaly_id for a in result.anomalies}
        assert "valor_muito_acima_media" in anomaly_ids, (
            "Critério 2 não detectado: R$ 800 é 5.3x a média de U001 (R$ 150)"
        )

    def test_criterio3_mudanca_comunicacao(self):
        """Critério 3: troca de número → mudança de canal comunicação."""
        result = analyze_level2(
            sanitized_input=_NUMERO_NOVO_MSG,
            user_id="U001",
            level1_risk_score=_NUMERO_NOVO_L1_SCORE,
            level1_signals=_NUMERO_NOVO_SIGNALS,
        )
        anomaly_ids = {a.anomaly_id for a in result.anomalies}
        assert "mudanca_canal_comunicacao" in anomaly_ids, (
            "Critério 3 não detectado: mudança de canal/número"
        )

    def test_criterio4_perfil_financeiro_u001(self):
        """
        Critério 4: R$ 800 / renda R$ 3500 = 22.8% — abaixo de 30%, não dispara.
        Mas para U003 (renda R$ 4800), R$ 800 = 16.7% também não dispara.
        Testamos com valor maior.
        """
        msg_alta = (
            "<conteudo_usuario>\n"
            "Preciso que você faça um Pix de R$ 1200 agora urgente.\n"
            "</conteudo_usuario>"
        )
        sinais_alta = [
            {"signal_id": "pedido_de_dinheiro", "label": "Pedido de dinheiro/Pix", "weight": 25.0},
            {"signal_id": "urgencia", "label": "Urgência", "weight": 20.0},
        ]
        result = analyze_level2(
            sanitized_input=msg_alta,
            user_id="U001",  # renda R$ 3500 → R$ 1200 = 34.3% → dispara
            level1_risk_score=45.0,
            level1_signals=sinais_alta,
        )
        anomaly_ids = {a.anomaly_id for a in result.anomalies}
        assert "valor_alto_vs_renda" in anomaly_ids, (
            "Critério 4 não detectado: R$ 1200 = 34.3% da renda de U001"
        )


class TestDiferencaNivel1Nivel2:
    """
    Demonstra a diferença de pontuação entre Nível 1 e Nível 2
    para o caso 'número novo' (R$ 800) com dois perfis de usuário.

    Exigência explícita do aprovador (T-05).
    """

    def test_score_aumenta_com_perfil_u001_baixa_familiaridade(self):
        """
        U001: média Pix = R$ 150. R$ 800 é 5.3x acima.
        Nível 2 deve AUMENTAR o score além do Nível 1.
        """
        l1_score = 90.0
        result = analyze_level2(
            sanitized_input=_NUMERO_NOVO_MSG,
            user_id="U001",
            level1_risk_score=l1_score,
            level1_signals=_NUMERO_NOVO_SIGNALS,
        )
        print(f"\n[U001] L1={l1_score}% → L2={result.adjusted_risk_score}% (delta={result.score_delta:+.1f})")
        print(f"Resumo: {result.summary}")
        # Score já em 90 → limitado a 100, mas delta deve ser positivo
        assert result.score_delta > 0, (
            f"U001: delta esperado positivo, obtido {result.score_delta}"
        )
        assert result.adjusted_risk_score >= l1_score

    def test_score_menor_com_perfil_u002_contato_habitual(self):
        """
        U002: Luciana M. é contato habitual. Pedido de R$ 200 (< média R$ 420).
        Nível 2 deve REDUZIR o score de Nível 1 (sinal de confiança no remetente).
        """
        msg_luciana = (
            "<conteudo_usuario>\n"
            "Carlos, é a Luciana. Você pode me mandar R$200 pra pagar a pizza?\n"
            "</conteudo_usuario>"
        )
        sinais_luciana = [
            {"signal_id": "pedido_de_dinheiro", "label": "Pedido de dinheiro/Pix", "weight": 25.0},
        ]
        l1_score = 25.0

        result = analyze_level2(
            sanitized_input=msg_luciana,
            user_id="U002",
            level1_risk_score=l1_score,
            level1_signals=sinais_luciana,
        )
        print(f"\n[U002/Luciana] L1={l1_score}% → L2={result.adjusted_risk_score}% (delta={result.score_delta:+.1f})")
        print(f"Resumo: {result.summary}")
        assert result.score_delta <= 0, (
            f"U002/Luciana: delta esperado ≤0 (contato habitual), obtido {result.score_delta}"
        )

    def test_sem_perfil_mantém_score_nivel1(self):
        """Usuário desconhecido → score do Nível 1 é mantido."""
        result = analyze_level2(
            sanitized_input=_NUMERO_NOVO_MSG,
            user_id="U999",  # não existe
            level1_risk_score=70.0,
            level1_signals=_NUMERO_NOVO_SIGNALS,
        )
        assert result.profile_found is False
        assert result.adjusted_risk_score == 70.0

    def test_score_limitado_a_100(self):
        """Score ajustado nunca pode ultrapassar 100."""
        result = analyze_level2(
            sanitized_input=_NUMERO_NOVO_MSG,
            user_id="U001",
            level1_risk_score=95.0,
            level1_signals=_NUMERO_NOVO_SIGNALS,
        )
        assert result.adjusted_risk_score <= 100.0

    def test_score_nao_negativo(self):
        """Score ajustado nunca pode ser negativo."""
        result = analyze_level2(
            sanitized_input="<conteudo_usuario>\nOi tudo bem?\n</conteudo_usuario>",
            user_id="U002",
            level1_risk_score=0.0,
            level1_signals=[],
        )
        assert result.adjusted_risk_score >= 0.0
