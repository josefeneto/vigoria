"""Comparação de fornecedores de LLM: o mesmo pedido, um plano por fornecedor (sem reserva).

Só métricas e uma pré-verificação em código (ids fora da lista permitida, «mês/meses»,
brasileirismos, termos da lista negra). Não substitui a verificação (papel 4).
Cada fornecedor faz uma chamada real: só o José corre a comparação.
"""

import re
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from vigoria.conteudo.carregar import carregar_avisos
from vigoria.llm.base import ErroLLM, Metricas, ProvedorLLM
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor.gerador import gerar_plano
from vigoria.motor.selecao import selecionar_exercicios
from vigoria.motor.voz import encontrar_termos, textos_da_llm

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
    exercicios_por_fase: tuple[int, ...] = ()
    ids_fora_da_lista: tuple[str, ...] = ()
    mencoes_meses: int = 0
    brasileirismos: tuple[str, ...] = ()
    lista_negra: tuple[str, ...] = ()
    caracteres_texto: int = 0
    erro: str | None = None


def avaliar_plano(plano: Plano, e: Estrategia, metricas: Metricas | None) -> Avaliacao:
    """Métricas e pré-verificação de um plano."""
    fora: list[str] = []
    por_fase: list[int] = []
    for fase in (1, 2, 3, 4):
        permitidos = {p.id for p in selecionar_exercicios(e, fase)}
        exercicios = getattr(plano.treino, f"fase_{fase}").exercicios
        por_fase.append(len(exercicios))
        fora += [
            f"fase {fase}: {x.exercicio_id}" for x in exercicios if x.exercicio_id not in permitidos
        ]
    textos = textos_da_llm(plano)
    tudo = "\n".join(textos)
    avisos = carregar_avisos()
    return Avaliacao(
        provedor=plano.provedor,
        modelo=metricas.modelo if metricas else "",
        segundos=metricas.segundos if metricas else None,
        tokens_entrada=metricas.tokens_entrada if metricas else None,
        tokens_saida=metricas.tokens_saida if metricas else None,
        exercicios_por_fase=tuple(por_fase),
        ids_fora_da_lista=tuple(fora),
        mencoes_meses=len(_MESES.findall(tudo)),
        brasileirismos=encontrar_termos(avisos.brasileirismos, tudo),
        lista_negra=encontrar_termos(avisos.lista_negra.termos, tudo),
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
            plano = gerar_plano(q, e, provedor)
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
        avaliacoes.append(avaliar_plano(plano, e, getattr(provedor, "ultimas_metricas", None)))
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
        ("Exercícios por fase", lambda a: "/".join(map(str, a.exercicios_por_fase)) or "-"),
        ("Ids fora da lista", lambda a: lista(a.ids_fora_da_lista)),
        ("Menções a mês/meses", lambda a: str(a.mencoes_meses)),
        ("Brasileirismos", lambda a: lista(a.brasileirismos)),
        ("Lista negra", lambda a: lista(a.lista_negra)),
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
