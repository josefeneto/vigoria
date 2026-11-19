"""Tai Chi (opcional), Fase 10F: REGRAS_DOMINIO §5.2 (T1 a T7)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from paginas import componentes
from vigoria.conteudo.carregar import ConteudoTaiChi, NivelLigacao, carregar_taichi
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import TaiChi
from vigoria.modelos.questionario import Intensidade, Questionario
from vigoria.motor.danca import construir_danca
from vigoria.motor.pipeline import gerar_plano_verificado
from vigoria.motor.taichi import construir_taichi, ligacoes_taichi
from vigoria.regras import taichi as regras
from vigoria.regras.atividades import minutos_atividade
from vigoria.regras.elegibilidade import Modo

RAIZ = Path(__file__).resolve().parents[1]
L, M, A = Intensidade.LIGEIRA, Intensidade.MEDIA, Intensidade.ALTA


def _q(**alteracoes: Any) -> Questionario:
    """Persona de teste sem condições nem limitações, com Tai Chi; validada de novo."""
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8"))
    dados |= {
        "condicoes": ["nenhuma"],
        "condicoes_controladas": {},
        "limitacoes": ["nenhuma"],
        "limitacoes_gravidade": {},
        "preferencias": ["caminhada", "tai_chi"],
    }
    dados |= alteracoes
    return Questionario.model_validate(dados)


def _e(intensidade: Intensidade | None = M) -> Estrategia:
    return Estrategia(
        pode_gerar_plano=intensidade is not None,
        modo=Modo.BASE,
        motivos=(),
        intensidade_pedida=M,
        intensidade_efetiva=intensidade,
    )


def _taichi(intensidade: Intensidade, so_ligeira: bool = False) -> TaiChi:
    return TaiChi(minutos=(10, 10, 10, 10), intensidade=intensidade, so_ligeira=so_ligeira)


# ---------------------------------------------------------------- T1


def test_t1_so_com_taichi_nas_preferencias() -> None:
    assert regras.tem_taichi(_q())
    sem = _q(preferencias=["caminhada", "danca"])
    assert not regras.tem_taichi(sem)
    assert construir_taichi(_e(), sem) is None
    assert construir_taichi(_e(), _q()) is not None


def test_t1_sem_intensidade_efetiva_nao_ha_bloco() -> None:
    assert construir_taichi(_e(None), _q()) is None


def test_t1_no_plano_gerado() -> None:
    plano = gerar_plano_verificado(_q(), ProvedorSimulado(), progresso=lambda _: None).plano
    assert plano.taichi is not None and plano.danca is None
    sem = _q(preferencias=["caminhada"])
    plano = gerar_plano_verificado(sem, ProvedorSimulado(), progresso=lambda _: None).plano
    assert plano.taichi is None


def test_plano_antigo_sem_taichi_continua_valido() -> None:
    plano = gerar_plano_verificado(_q(), ProvedorSimulado(), progresso=lambda _: None).plano
    dados = plano.model_dump(mode="json")
    del dados["taichi"]
    assert type(plano).model_validate(dados).taichi is None


# ---------------------------------------------------------------- T2, T4 e T5 (textos)


def test_t2_estrutura_aquecimento_curto_taichi_retorno() -> None:
    c = carregar_taichi().textos
    assert "aquecimento curto" in c.estrutura and "retorno à calma" in c.estrutura
    assert "articulações" in c.aquecimento and "respire" in c.aquecimento


def test_t4_nao_substitui_o_cardio_nem_conta_como_cardio() -> None:
    c = carregar_taichi().textos
    assert "não conta como minutos de cardio" in c.nao_cardio
    # Decisões de 18/11/2026: nos dias sem treino, antes ou depois da caminhada leve; nos
    # dias de treino, só em vez do retorno à calma, com a mesma duração.
    assert "antes ou depois da caminhada leve" in c.dias_sem_treino
    assert "em vez do retorno à calma" in c.dias_treino and "mesma duração" in c.dias_treino
    assert "cardio" not in c.dias_treino and "descanso" not in c.dias_sem_treino


def test_t5_texto_fixo() -> None:
    assert carregar_taichi().textos.postura == (
        "Movimentos lentos e postura alta: joelhos ligeiramente fletidos, sem descer. Se perder "
        "o equilíbrio, apoie-se numa cadeira ou parede."
    )


# ---------------------------------------------------------------- T3


@pytest.mark.parametrize(
    ("intensidade", "fase_1", "fases_2_a_4"), [(L, 10, 10), (M, 15, 20), (A, 20, 30)]
)
def test_t3_minutos_iguais_aos_da_danca(
    intensidade: Intensidade, fase_1: int, fases_2_a_4: int
) -> None:
    t = construir_taichi(_e(intensidade), _q(minutos_dia=60))
    assert t is not None
    assert t.minutos == (fase_1, fases_2_a_4, fases_2_a_4, fases_2_a_4)


@pytest.mark.parametrize("minutos_dia", [15, 20, 30, 45, 60])
def test_t3_limitado_a_sessao_como_a_danca(minutos_dia: int) -> None:
    q = _q(minutos_dia=minutos_dia, preferencias=["danca", "tai_chi"])
    t = construir_taichi(_e(A), q)
    d = construir_danca(_e(A), q)
    assert t is not None and d is not None
    assert t.minutos == d.minutos
    assert all(m == max(10, min(m, minutos_dia - 10)) for m in t.minutos)
    assert t.minutos[1] == minutos_atividade(2, A, minutos_dia)


# ---------------------------------------------------------------- T6 (condições)


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"limitacoes": ["equilibrio"], "limitacoes_gravidade": {"equilibrio": "ligeira"}},
        {"limitacoes": ["equilibrio"], "limitacoes_gravidade": {"equilibrio": "importante"}},
        {"condicoes": ["osteoporose"], "osteoporose_risco": "nao"},
        {"condicoes": ["osteoporose"], "osteoporose_risco": "sim"},
    ],
)
def test_t6_equilibrio_ou_osteoporose_so_ligeira(alteracoes: dict[str, Any]) -> None:
    q = _q(**alteracoes)
    assert regras.so_nivel_ligeira(q)
    t = construir_taichi(_e(A), q)
    assert t is not None and t.so_ligeira
    lig = ligacoes_taichi(t)
    assert {x.nivel for x in lig.principais} == {NivelLigacao.LIGEIRA}
    assert lig.mais_calmo is None


@pytest.mark.parametrize(
    "alteracoes",
    [
        {},
        {"limitacoes": ["joelhos"], "limitacoes_gravidade": {"joelhos": "importante"}},
        {"condicoes": ["doenca_cardiovascular"]},
        {"condicoes": ["protese_ou_cirurgia_recente"]},
        {"condicoes": ["hipertensao"], "condicoes_controladas": {"hipertensao": True}},
    ],
)
def test_t6_outras_condicoes_nao_limitam_o_taichi(alteracoes: dict[str, Any]) -> None:
    """Ao contrário da dança (D6), só o equilíbrio e a osteoporose limitam o Tai Chi."""
    assert not regras.so_nivel_ligeira(_q(**alteracoes))


# ---------------------------------------------------------------- T6 (ligações)


@pytest.mark.parametrize(
    ("intensidade", "abaixo"),
    [(L, None), (M, NivelLigacao.LIGEIRA), (A, NivelLigacao.MEDIA)],
)
def test_t6_nivel_da_pessoa_e_um_do_nivel_abaixo(
    intensidade: Intensidade, abaixo: NivelLigacao | None
) -> None:
    lig = ligacoes_taichi(_taichi(intensidade))
    assert lig.principais == carregar_taichi().do_nivel(NivelLigacao(intensidade))
    if abaixo is None:
        assert lig.mais_calmo is None
    else:
        assert lig.mais_calmo is not None and lig.mais_calmo.nivel is abaixo
    assert lig.mais_aulas == () and lig.ajuste == ""


def test_t6_ligeira_tem_as_duas_ligacoes_da_cadeira() -> None:
    lig = ligacoes_taichi(_taichi(L))
    assert len(lig.principais) == 2
    assert all("cadeira" in x.titulo for x in lig.principais)


def test_pessoa_com_danca_e_taichi() -> None:
    """Níveis independentes: a dança limita com joelhos, o Tai Chi não."""
    q = _q(
        preferencias=["danca", "tai_chi"],
        limitacoes=["joelhos"],
        limitacoes_gravidade={"joelhos": "ligeira"},
    )
    plano = gerar_plano_verificado(q, ProvedorSimulado(), progresso=lambda _: None).plano
    assert plano.danca is not None and plano.taichi is not None
    assert plano.danca.so_ligeira and not plano.taichi.so_ligeira
    assert plano.danca.minutos == plano.taichi.minutos


# ---------------------------------------------------------------- Conteúdo


def test_conteudo_valido_sem_mais_aulas() -> None:
    c = carregar_taichi()
    assert {x.nivel for x in c.ligacoes} == {L.value, M.value, A.value}
    assert not c.do_nivel(NivelLigacao.MAIS_AULAS)


def _dados(**ligacoes: Any) -> dict[str, Any]:
    base = {
        "ligeira": "https://www.youtube.com/watch?v=l",
        "media": "https://www.youtube.com/watch?v=m",
        "alta": "https://www.youtube.com/watch?v=a",
    } | ligacoes
    return {
        "textos": carregar_taichi().textos.model_dump(),
        "ligacoes": [
            {"titulo": "T", "url": u, "canal": "C", "nivel": n, "verificado_em": "2026-11-18"}
            for n, u in base.items()
        ],
    }


def test_validacao_exige_os_tres_niveis() -> None:
    dados = _dados()
    dados["ligacoes"] = dados["ligacoes"][:2]
    with pytest.raises(ValidationError, match="níveis sem ligações: alta"):
        ConteudoTaiChi.model_validate(dados)


def test_validacao_recusa_mais_aulas() -> None:
    with pytest.raises(ValidationError, match="Mais aulas"):
        ConteudoTaiChi.model_validate(_dados(mais_aulas="https://www.youtube.com/watch?v=x"))


# ---------------------------------------------------------------- T7 e interface


def test_t7_cartao_com_ligacoes_numa_janela_nova_sem_ajuste() -> None:
    lig = ligacoes_taichi(_taichi(M))
    c = carregar_taichi().textos
    html = componentes.cartao_atividade(
        "taichi",
        "mobilidade",
        c.titulo,
        "20 minutos de Tai Chi",
        "",
        (c.dias_sem_treino,),
        (("", c.aquecimento), (c.taichi, "20 minutos"), ("", "Retorno")),
        c.postura,
        "",
        lig.grupos(c.ligacoes, c.mais_calmo),
        "Nota",
    )
    assert 'class="v-cartao v-taichi v-atividade"' in html
    assert html.count('target="_blank" rel="noopener noreferrer"') == 2  # a media e a mais calma
    assert "<iframe" not in html and "youtube.com/embed" not in html
    assert "<p></p>" not in html  # sem ajuste, sem parágrafo vazio


def test_video_do_taichi_sem_som_em_ciclo_e_menos_movimento() -> None:
    html = componentes.video_taichi("Descrição", "Pausar", "Ver")
    assert "app/static/video/taichi_web.mp4" in html
    assert "app/static/video/taichi_poster.jpg" in html
    assert "muted" in html and "playsinline" in html
    assert "autoplay" not in html
    assert "prefers-reduced-motion" in html


def test_capa_do_pdf_igual_a_da_app() -> None:
    copia = RAIZ / "src" / "vigoria" / "exportacao" / "recursos" / "taichi_poster.jpg"
    assert copia.read_bytes() == (RAIZ / "static" / "video" / "taichi_poster.jpg").read_bytes()


def test_credito_do_video() -> None:
    creditos = (RAIZ / "docs" / "CREDITOS_IMAGENS.md").read_text("utf-8")
    assert "taichi_web.mp4" in creditos and "4558846" in creditos


def test_textos_sem_promessas_termos_proibidos_nem_brasileirismos() -> None:
    from paginas import textos as t
    from vigoria.conteudo.carregar import carregar_avisos
    from vigoria.motor.voz import encontrar_termos

    avisos = carregar_avisos()
    c = carregar_taichi()
    texto = " ".join(
        [*c.textos.model_dump().values(), *(x.titulo for x in c.ligacoes), t.TAICHI_VIDEO_DESCRICAO]
    )
    for termos in (avisos.lista_negra.promessas, avisos.lista_negra.termos, avisos.brasileirismos):
        assert encontrar_termos(termos, texto) == ()
    for proibido in ("emagrec", "barriga", "cintura", "queima"):
        assert proibido not in texto.lower()
