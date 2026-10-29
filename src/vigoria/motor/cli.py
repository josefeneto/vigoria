"""Linha de comando do motor: gera a estratégia (ou, a partir da Fase 4, o plano) sem interface.

Uso: python -m vigoria.motor.cli --so-estrategia exemplos/persona_teste.json
     python -m vigoria.motor.cli --so-pedido exemplos/persona_teste.json
     python -m vigoria.motor.cli --testar-ligacao
--so-estrategia e --so-pedido correm sem LLM. --testar-ligacao e a geração completa
chamam a LLM (Gemini, Groq) e só o José os executa.
"""

import argparse
import io
import json
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from vigoria.config import Configuracao, NomeProvedor, obter_configuracao
from vigoria.llm.base import TIMEOUT_TESTE_S, ErroLLM, ProvedorLLM
from vigoria.llm.escolha import criar_fornecedor
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.gerador import ErroGeracao, montar_pedido
from vigoria.regras.calculos import ClasseImc
from vigoria.regras.textos import NOMES_INTENSIDADE, numero

NOMES_CLASSE_IMC = {
    ClasseImc.BAIXO_PESO: "baixo peso",
    ClasseImc.NORMAL: "normal",
    ClasseImc.EXCESSO_PESO: "excesso de peso",
    ClasseImc.OBESIDADE_I: "obesidade grau I",
    ClasseImc.FORA_DA_VERSAO_BASE: "igual ou superior a 35",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m vigoria.motor.cli", description="Gera a estratégia a partir de um JSON."
    )
    parser.add_argument(
        "questionario", type=Path, nargs="?", help="ficheiro JSON com o questionário"
    )
    parser.add_argument(
        "--so-estrategia", action="store_true", help="só a estratégia, sem chamar a LLM"
    )
    parser.add_argument(
        "--so-pedido",
        action="store_true",
        help="mostra o pedido que seria enviado à LLM, sem a chamar",
    )
    parser.add_argument(
        "--testar-ligacao",
        action="store_true",
        help=f"envia «Responde só: ok» ao fornecedor principal e à reserva "
        f"({TIMEOUT_TESTE_S} s no máximo cada)",
    )
    args = parser.parse_args(argv)

    _consola_utf8()
    if args.testar_ligacao:
        return testar_ligacao()
    if args.questionario is None:
        parser.error("indique o ficheiro JSON com o questionário")
    if not (args.so_estrategia or args.so_pedido):
        print(
            "A geração completa do plano só chega com a verificação (Fase 4, parte 2). "
            "Use --so-estrategia ou --so-pedido."
        )
        return 2

    try:
        dados = json.loads(args.questionario.read_text(encoding="utf-8"))
        q = Questionario.model_validate(dados)
    except (OSError, json.JSONDecodeError) as erro:
        print(f"Não foi possível ler o ficheiro: {erro}")
        return 1
    except ValidationError as erro:
        print(f"Questionário inválido:\n{erro}")
        return 1

    estrategia = gerar_estrategia(q)
    if args.so_estrategia:
        print(formatar_estrategia(estrategia, args.questionario.name))
        return 0
    try:
        pedido = montar_pedido(q, estrategia)
    except ErroGeracao as erro:
        print(erro)
        return 1
    print(f"=== PROMPT DE SISTEMA (versão {pedido.versao_prompt}) ===\n")
    print(pedido.sistema)
    print("\n=== PEDIDO (indentado para leitura; segue em JSON compacto) ===\n")
    cabecalho, corpo = pedido.conteudo.split("\n", 1)
    print(cabecalho)
    print(json.dumps(json.loads(corpo), ensure_ascii=False, indent=2))
    print(f"\nTamanho enviado: {len(pedido.sistema) + len(pedido.conteudo)} caracteres")
    return 0


def _consola_utf8() -> None:
    """Fora de uma consola interativa, o Windows usaria cp1252 e estragaria os acentos."""
    for fluxo in (sys.stdout, sys.stderr):
        if isinstance(fluxo, io.TextIOWrapper):
            fluxo.reconfigure(encoding="utf-8")


