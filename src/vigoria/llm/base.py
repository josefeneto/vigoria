"""Interface comum aos provedores de LLM e a lógica que todos partilham.

Os provedores só registam métricas (tempo, tokens, tentativas), nunca o conteúdo
do pedido ou da resposta: o pedido leva dados de saúde (REGRAS_DOMINIO e RGPD).

`ProvedorBase` trata, para todos, do tempo máximo, das repetições (429 por minuto,
503/504), do progresso em stderr e das mensagens de erro. Cada provedor só diz como
chamar o serviço e como classificar os erros dele (`_falha`).
"""

import logging
import sys
import time
from collections.abc import Callable
from enum import StrEnum
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

registo = logging.getLogger("vigoria.llm")

MAX_TENTATIVAS = 3
TIMEOUT_S = 120  # por chamada
TIMEOUT_TESTE_S = 30  # --testar-ligacao
ESPERA_MAX_S = 60.0
ESPERA_EXPONENCIAL = wait_exponential(multiplier=2, min=2, max=ESPERA_MAX_S)  # 2 s, 4 s, ...
PERGUNTA_TESTE = "Responde só: ok"

Progresso = Callable[[str], None]


def progresso_stderr(mensagem: str) -> None:
    """Escreve uma linha de progresso em stderr (só metadados)."""
    print(f"[vigoria.llm] {mensagem}", file=sys.stderr, flush=True)


class ErroLLM(Exception):
    """Falha na chamada à LLM. A mensagem nunca inclui o conteúdo do pedido ou da resposta.

    `codigo` é o código HTTP devolvido pelo serviço (None: rede, tempo esgotado ou formato).
    `permite_reserva`: o fornecedor falhou de vez e vale a pena tentar a reserva
    (503/504 depois das repetições, tempo máximo, quota diária, pedido demasiado grande).
    `tipo`: a falha do serviço já classificada (None: rede, tempo esgotado, formato ou
    configuração); a interface usa-o para escolher a mensagem ao utilizador.
    """

    def __init__(
        self,
        mensagem: str,
        codigo: int | None = None,
        permite_reserva: bool = False,
        tipo: TipoFalha | None = None,
    ) -> None:
        super().__init__(mensagem)
        self.codigo = codigo
        self.permite_reserva = permite_reserva
        self.tipo = tipo


class Metricas(BaseModel):
    """O que se regista de cada chamada."""

    model_config = ConfigDict(frozen=True)

    provedor: str
    modelo: str
    segundos: float
    tentativas: int
    tokens_entrada: int | None = None
    tokens_saida: int | None = None


class RespostaTeste(BaseModel):
    """Resultado de --testar-ligacao: o texto devolvido e, se houver, os limites da conta."""

    model_config = ConfigDict(frozen=True)

    texto: str
    limites: tuple[str, ...] = ()  # linhas já legíveis, por exemplo «Tokens por minuto: 8000»


class ProvedorLLM(Protocol):
    """Gera uma resposta JSON validada pelo schema Pydantic indicado."""

    nome: str
    modelo: str
    ultimo_provedor: str | None  # o fornecedor que respondeu à última chamada

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        """Chama a LLM com o prompt de sistema e o pedido; devolve a resposta validada.

        Levanta ErroLLM se a chamada falhar ou a resposta não respeitar o schema.
        """
        ...

    def testar_ligacao(self) -> RespostaTeste:
        """Pergunta mínima (30 s no máximo, sem repetições) para confirmar chave, modelo e rede."""
        ...


def registar_metricas(metricas: Metricas) -> None:
    """Regista só identificadores técnicos e números."""
    registo.info("chamada LLM concluída", extra={"metricas": metricas.model_dump()})


# ---------------------------------------------------------------- Erros do serviço


