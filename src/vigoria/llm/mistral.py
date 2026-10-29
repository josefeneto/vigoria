"""Provedor Mistral, pela API compatível com a OpenAI (endereço europeu: dados na UE/EFTA).

O modelo vem de MISTRAL_MODEL (config.py). A lógica está em llm/openai_compat.py.
Os nomes dos cabeçalhos de limites não estão confirmados na documentação: o
--testar-ligacao mostra todos os que tiverem «ratelimit» no nome.
"""

import httpx

from vigoria.llm.openai_compat import ProvedorCompativelOpenAI


class ProvedorMistral(ProvedorCompativelOpenAI):
    nome = "mistral"
    rotulo = "Mistral"
    url_base = "https://api.eu.mistral.ai/v1"

    def limites(self, cabecalhos: httpx.Headers) -> tuple[str, ...]:
        linhas = tuple(
            f"{nome}: {valor}" for nome, valor in cabecalhos.items() if "ratelimit" in nome.lower()
        )
        return linhas or ("Limites: a resposta não trouxe cabeçalhos «ratelimit».",)
