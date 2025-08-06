from pydantic_settings import BaseSettings, SettingsConfigDict


class ENV(BaseSettings):
    model_config = SettingsConfigDict(validate_default=True, env_file=".env")
    BOT_TOKEN: str
    KIE_TOKEN: str