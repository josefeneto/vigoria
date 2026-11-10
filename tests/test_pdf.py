"""Plano em PDF (exportacao/pdf.py) com a persona de teste e o fornecedor simulado.

Sem biblioteca para ler PDFs: os testes registam o texto que o gerador escreve em cada
página (e o tamanho da letra) e confirmam o ficheiro pelo cabeçalho e pelo número de páginas.
"""

import re
import warnings
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from vigoria.conteudo.carregar import carregar_manutencao
from vigoria.exportacao import pdf
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor.pipeline import gerar_plano_verificado

RAIZ = Path(__file__).resolve().parents[1]
DATA = datetime(2026, 11, 4, 17, 30, tzinfo=UTC)
# Fase 5D: era 18. Com todo o texto e letra de pelo menos 11 pt: 11 na persona de teste
# (objetivo do José, 10/11/2026) e até 12 nas outras (a da osteoporose tem mais notas).
MAX_PAGINAS_TESTE = 11
MAX_PAGINAS = 12
OCUPACAO_MINIMA = 0.25  # nenhuma página quase vazia, exceto a última
PERSONAS = [
    "persona_teste",
    "persona_50_alta",
    "persona_imc36",
    "persona_osteoporose",
    "persona_renal",
]


@cache
def _plano(persona: str = "persona_teste") -> Plano:
    q = Questionario.model_validate_json((RAIZ / "exemplos" / f"{persona}.json").read_text("utf-8"))
    return gerar_plano_verificado(q, ProvedorSimulado(), progresso=lambda _: None).plano


