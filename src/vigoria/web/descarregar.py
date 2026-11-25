"""Descarregar o plano (PDF) ou os dados (JSON) na app instalada (25/11/2026).

O Caddy encaminha /descarregar para aqui (o mesmo uvicorn de web/cancelar.py). A app abre
este endereço com target="_blank" só quando está instalada no ecrã principal: no iPhone,
abre no Safari por cima da app, com «OK» para voltar (exportacao/ligacao.py explica o token).

GET /descarregar?t=…: valida o token com o `sub` da conta, gera o ficheiro e devolve-o para
ver no ecrã (inline). Conta a descarga (dados/gestao.py), sem quem. Os registos só têm o
tipo, o id técnico e o resultado; nunca o token, o email nem o conteúdo.
"""

import html
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import cache
from importlib.resources import files
from string import Template

import yaml
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, sessionmaker
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

from vigoria.config import Configuracao
from vigoria.dados import repositorios
from vigoria.dados.gestao import TipoContagem, contar
from vigoria.exportacao import ligacao
from vigoria.exportacao.ligacao import EstadoLigacao, TipoDescarga
from vigoria.exportacao.pdf import plano_pdf
from vigoria.notificacoes.lembrete import CORES, modelo_cancelar
from vigoria.regras.progresso import dia_em_lisboa

registo = logging.getLogger(__name__)

CABECALHOS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
ESTADOS_HTTP = {EstadoLigacao.INVALIDA: 400, EstadoLigacao.EXPIRADA: 410}
FICHEIRO_PDF = "vigoria_plano_{data}.pdf"  # como paginas/textos.PDF_FICHEIRO
FICHEIRO_DADOS = "vigoria_os_meus_dados.json"  # como paginas/textos.CONTA_EXPORTAR_FICHEIRO


class TextosDescarregar(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    titulo: str
    invalida: str
    expirada: str
    voltar: str
    inicio: str


@cache
def textos_descarregar() -> TextosDescarregar:
    ficheiro = files("vigoria.notificacoes") / "modelos" / "descarregar.yaml"
    dados = yaml.safe_load(ficheiro.read_text(encoding="utf-8"))
    minutos = int(ligacao.VALIDADE.total_seconds() // 60)
    dados["expirada"] = dados["expirada"].format(minutos=minutos)
    return TextosDescarregar.model_validate(dados)


@dataclass(frozen=True)
class _Ficheiro:
    dados: bytes
    tipo_mime: str
    nome: str
    contagem: TipoContagem


def _aviso(estado: EstadoLigacao) -> HTMLResponse:
    t = textos_descarregar()
    texto = t.expirada if estado is EstadoLigacao.EXPIRADA else t.invalida
    conteudo = (
        f"<p>{html.escape(texto)}</p><p>{html.escape(t.voltar)}</p>"
        f'<p><a href="/">{html.escape(t.inicio)}</a></p>'
    )
    corpo = Template(modelo_cancelar()).substitute(
        titulo=html.escape(t.titulo),
        conteudo=conteudo,
        **{f"cor_{k}": v for k, v in CORES.items()},
    )
    return HTMLResponse(corpo, status_code=ESTADOS_HTTP[estado], headers=CABECALHOS)


def _gerar(s: Session, pedido: ligacao.PedidoDescarga) -> _Ficheiro | None:
    """O ficheiro pedido; None se o plano já não existir (ou for de outra conta)."""
    if pedido.tipo is TipoDescarga.DADOS:
        dados = repositorios.exportar_dados(s, pedido.utilizador_id)
        return _Ficheiro(
            json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            FICHEIRO_DADOS,
            TipoContagem.DADOS_DESCARREGADOS,
        )
    guardado = repositorios.obter_plano(s, pedido.utilizador_id, pedido.plano_id)
    if guardado is None:
        return None
    return _Ficheiro(
        plano_pdf(guardado.plano, guardado.criado_em, guardado.idade),
        "application/pdf",
        FICHEIRO_PDF.format(data=dia_em_lisboa(guardado.criado_em).isoformat()),
        TipoContagem.PDF_DESCARREGADO,
    )


def descarregar(
    request: Request,
    fabrica: sessionmaker[Session],
    config: Configuracao,
    relogio: Callable[[], datetime],
) -> Response:
    pedido = ligacao.ler(request.query_params.get("t", ""))
    segredo = config.vigoria_segredo_lembretes
    if pedido is None or segredo is None:
        registo.info("descarregar: ligação inválida")
        return _aviso(EstadoLigacao.INVALIDA)
    ficheiro: _Ficheiro | None = None
    with fabrica.begin() as s:
        sub = repositorios.sub_do_utilizador(s, pedido.utilizador_id)
        estado = (
            EstadoLigacao.INVALIDA
            if sub is None
            else ligacao.verificar(pedido, sub, segredo, relogio())
        )
        if estado is EstadoLigacao.VALIDA:
            ficheiro = _gerar(s, pedido)
            if ficheiro is None:
                estado = EstadoLigacao.INVALIDA
            else:
                contar(s, ficheiro.contagem)
    registo.info("descarregar: %s, utilizador %s, %s", pedido.tipo, pedido.utilizador_id, estado)
    if ficheiro is None:
        return _aviso(estado)
    cabecalhos = CABECALHOS | {"Content-Disposition": f'inline; filename="{ficheiro.nome}"'}
    return Response(ficheiro.dados, media_type=ficheiro.tipo_mime, headers=cabecalhos)
