from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"
    SECRET_KEY: str = "SECRET_KEY_CHANGE_ME_IN_PRODUCTION"

    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "mail_prova@gmail.com"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    FRONTEND_URL: str = "http://localhost:4200"
    RESET_PASSWORD_TOKEN_LIFETIME_SECONDS: int = 1800
    COOKIE_SECURE: bool = False

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadminpassword"
    MINIO_BUCKET_NAME: str = "mission-documents"
    MINIO_SECURE: bool = False

    RECEIPT_AI_TIMEOUT_SECONDS: float = 45.0
    OLLAMA_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "gemma4:latest"
    OLLAMA_KEEP_ALIVE: str = "2m"
    OLLAMA_VISION_ENABLED: bool = True

    RECEIPT_DETECTOR_PROVIDER: str = "remote"
    DETECTOR_API_URL: str = ""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()