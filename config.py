
from pydantic_settings import BaseSettings, SettingsConfigDict


class ENV(BaseSettings):
    model_config = SettingsConfigDict(validate_default=True, env_file=".env")
    BOT_TOKEN: str
    KIE_TOKEN: str
    yc_folder_id: str
    yc_api_key: str
    yc_s3_access_key_id: str
    yc_s3_secret_access_key: str
    yc_s3_endpoint_url: str = "https://storage.yandexcloud.net"
    webhook_endpoint: str

    bot_api_token: str

    DEBUG: bool

    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_NAME: str
    POSTGRES_USER: str
    POSTGRES_PASS: str

    redis_url: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    CELERY_TIMEZONE: str
    
    test_payment_token: str
    life_payment_token: str

    OPENAI_API_KEY: str
    OPENAI_MODEL: str

    BASE_URL: str
    CALLBACK_PATH: str
    SUPPORT_USERNAME: str

    LIVE_YOOKASSA_ACCOINT_ID: str
    LIVE_YOOKASSA_SECRET_KEY: str
    TEST_YOOKASSA_ACCOINT_ID: str
    TEST_YOOKASSA_SECRET_KEY: str
    ADMINS_CHAT_ID: str
    ADMIN_SITE: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

class Settings():
    def __init__(self):
        self.env = ENV()

    def generate_postgres_url(self) -> str:
        return f"postgresql+asyncpg://{self.env.POSTGRES_USER}:{self.env.POSTGRES_PASS}@{self.env.POSTGRES_HOST}:{self.env.POSTGRES_PORT}/{self.env.POSTGRES_NAME}"
    
    def get_admins_chat_id(self) -> list[int]:
        ids = self.env.ADMINS_CHAT_ID.split(":")
        return [int(id) for id in ids]
