"""Modelos e carregamento do conteúdo editorial (REGRAS_DOMINIO §5 a §8).

Os YAML são copiados dos volumes 1 a 3; aqui só se valida a estrutura.
Só depende de modelos/zonas.py: regras/textos.py importa este módulo.
"""

from enum import StrEnum
from functools import cache
from importlib.resources import files
from typing import Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from vigoria.modelos.zonas import Zona


class ErroConteudo(Exception):
    """Ficheiro de conteúdo em falta ou inválido; a mensagem indica qual e porquê."""


class _Conteudo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Grupo(StrEnum):
    FORCA = "forca"
    CARDIO = "cardio"
    MOBILIDADE = "mobilidade"
    EQUILIBRIO = "equilibrio"


class Impacto(StrEnum):
    BAIXO = "baixo"
    MEDIO = "medio"
    ALTO = "alto"


class Nivel(StrEnum):
    BASE = "base"
    INTERMEDIO = "intermedio"
    AVANCADO = "avancado"


class Equipamento(StrEnum):
    """Equipamento necessário (os halteres opcionais ficam em `variante_halteres`)."""

    CADEIRA = "cadeira"
    PAREDE = "parede"
    BANCADA = "bancada"
    DEGRAU = "degrau"
    HALTERES = "halteres"
    PASSADEIRA = "passadeira"
    ELIPTICA = "eliptica"


class Exercicio(_Conteudo):
    """Um exercício da biblioteca (§6.1)."""

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    nome: str
    descricao: str
    grupo: Grupo
    fase_minima: int = Field(ge=1, le=4)
    equipamento: tuple[Equipamento, ...] = ()
    impacto: Impacto
    nivel: Nivel
    variante_halteres: str | None = None
    regressao: str | None = None
    contraindicacoes: tuple[str, ...] = ()
    zonas: tuple[Zona, ...] = ()
    flexao_tronco_carga: bool = False
    apoio_equilibrio: bool = False


class Intervalo(_Conteudo):
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordem(self) -> Self:
        if self.min > self.max:
            raise ValueError(f"mínimo {self.min} maior do que o máximo {self.max}")
        return self


class PosicaoFase(_Conteudo):
    """Uma linha da tabela da fase no Vol. 2, com o texto dessa fase."""

    id: str
    alternativas: tuple[str, ...] = ()
    series: int = Field(ge=1)
    repeticoes: str = Field(min_length=1)
    descanso_s: Intervalo
    como_executar: str
    com_halteres: str


class FocoAlimentar(_Conteudo):
    objetivo: str
    pontos: tuple[str, ...]


class Fase(_Conteudo):
    numero: int = Field(ge=1, le=4)
    nome: str
    semanas: Intervalo
    foco_treino: str
    foco_estrategico: str
    foco_alimentar: FocoAlimentar
    esforco: Intervalo
    exercicios: tuple[PosicaoFase, ...] = Field(min_length=1)


class EstruturaSessao(_Conteudo):
    """Estrutura padrão de cada sessão (Vol. 2, versão-base de §6.3)."""

    aquecimento: str
    bloco_principal: str
    cardio_finalizador: str
    retorno_calma: str


class Programa(_Conteudo):
    estrutura_sessao: EstruturaSessao
    fases: tuple[Fase, ...] = Field(min_length=4, max_length=4)


class _Biblioteca(_Conteudo):
    exercicios: tuple[Exercicio, ...] = Field(min_length=1)


# ---------------------------------------------------------------- avisos.yaml (§7 e §8)


class Rotulos(_Conteudo):
    intensidade: dict[str, str]
    zonas_limitacao: dict[str, str]


class ListaNegra(_Conteudo):
    termos: tuple[str, ...] = Field(min_length=1)  # procurados à letra pelo código
    ideias: tuple[str, ...] = ()  # para a revisão crítica pela LLM


class Avisos(_Conteudo):
    obrigatorios: tuple[str, ...] = Field(min_length=1)
    textos: dict[str, str]
    rotulos: Rotulos
    lista_negra: ListaNegra
    brasileirismos: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _ids_validos(self) -> Self:
        for id_ in self.textos:
            if not id_.isascii() or not id_.isidentifier() or id_ != id_.lower():
                raise ValueError(f"id inválido: {id_!r} (minúsculas, sem acentos)")
        em_falta = [id_ for id_ in self.obrigatorios if id_ not in self.textos]
        if em_falta:
            raise ValueError(f"obrigatórios sem texto: {', '.join(em_falta)}")
        return self


# ---------------------------------------------------------------- alimentacao.yaml (Vol. 3)


