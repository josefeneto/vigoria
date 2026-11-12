"""O email de lembrete de registo: HTML simples e texto, sem dados de saúde (REGRAS §9).

Textos em modelos/lembrete.yaml; esqueletos em modelos/lembrete.html e modelos/lembrete.txt,
lidos com importlib.resources, como os prompts. Todo o texto entra no HTML com html.escape.
"""

import html
from functools import cache
from importlib.resources import files
from string import Template
from urllib.parse import quote

import yaml
from pydantic import BaseModel, ConfigDict

from vigoria.notificacoes.brevo import Email
from vigoria.notificacoes.token import VALIDADE

CAMINHO_PROGRESSO = "progresso"  # paginas/progresso.py
CAMINHO_CANCELAR = "cancelar-lembretes"  # paginas/cancelar_lembretes.py (app.py): demo e local
# Produção (Fase 10): o serviço Starlette por trás do Caddy (vigoria/web/cancelar.py), que
# aceita o POST do cancelamento num clique (RFC 8058).
CAMINHO_CANCELAR_UM_CLIQUE = "cancelar"

# Paleta da marca (paginas/estilos.py, CORES; um teste confirma que são iguais).
CORES = {
    "principal": "#1F5C63",
    "principal_profundo": "#123F45",
    "texto": "#2E3338",
    "texto_secundario": "#5A6168",
    "fundo": "#F7F3EC",
    "cartao": "#FFFDF9",
    "borda": "#DDD3C3",
    "branco": "#FFFFFF",
}


class TextosLembrete(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    assunto: str
    saudacao: str
    corpo: str
    botao: str
    ultimo: str
    rodape_motivo: str
    rodape_cancelar: str
    rodape_reativar: str


def _ficheiro(nome: str) -> str:
    return files("vigoria.notificacoes").joinpath("modelos", nome).read_text(encoding="utf-8")


class TextosCancelar(BaseModel):
    """Página «Deixar de receber lembretes» (modelos/cancelar.yaml)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    titulo: str
    pergunta: str
    botao: str
    feito: str
    reativar: str
    invalida: str
    expirada: str
    inicio: str


@cache
def textos_lembrete() -> TextosLembrete:
    return TextosLembrete.model_validate(yaml.safe_load(_ficheiro("lembrete.yaml")))


@cache
def textos_cancelar() -> TextosCancelar:
    dados = yaml.safe_load(_ficheiro("cancelar.yaml"))
    dados["expirada"] = dados["expirada"].format(dias=VALIDADE.days)
    return TextosCancelar.model_validate(dados)


def modelo_cancelar() -> str:
    return _ficheiro("cancelar.html")


def url_cancelar(app_url: str, token: str, *, um_clique: bool = False) -> str:
    caminho = CAMINHO_CANCELAR_UM_CLIQUE if um_clique else CAMINHO_CANCELAR
    return f"{app_url.rstrip('/')}/{caminho}?t={quote(token, safe='')}"


def email_lembrete(
    para: str, numero: int, app_url: str, token: str, *, um_clique: bool = False
) -> Email:
    """O lembrete número 1 ou 2 (o segundo diz que é o último).

    Com `um_clique` (produção), a ligação vai para o serviço que aceita o POST e o email leva
    List-Unsubscribe-Post (RFC 8058): o Gmail e outros mostram «Anular subscrição».
    """
    t = textos_lembrete()
    base = app_url.rstrip("/")
    cancelar = url_cancelar(base, token, um_clique=um_clique)
    ligacoes = {
        "url_registo": f"{base}/{CAMINHO_PROGRESSO}",
        "url_cancelar": cancelar,
    }
    ultimo = numero >= 2
    campos = t.model_dump()
    texto = Template(_ficheiro("lembrete.txt")).substitute(
        campos, ultimo_texto=f"{t.ultimo}\n" if ultimo else "", **ligacoes
    )
    seguro = {k: html.escape(v) for k, v in (campos | ligacoes).items()}
    paragrafo = f'<p style="margin:0 0 12px 0;">{html.escape(t.ultimo)}</p>' if ultimo else ""
    corpo_html = Template(_ficheiro("lembrete.html")).substitute(
        seguro, ultimo_html=paragrafo, **{f"cor_{k}": v for k, v in CORES.items()}
    )
    cabecalhos = {"List-Unsubscribe": f"<{cancelar}>"}
    if um_clique:
        cabecalhos["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    return Email(para=para, assunto=t.assunto, html=corpo_html, texto=texto, cabecalhos=cabecalhos)
