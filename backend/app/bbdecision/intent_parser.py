"""
Intent Parser do BB Decision.

RF-D-01, RF-D-02: o LLM converte a pergunta em linguagem natural em
parâmetros estruturados validados pelo schema (scenarios.py).

RESPONSABILIDADES DO LLM (apenas):
  1. Identificar o tipo de cenário.
  2. Extrair os valores numéricos mencionados na pergunta.
  3. Retornar JSON com os parâmetros.

PROIBIDO AO LLM:
  - Calcular qualquer valor numérico.
  - Inventar valores não mencionados (deve retornar missing_fields).
  - Alterar os parâmetros extraídos.

Se parâmetros obrigatórios estiverem ausentes → clarification_needed=True.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from app.bbdecision.scenarios import (
    IntentResult,
    ScenarioType,
    InstallmentParams,
    IncomeLossParams,
    JobChangeParams,
    HomePurchaseParams,
)
from app.guardiao.prompt_guard import sanitize_user_input, InputValidationError

# System prompt hardening: o LLM NUNCA calcula — apenas extrai e classifica.
_INTENT_SYSTEM_PROMPT = """Você é um assistente financeiro do Banco do Brasil.
Sua ÚNICA tarefa é analisar a pergunta do usuário e extrair parâmetros financeiros estruturados.

REGRAS ABSOLUTAS:
1. NUNCA calcule valores. NUNCA invente números que não foram mencionados.
2. Se um parâmetro obrigatório não foi informado, inclua seu nome em "missing_fields".
3. Retorne SOMENTE um objeto JSON válido, sem texto extra antes ou depois.
4. Se a pergunta for ambígua ou não se encaixar em nenhum cenário, use scenario_type="ambiguous".

CENÁRIOS DISPONÍVEIS:
- "parcelamento": usuário quer parcelar uma compra
- "perda_renda": usuário quer simular perda de renda por N meses
- "mudanca_emprego": usuário quer simular mudança de emprego
- "compra_casa": usuário quer simular compra de imóvel

PARÂMETROS POR CENÁRIO (retorne APENAS o JSON do cenário identificado):

parcelamento:
{"scenario_type":"parcelamento","purchase_value":NUMERO_OU_NULL,"installments":NUMERO_OU_NULL,"monthly_income":NUMERO_OU_NULL,"monthly_expenses":NUMERO_OU_NULL,"monthly_rate":NUMERO_OU_NULL,"missing_fields":["lista_de_campos_nao_informados"]}

perda_renda:
{"scenario_type":"perda_renda","monthly_income":NUMERO_OU_NULL,"monthly_expenses":NUMERO_OU_NULL,"emergency_reserve":NUMERO_OU_NULL,"loss_months":NUMERO_OU_NULL,"partial_income":NUMERO_OU_NULL,"missing_fields":["lista"]}

mudanca_emprego:
{"scenario_type":"mudanca_emprego","current_income":NUMERO_OU_NULL,"new_income":NUMERO_OU_NULL,"monthly_expenses":NUMERO_OU_NULL,"emergency_reserve":NUMERO_OU_NULL,"missing_fields":["lista"]}

compra_casa:
{"scenario_type":"compra_casa","property_value":NUMERO_OU_NULL,"down_payment":NUMERO_OU_NULL,"monthly_income":NUMERO_OU_NULL,"monthly_expenses":NUMERO_OU_NULL,"emergency_reserve":NUMERO_OU_NULL,"mortgage_term_months":NUMERO_OU_NULL,"mortgage_rate_monthly":NUMERO_OU_NULL,"missing_fields":["lista"]}

