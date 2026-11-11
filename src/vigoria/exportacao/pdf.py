"""Plano em PDF (A4), gerado no servidor com o fpdf2, sem serviços externos.

Letras do projeto (Fraunces nos títulos, Atkinson Hyperlegible no texto) em recursos/, em TTF
(scripts/converter_fontes.py). Texto base a 11,5 pt e nunca abaixo de 11 pt; cores da marca
escolhidas para se lerem impressas a preto e branco (texto em grafite, nada que dependa só da
cor). Rótulos em avisos.yaml (`rotulos.plano`), como no Markdown e na interface.

Cerca de 9 páginas (Fase 5D): início com resumo e as 4 fases; marcos, semana-tipo, sessão e
o que se repete em todas as fases; uma página por fase, com os exercícios em cartões a duas
colunas; alimentação; hábitos, registo e manutenção a duas colunas; avisos na última página.
Se um bloco não couber, passa para a página seguinte (nunca é cortado).

Sem dados identificativos: nem nome nem email, só «O seu plano Vigoria» e a data.
"""

import io
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import as_file, files
from typing import Any
from zoneinfo import ZoneInfo

from babel.dates import format_date
from fpdf import FPDF, FontFace, XPos, YPos
from fpdf.enums import MethodReturnValue

from vigoria.conteudo.carregar import carregar_avisos, carregar_exercicios, carregar_fases
from vigoria.modelos.plano import ExercicioPlano, ParteOrientacao, Plano, TreinoFase
from vigoria.motor.manutencao import orientacoes_manutencao
from vigoria.regras.textos import numero

RECURSOS = files("vigoria.exportacao") / "recursos"
ICONES = RECURSOS / "icones"  # cópias de assets/icones/exercicios/ (scripts/folha_icones.py)
# Semana-tipo: dia, atividade, duração, descrição (mm). «Segunda-feira» numa só linha.
LARGURAS_SEMANA = [31, 36, 21, 86]

# Paleta da marca (paginas/estilos.py, CORES; um teste confirma que são iguais).
CORES = {
    "principal": "#1F5C63",
    "principal_profundo": "#123F45",
    "cobre": "#A3532D",
    "terracota": "#C2693E",
    "texto": "#2E3338",
    "texto_secundario": "#5A6168",
    "nevoa": "#E4EFEE",
    "borda": "#DDD3C3",
    "aviso_fundo": "#FBF0D9",
    "aviso_borda": "#B7791F",
    "argila": "#F8E6DA",
}

TEXTO_PT = 11.5  # letra base (pedido: pelo menos 11 pt)
LINHA = 6.0  # altura de linha do texto base, em mm
CARTAO_PT = 11.0  # texto dos cartões a duas colunas (o mínimo pedido)
CARTAO_LINHA = 5.4
MARGEM = 18.0  # mm
INTERVALO = 5.0  # entre colunas e entre cartões, mm
FOLGA = 3.0  # margem interior dos cartões, mm
ICONE_PEQUENO = 7.0  # na lista compacta de «Em todas as fases», mm
ICONE = 10.0  # lado do quadrado do ícone nos cartões, mm (o desenho ocupa 3/4)

# Caracteres que as letras do projeto não têm (subconjunto latino). Os hífenes e espaços
# tipográficos aparecem no texto de alguns modelos (p. ex., «pequeno‑almoço» do Groq).
_SUBSTITUIR = str.maketrans(
    {
        "≥": "pelo menos ",
        "≤": "até ",
        "→": "-",
        "⇄": "",
        "✓": "-",
        "‐": "-",  # hífen tipográfico
        "‑": "-",  # hífen não separável
        "‒": "-",  # traço de algarismo
        " ": " ",  # espaço estreito não separável
        " ": " ",  # espaço fino
    }
)


def _rgb(nome: str) -> tuple[int, int, int]:
    h = CORES[nome].lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _limpo(texto: str) -> str:
    return texto.translate(_SUBSTITUIR).strip()


def _data(momento: datetime) -> str:
    """«4 de novembro de 2026», na data de Portugal continental (a base guarda em UTC)."""
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=UTC)
    return format_date(momento.astimezone(ZoneInfo("Europe/Lisbon")), "long", locale="pt_PT")


def _sem_prefixo_fase(texto: str) -> str:
    """«Fase 1: criar a rotina» → «criar a rotina» (o PDF já escreve «Fase 1:»)."""
    return re.sub(r"^\s*fase\s*\d+\s*[:.\-–—]\s*", "", texto, flags=re.IGNORECASE)


def _intervalo(minimo: int, maximo: int, unidade: str) -> str:
    return f"{minimo} {unidade}" if minimo == maximo else f"{minimo} a {maximo} {unidade}"


def _icone_svg(id_exercicio: str) -> io.BytesIO:
    """Ícone do movimento (exercicios.yaml, `icone`), com as cores da maqueta: figura em
    petróleo profundo, equipamento em terracota."""
    nome = carregar_exercicios()[id_exercicio].icone
    svg = (ICONES / f"{nome}.svg").read_text(encoding="utf-8")
    svg = svg.replace("currentColor", CORES["principal_profundo"])
    svg = svg.replace('class="d"', f'stroke="{CORES["terracota"]}"')
    return io.BytesIO(svg.encode("utf-8"))


# ---------------------------------------------------------------- o que se repete


