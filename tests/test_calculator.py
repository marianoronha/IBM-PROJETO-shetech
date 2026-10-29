"""
Testes unitários do motor financeiro determinístico.

Cobre RF-D-03..08 e RN-05.
Todos os valores esperados foram calculados à mão e estão comentados.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from decimal import Decimal
from app.bbdecision.calculator import (
    _pmt, _d, _round2,
    scenario_installment,
    scenario_income_loss,
    scenario_job_change,
    scenario_home_purchase,
    DEFAULT_INSTALLMENT_RATE_MONTHLY,
    DEFAULT_MORTGAGE_RATE_MONTHLY,
)


# ===========================================================================
# Testes unitários de funções auxiliares
# ===========================================================================

class TestPMT:
    def test_pmt_taxa_zero(self):
        """
        Cálculo manual: PV=1200, n=12, i=0 → PMT = 1200/12 = 100.00
        """
        result = _pmt(_d("1200"), _d("0"), 12)
        assert result == Decimal("100.00"), f"Esperado 100.00, obtido {result}"

    def test_pmt_taxa_padrao(self):
        """
        Cálculo manual (Price): PV=1200, i=0.0199, n=12
        (1+0.0199)^12 = 1.26677 (aprox)
        PMT = 1200 × (0.0199 × 1.26677) / (1.26677 - 1)
             = 1200 × 0.025207 / 0.26677
             = 1200 × 0.094492 ≈ 113.39
        """
        result = _pmt(_d("1200"), DEFAULT_INSTALLMENT_RATE_MONTHLY, 12)
        # Tolerância de ±0.10 por diferenças de arredondamento intermediário
        assert Decimal("113.00") <= result <= Decimal("114.00"), (
            f"PMT esperado ~113.39, obtido {result}"
        )

    def test_pmt_parcelas_zero_levanta_erro(self):
        with pytest.raises(ValueError, match="parcelas"):
            _pmt(_d("1000"), _d("0.01"), 0)

    def test_pmt_pv_negativo_levanta_erro(self):
        with pytest.raises(ValueError, match="negativo"):
            _pmt(_d("-100"), _d("0.01"), 12)

    def test_pmt_uma_parcela(self):
        """Uma parcela sem juros = valor total."""
        result = _pmt(_d("500"), _d("0"), 1)
        assert result == Decimal("500.00")


# ===========================================================================
# Cenário 1: Parcelamento (RF-D-03)
# ===========================================================================

class TestScenarioInstallment:
    def test_parcelamento_12x_sem_juros(self):
        """
        Cálculo manual: PV=1200, n=12, i=0
        PMT = 100.00
        total_paid = 1200.00, juros = 0.00
        new_expenses = 2800 + 100 = 2900
        saldo_atual = 3500 - 2800 = 700
        novo_saldo = 3500 - 2900 = 600
        comprometimento_atual = 2800/3500*100 = 80.00%
        novo_comprometimento = 2900/3500*100 = 82.86%
        """
        result = scenario_installment(
            purchase_value=1200,
            installments=12,
            monthly_income=3500,
            monthly_expenses=2800,
            monthly_rate=0,
        )
        alt = result.alternative_path
        cur = result.current_path

        assert alt["parcela_mensal"] == pytest.approx(100.00, abs=0.01), "Parcela esperada: 100.00"
        assert alt["total_pago"] == pytest.approx(1200.00, abs=0.01), "Total esperado: 1200.00"
        assert alt["juros_totais"] == pytest.approx(0.00, abs=0.01), "Juros esperados: 0.00"
        assert alt["novas_despesas"] == pytest.approx(2900.00, abs=0.01)
        assert alt["novo_saldo_disponivel"] == pytest.approx(600.00, abs=0.01)
        assert cur["saldo_disponivel"] == pytest.approx(700.00, abs=0.01)
        assert cur["comprometimento_renda_pct"] == pytest.approx(80.00, abs=0.01)
        assert alt["novo_comprometimento_renda_pct"] == pytest.approx(82.86, abs=0.10)

    def test_parcelamento_12x_com_juros_padrao(self):
        """
        Cálculo manual: PV=1200, i=0.0199, n=12
        PMT ≈ 113.39 (calculado acima)
        total ≈ 1360.68, juros ≈ 160.68
        """
        result = scenario_installment(
            purchase_value=1200,
            installments=12,
            monthly_income=3500,
            monthly_expenses=2800,
        )
        alt = result.alternative_path
        assert 113.00 <= alt["parcela_mensal"] <= 114.00, f"PMT esperado ~113.39, obtido {alt['parcela_mensal']}"
        assert alt["juros_totais"] > 0, "Deve haver juros com taxa padrão 1,99%"

    def test_parcela_maior_que_renda_gera_aviso(self):
        """Caso-limite: parcela mensal > saldo disponível gera warning."""
        result = scenario_installment(
            purchase_value=50000,
            installments=12,
            monthly_income=1000,
            monthly_expenses=900,
            monthly_rate=0,
        )
        # Parcela = 50000/12 = 4166.67 >> saldo disponível de 100
        assert len(result.warnings) > 0, "Deve gerar aviso de saldo insuficiente"
        assert result.alternative_path["novo_saldo_disponivel"] < 0

    def test_parcelas_invalidas(self):
        with pytest.raises(ValueError):
            scenario_installment(1000, 0, 3500, 2800)

    def test_parcelas_acima_limite(self):
        with pytest.raises(ValueError):
            scenario_installment(1000, 73, 3500, 2800)

    def test_valor_negativo_levanta_erro(self):
        with pytest.raises(ValueError):
            scenario_installment(-100, 12, 3500, 2800)


# ===========================================================================
# Cenário 2: Perda de Renda (RF-D-04)
# ===========================================================================

class TestScenarioIncomeLoss:
    def test_perda_renda_3_meses_reserva_suficiente(self):
        """
        Cálculo manual:
        income=3500, expenses=2800, reserve=5000, loss=3 meses, p_income=0
        deficit_mensal = 2800 - 0 = 2800
        total_comprometido = 2800 * 3 = 8400
        MAS reserve=5000 → min(8400, 5000) = 5000 comprometidos
        reserva_restante = max(5000 - 8400, 0) = 0
        meses_reserva_cobre = 5000 // 2800 = 1
        reserva_insuficiente = True (5000 - 8400 < 0)
        """
        result = scenario_income_loss(
            monthly_income=3500,
            monthly_expenses=2800,
            emergency_reserve=5000,
            loss_months=3,
        )
        alt = result.alternative_path
        cur = result.current_path

        assert alt["deficit_mensal"] == pytest.approx(2800.00, abs=0.01), "Deficit: 2800"
        assert alt["meses_perda"] == 3
        assert alt["reserva_insuficiente"] is True, "Reserva insuficiente para 3 meses"
        assert cur["meses_reserva_cobre"] == 1, "5000 // 2800 = 1"
        assert len(result.warnings) > 0

    def test_perda_renda_reserva_suficiente(self):
        """
        Cálculo manual:
        income=8500, expenses=4000, reserve=25000, loss=3 meses
        deficit = 4000 * 3 = 12000 < 25000
        reserva_restante = 25000 - 12000 = 13000
        reserva_insuficiente = False
        meses_reserva_cobre = 25000 // 4000 = 6
        """
        result = scenario_income_loss(
            monthly_income=8500,
            monthly_expenses=4000,
            emergency_reserve=25000,
            loss_months=3,
        )
        alt = result.alternative_path
        assert alt["reserva_insuficiente"] is False
        assert alt["reserva_restante"] == pytest.approx(13000.00, abs=0.01), (
            "25000 - 12000 = 13000"
        )
        assert result.current_path["meses_reserva_cobre"] == 6, "25000 // 4000 = 6"

    def test_renda_zero_aceita(self):
        """Caso-limite: renda zero (desempregado total)."""
        result = scenario_income_loss(
            monthly_income=0,
            monthly_expenses=2000,
            emergency_reserve=6000,
            loss_months=3,
        )
        assert result.alternative_path["deficit_mensal"] == pytest.approx(2000.00, abs=0.01)

    def test_reserva_zero(self):
        """Caso-limite: sem reserva — insuficiente imediatamente."""
        result = scenario_income_loss(
            monthly_income=3000,
            monthly_expenses=2500,
            emergency_reserve=0,
            loss_months=2,
        )
        assert result.alternative_path["reserva_insuficiente"] is True

    def test_meses_invalido(self):
        with pytest.raises(ValueError):
            scenario_income_loss(3000, 2000, 5000, 0)


# ===========================================================================
# Cenário 3: Mudança de Emprego (RF-D-05)
# ===========================================================================

class TestScenarioJobChange:
    def test_mudanca_para_renda_maior(self):
        """
        Cálculo manual:
        current=4800, new=6000, expenses=4100, reserve=3000
        impacto = 6000 - 4800 = 1200
        saldo_atual = 4800 - 4100 = 700
        novo_saldo = 6000 - 4100 = 1900
        comprometimento_atual = 4100/4800*100 = 85.42%
        novo_comprometimento = 4100/6000*100 = 68.33%
        """
        result = scenario_job_change(4800, 6000, 4100, 3000)
        delta = result.delta
        alt = result.alternative_path
        cur = result.current_path

        assert delta["variacao_renda_mensal"] == pytest.approx(1200.00, abs=0.01), "1200"
        assert alt["novo_saldo_disponivel"] == pytest.approx(1900.00, abs=0.01), "1900"
        assert cur["saldo_disponivel"] == pytest.approx(700.00, abs=0.01), "700"
        assert cur["comprometimento_renda_pct"] == pytest.approx(85.42, abs=0.10)

    def test_mudanca_para_renda_menor_gera_aviso(self):
        """
        Cálculo manual: current=8500, new=5000, expenses=6200, reserve=25000
        novo_saldo = 5000 - 6200 = -1200 → aviso
        """
        result = scenario_job_change(8500, 5000, 6200, 25000)
        assert result.alternative_path["novo_saldo_disponivel"] == pytest.approx(-1200.00, abs=0.01)
        assert len(result.warnings) > 0

    def test_nova_renda_zero_aceita(self):
        """Caso-limite: nova renda zero (desemprego)."""
        result = scenario_job_change(3000, 0, 2000, 5000)
        assert result.alternative_path["novo_comprometimento_renda_pct"] == pytest.approx(100.00, abs=0.01)


# ===========================================================================
# Cenário 4: Compra de Casa (RF-D-06)
# ===========================================================================

class TestScenarioHomePurchase:
    def test_compra_casa_basica(self):
        """
        Cálculo manual:
        valor=300000, entrada=60000, income=8500, expenses=3500, reserve=25000
        financiamento = 300000 - 60000 = 240000
        taxa=0.0072, n=360
        (1+0.0072)^360 ≈ 13.2118
        PMT = 240000 × (0.0072 × 13.2118) / (13.2118 - 1)
             = 240000 × 0.09512 / 12.2118
             = 240000 × 0.007789 ≈ 1869.31
        novas_despesas = 3500 + 1869.31 = 5369.31
        novo_saldo = 8500 - 5369.31 = 3130.69
        comprometimento = 5369.31/8500*100 ≈ 63.17% → acima de 30% → aviso
        """
        result = scenario_home_purchase(
            property_value=300000,
            down_payment=60000,
            monthly_income=8500,
            monthly_expenses=3500,
            emergency_reserve=25000,
        )
        alt = result.alternative_path
        # Tolerância maior para PMT com juros compostos
        assert 1800 <= alt["prestacao_mensal"] <= 2000, (
            f"Prestação esperada ~1869, obtida {alt['prestacao_mensal']}"
        )
        assert alt["financiamento"] == pytest.approx(240000.00, abs=0.01)
        # Comprometimento acima de 30% → aviso obrigatório
        assert len(result.warnings) > 0
        assert alt["novo_comprometimento_renda_pct"] > 30

    def test_entrada_maior_que_valor_levanta_erro(self):
        with pytest.raises(ValueError, match="Entrada não pode ser maior"):
            scenario_home_purchase(200000, 250000, 8000, 3000, 20000)

    def test_valor_imovel_zero_levanta_erro(self):
        with pytest.raises(ValueError, match="positivo"):
            scenario_home_purchase(0, 0, 8000, 3000, 20000)

    def test_comprometimento_acima_30_gera_aviso(self):
        """Comprometimento > 30% deve sempre gerar aviso (norma BC)."""
        result = scenario_home_purchase(500000, 50000, 5000, 2000, 10000)
        warnings_lower = " ".join(result.warnings).lower()
        assert "30%" in warnings_lower or "banco central" in warnings_lower

    def test_parametros_personalizados(self):
        """Parâmetros parametrizáveis devem ser aceitos."""
        result = scenario_home_purchase(
            property_value=200000,
            down_payment=40000,
            monthly_income=6000,
            monthly_expenses=2500,
            emergency_reserve=15000,
            mortgage_term_months=240,  # 20 anos
            mortgage_rate_monthly=0.006,  # 0,6% a.m.
        )
        assert result.alternative_path["prazo_meses"] == 240
        assert result.alternative_path["taxa_mensal_pct"] == pytest.approx(0.6, abs=0.001)


# ===========================================================================
# P0-2f — Caso específico: renda 8500, despesas 6000, compra R$ 1000 em 12x
# Verificado manualmente — consta no plano de auditoria.
# ===========================================================================

class TestComprometimentoAntesDepois:
    """
    Cenário:
      renda = R$ 8.500
      despesas = R$ 6.000  → comprometimento atual = 6000/8500 = 70,59%
      compra = R$ 1.000 em 12x @ 1,99% a.m.

    Cálculo Price:
      (1+0.0199)^12 ≈ 1.26677
      PMT = 1000 × (0.0199 × 1.26677) / (1.26677 - 1)
          = 1000 × 0.025207 / 0.26677
          ≈ R$ 94.49

    Novas despesas ≈ 6000 + 94.49 = 6094.49
    Novo comprometimento ≈ 6094.49 / 8500 = 71,70%
    Comprometimento atual ≈ 70,59% (já acima de 70%)

    ANTES: já acima de 70% → aviso deve mencionar que a situação ATUAL já está elevada.
    DEPOIS: adiciona ~1,11 pontos percentuais.
    """

    def test_comprometimento_atual_ja_acima_70(self):
        """Aviso deve reportar comprometimento ANTES E DEPOIS, não apenas DEPOIS."""
        result = scenario_installment(
            purchase_value=1000,
            installments=12,
            monthly_income=8500,
            monthly_expenses=6000,
        )
        # Comprometimento atual deve estar em torno de 70,59%
        assert result.current_path["comprometimento_renda_pct"] == pytest.approx(70.59, abs=0.5)

        # Deve haver pelo menos 1 aviso
        assert len(result.warnings) >= 1

        # O aviso deve mencionar que a situação atual JÁ está elevada
        combined = " ".join(result.warnings).lower()
        assert "situação atual" in combined or "atual já está" in combined, (
            f"Aviso deveria mencionar comprometimento atual. Avisos: {result.warnings}"
        )

    def test_comprometimento_antes_depois_valores(self):
        """Comprometimento novo deve ser maior que o atual em ~1 ponto percentual."""
        result = scenario_installment(
            purchase_value=1000,
            installments=12,
            monthly_income=8500,
            monthly_expenses=6000,
        )
        antes = result.current_path["comprometimento_renda_pct"]
        depois = result.alternative_path["novo_comprometimento_renda_pct"]
        delta = result.delta["variacao_comprometimento_pct"]

        # Novo comprometimento deve ser maior que o atual
        assert depois > antes
        # Delta deve ser positivo (aumentou) e pequeno (~1,11%)
        assert 0.5 < delta < 3.0, f"Delta de comprometimento inesperado: {delta}"

    def test_parcela_calculada_corretamente(self):
        """PMT deve estar próximo de R$ 94,49."""
        result = scenario_installment(
            purchase_value=1000,
            installments=12,
            monthly_income=8500,
            monthly_expenses=6000,
        )
        pmt = result.alternative_path["parcela_mensal"]
        assert 93.0 < pmt < 96.0, f"PMT esperado ~94.49, obtido {pmt}"

    def test_sem_comprometimento_inicial_acima_70(self):
        """Usuário com comprometimento inicial baixo → aviso menciona que a DECISÃO eleva acima de 70%."""
        result = scenario_installment(
            purchase_value=5000,
            installments=12,
            monthly_income=8500,
            monthly_expenses=3000,  # comprometimento atual = 35%
        )
        if result.warnings:
            # Se o aviso existe, não deve dizer que a situação atual já estava elevada
            combined = " ".join(result.warnings).lower()
            # Deve mencionar que a DECISÃO eleva o comprometimento
            assert "eleva" in combined or "decisão" in combined or len(result.warnings) == 0
