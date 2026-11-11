"""O meu progresso: onde a pessoa está, sugestões, registo, gráficos e registos anteriores.

Sem lógica de negócio: as regras estão em vigoria.regras.progresso e os dados em
vigoria.dados.repositorios, sempre filtrados pelo utilizador. As observações são da pessoa:
mostram-se como texto simples, sem interpretação.
"""

from collections.abc import Sequence

import streamlit as st
from pydantic import ValidationError

from paginas import componentes, comum, graficos, sessao
from paginas import textos as t
from vigoria.conteudo.carregar import carregar_alimentacao
from vigoria.dados import repositorios
from vigoria.dados.repositorios import PlanoDaConta, Preferencias, RegistoDaConta
from vigoria.interface.progresso import contexto_do_plano, medicoes_dos_registos
from vigoria.modelos.questionario import FrequenciaRegisto
from vigoria.modelos.registo import OBSERVACOES_MAX, Comparacao, ValoresRegisto
from vigoria.regras.progresso import (
    Alerta,
    ContextoPlano,
    TipoAlerta,
    avaliar,
    em_manutencao,
    fase_da_semana,
    frequencia_efetiva,
    linha_indicativa,
    periodo,
    periodo_ocupado,
    proximo_marco,
    semana_do_plano,
)
from vigoria.regras.textos import numero

EDITAR = "progresso_editar"  # id do registo a retificar
APAGAR = "progresso_apagar"  # id do registo à espera de confirmação
GERACAO = "progresso_geracao"  # muda ao guardar: o formulário volta a aparecer vazio
ULTIMOS_REGISTOS = 4  # para as médias por baixo dos gráficos
ANCORA_REGISTO = "registar"  # o botão «Registar» do topo salta para o formulário


# ---------------------------------------------------------------- Topo


def _topo(p: PlanoDaConta, semana: int) -> None:
    fase = fase_da_semana(semana)
    with st.container(key="progresso_topo"):  # subtítulo por baixo do título (maqueta)
        if fase is None:
            st.markdown(f"**{t.PROGRESSO_MANUTENCAO.format(s=semana)}**")
            return
        nome = next(f.nome for f in p.plano.treino.fases if f.numero == fase)
        st.markdown(f"**{t.PROGRESSO_SEMANA.format(s=semana, n=fase, nome=nome)}**")
        marco = proximo_marco(semana)
        peso = next((m.peso_indicativo_kg for m in p.plano.marcos if m.semana == marco), None)
        if marco is not None and peso is not None:
            st.write(t.PROGRESSO_MARCO.format(m=marco, kg=numero(peso)))


# ---------------------------------------------------------------- Sugestões


def _evolucao_abranda() -> None:
    e = carregar_alimentacao().evolucao_abranda
    with st.expander(t.ALERTA_ABAIXO_LISTA, expanded=True):
        st.write(" ".join(e.introducao))
        for x in e.verificar:
            # O texto do ponto 1 fala do «Volume 2», que a pessoa não conhece: fica só a pergunta.
            texto = "" if "Volume" in x.texto else f" {x.texto}"
            st.markdown(f"**{x.pergunta}**{texto}")
        st.write(" ".join(e.ajustar.introducao))
        st.markdown("\n".join(f"- {x}" for x in e.ajustar.exemplos))
        st.write(" ".join(e.ajustar.conclusao))


def _ver_manutencao() -> None:
    if st.button(t.ALERTA_VER_VIGIAR, key="ver_vigiar", icon=":material/autorenew:"):
        st.session_state["plano_seccao"] = "manutencao"
        st.switch_page(comum.PAGINA_PLANO)


