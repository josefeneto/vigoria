"""Acompanhamento do progresso (REGRAS_DOMINIO §9, tabela aprovada a 05/11/2026).

Funções puras: a data de hoje entra sempre como argumento. Devolvem códigos e números; os
textos estão em paginas/textos.py. As observações da pessoa nunca chegam aqui.
"""

from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict

from vigoria.modelos.questionario import FrequenciaRegisto
from vigoria.regras.calculos import SEMANAS_MARCOS, SEMANAS_PROGRAMA, ritmo_maximo_perda_pct

SEMANAS_POR_FASE = 4
FASE_MANUTENCAO_ESFORCO = 4  # na manutenção, o teto de esforço é o da fase 4

# A CONFIRMAR (revisão profissional): REGRAS_DOMINIO §9.
ABAIXO_SEMANA_MINIMA = 4
ABAIXO_FRACAO = 0.5  # perda acumulada < 50 % da indicativa
ABAIXO_DIFERENCA_KG = 1.0  # e mais de 1 kg acima da linha (absorve oscilações de ±0,8 kg)
RAPIDA_SEMANA_MINIMA = 3  # a perda inicial é sobretudo água
RAPIDA_JANELA_SEMANAS = 4
RAPIDA_MARGEM_KG_SEMANA = 0.4  # 2 × 0,8 kg em 4 semanas
SUBIDA_PESO_KG = 2.0
SUBIDA_CINTURA_CM = 3.0
PERIODOS_SEGUIDOS = 2


class TipoAlerta(StrEnum):
    PERDA_RAPIDA = "perda_rapida"
    ESFORCO_ACIMA = "esforco_acima"
    SUBIDA_PESO = "subida_peso"
    SUBIDA_CINTURA = "subida_cintura"
    EVOLUCAO_ABAIXO = "evolucao_abaixo"
    PERIODO_EM_FALTA = "periodo_em_falta"


class _Imutavel(BaseModel):
    model_config = ConfigDict(frozen=True)


class Medicao(_Imutavel):
    """O que as regras leem de um registo."""

    semana: int
    peso_kg: float | None = None
    cintura_cm: float | None = None
    esforco: int | None = None


class ContextoPlano(_Imutavel):
    """O que as regras precisam de saber do plano (calculado ao gerá-lo)."""

    inicio: date
    peso_inicial_kg: float | None = None
    idade: int | None = None
    peso_alvo_kg: float | None = None
    marcos: tuple[tuple[int, float], ...] = ()  # (semana, peso indicativo)
    esforco_fases: Mapping[int, tuple[int, int]] = {}  # fase: (mínimo, máximo)


class Alerta(_Imutavel):
    tipo: TipoAlerta
    semanas: tuple[int, int] | None = None  # período em falta
    pct: float | None = None  # ritmo máximo da faixa etária
    esforco: int | None = None
    esforco_faixa: tuple[int, int] | None = None
    referencia: float | None = None  # valor do início da manutenção


# ---------------------------------------------------------------- Semanas, fases e períodos


def dia_em_lisboa(instante: datetime) -> date:
    """O dia de um instante guardado na base (em UTC), na hora de Portugal continental."""
    if instante.tzinfo is None:  # o SQLite devolve sem fuso
        instante = instante.replace(tzinfo=UTC)
    return instante.astimezone(ZoneInfo("Europe/Lisbon")).date()


def inicio_do_plano(criado_em: datetime) -> date:
    """O dia da criação do plano, na hora de Portugal continental."""
    return dia_em_lisboa(criado_em)


def semana_do_plano(inicio: date, dia: date) -> int:
    """Dias 0 a 6 desde o início = semana 1. Sem semanas antes do início do plano."""
    if dia < inicio:
        raise ValueError("a data é anterior ao início do plano")
    return (dia - inicio).days // 7 + 1


def _validar_semana(semana: int) -> None:
    if semana < 1:
        raise ValueError("as semanas contam-se a partir de 1")


def em_manutencao(semana: int) -> bool:
    """A partir da semana 17, pela data, mesmo sem registos."""
    _validar_semana(semana)
    return semana > SEMANAS_PROGRAMA


def fase_da_semana(semana: int) -> int | None:
    """Fase 1 a 4; None na manutenção."""
    return None if em_manutencao(semana) else (semana - 1) // SEMANAS_POR_FASE + 1


def proximo_marco(semana: int) -> int | None:
    """O marco (4, 8, 12 ou 16) desta semana ou o seguinte; None na manutenção."""
    _validar_semana(semana)
    return next((m for m in SEMANAS_MARCOS if m >= semana), None)


def frequencia_efetiva(escolhida: FrequenciaRegisto, semana: int) -> FrequenciaRegisto:
    """Na manutenção, a cada 4 semanas, seja qual for a escolha."""
    return FrequenciaRegisto.A_CADA_4_SEMANAS if em_manutencao(semana) else escolhida


