"""
Endpoint de chat do Guardião.

POST /api/chat

Recebe histórico de mensagens e retorna resposta do assistente.
Usa o provedor de LLM configurado (watsonx / openai / mock).
Se nenhuma credencial estiver configurada, responde com base em
conhecimento pré-programado sobre golpes, segurança e finanças.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.llm.provider import get_llm_provider

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=20)


class ChatResponse(BaseModel):
    resposta: str


# ---------------------------------------------------------------------------
# System prompt do Guardião
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """Você é o Guardião, assistente virtual do SheTech em parceria com o Banco do Brasil.

Você ajuda pessoas a se protegerem de golpes digitais e fraudes, e também responde dúvidas gerais sobre finanças, tecnologia e segurança digital.

Diretrizes:
- Responda sempre em português brasileiro, de forma clara e acessível.
- Seja objetivo e direto, sem enrolação.
- Em casos de golpes ou fraudes, sempre oriente a pessoa a entrar em contato com o banco e registrar boletim de ocorrência.
- Nunca peça dados pessoais, senhas ou informações bancárias.
- Se não souber responder algo, diga honestamente.
- Mantenha um tom amigável e acolhedor.
"""

# ---------------------------------------------------------------------------
# Respostas de fallback — usadas quando o LLM é mock
# ---------------------------------------------------------------------------

_FALLBACK_RESPOSTAS: dict[str, str] = {
    "golpe": (
        "Para identificar um golpe, fique atento a estes sinais:\n\n"
        "🚨 **Urgência excessiva** — pressão para agir imediatamente\n"
        "🚨 **Ofertas boas demais** — ganhos fáceis ou prêmios inesperados\n"
        "🚨 **Pedido de dados pessoais** — CPF, senha ou código por mensagem\n"
        "🚨 **Links suspeitos** — URLs estranhas ou encurtadas\n"
        "🚨 **Contato não solicitado** — ligações ou mensagens de desconhecidos\n\n"
        "Em caso de dúvida, **não clique, não responda e não transfira dinheiro**. "
        "Ligue para o número oficial do seu banco."
    ),
    "phishing": (
        "Phishing é quando criminosos se passam por empresas ou pessoas de confiança "
        "para roubar seus dados.\n\n"
        "**Como se proteger:**\n"
        "✅ Verifique sempre o endereço do site (começa com https://)\n"
        "✅ Desconfie de e-mails pedindo senha ou dados bancários\n"
        "✅ Nunca clique em links de mensagens não solicitadas\n"
        "✅ Use autenticação em dois fatores nas suas contas"
    ),
    "senha": (
        "**Como criar uma senha segura:**\n\n"
        "✅ Use pelo menos 12 caracteres\n"
        "✅ Misture letras maiúsculas, minúsculas, números e símbolos\n"
        "✅ Não use datas de aniversário ou nomes\n"
        "✅ Use senhas diferentes para cada serviço\n"
        "✅ Considere usar um gerenciador de senhas\n\n"
        "Exemplo de senha forte: `Gua@rd1ao#2024!`"
    ),
    "pix": (
        "O Pix é seguro quando usado corretamente. Mas atenção:\n\n"
        "🚨 **Nunca transfira para 'desbloquear' valores** — isso é golpe\n"
        "🚨 **Confira sempre o nome do destinatário** antes de confirmar\n"
        "🚨 **Desconfie de Pix para 'testar'** ou receber troco\n"
        "🚨 **Bancos nunca pedem Pix** por telefone ou WhatsApp\n\n"
        "Em caso de golpe via Pix, acione o **Mecanismo Especial de Devolução (MED)** "
        "pelo seu banco em até 80 dias."
    ),
    "financas": (
        "**Dicas básicas de organização financeira:**\n\n"
        "📊 Anote todas as suas despesas por pelo menos 30 dias\n"
        "📊 Separe despesas fixas (aluguel, contas) das variáveis\n"
        "📊 Tente guardar pelo menos 10% da renda todo mês\n"
        "📊 Mantenha uma reserva de emergência de 3 a 6 meses de despesas\n"
        "📊 Quite dívidas com juros altos primeiro (cartão, cheque especial)"
    ),
    "link": (
        "**Como saber se um link é falso:**\n\n"
        "🔍 Passe o mouse sobre o link e veja o endereço real na barra inferior\n"
        "🔍 Desconfie de URLs com erros de digitação (ex: `bancodo-brasil.com`)\n"
        "🔍 Sites seguros têm o cadeado 🔒 e começam com `https://`\n"
        "🔍 Use o site **Registros.br** para verificar quem é o dono do domínio\n"
        "🔍 Encurtadores de URL (bit.ly, etc.) podem esconder destinos maliciosos"
    ),
    "default": (
        "Olá! Sou o Guardião, seu assistente de segurança digital. "
        "Posso te ajudar com:\n\n"
        "🛡️ Identificar golpes e fraudes\n"
        "🔐 Dicas de segurança digital\n"
        "💰 Orientações financeiras básicas\n"
        "🔗 Verificar links suspeitos\n\n"
        "Me conta com o que posso te ajudar!"
    ),
}


def _fallback_resposta(texto: str) -> str:
    """Retorna resposta pré-programada baseada em palavras-chave."""
    t = texto.lower()
    if any(p in t for p in ["golpe", "fraude", "scam", "identificar", "suspeito"]):
        return _FALLBACK_RESPOSTAS["golpe"]
    if any(p in t for p in ["phishing", "email falso", "site falso"]):
        return _FALLBACK_RESPOSTAS["phishing"]
    if any(p in t for p in ["senha", "password", "segura"]):
        return _FALLBACK_RESPOSTAS["senha"]
    if any(p in t for p in ["pix", "transferência", "devolução"]):
        return _FALLBACK_RESPOSTAS["pix"]
    if any(p in t for p in ["financ", "dinheiro", "orçamento", "gastar", "poupar", "economiz"]):
        return _FALLBACK_RESPOSTAS["financas"]
    if any(p in t for p in ["link", "url", "site", "endereço"]):
        return _FALLBACK_RESPOSTAS["link"]
    return _FALLBACK_RESPOSTAS["default"]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "",
    response_model=ChatResponse,
    summary="Envia mensagem para o assistente Guardião",
)
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Recebe o histórico de mensagens e retorna a resposta do assistente.

    Usa o provedor de LLM configurado (watsonx / openai).
    Sem credenciais, usa respostas pré-programadas sobre segurança digital.
    """
    # Última mensagem do usuário
    ultima = next(
        (m.content for m in reversed(req.messages) if m.role == "user"),
        "",
    )

    try:
        provider = get_llm_provider()

        # Se for mock, usa respostas pré-programadas mais ricas
        if getattr(provider, "PROVIDER_NAME", "") == "mock":
            return ChatResponse(resposta=_fallback_resposta(ultima))

        # Monta histórico para o LLM real
        historico = "\n".join(
            f"{'Usuário' if m.role == 'user' else 'Assistente'}: {m.content}"
            for m in req.messages[-10:]
        )

        resposta = provider.complete(
            system_prompt=_SYSTEM_PROMPT,
            user_message=historico,
        )
        return ChatResponse(resposta=resposta.text)

    except Exception as exc:
        logger.error("Erro no chat: %s", exc)
        # Fallback garantido — o chatbot nunca deve exibir erro técnico ao usuário
        return ChatResponse(resposta=_fallback_resposta(ultima))
