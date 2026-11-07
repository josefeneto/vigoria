"""Tabelas da base de dados (SQLAlchemy 2.x).

Cada linha de dados pessoais pertence a um utilizador; apagar o utilizador apaga tudo o que
é dele (ON DELETE CASCADE). O utilizador é identificado pelo `sub` do Auth0, nunca pelo email.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    true,
)
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
    # Preferências do acompanhamento: vêm do questionário de cada plano novo, alteráveis na conta.
    acompanhamento_ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    frequencia_registo: Mapped[str] = mapped_column(
        String(20), default="semanal", server_default="semanal"
    )
    lembretes_email: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())


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
    """Um registo por semana do plano; apagar o plano apaga os registos dele."""

    __tablename__ = "registo_progresso"
    __table_args__ = (UniqueConstraint("plano_id", "semana", name="uq_registo_plano_semana"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    utilizador_id: Mapped[int] = _dono()
    plano_id: Mapped[int] = mapped_column(ForeignKey("plano.id", ondelete="CASCADE"), index=True)
    semana: Mapped[int] = mapped_column(Integer)  # semana 1 = data de criação do plano
    data: Mapped[date] = mapped_column(Date)
    valores: Mapped[dict[str, Any]] = mapped_column(Json)  # ValoresRegisto em JSON
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=agora, onupdate=agora
    )


class LembreteEnviado(Base):
    """Um lembrete por email já enviado: nunca se repete o mesmo número no mesmo período."""

    __tablename__ = "lembrete_enviado"
    __table_args__ = (
        UniqueConstraint(
            "plano_id", "semana_inicio", "semana_fim", "numero", name="uq_lembrete_periodo_numero"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    utilizador_id: Mapped[int] = _dono()
    plano_id: Mapped[int] = mapped_column(ForeignKey("plano.id", ondelete="CASCADE"), index=True)
    semana_inicio: Mapped[int] = mapped_column(Integer)
    semana_fim: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(Integer)  # 1 ou 2
    enviado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
