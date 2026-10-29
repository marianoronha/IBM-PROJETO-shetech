"""
Abstração do provedor de LLM.

Suporta:
  - "mock"    → respostas deterministicas, sem credenciais (padrão quando nenhuma chave configurada)
  - "watsonx" → IBM watsonx.ai (requer WATSONX_API_KEY + WATSONX_PROJECT_ID)
  - "openai"  → OpenAI (requer OPENAI_API_KEY)

O provedor ativo é definido pela variável LLM_PROVIDER no .env.
Se LLM_PROVIDER=watsonx mas as credenciais estiverem ausentes, o sistema
recai automaticamente no MockLLMProvider com aviso em log.

SEGURANÇA: este módulo NÃO recebe entradas brutas do usuário.
Receba apenas prompts já sanitizados pelo prompt_guard.py.
"""

from __future__ import annotations

import logging
from typing import Protocol

from app.config import settings

logger = logging.getLogger(__name__)


class LLMResponse:
    """Resposta padronizada do LLM, independente do provedor."""

    def __init__(self, text: str, provider: str, model: str, is_mock: bool = False) -> None:
        self.text = text
        self.provider = provider
        self.model = model
        self.is_mock = is_mock   # True → resultado NÃO representa um LLM real

    def __repr__(self) -> str:  # pragma: no cover
        mock_flag = " [MOCK]" if self.is_mock else ""
        return (
            f"LLMResponse(provider={self.provider!r}{mock_flag}, "
            f"model={self.model!r}, text={self.text[:60]!r}...)"
        )


class LLMProvider(Protocol):
    """Interface que todo provedor deve implementar."""

    def complete(self, system_prompt: str, user_message: str) -> LLMResponse:
        ...


# ---------------------------------------------------------------------------
# Provedor Mock — determinístico, sem credenciais
# ---------------------------------------------------------------------------

class MockLLMProvider:
    """
    Provedor de LLM simulado para desenvolvimento e testes.

    Retorna respostas estruturadas fixas com base em palavras-chave no prompt.
    NÃO representa o comportamento de um LLM real.

    ⚠️  ATENÇÃO: resultados com este provider devem ser marcados como
        "obtidos com Mock LLM — não representam modelo real" em relatórios.
    """

    MODEL_ID = "mock-deterministic-v1"
    PROVIDER_NAME = "mock"

    # Respostas fixas usadas pelo narrador do BB Decision
    _NARRATIVES: dict[str, str] = {
        "parcelamento": (
            "Com essa compra parcelada, você pagará um total maior do que o valor à vista "
            "devido aos juros. O impacto mensal no seu orçamento está indicado acima. "
            "Compare o valor total pago com o preço à vista antes de decidir.\n\n"
            "⚠️ Resposta gerada por Mock LLM — não representa modelo de linguagem real."
        ),
        "perda_renda": (
            "Durante o período de perda de renda, suas despesas continuarão. "
            "Verifique se sua reserva de emergência é suficiente para cobrir o período. "
            "O detalhamento do impacto está nos campos acima.\n\n"
            "⚠️ Resposta gerada por Mock LLM — não representa modelo de linguagem real."
        ),
        "mudanca_emprego": (
            "A mudança de emprego terá um impacto direto no seu saldo mensal. "
            "Verifique o comprometimento de renda antes e depois da decisão. "
            "Os números detalhados estão na comparação acima.\n\n"
            "⚠️ Resposta gerada por Mock LLM — não representa modelo de linguagem real."
        ),
        "compra_casa": (
            "A compra desse imóvel impacta seu orçamento mensal com a prestação do financiamento "
            "e reduz sua reserva de emergência com a entrada. "
            "Verifique o comprometimento de renda resultante e compare com o limite recomendado.\n\n"
            "⚠️ Resposta gerada por Mock LLM — não representa modelo de linguagem real."
        ),
        "default": (
            "Os resultados da simulação estão detalhados nos campos acima. "
            "Compare a situação atual com a alternativa antes de tomar sua decisão.\n\n"
            "⚠️ Resposta gerada por Mock LLM — não representa modelo de linguagem real."
        ),
    }

    # Resposta fixa para intent parsing
    _INTENT_PARSE_TEMPLATE = (
        '{{"scenario_type": "ambiguous", "clarification_needed": true, '
        '"clarification_question": "Mock LLM: não foi possível identificar o cenário. '
        'Por favor, especifique o valor, número de parcelas ou tipo de decisão.", '
        '"params": {{}}}}'
    )

    def complete(self, system_prompt: str, user_message: str) -> LLMResponse:
        """
        Retorna uma resposta mock baseada em palavras-chave do prompt.
        Não faz chamada de rede.
        """
        combined = (system_prompt + " " + user_message).lower()

        # Detecta tipo de cenário pelo contexto do prompt
        scenario = "default"
        for key in self._NARRATIVES:
            if key != "default" and key in combined:
                scenario = key
                break

        # Se o prompt pede extração de intent (intent_parser), retorna JSON mínimo
        if "json" in combined and ("scenario_type" in combined or "intent" in combined):
            text = self._INTENT_PARSE_TEMPLATE
        else:
            text = self._NARRATIVES[scenario]

        return LLMResponse(
            text=text,
            provider=self.PROVIDER_NAME,
            model=self.MODEL_ID,
            is_mock=True,
        )


