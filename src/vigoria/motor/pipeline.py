"""Pipeline de geração: estratégia → treino e semana (motor) → gerador → voz → verificação.

Só o texto da LLM pode levar a uma regeneração; uma falha do que o motor monta é um
erro do código (ErroMotor), sem nova chamada.

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
from vigoria.motor.ortografia import palavras_desconhecidas
from vigoria.motor.verificacao import TIPOS_DO_MOTOR, Falha, verificar
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
    palavras_desconhecidas: tuple[str, ...] = ()  # ortografia: só aviso, não chumba


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
    falhas = _verificar(plano, e, q)
    motivos: tuple[str, ...] = ()
    if falhas:
        progresso(f"verificação: {_resumo(falhas)}; uma regeneração com os motivos")
        motivos = tuple(f.motivo for f in falhas)
        plano = _gerar(q, e, contado, motivos)
        falhas = _verificar(plano, e, q)
        if falhas:
            progresso(f"verificação depois da regeneração: {_resumo(falhas)}; plano recusado")
            raise ErroVerificacao(tuple(f.motivo for f in falhas))
        progresso("verificação: aprovado depois da regeneração")
    else:
        progresso("verificação: aprovado à primeira")

    desconhecidas = palavras_desconhecidas(plano)
    if desconhecidas:
        progresso(f"ortografia: {len(desconhecidas)} palavra(s) desconhecida(s) (só aviso)")
    return ResultadoPipeline(
        plano=plano,
        estrategia=e,
        chamadas=contado.chamadas,
        motivos_regeneracao=motivos,
        palavras_desconhecidas=desconhecidas,
    )


class ErroMotor(ErroGeracao):
    """Falhou uma verificação do que o próprio código monta: é um erro do código."""

    def __init__(self, motivos: tuple[str, ...]) -> None:
        super().__init__(textos.PLANO_NAO_VERIFICADO)
        self.motivos = motivos


def _verificar(plano: Plano, e: Estrategia, q: Questionario) -> list[Falha]:
    """Falhas do texto da LLM (regeneráveis). Uma falha do motor interrompe logo."""
    falhas = verificar(plano, e, q)
    do_motor = tuple(f.motivo for f in falhas if f.tipo in TIPOS_DO_MOTOR)
    if do_motor:
        raise ErroMotor(do_motor)
    return falhas


def _gerar(
    q: Questionario, e: Estrategia, provedor: _ProvedorContado, motivos: tuple[str, ...]
) -> Plano:
    return aplicar_voz(gerar_plano(q, e, provedor, motivos), e)  # type: ignore[arg-type]


def _resumo(falhas: list[Falha]) -> str:
    """Só o número de falhas por tipo (metadados)."""
    contagem = Counter(f.tipo.value for f in falhas)
    return f"{len(falhas)} falha(s) (" + ", ".join(f"{t}: {n}" for t, n in contagem.items()) + ")"
