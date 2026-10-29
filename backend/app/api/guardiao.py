"""
API REST do Guardião.

RF-G-12: entrada simples (mensagem/link/descrição).
RF-G-13..17: resposta completa (score, tipo, sinais, como aplica, próximo passo).
RF-G-18: resposta em dois perfis de linguagem.
RNF-05: validação de entradas, erros padronizados sem vazar detalhes internos.
RN-01: flag de revisão humana na resposta.
RC-02: campo de consentimento sintético (controle do cliente).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.guardiao.agent import run_guardiao
from app.guardiao.prompt_guard import InputValidationError
from app.config import settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas de entrada e saída
# ---------------------------------------------------------------------------

class LanguageProfileEnum(str, Enum):
    STANDARD = "standard"
    LOW = "low"


class InputChannelEnum(str, Enum):
    WHATSAPP_TEXT = "whatsapp_text"
    SMS_TEXT = "sms_text"
    EMAIL_TEXT = "email_text"
    TEXT = "text"


class GuardiaoRequest(BaseModel):
    """Requisição de análise do Guardião."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Mensagem, link ou descrição recebida para análise.",
        examples=["Oi, mãe. Troquei o número. Preciso que você faça um Pix de R$ 800 para mim agora."],
    )
    user_id: str = Field(
        default="",
        max_length=20,
        pattern=r"^[A-Za-z0-9_-]*$",
        description="ID sintético do usuário (opcional). Habilita análise de Nível 2.",
        examples=["U001"],
    )
    input_channel: InputChannelEnum = Field(
        default=InputChannelEnum.TEXT,
        description="Canal de origem da mensagem.",
    )
    transaction_id: Optional[str] = Field(
        default=None,
        max_length=20,
        pattern=r"^[A-Za-z0-9_-]*$",
        description="ID de transação pendente correlacionada (opcional).",
        examples=["TX003"],
    )
    language_profile: LanguageProfileEnum = Field(
        default=LanguageProfileEnum.STANDARD,
        description="Perfil de linguagem da resposta: 'standard' (técnico) ou 'low' (linguagem simples).",
    )
    monitoring_consent: bool = Field(
        default=True,
        description="RC-02: consentimento do cliente para uso do perfil no monitoramento.",
    )

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("A mensagem não pode ser composta apenas por espaços.")
        return v


class RiskSignalOut(BaseModel):
    signal_id: str
    label: str
    description: str
    evidence: str


class AnomalyOut(BaseModel):
    anomaly_id: str
    label: str
    description: str
    score_delta: float
    criterion: str


class RuleOut(BaseModel):
    rule_id: str
    triggered: bool
    reason: str


class InterventionOut(BaseModel):
    paused: bool
    pix_flow: bool = False          # True = fluxo (b): Pix pausado
    pause_is_temporary: bool
    scam_type: Optional[str]
    scam_name: Optional[str]
    how_it_works: Optional[str]
    how_applied: Optional[str]
    alert_signals: list[str]
    next_step: str
    language_profile: str
    language_profile_label: str
    user_control_note: str


class GuardiaoResponse(BaseModel):
    """Resposta completa da análise do Guardião."""

    # Risco
    risk_score: float = Field(description="Pontuação de risco de 0 a 100%.")
    risk_label: str = Field(description="Classificação qualitativa: baixo, médio ou alto.")

    # Sinais detectados (Nível 1)
    signals: list[RiskSignalOut] = Field(description="Sinais de engenharia social detectados.")

    # Análise de perfil (Nível 2)
    profile_found: bool
    anomalies: list[AnomalyOut] = Field(description="Anomalias em relação ao perfil do usuário.")
    level1_score: float
    level2_score_delta: float

    # Decisão
    requires_intervention: bool
    requires_human_review: bool
    rules_triggered: list[RuleOut]

    # Intervenção
    intervention: Optional[InterventionOut]
    intervention_message: str

    # Acompanhamento
    followup_message: str

    # Metadados
    input_channel: str
    language_profile: str
    transaction_id_analyzed: Optional[str] = None   # preenchido quando Pix foi correlacionado


