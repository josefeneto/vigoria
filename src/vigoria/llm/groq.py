"""Provedor Groq (fornecedor de reserva), pela API compatível com a OpenAI.

O modelo vem de GROQ_MODEL (config.py). A lógica está em llm/openai_compat.py.
Cabeçalhos da Groq: x-ratelimit-*-tokens são tokens por MINUTO e x-ratelimit-*-requests
são pedidos por DIA. Os tokens por dia não vêm em nenhum cabeçalho.
"""

from vigoria.llm.openai_compat import ProvedorCompativelOpenAI


class ProvedorGroq(ProvedorCompativelOpenAI):
    nome = "groq"
    rotulo = "Groq"
    url_base = "https://api.groq.com/openai/v1"
    cabecalhos_limites = (
        ("x-ratelimit-limit-tokens", "Tokens por minuto (limite)"),
        ("x-ratelimit-remaining-tokens", "Tokens por minuto (disponíveis agora)"),
        ("x-ratelimit-limit-requests", "Pedidos por dia (limite)"),
        ("x-ratelimit-remaining-requests", "Pedidos por dia (disponíveis)"),
    )
    notas_limites = (
        "Tokens por dia: a Groq não os indica nos cabeçalhos "
        "(ver https://console.groq.com/settings/limits).",
    )
