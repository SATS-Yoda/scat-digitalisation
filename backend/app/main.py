from sqlalchemy import create_engine

from .api import create_app
from .config import Settings

app = create_app(create_engine(Settings().database_url, pool_pre_ping=True))
