"""Linha de comando do motor: gera a estratégia (ou, a partir da Fase 4, o plano) sem interface.

Uso: python -m vigoria.motor.cli --so-estrategia exemplos/persona_teste.json
Só --so-estrategia corre sem LLM. A geração completa chama o Gemini e só o José a executa.
"""

import argparse
import io
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
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
    parser.add_argument("questionario", type=Path, help="ficheiro JSON com o questionário")
    parser.add_argument(
        "--so-estrategia", action="store_true", help="só a estratégia, sem chamar a LLM"
    )
    args = parser.parse_args(argv)

    if not args.so_estrategia:
        print("A geração completa do plano só chega na Fase 4. Use --so-estrategia.")
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

    # Fora de uma consola interativa, o Windows usaria cp1252 e estragaria os acentos.
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    print(formatar_estrategia(gerar_estrategia(q), args.questionario.name))
    return 0


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
    linhas += [
        "",
        "RESTRIÇÕES DE EXERCÍCIO",
        f"  Sem impacto: {_sim_nao(r.sem_impacto)}",
        f"  Sem intervalos: {_sim_nao(r.sem_intervalos)}",
        f"  Sem flexão do tronco com carga: {_sim_nao(r.sem_flexao_tronco_com_carga)}",
        f"  Equilíbrio com apoio: {_sim_nao(r.equilibrio_com_apoio)}",
        f"  Regressão nas zonas: {zonas}",
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
