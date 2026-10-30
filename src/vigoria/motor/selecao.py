"""Seleção dos exercícios permitidos em cada fase (determinístico, REGRAS_DOMINIO §6).

Recebe a Estrategia e o número da fase e devolve os exercícios permitidos, com que
motor/treino.py constrói o treino (Fase 4C: a LLM já não escolhe exercícios). Ordem dos
filtros: §6.6.
"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict

from vigoria.conteudo.carregar import (
    Equipamento,
    Exercicio,
    Grupo,
    Impacto,
    Nivel,
    carregar_exercicios,
)
from vigoria.modelos.estrategia import Estrategia, Restricoes
from vigoria.modelos.questionario import Equipamento as EquipamentoDeclarado
from vigoria.regras import textos
from vigoria.regras.regressao import resolver_regressao

# Só contam se o utilizador os declarar; cadeira, parede, bancada e degrau existem em casa.
EQUIPAMENTO_A_DECLARAR = {
    Equipamento.HALTERES: EquipamentoDeclarado.HALTERES,
    Equipamento.PASSADEIRA: EquipamentoDeclarado.PASSADEIRA,
    Equipamento.ELIPTICA: EquipamentoDeclarado.ELIPTICA,
}


class ExercicioPermitido(BaseModel):
    """Exercício que a LLM pode usar na fase, com os limites que o motor lhe impõe."""

    model_config = ConfigDict(frozen=True)

    id: str
    grupo: Grupo
    substitui: tuple[str, ...] = ()  # exercícios originais trocados por este (regressão)
    esforco_max: int | None = None  # 4 no fim da cadeia de regressões (§6.6)
    notas: tuple[str, ...] = ()


def selecionar_exercicios(
    estrategia: Estrategia, fase: int, biblioteca: Mapping[str, Exercicio] | None = None
) -> tuple[ExercicioPermitido, ...]:
    """Exercícios permitidos na fase, pela ordem da biblioteca e sem repetições."""
    if not estrategia.pode_gerar_plano:
        raise ValueError("A estratégia não permite gerar plano: não há exercícios a selecionar.")
    if not 1 <= fase <= 4:
        raise ValueError(f"Fase inválida: {fase} (de 1 a 4)")
    bib = carregar_exercicios() if biblioteca is None else biblioteca
    r = estrategia.restricoes

    permitidos: dict[str, ExercicioPermitido] = {}
    for exercicio in bib.values():
        if exercicio.fase_minima > fase or not _passa_filtros(exercicio, r):
            continue
        escolhido = _aplicar_regressoes(exercicio, r, bib)
        if escolhido is not None:
            _juntar(permitidos, escolhido)
    return tuple(permitidos.values())


def _passa_filtros(ex: Exercicio, r: Restricoes) -> bool:
    """Nível base, impacto, equipamento declarado e contraindicações (§6.3 e §6.6)."""
    if ex.nivel is not Nivel.BASE:
        return False
    if r.sem_impacto and ex.impacto is not Impacto.BAIXO:
        return False
    for equipamento in ex.equipamento:
        declarado = EQUIPAMENTO_A_DECLARAR.get(equipamento)
        if declarado is not None and declarado not in r.equipamento:
            return False
    return not set(ex.contraindicacoes) & set(r.contraindicacoes)


def _aplicar_regressoes(
    ex: Exercicio, r: Restricoes, bib: Mapping[str, Exercicio]
) -> ExercicioPermitido | None:
    """Troca o exercício pela regressão quando as restrições o pedem.

    A regressão pode ter fase_minima posterior (§6.6, ponto 4), mas tem de passar os
    restantes filtros; se não passar, o exercício sai da lista.
    """
    atual = ex
    if r.sem_flexao_tronco_com_carga and atual.flexao_tronco_carga:
        if atual.regressao is None:
            return None
        atual = bib[atual.regressao]
    if r.regressao_geral and atual.regressao is not None:
        atual = bib[atual.regressao]  # um passo na cadeia (§6.6)

    esforco_max = None
    notas: list[str] = []
    if r.zonas_regressao:
        regressao = resolver_regressao(atual.id, r.zonas_regressao, bib)
        atual = bib[regressao.exercicio_id]
        esforco_max = regressao.esforco_max
        if regressao.nota:
            notas.append(regressao.nota)
    if set(atual.zonas) & set(r.zonas_regressao_ligeira):
        atual = _regressao_ligeira(ex, atual, r, bib)
        if set(atual.zonas) & set(r.zonas_regressao_ligeira):
            notas.append(textos.AMPLITUDE_CONFORTAVEL)

    if atual is not ex and (
        not _passa_filtros(atual, r)
        or (r.sem_flexao_tronco_com_carga and atual.flexao_tronco_carga)
    ):
        return None
    if r.equilibrio_com_apoio and (atual.de_pe or atual.grupo is Grupo.EQUILIBRIO):
        notas.append(textos.APOIO_POR_PERTO)
    return ExercicioPermitido(
        id=atual.id,
        grupo=atual.grupo,
        substitui=() if atual is ex else (ex.id,),
        esforco_max=esforco_max,
        notas=tuple(dict.fromkeys(notas)),
    )


# A CONFIRMAR (revisão profissional): regra das zonas por gravidade, REGRAS_DOMINIO §6.6.
def _regressao_ligeira(
    ex: Exercicio, atual: Exercicio, r: Restricoes, bib: Mapping[str, Exercicio]
) -> Exercicio:
    """Limitação ligeira (§6.6): no máximo um passo, só nos exercícios de fase 2 a 4.

    Os de fase 1, o cardio e os já trocados por outra regra mantêm-se. O passo não é
    dado se a regressão solicitar uma zona da regra completa.
    """
    if atual is not ex or ex.fase_minima < 2 or ex.grupo is Grupo.CARDIO or ex.regressao is None:
        return atual
    passo = bib[ex.regressao]
    if set(passo.zonas) & set(r.zonas_regressao):
        return atual
    return passo


def _juntar(permitidos: dict[str, ExercicioPermitido], novo: ExercicioPermitido) -> None:
    """Junta duas entradas do mesmo exercício (por exemplo, original e regressão de outro)."""
    existente = permitidos.get(novo.id)
    if existente is None:
        permitidos[novo.id] = novo
        return
    limites = [e for e in (existente.esforco_max, novo.esforco_max) if e is not None]
    permitidos[novo.id] = existente.model_copy(
        update={
            "substitui": tuple(dict.fromkeys(existente.substitui + novo.substitui)),
            "esforco_max": min(limites) if limites else None,
            "notas": tuple(dict.fromkeys(existente.notas + novo.notas)),
        }
    )