def _alerta(a: Alerta) -> None:
    match a.tipo:
        case TipoAlerta.PERDA_RAPIDA:
            st.warning(
                t.ALERTA_PERDA_RAPIDA.format(pct=numero(a.pct or 0)), icon=":material/speed:"
            )
        case TipoAlerta.ESFORCO_ACIMA:
            minimo, maximo = a.esforco_faixa or (0, 0)
            st.warning(
                t.ALERTA_ESFORCO.format(e=a.esforco, min=minimo, max=maximo),
                icon=":material/fitness_center:",
            )
        case TipoAlerta.SUBIDA_PESO:
            ref = f"{numero(a.referencia or 0)} kg"
            st.info(t.ALERTA_SUBIDA.format(medida=t.MEDIDA_PESO, ref=ref), icon=":material/info:")
        case TipoAlerta.SUBIDA_CINTURA:
            ref = f"{numero(a.referencia or 0)} cm"
            st.info(
                t.ALERTA_SUBIDA.format(medida=t.MEDIDA_CINTURA, ref=ref), icon=":material/info:"
            )
        case TipoAlerta.EVOLUCAO_ABAIXO:
            st.info(t.ALERTA_ABAIXO, icon=":material/info:")
            _evolucao_abranda()
        case TipoAlerta.PERIODO_EM_FALTA:
            primeira, ultima = a.semanas or (0, 0)
            st.info(
                t.ALERTA_EM_FALTA.format(periodo=t.periodo_de(primeira, ultima)),
                icon=":material/edit_calendar:",
            )


# ---------------------------------------------------------------- Formulário


def _mensagem_invalida(erro: ValidationError) -> str:
    campos = [str(e["loc"][0]) for e in erro.errors() if e["loc"]]
    if not campos:
        return t.REGISTO_VAZIO
    return t.REGISTO_INVALIDO.format(campos=", ".join(t.ROTULOS_REGISTO[c] for c in campos))


def _gravar(
    p: PlanoDaConta,
    registo: RegistoDaConta | None,
    dia: object,
    campos: dict[str, object],
) -> None:
    hoje = comum.hoje()
    uid = sessao.utilizador_id()
    try:
        valores = ValoresRegisto.model_validate(campos)
        with sessao.fabrica().begin() as s:
            if registo is None:
                repositorios.guardar_registo(s, uid, p.id, dia, valores, hoje)  # type: ignore[arg-type]
            else:
                repositorios.atualizar_registo(s, uid, registo.id, dia, valores, hoje)  # type: ignore[arg-type]
    except ValidationError as erro:
        st.error(_mensagem_invalida(erro), icon=":material/error:")
        return
    except repositorios.DataFutura:
        st.error(t.REGISTO_DATA_FUTURA, icon=":material/error:")
        return
    except repositorios.DataAntesDoPlano:
        st.error(t.REGISTO_DATA_ANTES, icon=":material/error:")
        return
    except repositorios.PeriodoOcupado as ocupado:
        with sessao.fabrica().begin() as s:
            frequencia = repositorios.obter_preferencias(s, uid).frequencia
        primeira, ultima = periodo(ocupado.semana, frequencia_efetiva(frequencia, ocupado.semana))
        st.error(
            t.REGISTO_REPETIDO.format(periodo=t.periodo_para(primeira, ultima)),
            icon=":material/error:",
        )
        return
    st.session_state[GERACAO] = st.session_state.get(GERACAO, 0) + 1
    st.session_state.pop(EDITAR, None)
    st.toast(t.REGISTO_GUARDADO, icon=":material/check_circle:")
    st.rerun()


def _comparacao(rotulo: str, chave: str, atual: Comparacao | None) -> Comparacao | None:
    opcoes = list(Comparacao)
    return st.radio(
        rotulo,
        opcoes,
        index=opcoes.index(atual) if atual else None,
        format_func=t.COMPARACAO.__getitem__,
        horizontal=True,
        key=chave,
    )


