"""
Perfis de linguagem para respostas personalizadas do Guardião.

RF-G-18: adaptar explicação a pelo menos dois perfis:
  - "standard": linguagem técnica, detalhada.
  - "low": linguagem simples, direta, sem jargão.

RN-07: A IA deve adaptar a linguagem ao perfil do usuário.
"""

from __future__ import annotations

from enum import Enum


class LanguageProfile(str, Enum):
    STANDARD = "standard"
    LOW = "low"


# Instruções de tom incluídas no system prompt do LLM conforme o perfil
PROFILE_INSTRUCTIONS: dict[LanguageProfile, str] = {
    LanguageProfile.STANDARD: (
        "Explique de forma completa e técnica. Use termos como 'engenharia social', "
        "'vetor de ataque', 'indicadores de comprometimento'. O usuário tem "
        "familiaridade com tecnologia e banco."
    ),
    LanguageProfile.LOW: (
        "Use linguagem muito simples e direta. Evite termos técnicos. "
        "Use frases curtas. Prefira alertas diretos como 'Cuidado!' e "
        "'Não faça o Pix'. Oriente a ligar para a pessoa pelo número que já conhece."
    ),
}


def get_profile_instruction(profile: str) -> str:
    """Retorna a instrução de tom para o perfil informado."""
    try:
        lp = LanguageProfile(profile.lower())
    except ValueError:
        lp = LanguageProfile.STANDARD
    return PROFILE_INSTRUCTIONS[lp]


def get_profile_label(profile: str) -> str:
    """Retorna rótulo legível do perfil."""
    return "Linguagem simples" if profile == "low" else "Padrão"
