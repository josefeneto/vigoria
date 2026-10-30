"""Plano em Markdown (CLI --plano). Títulos e rótulos em avisos.yaml (`rotulos`).

O treino, a semana-tipo, a estrutura da sessão e o esforço de cada fase vêm do motor e
de fases.yaml; os números, da Estrategia; os hábitos, a hidratação e o acompanhamento,
de alimentacao.yaml. Só o resumo, os marcos de força, a alimentação e as notas vêm da LLM.
"""

from vigoria.conteudo.carregar import carregar_avisos, carregar_exercicios
from vigoria.modelos.plano import ExercicioPlano, Plano
from vigoria.regras.textos import numero


def _celula(texto: str) -> str:
    return texto.replace("|", "/").replace("\n", " ")


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(cabecalho) + " |",
        "|" + "---|" * len(cabecalho),
        *("| " + " | ".join(_celula(c) for c in linha) + " |" for linha in linhas),
        "",
    ]


def _intervalo(minimo: int, maximo: int, unidade: str) -> str:
    return f"{minimo} {unidade}" if minimo == maximo else f"{minimo}-{maximo} {unidade}"


def _notas(x: ExercicioPlano) -> str:
    rotulos = carregar_avisos().rotulos.plano
    partes = [x.descricao]
    if x.em_vez_de:
        partes.append(rotulos["em_vez_de"].format(nome=carregar_exercicios()[x.em_vez_de].nome))
    partes.extend(x.notas)
    return " ".join(partes)


def plano_para_markdown(plano: Plano) -> str:
    rotulos = carregar_avisos().rotulos
    r = rotulos.plano
    md = [f"# {r['titulo']}", "", f"## {r['resumo']}", "", plano.resumo, ""]

    md += [f"## {r['marcos']}", ""]
    md += _tabela(
        [r["semana"], r["fase"], r["peso_indicativo"], r["cintura"], r["forca_resistencia"]],
        [
            [
                str(m.semana),
                m.fase,
                f"{numero(m.peso_indicativo_kg)} kg",
                m.cintura,
                m.forca_resistencia,
            ]
            for m in plano.marcos
        ],
    )

    md += [f"## {r['semana_tipo']}", ""]
    md += _tabela(
        [r["dia"], r["atividade"], r["duracao"], r["descricao"]],
        [
            [
                rotulos.dias[s.dia],
                s.atividade,
                f"{s.duracao_min} min" if s.duracao_min else "-",
                s.descricao,
            ]
            for s in plano.semana_tipo
        ],
    )

    sessao = plano.treino.estrutura_sessao
    md += [f"## {r['treino']}", "", f"### {r['estrutura_sessao']}", ""]
    md += [
        f"- **{r[parte]}:** {getattr(sessao, parte)}"
        for parte in ("aquecimento", "bloco_principal", "cardio_finalizador", "retorno_calma")
    ]
    md += [""]
    for fase in plano.treino.fases:
        esforco = r["esforco"].format(min=fase.esforco[0], max=fase.esforco[1])
        md += [f"### {r['fase']} {fase.numero}: {fase.nome}", ""]
        md += [f"**{r['foco']}:** {fase.foco}", "", esforco, ""]
        md += [f"#### {r['forca_titulo']}", ""]
        md += _tabela(
            [r["exercicio"], r["series"], r["repeticoes"], r["descanso"], r["descricao"]],
            [
                [
                    x.nome,
                    str(x.series or "-"),
                    x.repeticoes or "-",
                    _intervalo(*x.descanso_s, "s") if x.descanso_s else "-",
                    _notas(x),
                ]
                for x in fase.forca
            ],
        )
        if fase.cardio_finalizador is not None:
            c = fase.cardio_finalizador
            duracao = r["cardio_duracao"].format(
                min=fase.cardio_duracao_min[0], max=fase.cardio_duracao_min[1]
            )
            md += [
                f"#### {r['cardio_finalizador']}",
                "",
                f"**{c.nome}** ({duracao}): {_notas(c)}",
                "",
            ]
        if fase.mobilidade_equilibrio:
            md += [f"#### {r['mobilidade_equilibrio']}", ""]
            md += [f"- **{x.nome}:** {_notas(x)}" for x in fase.mobilidade_equilibrio] + [""]

    a = plano.alimentacao
    md += [f"## {r['alimentacao']}", "", f"### {r['ajustes_refeicoes']}", ""]
    md += [f"- **{rotulos.refeicoes[x.refeicao]}:** {x.sugestao}" for x in a.ajustes_refeicoes]
    md += ["", f"### {r['bebidas_e_alcool']}", "", a.bebidas_e_alcool, ""]
    md += [f"### {r['prioridades_por_fase']}", ""]
    md += [f"{i}. {p}" for i, p in enumerate(a.prioridades_por_fase, start=1)]
    md += [""]

    p = plano.proteina
    md += [f"## {r['proteina']}", ""]
    if p.minimo_g is not None:
        md += [
            r["proteina_valores"].format(
                minimo=p.minimo_g,
                maximo=p.maximo_g,
                por_refeicao_min=p.por_refeicao_min_g,
                por_refeicao_max=p.por_refeicao_max_g,
            ),
            "",
        ]
    if p.nota:
        md += [p.nota, ""]

    h = plano.hidratacao
    md += [f"## {r['hidratacao']}", ""]
    if h.valores.central_ml is not None:
        md += [
            r["hidratacao_valores"].format(
                minimo=h.valores.minimo_ml, maximo=h.valores.maximo_ml, central=h.valores.central_ml
            ),
            "",
        ]
    if h.valores.nota:
        md += [h.valores.nota, ""]
    md += [f"- {d}" for d in h.dicas] + [""]

    md += [f"## {r['habitos']}", ""]
    md += [f"- **{x.titulo}:** {x.descricao}" for x in plano.habitos] + [""]
    md += [f"## {r['indicadores']}", ""]
    md += [f"- {x}" for x in plano.acompanhamento.indicadores] + [""]
    md += [f"- {x}" for x in plano.acompanhamento.perguntas_revisao]
    if plano.acompanhamento.perguntas_revisao:
        md += [""]
    md += [f"## {r['notas']}", ""]
    md += [f"- {x}" for x in plano.notas_personalizadas] + [""]
    md += [f"## {r['avisos']}", ""]
    md += [f"> {x}\n" for x in plano.avisos]
    md += ["---", "", r["gerado_por"].format(provedor=plano.provedor, versao=plano.versao_prompt)]
    return "\n".join(md) + "\n"
