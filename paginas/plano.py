"""O plano gerado, em separadores. Os avisos de segurança ficam no fim de cada um.

Os rótulos vêm de avisos.yaml (`rotulos`), como no Markdown da CLI; o plano vem de
st.session_state (ainda sem contas, Fase 5).
"""

import streamlit as st

from paginas import comum
from paginas import textos as t
from vigoria.conteudo.carregar import carregar_avisos, carregar_exercicios
from vigoria.modelos.plano import ExercicioPlano, Plano, TreinoFase
from vigoria.regras.textos import numero

rotulos = carregar_avisos().rotulos
r = rotulos.plano


def _intervalo(minimo: int, maximo: int, unidade: str) -> str:
    return f"{minimo} {unidade}" if minimo == maximo else f"{minimo} a {maximo} {unidade}"


def _exercicio(x: ExercicioPlano) -> None:
    with st.container(border=True):
        st.markdown(f"**{x.nome}**")
        prescricao = []
        if x.series:
            prescricao.append(f"{x.series} {r['series'].lower()}")
        if x.repeticoes:
            prescricao.append(f"{x.repeticoes} {r['repeticoes'].lower()}")
        if x.descanso_s:
            prescricao.append(f"{r['descanso'].lower()} {_intervalo(*x.descanso_s, 's')}")
        if prescricao:
            st.markdown(" · ".join(prescricao))
        st.write(x.descricao)
        if x.em_vez_de:
            nome = carregar_exercicios()[x.em_vez_de].nome
            st.markdown(f":material/swap_horiz: {r['em_vez_de'].format(nome=nome)}")
        for nota in x.notas:
            st.caption(nota)


def _resumo(plano: Plano) -> None:
    st.write(plano.resumo)
    st.subheader(r["marcos"])
    for m in plano.marcos:
        with st.container(border=True):
            st.markdown(f"**{r['semana']} {m.semana}** — {m.fase}")
            st.markdown(
                f"- {r['peso_indicativo']}: {numero(m.peso_indicativo_kg)} kg\n"
                f"- {r['cintura']}: {m.cintura}\n"
                f"- {r['forca_resistencia']}: {m.forca_resistencia}"
            )
    if plano.notas_personalizadas:
        st.subheader(r["notas"])
        st.markdown("\n".join(f"- {n}" for n in plano.notas_personalizadas))


def _semana(plano: Plano) -> None:
    st.subheader(r["semana_tipo"])
    # Tabela em Markdown, não st.table: o st.table precisa do pyarrow, cujas DLL o Smart App
    # Control do Windows bloqueia (31/10/2026). Três colunas estreitas, legíveis a 390 px.
    linhas = [
        f"| {r['dia']} | {r['atividade']} | {t.MINUTOS_COLUNA} |",
        "|---|---|---|",
        *(
            f"| {rotulos.dias[s.dia]} | {s.atividade if s.duracao_min else t.SEM_SESSAO} "
            f"| {s.duracao_min or t.SEM_RESPOSTA} |"
            for s in plano.semana_tipo
        ),
    ]
    st.markdown("\n".join(linhas))
    with st.expander(t.DETALHES_SEMANA):
        st.markdown(
            "\n".join(f"- **{rotulos.dias[s.dia]}:** {s.descricao}" for s in plano.semana_tipo)
        )


def _fase(fase: TreinoFase) -> None:
    st.markdown(f"**{r['foco']}:** {fase.foco}")
    st.caption(r["esforco"].format(min=fase.esforco[0], max=fase.esforco[1]))
    st.markdown(f"#### {r['forca_titulo']}")
    for x in fase.forca:
        _exercicio(x)
    if fase.cardio_finalizador is not None:
        duracao = r["cardio_duracao"].format(
            min=fase.cardio_duracao_min[0], max=fase.cardio_duracao_min[1]
        )
        st.markdown(f"#### {r['cardio_finalizador']} ({duracao})")
        _exercicio(fase.cardio_finalizador)
    if fase.mobilidade_equilibrio:
        st.markdown(f"#### {r['mobilidade_equilibrio']}")
        for x in fase.mobilidade_equilibrio:
            _exercicio(x)