@dataclass(frozen=True)
class Comuns:
    """O que é igual nas fases e se mostra uma só vez (bloco «Em todas as fases»)."""

    cardio: ExercicioPlano | None
    mobilidade_equilibrio: tuple[ExercicioPlano, ...]

    def diferencas(self, fase: TreinoFase) -> tuple[ExercicioPlano, ...]:
        """O que esta fase tem de diferente do bloco comum (vai para a página da fase)."""
        cardio = fase.cardio_finalizador
        proprio = () if cardio is None or cardio == self.cardio else (cardio,)
        outros = (x for x in fase.mobilidade_equilibrio if x not in self.mobilidade_equilibrio)
        return (*proprio, *outros)


def comuns(fases: Sequence[TreinoFase]) -> Comuns:
    """Cardio finalizador mais frequente (o primeiro, em caso de empate) e os exercícios de
    mobilidade e equilíbrio presentes, iguais, em todas as fases. Determinístico."""
    cardios = [f.cardio_finalizador for f in fases if f.cardio_finalizador is not None]
    cardio = Counter(cardios).most_common(1)[0][0] if cardios else None
    mob = tuple(
        x
        for x in (fases[0].mobilidade_equilibrio if fases else ())
        if all(x in f.mobilidade_equilibrio for f in fases)
    )
    return Comuns(cardio=cardio, mobilidade_equilibrio=mob)


# ---------------------------------------------------------------- blocos medidos


@dataclass(frozen=True)
class Texto:
    """Um parágrafo com a sua letra; `marca` desenha um marcador pendurado («•»)."""

    texto: str
    estilo: str = ""
    tamanho: float = CARTAO_PT
    cor: str = "texto"
    linha: float = CARTAO_LINHA
    depois: float = 1.0
    familia: str = "Atkinson"
    marca: str = ""


@dataclass(frozen=True)
class Cartao:
    """Cartão com borda: `topo` ao lado do ícone (se houver), `corpo` por baixo."""

    topo: tuple[Texto, ...]
    corpo: tuple[Texto, ...] = ()
    icone: str | None = None  # id do exercício
    fundo: str | None = None


_RECUO_MARCA = 5.0
TOPO_PAGINA = MARGEM + 2  # onde começa o texto, depois do cabeçalho


def _arrumar(
    alturas: Sequence[float], inicio: float, topo: float, fundo: float
) -> list[tuple[int, int, float]]:
    """(página relativa, coluna, y) de cada bloco, a encher duas colunas de cima para baixo.
    Um bloco maior do que a coluna fica sozinho nela (não há melhor sem o partir)."""
    lugares = []
    pagina, coluna, y, cima = 0, 0, inicio, inicio
    for h in alturas:
        if y + h > fundo and y > cima:
            coluna += 1
            if coluna == 2:
                pagina, coluna, cima = pagina + 1, 0, topo
            y = cima
        lugares.append((pagina, coluna, y))
        y += h
    return lugares


