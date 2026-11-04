"""
Configurações centrais da aplicação, carregadas de variáveis de ambiente.
Nenhuma credencial deve ser escrita aqui — use o arquivo .env.

O .env pode estar na raiz do projeto (bb-ia-mvp/) ou em backend/.
A busca é feita em ambos os locais, em ordem de prioridade.
"""

from __future__ import annotations
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Localiza o .env: verifica backend/.env e a raiz do projeto (um nível acima)
_here = Path(__file__).resolve().parent.parent  # backend/
_root = _here.parent                             # bb-ia-mvp/

_env_files: list[str] = []
for candidate in (_here / ".env", _root / ".env"):
    if candidate.is_file():
        _env_files.append(str(candidate))

# Fallback: usa ".env" relativo ao diretório de trabalho
_env_paths: tuple[str, ...] = tuple(_env_files) if _env_files else (".env",)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_paths,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provedor de LLM: "mock" (sem credenciais) | "watsonx" | "openai"
    # Padrão "mock" garante que o projeto rode sem credenciais.
    # Com credenciais ausentes, watsonx/openai recaem automaticamente em mock.
    llm_provider: str = "mock"

    # IBM watsonx.ai — texto (LLM pipeline) + visão (multimodal)
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_model_id: str = "ibm/granite-13b-chat-v2"
    # Modelo multimodal de visão para análise de imagens
    # Multitenant (sem deploy on demand), suporta português
    watsonx_vision_model_id: str = "meta-llama/llama-3-2-90b-vision-instruct"

    # IBM Watson Speech to Text — transcrição de áudios
    # Serviço separado do watsonx.ai: requer instância própria no IBM Cloud
    watson_stt_api_key: str = ""
    watson_stt_url: str = ""

    # OpenAI (mantido para compatibilidade — não é usado pelo multimodal IBM)
    openai_api_key: str = ""
    openai_model_id: str = "gpt-4o"
    openai_vision_model_id: str = "gpt-4o"

    # Aplicação
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./bb_ia_mvp.db"

    # Segurança
    max_input_length: int = 2000
    prompt_injection_guard: bool = True


settings = Settings()
