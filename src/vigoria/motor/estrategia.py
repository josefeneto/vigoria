"""Estratégia (papel 2, determinístico): modo, intensidade, restrições, avisos e marcos.

Recebe um Questionario e devolve uma Estrategia. Só usa as escolhas fechadas do
questionário: o texto livre nunca é interpretado (segue para a LLM só como contexto).
"""

from typing import assert_never

from vigoria.modelos.estrategia import Estrategia, Indicadores, Marco, Restricoes, Zona
from vigoria.modelos.questionario import (
    Articulacao,
    Condicao,
    Gravidade,
    Limitacao,
    Questionario,
    SimNaoNaoSei,
)
from vigoria.motor.acolhimento import Acolhimento, acolher
from vigoria.regras import textos
from vigoria.regras.calculos import SEMANAS_MARCOS, marcos_peso_kg
from vigoria.regras.elegibilidade import Elegibilidade, Modo, avaliar_elegibilidade
from vigoria.regras.intensidade import (
    abaixo_do_minimo,
    calcular_intensidade_efetiva,
    sessoes_curtas,
)


def gerar_estrategia(q: Questionario) -> Estrategia:
    """Aplica as secções 1 a 5 da REGRAS_DOMINIO ao questionário."""
    eleg = avaliar_elegibilidade(q)
    if eleg.modo is Modo.NAO_ELEGIVEL:
        return Estrategia(
            pode_gerar_plano=False,
            modo=eleg.modo,
            motivos=eleg.motivos,
            intensidade_pedida=q.intensidade_pedida,
            usar_frequencia_cardiaca=eleg.usar_frequencia_cardiaca,
        )

    acolhimento = acolher(q)
    intensidade = calcular_intensidade_efetiva(
        q.intensidade_pedida, eleg.intensidade_maxima, q.dias_semana, q.minutos_dia
    )
    return Estrategia(
        pode_gerar_plano=True,
        modo=eleg.modo,
        motivos=eleg.motivos,
        intensidade_pedida=intensidade.pedida,
        intensidade_efetiva=intensidade.efetiva,
        intensidade_limitada_por=intensidade.limitada_por,
        explicacao_intensidade=intensidade.explicacao,
        sessoes_curtas=sessoes_curtas(q.minutos_dia),
        caminhada_diaria_extra=abaixo_do_minimo(q.dias_semana),
        indicadores=acolhimento.indicadores,
        modulo_gordura_visceral=acolhimento.indicadores.cintura_de_risco,
        usar_frequencia_cardiaca=eleg.usar_frequencia_cardiaca,
        restricoes=restricoes_exercicio(q, eleg),
        avisos=avisos(q, eleg, acolhimento),
        marcos=marcos(q, acolhimento.indicadores),
    )


def restricoes_exercicio(q: Questionario, eleg: Elegibilidade) -> Restricoes:
    """Restrições de exercício da §1, da tabela 1.1 e da §6.3."""
    # Regra completa: dor articular persistente e limitação importante; regra ligeira: limitação
    # ligeira numa zona sem a completa (vale a mais restritiva, §1). REGRAS_DOMINIO §6.6.
    zonas_escolhidas = {str(lim) for lim in q.limitacoes} | {str(a) for a in q.dor_articular_zonas}
    completas = {str(a) for a in q.dor_articular_zonas} | {
        str(lim) for lim, g in q.limitacoes_gravidade.items() if g is Gravidade.IMPORTANTE
    }
    zonas = tuple(zona for zona in Zona if zona in completas)
    zonas_ligeira = tuple(zona for zona in Zona if zona in zonas_escolhidas - completas)
    osteoporose = Condicao.OSTEOPOROSE in q.condicoes
    osteoporose_com_risco = osteoporose and q.osteoporose_risco is not SimNaoNaoSei.NAO
    contraindicacoes = ({str(c) for c in q.condicoes} | zonas_escolhidas) - {
        Condicao.NENHUMA,
        Condicao.OUTRA,
        Limitacao.NENHUMA,
        Limitacao.OUTRA,
    }

    return Restricoes(
        sem_impacto=True,  # no MVP, para todos (decisão de 28/10/2026, REGRAS_DOMINIO §6.3)
        equilibrio_com_apoio=osteoporose_com_risco or Limitacao.EQUILIBRIO in q.limitacoes,
        sem_intervalos=eleg.modo is Modo.PRUDENTE,
        sem_flexao_tronco_com_carga=osteoporose,
        zonas_regressao=zonas,
        zonas_regressao_ligeira=zonas_ligeira,
        regressao_geral=Articulacao.OUTRA in q.dor_articular_zonas,
        contraindicacoes=tuple(sorted(contraindicacoes)),
        equipamento=tuple(q.equipamento),
    )


