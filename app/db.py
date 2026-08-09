"""SQLite wiring through SQLModel."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlmodel import Session, SQLModel, create_engine

from app.config import DB_PATH


def build_engine():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{DB_PATH}",
        connect_args={"check_same_thread": False},
    )


engine = build_engine()


def init_db() -> None:
    from app import models as _models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def new_session() -> Session:
    """Open a session for use from background threads."""
    return Session(engine)
