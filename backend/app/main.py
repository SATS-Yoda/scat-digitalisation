from sqlalchemy import create_engine

from .adapters import EntraProvider, RedisSessionStore
from .api import create_app
from .auth import AuthConfig, GroupMap
from .config import Settings
from .dify import DifySapSender

_AUTH_FIELDS = (
    "entra_tenant_id",
    "entra_client_id",
    "entra_client_secret",
    "entra_redirect_uri",
    "entra_group_icc1",
    "entra_group_icc2",
    "entra_group_admin",
    "redis_url",
)


def build_auth(settings: Settings) -> AuthConfig | None:
    """Real sign-in when fully configured. Otherwise only an explicit AUTH_DEV_MODE gives the
    open development identity; anything else refuses to start."""
    missing = [f.upper() for f in _AUTH_FIELDS if getattr(settings, f) is None]
    if len(missing) == len(_AUTH_FIELDS) and settings.auth_dev_mode:
        return None
    if missing:
        raise SystemExit(f"Sign-in is not configured; missing {', '.join(missing)}")
    return AuthConfig(
        provider=EntraProvider(
            settings.entra_tenant_id,
            settings.entra_client_id,
            settings.entra_client_secret.get_secret_value(),
            settings.entra_redirect_uri,
        ),
        store=RedisSessionStore.from_url(settings.redis_url.get_secret_value()),
        groups=GroupMap(
            settings.entra_group_icc1, settings.entra_group_icc2, settings.entra_group_admin
        ),
        # Plain http is allowed only for a localhost redirect URI.
        secure_cookie=not settings.entra_redirect_uri.startswith("http://localhost"),
    )


settings = Settings()
sap_sender = None
if settings.dify_base_url and settings.dify_sap_send_api_key:
    sap_sender = DifySapSender(
        settings.dify_base_url, settings.dify_sap_send_api_key.get_secret_value()
    )

app = create_app(
    create_engine(settings.database_url, pool_pre_ping=True), sap_sender, build_auth(settings)
)
