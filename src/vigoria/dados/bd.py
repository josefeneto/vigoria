"""Ligação à base de dados: SQLite em local, PostgreSQL (Neon) quando há DATABASE_URL.

O SQLAlchemy nunca escreve as consultas nem os valores nos registos (echo=False).
"""

from importlib.resources import files
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def criar_motor(url: str) -> Engine:
    """O motor da base de dados. «sqlite://» (em memória) partilha uma só ligação (testes)."""
    opcoes: dict[str, Any] = {"echo": False}
    if url in {"sqlite://", "sqlite:///:memory:"}:
        opcoes |= {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
    elif url.startswith("sqlite"):
        opcoes["connect_args"] = {"check_same_thread": False}
    else:
        opcoes["pool_pre_ping"] = True  # o Neon fecha as ligações paradas
    motor = create_engine(url, **opcoes)
    if motor.dialect.name == "sqlite":
        event.listen(motor, "connect", _ligar_chaves_estrangeiras)
    return motor


def _ligar_chaves_estrangeiras(ligacao: Any, _registo: Any) -> None:
    """Sem isto, o SQLite ignora o ON DELETE CASCADE."""
    cursor = ligacao.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def fabrica_sessoes(motor: Engine) -> sessionmaker[Session]:
    return sessionmaker(motor, expire_on_commit=False)


def migrar(motor: Engine) -> None:
    """Aplica as migrações Alembic em falta (upgrade head)."""
    config = Config()
    config.set_main_option("script_location", str(files("vigoria.dados") / "migracoes"))
    with motor.begin() as ligacao:
        config.attributes["connection"] = ligacao
        command.upgrade(config, "head")
