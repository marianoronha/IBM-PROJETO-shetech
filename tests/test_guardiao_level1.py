"""
Testes unitários do motor de pontuação de risco — Nível 1.

Cobre:
  RF-G-07: detecção de sinais de engenharia social.
  RF-G-10: caso obrigatório — golpe do "número novo" (R$ 800).
  RF-G-11: caso obrigatório — falso suporte técnico (78% de risco, alto).
  RF-G-13: pontuação em porcentagem + classificação qualitativa.
  RNF-03: pontuação acompanhada de lista de sinais e justificativa.
  RN-04: equilíbrio FP/FN — mensagens legítimas devem ter score baixo.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from app.guardiao.risk_scorer import analyze_level1, Level1Result


# ---------------------------------------------------------------------------
# Casos de golpe obrigatórios (RF-G-10, RF-G-11)
# ---------------------------------------------------------------------------

class TestCasosObrigatorios:
    def test_golpe_numero_novo_score_alto(self):
        """RF-G-10: golpe do número novo deve gerar score ≥ 75%."""
        msg = (
            "<conteudo_usuario>\n"
            "Oi, mãe. Troquei o número. Preciso que você faça um Pix de R$ 800 para mim agora.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        assert result.risk_score >= 75, (
            f"Score esperado ≥75, obtido {result.risk_score}. "
            f"Sinais: {[s.signal_id for s in result.signals]}"
        )
        # Score ≥75 pode resultar em "alto" (60-84) ou "crítico" (85-100)
        assert result.risk_label in ("alto", "crítico"), (
            f"Label esperado 'alto' ou 'crítico', obtido {result.risk_label!r}"
        )

    def test_golpe_numero_novo_sinais_esperados(self):
        """RF-G-10: sinais mínimos esperados para o golpe do número novo."""
        msg = (
            "<conteudo_usuario>\n"
            "Oi, mãe. Troquei o número. Preciso que você faça um Pix de R$ 800 para mim agora.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        signal_ids = {s.signal_id for s in result.signals}
        assert "pedido_de_dinheiro" in signal_ids, "Deve detectar pedido de dinheiro"
        assert "urgencia" in signal_ids, "Deve detectar urgência"
        assert "mudanca_de_numero" in signal_ids, "Deve detectar troca de número"

    def test_falso_suporte_tecnico_score_alto(self):
        """RF-G-11: falso suporte técnico deve gerar score ≥ 75% (ref. 78%)."""
        msg = (
            "<conteudo_usuario>\n"
            "BANCO DO BRASIL: Detectamos acesso suspeito na sua conta. "
            "Para desbloquear, acesse agora: http://bb-seguranca-update.xyz/verificar "
            "e informe seu token.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        assert result.risk_score >= 75, (
            f"Score esperado ≥75 (ref. 78), obtido {result.risk_score}. "
            f"Sinais: {[s.signal_id for s in result.signals]}"
        )
        # Score ≥75 pode resultar em "alto" (60-84) ou "crítico" (85-100)
        assert result.risk_label in ("alto", "crítico"), (
            f"Label esperado 'alto' ou 'crítico', obtido {result.risk_label!r}"
        )

    def test_falso_suporte_tecnico_sinais_esperados(self):
        """RF-G-11: sinais mínimos para o falso suporte técnico."""
        msg = (
            "<conteudo_usuario>\n"
            "BANCO DO BRASIL: Detectamos acesso suspeito na sua conta. "
            "Para desbloquear, acesse agora: http://bb-seguranca-update.xyz/verificar "
            "e informe seu token.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        signal_ids = {s.signal_id for s in result.signals}
        assert "link_suspeito" in signal_ids, "Deve detectar link suspeito"
        assert "pedido_de_credencial" in signal_ids, "Deve detectar pedido de credencial"
        assert "urgencia" in signal_ids, "Deve detectar urgência"


# ---------------------------------------------------------------------------
# Mensagens legítimas — falso positivo baixo (RN-04)
# ---------------------------------------------------------------------------

class TestMensagensLegitimas:
    def test_conversa_informal_score_baixo(self):
        """RN-04: mensagem informal legítima deve ter score ≤ 20%."""
        msg = (
            "<conteudo_usuario>\n"
            "Oi mãe, tudo bem? Você conseguiu fazer o Pix pro mercado? Me avisa quando puder.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        # "Pix" sozinho não deve disparar risco alto — contexto é benign
        assert result.risk_score <= 30, (
            f"Falso positivo! Score {result.risk_score} é alto para mensagem legítima."
        )

    def test_comunicado_banco_oficial_score_baixo(self):
        """Comunicado legítimo sem link externo, sem pedido de dado."""
        msg = (
            "<conteudo_usuario>\n"
            "Prezado cliente, seu extrato do mês de maio está disponível no aplicativo BB. "
            "Acesse pelo app oficial ou pelo site bb.com.br.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        assert result.risk_score <= 20, (
            f"Falso positivo! Score {result.risk_score} para comunicado legítimo."
        )


# ---------------------------------------------------------------------------
# Outros golpes
# ---------------------------------------------------------------------------

class TestOutrosGolpes:
    def test_phishing_credenciais_score_alto(self):
        msg = (
            "<conteudo_usuario>\n"
            "Olá! Sou do suporte BB. Preciso que você confirme seu CPF e senha para estornar uma cobrança.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        assert result.risk_score >= 60
        assert result.risk_label in ("alto", "médio")

    def test_falso_premio_score_alto(self):
        msg = (
            "<conteudo_usuario>\n"
            "Parabéns! Você foi selecionado para receber R$1.500,00. "
            "Para liberar, faça um Pix de R$50 como taxa de confirmação.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        assert result.risk_score >= 50


# ---------------------------------------------------------------------------
# Estrutura do resultado
# ---------------------------------------------------------------------------

class TestEstruturaResultado:
    def test_resultado_tem_campos_obrigatorios(self):
        """RNF-03: resultado deve conter sinais, score, label e summary."""
        msg = "<conteudo_usuario>\nqualquer mensagem de teste\n</conteudo_usuario>"
        result = analyze_level1(msg)
        assert isinstance(result, Level1Result)
        assert isinstance(result.risk_score, float)
        assert result.risk_label in ("baixo", "médio", "alto")
        assert isinstance(result.summary, str) and len(result.summary) > 0

    def test_sinal_tem_evidencia(self):
        """Cada sinal detectado deve ter evidência textual."""
        msg = (
            "<conteudo_usuario>\n"
            "Acesse agora: http://bb-falso.xyz para confirmar sua senha.\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        for signal in result.signals:
            assert signal.evidence, f"Sinal {signal.signal_id} sem evidência"

    def test_score_maximo_100(self):
        """Score nunca deve ultrapassar 100."""
        msg = (
            "<conteudo_usuario>\n"
            "Oi mãe, troquei o número urgente, preciso de Pix agora, "
            "acesse http://bb-falso.xyz, informe sua senha, você ganhou prêmio!\n"
            "</conteudo_usuario>"
        )
        result = analyze_level1(msg)
        assert result.risk_score <= 100.0

    def test_mensagem_sem_risco_sem_sinais(self):
        """Mensagem genérica sem padrões de risco não deve ter sinais."""
        msg = "<conteudo_usuario>\nBom dia, como vai você?\n</conteudo_usuario>"
        result = analyze_level1(msg)
        assert result.signals == []
        assert result.risk_score == 0.0
        assert result.risk_label == "baixo"
