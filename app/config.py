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
    
    # Gemini fallback
    GEMINI_API_KEY: str
    GEMINI_MODEL: str
    GEMINI_TIMEOUT_SECONDS: int
    LLM_FALLBACK_ENABLED: bool 
    
    SERVICE_VERSION: str = "0.2.0"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"     #"json" | "text"

    # Circuit breaker
    LLM_CIRCUIT_FAILURE_THRESHOLD: int
    LLM_CIRCUIT_OPEN_SECONDS: int
    
settings = Settings()