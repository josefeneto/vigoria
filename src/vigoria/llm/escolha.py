"""Escolha do fornecedor de LLM: VIGORIA_PROVEDOR_LLM e, opcional, VIGORIA_PROVEDOR_RESERVA.

A reserva só é usada quando o principal falha de vez (ErroLLM.permite_reserva):
503/504 depois das repetições, tempo máximo excedido, quota diária esgotada ou
pedido demasiado grande (413). Nunca por o principal demorar, dentro dos 120 s.
"""

from collections.abc import Callable

from pydantic import BaseModel

from vigoria.config import Configuracao, NomeProvedor, obter_configuracao
from vigoria.llm.base import ErroLLM, Progresso, ProvedorLLM, RespostaTeste, progresso_stderr
from vigoria.llm.gemini import ProvedorGemini
from vigoria.llm.groq import ProvedorGroq
from vigoria.llm.mistral import ProvedorMistral

FORNECEDORES: dict[str, Callable[[Configuracao], ProvedorLLM]] = {
    "gemini": lambda config: ProvedorGemini(config=config),
    "groq": lambda config: ProvedorGroq(config=config),
    "mistral": lambda config: ProvedorMistral(config=config),
}


def criar_fornecedor(nome: NomeProvedor, config: Configuracao | None = None) -> ProvedorLLM:
    """Um fornecedor pelo nome, com a chave e o modelo da configuração."""
    return FORNECEDORES[nome](obter_configuracao() if config is None else config)


def criar_provedor(config: Configuracao | None = None) -> ProvedorComReserva:
    """O fornecedor principal e, se estiver configurada, a reserva."""
    config = obter_configuracao() if config is None else config
    principal = criar_fornecedor(config.vigoria_provedor_llm, config)
    reserva = config.vigoria_provedor_reserva
    return ProvedorComReserva(principal, criar_fornecedor(reserva, config) if reserva else None)


class ProvedorComReserva:
    """Implementa ProvedorLLM: tenta o principal e, se falhar de vez, a reserva."""

    def __init__(
        self,
        principal: ProvedorLLM,
        reserva: ProvedorLLM | None = None,
        progresso: Progresso = progresso_stderr,
    ) -> None:
        self.principal = principal
        self.reserva = reserva
        self.nome = principal.nome
        self.modelo = principal.modelo
        self.ultimo_provedor: str | None = None
        self._progresso = progresso

    def gerar_json[M: BaseModel](self, sistema: str, pedido: str, schema: type[M]) -> M:
        usado = self.principal
        try:
            resultado = self.principal.gerar_json(sistema, pedido, schema)
        except ErroLLM as erro:
            if self.reserva is None or not erro.permite_reserva:
                raise
            usado = self.reserva
            self._progresso(
                f"{self.principal.nome} falhou de vez (código {erro.codigo or '-'}); "
                f"a usar a reserva {usado.nome}"
            )
            try:
                resultado = usado.gerar_json(sistema, pedido, schema)
            except ErroLLM as erro_reserva:
                raise ErroLLM(
                    f"{erro} A reserva ({usado.nome}) também falhou: {erro_reserva}",
                    erro_reserva.codigo,
                ) from None
        self.ultimo_provedor = usado.nome
        self._progresso(f"resposta gerada por: {usado.nome} (modelo {usado.modelo})")
        return resultado

    def testar_ligacao(self) -> RespostaTeste:
        return self.principal.testar_ligacao()