class ErrorResponse(BaseModel):
    error: str
    code: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/analyze",
    response_model=GuardiaoResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Entrada inválida"},
        422: {"model": ErrorResponse, "description": "Erro de validação"},
        500: {"model": ErrorResponse, "description": "Erro interno"},
    },
    summary="Analisa uma mensagem em busca de golpes de engenharia social",
    description=(
        "Executa o fluxo agêntico completo do Guardião (6 etapas) sobre a mensagem "
        "informada. Retorna pontuação de risco, sinais detectados, tipo do golpe, "
        "como é aplicado, próximo passo pelos canais oficiais e, se necessário, "
        "mensagem de intervenção adaptada ao perfil do usuário.\n\n"
        "**Segurança**: o texto da mensagem nunca é registrado em logs."
    ),
)
def analyze_message(request: GuardiaoRequest) -> GuardiaoResponse:
    """
    Endpoint principal do Guardião.

    Mapeia GuardiaoRequest → run_guardiao → GuardiaoResponse.
    Erros de validação de entrada são retornados com HTTP 400.
    Erros internos retornam HTTP 500 sem expor detalhes.
    """
    try:
        result = run_guardiao(
            raw_input=request.message,
            user_id=request.user_id,
            input_channel=request.input_channel.value,
            transaction_id=request.transaction_id,
            language_profile=request.language_profile.value,
        )
    except InputValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(exc), "code": "INPUT_VALIDATION_ERROR"},
        )
    except Exception:
        # Não vazar detalhes internos
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Erro interno ao processar a análise.", "code": "INTERNAL_ERROR"},
        )

    if result.get("aborted"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": result.get("error", "Entrada inválida."),
                "code": "INPUT_VALIDATION_ERROR",
            },
        )

    l1 = result.get("level1_result", {})
    l2 = result.get("level2_result", {})
    intervention_data = result.get("intervention_data", {})
    rules = result.get("decision_rules_triggered", [])

    # Monta InterventionOut apenas se houve intervenção
    intervention_out: Optional[InterventionOut] = None
    if result.get("requires_intervention"):
        intervention_out = InterventionOut(
            paused=intervention_data.get("paused", False),
            pix_flow=intervention_data.get("pix_flow", False),
            pause_is_temporary=intervention_data.get("pause_is_temporary", False),
            scam_type=intervention_data.get("scam_type"),
            scam_name=intervention_data.get("scam_name"),
            how_it_works=intervention_data.get("how_it_works"),
            how_applied=intervention_data.get("how_applied"),
            alert_signals=intervention_data.get("alert_signals", []),
            next_step=intervention_data.get("next_step", ""),
            language_profile=intervention_data.get("language_profile", "standard"),
            language_profile_label=intervention_data.get("language_profile_label", "Padrão"),
            user_control_note=intervention_data.get("user_control_note", ""),
        )

    return GuardiaoResponse(
        risk_score=result.get("final_risk_score", 0.0),
        risk_label=result.get("final_risk_label", "baixo"),
        signals=[
            RiskSignalOut(
                signal_id=s["signal_id"],
                label=s["label"],
                description=s["description"],
                evidence=s.get("evidence", ""),
            )
            for s in l1.get("signals", [])
        ],
        profile_found=l2.get("profile_found", False),
        anomalies=[
            AnomalyOut(
                anomaly_id=a["anomaly_id"],
                label=a["label"],
                description=a["description"],
                score_delta=a["score_delta"],
                criterion=a["criterion"],
            )
            for a in l2.get("anomalies", [])
        ],
        level1_score=l1.get("risk_score", 0.0),
        level2_score_delta=l2.get("score_delta", 0.0),
        requires_intervention=result.get("requires_intervention", False),
        requires_human_review=result.get("requires_human_review", False),
        rules_triggered=[
            RuleOut(
                rule_id=r["rule_id"],
                triggered=r["triggered"],
                reason=r["reason"],
            )
            for r in rules
        ],
        intervention=intervention_out,
        intervention_message=result.get("intervention_message", ""),
        followup_message=result.get("followup_message", ""),
        input_channel=request.input_channel.value,
        language_profile=request.language_profile.value,
        transaction_id_analyzed=request.transaction_id,
    )


@router.get(
    "/health",
    summary="Verifica disponibilidade do Guardião",
    tags=["Infraestrutura"],
)
def guardiao_health() -> dict:
    return {"status": "ok", "service": "guardiao"}
