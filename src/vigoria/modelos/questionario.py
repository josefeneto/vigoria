"""Modelo do questionário, segundo docs/dominio/QUESTIONARIO.md.

Valida tipos, intervalos e coerência entre campos. Não toma decisões de domínio
(modo prudente, gravidez, intensidade efetiva): isso cabe a regras/ e motor/.
Email e telemóvel não pertencem a este modelo (ficam no Utilizador).
"""

from enum import StrEnum
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

TextoCurto = Annotated[str, Field(max_length=200)]
TextoRefeicao = Annotated[str, Field(max_length=150)]


class Sexo(StrEnum):
    MASCULINO = "masculino"
    FEMININO = "feminino"


class AtividadeAtual(StrEnum):
    SEDENTARIO = "sedentario"
    LIGEIRO = "ligeiro"
    MODERADO = "moderado"
    ATIVO = "ativo"


class Condicao(StrEnum):
    HIPERTENSAO = "hipertensao"
    DIABETES = "diabetes"
    DOENCA_CARDIOVASCULAR = "doenca_cardiovascular"
    DOENCA_RESPIRATORIA = "doenca_respiratoria"
    DOENCA_RENAL = "doenca_renal"
    OSTEOPOROSE = "osteoporose"
    DOENCA_INFLAMATORIA_INTESTINAL = "doenca_inflamatoria_intestinal"
    DOR_ARTICULAR_PERSISTENTE = "dor_articular_persistente"
    PROTESE_OU_CIRURGIA_RECENTE = "protese_ou_cirurgia_recente"
    GRAVIDEZ = "gravidez"
    NENHUMA = "nenhuma"
    OUTRA = "outra"


# Condições para as quais se pergunta «Está controlada com o tratamento atual?»
CONDICOES_COM_CONTROLO = frozenset(
    {Condicao.HIPERTENSAO, Condicao.DIABETES, Condicao.DOENCA_INFLAMATORIA_INTESTINAL}
)


class SimNaoNaoSei(StrEnum):
    SIM = "sim"
    NAO = "nao"
    NAO_SEI = "nao_sei"


class Limitacao(StrEnum):
    JOELHOS = "joelhos"
    ANCAS = "ancas"
    OMBROS = "ombros"
    COLUNA = "coluna"
    EQUILIBRIO = "equilibrio"
    OUTRA = "outra"
    NENHUMA = "nenhuma"


class Gravidade(StrEnum):
    LIGEIRA = "ligeira"
    IMPORTANTE = "importante"


class Equipamento(StrEnum):
    NENHUM = "nenhum"
    BANDAS_ELASTICAS = "bandas_elasticas"
    HALTERES = "halteres"
    STEP = "step"
    ELIPTICA = "eliptica"
    PASSADEIRA = "passadeira"
    CADEIRA_FIRME = "cadeira_firme"
    OUTRO = "outro"


class Preferencia(StrEnum):
    CAMINHADA = "caminhada"
    TAI_CHI = "tai_chi"
    DANCA = "danca"
    FORCA = "forca"
    NATACAO = "natacao"
    OUTRO = "outro"


class RestricaoAlimentar(StrEnum):
    VEGETARIANO = "vegetariano"
    SEM_LACTOSE = "sem_lactose"
    SEM_GLUTEN = "sem_gluten"
    OUTRA = "outra"


class AguaLitros(StrEnum):
    MENOS_0_5 = "<0,5"
    DE_0_5_A_1 = "0,5-1"
    DE_1_A_1_5 = "1-1,5"
    DE_1_5_A_2 = "1,5-2"
    MAIS_2 = ">2"


class BebidasAcucaradas(StrEnum):
    NENHUMA = "nenhuma"
    MENOS_0_33 = "<0,33"
    DE_0_33_A_1 = "0,33-1"
    MAIS_1 = ">1"


class PaoPorDia(StrEnum):
    NENHUM = "nenhum"
    UM = "1"
    DOIS = "2"
    TRES = "3"
    QUATRO_OU_MAIS = "4+"


class Intensidade(StrEnum):
    LIGEIRA = "ligeira"
    MEDIA = "media"
    ALTA = "alta"


class FrequenciaRegisto(StrEnum):
    SEMANAL = "semanal"
    A_CADA_4_SEMANAS = "a_cada_4_semanas"


