"""Plano em PDF (A4), gerado no servidor com o fpdf2, sem serviços externos.

Letras do projeto (Fraunces nos títulos, Atkinson Hyperlegible no texto) em recursos/, em TTF
(scripts/converter_fontes.py). Texto base a 11,5 pt; cores da marca escolhidas para se lerem
impressas a preto e branco (texto em grafite, nada que dependa só da cor). Rótulos em
avisos.yaml (`rotulos.plano`), como no Markdown e na interface.

Sem dados identificativos: nem nome nem email, só «O seu plano Vigoria» e a data. Os avisos
ficam sempre na última página, numa caixa destacada.
"""

import re
from datetime import UTC, datetime
from importlib.resources import as_file, files
from typing import Any
from zoneinfo import ZoneInfo

from babel.dates import format_date
from fpdf import FPDF, FontFace, XPos, YPos
from fpdf.enums import MethodReturnValue

from vigoria.conteudo.carregar import carregar_avisos, carregar_exercicios, carregar_fases
from vigoria.modelos.plano import ExercicioPlano, Plano, TreinoFase
from vigoria.regras.textos import numero

RECURSOS = files("vigoria.exportacao") / "recursos"

# Paleta da marca (paginas/estilos.py, CORES; um teste confirma que são iguais).
CORES = {
    "principal": "#1F5C63",
    "principal_profundo": "#123F45",
    "cobre": "#A3532D",
    "texto": "#2E3338",
    "texto_secundario": "#5A6168",
    "nevoa": "#E4EFEE",
    "borda": "#DDD3C3",
    "aviso_fundo": "#FBF0D9",
    "aviso_borda": "#B7791F",
}

TEXTO_PT = 11.5  # letra base (pedido: pelo menos 11 pt)
LINHA = 6.0  # altura de linha do texto base, em mm
MARGEM = 18.0  # mm