def avisos(q: Questionario, eleg: Elegibilidade, acolhimento: Acolhimento) -> tuple[str, ...]:
    """Avisos obrigatórios (§7) e condicionais, sem repetições e por ordem de importância."""
    ind = acolhimento.indicadores
    lista = [textos.AVISO_GERAL, textos.SINAIS_INTERROMPER]
    if eleg.modo is Modo.PRUDENTE:
        lista.append(textos.ORIENTACAO_INDIVIDUALIZADA)
    lista.extend(avisos_condicoes(q))
    if not eleg.usar_frequencia_cardiaca:
        lista.append(textos.ESFORCO_PERCEBIDO)
    if abaixo_do_minimo(q.dias_semana):
        lista.append(
            textos.DISPONIBILIDADE_1_DIA if q.dias_semana == 1 else textos.DISPONIBILIDADE_2_DIAS
        )
    lista.extend(avisos_objetivo(acolhimento))
    # O ganho muscular pedido nunca excede o máximo: o questionário limita-o a 2 kg (5.C).
    if ind.cintura_de_risco:
        lista.extend([textos.VISCERAL_REDUCAO, textos.VISCERAL_INDICADOR])
        if {Condicao.HIPERTENSAO, Condicao.DOENCA_CARDIOVASCULAR} & set(q.condicoes):
            lista.append(textos.INTENSIFICACAO_VALIDACAO_MEDICA)
    return tuple(dict.fromkeys(lista))


def avisos_objetivo(acolhimento: Acolhimento) -> list[str]:
    """Incoerências nos objetivos e, se o ritmo exceder o máximo, o alvo realista (§2).
    Também usados no passo 5 do questionário, logo ao indicar o peso-alvo."""
    ind = acolhimento.indicadores
    lista = list(acolhimento.incoerencias)
    perda = ind.perda_peso
    if not perda.realista:
        lista.append(
            textos.PERDA_NAO_REALISTA.format(
                peso_alvo=textos.numero(ind.peso_alvo_usado_kg),
                ritmo_necessario=textos.numero(perda.ritmo_necessario_kg_semana, 2),
                ritmo_maximo=textos.numero(perda.ritmo_maximo_kg_semana, 2),
                alvo_16=textos.numero(perda.alvo_semana_16_kg),
                semana=perda.semana_objetivo,
            )
        )
    return lista


def avisos_condicoes(q: Questionario) -> list[str]:
    """Consequências adicionais de cada condição da tabela 1.1 que são avisos."""
    lista = []
    for condicao in q.condicoes:
        controlada = q.condicoes_controladas.get(condicao)
        match condicao:
            case Condicao.HIPERTENSAO:
                if controlada:
                    lista.append(textos.INTENSIFICACAO_VALIDACAO_MEDICA)
                else:
                    lista.append(textos.FALAR_COM_MEDICO_ANTES)
            case Condicao.DIABETES:
                lista.append(textos.DIABETES_HIPOGLICEMIA)
                if not controlada:
                    lista.append(textos.FALAR_COM_MEDICO_ANTES)
            case Condicao.DOENCA_CARDIOVASCULAR:
                lista.append(textos.VALIDACAO_MEDICA_ANTES)
            case Condicao.DOENCA_RESPIRATORIA:
                lista.append(textos.RESPIRATORIA_TESTE_DA_FALA)
            case Condicao.DOENCA_INFLAMATORIA_INTESTINAL:
                lista.append(textos.DII_PLANO_ALIMENTAR)
                if not controlada:
                    lista.append(textos.DII_ADIAR_MUDANCAS)
            case Condicao.PROTESE_OU_CIRURGIA_RECENTE:
                lista.append(textos.VALIDACAO_CIRURGIAO_ANTES)
            case (
                Condicao.DOENCA_RENAL  # notas da proteína e da hidratação, nos indicadores
                | Condicao.OSTEOPOROSE  # restrições de exercício
                | Condicao.DOR_ARTICULAR_PERSISTENTE  # restrições de exercício
                | Condicao.OUTRA  # aviso de orientação individualizada (modo prudente)
                | Condicao.GRAVIDEZ
                | Condicao.NENHUMA
            ):
                pass
            case _:
                assert_never(condicao)
    return lista


def marcos(q: Questionario, ind: Indicadores) -> tuple[Marco, ...]:
    """Marcos das semanas 4, 8, 12 e 16 (§5, decisão de 28/10/2026)."""
    pesos = marcos_peso_kg(q.peso_kg, ind.peso_alvo_usado_kg, q.idade)
    if ind.cintura_de_risco:
        cintura = textos.CINTURA_MEDIR_COM_LIMIAR.format(limiar=ind.limiar_cintura_cm)
    else:
        cintura = textos.CINTURA_MEDIR
    return tuple(
        Marco(semana=semana, fase=fase, peso_indicativo_kg=peso, cintura=cintura)
        for semana, fase, peso in zip(SEMANAS_MARCOS, textos.FASES, pesos, strict=True)
    )
