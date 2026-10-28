"""Textos visíveis ao utilizador produzidos pelas regras (REGRAS_DOMINIO §1 a §7).

Os textos vivem em conteudo/avisos.yaml; aqui só se expõem com os nomes usados no motor.
"""

from vigoria.conteudo.carregar import carregar_avisos, carregar_fases
from vigoria.modelos.questionario import Intensidade, Limitacao

_AVISOS = carregar_avisos()
_T = _AVISOS.textos


def numero(valor: float, casas: int = 1) -> str:
    """Número em PT-EU (vírgula decimal), sem zeros finais: 88.0 → «88», 0.38 → «0,38»."""
    texto = f"{valor:.{casas}f}".rstrip("0").rstrip(".") if casas else f"{valor:.0f}"
    return texto.replace(".", ",")


# Não elegível (§1)
MENOR_IDADE = _T["menor_idade"]
GRAVIDEZ = _T["gravidez"]

# Motivos de modo prudente (§1 e §1.1)
IMC_35_OU_MAIS = _T["imc_35_ou_mais"]
HIPERTENSAO_NAO_CONTROLADA = _T["hipertensao_nao_controlada"]
DIABETES_CONTROLADA = _T["diabetes_controlada"]
DIABETES_NAO_CONTROLADA = _T["diabetes_nao_controlada"]
DOENCA_CARDIOVASCULAR = _T["doenca_cardiovascular"]
DOENCA_RESPIRATORIA = _T["doenca_respiratoria"]
DOENCA_RENAL = _T["doenca_renal"]
OSTEOPOROSE_COM_RISCO = _T["osteoporose_com_risco"]
OSTEOPOROSE_RISCO_DESCONHECIDO = _T["osteoporose_risco_desconhecido"]
DII_NAO_CONTROLADA = _T["dii_nao_controlada"]
DOR_ARTICULAR_PERSISTENTE = _T["dor_articular_persistente"]
PROTESE_OU_CIRURGIA_RECENTE = _T["protese_ou_cirurgia_recente"]
CONDICAO_OUTRA = _T["condicao_outra"]
LIMITACAO_IMPORTANTE = _T["limitacao_importante"]
LIMITACAO_OUTRA = _T["limitacao_outra"]

ZONAS_LIMITACAO = {Limitacao(k): v for k, v in _AVISOS.rotulos.zonas_limitacao.items()}

# Notas dos cálculos (§2)
HIDRATACAO_DOENCA_RENAL = _T["hidratacao_doenca_renal"]
HIDRATACAO_DOENCA_CARDIOVASCULAR = _T["hidratacao_doenca_cardiovascular"]
PROTEINA_DOENCA_RENAL = _T["proteina_doenca_renal"]
PROTEINA_ATE_1_5 = _T["proteina_ate_1_5"]

# Intensidade (§3)
NOMES_INTENSIDADE = {Intensidade(k): v for k, v in _AVISOS.rotulos.intensidade.items()}
INTENSIDADE_REDUZIDA = _T["intensidade_reduzida"]
MOTIVO_TETO_IMC = _T["motivo_teto_imc"]
MOTIVO_TETO_PRUDENTE = _T["motivo_teto_prudente"]
MOTIVO_DISPONIBILIDADE = _T["motivo_disponibilidade"]

# Avisos obrigatórios em todos os planos (§7)
AVISO_GERAL = _T["aviso_geral"]
SINAIS_INTERROMPER = _T["sinais_interromper"]

# Avisos condicionais (§1, §1.1, §3 e §4)
ORIENTACAO_INDIVIDUALIZADA = _T["orientacao_individualizada"]
INTENSIFICACAO_VALIDACAO_MEDICA = _T["intensificacao_validacao_medica"]
FALAR_COM_MEDICO_ANTES = _T["falar_com_medico_antes"]
VALIDACAO_MEDICA_ANTES = _T["validacao_medica_antes"]
VALIDACAO_CIRURGIAO_ANTES = _T["validacao_cirurgiao_antes"]
DIABETES_HIPOGLICEMIA = _T["diabetes_hipoglicemia"]
RESPIRATORIA_TESTE_DA_FALA = _T["respiratoria_teste_da_fala"]
DII_PLANO_ALIMENTAR = _T["dii_plano_alimentar"]
DII_ADIAR_MUDANCAS = _T["dii_adiar_mudancas"]
ESFORCO_PERCEBIDO = _T["esforco_percebido"]
DISPONIBILIDADE_1_DIA = _T["disponibilidade_1_dia"]
DISPONIBILIDADE_2_DIAS = _T["disponibilidade_2_dias"]
VISCERAL_REDUCAO = _T["visceral_reducao"]
VISCERAL_INDICADOR = _T["visceral_indicador"]

# Realismo e incoerências nos objetivos (§2)
PERDA_NAO_REALISTA = _T["perda_nao_realista"]
PESO_ALVO_IMC_BAIXO = _T["peso_alvo_imc_baixo"]
CINTURA_ALVO_NAO_REDUZ = _T["cintura_alvo_nao_reduz"]
PESO_ALVO_SEM_PERDA = _T["peso_alvo_sem_perda"]

# Regressões no fim da cadeia (§6.6)
AMPLITUDE_CONFORTAVEL = _T["amplitude_confortavel"]

# Marcos (§5)
FASES = tuple(fase.nome for fase in carregar_fases())
CINTURA_MEDIR = _T["cintura_medir"]
CINTURA_MEDIR_COM_LIMIAR = _T["cintura_medir_com_limiar"]