def _formulario(
    p: PlanoDaConta,
    contexto: ContextoPlano,
    frequencia: FrequenciaRegisto,
    semana: int,
    registo: RegistoDaConta | None = None,
) -> None:
    v = registo.valores if registo else None
    a_cada_4 = frequencia_efetiva(frequencia, semana) is FrequenciaRegisto.A_CADA_4_SEMANAS
    base = f"registo_{registo.id}" if registo else f"novo_{st.session_state.get(GERACAO, 0)}"
    rotulos = t.ROTULOS_REGISTO
    with st.form(base):
        if em_manutencao(semana):
            st.caption(t.REGISTO_NOTA_MANUTENCAO)
        dia = st.date_input(
            rotulos["data"],
            value=registo.data if registo else comum.hoje(),
            min_value=contexto.inicio,
            max_value=comum.hoje(),
            format="DD/MM/YYYY",
            key=f"{base}_data",
        )
        peso = st.number_input(
            rotulos["peso_kg"],
            min_value=35.0,
            max_value=250.0,
            value=v.peso_kg if v else None,
            step=0.1,
            format="%.1f",
            key=f"{base}_peso",
        )
        cintura = st.number_input(
            rotulos["cintura_cm"],
            min_value=50.0,
            max_value=200.0,
            value=v.cintura_cm if v else None,
            step=0.5,
            format="%.1f",
            key=f"{base}_cintura",
        )
        sessoes = st.number_input(
            t.REGISTO_SESSOES_4 if a_cada_4 else rotulos["sessoes"],
            min_value=0,
            max_value=14,
            value=v.sessoes if v else None,
            step=1,
            key=f"{base}_sessoes",
        )
        cardio = st.number_input(
            t.REGISTO_CARDIO_4 if a_cada_4 else rotulos["cardio_min"],
            min_value=0,
            max_value=600,
            value=v.cardio_min if v else None,
            step=5,
            key=f"{base}_cardio",
        )
        energia = st.number_input(
            rotulos["energia"],
            min_value=0,
            max_value=10,
            value=v.energia if v else None,
            step=1,
            key=f"{base}_energia",
        )
        esforco = st.number_input(
            rotulos["esforco"],
            min_value=0,
            max_value=10,
            value=v.esforco if v else None,
            step=1,
            key=f"{base}_esforco",
        )
        sono = st.number_input(
            rotulos["sono_h"],
            min_value=3.0,
            max_value=12.0,
            value=v.sono_h if v else None,
            step=0.5,
            format="%.1f",
            key=f"{base}_sono",
        )
        forca = _comparacao(t.REGISTO_FORCA, f"{base}_forca", v.forca if v else None)
        mobilidade = _comparacao(
            t.REGISTO_MOBILIDADE, f"{base}_mobilidade", v.mobilidade_equilibrio if v else None
        )
        if a_cada_4:
            perguntas = carregar_alimentacao().acompanhamento.perguntas_revisao
            st.markdown(f"**{t.PERGUNTAS_REVISAO}**")
            st.markdown("\n".join(f"- {x}" for x in perguntas))
        observacoes = st.text_area(
            rotulos["observacoes"],
            value=(v.observacoes or "") if v else "",
            max_chars=OBSERVACOES_MAX,
            key=f"{base}_observacoes",
        )
        st.caption(t.REGISTO_OBSERVACOES_AJUDA)
        guardar = st.form_submit_button(
            t.REGISTO_GUARDAR, type="primary", icon=":material/save:", width="stretch"
        )
        cancelar = st.form_submit_button(t.REGISTO_CANCELAR, width="stretch") if registo else False
    if cancelar:
        st.session_state.pop(EDITAR, None)
        st.rerun()
    if guardar:
        campos = {
            "peso_kg": peso,
            "cintura_cm": cintura,
            "sessoes": sessoes,
            "cardio_min": cardio,
            "energia": energia,
            "esforco": esforco,
            "sono_h": sono,
            "forca": forca,
            "mobilidade_equilibrio": mobilidade,
            "observacoes": observacoes or None,
        }
        _gravar(p, registo, dia, campos)


# ---------------------------------------------------------------- Gráficos


def _mostrar(figura: object, chave: str, resumo: str) -> None:
    st.plotly_chart(figura, key=chave, theme=None, config=graficos.CONFIG, alt=resumo)
    st.write(resumo)


def _media(valores: list[float]) -> str:
    return numero(sum(valores) / len(valores))


