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

    # Knowledge Base (langchain-llm-toolkit RAG)
    KNOWLEDGE_BASE_PATH: str = "../langchain-llm-toolkit"

    # Roundtable Settings
    ROUNDTABLE_MAX_ROUNDS: int = 6

    # Domestic Interest Rates (China)
    CN_DEPOSIT_RATE: float = 1.45  # 1年期存款基准利率(%)
    CN_LPR_RATE: float = 3.1       # 1年期LPR(%)
    CN_BOND_YIELD: float = 1.7     # 10年期国债收益率(%)

    # Application Settings
    APP_NAME: str = "AutoGen Asset Analyst"

    # API Server Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8002

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")


settings = Settings()
