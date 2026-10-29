"""
Motor financeiro determinístico do BB Decision.

RF-D-03..08, RN-05: ZERO uso de LLM. Todos os valores são calculados aqui.
Usa Decimal (não float) para valores monetários, conforme T-10.

PREMISSAS E FÓRMULAS DOCUMENTADAS
==================================

1. PARCELAMENTO (cenário_parcelamento)
   ─────────────────────────────────────
   Sistema: Price (parcelas fixas).
   Fórmula da parcela:
       PMT = PV × [i × (1+i)^n] / [(1+i)^n - 1]
   onde:
       PV = valor total da compra
       i  = taxa de juros mensal (decimal)
       n  = número de parcelas
   Premissa: taxa padrão = 1,99% a.m. (configurável via parâmetro).
   Taxa zero: parcela = PV / n.
   Arredondamento: ROUND_HALF_UP com 2 casas decimais.

2. PERDA DE RENDA (cenário_perda_renda)
   ─────────────────────────────────────
   Tempo de sustentação da reserva:
       meses_sustentados = reserva / despesas_mensais  (truncado)
   Deficit mensal (se renda parcial):
       deficit = despesas_mensais - renda_parcial
   Premissa: despesas são fixas no período de perda.

3. MUDANÇA DE EMPREGO (cenário_mudanca_emprego)
   ───────────────────────────────────────────────
   Impacto mensal = nova_renda - renda_atual
   Meses para equilibrar (se nova_renda < renda_atual):
       meses_para_equilibrar = abs(impacto_mensal) / reserva  (reserva > 0)
   Novo comprometimento de renda:
       comprometimento = despesas_mensais / nova_renda  (se nova_renda > 0)
   Premissa: despesas permanecem iguais no curto prazo.

4. COMPRA DE CASA (cenário_compra_casa)
   ─────────────────────────────────────
   Financiamento = valor_imovel - entrada
   Prestação mensal (Price):
       prestacao = PMT(financiamento, taxa_financiamento_mensal, prazo_meses)
   Comprometimento de renda = (despesas_atuais + prestacao) / renda_mensal
   Prazo padrão: 360 meses (30 anos).
   Taxa padrão financiamento: 0,72% a.m. (≈ 9% a.a., configurável).
   Comprometimento máximo recomendado pelo BC: 30%.
   Arredondamento: ROUND_HALF_UP com 2 casas decimais.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation


# ---------------------------------------------------------------------------
# Configurações paramétricas (podem ser sobrescritas nos cenários)
# ---------------------------------------------------------------------------

DEFAULT_INSTALLMENT_RATE_MONTHLY = Decimal("0.0199")   # 1,99% a.m.
DEFAULT_MORTGAGE_RATE_MONTHLY = Decimal("0.0072")      # 0,72% a.m. ≈ 9% a.a.
DEFAULT_MORTGAGE_TERM_MONTHS = 360                     # 30 anos
MAX_RECOMMENDED_INCOME_COMMITMENT = Decimal("0.30")    # 30% (norma BC)
TWO_PLACES = Decimal("0.01")


def _d(value: int | float | str | Decimal) -> Decimal:
    """Converte para Decimal com tratamento de erro."""
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Valor monetário inválido: {value!r}") from exc


def _round2(value: Decimal) -> Decimal:
    """Arredonda para 2 casas decimais com ROUND_HALF_UP."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _pmt(pv: Decimal, rate: Decimal, n: int) -> Decimal:
    """
    Calcula a parcela fixa pelo sistema Price.

    PMT = PV × [i × (1+i)^n] / [(1+i)^n - 1]

    Caso especial: taxa == 0 → PMT = PV / n
    Caso especial: n == 0 → raise ValueError
    """
    if n <= 0:
        raise ValueError("Número de parcelas deve ser maior que zero.")
    pv = _d(pv)
    if pv < Decimal("0"):
        raise ValueError("Valor presente (PV) não pode ser negativo.")
    if rate == Decimal("0"):
        return _round2(pv / _d(n))
    factor = (Decimal("1") + rate) ** n
    return _round2(pv * (rate * factor) / (factor - Decimal("1")))