class TipoFalha(StrEnum):
    POR_MINUTO = "por_minuto"  # 429 que vale a pena repetir
    QUOTA_DIARIA = "quota_diaria"  # 429 que não se repete
    INDISPONIVEL = "indisponivel"  # 503/504: repete; no fim, reserva
    DEMASIADO_GRANDE = "demasiado_grande"  # 413: não repete; reserva
    OUTRA = "outra"


REPETIVEIS = frozenset({TipoFalha.POR_MINUTO, TipoFalha.INDISPONIVEL})
PARA_RESERVA = frozenset(
    {TipoFalha.QUOTA_DIARIA, TipoFalha.INDISPONIVEL, TipoFalha.DEMASIADO_GRANDE}
)


class FalhaApi(BaseModel):
    """Erro do serviço já classificado. Nunca guarda a mensagem do serviço (pode citar o pedido)."""

    model_config = ConfigDict(frozen=True)

    codigo: int
    tipo: TipoFalha
    espera_s: float | None = None  # sugerida pelo serviço (retryDelay, retry-after)


# ---------------------------------------------------------------- Provedor base


class ProvedorBase:
    """Lógica comum. As subclasses definem `nome`, `rotulo`, `_falha` e `_tokens`.

    `dormir` e `progresso` só se mudam nos testes (sem esperas reais).
    """

    nome = ""  # identificador técnico: «gemini», «groq»
    rotulo = ""  # nome nas mensagens: «Gemini», «Groq»

    def __init__(
        self,
        modelo: str,
        timeout_s: float = TIMEOUT_S,
        dormir: Callable[[float], None] = time.sleep,
        progresso: Progresso = progresso_stderr,
    ) -> None:
        self.modelo = modelo
        self.timeout_s = timeout_s
        self.ultimo_provedor: str | None = None
        self.ultimas_metricas: Metricas | None = None
        self._dormir = dormir
        self._progresso = progresso

    # -- a definir em cada provedor

    def _falha(self, erro: BaseException) -> FalhaApi | None:
        """Classifica um erro do serviço; None se não for um erro do serviço."""
        raise NotImplementedError

    def _tokens(self, resposta: Any) -> tuple[int | None, int | None]:
        """Tokens de entrada e de saída da resposta."""
        raise NotImplementedError

    def _texto_quota_diaria(self, falha: FalhaApi) -> str:
        return "quota diária esgotada, tenta mais tarde"

    # -- comum

    def _validar[M: BaseModel](self, schema: type[M], texto: str) -> M:
        try:
            return schema.model_validate_json(texto)
        except ValidationError:
            # Sem o conteúdo nem os detalhes da validação (podem citar a resposta).
            raise ErroLLM(f"A resposta do {self.rotulo} não respeita o formato do plano.") from None

    def _executar[R](self, chamada: Callable[[], R], timeout_s: float, repetir: bool = True) -> R:
        """Faz a chamada com as repetições (429 por minuto, 503/504) e regista as métricas."""
        maximo = MAX_TENTATIVAS if repetir else 1
        tentativas = Retrying(
            retry=retry_if_exception(self._repetivel),
            stop=stop_after_attempt(maximo),
            wait=self._espera,
            sleep=self._dormir,
            before_sleep=self._antes_de_esperar,
            reraise=True,
        )
        inicio = time.perf_counter()
        numero = 0
        try:
            for tentativa in tentativas:
                with tentativa:
                    numero = tentativa.retry_state.attempt_number
                    self._progresso(
                        f"{self.nome}: chamada iniciada (tentativa {numero}/{maximo}, "
                        f"modelo {self.modelo}, tempo máximo {timeout_s:g} s)"
                    )
                    resposta = chamada()
        except httpx.TimeoutException:
            segundos = time.perf_counter() - inicio
            self._progresso(f"{self.nome}: sem resposta ao fim de {segundos:.1f} s")
            raise ErroLLM(
                f"O {self.rotulo} não respondeu em {timeout_s:g} s. Verifique a ligação à "
                "Internet e tente de novo.",
                permite_reserva=True,
            ) from None
        except httpx.HTTPError as erro:
            self._progresso(f"{self.nome}: falha de rede ({type(erro).__name__})")
            raise ErroLLM(
                f"Não foi possível ligar ao {self.rotulo}. Verifique a ligação à Internet."
            ) from None
        except Exception as erro:
            falha = self._falha(erro)
            if falha is None:
                raise
            raise self._erro_api(falha, numero, inicio) from None

        segundos = round(time.perf_counter() - inicio, 3)
        entrada, saida = self._tokens(resposta)
        self.ultimas_metricas = Metricas(
            provedor=self.nome,
            modelo=self.modelo,
            segundos=segundos,
            tentativas=numero,
            tokens_entrada=entrada,
            tokens_saida=saida,
        )
        registar_metricas(self.ultimas_metricas)
        self._progresso(
            f"{self.nome}: chamada concluída em {segundos:.1f} s (tentativa {numero}; "
            f"tokens: {entrada} de entrada, {saida} de saída)"
        )
        self.ultimo_provedor = self.nome
        return resposta

    def _repetivel(self, erro: BaseException) -> bool:
        falha = self._falha(erro)
        return falha is not None and falha.tipo in REPETIVEIS

    def _espera(self, estado: RetryCallState) -> float:
        """A maior entre a exponencial e a sugerida pelo serviço, no máximo 60 s."""
        erro = estado.outcome.exception() if estado.outcome else None
        falha = self._falha(erro) if erro is not None else None
        sugerida = falha.espera_s if falha is not None else None
        return min(max(ESPERA_EXPONENCIAL(estado), sugerida or 0.0), ESPERA_MAX_S)

    def _antes_de_esperar(self, estado: RetryCallState) -> None:
        espera = estado.next_action.sleep if estado.next_action else 0.0
        erro = estado.outcome.exception() if estado.outcome else None
        falha = self._falha(erro) if erro is not None else None
        motivo = (
            "limite de pedidos por minuto (429)"
            if falha is None or falha.tipo is TipoFalha.POR_MINUTO
            else f"serviço indisponível ({falha.codigo})"
        )
        self._progresso(
            f"{self.nome}: {motivo} na tentativa {estado.attempt_number}; "
            f"nova tentativa daqui a {espera:.1f} s"
        )

    def _erro_api(self, falha: FalhaApi, tentativas: int, inicio: float) -> ErroLLM:
        """Erro claro, só com o código: a mensagem do serviço pode citar partes do pedido."""
        segundos = time.perf_counter() - inicio
        self._progresso(
            f"{self.nome}: erro {falha.codigo} ao fim de {segundos:.1f} s (tentativa {tentativas})"
        )
        reserva = falha.tipo in PARA_RESERVA
        match falha.tipo:
            case TipoFalha.QUOTA_DIARIA:
                mensagem = f"O {self.rotulo} recusou o pedido: {self._texto_quota_diaria(falha)}."
            case TipoFalha.POR_MINUTO:
                mensagem = (
                    f"O {self.rotulo} recusou {tentativas} pedidos seguidos por limite de "
                    "pedidos por minuto (429). Tente daqui a alguns minutos."
                )
            case TipoFalha.INDISPONIVEL:
                mensagem = (
                    f"O {self.rotulo} está indisponível (código {falha.codigo}) depois de "
                    f"{tentativas} tentativa(s). Tente mais tarde."
                )
            case TipoFalha.DEMASIADO_GRANDE:
                mensagem = (
                    f"O pedido é demasiado grande para os limites do {self.rotulo} "
                    f"(código {falha.codigo})."
                )
            case _:
                mensagem = f"O {self.rotulo} devolveu um erro (código {falha.codigo})."
        return ErroLLM(mensagem, falha.codigo, permite_reserva=reserva, tipo=falha.tipo)
