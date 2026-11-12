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

    # Local development only: act as a fixed admin with no sign-in. Without it the process
    # refuses to start until Entra sign-in is configured.
    auth_dev_mode: bool = False

    # Entra sign-in (authorization-code flow, confidential client) and the groups that grant
    # each plant and admin rights. All of these, plus the Redis URL, are needed unless
    # AUTH_DEV_MODE is on.
    entra_tenant_id: str | None = None
    entra_client_id: str | None = None
    entra_client_secret: SecretStr | None = None
    entra_redirect_uri: str | None = None  # https://<host>/auth/callback
    entra_group_icc1: str | None = None
    entra_group_icc2: str | None = None
    entra_group_admin: str | None = None
    redis_url: SecretStr | None = None  # rediss://... ; may carry the password
