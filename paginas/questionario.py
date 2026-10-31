"""Questionário em passos (docs/dominio/QUESTIONARIO.md): um passo por ecrã.

As respostas ficam nas chaves «q.*» de st.session_state (paginas/comum.py); a validação,
as decisões e a geração vêm de vigoria.interface e vigoria.motor.
"""

import logging
from pathlib import Path
from typing import Any

import streamlit as st

from paginas import comum
from paginas import textos as t
from vigoria.config import obter_configuracao
from vigoria.conteudo.carregar import carregar_avisos
from vigoria.interface.decisoes import avisos_passo_objetivo, decisoes_estrategia, imc_com_classe
from vigoria.interface.erros import classificar_erro
from vigoria.interface.estado import (
    FORCA_TONUS,
    OBJETIVO_KG,
    OBJETIVO_TIPO,
    ZERO_E_VAZIO,
    chave,
    para_estado,
)
from vigoria.interface.passos import (
    CAMPOS,
    PASSOS,
    REFEICOES,
    controladas_aplicaveis,
    limitacoes_com_gravidade,
    montar_questionario,
    respostas_de_questionario,
    tem_gravidez,
    validar_passo,
)
from vigoria.llm.escolha import criar_provedor
from vigoria.modelos.questionario import Questionario
from vigoria.motor.estrategia import gerar_estrategia
from vigoria.motor.pipeline import gerar_plano_verificado
from vigoria.regras import textos as avisos_motor
from vigoria.regras.textos import numero

registo = logging.getLogger(__name__)
PERSONA_TESTE = Path(__file__).resolve().parents[1] / "exemplos" / "persona_teste.json"
A_GERAR = "a_gerar"
ERRO_GERACAO = "erro_geracao"
W = comum.widget
ESPIRITUOSAS_DL = [x / 2 for x in range(11)]  # 0 a 5 dl, de 0,5 em 0,5

comum.iniciar_estado()


# ---------------------------------------------------------------- Navegação (callbacks)


def _ir_para(passo: str) -> None:
    st.session_state[comum.PASSO] = passo
    st.session_state.pop(comum.ERROS, None)


def _seguinte() -> None:
    passo = st.session_state[comum.PASSO]
    r = comum.respostas()
    erros = validar_passo(passo, r)
    if erros:
        st.session_state[comum.ERROS] = {e.campo: t.mensagem_erro(e) for e in erros}
        return
    if passo == "2a" and tem_gravidez(r):
        comum.apagar_respostas()
        st.session_state[comum.TERMINADO_GRAVIDEZ] = True
        return
    _ir_para(PASSOS[PASSOS.index(passo) + 1])


def _anterior() -> None:
    passo = st.session_state[comum.PASSO]
    _ir_para(PASSOS[PASSOS.index(passo) - 1])


def _recomecar() -> None:
    comum.apagar_respostas()
    st.session_state.pop(comum.TERMINADO_GRAVIDEZ, None)


def _preencher_persona() -> None:
    if obter_configuracao().ambiente != "local":
        return
    q = Questionario.model_validate_json(PERSONA_TESTE.read_text("utf-8"))
    for k, v in para_estado(respostas_de_questionario(q)).items():
        st.session_state[k] = v
    _ir_para("7")


def _pedir_geracao() -> None:
    st.session_state[A_GERAR] = True
    st.session_state.pop(ERRO_GERACAO, None)


# ---------------------------------------------------------------- Widgets


def _pills(campo: str, opcoes: dict[str, str]) -> None:
    st.pills(
        t.ROTULOS[campo],
        list(opcoes),
        selection_mode="multi",
        format_func=opcoes.__getitem__,
        **W(campo),
    )
    comum.erro(campo)


def _escolha(
    campo: str, opcoes: dict[str, str], rotulo: str | None = None, **opcional: Any
) -> None:
    rotulo = rotulo or t.ROTULOS[campo]
    st.segmented_control(rotulo, list(opcoes), format_func=opcoes.__getitem__, **opcional)
    comum.erro(opcional.get("key", chave(campo)).removeprefix("q."))


