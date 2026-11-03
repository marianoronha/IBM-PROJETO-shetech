"""
Configurações centrais da aplicação, carregadas de variáveis de ambiente.
Nenhuma credencial deve ser escrita aqui — use o arquivo .env.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Provedor de LLM: "mock" (sem credenciais) | "watsonx" | "openai"
    # Padrão "mock" garante que o projeto rode sem credenciais.
    # Com credenciais ausentes, watsonx/openai recaem automaticamente em mock.
    llm_provider: str = "mock"

    # IBM watsonx.ai
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_model_id: str = "ibm/granite-13b-chat-v2"

    # OpenAI (fallback + multimodal)
    openai_api_key: str = ""
    openai_model_id: str = "gpt-4o"
    # Modelo com suporte a visão, usado para análise de imagens (multimodal)
    openai_vision_model_id: str = "gpt-4o"

    # Aplicação
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./bb_ia_mvp.db"

    # Segurança
    max_input_length: int = 2000
    prompt_injection_guard: bool = True


settings = Settings()
