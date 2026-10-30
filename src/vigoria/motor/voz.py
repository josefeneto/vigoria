"""Voz de marca (papel 5, determinístico): avisos obrigatórios e deteção de brasileirismos.

Os textos obrigatórios (§7) vêm de conteudo/avisos.yaml e são inseridos pelo código,
nunca pela LLM. A deteção de brasileirismos só olha para o texto escrito pela LLM;
a verificação (motor/verificacao.py) chumba o plano se encontrar algum.
"""

import re
from collections.abc import Iterable, Iterator
from typing import Any

from vigoria.conteudo.carregar import carregar_avisos
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano


def textos_obrigatorios() -> tuple[str, ...]:
    """Aviso geral e sinais para interromper (avisos.yaml, `obrigatorios`)."""
    avisos = carregar_avisos()
    return tuple(avisos.textos[id_] for id_ in avisos.obrigatorios)


def inserir_avisos(plano: Plano, e: Estrategia) -> Plano:
    """Avisos do plano: primeiro os obrigatórios, depois os da Estrategia, sem repetições."""
    avisos = tuple(dict.fromkeys((*textos_obrigatorios(), *e.avisos)))
    return plano.model_copy(update={"avisos": avisos})


def textos_da_llm(plano: Plano) -> list[str]:
    """Só o texto escrito pela LLM (sem avisos fixos nem números da Estrategia)."""
    escrito = plano.model_dump(
        mode="json",
        include={
            "resumo",
            "semana_tipo",
            "treino",
            "alimentacao",
            "habitos",
            "indicadores_acompanhamento",
            "notas_personalizadas",
        },
    )
    escrito["forca"] = [m.forca_resistencia for m in plano.marcos]
    escrito["dicas"] = plano.hidratacao.dicas
    return list(_cadeias(escrito))


def _cadeias(valor: Any) -> Iterator[str]:
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _cadeias(v)
    elif isinstance(valor, list):
        for v in valor:
            yield from _cadeias(v)


def encontrar_termos(termos: Iterable[str], texto: str) -> tuple[str, ...]:
    """Termos presentes como palavra ou expressão inteira, sem distinguir maiúsculas."""
    return tuple(
        t for t in termos if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", texto, re.IGNORECASE)
    )


def detetar_brasileirismos(plano: Plano) -> tuple[str, ...]:
    """Brasileirismos da lista de avisos.yaml no texto escrito pela LLM."""
    return encontrar_termos(carregar_avisos().brasileirismos, "\n".join(textos_da_llm(plano)))


def aplicar_voz(plano: Plano, e: Estrategia) -> Plano:
    """Pós-processamento do plano gerado: por agora, a inserção dos avisos obrigatórios."""
    return inserir_avisos(plano, e)
