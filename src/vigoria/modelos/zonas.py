"""Zonas articulares (REGRAS_DOMINIO §1.1 e §6.6), sem dependências para evitar ciclos."""

from enum import StrEnum


class Zona(StrEnum):
    """Zonas com regressão (e exclusão dos exercícios que as tenham em contraindicações)."""

    JOELHOS = "joelhos"
    ANCAS = "ancas"
    OMBROS = "ombros"
    COLUNA = "coluna"
