"""Comparação de fornecedores de LLM: o mesmo pedido, um plano por fornecedor (sem reserva).

Fase 4C: o treino e a semana são do motor, por isso só se compara o texto da LLM:
falhas da verificação desse texto (números, lista negra, promessas, brasileirismos,
contagens), menções a meses e palavras que o dicionário pt_PT não conhece.
Cada fornecedor faz uma chamada real: só o José corre a comparação.
"""

import re
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from vigoria.llm.base import ErroLLM, Metricas, ProvedorLLM
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor.gerador import gerar_plano
from vigoria.motor.ortografia import palavras_desconhecidas
from vigoria.motor.verificacao import TIPOS_DO_MOTOR, verificar
from vigoria.motor.voz import aplicar_voz, textos_da_llm

PASTA_SAIDAS = Path("saidas") / "comparacao"  # saidas/ está no .gitignore
_MESES = re.compile(r"\bm[eê]s(?:es)?\b", re.IGNORECASE)


class Avaliacao(BaseModel):
    """Métricas de um plano gerado (ou o erro, se a geração falhou)."""

    model_config = ConfigDict(frozen=True)

    provedor: str
    modelo: str
    segundos: float | None = None
    tokens_entrada: int | None = None
    tokens_saida: int | None = None
    falhas: tuple[str, ...] = ()  # tipos das falhas da verificação do texto da LLM
    mencoes_meses: int = 0
    palavras_desconhecidas: tuple[str, ...] = ()
    caracteres_texto: int = 0
    erro: str | None = None


def avaliar_plano(
    plano: Plano, e: Estrategia, q: Questionario, metricas: Metricas | None
) -> Avaliacao:
    """Métricas e verificação do texto da LLM de um plano."""
    textos = textos_da_llm(plano)
    falhas = [f for f in verificar(plano, e, q) if f.tipo not in TIPOS_DO_MOTOR]
    return Avaliacao(
        provedor=plano.provedor,
        modelo=metricas.modelo if metricas else "",
        segundos=metricas.segundos if metricas else None,
        tokens_entrada=metricas.tokens_entrada if metricas else None,
        tokens_saida=metricas.tokens_saida if metricas else None,
        falhas=tuple(f.tipo.value for f in falhas),
        mencoes_meses=len(_MESES.findall("\n".join(textos))),
        palavras_desconhecidas=palavras_desconhecidas(plano),
        caracteres_texto=sum(len(t) for t in textos),
    )


def comparar(
    q: Questionario,
    e: Estrategia,
    provedores: list[ProvedorLLM],
    guardar: Callable[[str, Plano], None] | None = None,
) -> list[Avaliacao]:
    """Gera um plano com cada fornecedor, um de cada vez; uma falha não para os outros."""
    avaliacoes = []
    for provedor in provedores:
        inicio = time.perf_counter()
        try:
            plano = aplicar_voz(gerar_plano(q, e, provedor), e)
        except ErroLLM as erro:
            avaliacoes.append(
                Avaliacao(
                    provedor=provedor.nome,
                    modelo=provedor.modelo,
                    segundos=round(time.perf_counter() - inicio, 1),
                    erro=str(erro),
                )
            )
            continue
        if guardar is not None:
            guardar(provedor.nome, plano)
        metricas = getattr(provedor, "ultimas_metricas", None)
        avaliacoes.append(avaliar_plano(plano, e, q, metricas))
    return avaliacoes


def formatar_comparacao(avaliacoes: list[Avaliacao]) -> str:
    """Tabela em texto: uma coluna por fornecedor."""

    def lista(valores: tuple[str, ...]) -> str:
        return ", ".join(valores) if valores else "nenhum"

    linhas_def: list[tuple[str, Callable[[Avaliacao], str]]] = [
        ("Modelo", lambda a: a.modelo or "-"),
        ("Tempo (s)", lambda a: "-" if a.segundos is None else f"{a.segundos:.1f}"),
        ("Tokens de entrada", lambda a: str(a.tokens_entrada or "-")),
        ("Tokens de saída", lambda a: str(a.tokens_saida or "-")),
        ("Falhas na verificação", lambda a: lista(a.falhas)),
        ("Menções a mês/meses", lambda a: str(a.mencoes_meses)),
        ("Palavras desconhecidas", lambda a: lista(a.palavras_desconhecidas)),
        ("Caracteres de texto", lambda a: str(a.caracteres_texto)),
    ]
    tabela = [["", *(a.provedor for a in avaliacoes)]]
    tabela += [[rotulo, *(valor(a) for a in avaliacoes)] for rotulo, valor in linhas_def]
    larguras = [max(len(linha[c]) for linha in tabela) for c in range(len(tabela[0]))]
    linhas = [
        " | ".join(celula.ljust(larguras[c]) for c, celula in enumerate(linha)).rstrip()
        for linha in tabela
    ]
    for a in avaliacoes:
        if a.erro:
            linhas.append(f"\n{a.provedor} falhou: {a.erro}")
    return "\n".join(linhas)