class Principio(_Conteudo):
    titulo: str
    texto: tuple[str, ...] = Field(min_length=1)
    exemplos: tuple[str, ...] = ()
    nota: str | None = None


class Principios(_Conteudo):
    introducao: str
    lista: tuple[Principio, ...] = Field(min_length=1)


class ElementoRefeicao(_Conteudo):
    titulo: str
    texto: str


class RefeicaoSimples(_Conteudo):
    introducao: tuple[str, ...]
    elementos: tuple[ElementoRefeicao, ...] = Field(min_length=1)
    notas: tuple[str, ...]
    exemplos: tuple[str, ...]
    conclusao: tuple[str, ...]


class Verificacao(_Conteudo):
    pergunta: str
    texto: str


class Ajuste(_Conteudo):
    introducao: tuple[str, ...]
    exemplos: tuple[str, ...] = Field(min_length=1)
    conclusao: tuple[str, ...]


class EvolucaoAbranda(_Conteudo):
    introducao: tuple[str, ...]
    verificar: tuple[Verificacao, ...] = Field(min_length=1)
    ajustar: Ajuste


class Alimentacao(_Conteudo):
    principios: Principios
    refeicao_simples: RefeicaoSimples
    evolucao_abranda: EvolucaoAbranda


# ---------------------------------------------------------------- Carregamento


class Conteudo(_Conteudo):
    """Todo o conteúdo editorial, validado e com as referências cruzadas confirmadas."""

    exercicios: dict[str, Exercicio]
    programa: Programa
    alimentacao: Alimentacao
    avisos: Avisos


def _carregar[M: BaseModel](nome: str, modelo: type[M]) -> M:
    """Lê e valida um YAML; qualquer falha vira ErroConteudo com o nome do ficheiro."""
    try:
        texto = files("vigoria.conteudo").joinpath(nome).read_text(encoding="utf-8")
        return modelo.model_validate(yaml.safe_load(texto))
    except OSError as erro:
        raise ErroConteudo(f"conteudo/{nome}: não foi possível ler o ficheiro ({erro})") from erro
    except yaml.YAMLError as erro:
        raise ErroConteudo(f"conteudo/{nome}: YAML inválido\n{erro}") from erro
    except ValidationError as erro:
        raise ErroConteudo(f"conteudo/{nome}: estrutura inválida\n{erro}") from erro


@cache
def carregar_exercicios() -> dict[str, Exercicio]:
    """Biblioteca de exercícios, indexada pelo id. Falha se houver ids repetidos."""
    biblioteca: dict[str, Exercicio] = {}
    for exercicio in _carregar("exercicios.yaml", _Biblioteca).exercicios:
        if exercicio.id in biblioteca:
            raise ErroConteudo(f"conteudo/exercicios.yaml: exercício repetido: {exercicio.id}")
        biblioteca[exercicio.id] = exercicio
    return biblioteca


@cache
def carregar_programa() -> Programa:
    """Estrutura da sessão e as 4 fases."""
    return _carregar("fases.yaml", Programa)


def carregar_fases() -> tuple[Fase, ...]:
    """As 4 fases, por ordem."""
    return carregar_programa().fases


@cache
def carregar_avisos() -> Avisos:
    """Textos fixos, rótulos, lista negra e brasileirismos."""
    return _carregar("avisos.yaml", Avisos)


@cache
def carregar_alimentacao() -> Alimentacao:
    """Princípios, refeição simples e «quando a evolução abranda» (Vol. 3)."""
    return _carregar("alimentacao.yaml", Alimentacao)


def carregar_conteudo() -> Conteudo:
    """Carrega os quatro ficheiros e confirma as referências entre eles.

    Falha com ErroConteudo (ficheiro e motivo) ao primeiro problema encontrado.
    """
    exercicios = carregar_exercicios()
    programa = carregar_programa()
    for exercicio in exercicios.values():
        if exercicio.regressao is not None and exercicio.regressao not in exercicios:
            raise ErroConteudo(
                f"conteudo/exercicios.yaml: a regressão de {exercicio.id} "
                f"({exercicio.regressao}) não existe na biblioteca"
            )
    for fase in programa.fases:
        for posicao in fase.exercicios:
            for id_ in (posicao.id, *posicao.alternativas):
                if id_ not in exercicios:
                    raise ErroConteudo(
                        f"conteudo/fases.yaml: a fase {fase.numero} usa {id_}, "
                        "que não existe em exercicios.yaml"
                    )
    return Conteudo(
        exercicios=exercicios,
        programa=programa,
        alimentacao=carregar_alimentacao(),
        avisos=carregar_avisos(),
    )
