"""Modelo da estratégia: tudo o que o motor decide antes da LLM (REGRAS_DOMINIO §1 a §5).

O gerador recebe a Estrategia já calculada; a LLM nunca recalcula estes valores.
"""

from pydantic import BaseModel, ConfigDict

from vigoria.modelos.questionario import Equipamento, Intensidade
from vigoria.modelos.zonas import Zona
from vigoria.regras.calculos import (
    AvaliacaoGanhoMuscular,
    AvaliacaoPerdaPeso,
    ClasseImc,
    Hidratacao,
    Proteina,
)
from vigoria.regras.elegibilidade import Modo
from vigoria.regras.intensidade import Limitador


class _Imutavel(BaseModel):
    model_config = ConfigDict(frozen=True)


class Indicadores(_Imutavel):
    """Valores calculados em regras/ (§2)."""

    imc: float
    classe_imc: ClasseImc
    cintura_cm: float
    limiar_cintura_cm: int
    cintura_de_risco: bool
    peso_alvo_usado_kg: float  # limitado a IMC 18,5 se o pedido ficasse abaixo
    hidratacao: Hidratacao
    proteina: Proteina
    perda_peso: AvaliacaoPerdaPeso
    ganho_muscular: AvaliacaoGanhoMuscular


class Restricoes(_Imutavel):
    """Restrições de exercício (§1, §1.1 e §6.3)."""

    sem_impacto: bool = True  # no MVP, sempre (§6.3)
    sem_intervalos: bool = False
    sem_flexao_tronco_com_carga: bool = False  # osteoporose: bird-dog em vez de crunch
    equilibrio_com_apoio: bool = False
    # Regra completa (§6.6): dor articular persistente e limitação importante.
    zonas_regressao: tuple[Zona, ...] = ()
    # Regra ligeira (§6.6): limitação ligeira numa zona sem a regra completa.
    zonas_regressao_ligeira: tuple[Zona, ...] = ()
    regressao_geral: bool = False  # dor articular em «outra» articulação
    # Condições e zonas escolhidas: excluem os exercícios que as tenham em contraindicações.
    contraindicacoes: tuple[str, ...] = ()
    equipamento: tuple[Equipamento, ...] = ()  # declarado no questionário (passo 3)


class Marco(_Imutavel):
    """Marco no fim de cada fase. Os de força ficam para a LLM (decisão de 28/10/2026)."""

    semana: int
    fase: str
    peso_indicativo_kg: float
    cintura: str  # sem número: «medir e comparar»


class Estrategia(_Imutavel):
    """Saída dos passos de acolhimento e estratégia; entrada do gerador."""

    pode_gerar_plano: bool
    modo: Modo
    motivos: tuple[str, ...]  # porque não é elegível ou porque está em modo prudente

    # Os campos seguintes ficam vazios quando não pode gerar plano.
    intensidade_pedida: Intensidade
    intensidade_efetiva: Intensidade | None = None
    intensidade_limitada_por: tuple[Limitador, ...] = ()
    explicacao_intensidade: str | None = None
    sessoes_curtas: bool = False  # 15 ou 20 min/dia: só o essencial + caminhada diária
    caminhada_diaria_extra: bool = False  # 1 ou 2 dias/semana

    indicadores: Indicadores | None = None
    modulo_gordura_visceral: bool = False
    usar_frequencia_cardiaca: bool = False  # falso ⇒ esforço percebido e teste da fala
    restricoes: Restricoes = Restricoes()
    avisos: tuple[str, ...] = ()  # obrigatórios (§7) primeiro, depois os condicionais
    marcos: tuple[Marco, ...] = ()
