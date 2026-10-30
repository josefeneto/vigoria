"""Testes de avisos.yaml e alimentacao.yaml (REGRAS_DOMINIO §7 e §8) e do carregamento."""

import ast
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from vigoria.conteudo import carregar
from vigoria.conteudo.carregar import (
    ErroConteudo,
    carregar_alimentacao,
    carregar_avisos,
    carregar_conteudo,
)
from vigoria.regras import textos

SRC = Path(__file__).parent.parent / "src" / "vigoria"
AVISOS = carregar_avisos()


def _textos(valor: Any) -> Iterator[str]:
    """Todos os textos de uma estrutura (dicionários, listas, modelos)."""
    if isinstance(valor, str):
        yield valor
    elif isinstance(valor, dict):
        for v in valor.values():
            yield from _textos(v)
    elif isinstance(valor, list | tuple):
        for v in valor:
            yield from _textos(v)
    elif hasattr(valor, "model_dump"):
        yield from _textos(valor.model_dump())


def _encontrados(texto: str, termos: tuple[str, ...]) -> list[str]:
    """Termos presentes como palavra ou expressão inteira, sem distinguir maiúsculas."""
    return [t for t in termos if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", texto, re.IGNORECASE)]


TEXTOS_VERIFICADOS = [
    *_textos(AVISOS.textos),
    *_textos(AVISOS.rotulos),
    *_textos(carregar_alimentacao()),
]


@pytest.mark.parametrize("texto", TEXTOS_VERIFICADOS)
def test_sem_lista_negra_nem_brasileirismos(texto: str) -> None:
    assert _encontrados(texto, AVISOS.lista_negra.termos) == []
    assert _encontrados(texto, AVISOS.brasileirismos) == []


def test_procura_por_palavra_inteira() -> None:
    assert _encontrados("Um chá Detox não serve.", AVISOS.lista_negra.termos) == ["detox"]
    assert _encontrados("Guarde no ecrã do telemóvel.", AVISOS.brasileirismos) == []
    assert _encontrados("Use a cautela de sempre.", AVISOS.brasileirismos) == []  # «tela»
    assert _encontrados("para baixar a frequência cardíaca", AVISOS.brasileirismos) == []
    assert _encontrados("Pode baixar a app.", AVISOS.brasileirismos) == ["baixar a app"]


def test_obrigatorios_de_7() -> None:
    assert AVISOS.obrigatorios == ("aviso_geral", "sinais_interromper")
    assert textos.AVISO_GERAL.startswith("Este plano é uma sugestão de apoio à decisão")
    assert "dor no peito" in textos.SINAIS_INTERROMPER


def _usos_de_textos() -> set[str]:
    """Nomes de regras/textos.py usados em src/ (textos.X e from ...textos import X)."""
    usados: set[str] = set()
    for ficheiro in SRC.rglob("*.py"):
        if ficheiro.name == "textos.py":
            continue
        for no in ast.walk(ast.parse(ficheiro.read_text(encoding="utf-8"))):
            if (
                isinstance(no, ast.Attribute)
                and isinstance(no.value, ast.Name)
                and no.value.id == "textos"
            ):
                usados.add(no.attr)
            elif isinstance(no, ast.ImportFrom) and no.module == "vigoria.regras.textos":
                usados.update(alias.name for alias in no.names)
    return usados


def test_avisos_usados_pelo_motor_existem_em_avisos_yaml() -> None:
    usados = _usos_de_textos() - {"numero"}
    assert usados, "não foi encontrado nenhum uso de textos"
    rotulos = {"NOMES_INTENSIDADE", "ZONAS_LIMITACAO", "FASES"}
    for nome in usados:
        valor = getattr(textos, nome)
        if nome in rotulos:
            continue
        assert valor == AVISOS.textos[nome.lower()], nome


def test_textos_py_sem_textos_escritos_no_codigo() -> None:
    arvore = ast.parse((SRC / "regras" / "textos.py").read_text(encoding="utf-8"))
    # Fora da docstring do módulo e da função numero() (só formatação de números),
    # as únicas strings são ids de avisos.yaml.
    for instrucao in arvore.body[1:]:
        if isinstance(instrucao, ast.FunctionDef):
            continue
        for no in ast.walk(instrucao):
            if isinstance(no, ast.Constant) and isinstance(no.value, str):
                assert no.value in AVISOS.textos, no.value


def test_rotulos_cobrem_os_enums() -> None:
    assert len(textos.NOMES_INTENSIDADE) == 3
    assert len(textos.ZONAS_LIMITACAO) == 5
    assert textos.FASES == ("Adaptação", "Construção", "Consolidação", "Integração")


def test_alimentacao_completa() -> None:
    a = carregar_alimentacao()
    assert len(a.principios.lista) == 5
    assert [e.titulo for e in a.refeicao_simples.elementos] == [
        "1. Proteína",
        "2. Hortícolas",
        "3. Fonte de energia",
        "4. Gordura",
    ]
    assert len(a.evolucao_abranda.verificar) == 6
    assert "Não mudar cinco coisas ao mesmo tempo." in a.evolucao_abranda.ajustar.conclusao


def test_carregar_conteudo_completo() -> None:
    conteudo = carregar_conteudo()
    assert len(conteudo.exercicios) == 45
    assert len(conteudo.programa.fases) == 4
    assert conteudo.avisos is AVISOS


# ---------------------------------------------------------------- Mensagens de erro


@pytest.fixture
def pasta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Faz o carregamento ler da pasta temporária em vez do pacote."""
    monkeypatch.setattr(carregar, "files", lambda _pacote: tmp_path)
    return tmp_path


def test_erro_ficheiro_em_falta(pasta: Path) -> None:
    with pytest.raises(ErroConteudo, match=r"conteudo/avisos\.yaml: não foi possível ler"):
        carregar._carregar("avisos.yaml", carregar.Avisos)


def test_erro_yaml_invalido(pasta: Path) -> None:
    (pasta / "avisos.yaml").write_text("textos: [sem fecho\n", encoding="utf-8")
    with pytest.raises(ErroConteudo, match=r"conteudo/avisos\.yaml: YAML inválido"):
        carregar._carregar("avisos.yaml", carregar.Avisos)


def test_erro_obrigatorio_sem_texto(pasta: Path) -> None:
    (pasta / "avisos.yaml").write_text(
        "obrigatorios: [aviso_geral]\n"
        "textos: {outro: Texto.}\n"
        "rotulos: {intensidade: {}, zonas_limitacao: {}, plano: {}, dias: {}, refeicoes: {}}\n"
        "lista_negra: {termos: [detox]}\n"
        "brasileirismos: [tela]\n",
        encoding="utf-8",
    )
    with pytest.raises(ErroConteudo, match=r"(?s)estrutura inválida.*obrigatórios sem texto"):
        carregar._carregar("avisos.yaml", carregar.Avisos)


def test_erro_referencia_cruzada(monkeypatch: pytest.MonkeyPatch) -> None:
    exercicios = dict(carregar.carregar_exercicios())
    del exercicios["bird_dog"]
    monkeypatch.setattr(carregar, "carregar_exercicios", lambda: exercicios)
    with pytest.raises(ErroConteudo, match=r"bird_dog"):
        carregar_conteudo()