def _treino(plano: Plano) -> None:
    _semana(plano)
    st.subheader(r["estrutura_sessao"])
    sessao = plano.treino.estrutura_sessao
    st.markdown(
        "\n".join(
            f"- **{r[parte]}:** {getattr(sessao, parte)}"
            for parte in ("aquecimento", "bloco_principal", "cardio_finalizador", "retorno_calma")
        )
    )
    fases = {f.numero: f for f in plano.treino.fases}
    st.subheader(r["treino"])
    escolhida = st.segmented_control(
        t.ESCOLHER_FASE,
        list(fases),
        default=min(fases),
        required=True,
        format_func=lambda n: f"{r['fase']} {n}: {fases[n].nome}",
        key="plano_fase",
    )
    _fase(fases[escolhida or min(fases)])


def _alimentacao(plano: Plano) -> None:
    a = plano.alimentacao
    st.subheader(r["ajustes_refeicoes"])
    st.markdown(
        "\n".join(
            f"- **{rotulos.refeicoes[x.refeicao]}:** {x.sugestao}" for x in a.ajustes_refeicoes
        )
    )
    st.subheader(r["bebidas_e_alcool"])
    st.write(a.bebidas_e_alcool)
    st.subheader(r["prioridades_por_fase"])
    st.markdown(
        "\n".join(
            f"{i}. **{r['fase']} {i}:** {p}" for i, p in enumerate(a.prioridades_por_fase, start=1)
        )
    )
    p = plano.proteina
    st.subheader(r["proteina"])
    if p.minimo_g is not None:
        st.write(
            r["proteina_valores"].format(
                minimo=p.minimo_g,
                maximo=p.maximo_g,
                por_refeicao_min=p.por_refeicao_min_g,
                por_refeicao_max=p.por_refeicao_max_g,
            )
        )
    if p.nota:
        st.caption(p.nota)
    h = plano.hidratacao
    st.subheader(r["hidratacao"])
    if h.valores.central_ml is not None:
        st.write(
            r["hidratacao_valores"].format(
                minimo=h.valores.minimo_ml, maximo=h.valores.maximo_ml, central=h.valores.central_ml
            )
        )
    if h.valores.nota:
        st.caption(h.valores.nota)
    if h.dicas:
        st.markdown("\n".join(f"- {d}" for d in h.dicas))


def _habitos(plano: Plano) -> None:
    for x in plano.habitos:
        with st.container(border=True):
            st.markdown(f"**{x.titulo}**")
            st.write(x.descricao)


def _acompanhamento(plano: Plano) -> None:
    a = plano.acompanhamento
    st.subheader(r["indicadores"])
    st.caption(t.FREQUENCIA_PLANO.get(a.frequencia, a.frequencia))
    st.markdown("\n".join(f"- {x}" for x in a.indicadores))
    if a.perguntas_revisao:
        st.subheader(t.PERGUNTAS_REVISAO)
        st.markdown("\n".join(f"- {x}" for x in a.perguntas_revisao))


# ---------------------------------------------------------------- Página

resultado = st.session_state.get(comum.RESULTADO)
if resultado is None:
    st.title(r["titulo"])
    st.info(t.SEM_PLANO, icon=":material/info:")
    st.page_link(comum.PAGINA_QUESTIONARIO, label=t.COMECAR, icon=":material/arrow_forward:")
    st.stop()

plano: Plano = resultado.plano
if plano.provedor == "simulado":
    st.warning(t.PLANO_SIMULADO_NOTA, title=t.PLANO_SIMULADO, icon=":material/science:")
st.title(r["titulo"])
st.caption(t.NOTA_SESSAO_PLANO)

for separador, desenhar in zip(
    st.tabs(t.SEPARADORES),
    (_resumo, _treino, _alimentacao, _habitos, _acompanhamento),
    strict=True,
):
    with separador:
        desenhar(plano)
        comum.avisos(plano)

st.page_link(comum.PAGINA_QUESTIONARIO, label=t.VOLTAR_QUESTIONARIO, icon=":material/arrow_back:")
st.caption(r["gerado_por"].format(provedor=plano.provedor, versao=plano.versao_prompt))