def _medias(sessoes: list[tuple[int, int]], cardio: list[tuple[int, int]], previsto: int) -> None:
    """Cartões das médias dos últimos registos (sessões e cardio), se houver valores."""
    itens = []
    contagens = []
    if sessoes:
        ultimos = [v for _, v in sessoes[-ULTIMOS_REGISTOS:]]
        contagens.append(len(ultimos))
        itens.append((t.MEDIA_SESSOES, _media(ultimos), t.MEDIA_SESSOES_DE.format(d=previsto)))
    if cardio:
        ultimos = [v for _, v in cardio[-ULTIMOS_REGISTOS:]]
        contagens.append(len(ultimos))
        itens.append((t.MEDIA_CARDIO, _media(ultimos), t.UNIDADE_MINUTOS))
    if itens:
        st.html(componentes.medias(itens))
        st.caption(t.medias_de(max(contagens)))


def _grafico_peso(
    p: PlanoDaConta,
    pesos: list[tuple[int, float]],
    manutencao: bool,
    marcos: Sequence[tuple[int, float]],
) -> None:
    st.markdown(f"#### {t.GRAFICO_PESO}")
    semanas, valores = (list(x) for x in zip(*pesos, strict=True))
    ultima, ultimo = pesos[-1]
    linha: list[tuple[int, float]] = []
    if not manutencao and p.peso_kg is not None:
        linha = [(0, p.peso_kg), *marcos]
        semanas, valores = [0, *semanas], [p.peso_kg, *valores]
    if linha and ultima <= graficos.SEMANAS_TOTAL and p.peso_kg is not None:
        resumo = t.RESUMO_PESO.format(
            p=numero(ultimo),
            s=ultima,
            l=numero(linha_indicativa(p.peso_kg, marcos, ultima)),
        )
    else:
        resumo = t.RESUMO_PESO_MANUTENCAO.format(p=numero(ultimo), s=ultima)
    _mostrar(graficos.peso(semanas, valores, linha), "grafico_peso", resumo)


def _graficos(p: PlanoDaConta, registos: list[RegistoDaConta], semana: int) -> None:
    st.subheader(t.GRAFICOS_TITULO)
    if not registos:
        st.caption(t.GRAFICOS_SEM_REGISTOS)
        return
    manutencao = em_manutencao(semana)
    contexto = contexto_do_plano(p)
    indicadores = p.estrategia.indicadores
    previsto = sum(1 for d in p.plano.semana_tipo if d.duracao_min)
    pesos = [(r.semana, r.valores.peso_kg) for r in registos if r.valores.peso_kg is not None]
    sessoes = [(r.semana, r.valores.sessoes) for r in registos if r.valores.sessoes is not None]
    cardio = [
        (r.semana, r.valores.cardio_min) for r in registos if r.valores.cardio_min is not None
    ]

    # Maqueta Progresso: o peso e as médias lado a lado no computador, empilhados no telemóvel.
    if pesos:
        coluna_peso, coluna_medias = st.columns([3, 2], gap="medium")
        with coluna_peso:
            _grafico_peso(p, pesos, manutencao, contexto.marcos)
        with coluna_medias:
            _medias(sessoes, cardio, previsto)
    else:
        _medias(sessoes, cardio, previsto)

    cinturas = [
        (r.semana, r.valores.cintura_cm) for r in registos if r.valores.cintura_cm is not None
    ]
    if cinturas:
        st.markdown(f"#### {t.GRAFICO_CINTURA}")
        semanas, valores = (list(x) for x in zip(*cinturas, strict=True))
        ultima, ultimo = cinturas[-1]
        inicial = indicadores.cintura_cm if indicadores else None
        limiar = (
            indicadores.limiar_cintura_cm if indicadores and indicadores.cintura_de_risco else None
        )
        if inicial is not None:
            semanas, valores = [0, *semanas], [inicial, *valores]
        resumo = t.RESUMO_CINTURA.format(
            c=numero(ultimo), s=ultima, c0=numero(inicial if inicial is not None else ultimo)
        )
        if limiar is not None:
            resumo += " " + t.RESUMO_CINTURA_LIMIAR.format(limiar=limiar)
        _mostrar(graficos.cintura(semanas, valores, limiar), "grafico_cintura", resumo)

    if sessoes:
        st.markdown(f"#### {t.GRAFICO_SESSOES}")
        ultimos = [v for _, v in sessoes[-ULTIMOS_REGISTOS:]]
        resumo = t.RESUMO_SESSOES.format(
            registos=t.ultimos_registos(len(ultimos)), x=_media(ultimos), d=previsto
        )
        semanas, valores = (list(x) for x in zip(*sessoes, strict=True))
        figura = graficos.barras(semanas, valores, t.UNIDADE_SESSOES, previsto)
        _mostrar(figura, "grafico_sessoes", resumo)

    if cardio:
        st.markdown(f"#### {t.GRAFICO_CARDIO}")
        ultimos = [v for _, v in cardio[-ULTIMOS_REGISTOS:]]
        resumo = t.RESUMO_CARDIO.format(
            registos=t.ultimos_registos(len(ultimos)), m=_media(ultimos)
        )
        semanas, valores = (list(x) for x in zip(*cardio, strict=True))
        _mostrar(graficos.barras(semanas, valores, t.UNIDADE_MINUTOS), "grafico_cardio", resumo)


