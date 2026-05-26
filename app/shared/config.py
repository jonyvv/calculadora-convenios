from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    storage_root: str = "storage"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-flash"
    gemini_timeout_seconds: int = 90
    gemini_max_output_tokens: int = 65536
    gemini_structuring_chunk_chars: int = 18000
    gemini_fallback_to_mock: bool = True
    use_mock_gemini: bool = False
    database_url: str = "postgresql://postgres:postgres@postgres:5432/payroll"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def normalize_gemini_api_key(cls, value):
        if value is None:
            return value
        cleaned = str(value).strip().strip('"').strip("'")
        if cleaned.startswith("AAIza"):
            raise ValueError("GEMINI_API_KEY parece tener una 'A' extra al inicio. Debe empezar con 'AIza'.")
        return cleaned