def _radio(campo: str, opcoes: dict[str, str], legendas: dict[str, str] | None = None) -> None:
    st.radio(
        t.ROTULOS[campo],
        list(opcoes),
        index=None,
        format_func=opcoes.__getitem__,
        captions=[legendas[o] for o in opcoes] if legendas else None,
        **W(campo),
    )
    comum.erro(campo)


def _numero(campo: str) -> None:
    """Só números inteiros: não se pede mais rigor a quem responde (a cintura 113 chega).

    Os campos de ZERO_E_VAZIO começam em 0 (estado.py), para as setas +/− funcionarem logo.
    """
    minimo = 0 if campo in ZERO_E_VAZIO else None
    st.number_input(t.ROTULOS[campo], value=None, step=1, min_value=minimo, **W(campo))
    comum.erro(campo)


def _espirituosas() -> None:
    """Lista em vez de caixa de número: assim aparece «0,5» com vírgula, como em Portugal."""
    campo = "espirituosas_dl_dia"
    st.selectbox(
        t.ROTULOS[campo],
        ESPIRITUOSAS_DL,
        index=None,
        format_func=lambda dl: numero(dl) + t.UNIDADES[campo],
        placeholder=t.ESCOLHER,
        **W(campo),
    )
    comum.erro(campo)


def _texto(campo: str, maximo: int = 200) -> None:
    st.text_input(t.ROTULOS[campo], max_chars=maximo, **W(campo))
    comum.erro(campo)


# ---------------------------------------------------------------- Passos


def passo_0() -> None:
    st.write(t.BOAS_VINDAS)
    for campo, rotulo in t.ROTULOS_CONSENTIMENTO.items():
        st.checkbox(rotulo, **W(campo))
        comum.erro(campo)
    st.page_link(comum.PAGINA_PRIVACIDADE, label=t.LER_PRIVACIDADE, icon=":material/policy:")
    st.caption(t.TERMOS_EM_PREPARACAO)


def passo_1() -> None:
    _escolha("sexo", t.SEXO, **W("sexo"))
    _numero("idade")
    _numero("altura_cm")
    _numero("peso_kg")
    _numero("sono_horas")
    _numero("cintura_cm")
    st.caption(t.AJUDA_CINTURA)
    _radio("atividade_atual", t.ATIVIDADE, t.ATIVIDADE_DESCRICAO)


def _imc() -> None:
    r = comum.respostas()
    if r.get("peso_kg") and r.get("altura_cm"):
        imc, classe = imc_com_classe(r["peso_kg"], r["altura_cm"])
        st.info(t.IMC_CONTEXTO[classe], title=t.IMC_TITULO.format(imc=numero(imc)))
        st.caption(t.IMC_NOTA)


def passo_2a() -> None:
    _imc()
    _pills("condicoes", t.CONDICOES)
    r = comum.respostas()
    for c in controladas_aplicaveis(r):
        rotulo = t.CONTROLADA.format(condicao=t.CONDICOES[c])
        _escolha(
            "condicoes_controladas",
            {"sim": t.SIM, "nao": t.NAO},
            rotulo,
            **W("condicoes_controladas", c),
        )
    if "osteoporose" in r["condicoes"]:
        _escolha("osteoporose_risco", t.SIM_NAO_NAO_SEI, **W("osteoporose_risco"))
    if "dor_articular_persistente" in r["condicoes"]:
        _pills("dor_articular_zonas", t.ARTICULACOES)
        if "outra" in (r.get("dor_articular_zonas") or []):
            _texto("dor_articular_outra")
    if "outra" in r["condicoes"]:
        _texto("condicoes_outras")
    _escolha("medicacao_afeta_fc", t.SIM_NAO_NAO_SEI, **W("medicacao_afeta_fc"))
    _texto("medicacao_notas")


def passo_2b() -> None:
    _pills("limitacoes", t.LIMITACOES)
    r = comum.respostas()
    com_gravidade = limitacoes_com_gravidade(r)
    if com_gravidade:
        st.caption(t.GRAVIDADE_AJUDA)
    for x in com_gravidade:
        rotulo = t.GRAVIDADE_PERGUNTA.format(limitacao=t.LIMITACOES[x])
        _escolha("limitacoes_gravidade", t.GRAVIDADE, rotulo, **W("limitacoes_gravidade", x))
    if "outra" in r["limitacoes"]:
        _texto("limitacoes_outra")


