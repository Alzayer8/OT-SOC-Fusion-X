from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


@lru_cache(maxsize=8)
def get_engine(database_url: str, connect_timeout_seconds: int) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": connect_timeout_seconds},
    )


def engine_for(settings: Settings) -> Engine:
    return get_engine(
        settings.database_url_string,
        settings.database_connect_timeout_seconds,
    )


def session_factory(settings: Settings) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine_for(settings),
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


@contextmanager
def session_scope(settings: Settings) -> Generator[Session, None, None]:
    session = session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Generator[Session, None, None]:
    with session_scope(settings) as session:
        yield session
