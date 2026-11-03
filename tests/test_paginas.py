"""Páginas Streamlit, sem browser (streamlit.testing.AppTest). Nunca chamam uma LLM real:
a geração usa o fornecedor simulado (VIGORIA_PROVEDOR_LLM=simulado, AMBIENTE=local)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from vigoria.config import obter_configuracao
from vigoria.interface.estado import chave, para_estado
from vigoria.interface.passos import respostas_de_questionario
from vigoria.modelos.questionario import Questionario
from vigoria.regras import textos

RAIZ = Path(__file__).resolve().parents[1]
APP = str(RAIZ / "app.py")
QUESTIONARIO = "paginas/questionario.py"


@pytest.fixture(autouse=True)
def _simulado(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fornecedor simulado, utilizador local fictício e uma base SQLite nova por teste."""
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "simulado")
    monkeypatch.setenv("VIGORIA_PROVEDOR_RESERVA", "")
    monkeypatch.setenv("AMBIENTE", "local")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "1")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'vigoria.db'}")
    obter_configuracao.cache_clear()
    yield
    obter_configuracao.cache_clear()


def _app() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page(QUESTIONARIO).run()
    assert not at.exception
    return at


def _texto(at: AppTest) -> str:
    """Markdown e HTML da página (os cartões do plano são HTML, desde a Fase 5B)."""
    return "\n".join([m.value for m in at.markdown] + [h.proto.body for h in at.get("html")])


def _botao(at: AppTest, rotulo: str):  # type: ignore[no-untyped-def]
    return next(b for b in at.button if b.label == rotulo)


def _persona(at: AppTest, **alteracoes: object) -> None:
    q = Questionario.model_validate_json(
        (RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8")
    )
    for k, v in para_estado(respostas_de_questionario(q) | alteracoes).items():
        at.session_state[k] = v


def test_passo_0_nao_avanca_sem_consentimento() -> None:
    at = _app()
    _botao(at, "Seguinte").click().run()
    assert at.session_state["passo"] == "0"
    assert at.error  # mensagem geral e uma por caixa
    for caixa in at.checkbox:
        caixa.check()
    at.run()
    _botao(at, "Seguinte").click().run()
    assert at.session_state["passo"] == "1"
    assert not at.exception


def test_primeiro_ecra_tem_anterior_que_volta_ao_inicio() -> None:
    at = _app()
    _botao(at, "Anterior").click().run()
    assert not at.exception
    assert any(b.label == "Começar o questionário" for b in at.button)  # página de início


def test_numeros_pedidos_sem_casas_decimais() -> None:
    at = _app()
    _persona(at)
    at.session_state["passo"] = "1"
    at.run()
    assert not at.exception
    assert {n.label: n.value for n in at.number_input} == {
        "Idade (anos)": 68,
        "Altura (cm)": 172,
        "Peso (kg)": 94,
        "Horas de sono por noite": 7,
        "Perímetro da cintura (cm)": 108,
    }
    assert all(type(n.value) is int for n in at.number_input)
    assert all(n.min == 0 for n in at.number_input)  # começam em 0: setas ativas
    at.session_state["passo"] = "4b"
    at.run()
    espirituosas = at.selectbox[0]
    assert "0,5 dl" in espirituosas.options and espirituosas.value == 0


def test_gravidez_termina_sem_guardar_respostas() -> None:
    at = _app()
    _persona(at, condicoes=["gravidez"], condicoes_controladas={})
    at.session_state["passo"] = "2a"
    at.run()
    _botao(at, "Seguinte").click().run()
    assert not at.exception
    assert any(textos.GRAVIDEZ in i.value for i in at.info)
    assert at.session_state[chave("peso_kg")] == 0  # respostas apagadas (valor inicial)
    assert "resultado" not in at.session_state


def test_articulacoes_so_aparecem_com_dor_articular() -> None:
    at = _app()
    _persona(at)
    at.session_state["passo"] = "2a"
    at.run()
    rotulos = [p.label for p in at.get("button_group")]
    assert "Em que articulações?" not in rotulos
    at.session_state[chave("condicoes")] = ["dor_articular_persistente"]
    at.run()
    assert "Em que articulações?" in [p.label for p in at.get("button_group")]


def test_revisao_mostra_decisoes_e_gera_plano_simulado() -> None:
    at = _app()
    _persona(at)
    at.session_state["passo"] = "7"
    at.run()
    assert not at.exception
    texto = "\n".join(m.value for m in at.markdown)
    assert "à semana 16" in texto  # objetivo ajustado da persona
    _botao(at, "Gerar o meu plano").click().run(timeout=60)
    assert not at.exception
    resultado = at.session_state["resultado"]
    assert resultado.plano.provedor == "simulado"
    assert resultado.id > 0  # guardado na conta
    assert "erro_guardar" not in at.session_state


def test_plano_mostra_faixa_simulado_e_avisos_em_cada_seccao() -> None:
    at = _app()
    _persona(at)
    at.session_state["passo"] = "7"
    at.run()
    _botao(at, "Gerar o meu plano").click().run(timeout=60)
    at.switch_page("paginas/plano.py").run()
    assert not at.exception
    assert "Plano simulado (persona de teste)" in [w.proto.title for w in at.warning]
    # Cintura sem número por fase (REGRAS §5): o mesmo texto, mostrado uma só vez.
    assert _texto(at).count("limiar de risco de 94 cm") == 1
    for seccao in ("resumo", "treino", "alimentacao", "habitos", "acompanhamento"):
        at.session_state["plano_seccao"] = seccao
        at.run()
        assert not at.exception
        titulos = [w.proto.title for w in at.warning]
        assert titulos.count("Avisos importantes") == 1, seccao  # em todas as secções
    at.session_state["plano_seccao"] = "treino"
    at.run()
    assert "Em vez de:" not in _texto(at)  # fase 1: a limitação ligeira só troca nas fases 2 a 4
    at.session_state["plano_fase"] = 2
    at.run()
    assert "Em vez de:" in _texto(at)


def test_faixa_de_demonstracao_so_em_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    aviso = "Versão de demonstração — não introduza dados reais de saúde."
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not any(aviso in w.value for w in at.warning)
    monkeypatch.setenv("AMBIENTE", "demo")
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "gemini")
    monkeypatch.setenv("VIGORIA_UTILIZADOR_LOCAL", "0")  # sem sessão: só as páginas públicas
    obter_configuracao.cache_clear()
    for pagina in ("paginas/inicio.py", "paginas/privacidade.py"):
        at.switch_page(pagina).run()
        assert not at.exception
        assert any(aviso in w.value for w in at.warning), pagina


def test_plano_sem_resultado_convida_ao_questionario() -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.switch_page("paginas/plano.py").run()
    assert not at.exception
    assert at.info


def test_inicio_em_faixas_com_video_e_dois_botoes() -> None:
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    html = "\n".join(h.proto.body for h in at.get("html"))
    assert "<video" in html and "app/static/video/inicio.mp4" in html
    # A capa vem embutida como fundo da caixa: vê-se mesmo que o vídeo demore ou falhe.
    assert 'class="v-video" style="background-image:url(data:image/webp;base64,' in html
    assert 'addEventListener("error"' in html
    assert " autoplay" not in html  # só arranca por código, se o sistema não pedir menos movimento
    assert "Como funciona" in html and "Pronto para começar?" in html
    assert [b.label for b in at.button].count("Começar o questionário") == 2


def test_promessa_sem_travessao_no_inicio_da_linha() -> None:
    from paginas import textos as t

    assert "\u00a0— para" in t.PROMESSA
    assert " — " not in t.PROMESSA
