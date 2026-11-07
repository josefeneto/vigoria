"""O email de lembrete (notificacoes/lembrete.py): sem dados de saúde, sem promessas nem
brasileirismos, com as duas ligações (registo e deixar de receber)."""

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from vigoria.conteudo.carregar import carregar_avisos
from vigoria.motor.voz import encontrar_termos
from vigoria.notificacoes import lembrete
from vigoria.notificacoes.lembrete import email_lembrete, textos_lembrete

RAIZ = Path(__file__).resolve().parents[1]
APP_URL = "https://vigoria.exemplo"
TOKEN = "12.abc_DEF-1"


class _Texto(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.partes: list[str] = []
        self.ligacoes: list[str] = []

    def handle_data(self, data: str) -> None:
        self.partes.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.ligacoes.extend(v or "" for k, v in attrs if k == "href")


def _visivel(html: str) -> _Texto:
    p = _Texto()
    p.feed(html)
    return p


@pytest.fixture(params=[1, 2])
def numero(request: pytest.FixtureRequest) -> int:
    return request.param


def _todo_o_texto(numero: int) -> str:
    e = email_lembrete("ana@exemplo.pt", numero, APP_URL, TOKEN)
    return "\n".join([e.assunto, e.texto, " ".join(_visivel(e.html).partes)])


def test_textos_aprovados() -> None:
    t = textos_lembrete()
    assert t.assunto == "Tem um registo por fazer na Vigoria"
    assert t.rodape_reativar == "Pode voltar a ativá-los em “A minha conta”."


def test_ligacoes_no_html_e_no_texto(numero: int) -> None:
    e = email_lembrete("ana@exemplo.pt", numero, APP_URL + "/", TOKEN)
    registo = f"{APP_URL}/progresso"
    cancelar = f"{APP_URL}/cancelar-lembretes?t={TOKEN}"
    assert _visivel(e.html).ligacoes == [registo, cancelar]
    assert registo in e.texto and cancelar in e.texto
    assert e.cabecalhos == {"List-Unsubscribe": f"<{cancelar}>"}
    assert f'src="{APP_URL}/app/static/icones/icone-192.png"' in e.html
    assert (RAIZ / "static" / "icones" / "icone-192.png").is_file()


def test_so_o_segundo_diz_que_e_o_ultimo() -> None:
    ultimo = textos_lembrete().ultimo
    assert ultimo not in _todo_o_texto(1)
    e = email_lembrete("ana@exemplo.pt", 2, APP_URL, TOKEN)
    assert ultimo in e.texto and ultimo in e.html


def test_sem_dados_de_saude(numero: int) -> None:
    texto = _todo_o_texto(numero).lower()
    palavras = (
        "peso", "cintura", "kg", "cm", "imc", "gordura", "doença", "diabetes", "hipertensão",
        "medicação", "condição", "condições", "semana", "fase", "esforço",
    )  # fmt: skip
    for palavra in palavras:
        assert not re.search(rf"(?<!\w){palavra}(?!\w)", texto), palavra
    sem_ligacoes = re.sub(r"https?://\S+", "", texto)  # o token da ligação tem o id
    assert not re.search(r"\d", sem_ligacoes)  # nem números, nem datas


def test_sem_valores_da_persona(numero: int) -> None:
    persona = json.loads((RAIZ / "exemplos" / "persona_teste.json").read_text("utf-8"))
    texto = _todo_o_texto(numero)
    for campo in ("peso_kg", "cintura_cm", "altura_cm", "idade"):
        assert str(persona[campo]).replace(".", ",") not in texto
        assert str(persona[campo]) not in texto


def test_sem_promessas_lista_negra_nem_brasileirismos(numero: int) -> None:
    avisos = carregar_avisos()
    texto = _todo_o_texto(numero)
    assert encontrar_termos(avisos.lista_negra.promessas, texto) == ()
    assert encontrar_termos(avisos.lista_negra.termos, texto) == ()
    assert encontrar_termos(avisos.brasileirismos, texto) == ()


def test_texto_escapado_no_html(monkeypatch: pytest.MonkeyPatch) -> None:
    original = textos_lembrete()
    monkeypatch.setattr(
        lembrete, "textos_lembrete", lambda: original.model_copy(update={"corpo": "<b>a & b</b>"})
    )
    e = email_lembrete("ana@exemplo.pt", 1, APP_URL, TOKEN)
    assert "&lt;b&gt;a &amp; b&lt;/b&gt;" in e.html


def test_cores_iguais_as_da_marca() -> None:
    from paginas.estilos import CORES

    for nome, valor in lembrete.CORES.items():
        assert CORES[nome] == valor
