"""Palavras aceites pela ortografia (motor/ortografia.py, `ortografia_aceites`)."""

import pytest

from vigoria.motor.ortografia import _conhecida, vocabulario_aceite


@pytest.mark.parametrize("palavra", ["oleaginosos", "oleaginosas", "tónus", "lanches"])
def test_palavras_da_comparacao_aceites(palavra: str) -> None:
    """Comparação de 12/11/2026: «oleaginosos» faltava no dicionário pt_PT."""
    assert _conhecida(palavra, vocabulario_aceite())


def test_tonus_do_brasil_continua_desconhecido() -> None:
    assert not _conhecida("tônus", vocabulario_aceite())  # a voz corrige-o para «tónus»