# ---------------------------------------------------------------------------
# Estruturas de resultado
# ---------------------------------------------------------------------------

@dataclass
class ScenarioResult:
    """Resultado genérico de um cenário financeiro."""
    scenario_type: str
    current_path: dict          # situação atual
    alternative_path: dict      # situação com a decisão aplicada
    delta: dict                 # diferenças (alternativo - atual)
    warnings: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Cenário 1: Parcelamento
# RF-D-03
# ---------------------------------------------------------------------------

def scenario_installment(
    purchase_value: Decimal | float | str,
    installments: int,
    monthly_income: Decimal | float | str,
    monthly_expenses: Decimal | float | str,
    monthly_rate: Decimal | float | str | None = None,
) -> ScenarioResult:
    """
    Simula o impacto de parcelar uma compra no orçamento mensal e nas metas.

    Args:
        purchase_value: valor total da compra.
        installments: número de parcelas (1–72).
        monthly_income: renda mensal.
        monthly_expenses: despesas mensais atuais.
        monthly_rate: taxa de juros mensal (Decimal, ex: 0.0199 para 1,99%).
                      None usa DEFAULT_INSTALLMENT_RATE_MONTHLY.
    """
    pv = _d(purchase_value)
    n = int(installments)
    income = _d(monthly_income)
    expenses = _d(monthly_expenses)
    rate = _d(monthly_rate) if monthly_rate is not None else DEFAULT_INSTALLMENT_RATE_MONTHLY

    if n < 1 or n > 72:
        raise ValueError("Número de parcelas deve ser entre 1 e 72.")
    if pv < Decimal("0"):
        raise ValueError("Valor da compra não pode ser negativo.")
    if income < Decimal("0"):
        raise ValueError("Renda mensal não pode ser negativa.")

    pmt = _pmt(pv, rate, n)
    total_paid = _round2(pmt * _d(n))
    total_interest = _round2(total_paid - pv)
    new_expenses = _round2(expenses + pmt)
    current_surplus = _round2(income - expenses)
    new_surplus = _round2(income - new_expenses)
    current_commitment = _round2(expenses / income * 100) if income > 0 else Decimal("0")
    new_commitment = _round2(new_expenses / income * 100) if income > 0 else Decimal("100")

    warnings = []
    if new_surplus < Decimal("0"):
        warnings.append(
            f"A parcela de R$ {pmt} excede o saldo disponível após despesas. "
            f"Deficit mensal projetado: R$ {abs(new_surplus)}."
        )
    # Aviso de comprometimento: compara ANTES e DEPOIS
    if new_commitment > 70:
        if current_commitment > 70:
            warnings.append(
                f"Sua situação atual já está com comprometimento de renda em "
                f"{current_commitment}% (acima de 70%). Esta decisão adiciona "
                f"{(new_commitment - current_commitment):.1f} pontos percentuais, "
                f"chegando a {new_commitment}%. Avalie com cuidado."
            )
        else:
            warnings.append(
                f"Esta decisão eleva o comprometimento de renda de "
                f"{current_commitment}% para {new_commitment}% (acima de 70%). "
                "Risco de dificuldade para honrar compromissos."
            )

    return ScenarioResult(
        scenario_type="parcelamento",
        current_path={
            "despesas_mensais": float(expenses),
            "saldo_disponivel": float(current_surplus),
            "comprometimento_renda_pct": float(current_commitment),
        },
        alternative_path={
            "parcela_mensal": float(pmt),
            "total_pago": float(total_paid),
            "juros_totais": float(total_interest),
            "novas_despesas": float(new_expenses),
            "novo_saldo_disponivel": float(new_surplus),
            "novo_comprometimento_renda_pct": float(new_commitment),
            "taxa_mensal_pct": float(rate * 100),
            "num_parcelas": n,
        },
        delta={
            "variacao_saldo": float(new_surplus - current_surplus),
            "variacao_comprometimento_pct": float(new_commitment - current_commitment),
        },
        warnings=warnings,
        assumptions=[
            f"Sistema Price (parcelas fixas).",
            f"Taxa de juros: {float(rate * 100):.2f}% a.m.",
            f"Arredondamento: ROUND_HALF_UP, 2 casas decimais.",
        ],
    )