ambiguous:
{"scenario_type":"ambiguous","missing_fields":[],"clarification_question":"PERGUNTA_DE_ESCLARECIMENTO"}
"""

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "parcelamento": ["purchase_value", "installments", "monthly_income", "monthly_expenses"],
    "perda_renda": ["monthly_income", "monthly_expenses", "emergency_reserve", "loss_months"],
    "mudanca_emprego": ["current_income", "new_income", "monthly_expenses", "emergency_reserve"],
    "compra_casa": ["property_value", "down_payment", "monthly_income", "monthly_expenses", "emergency_reserve"],
}


def _extract_json(text: str) -> dict:
    """Extrai o primeiro objeto JSON válido do texto do LLM."""
    text = text.strip()
    # Tenta direto
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Tenta encontrar bloco JSON na resposta
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise ValueError("LLM não retornou JSON válido.")


def _build_params(scenario_type: str, raw: dict):
    """Constrói o objeto de parâmetros a partir do dict extraído pelo LLM."""
    # Remove campos nulos e não-parâmetros
    excluded = {"scenario_type", "missing_fields", "clarification_question"}
    params_dict = {k: v for k, v in raw.items() if k not in excluded and v is not None}

    if scenario_type == "parcelamento":
        return InstallmentParams(**params_dict)
    if scenario_type == "perda_renda":
        return IncomeLossParams(**params_dict)
    if scenario_type == "mudanca_emprego":
        return JobChangeParams(**params_dict)
    if scenario_type == "compra_casa":
        return HomePurchaseParams(**params_dict)
    return None


def parse_intent(
    question: str,
    llm_provider=None,
    user_context: Optional[dict] = None,
) -> IntentResult:
    """
    Converte a pergunta em linguagem natural em IntentResult estruturado.

    Se llm_provider for None (modo de teste/fallback), usa extração por regex.
    Se parâmetros obrigatórios estiverem faltando, retorna clarification_needed=True.

    Args:
        question: pergunta do usuário (entrada NÃO CONFIÁVEL — será sanitizada).
        llm_provider: provedor LLM (opcional).
        user_context: contexto sintético do usuário para pré-popular parâmetros.

    Returns:
        IntentResult com scenario_type, params ou missing_fields.
    """
    # Sanitiza o input (entrada não confiável)
    try:
        sanitized = sanitize_user_input(question)
    except InputValidationError as exc:
        return IntentResult(
            scenario_type="ambiguous",
            clarification_needed=True,
            clarification_question=f"Não consegui processar sua pergunta: {exc}",
            raw_question="[REDACTED]",
        )

    raw_question = re.sub(r"</?conteudo_usuario>", "", sanitized).strip()

    if llm_provider is not None:
        return _parse_with_llm(raw_question, llm_provider, user_context)
    else:
        return _parse_with_regex(raw_question, user_context)


def _parse_with_llm(
    question: str,
    llm_provider,
    user_context: Optional[dict],
) -> IntentResult:
    """Usa o LLM para extrair parâmetros estruturados."""
    context_note = ""
    if user_context:
        # Injeta contexto do usuário SOMENTE como valores sugeridos no prompt
        income = user_context.get("monthly_income", "não informado")
        expenses = user_context.get("monthly_expenses", "não informado")
        reserve = user_context.get("emergency_reserve", "não informado")
        context_note = (
            f"\nContexto financeiro do usuário (use se não informado na pergunta):\n"
            f"- Renda mensal: R$ {income}\n"
            f"- Despesas mensais: R$ {expenses}\n"
            f"- Reserva de emergência: R$ {reserve}\n"
        )

    user_msg = f"{context_note}\nPergunta do usuário:\n{question}"

    try:
        response = llm_provider.complete(
            system_prompt=_INTENT_SYSTEM_PROMPT,
            user_message=user_msg,
        )
        raw = _extract_json(response.text)
    except Exception as exc:
        return IntentResult(
            scenario_type="ambiguous",
            clarification_needed=True,
            clarification_question=(
                "Não consegui interpretar sua pergunta. "
                "Poderia reformulá-la com mais detalhes sobre o valor e o prazo?"
            ),
            raw_question=question[:100],
        )

    return _build_intent_result(raw, question)


def _parse_with_regex(question: str, user_context: Optional[dict]) -> IntentResult:
    """
    Fallback para testes sem LLM: extrai parâmetros básicos por regex.
    Usado apenas em testes unitários e demonstrações sem credenciais.
    """
    q_lower = question.lower()

    # Detecta cenário
    if any(w in q_lower for w in ["parcel", "12x", "vezes", "prestação"]):
        scenario = "parcelamento"
    elif any(w in q_lower for w in ["perder", "perda", "sem renda", "ficar sem"]):
        scenario = "perda_renda"
    elif any(w in q_lower for w in ["mudar de emprego", "novo emprego", "mudança de emprego", "trocar de emprego"]):
        scenario = "mudanca_emprego"
    elif any(w in q_lower for w in ["comprar", "casa", "imóvel", "apartamento", "financiamento"]):
        scenario = "compra_casa"
    else:
        return IntentResult(
            scenario_type="ambiguous",
            clarification_needed=True,
            clarification_question=(
                "Não identificei o tipo de simulação. Você quer simular: "
                "parcelamento, perda de renda, mudança de emprego ou compra de imóvel?"
            ),
            raw_question=question[:100],
        )

    # Extrai valores numéricos da pergunta
    values = re.findall(r"R?\$?\s*(\d[\d.,]*)", question)
    numbers = []
    for v in values:
        try:
            numbers.append(float(v.replace(".", "").replace(",", ".")))
        except ValueError:
            pass

    # Mescla com contexto do usuário
    ctx = user_context or {}

    raw: dict = {"scenario_type": scenario, "missing_fields": []}

    if scenario == "parcelamento":
        raw["purchase_value"] = numbers[0] if numbers else None
        raw["installments"] = None
        raw["monthly_income"] = ctx.get("monthly_income")
        raw["monthly_expenses"] = ctx.get("monthly_expenses")
        # Tenta extrair parcelas
        m = re.search(r"(\d+)\s*x", q_lower)
        if m:
            raw["installments"] = int(m.group(1))

    elif scenario == "perda_renda":
        raw["monthly_income"] = ctx.get("monthly_income")
        raw["monthly_expenses"] = ctx.get("monthly_expenses")
        raw["emergency_reserve"] = ctx.get("emergency_reserve")
        m = re.search(r"(\d+)\s*m[eê]s", q_lower)
        raw["loss_months"] = int(m.group(1)) if m else None
        raw["partial_income"] = 0.0

    elif scenario == "mudanca_emprego":
        raw["current_income"] = ctx.get("monthly_income")
        raw["new_income"] = numbers[0] if numbers else None
        raw["monthly_expenses"] = ctx.get("monthly_expenses")
        raw["emergency_reserve"] = ctx.get("emergency_reserve")

    elif scenario == "compra_casa":
        raw["property_value"] = numbers[0] if numbers else None
        raw["down_payment"] = numbers[1] if len(numbers) > 1 else None
        raw["monthly_income"] = ctx.get("monthly_income")
        raw["monthly_expenses"] = ctx.get("monthly_expenses")
        raw["emergency_reserve"] = ctx.get("emergency_reserve")

    return _build_intent_result(raw, question)


def _build_intent_result(raw: dict, original_question: str) -> IntentResult:
    """Valida o dict extraído e constrói IntentResult."""
    scenario_type: ScenarioType = raw.get("scenario_type", "ambiguous")

    if scenario_type == "ambiguous":
        return IntentResult(
            scenario_type="ambiguous",
            clarification_needed=True,
            clarification_question=raw.get("clarification_question", (
                "Poderia detalhar mais sua pergunta? "
                "Informe o valor e o tipo de simulação desejada."
            )),
            raw_question=original_question[:100],
        )

    required = _REQUIRED_FIELDS.get(scenario_type, [])
    missing = [
        f for f in required
        if raw.get(f) is None
    ]
    # Adiciona ao missing os que vieram no array do LLM
    llm_missing = raw.get("missing_fields", [])
    missing = list(set(missing + llm_missing))

    if missing:
        field_labels = {
            "purchase_value": "valor da compra",
            "installments": "número de parcelas",
            "monthly_income": "renda mensal",
            "monthly_expenses": "despesas mensais",
            "emergency_reserve": "reserva de emergência",
            "loss_months": "meses de perda de renda",
            "partial_income": "renda parcial no período",
            "current_income": "renda atual",
            "new_income": "nova renda",
            "property_value": "valor do imóvel",
            "down_payment": "valor da entrada",
        }
        missing_labels = [field_labels.get(f, f) for f in missing]
        return IntentResult(
            scenario_type=scenario_type,
            clarification_needed=True,
            clarification_question=(
                f"Para simular o cenário de {scenario_type.replace('_', ' ')}, "
                f"preciso das seguintes informações: {', '.join(missing_labels)}."
            ),
            missing_fields=missing,
            raw_question=original_question[:100],
        )

    try:
        params = _build_params(scenario_type, raw)
    except Exception as exc:
        return IntentResult(
            scenario_type=scenario_type,
            clarification_needed=True,
            clarification_question=f"Parâmetros inválidos: {exc}. Poderia verificar os valores?",
            raw_question=original_question[:100],
        )

    return IntentResult(
        scenario_type=scenario_type,
        params=params,
        clarification_needed=False,
        raw_question=original_question[:100],
    )
