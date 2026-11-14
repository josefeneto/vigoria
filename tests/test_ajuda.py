"""Página de Ajuda (Fase 8B): conteúdo, marcadores, variantes por ambiente e página."""

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from paginas import textos as t
from vigoria.config import obter_configuracao
from vigoria.conteudo.carregar import ErroConteudo, carregar_ajuda, carregar_avisos
from vigoria.interface import ajuda as modulo
from vigoria.interface.ajuda import VALORES, ajuda, marcadores, preencher
from vigoria.motor.voz import encontrar_termos
from vigoria.regras import lembretes
from vigoria.regras.calculos import SEMANAS_PROGRAMA

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "app.py")
AJUDA = "paginas/ajuda.py"
TEMAS = ["como_funciona", "plano", "registo", "lembretes", "seguranca", "conta", "contacto"]


def _textos_crus() -> list[str]:
    return [
        texto
        for tema in carregar_ajuda().temas
        for texto in (tema.titulo, *(x for p in tema.perguntas for x in (p.pergunta, p.resposta)))
    ]


def _resposta(id_: str, ambiente: str | None = None) -> str:
    return next(p.resposta for tema in ajuda(ambiente) for p in tema.perguntas if p.id == id_)


def _ids(ambiente: str | None) -> set[str]:
    return {p.id for tema in ajuda(ambiente) for p in tema.perguntas}


# ---------------------------------------------------------------- Conteúdo


def test_temas_pela_ordem_pedida() -> None:
    assert [tema.id for tema in carregar_ajuda().temas] == TEMAS


def test_cada_resposta_tem_de_uma_a_tres_frases() -> None:
    for tema in ajuda(None):
        for p in tema.perguntas:
            frases = [f for f in re.split(r"(?<=[.!?])\s+", p.resposta.strip()) if f]
            assert 1 <= len(frases) <= 3, p.id


def test_sem_algarismos_no_yaml() -> None:
    # Os números vêm sempre do código, por marcadores.
    for texto in _textos_crus():
        assert not re.search(r"\d", texto), texto


def test_todos_os_marcadores_existem_e_ficam_preenchidos() -> None:
    usados = set().union(*(marcadores(x) for x in _textos_crus()))
    assert usados and usados <= VALORES.keys()
    for tema in ajuda(None):
        for texto in (tema.titulo, *(x for p in tema.perguntas for x in (p.pergunta, p.resposta))):
            assert "{" not in texto and "}" not in texto, texto


def test_marcador_desconhecido_da_erro() -> None:
    with pytest.raises(ErroConteudo, match="inventado"):
        preencher("São {inventado} dias.")


def test_numeros_vem_das_constantes(monkeypatch: pytest.MonkeyPatch) -> None:
    quando = _resposta("quando")
    for n in (
        lembretes.DIAS_PRIMEIRO,
        lembretes.DIAS_SEGUNDO,
        lembretes.MAXIMO_POR_PERIODO,
        lembretes.DIAS_MAXIMO,
    ):
        assert f" {n} " in quando
    assert f"{lembretes.PERIODOS_PARA_SUSPENDER} períodos" in _resposta("suspensos")
    assert f"{SEMANAS_PROGRAMA} semanas" in _resposta("semanas")
    assert f"semana {SEMANAS_PROGRAMA + 1}" in _resposta("semanas")
    # Se a regra mudar, a Ajuda muda com ela.
    monkeypatch.setitem(modulo.VALORES, "dias_primeiro", 3)
    assert "chega 3 dias depois" in _resposta("quando")


def test_rotulos_iguais_aos_da_interface() -> None:
    assert f"«{t.CONTA_LEMBRETES_EMAIL}»" in _resposta("desligar")
    assert f"«{t.CONTA_ACOMPANHAMENTO_ATIVO}»" in _resposta("desligar_acompanhamento")
    assert f"«{t.DESCARREGAR_PDF}»" in _resposta("pdf")
    assert f"«{t.CONTA_APAGAR_TITULO}»" in _resposta("apagar_conta")
    for seccao in ("Resumo", "Treino", "Alimentação", "Hábitos", "Acompanhamento", "Manutenção"):
        assert seccao in _resposta("seccoes")
    assert "geral@vigoria.pt" in _resposta("email")


