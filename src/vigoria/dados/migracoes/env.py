"""Ambiente do Alembic. A app passa a ligação (bd.migrar); na linha de comandos, usa-se o
DATABASE_URL da configuração (python -m alembic upgrade head)."""

from alembic import context

from vigoria.config import obter_configuracao
from vigoria.dados.bd import criar_motor
from vigoria.dados.tabelas import Base

alvo = Base.metadata


def _correr(ligacao: object) -> None:
    context.configure(connection=ligacao, target_metadata=alvo, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


ligacao = context.config.attributes.get("connection")
if ligacao is not None:
    _correr(ligacao)
else:
    with criar_motor(obter_configuracao().database_url).begin() as nova:
        _correr(nova)
