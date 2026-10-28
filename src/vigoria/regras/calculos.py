"""Cálculos determinísticos (REGRAS_DOMINIO §2). Funções puras, sem LLM.

As contas são feitas em Decimal para que os limiares (IMC 35,0, ritmos de perda)
não dependam de erros de vírgula flutuante.
"""

from collections.abc import Collection
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from vigoria.modelos.questionario import Condicao, Sexo
from vigoria.regras import textos

SEMANAS_PROGRAMA = 16
SEMANAS_MARCOS = (4, 8, 12, 16)

LIMIAR_IMC_PRUDENTE = Decimal("35")
LIMIAR_IMC_BAIXO_PESO = Decimal("18.5")
LIMIAR_CINTURA_CM = {Sexo.MASCULINO: 94, Sexo.FEMININO: 80}
HIDRATACAO_ML_POR_KG = (Decimal("25"), Decimal("30"), Decimal("35"))
PROTEINA_G_POR_KG = (Decimal("1.0"), Decimal("1.2"))
PROTEINA_POR_REFEICAO_G = (25, 30)
# (idade mínima da faixa, % do peso atual por semana), da faixa mais velha para a mais nova
RITMO_MAXIMO_PERDA_PCT = ((61, Decimal("0.4")), (45, Decimal("0.5")), (18, Decimal("0.6")))
GANHO_MUSCULAR_KG_POR_4_SEMANAS = Decimal("0.5")


class _Resultado(BaseModel):
    model_config = ConfigDict(frozen=True)


class ClasseImc(StrEnum):
    BAIXO_PESO = "baixo_peso"
    NORMAL = "normal"
    EXCESSO_PESO = "excesso_peso"
    OBESIDADE_I = "obesidade_i"
    FORA_DA_VERSAO_BASE = "fora_da_versao_base"


class Hidratacao(_Resultado):
    """Intervalo diário em ml. Sem valores (None) com doença renal."""

    minimo_ml: int | None
    central_ml: int | None
    maximo_ml: int | None
    nota: str | None = None


class Proteina(_Resultado):
    """Intervalo diário em g. Sem valores (None) com doença renal."""

    minimo_g: int | None
    maximo_g: int | None
    por_refeicao_min_g: int | None
    por_refeicao_max_g: int | None
    nota: str | None = None


class AvaliacaoPerdaPeso(_Resultado):
    """Objetivo de peso face ao ritmo máximo da faixa etária."""

    perda_pedida_kg: float
    ritmo_necessario_kg_semana: float
    ritmo_maximo_kg_semana: float
    realista: bool
    alvo_semana_16_kg: float  # o peso-alvo, se realista; senão, o alvo realista
    semana_objetivo: int | None  # semana estimada para o objetivo completo; None sem perda


class AvaliacaoGanhoMuscular(_Resultado):
    """Objetivo de massa muscular face ao máximo de 0,5 kg por cada 4 semanas."""

    pedido_kg: float | None  # None = «aumentar força e tónus», sem alvo numérico
    maximo_kg: float
    realista: bool
    alvo_semana_16_kg: float | None
    semana_objetivo: int | None


def calcular_imc(peso_kg: float, altura_cm: float) -> float:
    """IMC = peso / altura², arredondado a 1 casa decimal (meio para cima)."""
    if peso_kg <= 0 or altura_cm <= 0:
        raise ValueError("peso e altura têm de ser positivos")
    altura_m = _d(altura_cm) / 100
    return _arredondar(_d(peso_kg) / altura_m**2, "0.1")


def classe_imc(imc: float) -> ClasseImc:
    """Classe de IMC (Vol. 1 / OMS); ≥ 35 fica fora da versão-base."""
    valor = _d(imc)
    if valor < Decimal("18.5"):
        return ClasseImc.BAIXO_PESO
    if valor < 25:
        return ClasseImc.NORMAL
    if valor < 30:
        return ClasseImc.EXCESSO_PESO
    if valor < LIMIAR_IMC_PRUDENTE:
        return ClasseImc.OBESIDADE_I
    return ClasseImc.FORA_DA_VERSAO_BASE


