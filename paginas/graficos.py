"""Gráficos do progresso (plotly), legíveis a 390 px: uma série e, no máximo, uma referência.

Os registos a petróleo; a referência a cobre e tracejada, para não depender só da cor. Sem
zoom nem arrastar: no telemóvel, o dedo desloca a página. Cada gráfico tem por baixo uma frase
com o resumo em texto, e os mesmos valores estão na lista de registos.
"""

from collections.abc import Sequence

import plotly.graph_objects as go

from paginas import textos as t
from paginas.estilos import CORES

CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}
ALTURA = 280
LETRA = '"Atkinson Hyperlegible Next", sans-serif'
SEMANAS_TOTAL = 16


def _figura(semanas: Sequence[int], unidade: str, *, legenda: bool, inicio_zero: bool) -> go.Figure:
    """A base de todos os gráficos: grelha discreta, eixo das semanas de 4 em 4."""
    fim = max(SEMANAS_TOTAL, *semanas) if semanas else SEMANAS_TOTAL
    eixo_y: dict[str, object] = {
        "title": {"text": unidade},
        "gridcolor": CORES["grelha"],
        "zeroline": False,
        "fixedrange": True,
    }
    if inicio_zero:
        eixo_y["rangemode"] = "tozero"
    figura = go.Figure()
    figura.update_layout(
        height=ALTURA,
        margin={"l": 52, "r": 12, "t": 8, "b": 96 if legenda else 52},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": LETRA, "size": 13, "color": CORES["texto_secundario"]},
        separators=", ",
        showlegend=legenda,
        # Por baixo do gráfico, como na maqueta (Fase 8D).
        legend={"orientation": "h", "x": 0, "y": -0.32, "yanchor": "top"},
        dragmode=False,
        barcornerradius=4,
        hoverlabel={"bgcolor": CORES["cartao"], "font": {"color": CORES["texto"]}},
        xaxis={
            "title": {"text": t.GRAFICO_SEMANA},
            "range": [-0.5, fim + 0.5],
            "tick0": 0,
            "dtick": 4,
            "showgrid": False,
            "zeroline": False,
            "fixedrange": True,
        },
        yaxis=eixo_y,
    )
    return figura


def _registos(
    figura: go.Figure, semanas: Sequence[int], valores: Sequence[float], unidade: str
) -> None:
    figura.add_scatter(
        x=list(semanas),
        y=list(valores),
        name=t.GRAFICO_REGISTOS,
        mode="lines+markers",
        line={"color": CORES["principal"], "width": 3},
        # O último registo maior e com contorno claro (maqueta Progresso).
        marker={
            "color": CORES["principal"],
            "size": [9] * (len(valores) - 1) + [13],
            "line": {"color": CORES["cartao"], "width": [0] * (len(valores) - 1) + [2]},
        },
        hovertemplate=t.GRAFICO_DICA.format(unidade=unidade) + "<extra></extra>",
    )


def _referencia(
    figura: go.Figure, semanas: Sequence[int], valores: Sequence[float], nome: str, unidade: str
) -> None:
    figura.add_scatter(
        x=list(semanas),
        y=list(valores),
        name=nome,
        mode="lines",
        line={"color": CORES["cobre"], "width": 2, "dash": "dash"},
        hovertemplate=t.GRAFICO_DICA.format(unidade=unidade) + "<extra></extra>",
    )


def peso(
    semanas: Sequence[int], valores: Sequence[float], linha: Sequence[tuple[int, float]]
) -> go.Figure:
    """Na manutenção, `linha` vem vazia: sem linha de objetivo (R12)."""
    figura = _figura(semanas, "kg", legenda=bool(linha), inicio_zero=False)
    if linha:
        _referencia(figura, *zip(*linha, strict=True), t.GRAFICO_LINHA, "kg")
    _registos(figura, semanas, valores, "kg")
    return figura


def cintura(semanas: Sequence[int], valores: Sequence[float], limiar: int | None) -> go.Figure:
    """Sem linha de objetivo (§5 não dá número); o limiar só se a cintura inicial o passava."""
    figura = _figura(semanas, "cm", legenda=limiar is not None, inicio_zero=False)
    if limiar is not None:
        fim = max(SEMANAS_TOTAL, *semanas)
        _referencia(figura, (0, fim), (limiar, limiar), t.GRAFICO_LIMIAR, "cm")
    _registos(figura, semanas, valores, "cm")
    return figura


def barras(
    semanas: Sequence[int],
    valores: Sequence[float],
    unidade: str,
    previsto: int | None = None,
) -> go.Figure:
    """Sessões ou minutos de cardio por semana, com o previsto no plano, se houver."""
    figura = _figura(semanas, unidade, legenda=previsto is not None, inicio_zero=True)
    figura.add_bar(
        x=list(semanas),
        y=list(valores),
        name=t.GRAFICO_REGISTOS,
        width=0.6,
        marker={"color": CORES["principal"]},
        hovertemplate=t.GRAFICO_DICA.format(unidade=unidade) + "<extra></extra>",
    )
    if previsto is not None:
        fim = max(SEMANAS_TOTAL, *semanas)
        _referencia(figura, (0, fim), (previsto, previsto), t.GRAFICO_PREVISTO, unidade)
    return figura
