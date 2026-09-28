"""Conexão com o SQLite.

O banco padrão fica em data/recepcao24h.db. A variável DATABASE_URL troca o
arquivo (os testes e a bancada usam cópias temporárias).
"""
import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

RAIZ = Path(__file__).resolve().parent.parent
URL_PADRAO = f"sqlite:///{(RAIZ / 'data' / 'recepcao24h.db').as_posix()}"


class Base(DeclarativeBase):
    pass


engine = None
SessionLocal = None


def configurar(url: str | None = None):
    """(Re)cria o engine. Chamado na importação e pelos testes."""
    global engine, SessionLocal
    url = url or os.environ.get("DATABASE_URL", URL_PADRAO)
    if engine is not None:
        engine.dispose()
    engine = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return engine


def criar_tabelas():
    from app import models  # noqa: F401  (registra as tabelas)

    Base.metadata.create_all(engine)


def apagar_tabelas():
    from app import models  # noqa: F401

    Base.metadata.drop_all(engine)


def get_db():
    """Dependência do FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def sessao():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


configurar()
