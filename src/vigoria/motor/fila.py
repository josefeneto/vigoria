"""Fila de geração (Fase 10C): um plano de cada vez, por processo.

Em produção há um só contentor com um só processo Streamlit (Railway, réplicas = 1), e cada
sessão corre numa thread: um threading.Lock chega. Um plano faz até 3 chamadas à LLM; com
gerações em paralelo, o limite de tokens por minuto do fornecedor esgotava-se mais depressa.

Quem chega com outra geração a decorrer espera a vez, no máximo ESPERA_MAX_S. Depois disso,
FilaOcupada: a interface pede para tentar mais tarde (paginas/textos.py).
"""

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

registo = logging.getLogger(__name__)

ESPERA_MAX_S = 180.0  # 3 minutos
_TRANCA = threading.Lock()


class FilaOcupada(Exception):
    """A vez não chegou dentro do tempo máximo de espera."""


@contextmanager
def vez_na_fila(
    ao_esperar: Callable[[], None] | None = None,
    espera_max_s: float = ESPERA_MAX_S,
    tranca: threading.Lock = _TRANCA,
) -> Iterator[None]:
    """Bloco com a vez de gerar. Se tiver de esperar, chama primeiro `ao_esperar`."""
    if not tranca.acquire(blocking=False):
        if ao_esperar is not None:
            ao_esperar()
        inicio = time.perf_counter()
        registo.info("fila: à espera da vez")
        if not tranca.acquire(timeout=espera_max_s):
            registo.warning("fila: espera máxima de %.0f s excedida", espera_max_s)
            raise FilaOcupada
        registo.info("fila: vez obtida ao fim de %.1f s", time.perf_counter() - inicio)
    try:
        yield
    finally:
        tranca.release()
