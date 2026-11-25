"""Descarregar o plano (PDF) ou os dados (JSON) na app instalada (25/11/2026).

O Caddy encaminha /descarregar para aqui (o mesmo uvicorn de web/cancelar.py). A app mostra
esta ligação só quando está instalada no ecrã principal (exportacao/ligacao.py explica o
token). O iPhone abre-a na mesma janela da app, sem botão de voltar (o endereço pertence à
app, `scope` do manifesto). Por isso:

- GET /descarregar?t=…: uma página da Vigoria com a barra «Voltar à Vigoria» sempre no topo
  e um botão que entrega o ficheiro ao menu de partilha do telemóvel (guardar em Ficheiros,
  abrir noutra app, enviar). O ficheiro não se mostra na página. Conta a descarga
  (dados/gestao.py), sem quem.
- GET /descarregar?t=…&ficheiro=1: o ficheiro em si, que a página vai buscar (não conta).

Os registos só têm o tipo, o id técnico e o resultado; nunca o token, o email nem o conteúdo.
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
from vigoria.notificacoes.lembrete import CORES
from vigoria.regras.progresso import dia_em_lisboa

registo = logging.getLogger(__name__)

CABECALHOS = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
ESTADOS_HTTP = {EstadoLigacao.INVALIDA: 400, EstadoLigacao.EXPIRADA: 410}
FICHEIRO_PDF = "vigoria_plano_{data}.pdf"  # como paginas/textos.PDF_FICHEIRO
FICHEIRO_DADOS = "vigoria_os_meus_dados.json"  # como paginas/textos.CONTA_EXPORTAR_FICHEIRO
VOLTAR_PARA = {TipoDescarga.PDF: "/plano", TipoDescarga.DADOS: "/conta"}  # sem histórico


class TextosDescarregar(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    titulo: str
    voltar: str
    invalida: str
    expirada: str
    pdf_titulo: str
    pdf_texto: str
    pdf_botao: str
    dados_titulo: str
    dados_texto: str
    dados_botao: str
    a_preparar: str
    erro: str
    nota: str


def _modelo(nome: str) -> str:
    return files("vigoria.notificacoes").joinpath("modelos", nome).read_text(encoding="utf-8")


@cache
def textos_descarregar() -> TextosDescarregar:
    dados = yaml.safe_load(_modelo("descarregar.yaml"))
    minutos = int(ligacao.VALIDADE.total_seconds() // 60)
    dados["expirada"] = dados["expirada"].format(minutos=minutos)
    return TextosDescarregar.model_validate(dados)


@dataclass(frozen=True)
class _Ficheiro:
    gerar: Callable[[], bytes]
    tipo_mime: str
    nome: str
    contagem: TipoContagem


# A página vai buscar o ficheiro e entrega-o ao menu de partilha (Web Share API); sem ele
# (computador, navegadores antigos), descarrega-o. O botão só fica ativo com o ficheiro pronto:
# o iPhone só abre o menu de partilha dentro do próprio toque.
_SCRIPT = """<script>
(function () {
  var cfg = __CONFIG__;
  var botao = document.getElementById("partilhar");
  var aviso = document.getElementById("aviso");
  var ficheiro = null;
  fetch(cfg.url, { cache: "no-store", credentials: "same-origin" })
    .then(function (r) { if (!r.ok) { throw new Error(); } return r.blob(); })
    .then(function (b) {
      ficheiro = new File([b], cfg.nome, { type: cfg.tipo });
      botao.disabled = false;
      botao.textContent = cfg.botao;
    })
    .catch(function () { botao.hidden = true; aviso.textContent = cfg.erro; });
  botao.addEventListener("click", function () {
    if (!ficheiro) { return; }
    if (navigator.canShare && navigator.canShare({ files: [ficheiro] })) {
      navigator.share({ files: [ficheiro] }).catch(function () {});
      return;
    }
    var a = document.createElement("a");
    a.href = URL.createObjectURL(ficheiro);
    a.download = cfg.nome;
    document.body.appendChild(a);
    a.click();
    a.remove();
  });
})();
</script>"""


def _json_no_script(valor: object) -> str:
    """JSON seguro dentro de <script> (nada de «</script>» nem «<!--»)."""
    texto = json.dumps(valor, ensure_ascii=False)
    return texto.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _pagina(
    titulo: str,
    conteudo: str,
    voltar_url: str,
    estado: int = 200,
    script: str = "",
) -> HTMLResponse:
    t = textos_descarregar()
    corpo = Template(_modelo("descarregar.html")).substitute(
        titulo=html.escape(titulo),
        voltar=html.escape(t.voltar),
        voltar_url=html.escape(voltar_url),
        conteudo=conteudo,
        script=script,
        **{f"cor_{k}": v for k, v in CORES.items()},
    )
    return HTMLResponse(corpo, status_code=estado, headers=CABECALHOS)


def _aviso(estado: EstadoLigacao) -> HTMLResponse:
    t = textos_descarregar()
    texto = t.expirada if estado is EstadoLigacao.EXPIRADA else t.invalida
    return _pagina(t.titulo, f"<p>{html.escape(texto)}</p>", "/", ESTADOS_HTTP[estado])


def _ficheiro(s: Session, pedido: ligacao.PedidoDescarga) -> _Ficheiro | None:
    """O ficheiro pedido (gerado só quando é preciso); None se o plano já não existir."""
    if pedido.tipo is TipoDescarga.DADOS:
        dados = repositorios.exportar_dados(s, pedido.utilizador_id)
        return _Ficheiro(
            lambda: json.dumps(dados, ensure_ascii=False, indent=2).encode("utf-8"),
            "application/json",
            FICHEIRO_DADOS,
            TipoContagem.DADOS_DESCARREGADOS,
        )
    guardado = repositorios.obter_plano(s, pedido.utilizador_id, pedido.plano_id)
    if guardado is None:
        return None
    return _Ficheiro(
        lambda: plano_pdf(guardado.plano, guardado.criado_em, guardado.idade),
        "application/pdf",
        FICHEIRO_PDF.format(data=dia_em_lisboa(guardado.criado_em).isoformat()),
        TipoContagem.PDF_DESCARREGADO,
    )


def _pagina_ficheiro(pedido: ligacao.PedidoDescarga, ficheiro: _Ficheiro, token: str) -> Response:
    t = textos_descarregar()
    pdf = pedido.tipo is TipoDescarga.PDF
    titulo, texto, botao = (
        (t.pdf_titulo, t.pdf_texto, t.pdf_botao)
        if pdf
        else (t.dados_titulo, t.dados_texto, t.dados_botao)
    )
    conteudo = (
        f"<p>{html.escape(texto)}</p>"
        f'<button id="partilhar" type="button" disabled>{html.escape(t.a_preparar)}</button>'
        '<p id="aviso" role="status"></p>'
        f'<p class="nota">{html.escape(t.nota)}</p>'
    )
    config = {
        "url": f"{ligacao.url(token)}&ficheiro=1",
        "nome": ficheiro.nome,
        "tipo": ficheiro.tipo_mime,
        "botao": botao,
        "erro": t.erro,
    }
    script = _SCRIPT.replace("__CONFIG__", _json_no_script(config))
    return _pagina(titulo, conteudo, VOLTAR_PARA[pedido.tipo], script=script)


def descarregar(
    request: Request,
    fabrica: sessionmaker[Session],
    config: Configuracao,
    relogio: Callable[[], datetime],
) -> Response:
    token = request.query_params.get("t", "")
    so_ficheiro = request.query_params.get("ficheiro") == "1"
    pedido = ligacao.ler(token)
    segredo = config.vigoria_segredo_lembretes
    if pedido is None or segredo is None:
        registo.info("descarregar: ligação inválida")
        return _aviso(EstadoLigacao.INVALIDA)
    resposta: Response | None = None
    with fabrica.begin() as s:
        sub = repositorios.sub_do_utilizador(s, pedido.utilizador_id)
        estado = (
            EstadoLigacao.INVALIDA
            if sub is None
            else ligacao.verificar(pedido, sub, segredo, relogio())
        )
        ficheiro = _ficheiro(s, pedido) if estado is EstadoLigacao.VALIDA else None
        if estado is EstadoLigacao.VALIDA and ficheiro is None:
            estado = EstadoLigacao.INVALIDA
        if ficheiro is not None and so_ficheiro:
            disposicao = {"Content-Disposition": f'inline; filename="{ficheiro.nome}"'}
            resposta = Response(
                ficheiro.gerar(), media_type=ficheiro.tipo_mime, headers=CABECALHOS | disposicao
            )
        elif ficheiro is not None:  # a página conta a descarga; o ficheiro que ela busca, não
            contar(s, ficheiro.contagem)
            resposta = _pagina_ficheiro(pedido, ficheiro, token)
    registo.info(
        "descarregar: %s%s, utilizador %s, %s",
        pedido.tipo,
        " (ficheiro)" if so_ficheiro else "",
        pedido.utilizador_id,
        estado,
    )
    return resposta if resposta is not None else _aviso(estado)