def periodo(semana: int, frequencia: FrequenciaRegisto) -> tuple[int, int]:
    """(primeira, última) semana do período: a própria semana, ou o bloco 1–4, 5–8, 9–12..."""
    _validar_semana(semana)
    if frequencia is FrequenciaRegisto.SEMANAL:
        return semana, semana
    fim = ((semana - 1) // SEMANAS_POR_FASE + 1) * SEMANAS_POR_FASE
    return fim - SEMANAS_POR_FASE + 1, fim


def periodo_ocupado(
    semana: int, frequencia: FrequenciaRegisto, semanas_com_registo: Iterable[int]
) -> bool:
    """Já há um registo no período desta semana (um registo por período)."""
    inicio, fim = periodo(semana, frequencia_efetiva(frequencia, semana))
    return any(inicio <= s <= fim for s in semanas_com_registo)


def ultimo_dia_do_periodo(inicio: date, semanas: tuple[int, int]) -> date:
    """O prazo do período: o último dia da última semana."""
    return inicio + timedelta(days=7 * semanas[1] - 1)


def periodos_terminados(
    inicio: date, hoje: date, frequencia: FrequenciaRegisto
) -> Iterator[tuple[int, int]]:
    """Os períodos já terminados, do mais recente para o mais antigo. O último dia ainda conta."""
    if hoje <= inicio:
        return
    semana = semana_do_plano(inicio, hoje - timedelta(days=1))
    while semana >= 1:
        semanas = periodo(semana, frequencia_efetiva(frequencia, semana))
        if hoje > ultimo_dia_do_periodo(inicio, semanas):
            yield semanas
        semana = semanas[0] - 1


def tem_registo(semanas: tuple[int, int], semanas_com_registo: Iterable[int]) -> bool:
    return any(semanas[0] <= s <= semanas[1] for s in semanas_com_registo)


def periodo_em_falta(
    inicio: date,
    hoje: date,
    frequencia: FrequenciaRegisto,
    semanas_com_registo: Collection[int],
) -> tuple[int, int] | None:
    """O período terminado mais recente sem registo."""
    return next(
        (
            p
            for p in periodos_terminados(inicio, hoje, frequencia)
            if not tem_registo(p, semanas_com_registo)
        ),
        None,
    )


# ---------------------------------------------------------------- Linha indicativa


def linha_indicativa(
    peso_inicial_kg: float, marcos: Sequence[tuple[int, float]], semana: int
) -> float:
    """Peso indicativo numa semana: reta entre os marcos, a partir do peso do questionário."""
    pontos = [(0, peso_inicial_kg), *sorted(marcos)]
    if semana >= pontos[-1][0]:
        return pontos[-1][1]
    for (s0, p0), (s1, p1) in zip(pontos, pontos[1:], strict=False):
        if semana <= s1:
            return round(p0 + (p1 - p0) * (semana - s0) / (s1 - s0), 2)
    raise AssertionError("inalcançável: a semana é anterior ao último marco")


# ---------------------------------------------------------------- Regras


def _com_peso(medicoes: Iterable[Medicao]) -> list[Medicao]:
    return sorted((m for m in medicoes if m.peso_kg is not None), key=lambda m: m.semana)


def _ultimos_todos(medicoes: Sequence[Medicao], condicao: Callable[[Medicao], bool]) -> bool:
    """Os 2 últimos registos cumprem a condição (nunca com menos de 2)."""
    ultimos = medicoes[-PERIODOS_SEGUIDOS:]
    return len(ultimos) == PERIODOS_SEGUIDOS and all(condicao(m) for m in ultimos)


def evolucao_abaixo(
    medicoes: Iterable[Medicao],
    peso_inicial_kg: float,
    marcos: Sequence[tuple[int, float]],
    peso_alvo_kg: float,
) -> bool:
    """R8: a perda acumulada fica abaixo da linha indicativa em 2 registos seguidos com peso.

    Só compara o peso (a cintura não tem número, §5). Nunca com objetivo de manter (linha
    sem perda) nem depois de atingir o peso-alvo. Quem chama trata da manutenção.
    """

    def abaixo(m: Medicao) -> bool:
        assert m.peso_kg is not None
        if m.semana < ABAIXO_SEMANA_MINIMA or m.peso_kg <= peso_alvo_kg:
            return False
        linha = linha_indicativa(peso_inicial_kg, marcos, m.semana)
        indicativa = peso_inicial_kg - linha
        return (
            indicativa > 0
            and round(peso_inicial_kg - m.peso_kg, 6) < round(indicativa * ABAIXO_FRACAO, 6)
            and round(m.peso_kg - linha, 6) > ABAIXO_DIFERENCA_KG
        )

    return _ultimos_todos(_com_peso(medicoes), abaixo)


def ritmo_medio_kg_semana(
    medicoes: Iterable[Medicao], peso_inicial_kg: float, semana: int
) -> float:
    """Perda média por semana nas últimas 4 semanas (ou desde o início, se houver menos).

    Sem registo há exatamente 4 semanas, usa o mais próximo antes disso.
    """
    com_peso = {m.semana: m.peso_kg for m in _com_peso(medicoes)}
    if semana not in com_peso:
        raise ValueError("sem peso registado nesta semana")
    anteriores = [s for s in com_peso if s <= semana - RAPIDA_JANELA_SEMANAS]
    if anteriores:
        base = max(anteriores)
        peso_base = com_peso[base]
    else:
        base, peso_base = 0, peso_inicial_kg
    return (peso_base - com_peso[semana]) / (semana - base)  # type: ignore[operator]


def perda_rapida(medicoes: Iterable[Medicao], peso_inicial_kg: float, idade: int) -> float | None:
    """R9: o % máximo da faixa etária, se o ritmo médio o exceder em 2 registos seguidos.

    O máximo calcula-se sobre o peso do questionário, como o ritmo máximo do plano
    (`avaliar_perda_peso`), mais uma margem para a oscilação normal do peso.
    """
    lista = _com_peso(medicoes)
    pct = ritmo_maximo_perda_pct(idade)
    limite = peso_inicial_kg * pct / 100 + RAPIDA_MARGEM_KG_SEMANA

    def rapida(m: Medicao) -> bool:
        if m.semana < RAPIDA_SEMANA_MINIMA:
            return False
        return round(ritmo_medio_kg_semana(lista, peso_inicial_kg, m.semana) - limite, 6) > 0

    return pct if _ultimos_todos(lista, rapida) else None


def esforco_acima(
    medicoes: Iterable[Medicao], esforco_fases: Mapping[int, tuple[int, int]]
) -> tuple[int, tuple[int, int]] | None:
    """R10: (esforço, faixa da fase), se o último registo com esforço passar o teto da fase."""
    com_esforco = sorted((m for m in medicoes if m.esforco is not None), key=lambda m: m.semana)
    if not com_esforco:
        return None
    ultimo = com_esforco[-1]
    fase = fase_da_semana(ultimo.semana) or FASE_MANUTENCAO_ESFORCO
    faixa = esforco_fases.get(fase)
    if faixa is None or ultimo.esforco is None or ultimo.esforco <= faixa[1]:
        return None
    return ultimo.esforco, faixa


def _subida(valores: Sequence[tuple[int, float]], margem: float) -> float | None:
    """A referência, se os 2 últimos valores da manutenção ficarem acima dela pela margem."""
    manutencao = [v for s, v in valores if em_manutencao(s)]
    antes = [v for s, v in valores if not em_manutencao(s)]
    if not manutencao:
        return None
    referencia = antes[-1] if antes else manutencao[0]
    ultimos = manutencao[-PERIODOS_SEGUIDOS:]
    if len(ultimos) < PERIODOS_SEGUIDOS:
        return None
    return referencia if all(round(v - referencia, 6) >= margem for v in ultimos) else None


def subida_manutencao(medicoes: Iterable[Medicao]) -> tuple[float | None, float | None]:
    """R11: (referência do peso, referência da cintura), quando há subida consistente."""
    ordenadas = sorted(medicoes, key=lambda m: m.semana)
    pesos = [(m.semana, m.peso_kg) for m in ordenadas if m.peso_kg is not None]
    cinturas = [(m.semana, m.cintura_cm) for m in ordenadas if m.cintura_cm is not None]
    return _subida(pesos, SUBIDA_PESO_KG), _subida(cinturas, SUBIDA_CINTURA_CM)


def avaliar(
    contexto: ContextoPlano,
    medicoes: Sequence[Medicao],
    frequencia: FrequenciaRegisto,
    hoje: date,
) -> tuple[Alerta, ...]:
    """Os alertas de hoje, primeiro os de segurança. Com o acompanhamento desligado, não chamar."""
    semana = semana_do_plano(contexto.inicio, hoje)
    alertas: list[Alerta] = []

    c = contexto
    if c.peso_inicial_kg is not None and c.idade is not None:
        pct = perda_rapida(medicoes, c.peso_inicial_kg, c.idade)
        if pct is not None:
            alertas.append(Alerta(tipo=TipoAlerta.PERDA_RAPIDA, pct=pct))

    acima = esforco_acima(medicoes, c.esforco_fases)
    if acima is not None:
        alertas.append(
            Alerta(tipo=TipoAlerta.ESFORCO_ACIMA, esforco=acima[0], esforco_faixa=acima[1])
        )

    if em_manutencao(semana):
        peso, cintura = subida_manutencao(medicoes)
        if peso is not None:
            alertas.append(Alerta(tipo=TipoAlerta.SUBIDA_PESO, referencia=peso))
        if cintura is not None:
            alertas.append(Alerta(tipo=TipoAlerta.SUBIDA_CINTURA, referencia=cintura))
    elif (
        c.peso_inicial_kg is not None
        and c.peso_alvo_kg is not None
        and c.marcos
        and evolucao_abaixo(medicoes, c.peso_inicial_kg, c.marcos, c.peso_alvo_kg)
    ):
        alertas.append(Alerta(tipo=TipoAlerta.EVOLUCAO_ABAIXO))

    falta = periodo_em_falta(c.inicio, hoje, frequencia, {m.semana for m in medicoes})
    if falta is not None:
        alertas.append(Alerta(tipo=TipoAlerta.PERIODO_EM_FALTA, semanas=falta))
    return tuple(alertas)
