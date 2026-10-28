"""Textos visíveis ao utilizador produzidos pelas regras (REGRAS_DOMINIO §1, §1.1 e §2).

Ficam todos aqui até passarem para conteudo/avisos.yaml, na Fase 3.
"""

from vigoria.modelos.questionario import Limitacao

# Não elegível (§1)
MENOR_IDADE = "A Vigoria destina-se a maiores de 18 anos."
GRAVIDEZ = (
    "A Vigoria não é recomendável para situações de gravidez. "
    "Fale com o seu médico ou obstetra sobre a atividade física mais adequada nesta fase."
)

# Motivos de modo prudente (§1 e §1.1)
IMC_35_OU_MAIS = "IMC de {imc} (igual ou superior a 35)."
HIPERTENSAO_NAO_CONTROLADA = "Hipertensão não controlada."
DIABETES_CONTROLADA = "Diabetes controlada."
DIABETES_NAO_CONTROLADA = "Diabetes não controlada."
DOENCA_CARDIOVASCULAR = "Doença cardiovascular."
DOENCA_RESPIRATORIA = "Doença respiratória."
DOENCA_RENAL = "Doença renal."
OSTEOPOROSE_COM_RISCO = (
    "Osteoporose com fratura anterior por fragilidade ou risco elevado indicado pelo médico."
)
OSTEOPOROSE_RISCO_DESCONHECIDO = "Osteoporose, sem saber se há fratura anterior ou risco elevado."
DII_NAO_CONTROLADA = "Doença inflamatória intestinal em crise ou não controlada."
DOR_ARTICULAR_PERSISTENTE = "Dor articular persistente."
PROTESE_OU_CIRURGIA_RECENTE = "Prótese articular ou cirurgia recente."
CONDICAO_OUTRA = "Outra condição de saúde indicada."
LIMITACAO_IMPORTANTE = "Limitação importante {zona}."
LIMITACAO_OUTRA = "Outra limitação física indicada."

ZONAS_LIMITACAO = {
    Limitacao.JOELHOS: "nos joelhos",
    Limitacao.ANCAS: "nas ancas",
    Limitacao.OMBROS: "nos ombros",
    Limitacao.COLUNA: "na coluna",
    Limitacao.EQUILIBRIO: "no equilíbrio",
}

# Notas dos cálculos (§2)
HIDRATACAO_DOENCA_RENAL = "A quantidade de líquidos deve ser definida pelo seu médico."
HIDRATACAO_DOENCA_CARDIOVASCULAR = (
    "Se tiver indicação médica para limitar líquidos (por exemplo, insuficiência cardíaca), "
    "siga essa indicação."
)
PROTEINA_DOENCA_RENAL = (
    "A quantidade de proteína deve ser definida pelo seu médico ou nutricionista."
)
PROTEINA_ATE_1_5 = (
    "Em algumas situações, o médico ou nutricionista pode indicar até 1,5 g/kg; "
    "não aumente sem essa indicação."
)
