from sqlalchemy import create_engine

from .api import create_app
from .config import Settings
from .dify import DifySapSender

settings = Settings()
sap_sender = None
if settings.dify_base_url and settings.dify_sap_send_api_key:
    sap_sender = DifySapSender(
        settings.dify_base_url, settings.dify_sap_send_api_key.get_secret_value()
    )

app = create_app(create_engine(settings.database_url, pool_pre_ping=True), sap_sender)