# ---------------------------------------------------------------------------
# Cenário 2: Perda de Renda
# RF-D-04
# ---------------------------------------------------------------------------

def scenario_income_loss(
    monthly_income: Decimal | float | str,
    monthly_expenses: Decimal | float | str,
    emergency_reserve: Decimal | float | str,
    loss_months: int,
    partial_income: Decimal | float | str | None = None,
) -> ScenarioResult:
    """
    Simula o impacto de perder a renda por N meses.

    Args:
        monthly_income: renda mensal atual.
        monthly_expenses: despesas mensais.
        emergency_reserve: reserva de emergência atual.
        loss_months: meses de perda de renda.
        partial_income: renda parcial durante o período (0 se total).
    """
    income = _d(monthly_income)
    expenses = _d(monthly_expenses)
    reserve = _d(emergency_reserve)
    n_months = int(loss_months)
    p_income = _d(partial_income) if partial_income is not None else Decimal("0")

    if n_months < 1:
        raise ValueError("O número de meses deve ser pelo menos 1.")
    if reserve < Decimal("0"):
        raise ValueError("Reserva de emergência não pode ser negativa.")
    if expenses < Decimal("0"):
        raise ValueError("Despesas mensais não podem ser negativas.")

    monthly_deficit = _round2(expenses - p_income)
    months_reserve_sustains = (
        int(reserve / expenses) if expenses > 0 else 9999
    )
    total_loss = _round2(monthly_deficit * _d(n_months))
    reserve_after = _round2(reserve - total_loss)
    reserve_depleted = reserve_after < Decimal("0")
    months_until_depleted = (
        int(reserve / monthly_deficit)
        if monthly_deficit > 0 and reserve > 0
        else (9999 if monthly_deficit <= 0 else 0)
    )

    current_surplus = _round2(income - expenses)

    warnings = []
    if reserve_depleted:
        shortage = _round2(abs(reserve_after))
        warnings.append(
            f"A reserva não cobre os {n_months} meses de perda. "
            f"Deficit total após esgotar reserva: R$ {shortage}."
        )
    if months_reserve_sustains < 3:
        warnings.append(
            f"Reserva cobre apenas {months_reserve_sustains} mês(es) de despesas. "
            "Recomendado: mínimo 3–6 meses."
        )

    return ScenarioResult(
        scenario_type="perda_renda",
        current_path={
            "renda_mensal": float(income),
            "despesas_mensais": float(expenses),
            "reserva_emergencia": float(reserve),
            "saldo_disponivel": float(current_surplus),
            "meses_reserva_cobre": months_reserve_sustains,
        },
        alternative_path={
            "renda_parcial": float(p_income),
            "deficit_mensal": float(monthly_deficit),
            "meses_perda": n_months,
            "total_comprometido_da_reserva": float(min(total_loss, reserve)),
            "reserva_restante": float(max(reserve_after, Decimal("0"))),
            "reserva_insuficiente": reserve_depleted,
            "meses_ate_esgotar_reserva": min(months_until_depleted, n_months),
        },
        delta={
            "impacto_total_na_reserva": float(_round2(-min(total_loss, reserve))),
            "variacao_saldo_mensal": float(_round2(p_income - income)),
        },
        warnings=warnings,
        assumptions=[
            "Despesas mensais permanecem fixas durante o período.",
            "Reserva usada na ordem FIFO (primeiro a entrar, primeiro a sair).",
            "Renda parcial padrão: R$ 0 (perda total), parametrizável.",
        ],
    )


# ---------------------------------------------------------------------------
# Cenário 3: Mudança de Emprego
# RF-D-05
# ---------------------------------------------------------------------------