def passo_3() -> None:
    _pills("equipamento", t.EQUIPAMENTO)
    if "halteres" in comum.respostas()["equipamento"]:
        _numero("halteres_kg")
    _escolha("dias_semana", {d: str(d) for d in range(1, 8)}, **W("dias_semana"))
    minutos = {m: t.MINUTOS.format(n=m) for m in (15, 20, 30, 45, 60)}
    _escolha("minutos_dia", minutos, **W("minutos_dia"))
    _pills("preferencias", t.PREFERENCIAS)


def passo_4a() -> None:
    st.write(t.REFEICOES_INTRO)
    rotulos = carregar_avisos().rotulos.refeicoes
    for x in REFEICOES:
        with st.container(border=True):
            st.checkbox(f"**{rotulos[x]}** — {t.FACO_REFEICAO.lower()}", **W("refeicoes_faz", x))
            if st.session_state[chave("refeicoes_faz", x)]:
                st.text_input(t.O_QUE_COME, max_chars=150, **W("refeicoes", x))
                comum.erro(f"refeicoes.{x}")
    _pills("restricoes_alimentares", t.RESTRICOES)
    if "outra" in comum.respostas()["restricoes_alimentares"]:
        _texto("restricoes_outra")


def passo_4b() -> None:
    _radio("agua_litros", t.AGUA)
    _radio("bebidas_acucaradas_litros", t.BEBIDAS_ACUCARADAS)
    _numero("vinho_copos_dia")
    _espirituosas()
    _escolha("pao_por_dia", t.PAO, **W("pao_por_dia"))
    _numero("doces_por_semana")


def passo_5() -> None:
    st.info(t.PROGRAMA_16_SEMANAS, icon=":material/calendar_month:")
    _numero("peso_alvo_kg")
    for aviso in avisos_passo_objetivo(comum.respostas()):
        st.warning(aviso, icon=":material/info:")
    _numero("cintura_alvo_cm")
    st.radio(
        t.ROTULOS["objetivo_muscular"],
        list(t.OBJETIVO_MUSCULAR),
        index=None,
        format_func=t.OBJETIVO_MUSCULAR.__getitem__,
        **W(OBJETIVO_TIPO),
    )
    if st.session_state[chave(OBJETIVO_TIPO)] == "kg":
        st.number_input(t.OBJETIVO_MUSCULAR_KG, value=None, step=1, min_value=0, **W(OBJETIVO_KG))
    st.caption(t.NOTA_GANHO_MUSCULAR)
    comum.erro("objetivo_muscular")
    _radio("intensidade_pedida", t.INTENSIDADE, t.INTENSIDADE_DESCRICAO)
    st.caption(t.INTENSIDADE_NOTA)


def passo_6() -> None:
    st.toggle(t.ROTULOS["acompanhamento_ativo"], **W("acompanhamento_ativo"))
    if st.session_state[chave("acompanhamento_ativo")]:
        _escolha("frequencia_registo", t.FREQUENCIA, **W("frequencia_registo"))
        st.toggle(t.ROTULOS["lembretes_email"], **W("lembretes_email"))
    st.caption(t.ACOMPANHAMENTO_NOTA)


# ---------------------------------------------------------------- Passo 7


def _valor(campo: str, valor: Any) -> str:
    opcoes = t.OPCOES.get(campo)
    if isinstance(valor, list):
        return ", ".join(opcoes[v] if opcoes else str(v) for v in valor) or t.SEM_RESPOSTA
    if isinstance(valor, bool):
        return t.SIM if valor else t.NAO
    if isinstance(valor, float | int):
        return numero(valor) + t.UNIDADES.get(campo, "")
    if opcoes and valor in opcoes:
        return opcoes[valor]
    return str(valor) if valor not in (None, "") else t.SEM_RESPOSTA


def _rotulo(campo: str) -> str:
    return t.ROTULOS_RESUMO.get(campo, t.ROTULOS[campo])