def testar_ligacao(
    config: Configuracao | None = None,
    criar: Callable[[NomeProvedor, Configuracao], ProvedorLLM] = criar_fornecedor,
) -> int:
    """Testa o fornecedor principal e, se houver, a reserva. Nunca mostra as chaves."""
    config = obter_configuracao() if config is None else config
    fornecedores: list[tuple[str, NomeProvedor]] = [("principal", config.vigoria_provedor_llm)]
    if config.vigoria_provedor_reserva:
        fornecedores.append(("reserva", config.vigoria_provedor_reserva))
    falhas = 0
    for n, (papel, nome) in enumerate(fornecedores):
        print(f"{'\n' if n else ''}== {nome} ({papel}) ==")
        falhas += _testar_fornecedor(nome, config, criar)
    return 1 if falhas else 0


def _testar_fornecedor(
    nome: NomeProvedor,
    config: Configuracao,
    criar: Callable[[NomeProvedor, Configuracao], ProvedorLLM],
) -> int:
    variavel = nome.upper()
    chave = getattr(config, f"{nome}_api_key")
    modelo = getattr(config, f"{nome}_model")
    print(f"Chave ({variavel}_API_KEY): {'definida' if chave else 'em falta'}")
    print(f"Modelo ({variavel}_MODEL): {modelo or 'em falta'}")
    if chave is None or not modelo:
        print("Falta configuração: veja o .env.example.")
        return 1
    try:
        resposta = criar(nome, config).testar_ligacao()
    except ErroLLM as erro:
        print(f"Falhou: {erro}")
        print(f"Diagnóstico: {_diagnostico(erro.codigo, modelo, variavel)}")
        return 1
    print(f"Resposta do modelo: «{resposta.texto[:40]}»")
    for linha in resposta.limites:
        print(f"  {linha}")
    print("Chave, modelo e rede: a funcionar.")
    return 0


def _diagnostico(codigo: int | None, modelo: str, variavel: str) -> str:
    match codigo:
        case None:
            return "rede ou tempo esgotado (a chave e o modelo não chegaram a ser verificados)."
        case 400 | 401 | 403:
            return f"a chave foi recusada; confirme o {variavel}_API_KEY."
        case 404:
            return f"o modelo «{modelo}» não existe ou não está disponível para esta chave."
        case 429:
            return "a chave e o modelo funcionam, mas a quota está esgotada."
        case _:
            return "erro do lado do serviço; tente mais tarde."