def scenario_job_change(
    current_income: Decimal | float | str,
    new_income: Decimal | float | str,
    monthly_expenses: Decimal | float | str,
    emergency_reserve: Decimal | float | str,
) -> ScenarioResult:
    """
    Simula o efeito de mudança de emprego (renda e benefícios).

    Args:
        current_income: renda mensal atual.
        new_income: nova renda mensal esperada.
        monthly_expenses: despesas mensais.
        emergency_reserve: reserva de emergência atual.
    """
    inc_atual = _d(current_income)
    inc_nova = _d(new_income)
    expenses = _d(monthly_expenses)
    reserve = _d(emergency_reserve)

    if inc_atual < Decimal("0") or inc_nova < Decimal("0"):
        raise ValueError("Rendas não podem ser negativas.")
    if expenses < Decimal("0"):
        raise ValueError("Despesas não podem ser negativas.")

    impacto_mensal = _round2(inc_nova - inc_atual)
    saldo_atual = _round2(inc_atual - expenses)
    novo_saldo = _round2(inc_nova - expenses)
    comprometimento_atual = (
        _round2(expenses / inc_atual * 100) if inc_atual > 0 else Decimal("100")
    )
    novo_comprometimento = (
        _round2(expenses / inc_nova * 100) if inc_nova > 0 else Decimal("100")
    )

    # Meses para equilibrar com a reserva (se nova renda < atual)
    meses_equilibrar = 0
    if impacto_mensal < 0 and reserve > 0:
        meses_equilibrar = int(reserve / abs(impacto_mensal))

    warnings = []
    if novo_saldo < Decimal("0"):
        warnings.append(
            f"Com a nova renda (R$ {inc_nova}), as despesas (R$ {expenses}) "
            f"superam a renda. Deficit mensal: R$ {abs(novo_saldo)}."
        )
    if novo_comprometimento > Decimal("50"):
        warnings.append(
            f"Comprometimento de renda ({novo_comprometimento}%) acima de 50% "
            "com a nova renda."
        )

    return ScenarioResult(
        scenario_type="mudanca_emprego",
        current_path={
            "renda_mensal": float(inc_atual),
            "despesas_mensais": float(expenses),
            "saldo_disponivel": float(saldo_atual),
            "comprometimento_renda_pct": float(comprometimento_atual),
            "reserva_emergencia": float(reserve),
        },
        alternative_path={
            "nova_renda_mensal": float(inc_nova),
            "novo_saldo_disponivel": float(novo_saldo),
            "novo_comprometimento_renda_pct": float(novo_comprometimento),
            "meses_reserva_suporta_transicao": meses_equilibrar,
        },
        delta={
            "variacao_renda_mensal": float(impacto_mensal),
            "variacao_saldo": float(novo_saldo - saldo_atual),
            "variacao_comprometimento_pct": float(novo_comprometimento - comprometimento_atual),
        },
        warnings=warnings,
        assumptions=[
            "Despesas permanecem iguais no curto prazo.",
            "Benefícios (plano de saúde, vale-refeição) não modelados neste protótipo.",
            "Meses de transição calculados com base na reserva de emergência.",
        ],
    )


# ---------------------------------------------------------------------------
# Cenário 4: Compra de Casa
# RF-D-06
# ---------------------------------------------------------------------------