def _linhas(q: Questionario, passo: str) -> list[str]:
    dados = q.model_dump(mode="json")
    linhas = []
    for campo in CAMPOS[passo]:
        valor = dados[campo]
        if valor in (None, "", [], {}):
            continue
        if campo == "refeicoes":
            rotulos = carregar_avisos().rotulos.refeicoes
            linhas += [f"**{rotulos[x]}:** {texto}" for x, texto in valor.items() if texto]
        elif campo == "condicoes_controladas":
            linhas += [
                f"**{t.CONTROLADA_RESUMO.format(condicao=t.CONDICOES[c])}:** {_valor(campo, v)}"
                for c, v in valor.items()
            ]
        elif campo == "limitacoes_gravidade":
            linhas += [f"**{t.LIMITACOES[x]}:** {t.GRAVIDADE[g]}" for x, g in valor.items()]
        elif campo == "objetivo_muscular":
            texto = (
                t.OBJETIVO_MUSCULAR[FORCA_TONUS] if valor == FORCA_TONUS else _valor(campo, valor)
            )
            linhas.append(f"**{_rotulo(campo)}:** {texto}")
        else:
            linhas.append(f"**{_rotulo(campo)}:** {_valor(campo, valor)}")
    return linhas


def _revisao(q: Questionario) -> None:
    st.write(t.REVISAO_INTRO)
    for secao, passos in t.RESUMO_SECOES.items():
        with st.container(border=True):
            st.subheader(t.TITULOS_RESUMO[secao])
            st.markdown("\n".join(f"- {linha}" for p in passos for linha in _linhas(q, p)))
            st.button(
                t.ALTERAR,
                key=f"alterar_{secao}",
                icon=":material/edit:",
                on_click=_ir_para,
                args=(secao,),
            )


def _decisoes(q: Questionario) -> bool:
    d = decisoes_estrategia(gerar_estrategia(q), q)
    st.header(t.DECISOES_TITULO)
    st.write(t.DECISOES_INTRO)
    with st.container(border=True):
        linhas = [t.MODO[d.modo]]
        linhas += [f"  - {m}" for m in d.motivos]
        if d.intensidade_efetiva is not None:
            efetiva = t.INTENSIDADE[d.intensidade_efetiva]
            pedida = t.INTENSIDADE[d.intensidade_pedida]
            if d.intensidade_efetiva == d.intensidade_pedida:
                linhas.append(t.INTENSIDADE_IGUAL.format(efetiva=efetiva))
            else:
                linhas.append(t.INTENSIDADE_DECISAO.format(efetiva=efetiva, pedida=pedida))
                if d.explicacao_intensidade:
                    linhas.append(f"  - {d.explicacao_intensidade}")
        if d.semana_objetivo is None:
            linhas.append(t.OBJETIVO_SEM_PERDA)
        elif d.objetivo_realista:
            linhas.append(t.OBJETIVO_REALISTA.format(alvo=numero(d.peso_alvo_kg)))
        else:
            linhas.append(
                t.OBJETIVO_AJUSTADO.format(
                    alvo_16=numero(d.alvo_semana_16_kg or 0),
                    alvo=numero(d.peso_alvo_kg),
                    semana=d.semana_objetivo,
                )
            )
        if d.modulo_gordura_visceral:
            linhas.append(t.MODULO_VISCERAL)
        if not d.usar_frequencia_cardiaca:
            linhas.append(t.ESFORCO_PERCEBIDO)
        if d.sessoes_curtas:
            linhas.append(t.SESSOES_CURTAS)
        if d.caminhada_diaria_extra:
            linhas.append(t.CAMINHADA_EXTRA)
        st.markdown("\n".join(f"- {x}" if not x.startswith("  ") else x for x in linhas))
    if d.avisos_condicionais or d.avisos_obrigatorios:
        with st.expander(t.AVISOS_TITULO, expanded=True, icon=":material/health_and_safety:"):
            st.markdown(
                "\n".join(f"- {a}" for a in (*d.avisos_obrigatorios, *d.avisos_condicionais))
            )
    return d.pode_gerar_plano


