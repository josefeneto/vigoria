"""Semana-tipo (determinístico; regra de 30/10/2026, dias escolhidos desde 18/11/2026).

Parte da semana-base do Vol. 1 (seg força A + mobilidade; ter cardio + mobilidade;
qua força B + equilíbrio; qui cardio leve + mobilidade; sex força A/B; sáb cardio;
dom recuperação ativa) e ajusta-a aos dias de treino escolhidos (`dias_treino`):
força em 1 dia (1 dia por semana), 2 dias (2 a 4) ou 3 dias (5 a 7), nunca em dias
seguidos (domingo → segunda também conta, porque a semana repete-se). Se os dias
escolhidos não o permitirem, há menos dias de força. Os restantes dias com sessão são
de cardio. Cada sessão dura `minutos_dia`. Todos os dias valem o mesmo: os dias sem
sessão (duração 0) são «caminhada leve (opcional)», ou «caminhada diária» com menos de
3 dias por semana.

Questionários anteriores a 18/11/2026 só têm `dias_semana`: usam os dias de DIAS_FIXOS.
"""

from itertools import combinations

from vigoria.conteudo.carregar import carregar_avisos
from vigoria.modelos.estrategia import Estrategia
from vigoria.modelos.plano import DiaSemana, SessaoDia
from vigoria.modelos.questionario import Questionario

D = DiaSemana
ORDEM = list(DiaSemana)
# Dias de treino dos questionários sem `dias_treino` (a semana fixa até 18/11/2026).
DIAS_FIXOS: dict[int, tuple[DiaSemana, ...]] = {
    1: (D.QUARTA,),
    2: (D.SEGUNDA, D.QUINTA),
    3: (D.SEGUNDA, D.QUARTA, D.SEXTA),
    4: (D.SEGUNDA, D.TERCA, D.QUINTA, D.SABADO),
    5: tuple(ORDEM[:5]),
    6: tuple(ORDEM[:6]),
    7: tuple(ORDEM),
}
# Tipo de dia (avisos.yaml, rotulos.semana) dos dias de cardio, pela ordem da semana,
# por número de dias de treino.
_CARDIO: dict[int, tuple[str, ...]] = {
    1: (),
    2: (),
    3: ("cardio_mobilidade",),
    4: ("cardio_mobilidade", "cardio"),
    5: ("cardio_mobilidade", "cardio_leve_mobilidade"),
    6: ("cardio_mobilidade", "cardio_leve_mobilidade", "cardio"),
    7: ("cardio_mobilidade", "cardio_leve_mobilidade", "cardio", "recuperacao_ativa"),
}
TIPOS_FORCA = frozenset({"forca", "forca_equilibrio"})


def numero_dias_forca(dias_semana: int) -> int:
    """1 dia de força (1 dia por semana), 2 (2 a 4) ou 3 (5 a 7)."""
    return 1 if dias_semana == 1 else 2 if dias_semana <= 4 else 3


def _intervalos(indices: tuple[int, ...]) -> list[int]:
    """Dias entre dias de força consecutivos, com a volta de domingo para segunda."""
    if len(indices) < 2:
        return [7]
    return [(b - a) % 7 for a, b in zip(indices, indices[1:] + indices[:1], strict=True)]


def dias_de_forca(dias: tuple[DiaSemana, ...]) -> tuple[DiaSemana, ...]:
    """Os dias de força entre os dias de treino: o número de `numero_dias_forca`, nunca dois
    seguidos; se não couberem, menos. Entre as escolhas possíveis, a mais espaçada (maior
    intervalo mínimo) e, em empate, a que começa mais cedo na semana."""
    indices = sorted(ORDEM.index(d) for d in set(dias))
    for n in range(min(numero_dias_forca(len(indices)), len(indices)), 0, -1):
        possiveis = [c for c in combinations(indices, n) if min(_intervalos(c)) > 1]
        if possiveis:
            melhor = min(possiveis, key=lambda c: (-min(_intervalos(c)), c))
            return tuple(ORDEM[i] for i in melhor)
    return ()


def dias_de_treino(q: Questionario) -> tuple[DiaSemana, ...]:
    """Os dias escolhidos, pela ordem da semana; sem eles, os da semana fixa antiga."""
    return tuple(q.dias_treino) if q.dias_treino else DIAS_FIXOS[q.dias_semana]


def sessoes(q: Questionario) -> dict[DiaSemana, str]:
    """Tipo de dia (avisos.yaml, rotulos.semana) em cada dia com sessão."""
    dias = dias_de_treino(q)
    forca = dias_de_forca(dias)
    cardio = [d for d in dias if d not in forca]
    tipos_cardio = _CARDIO[len(dias)]
    if len(tipos_cardio) != len(cardio):  # menos dias de força do que o previsto
        tipos_cardio = ("cardio_mobilidade",) * len(cardio)
    tipos = {d: "forca" for d in forca}
    if len(forca) == 3:
        tipos[forca[1]] = "forca_equilibrio"
    tipos |= dict(zip(cardio, tipos_cardio, strict=True))
    return {d: tipos[d] for d in ORDEM if d in tipos}


def construir_semana(e: Estrategia, q: Questionario) -> tuple[SessaoDia, ...]:
    rotulos = carregar_avisos().rotulos.semana
    com_sessao = sessoes(q)
    livre = "caminhada_diaria" if e.caminhada_diaria_extra else "caminhada_leve"
    semana = []
    for dia in DiaSemana:
        if dia in com_sessao:
            tipo, duracao = com_sessao[dia], q.minutos_dia
        else:
            tipo, duracao = livre, 0
        rotulo = rotulos[tipo]
        semana.append(
            SessaoDia(
                dia=dia, atividade=rotulo.atividade, duracao_min=duracao, descricao=rotulo.descricao
            )
        )
    return tuple(semana)
