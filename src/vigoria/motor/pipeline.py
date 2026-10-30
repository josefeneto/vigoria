"""Pipeline de geração: estratégia → gerador → voz → verificação, e uma regeneração se preciso.

No máximo 3 chamadas à LLM por plano (CLAUDE.md): geração, revisão crítica (ainda por
fazer) e uma única regeneração com os motivos da verificação. Se a regeneração também
falhar, ErroVerificacao: a mensagem é para o utilizador; os motivos, para a CLI.
O progresso (stderr) só leva metadados: número e tipo das falhas, nunca o conteúdo.
"""

from collections import Counter

from pydantic import BaseModel, ConfigDict

from vigoria.llm.base import Progresso, ProvedorLLM, progresso_stderr
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import Plano
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import ErroGeracao, gerar_plano
from vigoria.motor.verificacao import Falha, verificar
from vigoria.motor.voz import aplicar_voz
from vigoria.regras import textos

MAX_CHAMADAS = 3


class ErroVerificacao(ErroGeracao):
    """O plano falhou a verificação também depois da regeneração."""

    def __init__(self, motivos: tuple[str, ...]) -> None:
        super().__init__(textos.PLANO_NAO_VERIFICADO)
        self.motivos = motivos


class ResultadoPipeline(BaseModel):
    model_config = ConfigDict(frozen=True)

    plano: Plano
    estrategia: Estrategia
    chamadas: int
    motivos_regeneracao: tuple[str, ...] = ()  # vazio se passou à primeira


class _ProvedorContado:
    """Conta as chamadas e recusa a que ultrapassar o máximo."""

    def __init__(self, provedor: ProvedorLLM, maximo: int = MAX_CHAMADAS) -> None:
        self._provedor = provedor
        self._maximo = maximo
        self.chamadas = 0
        self.nome = provedor.nome
        self.modelo = provedor.modelo

    @property
    def ultimo_provedor(self) -> str | None:
        return self._provedor.ultimo_provedor

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        if self.chamadas >= self._maximo:
            raise ErroGeracao(f"Máximo de {self._maximo} chamadas à LLM por plano.")
        self.chamadas += 1
        return self._provedor.gerar_json(sistema, pedido, schema)


def gerar_plano_verificado(
    q: Questionario, provedor: ProvedorLLM, progresso: Progresso = progresso_stderr
) -> ResultadoPipeline:
    """O plano completo, já com os avisos obrigatórios e verificado."""
    e = gerar_estrategia(q)
    contado = _ProvedorContado(provedor)

    plano = _gerar(q, e, contado, ())
    falhas = verificar(plano, e, q)
    if not falhas:
        progresso("verificação: aprovado à primeira")
        return ResultadoPipeline(plano=plano, estrategia=e, chamadas=contado.chamadas)

    progresso(f"verificação: {_resumo(falhas)}; uma regeneração com os motivos")
    motivos = tuple(f.motivo for f in falhas)
    plano = _gerar(q, e, contado, motivos)
    falhas = verificar(plano, e, q)
    if falhas:
        progresso(f"verificação depois da regeneração: {_resumo(falhas)}; plano recusado")
        raise ErroVerificacao(tuple(f.motivo for f in falhas))
    progresso("verificação: aprovado depois da regeneração")
    return ResultadoPipeline(
        plano=plano, estrategia=e, chamadas=contado.chamadas, motivos_regeneracao=motivos
    )


def _gerar(
    q: Questionario, e: Estrategia, provedor: _ProvedorContado, motivos: tuple[str, ...]
) -> Plano:
    return aplicar_voz(gerar_plano(q, e, provedor, motivos), e)  # type: ignore[arg-type]


def _resumo(falhas: list[Falha]) -> str:
    """Só o número de falhas por tipo (metadados)."""
    contagem = Counter(f.tipo.value for f in falhas)
    return f"{len(falhas)} falha(s) (" + ", ".join(f"{t}: {n}" for t, n in contagem.items()) + ")"