def _paginas(dados: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", dados))


@pytest.fixture
def escrito(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, float, str]]:
    """(página, tamanho da letra em pt, texto) de cada bloco de texto escrito."""
    registo: list[tuple[int, float, str]] = []
    original = pdf._Documento.multi_cell
    a_medir = [False]  # o fpdf2 mede (dry_run) chamando de novo multi_cell, sem dry_run

    def espiao(self: pdf._Documento, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("dry_run"):
            a_medir[0] = True
            try:
                return original(self, *args, **kwargs)
            finally:
                a_medir[0] = False
        if not a_medir[0]:
            texto = kwargs.get("text", args[2] if len(args) > 2 else "")
            registo.append((self.page_no(), self.font_size_pt, str(texto)))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(pdf._Documento, "multi_cell", espiao)
    return registo


@pytest.fixture
def fundos(monkeypatch: pytest.MonkeyPatch) -> dict[int, float]:
    """Página → y mais baixo onde acabou um bloco de texto (para medir a ocupação)."""
    registo: dict[int, float] = {}
    original = pdf._Documento.multi_cell
    a_medir = [False]

    def espiao(self: pdf._Documento, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("dry_run"):
            a_medir[0] = True
            try:
                return original(self, *args, **kwargs)
            finally:
                a_medir[0] = False
        resultado = original(self, *args, **kwargs)
        if not a_medir[0]:  # self.y e self.page: get_y() não se pode usar em unbreakable()
            registo[self.page] = max(registo.get(self.page, 0.0), self.y)
        return resultado

    monkeypatch.setattr(pdf._Documento, "multi_cell", espiao)
    return registo


def _sem_falhas_de_letra(caplog: pytest.LogCaptureFixture) -> None:
    """O fpdf2 regista (não avisa com warnings) os caracteres que faltam numa letra."""
    falhas = [r.getMessage() for r in caplog.records if "missing the following glyphs" in r.msg]
    assert not falhas, falhas


def test_gera_o_pdf_da_persona_de_teste_sem_erros(caplog: pytest.LogCaptureFixture) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dados = pdf.plano_pdf(_plano(), DATA)
    _sem_falhas_de_letra(caplog)
    assert dados.startswith(b"%PDF-")
    assert dados.rstrip().endswith(b"%%EOF")
    assert _paginas(dados) <= MAX_PAGINAS_TESTE


@pytest.mark.parametrize(
    "persona", ["persona_50_alta", "persona_imc36", "persona_osteoporose", "persona_renal"]
)
def test_gera_o_pdf_das_outras_personas(persona: str, caplog: pytest.LogCaptureFixture) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        dados = pdf.plano_pdf(_plano(persona), DATA)
    _sem_falhas_de_letra(caplog)
    assert _paginas(dados) <= MAX_PAGINAS


def test_conteudo_capa_seccoes_e_avisos_na_ultima_pagina(
    escrito: list[tuple[int, float, str]],
) -> None:
    plano = _plano()
    dados = pdf.plano_pdf(plano, DATA)
    ultima = _paginas(dados)
    capa = [texto for pagina, _, texto in escrito if pagina == 1]
    assert "O seu plano Vigoria" in capa
    assert "Criado a 4 de novembro de 2026" in capa
    todo = "\n".join(texto for _, _, texto in escrito)
    for titulo in ("Resumo", "Marcos", "Semana-tipo", "Alimentação", "Proteína", "Hidratação"):
        assert titulo in todo
    for titulo in ("Hábitos", "O que registar"):
        assert titulo in todo
    for fase in plano.treino.fases:
        assert f"Fase {fase.numero}: {fase.nome}" in todo
        for x in fase.forca:
            assert x.nome in todo and x.descricao in todo
    na_ultima = [texto for pagina, _, texto in escrito if pagina == ultima]
    # Os avisos fecham o PDF: na última página e nada escrito depois deles.
    inicio = na_ultima.index("Avisos importantes")
    assert [pdf._limpo(a) for a in plano.avisos] == na_ultima[inicio + 1 :]
    for aviso in plano.avisos:
        assert all(aviso not in t for p, _, t in escrito if p < ultima)  # só na última


def test_manutencao_antes_dos_avisos_e_oms_so_com_65_anos(
    escrito: list[tuple[int, float, str]],
) -> None:
    oms = pdf._limpo(carregar_manutencao().treino.oms_65)
    ultima = _paginas(pdf.plano_pdf(_plano(), DATA, 68))
    paginas = {texto: pagina for pagina, _, texto in escrito}
    assert paginas["Depois das 16 semanas"] < ultima  # antes da página dos avisos
    assert "Recomeçar" in paginas and oms in paginas
    escrito.clear()
    pdf.plano_pdf(_plano("persona_50_alta"), DATA, 50)
    textos = [texto for _, _, texto in escrito]
    assert "Depois das 16 semanas" in textos and oms not in textos


def test_hifenes_e_espacos_tipograficos_sem_falhas_de_letra(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # O Groq escreveu «pequeno‑almoço» com U+2011, que as letras do PDF não têm.
    especiais = "pequeno‑almoço, bem‐estar, 10‒15 min, 2 x"
    plano = _plano()
    plano = plano.model_copy(update={"resumo": f"{plano.resumo} {especiais}"})
    pdf.plano_pdf(plano, DATA)
    _sem_falhas_de_letra(caplog)
    assert pdf._limpo(especiais) == "pequeno-almoço, bem-estar, 10-15 min, 2 x"


def test_substitutos_existem_em_todas_as_letras() -> None:
    from fontTools.ttLib import TTFont

    substitutos = {c for v in pdf._SUBSTITUIR.values() if v for c in str(v)}
    for ficheiro in pdf.RECURSOS.iterdir():
        if ficheiro.name.endswith(".ttf"):
            with ficheiro.open("rb") as f:
                cmap = TTFont(f).getBestCmap()
            assert all(ord(c) in cmap for c in substitutos), ficheiro.name


def test_letra_base_de_pelo_menos_11_pt(escrito: list[tuple[int, float, str]]) -> None:
    pdf.plano_pdf(_plano(), DATA)
    assert min(tamanho for _, tamanho, _ in escrito) >= 11


def test_sem_dados_identificativos(escrito: list[tuple[int, float, str]]) -> None:
    dados = pdf.plano_pdf(_plano(), DATA)
    todo = "\n".join(texto for _, _, texto in escrito)
    assert "@" not in todo
    assert b"@" not in dados.split(b"stream")[0]  # metadados (título, autor) sem email


def test_prioridades_sem_fase_repetida() -> None:
    assert pdf._sem_prefixo_fase("Fase 1: criar a rotina") == "criar a rotina"
    assert pdf._sem_prefixo_fase("fase 2 — mais legumes") == "mais legumes"
    assert pdf._sem_prefixo_fase("Mais legumes na fase 3") == "Mais legumes na fase 3"


def test_cores_iguais_as_da_marca() -> None:
    from paginas.estilos import CORES

    for nome, valor in pdf.CORES.items():
        assert CORES[nome] == valor


def test_logotipo_do_pdf_igual_ao_da_marca() -> None:
    copia = (pdf.RECURSOS / "vigoria_logo.svg").read_bytes()
    assert copia == (RAIZ / "assets" / "marca" / "vigoria_logo.svg").read_bytes()


@pytest.mark.parametrize("persona", PERSONAS)
def test_cada_fase_numa_so_pagina(persona: str, escrito: list[tuple[int, float, str]]) -> None:
    plano = _plano(persona)
    pdf.plano_pdf(plano, DATA)
    textos = [(p, t) for p, _, t in escrito]
    titulos = [f"Fase {f.numero}: {f.nome}" for f in plano.treino.fases]
    inicios = [next(i for i, (_, t) in enumerate(textos) if t == titulo) for titulo in titulos]
    fim = next(i for i, (_, t) in enumerate(textos) if t == "Alimentação")
    for a, b in zip(inicios, [*inicios[1:], fim], strict=True):
        paginas = {p for p, _ in textos[a:b]}
        assert len(paginas) == 1, (persona, textos[a][1], paginas)


def test_mobilidade_e_cardio_uma_so_vez(escrito: list[tuple[int, float, str]]) -> None:
    plano = _plano()
    pdf.plano_pdf(plano, DATA)
    textos = [t for _, _, t in escrito]
    c = pdf.comuns(plano.treino.fases)
    assert c.cardio is not None and c.mobilidade_equilibrio
    for x in (c.cardio, *c.mobilidade_equilibrio):
        assert textos.count(x.nome) == 1, x.nome
    assert "Em todas as fases" in textos


def test_comuns_com_fases_iguais_e_com_uma_diferente() -> None:
    fases = _plano().treino.fases
    c = pdf.comuns(fases)
    assert c.cardio == fases[0].cardio_finalizador
    assert c.mobilidade_equilibrio == fases[0].mobilidade_equilibrio
    assert all(c.diferencas(f) == () for f in fases)
    # Uma fase com outro cardio e sem o último exercício de mobilidade.
    outro = next(
        x
        for f in _plano("persona_osteoporose").treino.fases
        for x in [f.cardio_finalizador]
        if x is not None and x != c.cardio
    )
    diferente = fases[3].model_copy(
        update={
            "cardio_finalizador": outro,
            "mobilidade_equilibrio": fases[3].mobilidade_equilibrio[:-1],
        }
    )
    c2 = pdf.comuns([*fases[:3], diferente])
    assert c2.cardio == c.cardio  # o mais frequente
    assert c2.mobilidade_equilibrio == fases[0].mobilidade_equilibrio[:-1]
    assert c2.diferencas(diferente) == (outro,)
    assert c2.diferencas(fases[0]) == (fases[0].mobilidade_equilibrio[-1],)


def test_osteoporose_mostra_o_cardio_diferente_so_na_sua_fase(
    escrito: list[tuple[int, float, str]],
) -> None:
    plano = _plano("persona_osteoporose")
    pdf.plano_pdf(plano, DATA)
    textos = [t for _, _, t in escrito]
    c = pdf.comuns(plano.treino.fases)
    proprios = [x for f in plano.treino.fases for x in c.diferencas(f)]
    assert proprios  # caminhada na fase 4 em vez da marcha
    assert any(t.startswith("Só nesta fase · Cardio finalizador") for t in textos)
    for x in proprios:
        assert x.nome in textos


def test_icone_em_todos_os_cartoes_de_exercicio(monkeypatch: pytest.MonkeyPatch) -> None:
    desenhados: list[str] = []
    original = pdf._icone_svg

    def espiao(id_exercicio: str) -> Any:
        desenhados.append(id_exercicio)
        return original(id_exercicio)

    monkeypatch.setattr(pdf, "_icone_svg", espiao)
    plano = _plano()
    pdf.plano_pdf(plano, DATA)
    forca = {x.id for f in plano.treino.fases for x in f.forca}
    assert forca <= set(desenhados)


@pytest.mark.parametrize("persona", PERSONAS)
def test_nenhuma_pagina_quase_vazia(persona: str, fundos: dict[int, float]) -> None:
    """Pelo menos 25 % da área de texto ocupada em todas as páginas, exceto a última
    (nada de páginas com um só cartão ou uma linha solta)."""
    total = _paginas(pdf.plano_pdf(_plano(persona), DATA))
    altura = pdf._Documento("").fundo - pdf.TOPO_PAGINA
    for pagina in range(1, total):
        ocupacao = (fundos.get(pagina, pdf.TOPO_PAGINA) - pdf.TOPO_PAGINA) / altura
        assert ocupacao >= OCUPACAO_MINIMA, (persona, pagina, round(ocupacao, 2))


def test_em_todas_as_fases_na_pagina_da_sessao(escrito: list[tuple[int, float, str]]) -> None:
    plano = _plano()
    pdf.plano_pdf(plano, DATA)
    paginas = {t: p for p, _, t in escrito}
    c = pdf.comuns(plano.treino.fases)
    assert paginas["Em todas as fases"] == paginas["Como é cada sessão"]
    for x in c.mobilidade_equilibrio:
        assert paginas[x.nome] == paginas["Como é cada sessão"], x.nome


def test_tabela_nunca_partida_entre_paginas() -> None:
    doc = pdf._Documento("p. {pagina}")
    doc.add_page()
    linhas = [["Segunda-feira", "Força", "30 min", "Circuito de força da fase."]] * 7
    doc.set_y(doc.fundo - 30)  # não cabe: passa inteira para a página seguinte
    doc.tabela(["Dia", "Atividade", "Duração", "Descrição"], linhas, [26, 38, 22, 88])
    assert doc.page_no() == 2
    altura = doc._altura_tabela(
        [["Dia", "Atividade", "Duração", "Descrição"], *linhas], [26, 38, 22, 88]
    )
    assert doc.get_y() == pytest.approx(pdf.TOPO_PAGINA + altura + 4, abs=1)


def test_proteina_e_hidratacao_na_pagina_da_alimentacao(
    escrito: list[tuple[int, float, str]],
) -> None:
    pdf.plano_pdf(_plano(), DATA)
    paginas: dict[str, int] = {}
    for p, _, t in escrito:
        paginas.setdefault(t, p)  # a primeira «Alimentação» (há outra na manutenção)
    assert paginas["Proteína"] == paginas["Hidratação"] == paginas["Alimentação"]
