"""
Proteção contra prompt injection.

Mensagens de golpistas são entrada NÃO CONFIÁVEL para o LLM (RNF-05).
Este módulo sanitiza o input antes de qualquer chamada ao modelo de linguagem.

Estratégia de defesa em profundidade:
1. Limite de tamanho (MAX_INPUT_LENGTH).
2. Detecção de padrões de instrução que tentam sobrescrever o system prompt.
3. Escapamento de marcadores de papel (SYSTEM, USER, ASSISTANT).
4. Wrap em delimitadores explícitos que isolam o conteúdo do usuário.
"""

from __future__ import annotations

import re

from app.config import settings

# Padrões que indicam tentativa de prompt injection
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"\[USER\]", re.IGNORECASE),
    re.compile(r"\[ASSISTANT\]", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now", re.IGNORECASE),
    re.compile(r"disregard\s+(your|all)", re.IGNORECASE),
    re.compile(r"new\s+instructions?:", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
    re.compile(r"<\|im_end\|>", re.IGNORECASE),
    re.compile(r"###\s*instruction", re.IGNORECASE),
    re.compile(r"act\s+as\s+(if\s+you\s+are|a\s+)", re.IGNORECASE),
]

# Marcadores de papel a escapar
_ROLE_MARKERS = ["[SYSTEM]", "[USER]", "[ASSISTANT]", "<|im_start|>", "<|im_end|>"]


class InputValidationError(ValueError):
    """Lançada quando o input viola as regras de segurança."""
    pass


def sanitize_user_input(raw_input: str) -> str:
    """
    Valida e sanitiza uma string de entrada do usuário.

    Passos:
    - Valida tamanho máximo.
    - Detecta e rejeita tentativas óbvias de prompt injection.
    - Escapa marcadores de papel residuais.
    - Envolve o conteúdo em delimitadores seguros.

    Returns:
        String sanitizada, pronta para ser inserida no prompt do LLM.

    Raises:
        InputValidationError: se o input violar regras de segurança.
    """
    if not isinstance(raw_input, str):
        raise InputValidationError("Input deve ser uma string.")

    stripped = raw_input.strip()

    if not stripped:
        raise InputValidationError("Input não pode ser vazio.")

    if len(stripped) > settings.max_input_length:
        raise InputValidationError(
            f"Input excede o tamanho máximo de {settings.max_input_length} caracteres."
        )

    if settings.prompt_injection_guard:
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(stripped):
                raise InputValidationError(
                    "Input contém padrões não permitidos. Por favor, cole apenas "
                    "a mensagem ou descrição que deseja analisar."
                )

    # Escapa marcadores de papel que sobreviveram à detecção
    sanitized = stripped
    for marker in _ROLE_MARKERS:
        sanitized = sanitized.replace(marker, f"[ESCAPED:{marker[1:-1]}]")

    # Envolve em delimitadores que isolam o conteúdo do usuário no prompt
    return f"<conteudo_usuario>\n{sanitized}\n</conteudo_usuario>"


def validate_length(text: str, field_name: str = "campo") -> str:
    """
    Valida apenas o tamanho — para campos que não são entradas brutas
    de usuário (ex.: IDs, parâmetros estruturados).
    """
    if len(text) > settings.max_input_length:
        raise InputValidationError(
            f"O {field_name} excede o tamanho máximo permitido."
        )
    return text