def scenario_home_purchase(
    property_value: Decimal | float | str,
    down_payment: Decimal | float | str,
    monthly_income: Decimal | float | str,
    monthly_expenses: Decimal | float | str,
    emergency_reserve: Decimal | float | str,
    mortgage_term_months: int | None = None,
    mortgage_rate_monthly: Decimal | float | str | None = None,
) -> ScenarioResult:
    """
    Simula o impacto de comprar uma casa (financiamento + comprometimento de renda).

    Args:
        property_value: valor do imóvel.
        down_payment: valor da entrada.
        monthly_income: renda mensal.
        monthly_expenses: despesas mensais atuais.
        emergency_reserve: reserva de emergência.
        mortgage_term_months: prazo do financiamento em meses (padrão 360).
        mortgage_rate_monthly: taxa mensal (padrão 0,72%).
    """
    valor = _d(property_value)
    entrada = _d(down_payment)
    income = _d(monthly_income)
    expenses = _d(monthly_expenses)
    reserve = _d(emergency_reserve)
    prazo = int(mortgage_term_months) if mortgage_term_months else DEFAULT_MORTGAGE_TERM_MONTHS
    taxa = _d(mortgage_rate_monthly) if mortgage_rate_monthly else DEFAULT_MORTGAGE_RATE_MONTHLY

    if entrada > valor:
        raise ValueError("Entrada não pode ser maior que o valor do imóvel.")
    if entrada < Decimal("0"):
        raise ValueError("Entrada não pode ser negativa.")
    if valor <= Decimal("0"):
        raise ValueError("Valor do imóvel deve ser positivo.")

    financiamento = _round2(valor - entrada)
    prestacao = _pmt(financiamento, taxa, prazo) if financiamento > 0 else Decimal("0")
    novas_despesas = _round2(expenses + prestacao)
    saldo_atual = _round2(income - expenses)
    novo_saldo = _round2(income - novas_despesas)
    comprometimento_atual = (
        _round2(expenses / income * 100) if income > 0 else Decimal("0")
    )
    novo_comprometimento = (
        _round2(novas_despesas / income * 100) if income > 0 else Decimal("100")
    )
    # Reserva usada para entrada
    reserva_apos_entrada = _round2(reserve - entrada)
    total_pago_financiamento = _round2(prestacao * _d(prazo))
    custo_total_imovel = _round2(total_pago_financiamento + entrada)

    warnings = []
    if novo_comprometimento > MAX_RECOMMENDED_INCOME_COMMITMENT * 100:
        warnings.append(
            f"Comprometimento de renda ({novo_comprometimento}%) ultrapassa 30% "
            "recomendado pelo Banco Central."
        )
    if novo_saldo < Decimal("0"):
        warnings.append(
            f"A prestação (R$ {prestacao}) excede o saldo disponível após despesas. "
            f"Deficit mensal projetado: R$ {abs(novo_saldo)}."
        )
    if reserva_apos_entrada < Decimal("0"):
        warnings.append(
            "A entrada supera a reserva de emergência disponível. "
            "Considere um valor de entrada menor ou ampliar a reserva antes."
        )

    return ScenarioResult(
        scenario_type="compra_casa",
        current_path={
            "renda_mensal": float(income),
            "despesas_mensais": float(expenses),
            "saldo_disponivel": float(saldo_atual),
            "comprometimento_renda_pct": float(comprometimento_atual),
            "reserva_emergencia": float(reserve),
        },
        alternative_path={
            "valor_imovel": float(valor),
            "entrada": float(entrada),
            "financiamento": float(financiamento),
            "prestacao_mensal": float(prestacao),
            "prazo_meses": prazo,
            "taxa_mensal_pct": float(taxa * 100),
            "total_pago_financiamento": float(total_pago_financiamento),
            "custo_total_imovel": float(custo_total_imovel),
            "novas_despesas": float(novas_despesas),
            "novo_saldo_disponivel": float(novo_saldo),
            "novo_comprometimento_renda_pct": float(novo_comprometimento),
            "reserva_apos_entrada": float(max(reserva_apos_entrada, Decimal("0"))),
        },
        delta={
            "variacao_saldo": float(novo_saldo - saldo_atual),
            "variacao_comprometimento_pct": float(novo_comprometimento - comprometimento_atual),
            "reserva_comprometida_para_entrada": float(min(entrada, reserve)),
        },
        warnings=warnings,
        assumptions=[
            f"Sistema Price (prestações fixas).",
            f"Taxa de financiamento: {float(taxa * 100):.2f}% a.m. ({float(taxa * 100 * 12):.2f}% a.a.).",
            f"Prazo: {prazo} meses ({prazo // 12} anos).",
            "Comprometimento máximo recomendado pelo Banco Central: 30%.",
            "Custos de cartório, ITBI e reformas não incluídos neste protótipo.",
        ],
    )
