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

    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_NAME: str
    POSTGRES_USER: str
    POSTGRES_PASS: str

    redis_url: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

class Settings():
    def __init__(self):
        self.env = ENV()

    def generate_postgres_url(self) -> str:
        return f"postgresql+asyncpg://{self.env.POSTGRES_USER}:{self.env.POSTGRES_PASS}@{self.env.POSTGRES_HOST}:{self.env.POSTGRES_PORT}/{self.env.POSTGRES_NAME}"