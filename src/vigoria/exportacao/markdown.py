"""Plano em Markdown (CLI --plano). Títulos e rótulos em avisos.yaml (`rotulos`).

Os nomes dos exercícios vêm da biblioteca; os números, da Estrategia (já no Plano);
a estrutura da sessão e o esforço percebido de cada fase, de fases.yaml (nunca da LLM).
"""

from vigoria.conteudo.carregar import carregar_avisos, carregar_exercicios, carregar_programa
from vigoria.modelos.plano import Plano
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


def plano_para_markdown(plano: Plano) -> str:
    rotulos = carregar_avisos().rotulos
    r = rotulos.plano
    biblioteca = carregar_exercicios()
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

    programa = carregar_programa()
    sessao = programa.estrutura_sessao
    md += [f"## {r['treino']}", "", f"### {r['estrutura_sessao']}", ""]
    md += [
        f"- **{r[parte]}:** {getattr(sessao, parte)}"
        for parte in ("aquecimento", "bloco_principal", "cardio_finalizador", "retorno_calma")
    ]
    md += [""]
    for n, fase_programa in enumerate(programa.fases, start=1):
        fase = getattr(plano.treino, f"fase_{n}")
        esforco = r["esforco"].format(min=fase_programa.esforco.min, max=fase_programa.esforco.max)
        md += [f"### {r['fase']} {n}: {fase_programa.nome}", ""]
        md += [f"**{r['foco']}:** {fase.foco}", "", esforco, ""]
        md += _tabela(
            [r["exercicio"], r["series"], r["repeticoes"], r["descanso"], r["adaptacao"]],
            [
                [
                    biblioteca[x.exercicio_id].nome
                    if x.exercicio_id in biblioteca
                    else x.exercicio_id,
                    str(x.series),
                    x.repeticoes,
                    x.descanso,
                    x.adaptacao or "-",
                ]
                for x in fase.exercicios
            ],
        )
        md += [f"**{r['progressao']}:** {fase.progressao}", ""]

    a = plano.alimentacao
    md += [f"## {r['alimentacao']}", "", a.resumo, "", f"### {r['ajustes_refeicoes']}", ""]
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
    md += [f"- {x}" for x in plano.indicadores_acompanhamento] + [""]
    md += [f"## {r['notas']}", ""]
    md += [f"- {x}" for x in plano.notas_personalizadas] + [""]
    md += [f"## {r['avisos']}", ""]
    md += [f"> {x}\n" for x in plano.avisos]
    md += ["---", "", r["gerado_por"].format(provedor=plano.provedor, versao=plano.versao_prompt)]
    return "\n".join(md) + "\n"