# ---------------------------------------------------------------------------
# Provedor IBM watsonx.ai
# ---------------------------------------------------------------------------

class WatsonxProvider:
    """Integração com IBM watsonx.ai via ibm-watsonx-ai SDK."""

    def __init__(self) -> None:
        if not settings.watsonx_api_key or not settings.watsonx_project_id:
            raise EnvironmentError(
                "WATSONX_API_KEY e WATSONX_PROJECT_ID são obrigatórios quando "
                "LLM_PROVIDER=watsonx. Configure o arquivo .env."
            )
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference

        credentials = Credentials(
            url=settings.watsonx_url,
            api_key=settings.watsonx_api_key,
        )
        client = APIClient(credentials=credentials, project_id=settings.watsonx_project_id)
        self._model = ModelInference(
            model_id=settings.watsonx_model_id,
            api_client=client,
        )
        self._model_id = settings.watsonx_model_id

    def complete(self, system_prompt: str, user_message: str) -> LLMResponse:
        prompt = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{user_message}\n\n[ASSISTANT]\n"
        result = self._model.generate_text(prompt=prompt)
        return LLMResponse(
            text=result,
            provider="watsonx",
            model=self._model_id,
            is_mock=False,
        )


# ---------------------------------------------------------------------------
# Provedor OpenAI (fallback)
# ---------------------------------------------------------------------------

class OpenAIProvider:
    """Integração com OpenAI como provedor alternativo."""

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY é obrigatória quando LLM_PROVIDER=openai. "
                "Configure o arquivo .env."
            )
        from openai import OpenAI

        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model_id = settings.openai_model_id

    def complete(self, system_prompt: str, user_message: str) -> LLMResponse:
        response = self._client.chat.completions.create(
            model=self._model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
        )
        text = response.choices[0].message.content or ""
        return LLMResponse(text=text, provider="openai", model=self._model_id, is_mock=False)


# ---------------------------------------------------------------------------
# Factory — seleciona o provedor via variável de ambiente
# ---------------------------------------------------------------------------

def get_llm_provider() -> LLMProvider:
    """
    Retorna a instância do provedor configurado em LLM_PROVIDER.

    Fallback automático para MockLLMProvider quando:
      - LLM_PROVIDER=mock (explícito)
      - LLM_PROVIDER=watsonx mas WATSONX_API_KEY ou WATSONX_PROJECT_ID ausentes
      - LLM_PROVIDER=openai mas OPENAI_API_KEY ausente

    O fallback emite um aviso de log para rastreabilidade.
    """
    provider = settings.llm_provider.lower()

    if provider == "mock":
        return MockLLMProvider()

    if provider == "watsonx":
        if not settings.watsonx_api_key or not settings.watsonx_project_id:
            logger.warning(
                "LLM_PROVIDER=watsonx mas credenciais ausentes. "
                "Usando MockLLMProvider. "
                "Resultados NÃO representam modelo IBM watsonx.ai real."
            )
            return MockLLMProvider()
        return WatsonxProvider()

    if provider == "openai":
        if not settings.openai_api_key:
            logger.warning(
                "LLM_PROVIDER=openai mas OPENAI_API_KEY ausente. "
                "Usando MockLLMProvider. "
                "Resultados NÃO representam modelo OpenAI real."
            )
            return MockLLMProvider()
        return OpenAIProvider()

    logger.warning(
        "LLM_PROVIDER=%r inválido. Usando MockLLMProvider.", provider
    )
    return MockLLMProvider()
