"""Um registo de progresso (Fase 7, REGRAS_DOMINIO §9): todos os campos são opcionais.

As observações são texto livre da pessoa: o motor nunca as interpreta e nunca vão à LLM.
"""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

OBSERVACOES_MAX = 300


class Comparacao(StrEnum):
    """Força e mobilidade/equilíbrio, face ao registo anterior (§9, R6). Não gera alertas."""

    MAIS_DIFICIL = "mais_dificil"
    IGUAL = "igual"
    MAIS_FACIL = "mais_facil"


class RegistoVazio(ValueError):
    """Um registo sem nenhum campo preenchido."""


class ValoresRegisto(BaseModel):
    """Os valores de um registo, com os mesmos intervalos do questionário."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    peso_kg: float | None = Field(default=None, ge=35, le=250)
    cintura_cm: float | None = Field(default=None, ge=50, le=200)
    sessoes: int | None = Field(default=None, ge=0, le=14)
    cardio_min: int | None = Field(default=None, ge=0, le=600)
    energia: int | None = Field(default=None, ge=0, le=10)
    esforco: int | None = Field(default=None, ge=0, le=10)
    sono_h: float | None = Field(default=None, ge=3, le=12, multiple_of=0.5)
    forca: Comparacao | None = None
    mobilidade_equilibrio: Comparacao | None = None
    observacoes: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=OBSERVACOES_MAX)] | None
    ) = None

    @model_validator(mode="after")
    def _pelo_menos_um(self) -> Self:
        if self.observacoes == "":
            object.__setattr__(self, "observacoes", None)
        if all(getattr(self, campo) is None for campo in type(self).model_fields):
            raise RegistoVazio("preencha pelo menos um campo")
        return self