def formatar_estrategia(e: Estrategia, origem: str = "") -> str:
    """Estratégia em texto legível (PT-EU), para rever na linha de comando."""
    linhas = [f"ESTRATÉGIA{f' - {origem}' if origem else ''}", ""]
    if not e.pode_gerar_plano:
        linhas.append("Não é possível gerar plano:")
        linhas.extend(f"  - {m}" for m in e.motivos)
        return "\n".join(linhas)

    linhas.append(f"Modo: {'prudente' if e.modo == 'prudente' else 'versão-base'}")
    linhas.extend(f"  - {m}" for m in e.motivos)

    efetiva = NOMES_INTENSIDADE[e.intensidade_efetiva] if e.intensidade_efetiva else "-"
    linhas += [
        "",
        "INTENSIDADE",
        f"  Pedida: {NOMES_INTENSIDADE[e.intensidade_pedida]} | Efetiva: {efetiva}",
    ]
    if e.explicacao_intensidade:
        linhas.append(f"  {e.explicacao_intensidade}")
    if e.sessoes_curtas:
        linhas.append("  Sessões curtas: só o essencial, completadas com caminhada diária.")
    if e.caminhada_diaria_extra:
        linhas.append("  Caminhada diária fora das sessões (menos de 3 dias por semana).")
    fc = "sim" if e.usar_frequencia_cardiaca else "não (esforço percebido 0-10 e teste da fala)"
    linhas.append(f"  Usar frequência cardíaca: {fc}")

    ind = e.indicadores
    if ind is not None:
        linhas += ["", "INDICADORES"]
        linhas.append(f"  IMC: {numero(ind.imc)} ({NOMES_CLASSE_IMC[ind.classe_imc]})")
        risco = "acima" if ind.cintura_de_risco else "dentro"
        linhas.append(
            f"  Cintura: {numero(ind.cintura_cm)} cm ({risco} do limiar de "
            f"{ind.limiar_cintura_cm} cm)"
        )
        linhas.append(
            "  Módulo de gordura visceral: " + ("ativo" if e.modulo_gordura_visceral else "não")
        )
        h = ind.hidratacao
        if h.central_ml is not None:
            linhas.append(
                f"  Hidratação: {h.minimo_ml} a {h.maximo_ml} ml/dia (central {h.central_ml} ml)"
            )
        if h.nota:
            linhas.append(f"  Hidratação (nota): {h.nota}")
        p = ind.proteina
        if p.minimo_g is not None:
            linhas.append(
                f"  Proteína: {p.minimo_g} a {p.maximo_g} g/dia; "
                f"{p.por_refeicao_min_g} a {p.por_refeicao_max_g} g por refeição principal"
            )
        if p.nota:
            linhas.append(f"  Proteína (nota): {p.nota}")
        pp = ind.perda_peso
        linhas.append(
            f"  Peso-alvo usado: {numero(ind.peso_alvo_usado_kg)} kg | perda pedida "
            f"{numero(pp.perda_pedida_kg)} kg | ritmo necessário "
            f"{numero(pp.ritmo_necessario_kg_semana, 2)} kg/semana | máximo "
            f"{numero(pp.ritmo_maximo_kg_semana, 2)} kg/semana"
        )
        if pp.perda_pedida_kg > 0:
            realista = "sim" if pp.realista else "não"
            linhas.append(
                f"  Realista em 16 semanas: {realista} | alvo à semana 16: "
                f"{numero(pp.alvo_semana_16_kg)} kg | objetivo completo por volta da "
                f"semana {pp.semana_objetivo}"
            )
        g = ind.ganho_muscular
        pedido = "aumentar força e tónus" if g.pedido_kg is None else f"{numero(g.pedido_kg)} kg"
        linhas.append(f"  Massa muscular: {pedido} (máximo {numero(g.maximo_kg)} kg em 16 semanas)")

    r = e.restricoes
    zonas = ", ".join(r.zonas_regressao) or "nenhuma"
    zonas_ligeira = ", ".join(r.zonas_regressao_ligeira) or "nenhuma"
    linhas += [
        "",
        "RESTRIÇÕES DE EXERCÍCIO",
        f"  Sem impacto: {_sim_nao(r.sem_impacto)}",
        f"  Sem intervalos: {_sim_nao(r.sem_intervalos)}",
        f"  Sem flexão do tronco com carga: {_sim_nao(r.sem_flexao_tronco_com_carga)}",
        f"  Equilíbrio com apoio: {_sim_nao(r.equilibrio_com_apoio)}",
        f"  Regressão nas zonas (cadeia completa): {zonas}",
        f"  Regressão ligeira nas zonas (um passo): {zonas_ligeira}",
        f"  Regressão geral: {_sim_nao(r.regressao_geral)}",
        "  Só variantes-base (nível base) da biblioteca.",
        "",
        "MARCOS",
    ]
    for m in e.marcos:
        linhas.append(
            f"  Semana {m.semana:>2} ({m.fase}): peso indicativo {numero(m.peso_indicativo_kg)} kg"
        )
    if e.marcos:
        linhas.append(f"  Cintura: {e.marcos[0].cintura}")
        linhas.append("  Força e resistência: definidos no plano, a partir da biblioteca.")

    linhas += ["", "AVISOS"]
    linhas.extend(f"  {n}. {aviso}" for n, aviso in enumerate(e.avisos, start=1))
    return "\n".join(linhas)


def _sim_nao(valor: bool) -> str:
    return "sim" if valor else "não"


if __name__ == "__main__":
    sys.exit(main())
