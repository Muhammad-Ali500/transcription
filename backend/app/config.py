from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    APP_NAME: str = "Transcription & Segmentation App"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    DB_HOST: str = "postgres"
    DB_PORT: int = 5432
    DB_NAME: str = "transcription_db"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"

    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "uploads"

    WHISPER_MODEL: str = "large-v3"
    WHISPER_MODEL_DIR: str = "/app/models"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024
    ALLOWED_EXTENSIONS: list = [".mp3", ".wav", ".mp4", ".m4a", ".ogg", ".flac", ".aac"]
    UPLOAD_DIR: str = "/tmp/uploads"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
