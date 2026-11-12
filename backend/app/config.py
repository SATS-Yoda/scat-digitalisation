from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration. Instantiating it fails when a required value is missing."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
