"""Ortografia PT-EU (AO90) do texto escrito pela LLM, com o dicionário Hunspell pt_PT.

Dicionário: LibreOffice/Natura (Universidade do Minho), em conteudo/dicionario/
(licença GPL/LGPL/MPL, ver README_pt_PT.txt), lido pelo spylls (só Python).
Por agora só avisa (decisão de 30/10/2026): as palavras desconhecidas aparecem na CLI
e não obrigam a regenerar. Aceita o vocabulário dos YAML editoriais e as palavras de
`ortografia_aceites` (avisos.yaml).
"""

import re
from collections.abc import Iterable, Iterator
from functools import cache
from pathlib import Path
from typing import Any

from spylls.hunspell import Dictionary

from vigoria.conteudo.carregar import (
    carregar_alimentacao,
    carregar_avisos,
    carregar_exercicios,
    carregar_programa,
)
from vigoria.modelos.plano import Plano
from vigoria.motor.voz import textos_da_llm

DICIONARIO = Path(__file__).resolve().parents[1] / "conteudo" / "dicionario" / "pt_PT"
_PALAVRA = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


@cache
def _dicionario() -> Dictionary:
    return Dictionary.from_files(str(DICIONARIO))


@cache
def vocabulario_aceite() -> frozenset[str]:
    """Palavras dos YAML editoriais e de `ortografia_aceites`, em minúsculas."""
    avisos = carregar_avisos()
    fontes: list[Any] = [
        [e.model_dump(mode="json") for e in carregar_exercicios().values()],
        carregar_programa().model_dump(mode="json"),
        carregar_alimentacao().model_dump(mode="json"),
        avisos.model_dump(mode="json"),
    ]
    return frozenset(p.lower() for p in _palavras(_cadeias(fontes)))


def _cadeias(valor: Any) -> Iterator[str]:
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _cadeias(v)
    elif isinstance(valor, list | tuple):
        for v in valor:
            yield from _cadeias(v)


def _palavras(textos: Iterable[str]) -> Iterator[str]:
    for texto in textos:
        yield from _PALAVRA.findall(texto)


def _conhecida(palavra: str, aceites: frozenset[str]) -> bool:
    if palavra.lower() in aceites:
        return True
    dicionario = _dicionario()
    if dicionario.lookup(palavra):
        return True
    # Palavras compostas por hífen que o dicionário não tem inteiras: basta cada parte.
    partes = palavra.split("-")
    return len(partes) > 1 and all(
        p.lower() in aceites or dicionario.lookup(p) for p in partes if p
    )


def palavras_desconhecidas(plano: Plano) -> tuple[str, ...]:
    """Palavras do texto da LLM que nem o dicionário nem o vocabulário aceite conhecem."""
    aceites = vocabulario_aceite()
    vistas: dict[str, None] = {}
    for palavra in _palavras(textos_da_llm(plano)):
        if palavra not in vistas and not _conhecida(palavra, aceites):
            vistas[palavra] = None
    return tuple(vistas)
