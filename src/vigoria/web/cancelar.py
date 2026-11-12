"""Cancelamento dos lembretes num clique (RFC 8058), em produção (Fase 10B).

O Caddy encaminha /cancelar para aqui (uvicorn em 127.0.0.1:8001, docker/arrancar.sh):

- GET /cancelar?t=…: só lê. Mostra a pergunta e o botão (formulário POST), ou o aviso de
  ligação inválida ou expirada. Abrir a ligação nunca desliga nada: os antivírus do email
  abrem ligações sozinhos.
- POST /cancelar?t=…: o pedido do Gmail e de outros (corpo «List-Unsubscribe=One-Click») ou o
  botão da página. Valida o token e desliga os lembretes.

Os registos só têm o método, o id técnico e o resultado; nunca o token nem o email. O uvicorn
corre sem registo de acessos, porque o endereço leva o token.
"""

import html
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from string import Template

from sqlalchemy.orm import Session, sessionmaker
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route

from vigoria.config import Configuracao, obter_configuracao
from vigoria.dados.bd import criar_motor, fabrica_sessoes
from vigoria.notificacoes.cancelamento import cancelar_lembretes, estado_da_ligacao
from vigoria.notificacoes.lembrete import CORES, modelo_cancelar, textos_cancelar, url_cancelar
from vigoria.notificacoes.token import EstadoToken, id_do_token

registo = logging.getLogger(__name__)

CAMINHO = "/cancelar"
ESTADOS_HTTP = {EstadoToken.VALIDO: 200, EstadoToken.INVALIDO: 400, EstadoToken.EXPIRADO: 410}
CABECALHOS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}


def _pagina(conteudo: str, estado_http: int) -> HTMLResponse:
    t = textos_cancelar()
    corpo = Template(modelo_cancelar()).substitute(
        titulo=html.escape(t.titulo),
        conteudo=conteudo,
        **{f"cor_{k}": v for k, v in CORES.items()},
    )
    return HTMLResponse(corpo, status_code=estado_http, headers=CABECALHOS)


def _paragrafo(texto: str) -> str:
    return f"<p>{html.escape(texto)}</p>"


def _aviso(estado: EstadoToken) -> HTMLResponse:
    t = textos_cancelar()
    texto = t.expirada if estado is EstadoToken.EXPIRADO else t.invalida
    ligacao = f'<p><a href="/">{html.escape(t.inicio)}</a></p>'
    return _pagina(_paragrafo(texto) + ligacao, ESTADOS_HTTP[estado])


def criar_app(
    fabrica: sessionmaker[Session] | None = None,
    config: Configuracao | None = None,
    relogio: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Starlette:
    """A aplicação; sem argumentos (uvicorn --factory), lê a configuração no primeiro pedido."""
    if fabrica is None:  # no contentor: as linhas «cancelar: …» aparecem nos registos
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    criada: dict[str, sessionmaker[Session]] = {}

    def _config() -> Configuracao:
        return obter_configuracao() if config is None else config

    def _fabrica() -> sessionmaker[Session]:
        if fabrica is not None:
            return fabrica
        if "f" not in criada:
            criada["f"] = fabrica_sessoes(criar_motor(_config().database_url))
        return criada["f"]

    # Funções síncronas: o Starlette corre-as numa thread à parte (a base de dados é síncrona).
    def cancelar(request: Request) -> HTMLResponse:
        token = request.query_params.get("t", "")
        segredo = _config().vigoria_segredo_lembretes
        with _fabrica().begin() as s:
            if request.method == "POST":
                estado = cancelar_lembretes(s, token, segredo, relogio())
            else:
                estado = estado_da_ligacao(s, token, segredo, relogio())
        registo.info("cancelar: %s, utilizador %s, %s", request.method, id_do_token(token), estado)
        t = textos_cancelar()
        if estado is not EstadoToken.VALIDO:
            return _aviso(estado)
        if request.method == "POST":
            return _pagina(_paragrafo(t.feito) + _paragrafo(t.reativar), 200)
        # Endereço relativo: o formulário volta a este mesmo serviço, com o mesmo token.
        acao = html.escape(url_cancelar("", token, um_clique=True))
        formulario = (
            f'<form method="post" action="{acao}">'
            f'<button type="submit">{html.escape(t.botao)}</button></form>'
        )
        return _pagina(_paragrafo(t.pergunta) + formulario, 200)

    return Starlette(routes=[Route(CAMINHO, cancelar, methods=["GET", "POST"])])
