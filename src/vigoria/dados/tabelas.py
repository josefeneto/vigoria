"""Tabelas da base de dados (SQLAlchemy 2.x).

Cada linha de dados pessoais pertence a um utilizador; apagar o utilizador apaga tudo o que
é dele (ON DELETE CASCADE). O utilizador é identificado pelo `sub` do Auth0, nunca pelo email.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Json = JSON().with_variant(JSONB(), "postgresql")


def agora() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


def _dono() -> Mapped[int]:
    return mapped_column(ForeignKey("utilizador.id", ondelete="CASCADE"), index=True)


class Utilizador(Base):
    __tablename__ = "utilizador"

    id: Mapped[int] = mapped_column(primary_key=True)
    sub: Mapped[str] = mapped_column(String(255), unique=True)
    fornecedor: Mapped[str] = mapped_column(String(50))  # «google-oauth2», «auth0»
    email: Mapped[str] = mapped_column(String(320), index=True)  # em minúsculas
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Consentimento(Base):
    __tablename__ = "consentimento"

    id: Mapped[int] = mapped_column(primary_key=True)
    utilizador_id: Mapped[int] = _dono()
    tipo: Mapped[str] = mapped_column(String(30))  # termos, saude, maior_idade
    versao_texto: Mapped[str] = mapped_column(String(30))
    data: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class QuestionarioGuardado(Base):
    __tablename__ = "questionario"

    id: Mapped[int] = mapped_column(primary_key=True)
    utilizador_id: Mapped[int] = _dono()
    respostas: Mapped[dict[str, Any]] = mapped_column(Json)  # Questionario em JSON
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class PlanoGuardado(Base):
    __tablename__ = "plano"

    id: Mapped[int] = mapped_column(primary_key=True)
    utilizador_id: Mapped[int] = _dono()
    questionario_id: Mapped[int] = mapped_column(
        ForeignKey("questionario.id", ondelete="CASCADE"), index=True
    )
    conteudo: Mapped[dict[str, Any]] = mapped_column(Json)  # Plano em JSON
    estrategia: Mapped[dict[str, Any]] = mapped_column(Json)  # Estrategia em JSON
    versao_prompt: Mapped[str] = mapped_column(String(50))
    provedor: Mapped[str] = mapped_column(String(50))
    modelo: Mapped[str] = mapped_column(String(100))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class RegistoProgresso(Base):
    """Fase 7: por agora só a estrutura."""

    __tablename__ = "registo_progresso"

    id: Mapped[int] = mapped_column(primary_key=True)
    utilizador_id: Mapped[int] = _dono()
    data: Mapped[date] = mapped_column(Date)
    valores: Mapped[dict[str, Any]] = mapped_column(Json)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
