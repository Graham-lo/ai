from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./app.db"
    API_TOKEN: str = "devtoken"
    MASTER_KEY: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    APP_TIMEZONE: str = "Asia/Singapore"
    BASE_CURRENCY: str = "USDT"
    SYNC_INTERVAL_MINUTES: int = 0
    SYNC_PRESET: str = "last_30d"
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    class Config:
        env_file = ".env"


settings = Settings()
