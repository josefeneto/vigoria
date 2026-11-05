"""Leitura e gravação dos dados de cada utilizador.

Todas as funções de dados pessoais recebem o `utilizador_id` e filtram por ele: um
utilizador nunca lê nem altera dados de outro (tests/test_dados.py). As funções não fazem
commit: quem chama abre a transação (`with fabrica.begin() as s:`). Nada aqui é registado
em logs.
"""

from datetime import date, datetime
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
from vigoria.modelos.questionario import FrequenciaRegisto, Questionario
from vigoria.modelos.registo import ValoresRegisto
from vigoria.regras.progresso import inicio_do_plano, periodo_ocupado, semana_do_plano

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
    peso_kg: float | None = None  # do questionário do plano (progresso: ponto de partida)


class ResumoPlano(BaseModel):
    """Uma linha da lista de planos anteriores."""

    model_config = ConfigDict(frozen=True)

    id: int
    criado_em: datetime


class RegistoDaConta(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    plano_id: int
    semana: int
    data: date
    valores: ValoresRegisto


class Preferencias(BaseModel):
    """O acompanhamento desta conta (questionário, passo 6; alterável na conta)."""

    model_config = ConfigDict(frozen=True)

    ativo: bool = True
    frequencia: FrequenciaRegisto = FrequenciaRegisto.SEMANAL


class PlanoDeOutro(LookupError):
    """O questionário ou o plano indicado não pertence a este utilizador."""


class DataFutura(ValueError):
    """A data do registo é posterior a hoje."""


class DataAntesDoPlano(ValueError):
    """A data do registo é anterior ao início do plano."""


class PeriodoOcupado(ValueError):
    """Já há um registo neste período (um por período). Traz a semana da data pedida."""

    def __init__(self, semana: int) -> None:
        super().__init__(semana)
        self.semana = semana


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
    for tabela in (RegistoProgresso, PlanoGuardado, QuestionarioGuardado, Consentimento):
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
    questionario = s.scalar(
        select(QuestionarioGuardado).where(
            QuestionarioGuardado.id == questionario_id,
            QuestionarioGuardado.utilizador_id == utilizador_id,
        )
    )
    if questionario is None:
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
    utilizador = s.get(Utilizador, utilizador_id)
    if utilizador is not None:  # o plano novo traz a escolha feita no questionário
        utilizador.acompanhamento_ativo = questionario.respostas.get("acompanhamento_ativo", True)
        utilizador.frequencia_registo = questionario.respostas.get(
            "frequencia_registo", FrequenciaRegisto.SEMANAL.value
        )
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
    """Apaga um plano da pessoa e os registos dele; False se não existir ou for de outro.

    O questionário que lhe deu origem fica: serve para preencher o próximo.
    """
    s.execute(
        delete(RegistoProgresso).where(
            RegistoProgresso.plano_id == plano_id, RegistoProgresso.utilizador_id == utilizador_id
        )
    )
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
    peso = respostas.get("peso_kg") if isinstance(respostas, dict) else None
    return PlanoDaConta(
        id=linha.id,
        criado_em=linha.criado_em,
        plano=Plano.model_validate(linha.conteudo),
        estrategia=Estrategia.model_validate(linha.estrategia),
        idade=idade if isinstance(idade, int) else None,
        peso_kg=float(peso) if isinstance(peso, int | float) else None,
    )


# ---------------------------------------------------------------- Acompanhamento


def obter_preferencias(s: Session, utilizador_id: int) -> Preferencias:
    utilizador = s.get(Utilizador, utilizador_id)
    if utilizador is None:
        return Preferencias()
    return Preferencias(
        ativo=utilizador.acompanhamento_ativo,
        frequencia=FrequenciaRegisto(utilizador.frequencia_registo),
    )


def guardar_preferencias(s: Session, utilizador_id: int, preferencias: Preferencias) -> None:
    utilizador = s.get(Utilizador, utilizador_id)
    if utilizador is not None:
        utilizador.acompanhamento_ativo = preferencias.ativo
        utilizador.frequencia_registo = preferencias.frequencia.value
        s.flush()


def _para_registo(linha: RegistoProgresso) -> RegistoDaConta:
    return RegistoDaConta(
        id=linha.id,
        plano_id=linha.plano_id,
        semana=linha.semana,
        data=linha.data,
        valores=ValoresRegisto.model_validate(linha.valores),
    )


def _semana_valida(inicio: date, dia: date, hoje: date) -> int:
    if dia > hoje:
        raise DataFutura(dia)
    if dia < inicio:
        raise DataAntesDoPlano(dia)
    return semana_do_plano(inicio, dia)


def _criado_em(s: Session, utilizador_id: int, plano_id: int) -> datetime | None:
    return s.scalar(
        select(PlanoGuardado.criado_em).where(
            PlanoGuardado.id == plano_id, PlanoGuardado.utilizador_id == utilizador_id
        )
    )


def _semanas_do_plano(s: Session, utilizador_id: int, plano_id: int) -> list[int]:
    return list(
        s.scalars(
            select(RegistoProgresso.semana).where(
                RegistoProgresso.plano_id == plano_id,
                RegistoProgresso.utilizador_id == utilizador_id,
            )
        )
    )


def listar_registos(s: Session, utilizador_id: int, plano_id: int) -> list[RegistoDaConta]:
    """Os registos de um plano, da semana mais antiga para a mais recente."""
    linhas = s.scalars(
        select(RegistoProgresso)
        .where(
            RegistoProgresso.plano_id == plano_id,
            RegistoProgresso.utilizador_id == utilizador_id,
        )
        .order_by(RegistoProgresso.semana)
    )
    return [_para_registo(linha) for linha in linhas]


def guardar_registo(
    s: Session,
    utilizador_id: int,
    plano_id: int,
    dia: date,
    valores: ValoresRegisto,
    hoje: date,
) -> RegistoDaConta:
    """Um registo novo, ligado à semana do plano. Só nos planos da própria pessoa."""
    criado_em = _criado_em(s, utilizador_id, plano_id)
    if criado_em is None:
        raise PlanoDeOutro(plano_id)
    semana = _semana_valida(inicio_do_plano(criado_em), dia, hoje)
    frequencia = obter_preferencias(s, utilizador_id).frequencia
    if periodo_ocupado(semana, frequencia, _semanas_do_plano(s, utilizador_id, plano_id)):
        raise PeriodoOcupado(semana)
    linha = RegistoProgresso(
        utilizador_id=utilizador_id,
        plano_id=plano_id,
        semana=semana,
        data=dia,
        valores=valores.model_dump(mode="json", exclude_none=True),
    )
    s.add(linha)
    s.flush()
    return _para_registo(linha)


def atualizar_registo(
    s: Session,
    utilizador_id: int,
    registo_id: int,
    dia: date,
    valores: ValoresRegisto,
    hoje: date,
) -> RegistoDaConta | None:
    """Retifica um registo; None se não existir ou for de outro utilizador."""
    linha = s.scalar(
        select(RegistoProgresso).where(
            RegistoProgresso.id == registo_id, RegistoProgresso.utilizador_id == utilizador_id
        )
    )
    if linha is None:
        return None
    criado_em = _criado_em(s, utilizador_id, linha.plano_id)
    if criado_em is None:
        return None
    semana = _semana_valida(inicio_do_plano(criado_em), dia, hoje)
    if semana != linha.semana:  # na mesma semana, retificar é sempre possível
        semanas = _semanas_do_plano(s, utilizador_id, linha.plano_id)
        outras = [x for x in semanas if x != linha.semana]
        frequencia = obter_preferencias(s, utilizador_id).frequencia
        if periodo_ocupado(semana, frequencia, outras):
            raise PeriodoOcupado(semana)
    linha.semana = semana
    linha.data = dia
    linha.valores = valores.model_dump(mode="json", exclude_none=True)
    s.flush()
    return _para_registo(linha)


def apagar_registo(s: Session, utilizador_id: int, registo_id: int) -> bool:
    """False se não existir ou for de outro utilizador."""
    apagados = s.execute(
        delete(RegistoProgresso).where(
            RegistoProgresso.id == registo_id, RegistoProgresso.utilizador_id == utilizador_id
        )
    ).rowcount
    return apagados == 1


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
            {
                "plano_id": r.plano_id,
                "semana": r.semana,
                "data": r.data.isoformat(),
                "valores": r.valores,
                "criado_em": r.criado_em.isoformat(),
                "alterado_em": r.alterado_em.isoformat(),
            }
            for r in todas(RegistoProgresso)
        ],
    }
