"""Leitura e gravação dos dados de cada utilizador.

Todas as funções de dados pessoais recebem o `utilizador_id` e filtram por ele: um
utilizador nunca lê nem altera dados de outro (tests/test_dados.py). As funções não fazem
commit: quem chama abre a transação (`with fabrica.begin() as s:`). Nada aqui é registado
em logs.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from vigoria.contas.entrada import Identidade
from vigoria.dados.tabelas import (
    Consentimento,
    PlanoGuardado,
    QuestionarioGuardado,
    RegistoProgresso,
    Utilizador,
)
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario

TIPOS_CONSENTIMENTO = ("termos", "saude", "maior_idade")


class Recusa(StrEnum):
    EMAIL_POR_VERIFICAR = "email_por_verificar"
    EMAIL_NOUTRO_METODO = "email_noutro_metodo"
    NAO_CONVIDADO = "nao_convidado"  # fora da lista de convidados (decidido em paginas/sessao.py)


class PlanoDaConta(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    criado_em: datetime
    plano: Plano
    estrategia: Estrategia
    idade: int | None = None  # do questionário do plano (manutenção: OMS só com ≥ 65)


class ResumoPlano(BaseModel):
    """Uma linha da lista de planos anteriores."""

    model_config = ConfigDict(frozen=True)

    id: int
    criado_em: datetime


class PlanoDeOutro(LookupError):
    """O questionário indicado não pertence a este utilizador."""


# ---------------------------------------------------------------- Conta


def entrar(s: Session, identidade: Identidade) -> Utilizador | Recusa:
    """O utilizador do `sub`, criado no primeiro login. Sem juntar contas pelo email."""
    if not identidade.email_verificado:
        return Recusa.EMAIL_POR_VERIFICAR
    utilizador = s.scalar(select(Utilizador).where(Utilizador.sub == identidade.sub))
    outro = s.scalar(
        select(Utilizador.id).where(
            Utilizador.email == identidade.email, Utilizador.sub != identidade.sub
        )
    )
    if utilizador is None:
        if outro is not None:
            return Recusa.EMAIL_NOUTRO_METODO
        utilizador = Utilizador(
            sub=identidade.sub, fornecedor=identidade.fornecedor, email=identidade.email
        )
        s.add(utilizador)
        s.flush()
    elif utilizador.email != identidade.email and outro is None:
        utilizador.email = identidade.email  # mudou o email no Auth0
    return utilizador


def apagar_utilizador(s: Session, utilizador_id: int) -> str | None:
    """Apaga a conta e todos os dados dela. Devolve o `sub` (para apagar no Auth0)."""
    utilizador = s.get(Utilizador, utilizador_id)
    if utilizador is None:
        return None
    sub = utilizador.sub
    # Explícito, além do ON DELETE CASCADE: não depende da configuração da base de dados.
    for tabela in (PlanoGuardado, QuestionarioGuardado, Consentimento, RegistoProgresso):
        s.execute(delete(tabela).where(tabela.utilizador_id == utilizador_id))
    s.delete(utilizador)
    s.flush()
    return sub


# ---------------------------------------------------------------- Questionário e consentimento


def guardar_consentimentos(s: Session, utilizador_id: int, versao_texto: str) -> None:
    """Os três consentimentos do passo 0, com a versão do texto que a pessoa viu."""
    s.add_all(
        Consentimento(utilizador_id=utilizador_id, tipo=tipo, versao_texto=versao_texto)
        for tipo in TIPOS_CONSENTIMENTO
    )
    s.flush()


def guardar_questionario(s: Session, utilizador_id: int, q: Questionario) -> int:
    linha = QuestionarioGuardado(utilizador_id=utilizador_id, respostas=q.model_dump(mode="json"))
    s.add(linha)
    s.flush()
    return linha.id


def ultimo_questionario(s: Session, utilizador_id: int) -> Questionario | None:
    respostas = s.scalar(
        select(QuestionarioGuardado.respostas)
        .where(QuestionarioGuardado.utilizador_id == utilizador_id)
        .order_by(QuestionarioGuardado.id.desc())
        .limit(1)
    )
    return None if respostas is None else Questionario.model_validate(respostas)


# ---------------------------------------------------------------- Planos


def guardar_plano(
    s: Session,
    utilizador_id: int,
    questionario_id: int,
    plano: Plano,
    estrategia: Estrategia,
    modelo: str,
) -> PlanoDaConta:
    dono = s.scalar(
        select(QuestionarioGuardado.utilizador_id).where(QuestionarioGuardado.id == questionario_id)
    )
    if dono != utilizador_id:
        raise PlanoDeOutro(questionario_id)
    linha = PlanoGuardado(
        utilizador_id=utilizador_id,
        questionario_id=questionario_id,
        conteudo=plano.model_dump(mode="json"),
        estrategia=estrategia.model_dump(mode="json"),
        versao_prompt=plano.versao_prompt,
        provedor=plano.provedor,
        modelo=modelo,
    )
    s.add(linha)
    s.flush()
    return _plano_da_conta(s, linha)


def listar_planos(s: Session, utilizador_id: int) -> list[ResumoPlano]:
    """Do mais recente para o mais antigo."""
    linhas = s.execute(
        select(PlanoGuardado.id, PlanoGuardado.criado_em)
        .where(PlanoGuardado.utilizador_id == utilizador_id)
        .order_by(PlanoGuardado.id.desc())
    )
    return [ResumoPlano(id=i, criado_em=c) for i, c in linhas]


def obter_plano(s: Session, utilizador_id: int, plano_id: int) -> PlanoDaConta | None:
    """None também se o plano existir mas for de outro utilizador."""
    linha = s.scalar(
        select(PlanoGuardado).where(
            PlanoGuardado.id == plano_id, PlanoGuardado.utilizador_id == utilizador_id
        )
    )
    return None if linha is None else _plano_da_conta(s, linha)


def ultimo_plano(s: Session, utilizador_id: int) -> PlanoDaConta | None:
    linha = s.scalar(
        select(PlanoGuardado)
        .where(PlanoGuardado.utilizador_id == utilizador_id)
        .order_by(PlanoGuardado.id.desc())
        .limit(1)
    )
    return None if linha is None else _plano_da_conta(s, linha)


def apagar_plano(s: Session, utilizador_id: int, plano_id: int) -> bool:
    """Apaga um plano da pessoa; False se não existir ou for de outro utilizador.

    O questionário que lhe deu origem fica: serve para preencher o próximo.
    """
    apagados = s.execute(
        delete(PlanoGuardado).where(
            PlanoGuardado.id == plano_id, PlanoGuardado.utilizador_id == utilizador_id
        )
    ).rowcount
    return apagados == 1


def _plano_da_conta(s: Session, linha: PlanoGuardado) -> PlanoDaConta:
    # O questionário é do mesmo utilizador (guardar_plano confirma-o).
    respostas = s.scalar(
        select(QuestionarioGuardado.respostas).where(
            QuestionarioGuardado.id == linha.questionario_id,
            QuestionarioGuardado.utilizador_id == linha.utilizador_id,
        )
    )
    idade = respostas.get("idade") if isinstance(respostas, dict) else None
    return PlanoDaConta(
        id=linha.id,
        criado_em=linha.criado_em,
        plano=Plano.model_validate(linha.conteudo),
        estrategia=Estrategia.model_validate(linha.estrategia),
        idade=idade if isinstance(idade, int) else None,
    )


# ---------------------------------------------------------------- Exportação (RGPD)


def exportar_dados(s: Session, utilizador_id: int) -> dict[str, Any]:
    """Todos os dados guardados deste utilizador, prontos para JSON (direito de acesso)."""
    utilizador = s.get(Utilizador, utilizador_id)
    if utilizador is None:
        return {}

    def todas[T: (Consentimento, QuestionarioGuardado, PlanoGuardado, RegistoProgresso)](
        tabela: type[T],
    ) -> list[T]:
        return list(
            s.scalars(
                select(tabela).where(tabela.utilizador_id == utilizador_id).order_by(tabela.id)
            )
        )

    return {
        "conta": {
            "email": utilizador.email,
            "metodo_de_entrada": utilizador.fornecedor,
            "criada_em": utilizador.criado_em.isoformat(),
        },
        "consentimentos": [
            {"tipo": c.tipo, "versao_texto": c.versao_texto, "data": c.data.isoformat()}
            for c in todas(Consentimento)
        ],
        "questionarios": [
            {"id": q.id, "criado_em": q.criado_em.isoformat(), "respostas": q.respostas}
            for q in todas(QuestionarioGuardado)
        ],
        "planos": [
            {
                "id": p.id,
                "questionario_id": p.questionario_id,
                "criado_em": p.criado_em.isoformat(),
                "versao_prompt": p.versao_prompt,
                "provedor": p.provedor,
                "modelo": p.modelo,
                "plano": p.conteudo,
                "estrategia": p.estrategia,
            }
            for p in todas(PlanoGuardado)
        ],
        "registos_progresso": [
            {"data": r.data.isoformat(), "valores": r.valores} for r in todas(RegistoProgresso)
        ],
    }