# Caracteres que as letras do projeto não têm (subconjunto latino).
_SUBSTITUIR = str.maketrans({"≥": "pelo menos ", "≤": "até ", "→": "-", "⇄": "", "✓": "-"})


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

    def multi_cell(self, *args: Any, align: str = "L", **kwargs: Any) -> Any:
        """Alinhado à esquerda por omissão: o justificado deixa espaços irregulares."""
        return super().multi_cell(*args, align=align, **kwargs)

    def header(self) -> None:
        if self.page_no() == 1:
            return  # a capa tem o logotipo grande
        with as_file(RECURSOS / "vigoria_logo.svg") as logo:
            self.image(str(logo), x=MARGEM, y=9, h=6)
        self.set_y(MARGEM + 2)

    def footer(self) -> None:
        if self.page_no() == 1:
            return
        self.set_y(-MARGEM + 4)
        self.set_font("Atkinson", "", 10)
        self.set_text_color(*_rgb("texto_secundario"))
        texto = self._rodape.format(pagina=self.page_no(), total="{nb}")
        self.cell(0, 5, texto, align="C")
        self.set_text_color(*_rgb("texto"))

    # ------------------------------------------------------------ blocos de texto

    def titulo(self, texto: str, *, nova_pagina: bool = False) -> None:
        """Título de secção: Fraunces, petróleo profundo, com um filete por baixo."""
        if nova_pagina or self.get_y() > self.h - 70:
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

    def subtitulo(self, texto: str) -> None:
        if self.get_y() > self.h - 70:  # com espaço para, pelo menos, o primeiro bloco
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

    def tabela(self, cabecalho: list[str], linhas: list[list[str]], larguras: list[int]) -> None:
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

    def exercicio(self, x: ExercicioPlano, r: dict[str, str]) -> None:
        """Nome, prescrição (séries, repetições, descanso) e descrição, sem partir a página."""
        prescricao = []
        if x.series:
            prescricao.append(f"{x.series} {r['series'].lower()}")
        if x.repeticoes:
            # «repetições» só depois de números («12», «10-12»); «30s (cada lado)» fica assim.
            so_numeros = re.fullmatch(r"\d+(\s*[-–a]\s*\d+)?", x.repeticoes.strip())
            rotulo = f" {r['repeticoes'].lower()}" if so_numeros else ""
            prescricao.append(f"{x.repeticoes}{rotulo}")
        if x.descanso_s:
            prescricao.append(f"{r['descanso'].lower()} {_intervalo(*x.descanso_s, 's')}")
        extras = list(x.notas)
        if x.em_vez_de:
            extras.insert(0, r["em_vez_de"].format(nome=carregar_exercicios()[x.em_vez_de].nome))
        with self.unbreakable() as doc:
            doc.set_font("Atkinson", "B", 12.5)
            doc.set_text_color(*_rgb("principal_profundo"))
            doc.multi_cell(0, LINHA + 0.5, _limpo(x.nome), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            doc.set_text_color(*_rgb("texto"))
            if prescricao:
                doc.set_font("Atkinson", "B", TEXTO_PT)
                doc.multi_cell(
                    0, LINHA, " · ".join(prescricao), new_x=XPos.LMARGIN, new_y=YPos.NEXT
                )
            doc.set_font("Atkinson", "", TEXTO_PT)
            doc.multi_cell(0, LINHA, _limpo(x.descricao), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            for extra in extras:
                doc.set_font("Atkinson", "I", TEXTO_PT)
                doc.multi_cell(0, LINHA, _limpo(extra), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            doc.ln(3.5)

    def caixa_avisos(self, titulo: str, avisos: list[str]) -> None:
        """Avisos em destaque: caixa com borda grossa, fundo claro e texto em grafite.

        Se não couberem todos numa página, cada aviso tem a sua caixa (nunca partida).
        """
        self.add_page()
        self.set_font("Fraunces", "B", 21)
        self.set_text_color(*_rgb("principal_profundo"))
        self.multi_cell(0, 10, _limpo(titulo), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)
        alturas = [self._altura_aviso(a) for a in avisos]
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


# ---------------------------------------------------------------- secções


def _capa(pdf: _Documento, r: dict[str, str], criado_em: datetime) -> None:
    pdf.add_page()
    with as_file(RECURSOS / "vigoria_logo.svg") as logo:
        pdf.image(str(logo), x=MARGEM, y=40, h=18)
    pdf.set_y(95)
    pdf.set_font("Fraunces", "B", 34)
    pdf.set_text_color(*_rgb("principal_profundo"))
    pdf.multi_cell(0, 15, r["pdf_titulo"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*_rgb("cobre"))
    pdf.set_line_width(1)
    pdf.line(MARGEM, pdf.get_y() + 3, MARGEM + 40, pdf.get_y() + 3)
    pdf.ln(10)
    pdf.set_font("Atkinson", "", 15)
    pdf.set_text_color(*_rgb("texto"))
    pdf.multi_cell(130, 8, r["pdf_subtitulo"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)
    pdf.set_font("Atkinson", "B", 13)
    pdf.multi_cell(0, 7, r["pdf_data"].format(data=_data(criado_em)))
    pdf.set_y(pdf.h - MARGEM - 22)
    pdf.set_font("Atkinson", "", TEXTO_PT)
    pdf.set_text_color(*_rgb("texto_secundario"))
    pdf.multi_cell(0, LINHA, r["pdf_capa_nota"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*_rgb("texto"))


def _resumo(pdf: _Documento, plano: Plano, r: dict[str, str]) -> None:
    pdf.titulo(r["resumo"], nova_pagina=True)
    pdf.paragrafo(plano.resumo)
    if plano.notas_personalizadas:
        pdf.subtitulo(r["notas"])
        pdf.lista(list(plano.notas_personalizadas))


def _marcos(pdf: _Documento, plano: Plano, r: dict[str, str]) -> None:
    pdf.titulo(r["pdf_fases"])
    semanas = {f.numero: f.semanas for f in carregar_fases()}
    for fase in plano.treino.fases:
        s = semanas[fase.numero]
        pdf.rotulo(
            r["pdf_fase_semanas"].format(n=fase.numero, min=s.min, max=s.max) + f": {fase.nome}",
            fase.foco,
        )
    if pdf.get_y() > pdf.h - 110:  # a tabela dos marcos inteira, não partida numa linha
        pdf.add_page()
    pdf.subtitulo(r["marcos"])
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
        [26, 38, 22, 88],
    )
    sessao = plano.treino.estrutura_sessao
    pdf.subtitulo(r["estrutura_sessao"])
    for parte in ("aquecimento", "bloco_principal", "cardio_finalizador", "retorno_calma"):
        pdf.rotulo(r[parte], getattr(sessao, parte))


def _fase(pdf: _Documento, fase: TreinoFase, r: dict[str, str]) -> None:
    s = {f.numero: f.semanas for f in carregar_fases()}[fase.numero]
    pdf.titulo(f"{r['fase']} {fase.numero}: {fase.nome}", nova_pagina=True)
    pdf.paragrafo(r["pdf_fase_semanas"].format(n=fase.numero, min=s.min, max=s.max), cor="cobre")
    pdf.rotulo(r["foco"], fase.foco)
    pdf.paragrafo(r["esforco"].format(min=fase.esforco[0], max=fase.esforco[1]), estilo="I")
    pdf.subtitulo(r["forca_titulo"])
    for x in fase.forca:
        pdf.exercicio(x, r)
    if fase.cardio_finalizador is not None:
        duracao = r["cardio_duracao"].format(
            min=fase.cardio_duracao_min[0], max=fase.cardio_duracao_min[1]
        )
        pdf.subtitulo(f"{r['cardio_finalizador']} ({duracao})")
        pdf.exercicio(fase.cardio_finalizador, r)
    if fase.mobilidade_equilibrio:
        pdf.subtitulo(r["mobilidade_equilibrio"])
        for x in fase.mobilidade_equilibrio:
            pdf.exercicio(x, r)


def _alimentacao(pdf: _Documento, plano: Plano, r: dict[str, str]) -> None:
    refeicoes = carregar_avisos().rotulos.refeicoes
    a = plano.alimentacao
    pdf.titulo(r["alimentacao"])
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
    pdf.titulo(r["proteina"])
    if p.minimo_g is not None:
        pdf.paragrafo(
            r["proteina_valores"].format(
                minimo=p.minimo_g,
                maximo=p.maximo_g,
                por_refeicao_min=p.por_refeicao_min_g,
                por_refeicao_max=p.por_refeicao_max_g,
            ),
            estilo="B",
        )
    if p.nota:
        pdf.paragrafo(p.nota)

    h = plano.hidratacao
    pdf.titulo(r["hidratacao"])
    if h.valores.central_ml is not None:
        pdf.paragrafo(
            r["hidratacao_valores"].format(
                minimo=h.valores.minimo_ml, maximo=h.valores.maximo_ml, central=h.valores.central_ml
            ),
            estilo="B",
        )
    if h.valores.nota:
        pdf.paragrafo(h.valores.nota)
    if h.dicas:
        pdf.lista(list(h.dicas))


def _habitos(pdf: _Documento, plano: Plano, r: dict[str, str]) -> None:
    pdf.titulo(r["habitos"])
    for x in plano.habitos:
        pdf.rotulo(x.titulo, x.descricao)

    a = plano.acompanhamento
    pdf.titulo(r["indicadores"])
    frequencia = {
        "semanal": r["pdf_registo_semanal"],
        "a_cada_4_semanas": r["pdf_registo_4_semanas"],
    }
    pdf.paragrafo(frequencia.get(a.frequencia, a.frequencia), estilo="B")
    pdf.lista(list(a.indicadores))
    if a.perguntas_revisao:
        pdf.subtitulo(r["pdf_perguntas_revisao"])
        pdf.lista(list(a.perguntas_revisao))
    pdf.paragrafo(
        r["gerado_por"].format(provedor=plano.provedor, versao=plano.versao_prompt),
        cor="texto_secundario",
    )


def plano_pdf(plano: Plano, criado_em: datetime) -> bytes:
    """O plano em PDF (A4). Os avisos ficam sempre na última página, em destaque."""
    r = carregar_avisos().rotulos.plano
    pdf = _Documento(r["pdf_rodape"])
    _capa(pdf, r, criado_em)
    _resumo(pdf, plano, r)
    _marcos(pdf, plano, r)
    _semana(pdf, plano, r)
    for fase in plano.treino.fases:
        _fase(pdf, fase, r)
    _alimentacao(pdf, plano, r)
    _habitos(pdf, plano, r)
    pdf.caixa_avisos(r["avisos"], list(plano.avisos))
    return bytes(pdf.output())
