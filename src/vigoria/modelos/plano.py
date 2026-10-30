"""Modelos do plano (REGRAS_DOMINIO §5 a §9).

Dois níveis (Fase 4C, 30/10/2026):
- `PlanoGerado` é o que a LLM devolve (schema da saída JSON): só texto de personalização
  (resumo, marcos de força, alimentação, notas). Sem números, treino ou semana.
- `Plano` é o plano final, montado pelo código: PlanoGerado + treino e semana-tipo
  (motor/treino.py e motor/semana.py) + números da Estrategia + textos fixos dos YAML.
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


class MarcosForca(_Modelo):
    """Marcos de força ou resistência: uma frase curta por marco, ligada ao treino."""

    semana_4: str
    semana_8: str
    semana_12: str
    semana_16: str


class AjusteRefeicao(_Modelo):
    refeicao: Refeicao
    sugestao: str


class PlanoGerado(_Modelo):
    """Schema da resposta JSON do gerador (prompt v4). Contagens: verificação."""

    resumo: str  # 3 a 5 frases
    marcos_forca: MarcosForca
    ajustes_refeicoes: list[AjusteRefeicao]
    bebidas_e_alcool: str
    prioridades_alimentares: list[str]  # 4, uma por fase
    notas_personalizadas: list[str]  # no máximo 3


# ---------------------------------------------------------------- Treino e semana (motor)


class SessaoDia(_Modelo):
    """Um dia da semana-tipo (motor/semana.py)."""

    dia: DiaSemana
    atividade: str
    duracao_min: int  # 0 nos dias sem sessão
    descricao: str


class ExercicioPlano(_Modelo):
    """Exercício do treino, já resolvido pelo motor (biblioteca + fases.yaml + seleção)."""

    id: str
    nome: str
    descricao: str
    series: int | None = None  # None na mobilidade e no equilíbrio
    repeticoes: str | None = None
    descanso_s: tuple[int, int] | None = None  # (mínimo, máximo)
    em_vez_de: str | None = None  # id do exercício do programa trocado por regressão
    notas: tuple[str, ...] = ()


class EstruturaSessao(_Modelo):
    aquecimento: str
    bloco_principal: str
    cardio_finalizador: str
    retorno_calma: str


class TreinoFase(_Modelo):
    numero: int
    nome: str
    foco: str
    esforco: tuple[int, int]  # esforço percebido (mínimo, máximo), escala de 0 a 10
    forca: tuple[ExercicioPlano, ...]
    cardio_finalizador: ExercicioPlano | None
    cardio_duracao_min: tuple[int, int]
    mobilidade_equilibrio: tuple[ExercicioPlano, ...]


class Treino(_Modelo):
    estrutura_sessao: EstruturaSessao
    fases: tuple[TreinoFase, ...]


# ---------------------------------------------------------------- Plano final


class MarcoPlano(_Modelo):
    """Marco no fim de cada fase: números da Estrategia, força da LLM."""

    semana: int
    fase: str
    peso_indicativo_kg: float
    cintura: str
    forca_resistencia: str


class OrientacaoAlimentar(_Modelo):
    ajustes_refeicoes: tuple[AjusteRefeicao, ...]
    bebidas_e_alcool: str
    prioridades_por_fase: tuple[str, ...]


class HidratacaoPlano(_Modelo):
    valores: Hidratacao  # da Estrategia; sem ml com doença renal
    dicas: tuple[str, ...]  # texto fixo (alimentacao.yaml); vazio com doença renal


class Habito(_Modelo):
    titulo: str
    descricao: str


class Acompanhamento(_Modelo):
    """O que registar, conforme a frequência escolhida (REGRAS §9)."""

    frequencia: str  # «semanal» ou «a_cada_4_semanas»
    indicadores: tuple[str, ...]
    perguntas_revisao: tuple[str, ...] = ()


class Plano(_Modelo):
    """Plano final: o que a interface mostra e a verificação confirma."""

    versao_prompt: str
    provedor: str  # fornecedor que gerou o texto («gemini», «groq», «mistral»)
    resumo: str
    marcos: tuple[MarcoPlano, ...]
    semana_tipo: tuple[SessaoDia, ...]
    treino: Treino
    alimentacao: OrientacaoAlimentar
    proteina: Proteina  # da Estrategia; sem valores com doença renal
    hidratacao: HidratacaoPlano
    habitos: tuple[Habito, ...]
    acompanhamento: Acompanhamento
    notas_personalizadas: tuple[str, ...]
    avisos: tuple[str, ...]  # textos fixos (§7) e condicionais, inseridos pelo código
