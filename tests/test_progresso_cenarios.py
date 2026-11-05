"""Os quatro cenários de scripts/registos_ficticios.py disparam os alertas certos; gráficos e
textos do progresso; as observações nunca chegam às regras."""

import importlib.util
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy.orm import Session, sessionmaker

from paginas import graficos, sessao
from paginas import textos as t
from vigoria.config import obter_configuracao
from vigoria.conteudo.carregar import carregar_avisos
from vigoria.dados import repositorios as r
from vigoria.dados.bd import criar_motor, fabrica_sessoes
from vigoria.interface.progresso import contexto_do_plano, medicoes_dos_registos
from vigoria.modelos.questionario import FrequenciaRegisto
from vigoria.modelos.registo import ValoresRegisto
from vigoria.motor.voz import encontrar_termos
from vigoria.regras.progresso import Medicao, TipoAlerta, avaliar

RAIZ = Path(__file__).resolve().parents[1]
HOJE = date(2026, 11, 5)


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "registos_ficticios", RAIZ / "scripts" / "registos_ficticios.py"
    )
    assert spec is not None
    assert spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def fabrica(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    url = f"sqlite:///{tmp_path / 'cenarios.db'}"
    monkeypatch.setenv("AMBIENTE", "local")
    monkeypatch.setenv("DATABASE_URL", url)
    obter_configuracao.cache_clear()
    motor = criar_motor(url)
    yield fabrica_sessoes(motor)
    motor.dispose()
    obter_configuracao.cache_clear()


def _alertas(fabrica: sessionmaker[Session], nome: str) -> tuple[list[TipoAlerta], r.PlanoDaConta]:
    uid, plano_id = _script().criar(nome, HOJE)
    with fabrica.begin() as s:
        plano = r.obter_plano(s, uid, plano_id)
        registos = r.listar_registos(s, uid, plano_id)
    assert plano is not None
    alertas = avaliar(
        contexto_do_plano(plano), medicoes_dos_registos(registos), FrequenciaRegisto.SEMANAL, HOJE
    )
    return [a.tipo for a in alertas], plano


@pytest.mark.parametrize(
    ("nome", "esperado"),
    [
        ("normal", []),
        ("lenta", [TipoAlerta.EVOLUCAO_ABAIXO]),
        ("rapida", [TipoAlerta.PERDA_RAPIDA]),
        ("manutencao", [TipoAlerta.SUBIDA_PESO, TipoAlerta.SUBIDA_CINTURA]),
    ],
)
def test_cada_cenario_dispara_o_alerta_certo(
    fabrica: sessionmaker[Session], nome: str, esperado: list[TipoAlerta]
) -> None:
    assert _alertas(fabrica, nome)[0] == esperado


def test_o_script_usa_o_utilizador_local_das_paginas() -> None:
    assert _script().UTILIZADOR_LOCAL == sessao.UTILIZADOR_LOCAL


@pytest.mark.parametrize(
    ("ambiente", "url"),
    [
        ("demo", "sqlite:///x.db"),
        ("local", "postgresql+psycopg://u:p@exemplo.invalid/bd"),
    ],
)
def test_o_script_recusa_fora_do_sqlite_local(
    monkeypatch: pytest.MonkeyPatch, ambiente: str, url: str
) -> None:
    monkeypatch.setenv("AMBIENTE", ambiente)
    monkeypatch.setenv("VIGORIA_PROVEDOR_LLM", "gemini")
    monkeypatch.setenv("DATABASE_URL", url)
    obter_configuracao.cache_clear()
    try:
        with pytest.raises(SystemExit, match="AMBIENTE=local"):
            _script().criar("normal", HOJE)
    finally:
        obter_configuracao.cache_clear()


def test_as_observacoes_nunca_chegam_as_regras() -> None:
    assert "observacoes" not in Medicao.model_fields
    registo = r.RegistoDaConta(
        id=1,
        plano_id=1,
        semana=1,
        data=HOJE - timedelta(days=1),
        valores=ValoresRegisto(peso_kg=80.0, observacoes="texto privado"),
    )
    assert "texto privado" not in str(medicoes_dos_registos([registo]))


# ---------------------------------------------------------------- Gráficos


def _nomes(figura: object) -> list[str]:
    return [traco.name for traco in figura.data]  # type: ignore[attr-defined]


def test_grafico_do_peso_com_linha_e_na_manutencao_sem_ela() -> None:
    com = graficos.peso([0, 1, 2], [94, 93.6, 93.3], [(0, 94.0), (4, 92.5), (16, 88.0)])
    assert _nomes(com) == [t.GRAFICO_LINHA, t.GRAFICO_REGISTOS]
    assert com.layout.showlegend is True
    sem = graficos.peso([20, 24], [90.5, 91.0], [])
    assert _nomes(sem) == [t.GRAFICO_REGISTOS]
    assert sem.layout.showlegend is False


def test_grafico_da_cintura_so_com_limiar_se_a_cintura_inicial_o_passava() -> None:
    assert _nomes(graficos.cintura([0, 4], [108, 106], 94)) == [
        t.GRAFICO_LIMIAR,
        t.GRAFICO_REGISTOS,
    ]
    assert _nomes(graficos.cintura([0, 4], [90, 89], None)) == [t.GRAFICO_REGISTOS]


def test_graficos_sem_zoom_nem_arrastar_e_com_uma_so_escala() -> None:
    figura = graficos.barras([1, 2], [4, 3], t.UNIDADE_SESSOES, 4)
    assert figura.layout.yaxis.fixedrange is True
    assert figura.layout.xaxis.fixedrange is True
    assert figura.layout.dragmode is False
    assert "yaxis2" not in figura.to_dict()["layout"]  # nunca dois eixos
    assert graficos.CONFIG["displayModeBar"] is False


# ---------------------------------------------------------------- Textos


def test_textos_do_progresso_sem_promessas_termos_proibidos_nem_brasileirismos() -> None:
    avisos = carregar_avisos()
    nomes = [
        n
        for n in dir(t)
        if n.startswith(("PROGRESSO_", "ALERTA_", "REGIST", "GRAFICO", "RESUMO_", "CONTA_ACOMP"))
    ]
    valores = [getattr(t, n) for n in nomes]
    texto = "\n".join(
        [
            *(v for v in valores if isinstance(v, str)),
            *t.ROTULOS_REGISTO.values(),
            *t.COMPARACAO.values(),
            t.CONVITE_NOVO_PLANO,
        ]
    )
    for termos in (avisos.lista_negra.promessas, avisos.lista_negra.termos, avisos.brasileirismos):
        assert encontrar_termos(termos, texto) == ()


def test_mensagens_aprovadas_a_05_11_2026() -> None:
    assert t.REGISTO_OBSERVACOES_AJUDA == (
        "Só para si. Fica guardado na sua conta, mas a Vigoria não o analisa nem o envia a "
        "terceiros."
    )
    assert "fale com o seu médico" in t.ALERTA_PERDA_RAPIDA
    assert "«O que vigiar»" in t.ALERTA_SUBIDA


@pytest.mark.parametrize(
    ("a", "b", "de", "para"),
    [
        (5, 5, "da semana 5", "para a semana 5"),
        (5, 8, "das semanas 5 a 8", "para as semanas 5 a 8"),
    ],
)
def test_periodos_em_texto(a: int, b: int, de: str, para: str) -> None:
    assert t.periodo_de(a, b) == de
    assert t.periodo_para(a, b) == para
