"""Pipeline de geração: estratégia → treino e semana (motor) → gerador → voz → verificação.

Só o texto da LLM pode levar a uma regeneração; uma falha do que o motor monta é um
erro do código (ErroMotor), sem nova chamada. O estilo (brasileirismos, grafia anterior
ao AO90, «garantir») é corrigido em voz.py, sem chamar a LLM.

No máximo 3 chamadas à LLM por plano (CLAUDE.md): geração, uma regeneração com os motivos
da verificação e, se a regeneração também falhar, uma terceira chamada para o fornecedor
de reserva, se estiver configurado (decisão de 30/10/2026). Se ainda falhar (ou sem
reserva), ErroVerificacao: a mensagem é para o utilizador; os motivos, para a CLI.
O progresso (stderr) só leva metadados: números e tipos, nunca o conteúdo.
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
from vigoria.motor.voz import RevisaoEstilo, inserir_avisos, rever_estilo
from vigoria.regras import textos

MAX_CHAMADAS = 3


class ErroVerificacao(ErroGeracao):
    """O plano falhou a verificação em todas as tentativas permitidas."""

    def __init__(self, motivos: tuple[str, ...]) -> None:
        super().__init__(textos.PLANO_NAO_VERIFICADO)
        self.motivos = motivos


class ErroMotor(ErroGeracao):
    """Falhou uma verificação do que o próprio código monta: é um erro do código."""

    def __init__(self, motivos: tuple[str, ...]) -> None:
        super().__init__(textos.PLANO_NAO_VERIFICADO)
        self.motivos = motivos


class ResultadoPipeline(BaseModel):
    model_config = ConfigDict(frozen=True)

    plano: Plano
    estrategia: Estrategia
    chamadas: int
    motivos_regeneracao: tuple[str, ...] = ()  # vazio se passou à primeira
    reserva_na_verificacao: bool = False  # a terceira chamada foi para a reserva
    correcoes_estilo: tuple[str, ...] = ()  # feitas pelo motor (voz.py)
    avisos_estilo: tuple[str, ...] = ()  # sem correção conhecida: só aviso
    palavras_desconhecidas: tuple[str, ...] = ()  # ortografia: só aviso, não chumba


class _ProvedorContado:
    """Conta as chamadas (também as da reserva) e recusa a que ultrapassar o máximo."""

    def __init__(self, provedor: ProvedorLLM, maximo: int = MAX_CHAMADAS) -> None:
        self._maximo = maximo
        self.chamadas = 0
        self.usar(provedor)

    def usar(self, provedor: ProvedorLLM) -> None:
        self._provedor = provedor
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
    """O plano completo, já com os avisos obrigatórios, o estilo corrigido e verificado."""
    e = gerar_estrategia(q)
    contado = _ProvedorContado(provedor)

    revisao = _gerar(q, e, contado, ())
    falhas = _verificar(revisao.plano, e, q)
    motivos: tuple[str, ...] = ()
    usou_reserva = False
    if falhas:
        progresso(f"verificação: {_resumo(falhas)}; uma regeneração com os motivos")
        motivos = tuple(f.motivo for f in falhas)
        revisao = _gerar(q, e, contado, motivos)
        falhas = _verificar(revisao.plano, e, q)
        reserva: ProvedorLLM | None = getattr(provedor, "reserva", None)
        if falhas and reserva is not None:
            progresso(
                f"verificação depois da regeneração: {_resumo(falhas)}; terceira chamada para "
                f"a reserva {reserva.nome}"
            )
            contado.usar(reserva)
            usou_reserva = True
            revisao = _gerar(q, e, contado, tuple(f.motivo for f in falhas))
            falhas = _verificar(revisao.plano, e, q)
        etapa = "na reserva" if usou_reserva else "depois da regeneração"
        if falhas:
            progresso(f"verificação {etapa}: {_resumo(falhas)}; plano recusado")
            raise ErroVerificacao(tuple(f.motivo for f in falhas))
        progresso(f"verificação: aprovado {etapa}")
    else:
        progresso("verificação: aprovado à primeira")

    plano = revisao.plano
    if revisao.correcoes or revisao.avisos:
        progresso(
            f"estilo: {len(revisao.correcoes)} correção(ões) automática(s); "
            f"{len(revisao.avisos)} aviso(s) sem correção (não bloqueiam)"
        )
    desconhecidas = palavras_desconhecidas(plano)
    if desconhecidas:
        progresso(f"ortografia: {len(desconhecidas)} palavra(s) desconhecida(s) (só aviso)")
    return ResultadoPipeline(
        plano=plano,
        estrategia=e,
        chamadas=contado.chamadas,
        motivos_regeneracao=motivos,
        reserva_na_verificacao=usou_reserva,
        correcoes_estilo=revisao.correcoes,
        avisos_estilo=revisao.avisos,
        palavras_desconhecidas=desconhecidas,
    )


def _verificar(plano: Plano, e: Estrategia, q: Questionario) -> list[Falha]:
    """Falhas do texto da LLM (regeneráveis). Uma falha do motor interrompe logo."""
    falhas = verificar(plano, e, q)
    do_motor = tuple(f.motivo for f in falhas if f.tipo in TIPOS_DO_MOTOR)
    if do_motor:
        raise ErroMotor(do_motor)
    return falhas


def _gerar(
    q: Questionario, e: Estrategia, provedor: _ProvedorContado, motivos: tuple[str, ...]
) -> RevisaoEstilo:
    plano = gerar_plano(q, e, provedor, motivos)  # type: ignore[arg-type]
    return rever_estilo(inserir_avisos(plano, e))


def _resumo(falhas: list[Falha]) -> str:
    """Só o número de falhas por tipo (metadados)."""
    contagem = Counter(f.tipo.value for f in falhas)
    return f"{len(falhas)} falha(s) (" + ", ".join(f"{t}: {n}" for t, n in contagem.items()) + ")"
