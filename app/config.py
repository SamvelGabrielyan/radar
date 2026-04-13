from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://radar:radar123@db:5432/radar"
    REDIS_URL: str = "redis://redis:6379/0"
    OPENAI_API_KEY: str = ""
    PARSER_DELAY: float = 2.0

    class Config:
        env_file = ".env"


settings = Settings()
