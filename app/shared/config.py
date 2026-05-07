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
