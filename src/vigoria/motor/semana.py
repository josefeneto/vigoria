"""Semana-tipo (determinístico, Fase 4C, regra aprovada a 30/10/2026).

Parte da semana-base do Vol. 1 (seg força A + mobilidade; ter cardio + mobilidade;
qua força B + equilíbrio; qui cardio leve + mobilidade; sex força A/B; sáb cardio;
dom recuperação ativa ou descanso) e ajusta-a a `dias_semana`:
força em 1 dia (1), 2 dias (2 a 4) ou 3 dias (5 a 7), nunca em dias seguidos; os
restantes dias com sessão são de cardio. Cada sessão dura `minutos_dia`. Os dias sem
sessão (duração 0) são «caminhada leve (opcional)», ou «caminhada diária» com menos de
3 dias por semana; o domingo sem sessão é descanso.
"""

from vigoria.conteudo.carregar import carregar_avisos
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import DiaSemana, SessaoDia
from vigoria.modelos.questionario import Questionario

D = DiaSemana
# Tipo de dia (avisos.yaml, rotulos.semana) em cada dia com sessão, por número de dias.
SESSOES: dict[int, dict[DiaSemana, str]] = {
    1: {D.QUARTA: "forca"},
    2: {D.SEGUNDA: "forca", D.QUINTA: "forca"},
    3: {D.SEGUNDA: "forca", D.QUARTA: "cardio_mobilidade", D.SEXTA: "forca"},
    4: {
        D.SEGUNDA: "forca",
        D.TERCA: "cardio_mobilidade",
        D.QUINTA: "forca",
        D.SABADO: "cardio",
    },
    5: {
        D.SEGUNDA: "forca",
        D.TERCA: "cardio_mobilidade",
        D.QUARTA: "forca_equilibrio",
        D.QUINTA: "cardio_leve_mobilidade",
        D.SEXTA: "forca",
    },
}
SESSOES[6] = SESSOES[5] | {D.SABADO: "cardio"}
SESSOES[7] = SESSOES[6] | {D.DOMINGO: "recuperacao_ativa"}
TIPOS_FORCA = frozenset({"forca", "forca_equilibrio"})


def construir_semana(e: Estrategia, q: Questionario) -> tuple[SessaoDia, ...]:
    rotulos = carregar_avisos().rotulos.semana
    sessoes = SESSOES[q.dias_semana]
    livre = "caminhada_diaria" if e.caminhada_diaria_extra else "caminhada_leve"
    semana = []
    for dia in DiaSemana:
        if dia in sessoes:
            tipo, duracao = sessoes[dia], q.minutos_dia
        else:
            tipo, duracao = ("descanso" if dia is D.DOMINGO else livre), 0
        rotulo = rotulos[tipo]
        semana.append(
            SessaoDia(
                dia=dia, atividade=rotulo.atividade, duracao_min=duracao, descricao=rotulo.descricao
            )
        )
    return tuple(semana)