def test_sem_promessas_termos_proibidos_nem_brasileirismos() -> None:
    avisos = carregar_avisos()
    texto = "\n".join(
        x
        for tema in ajuda(None)
        for x in (tema.titulo, *(y for p in tema.perguntas for y in (p.pergunta, p.resposta)))
    )
    for termos in (avisos.lista_negra.promessas, avisos.lista_negra.termos, avisos.brasileirismos):
        assert encontrar_termos(termos, texto) == ()


# ---------------------------------------------------------------- Variantes por ambiente


def test_demo_tem_servidores_fora_da_ue() -> None:
    ids = _ids("demo")
    assert "dados_onde_demo" in ids
    assert "dados_onde" not in ids
    assert "fora da UE" in _resposta("dados_onde_demo", "demo")


@pytest.mark.parametrize("ambiente", ["local", "producao"])
def test_local_e_producao_sem_as_perguntas_da_demo(ambiente: str) -> None:
    ids = _ids(ambiente)
    assert "dados_onde" in ids
    assert "dados_onde_demo" not in ids


@pytest.mark.parametrize("ambiente", ["local", "demo", "producao"])
def test_pergunta_do_convite_so_com_acesso_por_convite(ambiente: str) -> None:
    def ids(acesso: str) -> set[str]:
        return {p.id for tema in ajuda(ambiente, acesso=acesso) for p in tema.perguntas}

    assert "so_convite" in ids("convidados")
    assert "so_convite" not in ids("aberto")


@pytest.mark.parametrize("ambiente", ["local", "demo", "producao"])
def test_uma_so_pergunta_sobre_onde_ficam_os_dados(ambiente: str) -> None:
    perguntas = [p.pergunta for tema in ajuda(ambiente) for p in tema.perguntas]
    assert perguntas.count("Onde ficam os meus dados?") == 1


def test_tema_pedido_passa_para_o_inicio() -> None:
    assert [tema.id for tema in ajuda("local", "lembretes")] == [
        "lembretes",
        *(x for x in TEMAS if x != "lembretes"),
    ]
    assert [tema.id for tema in ajuda("local", "nao_existe")] == TEMAS


# ---------------------------------------------------------------- Página


def _titulos_expanders(at: AppTest) -> list[tuple[str, bool]]:
    return [(e.label, e.proto.expanded) for e in at.expander]


def test_pagina_sem_sessao(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "0")
    obter_configuracao.cache_clear()
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page(AJUDA).run()
    assert not at.exception
    assert at.title[0].value == t.AJUDA_TITULO
    assert [s.value for s in at.subheader][0] == "Como funciona"
    assert all(not aberto for _, aberto in _titulos_expanders(at))
    obter_configuracao.cache_clear()


def test_pagina_com_tema_pedido_abre_esse_tema_primeiro() -> None:
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["tema"] = "lembretes"
    at.run()
    at.switch_page(AJUDA)
    at.query_params["tema"] = "lembretes"
    at.run()
    assert not at.exception
    assert at.subheader[0].value == "Lembretes por email"
    expanders = _titulos_expanders(at)
    assert expanders[0] == ("Quando chegam os lembretes?", True)
    assert sum(aberto for _, aberto in expanders) == 3


@pytest.mark.parametrize("acesso", ["convidados", "aberto"])
def test_pagina_em_demo_mostra_a_variante_da_demo(
    monkeypatch: pytest.MonkeyPatch, acesso: str
) -> None:
    monkeypatch.setenv("AMBIENTE", "demo")
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "gemini")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "0")
    monkeypatch.setenv("VIGORIA_ACESSO", acesso)
    obter_configuracao.cache_clear()
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page(AJUDA).run()
    assert not at.exception
    rotulos = [r for r, _ in _titulos_expanders(at)]
    assert ("Porque é que não consigo usar a Vigoria?" in rotulos) is (acesso == "convidados")
    texto = "\n".join(m.value for m in at.markdown)
    assert "fora da UE" in texto
    obter_configuracao.cache_clear()


def _ligacoes(at: AppTest) -> list[object]:
    return [p.proto for p in at.get("page_link")]


def test_inicio_tem_ligacao_como_funciona() -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    ligacoes = [p for p in _ligacoes(at) if p.label == t.COMO_FUNCIONA_LIGACAO]
    assert len(ligacoes) == 1
    assert ligacoes[0].page.endswith("ajuda")
    assert "tema=como_funciona" in ligacoes[0].query_string
