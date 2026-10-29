"""
Schemas Pydantic para os parâmetros dos cenários do BB Decision.

O intent_parser extrai estes schemas a partir da pergunta do usuário (LLM).
O calculator usa estes schemas como entrada (deterministico).
Toda validação é aplicada ANTES de qualquer cálculo.
"""

from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


ScenarioType = Literal[
    "parcelamento",
    "perda_renda",
    "mudanca_emprego",
    "compra_casa",
    "ambiguous",
]


class InstallmentParams(BaseModel):
    """Parâmetros para o cenário de parcelamento."""
    purchase_value: float = Field(..., gt=0, description="Valor total da compra (R$).")
    installments: int = Field(..., ge=1, le=72, description="Número de parcelas (1–72).")
    monthly_income: float = Field(..., gt=0, description="Renda mensal do usuário (R$).")
    monthly_expenses: float = Field(..., gt=0, description="Despesas mensais atuais (R$).")
    monthly_rate: Optional[float] = Field(
        default=None,
        ge=0,
        le=0.30,
        description="Taxa de juros mensal (decimal, ex: 0.0199 para 1,99%). "
                    "Padrão: 1,99% a.m.",
    )


class IncomeLossParams(BaseModel):
    """Parâmetros para o cenário de perda de renda."""
    monthly_income: float = Field(..., ge=0, description="Renda mensal atual (R$).")
    monthly_expenses: float = Field(..., gt=0, description="Despesas mensais (R$).")
    emergency_reserve: float = Field(..., ge=0, description="Reserva de emergência atual (R$).")
    loss_months: int = Field(..., ge=1, le=60, description="Meses de perda de renda.")
    partial_income: Optional[float] = Field(
        default=0.0,
        ge=0,
        description="Renda parcial durante o período (R$, padrão 0).",
    )


class JobChangeParams(BaseModel):
    """Parâmetros para o cenário de mudança de emprego."""
    current_income: float = Field(..., gt=0, description="Renda mensal atual (R$).")
    new_income: float = Field(..., ge=0, description="Nova renda mensal esperada (R$).")
    monthly_expenses: float = Field(..., gt=0, description="Despesas mensais (R$).")
    emergency_reserve: float = Field(..., ge=0, description="Reserva de emergência (R$).")


class HomePurchaseParams(BaseModel):
    """Parâmetros para o cenário de compra de casa."""
    property_value: float = Field(..., gt=0, description="Valor do imóvel (R$).")
    down_payment: float = Field(..., ge=0, description="Valor da entrada (R$).")
    monthly_income: float = Field(..., gt=0, description="Renda mensal (R$).")
    monthly_expenses: float = Field(..., gt=0, description="Despesas mensais (R$).")
    emergency_reserve: float = Field(..., ge=0, description="Reserva de emergência (R$).")
    mortgage_term_months: Optional[int] = Field(
        default=360,
        ge=12,
        le=420,
        description="Prazo do financiamento em meses (padrão 360 = 30 anos).",
    )
    mortgage_rate_monthly: Optional[float] = Field(
        default=None,
        ge=0,
        le=0.05,
        description="Taxa mensal do financiamento (padrão 0,72% a.m.).",
    )

    @model_validator(mode="after")
    def down_payment_le_property(self) -> "HomePurchaseParams":
        if self.down_payment > self.property_value:
            raise ValueError("Entrada não pode ser maior que o valor do imóvel.")
        return self


class IntentResult(BaseModel):
    """Resultado do intent parser: tipo de cenário + parâmetros extraídos."""
    scenario_type: ScenarioType
    params: Optional[
        InstallmentParams | IncomeLossParams | JobChangeParams | HomePurchaseParams
    ] = None
    missing_fields: list[str] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    raw_question: str = ""
