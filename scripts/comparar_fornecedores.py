"""Comparação Gemini vs Groq com as 5 personas fictícias de exemplos/ (Fase 10C).

CHAMA A LLM REAL (10 planos): só o José o corre, à mão. Uso (PowerShell, com o .venv ativo):

    python scripts/comparar_fornecedores.py --modelo-groq openai/gpt-oss-120b

O Gemini usa a GEMINI_API_KEY e o GEMINI_MODEL do .env; o Groq usa a GROQ_API_KEY com o modelo
indicado. Cada plano passa pelo gerador e pela voz de marca (sem reserva), e mede-se o texto
da LLM (motor/comparacao.py): falhas da verificação, menções a meses, palavras que o
dicionário pt_PT não conhece (apanham brasileirismos fora da lista), tempo e tokens.
A tabela fica em saidas/comparacao/ (fora do Git) e aparece no ecrã.
"""

import argparse
import io
import json
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from vigoria.config import Configuracao, obter_configuracao
from vigoria.llm.base import ErroLLM, ProvedorLLM
from vigoria.llm.escolha import criar_fornecedor
from vigoria.modelos.questionario import Questionario
from vigoria.motor.comparacao import PASTA_SAIDAS, Avaliacao, comparar
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import ErroGeracao

RAIZ = Path(__file__).resolve().parents[1]
PERSONAS = tuple(
    RAIZ / "exemplos" / f"persona_{nome}.json"
    for nome in ("teste", "50_alta", "imc36", "osteoporose", "renal")
)
COLUNAS = (
    "Persona",
    "Fornecedor",
    "Tempo (s)",
    "Tokens (entrada/saída)",
    "Falhas na verificação",
    "Meses",
    "Palavras desconhecidas",
    "Erro",
)


def _celula(texto: str) -> str:
    return texto.replace("|", "/").replace("\n", " ")


def linha(persona: str, a: Avaliacao) -> list[str]:
    """Uma linha da tabela; o fornecedor aparece com o modelo (dois modelos do mesmo)."""
    return [
        persona,
        f"{a.provedor} ({a.modelo})" if a.modelo else a.provedor,
        "-" if a.segundos is None else f"{a.segundos:.1f}",
        f"{a.tokens_entrada or '-'}/{a.tokens_saida or '-'}",
        ", ".join(a.falhas) or "nenhuma",
        str(a.mencoes_meses),
        ", ".join(a.palavras_desconhecidas) or "nenhuma",
        _celula(a.erro or ""),
    ]


def resumo(resultados: list[tuple[str, Avaliacao]]) -> list[str]:
    """Por fornecedor: planos gerados, planos sem falhas e tempo médio."""
    linhas = []
    nomes = dict.fromkeys(linha("", a)[1] for _, a in resultados)
    for nome in nomes:
        deste = [a for _, a in resultados if linha("", a)[1] == nome]
        gerados = [a for a in deste if not a.erro]
        limpos = [a for a in gerados if not a.falhas and not a.mencoes_meses]
        tempos = [a.segundos for a in gerados if a.segundos is not None]
        medio = f"{sum(tempos) / len(tempos):.1f} s" if tempos else "-"
        linhas.append(
            f"- **{nome}**: {len(gerados)}/{len(deste)} planos gerados, "
            f"{len(limpos)} sem falhas nem meses, tempo médio {medio}."
        )
    return linhas


def markdown(resultados: list[tuple[str, Avaliacao]], quando: datetime) -> str:
    tabela = [
        "| " + " | ".join(COLUNAS) + " |",
        "|" + "---|" * len(COLUNAS),
        *("| " + " | ".join(linha(p, a)) + " |" for p, a in resultados),
    ]
    return "\n".join(
        [
            f"# Comparação de fornecedores ({quando:%d/%m/%Y %H:%M})",
            "",
            "Personas fictícias de exemplos/. Sem reserva; só o texto da LLM é avaliado.",
            "",
            *resumo(resultados),
            "",
            *tabela,
            "",
        ]
    )


def correr(
    personas: list[Path],
    provedores: list[ProvedorLLM],
    pausa_s: float = 0.0,
    dormir: Callable[[float], None] = time.sleep,
) -> list[tuple[str, Avaliacao]]:
    """Gera um plano por persona e fornecedor; uma falha não para os outros."""
    resultados: list[tuple[str, Avaliacao]] = []
    for n, caminho in enumerate(personas):
        if n and pausa_s:
            dormir(pausa_s)  # dá tempo ao limite de tokens por minuto
        nome = caminho.stem.removeprefix("persona_")
        q = Questionario.model_validate(json.loads(caminho.read_text(encoding="utf-8")))
        estrategia = gerar_estrategia(q)
        try:
            avaliacoes = comparar(q, estrategia, provedores)
        except ErroGeracao as erro:
            avaliacoes = [
                Avaliacao(provedor=p.nome, modelo=p.modelo, erro=str(erro)) for p in provedores
            ]
        resultados += [(nome, a) for a in avaliacoes]
    return resultados


def main(argv: list[str] | None = None, config: Configuracao | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/comparar_fornecedores.py",
        description="Gemini vs Groq com as 5 personas fictícias (chama a LLM real).",
    )
    parser.add_argument("--modelo-groq", required=True, help="por exemplo openai/gpt-oss-120b")
    parser.add_argument(
        "--pausa", type=float, default=30.0, help="segundos entre personas (por omissão 30)"
    )
    args = parser.parse_args(argv)
    for fluxo in (sys.stdout, sys.stderr):
        if isinstance(fluxo, io.TextIOWrapper):
            fluxo.reconfigure(encoding="utf-8")

    config = obter_configuracao() if config is None else config
    try:
        provedores = [
            criar_fornecedor("gemini", config),
            criar_fornecedor("groq", config, args.modelo_groq),
        ]
    except ErroLLM as erro:
        print(f"Falta configuração: {erro}")
        return 1
    quando = datetime.now()
    texto = markdown(correr(list(PERSONAS), provedores, args.pausa), quando)
    PASTA_SAIDAS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_SAIDAS / f"fornecedores_{quando:%Y%m%d_%H%M}.md"
    destino.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"Guardado em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
