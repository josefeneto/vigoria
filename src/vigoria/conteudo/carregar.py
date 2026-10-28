"""Modelos e carregamento do conteúdo editorial (REGRAS_DOMINIO §5 e §6).

Os YAML são copiados dos volumes 1 a 3; aqui só se valida a estrutura.
"""

from enum import StrEnum
from functools import cache
from importlib.resources import files
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from vigoria.modelos.estrategia import Zona


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


def _ler_yaml(nome: str) -> Any:
    texto = files("vigoria.conteudo").joinpath(nome).read_text(encoding="utf-8")
    return yaml.safe_load(texto)


@cache
def carregar_exercicios() -> dict[str, Exercicio]:
    """Biblioteca de exercícios, indexada pelo id. Falha se houver ids repetidos."""
    biblioteca: dict[str, Exercicio] = {}
    for dados in _ler_yaml("exercicios.yaml")["exercicios"]:
        exercicio = Exercicio.model_validate(dados)
        if exercicio.id in biblioteca:
            raise ValueError(f"Exercício repetido: {exercicio.id}")
        biblioteca[exercicio.id] = exercicio
    return biblioteca


@cache
def carregar_programa() -> Programa:
    """Estrutura da sessão e as 4 fases."""
    return Programa.model_validate(_ler_yaml("fases.yaml"))


def carregar_fases() -> tuple[Fase, ...]:
    """As 4 fases, por ordem."""
    return carregar_programa().fases