# ---------------------------------------------------------------- Registos anteriores


def _pedir_apagar(registo_id: int | None) -> None:
    st.session_state[APAGAR] = registo_id


def _editar(registo_id: int) -> None:
    st.session_state[EDITAR] = registo_id
    st.session_state.pop(APAGAR, None)


def _apagar(registo_id: int) -> None:
    with sessao.fabrica().begin() as s:
        repositorios.apagar_registo(s, sessao.utilizador_id(), registo_id)
    st.session_state.pop(APAGAR, None)
    st.toast(t.REGISTO_APAGADO, icon=":material/delete:")


def _detalhes(v: ValoresRegisto) -> str:
    partes = []
    if v.peso_kg is not None:
        partes.append(f"{t.ROTULOS_REGISTO['peso_kg']}: {numero(v.peso_kg)}")
    if v.cintura_cm is not None:
        partes.append(f"{t.ROTULOS_REGISTO['cintura_cm']}: {numero(v.cintura_cm)}")
    for campo in ("sessoes", "cardio_min", "energia", "esforco"):
        valor = getattr(v, campo)
        if valor is not None:
            partes.append(f"{t.ROTULOS_REGISTO[campo]}: {valor}")
    if v.sono_h is not None:
        partes.append(f"{t.ROTULOS_REGISTO['sono_h']}: {numero(v.sono_h)}")
    if v.forca is not None:
        partes.append(f"{t.ROTULOS_REGISTO['forca']}: {t.COMPARACAO[v.forca].lower()}")
    if v.mobilidade_equilibrio is not None:
        rotulo = t.ROTULOS_REGISTO["mobilidade_equilibrio"]
        partes.append(f"{rotulo}: {t.COMPARACAO[v.mobilidade_equilibrio].lower()}")
    return " · ".join(partes)


