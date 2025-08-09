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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")