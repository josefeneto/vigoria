"""Modelos do plano (REGRAS_DOMINIO §5 a §7).

Dois níveis:
- `PlanoGerado` é o que a LLM devolve (schema da saída JSON). Não tem campos para
  números de peso, proteína ou hidratação: esses vêm calculados da Estrategia.
- `Plano` é o plano final, montado pelo código: PlanoGerado + números + avisos fixos.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from vigoria.regras.calculos import Hidratacao, Proteina


class _Modelo(BaseModel):
    model_config = ConfigDict(frozen=True)


class DiaSemana(StrEnum):
    SEGUNDA = "segunda"
    TERCA = "terca"
    QUARTA = "quarta"
    QUINTA = "quinta"
    SEXTA = "sexta"
    SABADO = "sabado"
    DOMINGO = "domingo"


class Refeicao(StrEnum):
    PEQUENO_ALMOCO = "pequeno_almoco"
    ALMOCO = "almoco"
    LANCHE = "lanche"
    JANTAR = "jantar"
    CEIA = "ceia"


# ---------------------------------------------------------------- Saída da LLM


class SessaoDia(_Modelo):
    """Um dia da semana-tipo (Vol. 1, ajustada aos dias declarados)."""

    dia: DiaSemana
    atividade: str  # por exemplo, «Força A + mobilidade» ou «Descanso»
    duracao_min: int  # 0 nos dias de descanso
    descricao: str


class ExercicioPrescrito(_Modelo):
    """Um exercício da lista permitida, identificado só pelo id da biblioteca."""

    exercicio_id: str
    series: int
    repeticoes: str  # «12-15», «30-45s», «10 (por perna)»
    descanso: str  # «45 a 60 s»
    adaptacao: str  # vazio se não houver adaptação pessoal


class TreinoFase(_Modelo):
    foco: str
    exercicios: list[ExercicioPrescrito]
    progressao: str  # uma variável de cada vez (§5)


class TreinoPorFase(_Modelo):
    fase_1: TreinoFase
    fase_2: TreinoFase
    fase_3: TreinoFase
    fase_4: TreinoFase


class MarcosForca(_Modelo):
    """Marcos de força ou resistência, escritos pela LLM (decisão de 28/10/2026)."""

    semana_4: str
    semana_8: str
    semana_12: str
    semana_16: str


class AjusteRefeicao(_Modelo):
    refeicao: Refeicao
    sugestao: str


class OrientacaoAlimentar(_Modelo):
    resumo: str
    ajustes_refeicoes: list[AjusteRefeicao]
    bebidas_e_alcool: str
    prioridades_por_fase: list[str]  # quatro entradas, uma por fase (Vol. 3)


class Habito(_Modelo):
    titulo: str
    descricao: str


class PlanoGerado(_Modelo):
    """Schema da resposta JSON do gerador."""

    resumo: str
    marcos_forca: MarcosForca
    semana_tipo: list[SessaoDia]
    treino: TreinoPorFase
    alimentacao: OrientacaoAlimentar
    hidratacao_dicas: list[str]
    habitos: list[Habito]
    indicadores_acompanhamento: list[str]
    notas_personalizadas: list[str]


# ---------------------------------------------------------------- Plano final


class MarcoPlano(_Modelo):
    """Marco no fim de cada fase: números da Estrategia, força da LLM."""

    semana: int
    fase: str
    peso_indicativo_kg: float
    cintura: str
    forca_resistencia: str


class HidratacaoPlano(_Modelo):
    valores: Hidratacao  # da Estrategia; sem ml com doença renal
    dicas: list[str]


class Plano(_Modelo):
    """Plano final: o que a interface mostra e a verificação confirma."""

    versao_prompt: str
    resumo: str
    marcos: tuple[MarcoPlano, ...]
    semana_tipo: list[SessaoDia]
    treino: TreinoPorFase
    alimentacao: OrientacaoAlimentar
    proteina: Proteina  # da Estrategia; sem valores com doença renal
    hidratacao: HidratacaoPlano
    habitos: list[Habito]
    indicadores_acompanhamento: list[str]
    notas_personalizadas: list[str]
    avisos: tuple[str, ...]  # textos fixos (§7) e condicionais, inseridos pelo código
