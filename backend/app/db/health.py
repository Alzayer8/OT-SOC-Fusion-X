from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db.session import engine_for


def database_is_ready(settings: Settings) -> bool:
    try:
        with engine_for(settings).connect() as connection:
            return bool(connection.scalar(text("SELECT 1")) == 1)
    except SQLAlchemyError:
        return False