def imc_leva_a_prudente(imc: float) -> bool:
    """IMC ≥ 35 ⇒ modo prudente com teto «Ligeira» (§1)."""
    return _d(imc) >= LIMIAR_IMC_PRUDENTE


def limiar_cintura_cm(sexo: Sexo) -> int:
    """Limiar de cintura de risco: 94 cm (H) ou 80 cm (M)."""
    return LIMIAR_CINTURA_CM[sexo]


def cintura_de_risco(sexo: Sexo, cintura_cm: float) -> bool:
    """Cintura acima do limiar ⇒ ativa o módulo de gordura visceral."""
    return _d(cintura_cm) > limiar_cintura_cm(sexo)


def calcular_hidratacao(peso_kg: float, condicoes: Collection[Condicao]) -> Hidratacao:
    """25 a 35 ml/kg (central 30). Sem valores com doença renal; nota com doença cardiovascular."""
    if Condicao.DOENCA_RENAL in condicoes:
        return Hidratacao(
            minimo_ml=None, central_ml=None, maximo_ml=None, nota=textos.HIDRATACAO_DOENCA_RENAL
        )
    peso = _d(peso_kg)
    minimo, central, maximo = (_inteiro(peso * ml) for ml in HIDRATACAO_ML_POR_KG)
    nota = (
        textos.HIDRATACAO_DOENCA_CARDIOVASCULAR
        if Condicao.DOENCA_CARDIOVASCULAR in condicoes
        else None
    )
    return Hidratacao(minimo_ml=minimo, central_ml=central, maximo_ml=maximo, nota=nota)


def calcular_proteina(peso_kg: float, condicoes: Collection[Condicao]) -> Proteina:
    """1,0 a 1,2 g/kg, nunca acima. Sem valores com doença renal.

    Com qualquer outra condição da tabela 1.1, acrescenta a nota dos 1,5 g/kg.
    """
    if Condicao.DOENCA_RENAL in condicoes:
        return Proteina(
            minimo_g=None,
            maximo_g=None,
            por_refeicao_min_g=None,
            por_refeicao_max_g=None,
            nota=textos.PROTEINA_DOENCA_RENAL,
        )
    peso = _d(peso_kg)
    # Mínimo arredondado para cima e máximo para baixo: nunca sai de 1,0–1,2 g/kg.
    minimo = _inteiro(peso * PROTEINA_G_POR_KG[0], ROUND_CEILING)
    maximo = _inteiro(peso * PROTEINA_G_POR_KG[1], ROUND_FLOOR)
    tem_condicao = any(c is not Condicao.NENHUMA for c in condicoes)
    return Proteina(
        minimo_g=minimo,
        maximo_g=maximo,
        por_refeicao_min_g=PROTEINA_POR_REFEICAO_G[0],
        por_refeicao_max_g=PROTEINA_POR_REFEICAO_G[1],
        nota=textos.PROTEINA_ATE_1_5 if tem_condicao else None,
    )


def ritmo_maximo_perda_pct(idade: int) -> float:
    """% do peso atual que se pode perder por semana: 0,6 (18–44), 0,5 (45–60), 0,4 (61+)."""
    return float(_ritmo_maximo_pct(idade))


def avaliar_perda_peso(peso_kg: float, peso_alvo_kg: float, idade: int) -> AvaliacaoPerdaPeso:
    """Compara o ritmo necessário em 16 semanas com o máximo da faixa etária.

    Se o ultrapassar, propõe o alvo realista à semana 16 e a semana estimada para o
    objetivo completo. Peso-alvo igual ou acima do atual: sem perda pedida.
    """
    peso = _d(peso_kg)
    ritmo_maximo = peso * _ritmo_maximo_pct(idade) / 100
    perda = max(peso - _d(peso_alvo_kg), Decimal(0))
    ritmo_necessario = perda / SEMANAS_PROGRAMA
    realista = ritmo_necessario <= ritmo_maximo

    if perda == 0:
        alvo, semana = _d(peso_alvo_kg), None
    elif realista:
        alvo, semana = _d(peso_alvo_kg), SEMANAS_PROGRAMA
    else:
        alvo = peso - ritmo_maximo * SEMANAS_PROGRAMA
        semana = _ceil(perda / ritmo_maximo)

    return AvaliacaoPerdaPeso(
        perda_pedida_kg=_arredondar(perda, "0.1"),
        ritmo_necessario_kg_semana=_arredondar(ritmo_necessario, "0.01"),
        ritmo_maximo_kg_semana=_arredondar(ritmo_maximo, "0.01"),
        realista=realista,
        alvo_semana_16_kg=_arredondar(alvo, "0.1"),
        semana_objetivo=semana,
    )


