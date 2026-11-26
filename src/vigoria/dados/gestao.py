"""Números para a página Gestão (25/11/2026): contagens por dia e lista de contas.

Exceção consciente à regra de repositorios.py (tudo filtrado por `utilizador_id`): aqui leem-se
totais de todos e a lista de emails, só para as contas de administração (VIGORIA_ADMINS;
paginas/gestao.py verifica-o antes de chamar). Nada de respostas ao questionário, planos
ou registos de progresso: só contagens, emails, método de entrada e datas.

As contagens (`contar`) não guardam quem fez a ação: não se apagam com as contas.
Desde 26/11/2026 também os lembretes: enviados, falhados (o Brevo recusou), cancelados
pela ligação do email e cada execução do envio diário (para saber quando correu).
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as insert_postgresql
from sqlalchemy.dialects.sqlite import insert as insert_sqlite
from sqlalchemy.orm import Session

from vigoria.dados.tabelas import ContagemDiaria, PlanoGuardado, Utilizador, agora
from vigoria.regras.progresso import dia_em_lisboa


class TipoContagem(StrEnum):
    CONTA_CRIADA = "conta_criada"
    PLANO_GERADO = "plano_gerado"
    PDF_DESCARREGADO = "pdf_descarregado"
    DADOS_DESCARREGADOS = "dados_descarregados"
    LEMBRETE_ENVIADO = "lembrete_enviado"
    LEMBRETE_FALHADO = "lembrete_falhado"
    LEMBRETES_CANCELADOS = "lembretes_cancelados"
    ENVIO_DIARIO = "envio_diario"  # uma por execução do cron (não é um cartão)


PERIODOS_DIAS = (7, 30)
NUMEROS_GERAIS = (
    TipoContagem.CONTA_CRIADA,
    TipoContagem.PLANO_GERADO,
    TipoContagem.PDF_DESCARREGADO,
    TipoContagem.DADOS_DESCARREGADOS,
)
NUMEROS_LEMBRETES = (
    TipoContagem.LEMBRETE_ENVIADO,
    TipoContagem.LEMBRETE_FALHADO,
    TipoContagem.LEMBRETES_CANCELADOS,
)


def contar(s: Session, tipo: TipoContagem, quando: datetime | None = None) -> None:
    """Mais um no dia (de Lisboa) de `quando`; sem `quando`, agora."""
    valores = {"dia": dia_em_lisboa(quando or agora()), "tipo": tipo.value, "total": 1}
    inserir = insert_postgresql if s.get_bind().dialect.name == "postgresql" else insert_sqlite
    pedido = inserir(ContagemDiaria).values(**valores)
    s.execute(
        pedido.on_conflict_do_update(
            index_elements=["dia", "tipo"], set_={"total": ContagemDiaria.total + 1}
        )
    )


@dataclass(frozen=True)
class Numeros:
    """Um número: total acumulado e nos últimos 7 e 30 dias (hoje incluído)."""

    total: int
    ultimos: dict[int, int]


@dataclass(frozen=True)
class Resumo:
    contas_ativas: int  # contas que existem hoje (as apagadas já não contam)
    com_plano: int  # contas com pelo menos um plano: o questionário foi até ao fim
    lembretes_ligados: int  # acompanhamento e lembretes ligados, com um plano
    ultimo_envio_diario: date | None  # dia (Lisboa) da última execução do cron
    contagens: dict[TipoContagem, Numeros]  # NUMEROS_GERAIS e NUMEROS_LEMBRETES


def _numeros(s: Session, tipo: TipoContagem, hoje: date) -> Numeros:
    def soma(desde: date | None) -> int:
        pedido = select(func.coalesce(func.sum(ContagemDiaria.total), 0)).where(
            ContagemDiaria.tipo == tipo.value
        )
        if desde is not None:
            pedido = pedido.where(ContagemDiaria.dia >= desde)
        return int(s.scalar(pedido) or 0)

    return Numeros(
        total=soma(None),
        ultimos={n: soma(hoje - timedelta(days=n - 1)) for n in PERIODOS_DIAS},
    )


def resumo(s: Session, hoje: date) -> Resumo:
    contas = int(s.scalar(select(func.count()).select_from(Utilizador)) or 0)
    com_plano = int(s.scalar(select(func.count(func.distinct(PlanoGuardado.utilizador_id)))) or 0)
    ligados = s.scalar(
        select(func.count(func.distinct(Utilizador.id)))
        .join(PlanoGuardado, PlanoGuardado.utilizador_id == Utilizador.id)
        .where(Utilizador.acompanhamento_ativo, Utilizador.lembretes_email)
    )
    ultimo = s.scalar(
        select(func.max(ContagemDiaria.dia)).where(
            ContagemDiaria.tipo == TipoContagem.ENVIO_DIARIO.value
        )
    )
    return Resumo(
        contas_ativas=contas,
        com_plano=com_plano,
        lembretes_ligados=int(ligados or 0),
        ultimo_envio_diario=ultimo,
        contagens={tipo: _numeros(s, tipo, hoje) for tipo in NUMEROS_GERAIS + NUMEROS_LEMBRETES},
    )


@dataclass(frozen=True)
class Conta:
    email: str
    fornecedor: str  # «google-oauth2», «auth0»
    criada_em: date  # dia de Lisboa
    planos: int


def contas(s: Session) -> list[Conta]:
    """Todas as contas, da mais recente para a mais antiga."""
    planos = (
        select(PlanoGuardado.utilizador_id, func.count().label("n"))
        .group_by(PlanoGuardado.utilizador_id)
        .subquery()
    )
    linhas = s.execute(
        select(
            Utilizador.email,
            Utilizador.fornecedor,
            Utilizador.criado_em,
            func.coalesce(planos.c.n, 0),
        )
        .outerjoin(planos, planos.c.utilizador_id == Utilizador.id)
        .order_by(Utilizador.criado_em.desc(), Utilizador.id.desc())
    )
    return [
        Conta(email=e, fornecedor=f, criada_em=dia_em_lisboa(c), planos=int(n))
        for e, f, c, n in linhas
    ]


def contas_csv(lista: list[Conta], cabecalho: tuple[str, str, str, str]) -> str:
    """CSV com «;» (o Excel em português abre-o em colunas) e BOM para os acentos."""
    saida = io.StringIO()
    escrita = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escrita.writerow(cabecalho)
    for c in lista:
        escrita.writerow((c.email, c.fornecedor, c.criada_em.strftime("%d/%m/%Y"), c.planos))
    return "﻿" + saida.getvalue()
