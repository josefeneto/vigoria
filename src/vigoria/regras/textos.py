"""Textos visíveis ao utilizador produzidos pelas regras (REGRAS_DOMINIO §1 a §5 e §7).

Ficam todos aqui até passarem para conteudo/avisos.yaml, na Fase 3.
"""

from vigoria.modelos.questionario import Intensidade, Limitacao


def numero(valor: float, casas: int = 1) -> str:
    """Número em PT-EU (vírgula decimal), sem zeros finais: 88.0 → «88», 0.38 → «0,38»."""
    texto = f"{valor:.{casas}f}".rstrip("0").rstrip(".") if casas else f"{valor:.0f}"
    return texto.replace(".", ",")


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

# Intensidade (§3)
NOMES_INTENSIDADE = {
    Intensidade.LIGEIRA: "Ligeira",
    Intensidade.MEDIA: "Média",
    Intensidade.ALTA: "Alta",
}
INTENSIDADE_REDUZIDA = "A intensidade passa de «{pedida}» para «{efetiva}»: {motivo}."
MOTIVO_TETO_IMC = (
    "com um IMC igual ou superior a 35, o plano começa de forma mais gradual, por segurança"
)
MOTIVO_TETO_PRUDENTE = (
    "com a situação de saúde indicada, o plano segue o modo prudente, "
    "em que o máximo é a intensidade «Média»"
)
MOTIVO_DISPONIBILIDADE = (
    "com {dias} {palavra_dias} por semana e {minutos} min por dia, "
    "é a intensidade que cabe no tempo disponível"
)

# Avisos obrigatórios em todos os planos (§7)
AVISO_GERAL = (
    "Este plano é uma sugestão de apoio à decisão, preparada com recurso a inteligência "
    "artificial e a conteúdo editorial revisto. Não substitui avaliação, diagnóstico, tratamento "
    "ou acompanhamento por médico, nutricionista ou profissional de exercício. Antes de iniciar "
    "ou intensificar o plano — sobretudo com doenças crónicas, medicação regular ou idade "
    "avançada — valide-o com um profissional de saúde."
)
SINAIS_INTERROMPER = (
    "Interrompa imediatamente o exercício se sentir dor no peito, falta de ar invulgar ou "
    "desproporcionada, desmaio ou sensação de desmaio, confusão, palpitações preocupantes, "
    "tonturas ou dor articular aguda. Procure avaliação adequada."
)

# Avisos condicionais (§1, §1.1, §3 e §4)
ORIENTACAO_INDIVIDUALIZADA = (
    "Antes de iniciar, procure orientação individualizada de um profissional de saúde "
    "para adaptar este plano à sua situação."
)
INTENSIFICACAO_VALIDACAO_MEDICA = (
    "Qualquer intensificação (intervalos, ritmo vigoroso) deve ser validada antes com o seu médico."
)
FALAR_COM_MEDICO_ANTES = "Fale com o seu médico antes de iniciar o plano."
VALIDACAO_MEDICA_ANTES = "Valide o plano com o seu médico antes de iniciar."
VALIDACAO_CIRURGIAO_ANTES = "Valide o plano com o seu cirurgião ou fisioterapeuta antes de iniciar."
DIABETES_HIPOGLICEMIA = (
    "Não treine em jejum prolongado. Se usar insulina ou medicação que baixe o açúcar, "
    "tenha algo açucarado à mão durante o exercício."
)
RESPIRATORIA_TESTE_DA_FALA = (
    "No cardio, guie-se pelo teste da fala e interrompa perante falta de ar desproporcionada."
)
DII_PLANO_ALIMENTAR = (
    "As alterações alimentares (fibra, leguminosas, hortícolas crus, lacticínios) devem "
    "respeitar o plano alimentar indicado pelo seu médico ou nutricionista."
)
DII_ADIAR_MUDANCAS = "Adie as mudanças alimentares até a situação estabilizar."
ESFORCO_PERCEBIDO = (
    "A intensidade guia-se pela escala de esforço percebido (0 a 10) e pelo teste da fala, "
    "e não pela frequência cardíaca."
)
_CAMINHADA_E_MAIS_UM_DIA = (
    " O plano junta uma caminhada diária fora das sessões; logo que possa, acrescente mais um dia."
)
DISPONIBILIDADE_1_DIA = (
    "Com 1 dia por semana fica abaixo do mínimo recomendado de força (2 dias) e de "
    "atividade aeróbia regular." + _CAMINHADA_E_MAIS_UM_DIA
)
DISPONIBILIDADE_2_DIAS = (
    "Com 2 dias por semana cumpre o mínimo de força, mas fica abaixo da atividade aeróbia "
    "recomendada (150 a 300 minutos semanais)." + _CAMINHADA_E_MAIS_UM_DIA
)
VISCERAL_REDUCAO = (
    "A gordura visceral tende a reduzir-se proporcionalmente mais depressa do que a "
    "subcutânea com o mesmo plano."
)
VISCERAL_INDICADOR = (
    "O perímetro da cintura é um indicador de adiposidade central; "
    "não mede diretamente a gordura visceral."
)

# Realismo e incoerências nos objetivos (§2)
PERDA_NAO_REALISTA = (
    "Chegar aos {peso_alvo} kg em 16 semanas exigiria perder cerca de {ritmo_necessario} kg "
    "por semana, acima do máximo recomendado para a sua idade ({ritmo_maximo} kg por semana). "
    "O plano aponta para cerca de {alvo_16} kg à semana 16; os {peso_alvo} kg são alcançáveis "
    "por volta da semana {semana}."
)
PESO_ALVO_IMC_BAIXO = (
    "O peso-alvo indicado ({peso_alvo} kg) corresponderia a um IMC abaixo de 18,5 (baixo peso). "
    "O plano usa como alvo {peso_minimo} kg, que corresponde a um IMC de 18,5."
)
CINTURA_ALVO_NAO_REDUZ = (
    "A cintura-alvo indicada ({cintura_alvo} cm) é igual ou superior à atual ({cintura} cm)."
)
PESO_ALVO_SEM_PERDA = (
    "O peso-alvo é igual ou superior ao peso atual: o plano foca-se em manter o peso e "
    "ganhar força, sem objetivo de perda."
)

# Regressões no fim da cadeia (§6.6)
AMPLITUDE_CONFORTAVEL = "Amplitude confortável, sem dor."

# Marcos (§5)
FASES = ("Adaptação", "Construção", "Consolidação", "Integração")
CINTURA_MEDIR = "Medir e comparar com a medição inicial."
CINTURA_MEDIR_COM_LIMIAR = (
    "Medir e comparar com a medição inicial; referência: limiar de risco de {limiar} cm."
)
