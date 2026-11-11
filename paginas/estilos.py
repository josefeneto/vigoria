"""Sistema visual da Vigoria (Fase 5B): cores, espaçamentos, cantos, sombras e CSS.

As cores do tema do Streamlit estão em .streamlit/config.toml e repetem as de CORES
(um teste confirma que são iguais e que os pares de texto e fundo chegam ao WCAG AA).
O CSS (estilos.css) só aponta para elementos com key= (classes .st-key-*), para as classes
.v-* dos componentes da Vigoria e para atributos estáveis dos widgets (data-testid,
data-variant, aria-*), nunca para as classes st-emotion-cache-*, que mudam a cada versão.
"""

import base64
from functools import cache
from pathlib import Path

import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
PASTA_ICONES = RAIZ / "assets" / "icones"
CSS = Path(__file__).with_name("estilos.css")

CORES = {
    "principal": "#1F5C63",  # petróleo: botões, ligações, progresso
    "principal_profundo": "#123F45",  # títulos e cartão de topo do plano
    "nevoa": "#E4EFEE",  # escolhas marcadas, fundos de destaque
    "terracota": "#C2693E",  # só ícones e formas (3,5:1: não serve para texto)
    "cobre": "#A3532D",  # destaque em texto (sobretítulos, marca)
    "cobre_escuro": "#8F4524",  # cobre ao passar ou carregar
    "argila": "#F8E6DA",  # fundo dos ícones
    "pessego": "#E9B48F",  # sobre o petróleo: pormenores e o botão «Começar»
    "texto": "#2E3338",  # grafite
    "texto_secundario": "#5A6168",
    "fundo": "#F7F3EC",  # branco-osso
    "fundo_secundario": "#ECE5D8",
    "faixa": "#E5DCCD",  # cabeçalho e rodapé: um pouco mais escuro do que os campos
    "cartao": "#FFFDF9",
    "borda": "#DDD3C3",  # areia
    "aviso_texto": "#7A4A00",
    "aviso_fundo": "#FBF0D9",
    "aviso_borda": "#B7791F",
    "sucesso": "#2F6B45",
    "erro": "#A6342B",
    "branco": "#FFFFFF",
    # Só formas, nunca texto (Fase 8D, maquetas): a informação está sempre também em texto.
    "grelha": "#EDE6DA",  # linhas de grelha dos gráficos
    "nevoa_escura": "#C9DCDA",  # segmentos por preencher na escala de esforço
    "petroleo_medio": "#2C5A60",  # semanas por fazer, sobre o petróleo profundo
}

# Pares de texto e fundo usados na interface: todos com pelo menos 4,5:1 (testado).
PARES_TEXTO = (
    ("texto", "fundo"),
    ("texto", "cartao"),
    ("texto", "fundo_secundario"),
    ("texto_secundario", "fundo"),
    ("texto_secundario", "cartao"),
    ("principal", "fundo"),
    ("principal", "cartao"),
    ("principal", "nevoa"),
    ("principal_profundo", "fundo"),
    ("principal_profundo", "nevoa"),
    ("branco", "principal"),
    ("cobre", "fundo"),
    ("cobre", "cartao"),
    ("cobre", "argila"),
    ("branco", "cobre"),
    ("branco", "cobre_escuro"),
    ("fundo", "principal_profundo"),
    ("pessego", "principal_profundo"),
    ("aviso_texto", "aviso_fundo"),
    # Início em faixas (Fase 5C)
    ("principal_profundo", "pessego"),
    ("fundo", "principal"),
    ("argila", "principal"),
    ("texto", "argila"),
    ("principal_profundo", "argila"),
    # Cabeçalho e rodapé
    ("texto", "faixa"),
    ("texto_secundario", "faixa"),
    ("principal", "faixa"),
    ("principal_profundo", "faixa"),
    # Fase 8D: selo e textos sobre o petróleo, números, pastilhas e o cartão «Hoje»
    ("nevoa", "principal_profundo"),
    ("nevoa", "principal"),
    ("principal_profundo", "cartao"),
    ("texto_secundario", "nevoa"),
)

ICONES_PASSOS = {
    "0": "rebento",
    "1": "pessoa",
    "2a": "saude",
    "2b": "penso",
    "3": "sapatilha",
    "4a": "prato",
    "4b": "copo",
    "5": "alvo",
    "6": "calendario",
    "7": "lista",
}

# Ícone de cada dia da semana-tipo, pela primeira palavra da atividade (avisos.yaml).
ICONES_ATIVIDADES = {
    "força": "forca",
    "cardio": "cardio",
    "recuperação": "mobilidade",
    "caminhada": "caminhada",
    "descanso": "descanso",
}


@cache
def icone(nome: str, cor: str = "principal", destaque: str = "terracota") -> str:
    """Ícone de assets/icones/ como <img> decorativo (alt vazio), com as cores de CORES.

    Em <img> e não em <svg>: o st.html filtra o HTML (DOMPurify) e retira os <svg>.
    Os traços em currentColor levam `cor`; os de class="d", `destaque`.
    """
    svg = (PASTA_ICONES / f"{nome}.svg").read_text(encoding="utf-8").strip()
    svg = svg.replace("currentColor", CORES[cor])
    svg = svg.replace('class="d"', f'stroke="{CORES[destaque]}"')
    dados = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img src="data:image/svg+xml;base64,{dados}" alt="">'


def _variaveis() -> str:
    """As cores de CORES como variáveis CSS (--v-principal, --v-cobre...)."""
    return "".join(f"--v-{nome.replace('_', '-')}:{cor};" for nome, cor in CORES.items())


@cache
def _css() -> str:
    return CSS.read_text(encoding="utf-8")


def aplicar() -> None:
    """Aplica o CSS da Vigoria (uma vez por execução, em app.py)."""
    st.html(f"<style>:root{{{_variaveis()}}}\n{_css()}</style>")
