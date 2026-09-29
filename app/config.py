from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # API auth
    GUARDRAIL_API_TOKEN: str

    # Groq LLM
    GROQ_API_KEY: str
    GROQ_MODEL: str
    GROQ_TIMEOUT_SECONDS: int
    LLM_TEMPERATURE: float
    LLM_MAX_TOKENS: int
    LLM_CONSENSUS_ATTEMPTS: int

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()