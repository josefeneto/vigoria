"""Voz de marca (papel 5, determinístico): avisos obrigatórios e estilo do texto da LLM.

Os textos obrigatórios (§7) vêm de conteudo/avisos.yaml e são inseridos pelo código,
nunca pela LLM. O estilo (decisão de 30/10/2026) é corrigido aqui, sem chamar a LLM:
«garantir» → «assegurar», brasileirismos com alternativa conhecida e grafia anterior ao
AO90 (avisos.yaml, `estilo.correcoes`). O que não tem correção conhecida
(`estilo.sem_correcao` e brasileirismos que fiquem) só é registado: não bloqueia.
"""

import re
from collections.abc import Iterable, Iterator
from functools import cache
from typing import Any

from pydantic import BaseModel, ConfigDict

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
    """Só o texto escrito pela LLM (Fase 4C): resumo, marcos de força, alimentação e notas.
    O treino, a semana, os hábitos e o acompanhamento são do motor e dos YAML."""
    escrito = plano.model_dump(
        mode="json", include={"resumo", "alimentacao", "notas_personalizadas"}
    )
    escrito["forca"] = [m.forca_resistencia for m in plano.marcos]
    return list(_cadeias(escrito))


# Valores fixos (enumerações e ids), não texto escrito: «terca», «pequeno_almoco», ids.
_CAMPOS_NAO_TEXTO = frozenset({"dia", "refeicao", "exercicio_id"})


def _cadeias(valor: Any) -> Iterator[str]:
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for chave, v in valor.items():
            if chave not in _CAMPOS_NAO_TEXTO:
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


# ---------------------------------------------------------------- Estilo


class RevisaoEstilo(BaseModel):
    """Plano com o estilo corrigido, as correções feitas e o que ficou só como aviso."""

    model_config = ConfigDict(frozen=True)

    plano: Plano
    correcoes: tuple[str, ...] = ()  # «tela → ecrã», sem repetições
    avisos: tuple[str, ...] = ()  # termos sem correção conhecida


@cache
def _padrao_estilo() -> tuple[re.Pattern[str], dict[str, str]]:
    """Uma expressão com todas as correções, das mais longas para as mais curtas."""
    correcoes = {de.lower(): para for de, para in carregar_avisos().estilo.correcoes.items()}
    alternativas = "|".join(re.escape(de) for de in sorted(correcoes, key=len, reverse=True))
    return re.compile(rf"(?<!\w)(?:{alternativas})(?!\w)", re.IGNORECASE), correcoes


def corrigir_texto(texto: str) -> tuple[str, tuple[str, ...]]:
    """Aplica as correções de estilo; mantém a maiúscula inicial. Devolve as feitas."""
    padrao, correcoes = _padrao_estilo()
    feitas: list[str] = []

    def trocar(m: re.Match[str]) -> str:
        original = m.group(0)
        novo = correcoes[original.lower()]
        if original[0].isupper():
            novo = novo[0].upper() + novo[1:]
        feitas.append(f"{original} → {novo}")
        return novo

    return padrao.sub(trocar, texto), tuple(feitas)


def rever_estilo(plano: Plano) -> RevisaoEstilo:
    """Corrige o estilo dos campos escritos pela LLM e regista o que ficou por corrigir."""
    feitas: list[str] = []

    def corrigir(texto: str) -> str:
        novo, aqui = corrigir_texto(texto)
        feitas.extend(aqui)
        return novo

    a = plano.alimentacao
    corrigido = plano.model_copy(
        update={
            "resumo": corrigir(plano.resumo),
            "marcos": tuple(
                m.model_copy(update={"forca_resistencia": corrigir(m.forca_resistencia)})
                for m in plano.marcos
            ),
            "alimentacao": a.model_copy(
                update={
                    "ajustes_refeicoes": tuple(
                        x.model_copy(update={"sugestao": corrigir(x.sugestao)})
                        for x in a.ajustes_refeicoes
                    ),
                    "bebidas_e_alcool": corrigir(a.bebidas_e_alcool),
                    "prioridades_por_fase": tuple(corrigir(p) for p in a.prioridades_por_fase),
                }
            ),
            "notas_personalizadas": tuple(corrigir(n) for n in plano.notas_personalizadas),
        }
    )
    tudo = "\n".join(textos_da_llm(corrigido))
    estilo = carregar_avisos().estilo
    avisos = (*encontrar_termos(estilo.sem_correcao, tudo), *detetar_brasileirismos(corrigido))
    return RevisaoEstilo(
        plano=corrigido,
        correcoes=tuple(dict.fromkeys(feitas)),
        avisos=tuple(dict.fromkeys(avisos)),
    )


def aplicar_voz(plano: Plano, e: Estrategia) -> Plano:
    """Pós-processamento do plano gerado: avisos obrigatórios e estilo corrigido."""
    return rever_estilo(inserir_avisos(plano, e)).plano