class Refeicoes(BaseModel):
    """O que come em cada refeição. Texto vazio = não faz essa refeição."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pequeno_almoco: TextoRefeicao = ""
    almoco: TextoRefeicao = ""
    lanche: TextoRefeicao = ""
    jantar: TextoRefeicao = ""
    ceia: TextoRefeicao = ""


class Questionario(BaseModel):
    """Respostas ao questionário (passos 0 a 6)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # Passo 0 — consentimento
    aceita_termos: Literal[True]
    consentimento_saude: Literal[True]
    confirma_maior_idade: Literal[True]

    # Passo 1 — sobre si
    sexo: Sexo
    idade: int = Field(ge=18, le=100)
    altura_cm: int = Field(ge=120, le=220)
    peso_kg: float = Field(ge=35, le=250)
    sono_horas: float = Field(ge=3, le=12, multiple_of=0.5)
    cintura_cm: float = Field(ge=50, le=200)
    atividade_atual: AtividadeAtual

    # Passo 2a — saúde
    condicoes: list[Condicao] = Field(min_length=1)
    condicoes_controladas: dict[Condicao, bool] = {}
    osteoporose_risco: SimNaoNaoSei | None = None
    condicoes_outras: TextoCurto = ""
    medicacao_afeta_fc: SimNaoNaoSei
    medicacao_notas: TextoCurto = ""

    # Passo 2b — limitações
    limitacoes: list[Limitacao] = Field(min_length=1)
    limitacoes_gravidade: dict[Limitacao, Gravidade] = {}
    limitacoes_outra: TextoCurto = ""

    # Passo 3 — exercício
    equipamento: list[Equipamento] = Field(min_length=1)
    halteres_kg: float | None = Field(default=None, gt=0, le=50)
    dias_semana: int = Field(ge=1, le=7)
    minutos_dia: Literal[15, 20, 30, 45, 60]
    preferencias: list[Preferencia] = Field(min_length=1)

    # Passo 4a — refeições
    refeicoes: Refeicoes
    restricoes_alimentares: list[RestricaoAlimentar] = []
    restricoes_outra: TextoCurto = ""

    # Passo 4b — bebidas e consumos
    agua_litros: AguaLitros
    bebidas_acucaradas_litros: BebidasAcucaradas
    vinho_copos_dia: int = Field(ge=0, le=10)
    espirituosas_dl_dia: float = Field(ge=0, le=5)
    pao_por_dia: PaoPorDia
    doces_por_semana: int = Field(ge=0, le=14)

    # Passo 5 — objetivos
    peso_alvo_kg: float = Field(ge=35, le=250)
    cintura_alvo_cm: float | None = Field(default=None, ge=50, le=200)
    objetivo_muscular: Literal["aumentar_forca_tonus"] | Annotated[float, Field(gt=0, le=2)]
    intensidade_pedida: Intensidade

    # Passo 6 — acompanhamento
    acompanhamento_ativo: bool = True
    frequencia_registo: FrequenciaRegisto = FrequenciaRegisto.SEMANAL
    lembretes_email: bool = True

    @model_validator(mode="before")
    @classmethod
    def _ignorar_notas(cls, dados: Any) -> Any:
        """Ignora chaves começadas por «_» (notas em ficheiros de exemplo)."""
        if isinstance(dados, dict):
            return {k: v for k, v in dados.items() if not str(k).startswith("_")}
        return dados

    @model_validator(mode="after")
    def _validar_coerencia(self) -> Self:
        _exclusivo(self.condicoes, Condicao.NENHUMA, "condicoes")
        _exclusivo(self.limitacoes, Limitacao.NENHUMA, "limitacoes")
        _exclusivo(self.equipamento, Equipamento.NENHUM, "equipamento")

        com_controlo = CONDICOES_COM_CONTROLO.intersection(self.condicoes)
        if set(self.condicoes_controladas) != com_controlo:
            raise ValueError(
                "condicoes_controladas tem de responder exatamente às condições escolhidas "
                "entre hipertensão, diabetes e doença inflamatória intestinal"
            )

        _so_com(self.osteoporose_risco, Condicao.OSTEOPOROSE in self.condicoes, "osteoporose_risco")
        _so_com(self.condicoes_outras, Condicao.OUTRA in self.condicoes, "condicoes_outras")
        _so_com(self.limitacoes_outra, Limitacao.OUTRA in self.limitacoes, "limitacoes_outra")
        _so_com(self.halteres_kg, Equipamento.HALTERES in self.equipamento, "halteres_kg")
        _so_com(
            self.restricoes_outra,
            RestricaoAlimentar.OUTRA in self.restricoes_alimentares,
            "restricoes_outra",
        )

        com_gravidade = set(self.limitacoes) - {Limitacao.NENHUMA}
        if set(self.limitacoes_gravidade) != com_gravidade:
            raise ValueError("limitacoes_gravidade tem de indicar a gravidade de cada limitação")
        return self


def _exclusivo(escolhas: list[Any], nenhum: Any, campo: str) -> None:
    """«Nenhuma» não pode ser combinada com outras escolhas."""
    if nenhum in escolhas and len(escolhas) > 1:
        raise ValueError(f"{campo}: «{nenhum}» não pode ser combinado com outras escolhas")


def _so_com(valor: Any, escolhido: bool, campo: str) -> None:
    """O campo é obrigatório se a opção foi escolhida e tem de ficar vazio se não foi."""
    preenchido = valor not in (None, "")
    if escolhido and not preenchido:
        raise ValueError(f"{campo} é obrigatório para a opção escolhida")
    if preenchido and not escolhido:
        raise ValueError(
            f"{campo} só pode ser preenchido quando a opção correspondente é escolhida"
        )