class _Documento(FPDF):
    def __init__(self, rodape: str) -> None:
        super().__init__(format="A4", unit="mm")
        self._rodape = rodape
        self.set_margins(MARGEM, MARGEM, MARGEM)
        self.set_auto_page_break(auto=True, margin=MARGEM + 4)
        self.set_title(carregar_avisos().rotulos.plano["pdf_titulo"])
        self.set_creator("Vigoria")
        for familia, estilo, ficheiro in (
            ("Atkinson", "", "Atkinson-Regular.ttf"),
            ("Atkinson", "B", "Atkinson-Bold.ttf"),
            ("Atkinson", "I", "Atkinson-Italic.ttf"),
            ("Fraunces", "", "Fraunces-SemiBold.ttf"),
            ("Fraunces", "B", "Fraunces-Bold.ttf"),
        ):
            with as_file(RECURSOS / ficheiro) as caminho:
                self.add_font(familia, estilo, str(caminho))
        self.set_text_color(*_rgb("texto"))

    @property
    def fundo(self) -> float:
        """Onde acaba a área de texto da página (acima do rodapé)."""
        return self.h - MARGEM - 4

    def multi_cell(self, *args: Any, align: str = "L", **kwargs: Any) -> Any:
        """Alinhado à esquerda por omissão: o justificado deixa espaços irregulares."""
        return super().multi_cell(*args, align=align, **kwargs)

    def header(self) -> None:
        if self.page_no() == 1:
            return  # a primeira página tem a sua faixa, com o logotipo maior
        with as_file(RECURSOS / "vigoria_logo.svg") as logo:
            self.image(str(logo), x=MARGEM, y=9, h=6)
        self.set_y(MARGEM + 2)

    def footer(self) -> None:
        self.set_y(-MARGEM + 4)
        self.set_font("Atkinson", "", 10)
        self.set_text_color(*_rgb("texto_secundario"))
        texto = self._rodape.format(pagina=self.page_no(), total="{nb}")
        self.cell(0, 5, texto, align="C")
        self.set_text_color(*_rgb("texto"))

    # ------------------------------------------------------------ blocos de texto

    def titulo(self, texto: str, *, nova_pagina: bool = False, espaco: float = 50) -> None:
        """Título de secção: Fraunces, petróleo profundo, com um filete por baixo.

        `espaco`: altura mínima (mm) que tem de sobrar por baixo; se não sobrar, página nova.
        """
        if nova_pagina or self.get_y() > self.fundo - espaco:
            self.add_page()
        else:
            self.ln(4)
        self.set_font("Fraunces", "B", 19)
        self.set_text_color(*_rgb("principal_profundo"))
        self.multi_cell(0, 9, _limpo(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*_rgb("cobre"))
        self.set_line_width(0.6)
        self.line(MARGEM, self.get_y() + 1, MARGEM + 24, self.get_y() + 1)
        self.ln(5)
        self.set_text_color(*_rgb("texto"))

    def subtitulo(self, texto: str, *, espaco: float = 50) -> None:
        if self.get_y() > self.fundo - espaco:  # com espaço para, pelo menos, o primeiro bloco
            self.add_page()
        self.ln(2)
        self.set_font("Fraunces", "", 14)
        self.set_text_color(*_rgb("principal_profundo"))
        self.multi_cell(0, 7, _limpo(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.5)
        self.set_text_color(*_rgb("texto"))

    def paragrafo(self, texto: str, *, estilo: str = "", cor: str = "texto") -> None:
        self.set_font("Atkinson", estilo, TEXTO_PT)
        self.set_text_color(*_rgb(cor))
        self.multi_cell(0, LINHA, _limpo(texto), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_text_color(*_rgb("texto"))
        self.ln(2)

    def rotulo(self, rotulo: str, texto: str) -> None:
        """«Rótulo» a negrito numa linha e o texto por baixo (lê-se bem impresso)."""
        with self.unbreakable() as doc:
            doc.set_font("Atkinson", "B", TEXTO_PT)
            doc.multi_cell(0, LINHA, _limpo(rotulo), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            doc.paragrafo(texto)

    def lista(self, itens: list[str], *, numerada: bool = False) -> None:
        self.set_font("Atkinson", "", TEXTO_PT)
        for i, item in enumerate(itens, start=1):
            marca = f"{i}." if numerada else "•"
            y = self.get_y()
            if y > self.h - MARGEM - 12:
                self.add_page()
                y = self.get_y()
            self.set_x(MARGEM)
            self.cell(7, LINHA, marca)
            self.set_xy(MARGEM + 7, y)
            self.multi_cell(0, LINHA, _limpo(item), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.ln(1)
        self.ln(1.5)

    def _altura_tabela(self, linhas: list[list[str]], larguras: list[int]) -> float:
        """Altura da tabela (cabeçalho a negrito incluído), medida célula a célula."""
        total = 0.0
        for i, linha in enumerate(linhas):
            self.set_font("Atkinson", "B" if i == 0 else "", TEXTO_PT)
            total += 2 * 1.5 + max(
                float(
                    self.multi_cell(
                        w - 4, LINHA, _limpo(c), dry_run=True, output=MethodReturnValue.HEIGHT
                    )
                )
                for c, w in zip(linha, larguras, strict=True)
            )
        return total

    def tabela(self, cabecalho: list[str], linhas: list[list[str]], larguras: list[int]) -> None:
        """Tabela nunca partida entre páginas: se não couber, passa inteira para a seguinte."""
        if self.get_y() + self._altura_tabela([cabecalho, *linhas], larguras) > self.fundo:
            self.add_page()
        self.set_font("Atkinson", "", TEXTO_PT)
        self.set_draw_color(*_rgb("borda"))
        self.set_line_width(0.3)
        cabeca = FontFace(
            family="Atkinson", emphasis="BOLD", color=_rgb("principal_profundo"), fill_color=None
        )
        with self.table(
            col_widths=larguras,
            headings_style=cabeca,
            line_height=LINHA,
            padding=(1.5, 2),
            text_align="LEFT",
            borders_layout="HORIZONTAL_LINES",
            first_row_as_headings=True,
        ) as t:
            for linha in [cabecalho, *linhas]:
                fila = t.row()
                for celula in linha:
                    fila.cell(_limpo(celula))
        self.ln(4)

    # ------------------------------------------------------------ textos medidos

    def _fonte(self, t: Texto) -> None:
        self.set_font(t.familia, t.estilo, t.tamanho)
        self.set_text_color(*_rgb(t.cor))

    def altura(self, textos: Iterable[Texto], largura: float) -> float:
        total = 0.0
        for t in textos:
            if not t.texto:  # só espaço
                total += t.depois
                continue
            self._fonte(t)
            recuo = _RECUO_MARCA if t.marca else 0
            total += float(
                self.multi_cell(
                    largura - recuo,
                    t.linha,
                    _limpo(t.texto),
                    dry_run=True,
                    output=MethodReturnValue.HEIGHT,
                )
            )
            total += t.depois
        return total

    def escrever(self, textos: Iterable[Texto], x: float, largura: float) -> None:
        """Escreve a partir do y atual, na coluna (x, largura), sem quebra de página."""
        for t in textos:
            if not t.texto:  # só espaço
                self.set_y(self.get_y() + t.depois)
                continue
            self._fonte(t)
            y = self.get_y()
            recuo = 0.0
            if t.marca:
                self.set_xy(x, y)
                self.cell(_RECUO_MARCA, t.linha, t.marca)
                recuo = _RECUO_MARCA
            self.set_xy(x + recuo, y)
            self.multi_cell(
                largura - recuo, t.linha, _limpo(t.texto), new_x=XPos.LEFT, new_y=YPos.NEXT
            )
            self.set_y(self.get_y() + t.depois)
        self.set_text_color(*_rgb("texto"))

    # ------------------------------------------------------------ cartões

    def icone(self, id_exercicio: str, x: float, y: float, lado: float) -> None:
        """Como na maqueta: o pictograma num quadrado arredondado de fundo «argila»."""
        self.set_fill_color(*_rgb("argila"))
        self.rect(x, y, lado, lado, style="F", round_corners=True, corner_radius=lado / 4)
        margem = lado / 8
        desenho = lado - 2 * margem
        self.image(_icone_svg(id_exercicio), x=x + margem, y=y + margem, w=desenho, h=desenho)

    def lista_icones(self, itens: Sequence[tuple[str, Sequence[Texto]]], colunas: int = 2) -> None:
        """Lista compacta, sem caixas: ícone pequeno e, ao lado, nome e descrição, em grelha.
        Cada linha da grelha fica inteira numa página."""
        largura = (self.epw - INTERVALO * (colunas - 1)) / colunas
        recuo = ICONE_PEQUENO + 2.5
        automatica = self.auto_page_break
        self.set_auto_page_break(False)
        for i in range(0, len(itens), colunas):
            fila = itens[i : i + colunas]
            altura = self._altura_fila(fila, largura - recuo)
            if self.get_y() + altura > self.fundo:
                self.add_page()
            y = self.get_y()
            for j, (id_exercicio, textos) in enumerate(fila):
                x = MARGEM + j * (largura + INTERVALO)
                self.icone(id_exercicio, x, y + 0.5, ICONE_PEQUENO)
                self.set_y(y)
                self.escrever(textos, x + recuo, largura - recuo)
            self.set_y(y + altura + 2.5)
        self.set_auto_page_break(automatica, margin=MARGEM + 4)
        self.set_x(MARGEM)

    def _altura_fila(self, fila: Sequence[tuple[str, Sequence[Texto]]], largura: float) -> float:
        return max(max(ICONE_PEQUENO, self.altura(t, largura)) for _, t in fila)

    def altura_lista_icones(
        self, itens: Sequence[tuple[str, Sequence[Texto]]], colunas: int
    ) -> float:
        largura = (self.epw - INTERVALO * (colunas - 1)) / colunas - ICONE_PEQUENO - 2.5
        filas = [itens[i : i + colunas] for i in range(0, len(itens), colunas)]
        return sum(self._altura_fila(f, largura) + 2.5 for f in filas)

    def _altura_cartao(self, c: Cartao, largura: float) -> float:
        interior = largura - 2 * FOLGA
        recuo = ICONE + 2.5 if c.icone else 0
        topo = self.altura(c.topo, interior - recuo)
        if c.icone:
            topo = max(topo, ICONE + 1)
        return 2 * FOLGA + topo + self.altura(c.corpo, interior) - (0 if c.corpo else 1)

    def _cartao(self, c: Cartao, x: float, y: float, largura: float, altura: float) -> None:
        self.set_draw_color(*_rgb("borda"))
        self.set_line_width(0.4)
        if c.fundo:
            self.set_fill_color(*_rgb(c.fundo))
        self.rect(x, y, largura, altura, style="DF" if c.fundo else "D", round_corners=True)
        interior = largura - 2 * FOLGA
        recuo = 0.0
        if c.icone:
            self.icone(c.icone, x + FOLGA, y + FOLGA, ICONE)
            recuo = ICONE + 2.5
        self.set_y(y + FOLGA)
        self.escrever(c.topo, x + FOLGA + recuo, interior - recuo)
        if c.icone:
            self.set_y(max(self.get_y(), y + FOLGA + ICONE + 1))
        self.escrever(c.corpo, x + FOLGA, interior)

    def cartoes(self, cartoes: Sequence[Cartao], colunas: int = 2) -> None:
        """Cartões em grelha; os da mesma linha com a mesma altura; nunca partidos."""
        largura = (self.epw - INTERVALO * (colunas - 1)) / colunas
        automatica = self.auto_page_break
        self.set_auto_page_break(False)
        for i in range(0, len(cartoes), colunas):
            fila = cartoes[i : i + colunas]
            altura = max(self._altura_cartao(c, largura) for c in fila)
            if self.get_y() + altura > self.fundo:
                self.add_page()
            y = self.get_y()
            for j, c in enumerate(fila):
                self._cartao(c, MARGEM + j * (largura + INTERVALO), y, largura, altura)
            self.set_y(y + altura + INTERVALO - 1)
        self.set_auto_page_break(automatica, margin=MARGEM + 4)
        self.set_x(MARGEM)

    def faixa(self, textos: Sequence[Texto]) -> None:
        """Faixa a toda a largura em névoa (abre a página de cada fase)."""
        interior = self.epw - 2 * FOLGA - 2
        altura = self.altura(textos, interior) + 2 * FOLGA - 1
        y = self.get_y()
        self.set_fill_color(*_rgb("nevoa"))
        self.rect(MARGEM, y, self.epw, altura, style="F", round_corners=True)
        self.set_y(y + FOLGA)
        self.escrever(textos, MARGEM + FOLGA + 1, interior)
        self.set_y(y + altura + 4)

    def colunas(self, blocos: Sequence[Sequence[Texto]]) -> None:
        """Blocos em duas colunas, a encher a da esquerda e depois a da direita; um bloco
        que não caiba no resto da coluna passa para a seguinte (nunca é partido). Na última
        página, as duas colunas ficam com alturas parecidas (sobra espaço por baixo)."""
        largura = (self.epw - INTERVALO * 1.4) / 2
        alturas = [self.altura(b, largura) for b in blocos]
        inicio = self.get_y()
        lugares = _arrumar(alturas, inicio, TOPO_PAGINA, self.fundo)
        ultima = lugares[-1][0] if lugares else 0
        k = next(i for i, lugar in enumerate(lugares) if lugar[0] == ultima) if lugares else 0
        partida = inicio if ultima == 0 else TOPO_PAGINA
        # A menor altura de coluna em que os blocos da última página ainda cabem nela.
        for limite in range(int(partida + max(alturas[k:], default=0)) + 1, int(self.fundo)):
            tentativa = _arrumar(alturas[k:], partida, TOPO_PAGINA, float(limite))
            if tentativa[-1][0] == 0:
                lugares[k:] = [(ultima, c, y) for _, c, y in tentativa]
                break
        automatica = self.auto_page_break
        self.set_auto_page_break(False)
        pagina, fim = 0, inicio
        for bloco, altura, (p, coluna, y) in zip(blocos, alturas, lugares, strict=True):
            if p > pagina:
                self.add_page()
                pagina, fim = p, TOPO_PAGINA
            self.set_y(y)
            self.escrever(bloco, MARGEM + coluna * (largura + INTERVALO * 1.4), largura)
            fim = max(fim, y + altura)
        self.set_y(fim)
        self.set_auto_page_break(automatica, margin=MARGEM + 4)
        self.set_x(MARGEM)

    def lado_a_lado(self, esquerda: Sequence[Texto], direita: Sequence[Texto]) -> None:
        """Dois blocos curtos, um em cada coluna (p. ex., proteína e hidratação)."""
        largura = (self.epw - INTERVALO * 1.4) / 2
        altura = max(self.altura(esquerda, largura), self.altura(direita, largura))
        if self.get_y() + altura > self.fundo:
            self.add_page()
        y = self.get_y()
        self.escrever(esquerda, MARGEM, largura)
        self.set_y(y)
        self.escrever(direita, MARGEM + largura + INTERVALO * 1.4, largura)
        self.set_xy(MARGEM, y + altura)

    # ------------------------------------------------------------ avisos

    def caixa_avisos(self, titulo: str, avisos: list[str]) -> None:
        """Avisos em destaque: caixa com borda grossa, fundo claro e texto em grafite.

        Ficam sempre no fim do PDF: na mesma página do que vem antes, se couberem inteiros
        nela; senão, numa página nova. Se não couberem todos numa página, cada aviso tem a
        sua caixa (nunca partida).
        """
        alturas = [self._altura_aviso(a) for a in avisos]
        if self.get_y() + 8 + 14 + 10 + sum(alturas) > self.h - MARGEM - 8:
            self.add_page()
        else:
            self.ln(8)
        self.set_font("Fraunces", "B", 21)
        self.set_text_color(*_rgb("principal_profundo"))
        self.multi_cell(0, 10, _limpo(titulo), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)
        disponivel = self.h - MARGEM - 8 - self.get_y()
        if 10 + sum(alturas) <= disponivel:
            self._caixa(list(zip(avisos, alturas, strict=True)))
        else:
            for aviso, altura in zip(avisos, alturas, strict=True):
                if self.get_y() + altura + 10 > self.h - MARGEM - 8:
                    self.add_page()
                self._caixa([(aviso, altura)])
                self.ln(3)

    _INTERIOR = 174 - 28  # largura do texto do aviso (A4 menos margens e folgas)
    _AVISO_PT = TEXTO_PT + 0.5
    _AVISO_LINHA = LINHA + 0.4

    def _altura_aviso(self, aviso: str) -> float:
        self.set_font("Atkinson", "", self._AVISO_PT)
        altura = self.multi_cell(
            self._INTERIOR,
            self._AVISO_LINHA,
            _limpo(aviso),
            dry_run=True,
            output=MethodReturnValue.HEIGHT,
        )
        return float(altura) + 3

    def _caixa(self, avisos: list[tuple[str, float]]) -> None:
        topo = self.get_y()
        self.set_fill_color(*_rgb("aviso_fundo"))
        self.set_draw_color(*_rgb("aviso_borda"))
        self.set_line_width(1.2)
        self.rect(MARGEM, topo, self.epw, 7 + sum(a for _, a in avisos), style="DF")
        self.set_text_color(*_rgb("texto"))
        self.set_y(topo + 5)
        for aviso, _ in avisos:
            y = self.get_y()
            self.set_xy(MARGEM + 7, y)
            self.set_font("Atkinson", "B", self._AVISO_PT)
            self.cell(7, self._AVISO_LINHA, "!")
            self.set_xy(MARGEM + 14, y)
            self.set_font("Atkinson", "", self._AVISO_PT)
            self.multi_cell(
                self._INTERIOR,
                self._AVISO_LINHA,
                _limpo(aviso),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
            self.ln(3)
        self.set_y(topo + 7 + sum(a for _, a in avisos) + 2)


# ---------------------------------------------------------------- cartões de exercício


def _prescricao(x: ExercicioPlano, r: dict[str, str]) -> str:
    """«3 séries · 12-15 repetições · descanso 60 s»."""
    partes = []
    if x.series:
        partes.append(f"{x.series} {r['series'].lower()}")
    if x.repeticoes:
        # «repetições» só depois de números («12», «10-12»); «30s (cada lado)» fica assim.
        so_numeros = re.fullmatch(r"\d+(\s*[-–a]\s*\d+)?", x.repeticoes.strip())
        rotulo = f" {r['repeticoes'].lower()}" if so_numeros else ""
        partes.append(f"{x.repeticoes}{rotulo}")
    if x.descanso_s:
        descanso = _intervalo(*x.descanso_s, "s").replace(" s", " s")
        partes.append(f"{r['descanso'].lower()} {descanso}")
    return " · ".join(partes)


def _cartao_exercicio(x: ExercicioPlano, r: dict[str, str], extra: str = "") -> Cartao:
    """Ícone, nome, prescrição, descrição, notas («Com halteres: …») e «Em vez de: …»."""
    topo = [Texto(x.nome, "B", 12.5, "principal_profundo", 6.0, 0.5)]
    if extra:
        topo.append(Texto(extra, "B", CARTAO_PT, "cobre"))
    if prescricao := _prescricao(x, r):
        topo.append(Texto(prescricao, "B"))
    notas = list(x.notas)
    if x.em_vez_de:
        notas.insert(0, r["em_vez_de"].format(nome=carregar_exercicios()[x.em_vez_de].nome))
    corpo = [Texto(x.descricao), *(Texto(n, "I", cor="texto_secundario") for n in notas)]
    return Cartao(topo=tuple(topo), corpo=tuple(corpo), icone=x.id)


def _item_compacto(
    x: ExercicioPlano, r: dict[str, str], extra: str = ""
) -> tuple[str, tuple[Texto, ...]]:
    """Para a lista compacta: nome, etiqueta, prescrição (se houver), descrição e notas."""
    partes = [Texto(x.nome, "B", cor="principal_profundo", depois=0.3)]
    if extra:
        partes.append(Texto(extra, "B", cor="cobre", depois=0.3))
    if prescricao := _prescricao(x, r):
        partes.append(Texto(prescricao, "B", depois=0.3))
    partes.append(Texto(x.descricao, depois=0.3))
    partes.extend(Texto(n, "I", cor="texto_secundario", depois=0.3) for n in x.notas)
    return x.id, tuple(partes)


# ---------------------------------------------------------------- secções


def _inicio(pdf: _Documento, plano: Plano, r: dict[str, str], criado_em: datetime) -> None:
    """Página 1, sem capa separada: logotipo, título e data, resumo, notas e as 4 fases."""
    pdf.add_page()
    with as_file(RECURSOS / "vigoria_logo.svg") as logo:
        pdf.image(str(logo), x=MARGEM, y=MARGEM - 4, h=11)
    pdf.set_xy(MARGEM, MARGEM - 3)
    pdf.set_font("Atkinson", "", CARTAO_PT)
    pdf.set_text_color(*_rgb("texto_secundario"))
    pdf.multi_cell(0, 5, r["pdf_data"].format(data=_data(criado_em)), align="R", new_x=XPos.LMARGIN)
    pdf.set_y(MARGEM + 12)
    pdf.set_font("Fraunces", "B", 26)
    pdf.set_text_color(*_rgb("principal_profundo"))
    pdf.multi_cell(0, 12, r["pdf_titulo"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*_rgb("cobre"))
    pdf.set_line_width(0.8)
    pdf.line(MARGEM, pdf.get_y() + 1, MARGEM + 32, pdf.get_y() + 1)
    pdf.ln(5)
    pdf.paragrafo(r["pdf_capa_nota"], estilo="I", cor="texto_secundario")

    pdf.subtitulo(r["resumo"])
    pdf.paragrafo(plano.resumo)
    if plano.notas_personalizadas:
        pdf.subtitulo(r["notas"])
        pdf.lista(list(plano.notas_personalizadas))

    pdf.subtitulo(r["pdf_fases"], espaco=70)
    semanas = {f.numero: f.semanas for f in carregar_fases()}
    pdf.cartoes(
        [
            Cartao(
                topo=(
                    Texto(
                        r["pdf_fase_semanas"].format(
                            n=f.numero, min=semanas[f.numero].min, max=semanas[f.numero].max
                        ),
                        "B",
                        cor="cobre",
                    ),
                    Texto(f.nome, "B", 13, "principal_profundo", 6.2, 1.5, "Fraunces"),
                    Texto(f.foco, depois=0),
                ),
            )
            for f in plano.treino.fases
        ]
    )


def _marcos(pdf: _Documento, plano: Plano, r: dict[str, str]) -> None:
    pdf.titulo(r["marcos"], nova_pagina=True)
    # A cintura não tem número por fase (REGRAS §5): igual nos 4 marcos, diz-se uma vez.
    cinturas = {m.cintura for m in plano.marcos}
    cintura_unica = cinturas.pop() if len(cinturas) == 1 else None
    cabecalho = [r["semana"], r["peso_indicativo"], r["forca_resistencia"]]
    larguras = [24, 34, 116]
    if cintura_unica is None:
        cabecalho.insert(2, r["cintura"])
        larguras = [24, 32, 44, 74]
    linhas = []
    for m in plano.marcos:
        linha = [str(m.semana), f"{numero(m.peso_indicativo_kg)} kg", m.forca_resistencia]
        if cintura_unica is None:
            linha.insert(2, m.cintura)
        linhas.append(linha)
    pdf.tabela(cabecalho, linhas, larguras)
    if cintura_unica:
        pdf.paragrafo(
            r["pdf_cintura_fases"].format(texto=cintura_unica[:1].lower() + cintura_unica[1:])
        )


def _semana(pdf: _Documento, plano: Plano, r: dict[str, str]) -> None:
    dias = carregar_avisos().rotulos.dias
    pdf.titulo(r["semana_tipo"])
    pdf.tabela(
        [r["dia"], r["atividade"], r["duracao"], r["descricao"]],
        [
            [
                dias[s.dia],
                s.atividade,
                f"{s.duracao_min} min" if s.duracao_min else "-",
                s.descricao,
            ]
            for s in plano.semana_tipo
        ],
        LARGURAS_SEMANA,
    )
    sessao = plano.treino.estrutura_sessao
    pdf.subtitulo(r["estrutura_sessao"])
    for parte in ("aquecimento", "bloco_principal", "cardio_finalizador", "retorno_calma"):
        pdf.rotulo(r[parte], getattr(sessao, parte))


def _em_todas_as_fases(pdf: _Documento, plano: Plano, c: Comuns, r: dict[str, str]) -> None:
    """Mobilidade, equilíbrio e cardio finalizador uma só vez (iguais em todas as fases)."""
    if c.cardio is None and not c.mobilidade_equilibrio:
        return
    itens = []
    if c.cardio is not None:
        f = plano.treino.fases[0]
        duracao = r["cardio_duracao"].format(
            min=f.cardio_duracao_min[0], max=f.cardio_duracao_min[1]
        )
        itens.append(_item_compacto(c.cardio, r, f"{r['cardio_finalizador']} · {duracao}"))
    itens.extend(_item_compacto(x, r) for x in c.mobilidade_equilibrio)
    # O bloco inteiro na mesma página que «Como é cada sessão»: 2 colunas se couber, senão 3;
    # se nem assim couber, passa todo (título incluído) para a página seguinte.
    cabeca = 18.0  # título e nota
    disponivel = pdf.fundo - pdf.get_y() - cabeca
    colunas = next((n for n in (2, 3) if pdf.altura_lista_icones(itens, n) <= disponivel), 2)
    pdf.subtitulo(r["pdf_em_todas_fases"], espaco=cabeca + pdf.altura_lista_icones(itens, colunas))
    pdf.paragrafo(r["pdf_em_todas_fases_nota"])
    pdf.lista_icones(itens, colunas)


def _fase(pdf: _Documento, fase: TreinoFase, c: Comuns, r: dict[str, str]) -> None:
    s = {f.numero: f.semanas for f in carregar_fases()}[fase.numero]
    pdf.titulo(f"{r['fase']} {fase.numero}: {fase.nome}", nova_pagina=True)
    pdf.faixa(
        [
            Texto(
                r["pdf_fase_semanas"].format(n=fase.numero, min=s.min, max=s.max),
                "B",
                TEXTO_PT,
                "cobre",
                LINHA,
            ),
            Texto(r["foco"], "B", TEXTO_PT, linha=LINHA, depois=0),
            Texto(fase.foco, tamanho=TEXTO_PT, linha=LINHA),
            Texto(
                r["esforco"].format(min=fase.esforco[0], max=fase.esforco[1]),
                "I",
                TEXTO_PT,
                linha=LINHA,
                depois=0,
            ),
        ]
    )
    pdf.subtitulo(r["forca_titulo"])
    # O que difere do bloco «Em todas as fases» entra na mesma grelha, com etiqueta (ocupa
    # o lugar livre da última linha e a fase continua numa só página).
    cartoes = [_cartao_exercicio(x, r) for x in fase.forca]
    for x in c.diferencas(fase):
        tipo = "cardio_finalizador" if x == fase.cardio_finalizador else "mobilidade_equilibrio"
        cartoes.append(_cartao_exercicio(x, r, f"{r['pdf_so_nesta_fase']} · {r[tipo]}"))
    pdf.cartoes(cartoes)


def _alimentacao(pdf: _Documento, plano: Plano, r: dict[str, str]) -> None:
    refeicoes = carregar_avisos().rotulos.refeicoes
    a = plano.alimentacao
    pdf.titulo(r["alimentacao"], nova_pagina=True)
    pdf.subtitulo(r["ajustes_refeicoes"])
    for x in a.ajustes_refeicoes:
        pdf.rotulo(refeicoes[x.refeicao], x.sugestao)
    pdf.subtitulo(r["bebidas_e_alcool"])
    pdf.paragrafo(a.bebidas_e_alcool)
    pdf.subtitulo(r["prioridades_por_fase"])
    pdf.lista(
        [
            f"{r['fase']} {i}: {_sem_prefixo_fase(p)}"
            for i, p in enumerate(a.prioridades_por_fase, start=1)
        ]
    )

    p = plano.proteina
    proteina = [_titulo_coluna(r["proteina"])]
    if p.minimo_g is not None:
        valores = r["proteina_valores"].format(
            minimo=p.minimo_g,
            maximo=p.maximo_g,
            por_refeicao_min=p.por_refeicao_min_g,
            por_refeicao_max=p.por_refeicao_max_g,
        )
        proteina.append(Texto(valores, "B", depois=2))
    if p.nota:
        proteina.append(Texto(p.nota))

    h = plano.hidratacao
    hidratacao = [_titulo_coluna(r["hidratacao"])]
    if h.valores.central_ml is not None:
        valores = r["hidratacao_valores"].format(
            minimo=h.valores.minimo_ml, maximo=h.valores.maximo_ml, central=h.valores.central_ml
        )
        hidratacao.append(Texto(valores, "B", depois=2))
    if h.valores.nota:
        hidratacao.append(Texto(h.valores.nota, depois=2))
    hidratacao.extend(_ponto(d) for d in h.dicas)
    pdf.ln(2)
    pdf.lado_a_lado(proteina, hidratacao)


# Blocos das colunas (hábitos, registo, manutenção).


def _titulo_coluna(texto: str) -> Texto:
    return Texto(texto, "B", 15, "principal_profundo", 7.0, 2.0, "Fraunces")


def _subtitulo_coluna(texto: str) -> Texto:
    return Texto(texto, "", 13, "principal_profundo", 6.4, 1.0, "Fraunces")


def _negrito(texto: str) -> Texto:
    return Texto(texto, "B", depois=0.5)


def _ponto(texto: str) -> Texto:
    return Texto(texto, marca="•")


CURTO = 60  # caracteres: uma lista só de itens curtos lê-se melhor em texto corrido


def _pontos(itens: Sequence[str]) -> list[list[Texto]]:
    """Um bloco por item («•»); se forem todos curtos, um só parágrafo separado por « · »."""
    if itens and all(len(x) <= CURTO for x in itens):
        return [[Texto(" · ".join(x.strip().rstrip(";") for x in itens), depois=2)]]
    return [[_ponto(x)] for x in itens]


def _blocos_parte(titulo: str, parte: ParteOrientacao) -> list[list[Texto]]:
    blocos: list[list[Texto]] = []
    primeiro = [_subtitulo_coluna(titulo)]
    for i, p in enumerate(parte.introducao):
        if i == 0:
            primeiro.append(Texto(p, depois=2))
        else:
            blocos.append([Texto(p, depois=2)])
    blocos.insert(0, primeiro)
    if parte.pontos:
        cabeca = [_negrito(parte.titulo_pontos)] if parte.titulo_pontos else []
        pontos = _pontos(parte.pontos)
        blocos.append([*cabeca, *pontos[0]])
        blocos.extend(pontos[1:])
    blocos.extend([Texto(n, depois=2)] for n in parte.notas)
    blocos[-1].append(Texto("", depois=2))  # espaço antes da parte seguinte
    return blocos


def _habitos_e_manutencao(
    pdf: _Documento, plano: Plano, idade: int | None, r: dict[str, str]
) -> None:
    """Hábitos, o que registar e «Depois das 16 semanas», a duas colunas."""
    pdf.add_page()
    blocos: list[list[Texto]] = []
    habitos = [[_negrito(x.titulo), Texto(x.descricao, depois=2.5)] for x in plano.habitos]
    if habitos:
        habitos[0].insert(0, _titulo_coluna(r["habitos"]))
    blocos.extend(habitos)

    a = plano.acompanhamento
    frequencia = {
        "semanal": r["pdf_registo_semanal"],
        "a_cada_4_semanas": r["pdf_registo_4_semanas"],
    }
    blocos.append(
        [
            _titulo_coluna(r["indicadores"]),
            _negrito(frequencia.get(a.frequencia, a.frequencia)),
            Texto(" · ".join(a.indicadores), depois=2),
        ]
    )
    if a.perguntas_revisao:
        perguntas = _pontos(a.perguntas_revisao)
        blocos.append([_subtitulo_coluna(r["pdf_perguntas_revisao"]), *perguntas[0]])
        blocos.extend(perguntas[1:])
    blocos[-1].append(Texto("", depois=2))

    m = orientacoes_manutencao(plano, idade)
    blocos.append([_titulo_coluna(r["manutencao"]), Texto(" ".join(m.introducao), depois=3)])
    blocos.extend(_blocos_parte(r["manutencao_treino"], m.treino))
    blocos.append([_negrito(r["manutencao_variar"]), *(Texto(p, depois=2) for p in m.variar)])
    blocos.append(
        [_negrito(r["manutencao_exercicios"]), Texto(" · ".join(m.exercicios_base), depois=4)]
    )
    blocos.extend(_blocos_parte(r["manutencao_alimentacao"], m.alimentacao))
    blocos.extend(_blocos_parte(r["manutencao_vigiar"], m.vigiar))
    blocos.extend(_blocos_parte(r["manutencao_recomecar"], m.recomecar))
    blocos.append(
        [
            Texto(
                r["gerado_por"].format(provedor=plano.provedor, versao=plano.versao_prompt),
                cor="texto_secundario",
            )
        ]
    )
    pdf.colunas(blocos)


def plano_pdf(plano: Plano, criado_em: datetime, idade: int | None = None) -> bytes:
    """O plano em PDF (A4). Os avisos ficam sempre na última página, em destaque.

    `idade`: a do questionário do plano (a recomendação da OMS só aparece com ≥ 65).
    """
    r = carregar_avisos().rotulos.plano
    pdf = _Documento(r["pdf_rodape"])
    c = comuns(plano.treino.fases)
    _inicio(pdf, plano, r, criado_em)
    _marcos(pdf, plano, r)
    _semana(pdf, plano, r)
    _em_todas_as_fases(pdf, plano, c, r)
    for fase in plano.treino.fases:
        _fase(pdf, fase, c, r)
    _alimentacao(pdf, plano, r)
    _habitos_e_manutencao(pdf, plano, idade, r)
    pdf.caixa_avisos(r["avisos"], list(plano.avisos))
    return bytes(pdf.output())