def _registos_anteriores(
    p: PlanoDaConta,
    contexto: ContextoPlano,
    frequencia: FrequenciaRegisto,
    registos: list[RegistoDaConta],
) -> None:
    st.subheader(t.REGISTOS_TITULO)
    if not registos:
        st.caption(t.REGISTOS_VAZIO)
    por_confirmar = st.session_state.get(APAGAR)
    a_editar = st.session_state.get(EDITAR)
    for r in reversed(registos):
        with st.container(border=True, key=f"registo_cartao_{r.id}"):
            st.markdown(
                f"**{t.REGISTO_SEMANA.format(s=r.semana)}** · {r.data.strftime('%d/%m/%Y')}"
            )
            detalhes = _detalhes(r.valores)
            if detalhes:
                st.write(detalhes)
            if r.valores.observacoes:
                st.text(r.valores.observacoes)
            if r.id == a_editar:
                _formulario(p, contexto, frequencia, r.semana, r)
                continue
            with st.container(horizontal=True):
                st.button(
                    t.REGISTO_EDITAR,
                    key=f"editar_{r.id}",
                    icon=":material/edit:",
                    on_click=_editar,
                    args=(r.id,),
                )
                st.button(
                    t.REGISTO_APAGAR,
                    key=f"apagar_{r.id}",
                    icon=":material/delete:",
                    on_click=_pedir_apagar,
                    args=(r.id,),
                )
            if r.id == por_confirmar:
                st.write(t.REGISTO_APAGAR_PERGUNTA.format(s=r.semana))
                with st.container(horizontal=True):
                    st.button(
                        t.REGISTO_APAGAR_SIM,
                        key=f"apagar_sim_{r.id}",
                        type="primary",
                        icon=":material/delete_forever:",
                        on_click=_apagar,
                        args=(r.id,),
                    )
                    st.button(
                        t.REGISTO_APAGAR_NAO,
                        key=f"apagar_nao_{r.id}",
                        on_click=_pedir_apagar,
                        args=(None,),
                    )


# ---------------------------------------------------------------- Página


st.title(t.PROGRESSO_TITULO)
resultado = st.session_state.get(comum.RESULTADO)
if resultado is None or not resultado.id:  # id 0: o plano não ficou guardado na conta
    st.info(t.PROGRESSO_SEM_PLANO, icon=":material/info:")
    st.page_link(comum.PAGINA_QUESTIONARIO, label=t.COMECAR, icon=":material/arrow_forward:")
    comum.parar()

uid = sessao.utilizador_id()
with sessao.fabrica().begin() as s:
    preferencias: Preferencias = repositorios.obter_preferencias(s, uid)
    registos = repositorios.listar_registos(s, uid, resultado.id)

hoje = comum.hoje()
contexto = contexto_do_plano(resultado)
semana = semana_do_plano(contexto.inicio, hoje)
st.caption(t.CONTA_PLANO_DE.format(data=t.data_hora(resultado.criado_em)))
_topo(resultado, semana)
semanas_registadas = [r.semana for r in registos]
ocupado = periodo_ocupado(semana, preferencias.frequencia, semanas_registadas)
if preferencias.ativo and not ocupado:
    # Maqueta Progresso: o registo em falta logo no topo, com ligação ao formulário.
    primeira, ultima = periodo(semana, frequencia_efetiva(preferencias.frequencia, semana))
    st.html(
        componentes.registo_por_fazer(
            t.POR_FAZER_TITULO.format(periodo=t.periodo_de(primeira, ultima)),
            t.POR_FAZER_TEXTO,
            t.POR_FAZER_BOTAO,
            ANCORA_REGISTO,
        )
    )
comum.ligacao_ajuda("registo")

if preferencias.ativo:
    alertas = avaliar(contexto, medicoes_dos_registos(registos), preferencias.frequencia, hoje)
    for alerta in alertas:
        _alerta(alerta)
    if any(a.tipo in (TipoAlerta.SUBIDA_PESO, TipoAlerta.SUBIDA_CINTURA) for a in alertas):
        _ver_manutencao()  # um só botão, mesmo com os dois avisos
    st.subheader(t.REGISTAR_TITULO, anchor=ANCORA_REGISTO)
    if ocupado:
        primeira, ultima = periodo(semana, frequencia_efetiva(preferencias.frequencia, semana))
        st.caption(t.REGISTAR_FEITO.format(periodo=t.periodo_para(primeira, ultima)))
        with st.expander(t.REGISTAR_OUTRO):
            _formulario(resultado, contexto, preferencias.frequencia, semana)
    else:
        _formulario(resultado, contexto, preferencias.frequencia, semana)
else:
    st.info(t.PROGRESSO_DESLIGADO, icon=":material/toggle_off:")
    st.page_link(comum.PAGINA_CONTA, label=t.PAGINAS["conta"], icon=":material/person:")

_graficos(resultado, registos, semana)
_registos_anteriores(resultado, contexto, preferencias.frequencia, registos)
