"""Que mensagem mostrar quando a geração falha. Nunca mostra detalhes técnicos.

Os motivos técnicos ficam no progresso (stderr) e, nos erros da verificação, em
`motivos`; ao utilizador só chega uma de poucas mensagens honestas (paginas/textos.py).
"""

from enum import StrEnum

from vigoria.llm.base import ErroLLM, TipoFalha
from vigoria.motor.pipeline import ErroMotor, ErroVerificacao


class TipoErroUtilizador(StrEnum):
    QUOTA_DIARIA = "quota_diaria"  # limite diário do serviço esgotado
    MUITOS_PEDIDOS = "muitos_pedidos"  # 429 por minuto, depois das repetições
    INDISPONIVEL = "indisponivel"  # 503/504, tempo esgotado, rede, resposta fora do formato
    RECUSADO = "recusado"  # o plano não passou na verificação
    OUTRO = "outro"


def classificar_erro(erro: Exception) -> TipoErroUtilizador:
    if isinstance(erro, ErroVerificacao | ErroMotor):
        return TipoErroUtilizador.RECUSADO
    if not isinstance(erro, ErroLLM):
        return TipoErroUtilizador.OUTRO
    match erro.tipo:
        case TipoFalha.QUOTA_DIARIA:
            return TipoErroUtilizador.QUOTA_DIARIA
        case TipoFalha.POR_MINUTO:
            return TipoErroUtilizador.MUITOS_PEDIDOS
        case TipoFalha.INDISPONIVEL | TipoFalha.DEMASIADO_GRANDE | None:
            return TipoErroUtilizador.INDISPONIVEL
        case _:
            return TipoErroUtilizador.OUTRO
