from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process configuration. Instantiating it fails when a required value is missing."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Dify SAP-send workflow, e.g. https://<dify-host>/v1 and that workflow's app key.
    # Without both, Send answers 503 and nothing is claimed.
    dify_base_url: str | None = None
    dify_sap_send_api_key: SecretStr | None = None
