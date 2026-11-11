"""O plano gerado: cartão de topo com os números-chave e secções em cartões.

As secções escolhem-se com botões grandes, com ícone, que passam para outra linha no
telemóvel (os separadores cortavam «Acompanhamento» a 390 px); só a secção aberta é
desenhada. Os avisos de segurança ficam no fim de cada secção. Sem tabelas: a 390 px, a
semana-tipo e os exercícios leem-se melhor em lista e em cartões.

Os rótulos vêm de avisos.yaml (`rotulos`), como no Markdown da CLI; o plano vem de
st.session_state (o acabado de gerar, ou o último guardado na conta: comum.carregar_da_conta).
"""

import streamlit as st

from paginas import componentes, comum
from paginas import textos as t
from vigoria.conteudo.carregar import carregar_avisos, carregar_exercicios, carregar_fases
from vigoria.modelos.plano import ExercicioPlano, ParteOrientacao, Plano, TreinoFase
from vigoria.motor.manutencao import orientacoes_manutencao
from vigoria.regras.calculos import SEMANAS_PROGRAMA
from vigoria.regras.hoje import Hoje, TipoHoje, sessao_de_hoje
from vigoria.regras.progresso import (
    fase_da_semana,
    inicio_do_plano,
    proximo_marco,
    semana_do_plano,
)
from vigoria.regras.textos import numero

rotulos = carregar_avisos().rotulos
r = rotulos.plano


def _intervalo(minimo: int, maximo: int, unidade: str) -> str:
    return f"{minimo} {unidade}" if minimo == maximo else f"{minimo} a {maximo} {unidade}"


def _exercicio(x: ExercicioPlano) -> None:
    prescricao = []
    if x.series:
        prescricao.append(f"{x.series} {r['series'].lower()}")
    if x.repeticoes:
        prescricao.append(f"{x.repeticoes} {r['repeticoes'].lower()}")
    if x.descanso_s:
        prescricao.append(f"{r['descanso'].lower()} {_intervalo(*x.descanso_s, 's')}")
    extras = list(x.notas)
    if x.em_vez_de:
        extras.insert(0, "⇄ " + r["em_vez_de"].format(nome=carregar_exercicios()[x.em_vez_de].nome))
    icone = carregar_exercicios()[x.id].icone
    st.html(componentes.exercicio(icone, x.nome, prescricao, x.descricao, extras))


def _minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:]


def _convite_novo_plano() -> None:
    """Na semana 16 ou depois: responder de novo, sem obrigar (R15)."""
    criado_em = st.session_state[comum.RESULTADO].criado_em
    if semana_do_plano(inicio_do_plano(criado_em), comum.hoje()) >= SEMANAS_PROGRAMA:
        st.info(t.CONVITE_NOVO_PLANO, icon=":material/flag:")
        st.page_link(
            comum.PAGINA_QUESTIONARIO, label=t.RECOMECAR_QUESTIONARIO, icon=":material/restart_alt:"
        )


def _resumo(plano: Plano) -> None:
    _convite_novo_plano()
    st.write(plano.resumo)
    st.subheader(t.FASES_TITULO)
    semanas = {f.numero: f.semanas for f in carregar_fases()}
    marcos = {m.semana: m for m in plano.marcos}
    # A cintura não tem número por fase (REGRAS §5): o texto é igual nos 4 marcos e
    # mostra-se uma só vez, por baixo do título, em vez de repetido em cada cartão.
    cinturas = {m.cintura for m in plano.marcos}
    cintura_unica = cinturas.pop() if len(cinturas) == 1 else None
    if cintura_unica:
        st.markdown(t.CINTURA_FASES.format(rotulo=r["cintura"], texto=_minuscula(cintura_unica)))
    cartoes = []
    for fase in plano.treino.fases:
        intervalo = semanas[fase.numero]
        detalhes = []
        if (m := marcos.get(intervalo.max)) is not None:
            detalhes = [(r["peso_indicativo"], f"{numero(m.peso_indicativo_kg)} kg")]
            if cintura_unica is None:
                detalhes.append((r["cintura"], m.cintura))
            detalhes.append((r["forca_resistencia"], m.forca_resistencia))
        sobretitulo = t.FASE_SEMANAS.format(n=fase.numero, min=intervalo.min, max=intervalo.max)
        cartoes.append(componentes.cartao_fase(sobretitulo, fase.nome, fase.foco, detalhes))
    st.html(componentes.grelha(cartoes, colunas=2))
    st.caption(t.RESUMO_MANUTENCAO)


