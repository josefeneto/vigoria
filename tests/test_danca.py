"""Dança (opcional), Fase 10E: REGRAS_DOMINIO §5.1 (D1 a D7)."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from paginas import componentes
from vigoria.conteudo.carregar import ConteudoDanca, NivelLigacao, carregar_danca
from vigoria.llm.simulado import ProvedorSimulado
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Danca, DiasDanca
from vigoria.modelos.questionario import Intensidade, Questionario
from vigoria.motor.danca import construir_danca, ligacoes_danca
from vigoria.motor.pipeline import gerar_plano_verificado
from vigoria.regras import danca as regras
from vigoria.regras.elegibilidade import Modo

RAIZ = Path(__file__).resolve().parents[1]
L, M, A = Intensidade.LIGEIRA, Intensidade.MEDIA, Intensidade.ALTA


def _q(**alteracoes: Any) -> Questionario:
    """Persona de teste sem condições nem limitações, com dança; validada de novo."""
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8"))
    dados |= {
        "condicoes": ["nenhuma"],
        "condicoes_controladas": {},
        "limitacoes": ["nenhuma"],
        "limitacoes_gravidade": {},
        "preferencias": ["caminhada", "danca"],
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


# ---------------------------------------------------------------- D1


def test_d1_so_com_danca_nas_preferencias() -> None:
    assert regras.tem_danca(_q())
    sem = _q(preferencias=["caminhada", "forca"])
    assert not regras.tem_danca(sem)
    assert construir_danca(_e(), sem) is None
    assert construir_danca(_e(), _q()) is not None


def test_d1_sem_intensidade_efetiva_nao_ha_bloco() -> None:
    assert construir_danca(_e(None), _q()) is None


@pytest.mark.parametrize("com_danca", [False, True])
def test_d1_no_plano_gerado(com_danca: bool) -> None:
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8"))
    if com_danca:
        dados["preferencias"].append("danca")
    q = Questionario.model_validate(dados)
    plano = gerar_plano_verificado(q, ProvedorSimulado(), progresso=lambda _: None).plano
    assert (plano.danca is not None) is com_danca


def test_plano_antigo_sem_campo_danca_continua_valido() -> None:
    """Os planos guardados antes da Fase 10E não têm o campo: ficam sem bloco."""
    dados = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8"))
    q = Questionario.model_validate(dados)
    plano = gerar_plano_verificado(q, ProvedorSimulado(), progresso=lambda _: None).plano
    guardado = plano.model_dump(mode="json")
    guardado.pop("danca")
    assert type(plano).model_validate(guardado).danca is None


# ---------------------------------------------------------------- D3


@pytest.mark.parametrize(
    ("intensidade", "fase_1", "fases_2_a_4"),
    [(L, 10, 10), (M, 15, 20), (A, 20, 30)],
)
def test_d3_minutos_por_fase_e_intensidade(
    intensidade: Intensidade, fase_1: int, fases_2_a_4: int
) -> None:
    assert regras.minutos_danca(1, intensidade, 60) == fase_1
    for fase in (2, 3, 4):
        assert regras.minutos_danca(fase, intensidade, 60) == fases_2_a_4


@pytest.mark.parametrize(
    ("minutos_dia", "esperado"),
    [(60, 30), (45, 30), (40, 30), (39, 29), (30, 20), (20, 10), (15, 10)],
)
def test_d3_limitado_a_sessao_com_minimo_de_10(minutos_dia: int, esperado: int) -> None:
    """min(D3, minutos_dia − 10), nunca abaixo de 10 (alta, fase 2: D3 = 30)."""
    assert regras.minutos_danca(2, A, minutos_dia) == esperado


@pytest.mark.parametrize("fase", [0, 5])
def test_d3_fase_fora_do_programa(fase: int) -> None:
    with pytest.raises(ValueError, match="fora do programa"):
        regras.minutos_danca(fase, M, 30)


def test_d3_no_bloco_do_plano() -> None:
    d = construir_danca(_e(A), _q(minutos_dia=45))
    assert d is not None and d.minutos == (20, 30, 30, 30)
    d = construir_danca(_e(A), _q(minutos_dia=20))
    assert d is not None and d.minutos == (10, 10, 10, 10)


# ---------------------------------------------------------------- D4


@pytest.mark.parametrize(
    ("dias", "esperado"),
    [
        (1, DiasDanca.CAMINHADA),
        (2, DiasDanca.CAMINHADA),
        (3, DiasDanca.CARDIO),
        (4, DiasDanca.CARDIO),
        (5, DiasDanca.CARDIO),
        (7, DiasDanca.CARDIO),
    ],
)
def test_d4_dias_de_cardio_ou_de_caminhada(dias: int, esperado: DiasDanca) -> None:
    d = construir_danca(_e(), _q(dias_semana=dias))
    assert d is not None and d.dias is esperado


def test_d4_textos_dos_dias_e_do_registo() -> None:
    c = carregar_danca().textos
    assert "cardio" in c.dias_cardio and "outros dias" in c.dias_cardio
    # Desde 18/11/2026, todos os dias valem o mesmo: o domingo não é dia especial.
    assert "caminhada" in c.dias_sem_cardio and "domingo" not in c.dias_sem_cardio.lower()
    assert "cardio" in c.registo


# ---------------------------------------------------------------- D5 e D6 (textos)


def test_d5_texto_fixo_sem_saltos() -> None:
    assert carregar_danca().textos.sem_saltos == (
        "Sem saltos: acompanhe com passos no chão e use os braços para dar intensidade. "
        "Se sentir dor ou falta de ar, pare."
    )


def test_d6_texto_de_ajuste() -> None:
    c = carregar_danca().textos
    assert c.ajuste == "Deve conseguir falar, mas não cantar (esforço 3 a 6 em 10)."
    assert c.ajuste_subir == "Se for fácil demais, experimente o nível acima na semana seguinte."


# ---------------------------------------------------------------- D6 (condições)


@pytest.mark.parametrize(
    "alteracoes",
    [
        {"limitacoes": ["joelhos"], "limitacoes_gravidade": {"joelhos": "ligeira"}},
        {"limitacoes": ["joelhos"], "limitacoes_gravidade": {"joelhos": "importante"}},
        {"limitacoes": ["equilibrio"], "limitacoes_gravidade": {"equilibrio": "ligeira"}},
        {"condicoes": ["osteoporose"], "osteoporose_risco": "nao"},
        {"condicoes": ["doenca_cardiovascular"]},
        {"condicoes": ["protese_ou_cirurgia_recente"]},
        {"condicoes": ["dor_articular_persistente"], "dor_articular_zonas": ["joelhos"]},
        {
            "condicoes": ["dor_articular_persistente"],
            "dor_articular_zonas": ["ombros", "joelhos"],
        },
    ],
)
def test_d6_condicoes_que_limitam_a_ligeira(alteracoes: dict[str, Any]) -> None:
    assert regras.so_nivel_ligeira(_q(**alteracoes))


@pytest.mark.parametrize(
    "alteracoes",
    [
        {},
        {"condicoes": ["hipertensao"], "condicoes_controladas": {"hipertensao": True}},
        {"condicoes": ["diabetes"], "condicoes_controladas": {"diabetes": True}},
        {"condicoes": ["dor_articular_persistente"], "dor_articular_zonas": ["ancas"]},
        {"limitacoes": ["ancas"], "limitacoes_gravidade": {"ancas": "importante"}},
        {"limitacoes": ["ombros"], "limitacoes_gravidade": {"ombros": "ligeira"}},
    ],
)
def test_d6_condicoes_que_nao_limitam(alteracoes: dict[str, Any]) -> None:
    assert not regras.so_nivel_ligeira(_q(**alteracoes))


# ---------------------------------------------------------------- D6 (ligações)


def _danca(intensidade: Intensidade, so_ligeira: bool = False) -> Danca:
    return Danca(
        minutos=(10, 10, 10, 10),
        intensidade=intensidade,
        so_ligeira=so_ligeira,
        dias=DiasDanca.CARDIO,
    )


def _niveis(ligacoes: tuple[Any, ...]) -> set[NivelLigacao]:
    return {x.nivel for x in ligacoes}


@pytest.mark.parametrize(
    ("intensidade", "abaixo"),
    [(L, None), (M, NivelLigacao.LIGEIRA), (A, NivelLigacao.MEDIA)],
)
def test_d6_nivel_da_pessoa_e_um_do_nivel_abaixo(
    intensidade: Intensidade, abaixo: NivelLigacao | None
) -> None:
    lig = ligacoes_danca(_danca(intensidade))
    assert _niveis(lig.principais) == {NivelLigacao(intensidade)}
    assert lig.principais == carregar_danca().do_nivel(NivelLigacao(intensidade))
    if abaixo is None:
        assert lig.mais_calmo is None
    else:
        assert lig.mais_calmo is not None and lig.mais_calmo.nivel is abaixo


@pytest.mark.parametrize(("intensidade", "mostra"), [(L, False), (M, True), (A, True)])
def test_mais_aulas_so_para_media_e_alta(intensidade: Intensidade, mostra: bool) -> None:
    lig = ligacoes_danca(_danca(intensidade))
    assert bool(lig.mais_aulas) is mostra
    assert all(x.nivel is NivelLigacao.MAIS_AULAS for x in lig.mais_aulas)


@pytest.mark.parametrize("intensidade", [L, M, A])
def test_d6_com_condicoes_so_ligeira_sem_subir_nem_mais_aulas(intensidade: Intensidade) -> None:
    lig = ligacoes_danca(_danca(intensidade, so_ligeira=True))
    assert _niveis(lig.principais) == {NivelLigacao.LIGEIRA}
    assert lig.mais_calmo is None and lig.mais_aulas == ()
    assert "nível acima" not in lig.ajuste


@pytest.mark.parametrize(("intensidade", "sobe"), [(L, False), (M, True), (A, False)])
def test_d6_sugere_subir_so_se_houver_nivel_acima(intensidade: Intensidade, sobe: bool) -> None:
    lig = ligacoes_danca(_danca(intensidade))
    assert lig.ajuste.startswith(carregar_danca().textos.ajuste)
    assert ("nível acima" in lig.ajuste) is sobe


def test_d6_regressao_no_bloco_do_plano() -> None:
    q = _q(condicoes=["doenca_cardiovascular"])
    d = construir_danca(_e(M), q)
    assert d is not None and d.so_ligeira and d.intensidade is M
    assert d.minutos == (15, 20, 20, 20)  # os minutos seguem a intensidade (D3)


# ---------------------------------------------------------------- Conteúdo


def test_cada_nivel_tem_pelo_menos_uma_ligacao() -> None:
    c = carregar_danca()
    for nivel in NivelLigacao:
        assert c.do_nivel(nivel), nivel


def test_ligacoes_so_youtube_sem_lista_automatica() -> None:
    for x in carregar_danca().ligacoes:
        assert x.url.startswith("https://www.youtube.com/")
        assert "list=RD" not in x.url
    urls = {x.url for x in carregar_danca().ligacoes}
    assert "https://www.youtube.com/watch?v=zb9kM1VO9Yk" in urls


def _conteudo(ligacoes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "textos": carregar_danca().textos.model_dump(),
        "ligacoes": ligacoes,
    }


def _ligacao(nivel: str, url: str) -> dict[str, Any]:
    return {
        "titulo": "Título",
        "url": url,
        "canal": "Canal",
        "nivel": nivel,
        "verificado_em": "2026-11-17",
    }


def _quatro_niveis(**trocar: str) -> list[dict[str, Any]]:
    return [
        _ligacao(n.value, trocar.get(n.value, f"https://www.youtube.com/watch?v={n.value}"))
        for n in NivelLigacao
    ]


def test_validacao_aceita_os_quatro_niveis() -> None:
    ConteudoDanca.model_validate(_conteudo(_quatro_niveis()))


def test_validacao_recusa_nivel_sem_ligacoes() -> None:
    ligacoes = [x for x in _quatro_niveis() if x["nivel"] != "mais_aulas"]
    with pytest.raises(ValidationError, match="níveis sem ligações: mais_aulas"):
        ConteudoDanca.model_validate(_conteudo(ligacoes))


def test_validacao_recusa_lista_automatica() -> None:
    url = "https://www.youtube.com/watch?v=abc&list=RDabc"
    with pytest.raises(ValidationError, match="lista automática"):
        ConteudoDanca.model_validate(_conteudo(_quatro_niveis(alta=url)))


def test_validacao_recusa_fora_do_youtube() -> None:
    with pytest.raises(ValidationError):
        ConteudoDanca.model_validate(_conteudo(_quatro_niveis(alta="https://exemplo.pt/x")))


def test_validacao_recusa_ligacoes_repetidas() -> None:
    url = "https://www.youtube.com/watch?v=ligeira"
    with pytest.raises(ValidationError, match="ligações repetidas"):
        ConteudoDanca.model_validate(_conteudo(_quatro_niveis(media=url)))


# ---------------------------------------------------------------- D7 e interface


def test_d7_ligacoes_abrem_numa_janela_nova() -> None:
    html = componentes.cartao_atividade(
        "danca",
        "cardio",
        "Dança (opcional)",
        "20 minutos de dança",
        "",
        ("Texto",),
        (("Aquecimento", "a"), ("Dança", "b"), ("Retorno à calma", "c")),
        "Sem saltos",
        "Ajuste",
        (("Vídeos", (("Título <b>", "https://www.youtube.com/watch?v=x&y=1", "Canal"),)),),
        "Nota",
    )
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert "https://www.youtube.com/watch?v=x&amp;y=1" in html
    assert "Título &lt;b&gt;" in html  # texto escapado
    assert "<iframe" not in html and "youtube.com/embed" not in html


def test_video_da_danca_sem_som_em_ciclo_e_menos_movimento() -> None:
    html = componentes.video_danca("Descrição", "Pausar", "Ver")
    assert "app/static/video/danca_web.mp4" in html
    assert "app/static/video/danca_poster.jpg" in html
    assert "muted" in html and "playsinline" in html
    assert "autoplay" not in html  # só arranca por código, e não com «menos movimento»
    assert "prefers-reduced-motion" in html


def test_video_da_danca_sem_ficheiros(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(componentes, "PASTA_VIDEO", tmp_path)
    assert componentes.video_danca("Descrição", "Pausar", "Ver") == ""


def test_credito_do_video() -> None:
    creditos = (RAIZ / "docs" / "CREDITOS_IMAGENS.md").read_text("utf-8")
    assert "danca_web.mp4" in creditos and "Kampus Production" in creditos
    assert "pexels.com/video/happy-women-dancing-together-8956012" in creditos


def test_textos_sem_promessas_termos_proibidos_nem_brasileirismos() -> None:
    from paginas import textos as t
    from vigoria.conteudo.carregar import carregar_avisos
    from vigoria.motor.voz import encontrar_termos

    avisos = carregar_avisos()
    c = carregar_danca()
    texto = " ".join(
        [
            *c.textos.model_dump().values(),
            *(x.titulo for x in c.ligacoes),
            t.DANCA_VIDEO_DESCRICAO,
            t.REGISTO_CARDIO_DANCA,
        ]
    )
    for termos in (avisos.lista_negra.promessas, avisos.lista_negra.termos, avisos.brasileirismos):
        assert encontrar_termos(termos, texto) == ()
