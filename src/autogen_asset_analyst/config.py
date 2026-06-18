from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Model Settings
    DEFAULT_MODEL: str = "deepseek-chat"

    # OpenAI API Configuration
    OPENAI_API_KEY: str | None = None
    OPENAI_BASE_URL: str = "https://api.deepseek.com"

    # Asset-Lens Path
    ASSET_LENS_PATH: str = "../asset-lens"

    # Roundtable Settings
    ROUNDTABLE_MAX_ROUNDS: int = 6

    # Application Settings
    APP_NAME: str = "AutoGen Asset Analyst"

    # API Server Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8002

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