def _semana(plano: Plano) -> None:
    st.subheader(r["semana_tipo"])
    st.html(
        componentes.semana(
            (
                componentes.icone_atividade(s.atividade),
                rotulos.dias[s.dia],
                s.atividade,
                t.MINUTOS.format(n=s.duracao_min) if s.duracao_min else t.SEM_RESPOSTA,
            )
            for s in plano.semana_tipo
        )
    )
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
    st.page_link(
        comum.PAGINA_PROGRESSO, label=t.ACOMPANHAMENTO_LIGACAO, icon=":material/monitoring:"
    )


def _parte_manutencao(titulo: str, parte: ParteOrientacao) -> None:
    st.markdown(f"#### {titulo}")
    for p in parte.introducao:
        st.write(p)
    if parte.pontos:
        if parte.titulo_pontos:
            st.markdown(f"**{parte.titulo_pontos}**")
        st.markdown("\n".join(f"- {x}" for x in parte.pontos))
    for n in parte.notas:
        st.write(n)


def _manutencao(plano: Plano) -> None:
    # A idade vem do questionário do plano (a recomendação da OMS só aparece com ≥ 65).
    idade = getattr(st.session_state.get(comum.RESULTADO), "idade", None)
    m = orientacoes_manutencao(plano, idade)
    st.subheader(r["manutencao"])
    st.write(" ".join(m.introducao))
    _parte_manutencao(r["manutencao_treino"], m.treino)
    st.markdown(f"**{r['manutencao_variar']}**")
    for p in m.variar:
        st.write(p)
    st.markdown(f"**{r['manutencao_exercicios']}**")
    st.markdown("\n".join(f"- {x}" for x in m.exercicios_base))
    _parte_manutencao(r["manutencao_alimentacao"], m.alimentacao)
    _parte_manutencao(r["manutencao_vigiar"], m.vigiar)
    _parte_manutencao(r["manutencao_recomecar"], m.recomecar)
    st.page_link(
        comum.PAGINA_QUESTIONARIO, label=t.RECOMECAR_QUESTIONARIO, icon=":material/restart_alt:"
    )


# ---------------------------------------------------------------- Topo (Fase 8D)


def _semanas(plano: Plano, semana: int) -> str:
    """Cartão «Semana X de 16» com a fase e o próximo marco (ou a manutenção)."""
    aria = t.SEMANAS_ARIA.format(s=min(semana, SEMANAS_PROGRAMA))
    fase = fase_da_semana(semana)
    if fase is None:
        texto = t.SEMANA_MANUTENCAO_TEXTO.format(s=semana)
        return componentes.semanas(semana, t.SEMANA_MANUTENCAO, "", texto, aria)
    nome = next(f.nome for f in plano.treino.fases if f.numero == fase)
    marco = proximo_marco(semana)
    peso = next((m.peso_indicativo_kg for m in plano.marcos if m.semana == marco), None)
    texto = t.SEMANA_MARCO.format(m=marco, kg=numero(peso)) if peso is not None else ""
    return componentes.semanas(
        semana, t.SEMANA_DE.format(s=semana), t.SEMANA_FASE.format(n=fase, nome=nome), texto, aria
    )


def _abrir(seccao: str, fase: int | None = None) -> None:
    """Botão do cartão «Hoje»: abre a secção (e a fase) antes de a página se desenhar."""
    st.session_state["plano_seccao"] = seccao
    if fase is not None:
        st.session_state["plano_fase"] = fase


def _hoje(hoje: Hoje, fases: dict[int, TreinoFase]) -> None:
    """Cartão «Hoje»: a entrada da semana-tipo deste dia, o descanso ou a manutenção."""
    sobretitulo = t.HOJE_DIA.format(dia=rotulos.dias[hoje.dia])
    botao: tuple[str, str, int | None] | None = None  # (rótulo, secção, fase)
    if hoje.tipo is TipoHoje.MANUTENCAO:
        cartao = componentes.hoje(
            "rebento", sobretitulo, t.HOJE_MANUTENCAO, t.HOJE_MANUTENCAO_TEXTO
        )
        botao = (t.HOJE_VER_MANUTENCAO, "manutencao", None)
    elif hoje.tipo is TipoHoje.DESCANSO or hoje.sessao is None or hoje.fase is None:
        atividade = hoje.sessao.atividade if hoje.sessao is not None else ""
        # «Caminhada leve (opcional)» ou «Caminhada diária»: fica dita; «Descanso», não.
        detalhe = t.HOJE_DESCANSO_SEM_TREINO
        if atividade and componentes.icone_atividade(atividade) != "descanso":
            detalhe = f"{detalhe} {atividade}."
        cartao = componentes.hoje("descanso", sobretitulo, t.HOJE_DESCANSO, detalhe)
    else:
        a, b = fases[hoje.fase].esforco
        detalhe = t.HOJE_SESSAO.format(min=hoje.sessao.duracao_min, a=a, b=b)
        icone = componentes.icone_atividade(hoje.sessao.atividade)
        cartao = componentes.hoje(icone, sobretitulo, hoje.sessao.atividade, detalhe)
        botao = (t.HOJE_VER, "treino", hoje.fase)
    with st.container(key="plano_hoje", horizontal=True, vertical_alignment="center", gap="small"):
        st.html(cartao, width="stretch")
        if botao is not None:
            rotulo, seccao, fase = botao
            st.button(
                rotulo,
                icon=":material/arrow_forward:",
                type="primary",
                key="plano_hoje_ver",
                on_click=_abrir,
                args=(seccao, fase),
            )