def _gerar(q: Questionario) -> None:
    resultado = None
    with st.spinner(t.A_PREPARAR):
        try:
            resultado = gerar_plano_verificado(q, criar_provedor())
        except Exception as e:  # a mensagem ao utilizador nunca tem detalhes técnicos
            registo.warning("geração falhou: %s", type(e).__name__)
            st.session_state[ERRO_GERACAO] = classificar_erro(e)
        finally:
            st.session_state[A_GERAR] = False
    if resultado is not None:
        st.session_state[comum.RESULTADO] = resultado
        st.switch_page(comum.PAGINA_PLANO)
    st.rerun()


def passo_7() -> None:
    q = montar_questionario(comum.respostas())
    if st.session_state.get(A_GERAR):
        _gerar(q)
        return
    if erro_geracao := st.session_state.get(ERRO_GERACAO):
        st.error(t.ERROS_GERACAO[erro_geracao], title=t.ERRO_GERACAO_TITULO)
    _revisao(q)
    if _decisoes(q):
        st.button(
            t.GERAR,
            type="primary",
            icon=":material/auto_awesome:",
            width="stretch",
            on_click=_pedir_geracao,
        )
    else:
        st.error(t.NAO_PODE_GERAR)
    if comum.RESULTADO in st.session_state:
        st.page_link(comum.PAGINA_PLANO, label=t.VER_PLANO, icon=":material/description:")


PASSOS_DESENHO = {
    "0": passo_0,
    "1": passo_1,
    "2a": passo_2a,
    "2b": passo_2b,
    "3": passo_3,
    "4a": passo_4a,
    "4b": passo_4b,
    "5": passo_5,
    "6": passo_6,
    "7": passo_7,
}

# ---------------------------------------------------------------- Página

# O Streamlit mantém a posição do ecrã entre execuções: sem isto, o passo seguinte abria
# a meio. Só volta ao topo quando o passo muda (não a cada «+» ou opção escolhida).
_TOPO = """<script>
(() => {
  const passo = "%s";
  if (window.vigoriaPasso === passo) return;
  window.vigoriaPasso = passo;
  const subir = () => {
    window.scrollTo(0, 0);
    document
      .querySelectorAll('[data-testid="stMain"], [data-testid="stAppViewContainer"]')
      .forEach((e) => e.scrollTo(0, 0));
  };
  subir();
  setTimeout(subir, 150);
})();
</script>"""


def _ir_ao_topo(passo: str) -> None:
    st.html(_TOPO % passo, unsafe_allow_javascript=True)


if obter_configuracao().ambiente == "local":
    with st.sidebar:
        st.button(t.PREENCHER_PERSONA, help=t.PREENCHER_PERSONA_AJUDA, on_click=_preencher_persona)

if st.session_state.get(comum.TERMINADO_GRAVIDEZ):
    st.title(t.GRAVIDEZ_TITULO)
    st.info(avisos_motor.GRAVIDEZ, icon=":material/pregnant_woman:")
    st.caption(t.GRAVIDEZ_NADA_GUARDADO)
    st.button(t.VOLTAR_INICIO, width="stretch", on_click=_recomecar)
    st.stop()

passo = st.session_state[comum.PASSO]
indice = PASSOS.index(passo)
_ir_ao_topo(passo)
st.title(t.TITULOS[passo])
st.progress(indice / (len(PASSOS) - 1), text=t.PASSO_DE.format(n=indice + 1, total=len(PASSOS)))
if st.session_state.get(comum.ERROS):
    st.error(t.ERROS_NO_PASSO, icon=":material/error:")

PASSOS_DESENHO[passo]()

if passo != "7" or not st.session_state.get(A_GERAR):
    with st.container(horizontal=True):
        if indice > 0:
            st.button(t.ANTERIOR, icon=":material/arrow_back:", width="stretch", on_click=_anterior)
        # No primeiro ecrã não há passo anterior: «Anterior» volta à página de início.
        elif st.button(t.ANTERIOR, icon=":material/arrow_back:", width="stretch"):
            st.switch_page(comum.PAGINA_INICIO)
        if passo != "7":
            st.button(
                t.SEGUINTE,
                type="primary",
                icon=":material/arrow_forward:",
                icon_position="right",
                width="stretch",
                on_click=_seguinte,
            )