def peso_minimo_saudavel_kg(altura_cm: float) -> float:
    """Peso correspondente a IMC 18,5, arredondado para cima a 1 casa (o IMC nunca fica abaixo)."""
    if altura_cm <= 0:
        raise ValueError("a altura tem de ser positiva")
    altura_m = _d(altura_cm) / 100
    peso = LIMIAR_IMC_BAIXO_PESO * altura_m**2
    return float(peso.quantize(Decimal("0.1"), rounding=ROUND_CEILING))


def marcos_peso_kg(peso_kg: float, peso_alvo_kg: float, idade: int) -> tuple[float, ...]:
    """Peso indicativo às semanas 4, 8, 12 e 16 (decisão de 28/10/2026).

    Linear, com o ritmo usado = mínimo entre o necessário e o máximo da faixa etária.
    Atingido o objetivo, os marcos seguintes ficam iguais a ele (fase de manter).
    Sem perda pedida, todos os marcos são o peso atual.
    """
    peso, alvo = _d(peso_kg), _d(peso_alvo_kg)
    if alvo >= peso:
        return tuple(_arredondar(peso, "0.1") for _ in SEMANAS_MARCOS)
    ritmo_maximo = peso * _ritmo_maximo_pct(idade) / 100
    ritmo = min((peso - alvo) / SEMANAS_PROGRAMA, ritmo_maximo)
    return tuple(_arredondar(max(peso - ritmo * s, alvo), "0.1") for s in SEMANAS_MARCOS)


def ganho_muscular_maximo_kg(semanas: int = SEMANAS_PROGRAMA) -> float:
    """Máximo de 0,5 kg por cada 4 semanas (2 kg nas 16 semanas), em qualquer intensidade."""
    return float(_ganho_por_semana() * semanas)


def avaliar_ganho_muscular(
    objetivo: float | Literal["aumentar_forca_tonus"],
) -> AvaliacaoGanhoMuscular:
    """Compara o ganho pedido (5.C) com o máximo nas 16 semanas."""
    maximo = _ganho_por_semana() * SEMANAS_PROGRAMA
    if isinstance(objetivo, str):
        return AvaliacaoGanhoMuscular(
            pedido_kg=None,
            maximo_kg=float(maximo),
            realista=True,
            alvo_semana_16_kg=None,
            semana_objetivo=None,
        )
    pedido = _d(objetivo)
    if pedido <= 0:
        raise ValueError("o ganho muscular pedido tem de ser positivo")
    realista = pedido <= maximo
    return AvaliacaoGanhoMuscular(
        pedido_kg=float(pedido),
        maximo_kg=float(maximo),
        realista=realista,
        alvo_semana_16_kg=float(pedido if realista else maximo),
        semana_objetivo=SEMANAS_PROGRAMA if realista else _ceil(pedido / _ganho_por_semana()),
    )


def _ritmo_maximo_pct(idade: int) -> Decimal:
    for idade_minima, pct in RITMO_MAXIMO_PERDA_PCT:
        if idade >= idade_minima:
            return pct
    raise ValueError(f"idade fora do âmbito (menor de 18): {idade}")


def _ganho_por_semana() -> Decimal:
    return GANHO_MUSCULAR_KG_POR_4_SEMANAS / 4


def _d(valor: float) -> Decimal:
    return Decimal(str(valor))


def _arredondar(valor: Decimal, casas: str) -> float:
    return float(valor.quantize(Decimal(casas), rounding=ROUND_HALF_UP))


def _inteiro(valor: Decimal, modo: str = ROUND_HALF_UP) -> int:
    return int(valor.quantize(Decimal(1), rounding=modo))


def _ceil(valor: Decimal) -> int:
    return _inteiro(valor, ROUND_CEILING)