# ---------------------------------------------------------------- Página


resultado = st.session_state.get(comum.RESULTADO)
if resultado is None:
    st.title(r["titulo"])
    st.info(t.SEM_PLANO, icon=":material/info:")
    st.page_link(comum.PAGINA_QUESTIONARIO, label=t.COMECAR, icon=":material/arrow_forward:")
    comum.parar()

plano: Plano = resultado.plano
if plano.provedor == "simulado":
    st.warning(t.PLANO_SIMULADO_NOTA, title=t.PLANO_SIMULADO, icon=":material/science:")
with st.container(key="plano_titulo", horizontal=True, vertical_alignment="center"):
    st.title(r["titulo"], width="stretch")
    comum.botao_pdf(
        resultado.criado_em,
        plano=plano,
        idade=getattr(resultado, "idade", None),
        chave="plano_pdf",
    )
if st.session_state.get(comum.ERRO_GUARDAR):
    st.error(t.ERRO_GUARDAR, icon=":material/cloud_off:")
else:
    st.caption(t.NOTA_SESSAO_PLANO.format(data=t.data_hora(resultado.criado_em)))

inicio_plano = inicio_do_plano(resultado.criado_em)
dia_hoje = comum.hoje()
hoje = sessao_de_hoje(plano.semana_tipo, inicio_plano, dia_hoje)
fases_plano = {f.numero: f for f in plano.treino.fases}
with st.container(key="plano_topo"):
    st.html(_semanas(plano, hoje.semana))
    intensidade = resultado.estrategia.intensidade_efetiva
    dias = sum(1 for s in plano.semana_tipo if s.duracao_min)
    st.html(
        componentes.numeros(
            (
                (
                    t.NUMEROS_PLANO["objetivo"],
                    f"{numero(plano.marcos[-1].peso_indicativo_kg)} kg",
                ),
                (
                    t.NUMEROS_PLANO["intensidade"],
                    t.INTENSIDADE.get(intensidade or "", t.SEM_RESPOSTA),
                ),
                (t.NUMEROS_PLANO["dias"], t.DIAS_VALOR.get(dias, t.DIAS_VALOR_N.format(n=dias))),
            )
        )
    )
    if plano.notas_personalizadas:
        coluna_hoje, coluna_notas = st.columns(2, gap="small")
    else:
        coluna_hoje = coluna_notas = st.container()
    with coluna_hoje:
        _hoje(hoje, fases_plano)
    if plano.notas_personalizadas:
        with coluna_notas:
            st.html(componentes.notas(r["notas"], plano.notas_personalizadas))

SECCOES = {
    "resumo": _resumo,
    "treino": _treino,
    "alimentacao": _alimentacao,
    "habitos": _habitos,
    "acompanhamento": _acompanhamento,
    "manutencao": _manutencao,
}
seccao = st.segmented_control(
    t.SECCAO_PLANO,
    list(SECCOES),
    default="resumo",
    required=True,
    format_func=t.SECCOES_PLANO.__getitem__,
    key="plano_seccao",
    label_visibility="collapsed",
    width="stretch",
    wrap=True,
)
desenhar = SECCOES[seccao or "resumo"]
desenhar(plano)
comum.avisos(plano, chave=desenhar.__name__)

st.page_link(comum.PAGINA_QUESTIONARIO, label=t.VOLTAR_QUESTIONARIO, icon=":material/arrow_back:")
st.caption(r["gerado_por"].format(provedor=plano.provedor, versao=plano.versao_prompt))
