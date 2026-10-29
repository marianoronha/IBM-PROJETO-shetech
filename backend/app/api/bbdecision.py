"""
API REST do BB Decision.

RF-D-01..11: simula decisões financeiras em linguagem natural.
RF-D-10, RN-06: aviso obrigatório em TODA resposta.
RC-02: consentimento do cliente.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.bbdecision.intent_parser import parse_intent
from app.bbdecision.calculator import (
    scenario_installment,
    scenario_income_loss,
    scenario_job_change,
    scenario_home_purchase,
    ScenarioResult,
)
from app.bbdecision.narrator import narrate, DISCLAIMER
from app.bbdecision.scenarios import (
    IntentResult,
    InstallmentParams,
    IncomeLossParams,
    JobChangeParams,
    HomePurchaseParams,
)
from app.guardiao.prompt_guard import InputValidationError

router = APIRouter()

# Aviso obrigatório consolidado — RF-D-10, RN-06
# Exibido UMA VEZ no topo da resposta (campo 'disclaimer').
# O narrator NÃO adiciona disclaimer próprio — evitar duplicação.
MANDATORY_DISCLAIMER = (
    "Estimativa educacional. Não constitui garantia de resultado "
    "nem recomendação de investimento ou crédito."
)


# ---------------------------------------------------------------------------
# Schemas de entrada e saída
# ---------------------------------------------------------------------------

class BBDecisionRequest(BaseModel):
    """Requisição de simulação do BB Decision."""

    question: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Pergunta em linguagem natural, ex: 'E se eu parcelar em 12x?'",
        examples=["E se eu parcelar essa compra de R$ 1200 em 12 vezes?"],
    )
    user_id: str = Field(
        default="",
        max_length=20,
        pattern=r"^[A-Za-z0-9_-]*$",
        description="ID sintético do usuário (opcional). Habilita uso do perfil financeiro.",
    )
    language_profile: str = Field(
        default="standard",
        pattern=r"^(standard|low)$",
        description="Perfil de linguagem: 'standard' ou 'low'.",
    )
    simulation_consent: bool = Field(
        default=True,
        description="RC-02: consentimento do cliente para uso do perfil na simulação.",
    )

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("A pergunta não pode ser vazia.")
        return v


class PathSummary(BaseModel):
    """Resumo de um caminho (atual ou alternativo)."""
    label: str
    data: dict


class BBDecisionResponse(BaseModel):
    """Resposta da simulação do BB Decision."""

    # Cenário
    scenario_type: str
    question_understood: str

    # Resultados
    current_path: PathSummary
    alternative_path: PathSummary
    delta: dict
    warnings: list[str]
    assumptions: list[str]

    # Narrativa (LLM apenas narra)
    narrative: str

    # Aviso obrigatório — NUNCA omitir (RF-D-10, RN-06)
    disclaimer: str = MANDATORY_DISCLAIMER

    # Esclarecimento necessário
    clarification_needed: bool = False
    clarification_question: Optional[str] = None


class ClarificationResponse(BaseModel):
    """Retornado quando parâmetros estão faltando."""
    clarification_needed: bool = True
    scenario_type: str
    clarification_question: str
    missing_fields: list[str]
    disclaimer: str = MANDATORY_DISCLAIMER


class ErrorResponse(BaseModel):
    error: str
    code: str


# ---------------------------------------------------------------------------
# Função auxiliar: executa o calculador com base nos parâmetros extraídos
# ---------------------------------------------------------------------------

def _run_calculator(intent: IntentResult) -> ScenarioResult:
    """Despacha para o calculador correto com base no scenario_type."""
    p = intent.params
    st = intent.scenario_type

    if st == "parcelamento" and isinstance(p, InstallmentParams):
        return scenario_installment(
            purchase_value=p.purchase_value,
            installments=p.installments,
            monthly_income=p.monthly_income,
            monthly_expenses=p.monthly_expenses,
            monthly_rate=p.monthly_rate,
        )
    if st == "perda_renda" and isinstance(p, IncomeLossParams):
        return scenario_income_loss(
            monthly_income=p.monthly_income,
            monthly_expenses=p.monthly_expenses,
            emergency_reserve=p.emergency_reserve,
            loss_months=p.loss_months,
            partial_income=p.partial_income,
        )
    if st == "mudanca_emprego" and isinstance(p, JobChangeParams):
        return scenario_job_change(
            current_income=p.current_income,
            new_income=p.new_income,
            monthly_expenses=p.monthly_expenses,
            emergency_reserve=p.emergency_reserve,
        )
    if st == "compra_casa" and isinstance(p, HomePurchaseParams):
        return scenario_home_purchase(
            property_value=p.property_value,
            down_payment=p.down_payment,
            monthly_income=p.monthly_income,
            monthly_expenses=p.monthly_expenses,
            emergency_reserve=p.emergency_reserve,
            mortgage_term_months=p.mortgage_term_months,
            mortgage_rate_monthly=p.mortgage_rate_monthly,
        )
    raise ValueError(f"Cenário não suportado: {st}")


# ---------------------------------------------------------------------------
# Endpoint principal
# ---------------------------------------------------------------------------

@router.post(
    "/simulate",
    response_model=BBDecisionResponse,
    responses={
        200: {"description": "Simulação concluída"},
        202: {"model": ClarificationResponse, "description": "Esclarecimento necessário"},
        400: {"model": ErrorResponse, "description": "Entrada inválida"},
        500: {"model": ErrorResponse, "description": "Erro interno"},
    },
    summary="Simula decisões financeiras em linguagem natural",
    description=(
        "Interpreta a pergunta do usuário, identifica o cenário financeiro, "
        "executa o cálculo determinístico e retorna a comparação entre o "
        "caminho atual e o alternativo, com narrativa em linguagem simples.\n\n"
        "**Aviso obrigatório**: os resultados são estimativas educacionais, "
        "não constituem garantia nem recomendação de investimento."
    ),
)
def simulate(request: BBDecisionRequest) -> BBDecisionResponse:
    """Endpoint principal do BB Decision."""

    # Carrega perfil sintético do usuário se disponível
    user_context: Optional[dict] = None
    if request.user_id:
        from app.guardiao.user_repository import get_user_profile
        profile = get_user_profile(request.user_id)
        if profile:
            user_context = {
                "monthly_income": profile.get("monthly_income"),
                "monthly_expenses": profile.get("monthly_expenses"),
                "emergency_reserve": profile.get("emergency_reserve"),
            }

    # Intent parsing (sem LLM no MVP — usa fallback regex)
    # Em produção: passar llm_provider=get_llm_provider()
    try:
        intent = parse_intent(
            question=request.question,
            llm_provider=None,  # MVP: regex fallback
            user_context=user_context,
        )
    except InputValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "INPUT_VALIDATION_ERROR"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Erro ao processar a pergunta.", "code": "INTERNAL_ERROR"},
        )

    # Esclarecimento necessário
    if intent.clarification_needed:
        return BBDecisionResponse(
            scenario_type=intent.scenario_type,
            question_understood=intent.raw_question,
            current_path=PathSummary(label="atual", data={}),
            alternative_path=PathSummary(label="alternativo", data={}),
            delta={},
            warnings=[],
            assumptions=[],
            narrative=intent.clarification_question or "Preciso de mais informações.",
            disclaimer=MANDATORY_DISCLAIMER,
            clarification_needed=True,
            clarification_question=intent.clarification_question,
        )

    # Executa o motor financeiro determinístico
    try:
        calc_result = _run_calculator(intent)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "CALCULATION_ERROR"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Erro no cálculo da simulação.", "code": "INTERNAL_ERROR"},
        )

    # Narração (fallback determinístico no MVP)
    narrative = narrate(
        result=calc_result,
        llm_provider=None,  # MVP: fallback determinístico
        language_profile=request.language_profile,
    )

    return BBDecisionResponse(
        scenario_type=calc_result.scenario_type,
        question_understood=intent.raw_question,
        current_path=PathSummary(label="Situação atual", data=calc_result.current_path),
        alternative_path=PathSummary(label="Com a decisão", data=calc_result.alternative_path),
        delta=calc_result.delta,
        warnings=calc_result.warnings,
        assumptions=calc_result.assumptions,
        narrative=narrative,
        disclaimer=MANDATORY_DISCLAIMER,
        clarification_needed=False,
    )


@router.get("/health", summary="Verifica disponibilidade do BB Decision", tags=["Infraestrutura"])
def bbdecision_health() -> dict:
    return {"status": "ok", "service": "bbdecision"}
