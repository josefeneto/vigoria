"""Textos visíveis da interface (questionário, plano e mensagens de erro).

Os textos de segurança, os avisos e os rótulos do plano não estão aqui: vêm de
conteudo/avisos.yaml, através de vigoria.regras.textos e de carregar_avisos().rotulos.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from vigoria.dados.repositorios import Recusa
from vigoria.interface.erros import TipoErroUtilizador
from vigoria.interface.passos import CodigoErro, ErroCampo
from vigoria.regras.calculos import ClasseImc
from vigoria.regras.elegibilidade import Modo

# ---------------------------------------------------------------- Geral

MARCA = "Vigoria"
# Espaço não separável antes do travessão: «— para…» nunca começa uma linha.
PROMESSA = "O seu plano, à sua medida\u00a0— para ganhar força e energia, sem sair de casa."
DEMO_AVISO = (
    "Versão de demonstração — não introduza dados reais de saúde. "
    "Os dados são processados em servidores fora da UE."
)
ANTERIOR = "Anterior"
SEGUINTE = "Seguinte"
ALTERAR = "Alterar"
VOLTAR_INICIO = "Voltar ao início"
COMECAR = "Começar o questionário"
VER_PLANO = "Ver o meu plano"
PREENCHER_PERSONA = "Preencher com a persona de teste"
PREENCHER_PERSONA_AJUDA = "Só em ambiente local: preenche as respostas e salta para a revisão."
SEM_RESPOSTA = "—"
SIM, NAO, NAO_SEI = "Sim", "Não", "Não sei"

PAGINAS = {
    "inicio": "Início",
    "questionario": "Questionário",
    "plano": "O meu plano",
    "conta": "A minha conta",
    "sair": "Terminar sessão",
    "privacidade": "Privacidade",
}

# ---------------------------------------------------------------- Conta e sessão

ENTRAR = "Entrar ou criar conta"
BD_INDISPONIVEL = (
    "Não foi possível ligar à base de dados. Tente de novo dentro de momentos: "
    "os seus dados estão guardados."
)
LOGIN_POR_CONFIGURAR = (
    "A entrada com conta ainda não está configurada neste servidor (falta a secção [auth] do "
    "secrets.toml)."
)
RECUSAS = {
    Recusa.EMAIL_POR_VERIFICAR: (
        "Confirme o seu email",
        "Enviámos-lhe um email para confirmar o endereço. Abra-o, carregue na ligação e "
        "depois entre de novo.",
        "Já confirmei: entrar de novo",
    ),
    Recusa.EMAIL_NOUTRO_METODO: (
        "Esta conta já existe",
        "Já existe uma conta com este email. Entre com o método que usou da primeira vez.",
        "Entrar com outro método",
    ),
}
SO_POR_CONVITE = (
    "A Vigoria está em fase de testes, apenas por convite. Se quiser participar, contacte-nos."
)
UTILIZADOR_LOCAL = "Sessão de desenvolvimento (utilizador fictício, sem Auth0)."
# Muda sempre que o texto do passo 0 (ROTULOS_CONSENTIMENTO) ou a privacidade mudarem.
VERSAO_CONSENTIMENTO = "2026-11-03"
ERRO_GUARDAR = (
    "O plano foi preparado, mas não conseguimos guardá-lo na sua conta. Pode vê-lo agora; "
    "se fechar a janela, perde-se. Tente gerá-lo de novo mais tarde."
)

CONTA_TITULO = "A minha conta"
CONTA_EMAIL = "Entrou como **{email}**."
CONTA_PLANOS = "Os meus planos"
CONTA_SEM_PLANOS = "Ainda não tem planos guardados."
CONTA_PLANO_DE = "Plano de {data}"
CONTA_ABRIR = "Abrir"
CONTA_ATUAL = "Aberto"
CONTA_APAGAR_PLANO = "Apagar"
CONTA_APAGAR_PLANO_PERGUNTA = (
    "Apagar o plano de {data}? Não é possível recuperá-lo. As suas respostas ficam guardadas."
)
CONTA_APAGAR_PLANO_SIM = "Sim, apagar o plano"
CONTA_APAGAR_PLANO_NAO = "Cancelar"
CONTA_PLANO_APAGADO = "O plano foi apagado."
CONTA_EXPORTAR_TITULO = "Os meus dados"
CONTA_EXPORTAR_TEXTO = (
    "Descarregue tudo o que guardámos sobre si (conta, consentimentos, respostas e planos) "
    "num ficheiro JSON."
)
CONTA_EXPORTAR = "Descarregar os meus dados (formato técnico, JSON)"
DESCARREGAR_PDF = "Descarregar o plano (PDF)"
PDF_FICHEIRO = "vigoria_plano_{data}.pdf"
CONTA_EXPORTAR_FICHEIRO = "vigoria_os_meus_dados.json"
CONTA_APAGAR_TITULO = "Apagar a conta"
CONTA_APAGAR_TEXTO = (
    "Apaga a sua conta e todos os dados: respostas, planos e registos. Não é possível "
    "recuperá-los. A conta de entrada (Google ou email e palavra-passe) também é apagada."
)
CONTA_APAGAR_CONFIRMA = "Compreendo que apagar a conta é definitivo."
CONTA_APAGAR_PALAVRA = "APAGAR"
CONTA_APAGAR_ESCREVA = "Para confirmar, escreva APAGAR"
CONTA_APAGAR = "Apagar a conta e os dados"
CONTA_APAGADA = "A sua conta e os seus dados foram apagados."
CONTA_APAGADA_AUTH0_PENDENTE = (
    "Os seus dados foram apagados. A conta de entrada será removida em breve."
)
CONTA_APAGADA_SAIR = "Sair"


def data_hora(momento: datetime) -> str:
    """«03/11/2026, 14:05», na hora de Portugal continental (a base guarda em UTC)."""
    if momento.tzinfo is None:  # o SQLite devolve sem fuso
        momento = momento.replace(tzinfo=UTC)
    return momento.astimezone(ZoneInfo("Europe/Lisbon")).strftime("%d/%m/%Y, %H:%M")


INICIO_TEXTO = (
    "Um plano pessoal de 16 semanas para cuidar da sua saúde e vitalidade, com exercícios "
    "para fazer em casa e hábitos simples para o dia a dia."
)
COMO_FUNCIONA = (
    (
        "lista",
        "1. Responda ao questionário",
        "Cerca de 10 minutos sobre si, a sua saúde e a sua rotina.",
    ),
    (
        "intensidade",
        "2. Veja as nossas decisões",
        "Explicamos o que adaptámos e porquê, antes de preparar o plano.",
    ),
    (
        "calendario",
        "3. Receba o seu plano",
        "16 semanas em 4 fases, com treino em casa, alimentação e hábitos.",
    ),
)
FINAL_TITULO = "Pronto para começar?"
VIDEO_DESCRICOES = (  # pela ordem de componentes.VIDEOS_TOPO
    "Homem de cabelo grisalho a levantar halteres acima da cabeça, devagar e com controlo.",
    "Mulher a fazer agachamentos com uma banda elástica à volta das pernas, numa varanda, "
    "devagar e com controlo.",
)
VIDEO_PAUSAR = "Pausar o vídeo"
VIDEO_REPRODUZIR = "Ver o vídeo"
INICIO_COMO_TITULO = "Como funciona"
BENEFICIOS = (
    (
        "medida",
        "Feito à sua medida",
        "O plano parte das suas respostas: idade, saúde, rotina e objetivos. "
        "Nada de modelos iguais para todos.",
    ),
    (
        "casa",
        "Em casa, ao seu ritmo",
        "16 semanas em 4 fases, com exercícios para fazer em casa, com ou sem equipamento.",
    ),
    (
        "pessoa45",
        "Pensado para os 45+",
        "Respeita as articulações, o equilíbrio e o seu historial de saúde, com avisos claros "
        "sempre que é preciso.",
    ),
)
ALT_FOTO_INICIO = "Pessoa deitada num tapete, em casa, a levantar halteres com os dois braços."
ALT_FOTO_PLANO = "Pessoa a fazer um alongamento de pernas no chão de uma sala de estar."
ALT_FOTO_FIM = (
    "Pessoa ao ar livre, à sombra de uma árvore, a beber água com um tapete debaixo do braço."
)
INICIO_SESSAO = (
    "Para guardar o seu plano, entre com a conta Google ou com email e palavra-passe. "
    "Pode descarregar ou apagar os seus dados a qualquer momento."
)

PASSO_DE = "Passo {n} de {total}"

TITULOS = {
    "0": "Boas-vindas",
    "1": "Sobre si",
    "2a": "A sua saúde",
    "2b": "Limitações",
    "3": "Exercício",
    "4a": "Refeições",
    "4b": "Bebidas e consumos",
    "5": "Objetivos",
    "6": "Acompanhamento",
    "7": "Revisão",
}

ERROS_NO_PASSO = "Há respostas por completar neste passo. Veja as indicações em cada campo."

# ---------------------------------------------------------------- Passo 0

BOAS_VINDAS = (
    "Antes de começar, precisamos do seu consentimento. As perguntas seguintes incluem dados "
    "de saúde, que só usamos para preparar e acompanhar o seu plano."
)
ROTULOS_CONSENTIMENTO = {
    "aceita_termos": "Li e aceito os termos de utilização e a política de privacidade.",
    "consentimento_saude": (
        "Autorizo o tratamento dos meus dados de saúde para gerar e acompanhar o meu plano."
    ),
    "confirma_maior_idade": "Confirmo que tenho 18 anos ou mais.",
}
LER_PRIVACIDADE = "Ler a política de privacidade"
AJUDA_TEXTO_LIVRE = "Não escreva o seu nome nem contactos."
TERMOS_EM_PREPARACAO = "Os termos de utilização estão em preparação (versão de teste)."

# ---------------------------------------------------------------- Passo 1

ROTULOS = {
    "sexo": "Sexo",
    "idade": "Idade (anos)",
    "altura_cm": "Altura (cm)",
    "peso_kg": "Peso (kg)",
    "sono_horas": "Horas de sono por noite",
    "cintura_cm": "Perímetro da cintura (cm)",
    "atividade_atual": "Nível de atividade física atual",
    "condicoes": "Tem alguma destas condições de saúde?",
    "osteoporose_risco": (
        "Já teve alguma fratura por fragilidade, ou o seu médico indicou risco elevado de fratura?"
    ),
    "dor_articular_zonas": "Em que articulações?",
    "dor_articular_outra": "Que outra articulação?",
    "condicoes_outras": "Que outra condição?",
    "medicacao_afeta_fc": (
        "Toma medicação para o coração ou para a tensão que baixe o ritmo cardíaco "
        "(por exemplo, betabloqueantes)?"
    ),
    "medicacao_notas": "Notas sobre a medicação (opcional)",
    "limitacoes": "Tem alguma limitação física?",
    "limitacoes_outra": "Que outra limitação?",
    "equipamento": "Que equipamento tem em casa?",
    "halteres_kg": "Peso de cada haltere (kg)",
    "dias_semana": "Quantos dias por semana pode treinar?",
    "minutos_dia": "Quantos minutos por dia?",
    "preferencias": "De que atividades gosta?",
    "refeicoes": "Refeições",
    "restricoes_alimentares": "Restrições alimentares (opcional)",
    "restricoes_outra": "Que outra restrição?",
    "agua_litros": "Quanta água bebe por dia?",
    "bebidas_acucaradas_litros": "Refrigerantes e sumos açucarados por dia",
    "vinho_copos_dia": "Copos de vinho por dia",
    "espirituosas_dl_dia": "Bebidas espirituosas por dia (um cálice tem cerca de 0,4 dl)",
    "pao_por_dia": "Pão por dia (fatias ou papos-secos)",
    "doces_por_semana": "Doces por semana",
    "peso_alvo_kg": "Peso que gostaria de atingir (kg)",
    "cintura_alvo_cm": "Cintura que gostaria de atingir (cm, opcional)",
    "objetivo_muscular": "Objetivo de massa muscular",
    "intensidade_pedida": "Que intensidade prefere?",
    "acompanhamento_ativo": "Quero acompanhar o meu progresso (recomendado)",
    "frequencia_registo": "Com que frequência quer registar o peso e a cintura?",
    "lembretes_email": "Enviar-me um lembrete por email quando faltar um registo",
}

# Rótulos curtos no resumo do passo 7 (as perguntas não ficam bem antes de «:»).
ROTULOS_RESUMO = {
    "condicoes": "Condições de saúde",
    "osteoporose_risco": "Fratura por fragilidade ou risco elevado",
    "medicacao_afeta_fc": "Medicação que baixa o ritmo cardíaco",
    "limitacoes": "Limitações físicas",
    "equipamento": "Equipamento",
    "dias_semana": "Dias de treino por semana",
    "minutos_dia": "Minutos por dia",
    "preferencias": "Atividades preferidas",
    "agua_litros": "Água por dia",
    "espirituosas_dl_dia": "Bebidas espirituosas por dia",
    "intensidade_pedida": "Intensidade",
    "acompanhamento_ativo": "Acompanhar o progresso",
    "frequencia_registo": "Frequência dos registos",
    "lembretes_email": "Lembretes por email",
}

AJUDA_CINTURA = (
    "Como medir: ao nível do umbigo, depois de expirar, com a fita bem assente mas sem apertar."
)

SEXO = {"masculino": "Masculino", "feminino": "Feminino"}
ATIVIDADE = {
    "sedentario": "Sedentário",
    "ligeiro": "Ligeiro",
    "moderado": "Moderado",
    "ativo": "Ativo",
}
ATIVIDADE_DESCRICAO = {
    "sedentario": "Passa a maior parte do dia sentado e quase não caminha.",
    "ligeiro": "Caminha um pouco todos os dias ou faz tarefas leves.",
    "moderado": "Faz exercício ou caminhadas rápidas 2 a 3 vezes por semana.",
    "ativo": "Faz exercício 4 ou mais vezes por semana.",
}

IMC_TITULO = "O seu IMC é {imc}"
IMC_CONTEXTO = {
    ClasseImc.BAIXO_PESO: (
        "Está abaixo do intervalo de referência. O plano dá prioridade a ganhar força, "
        "sem perder peso."
    ),
    ClasseImc.NORMAL: "Está dentro do intervalo de referência (18,5 a 24,9).",
    ClasseImc.EXCESSO_PESO: (
        "Está um pouco acima do intervalo de referência. É um bom ponto de partida para "
        "um plano gradual."
    ),
    ClasseImc.OBESIDADE_I: (
        "Está acima do intervalo de referência. Com um ritmo adequado à sua idade, há muito "
        "a ganhar em saúde e disposição."
    ),
    ClasseImc.FORA_DA_VERSAO_BASE: (
        "Está bem acima do intervalo de referência. O plano será mais prudente, para começar "
        "com segurança."
    ),
}
IMC_NOTA = (
    "IMC (índice de massa corporal) — o peso a dividir pelo quadrado da altura. É só uma "
    "referência: não distingue músculo de gordura."
)

# ---------------------------------------------------------------- Passo 2a e 2b

CONDICOES = {
    "hipertensao": "Hipertensão (tensão alta)",
    "diabetes": "Diabetes",
    "doenca_cardiovascular": "Doença cardiovascular",
    "doenca_respiratoria": "Doença respiratória",
    "doenca_renal": "Doença renal",
    "osteoporose": "Osteoporose",
    "doenca_inflamatoria_intestinal": "Doença inflamatória intestinal",
    "dor_articular_persistente": "Dor articular persistente",
    "protese_ou_cirurgia_recente": "Prótese articular ou cirurgia nos últimos 6 meses",
    "gravidez": "Gravidez",
    "nenhuma": "Nenhuma",
    "outra": "Outra",
}
CONTROLADA = "{condicao}: está controlada com o tratamento atual?"
CONTROLADA_RESUMO = "{condicao} controlada"
SIM_NAO_NAO_SEI = {"sim": SIM, "nao": NAO, "nao_sei": NAO_SEI}
ARTICULACOES = {
    "joelhos": "Joelhos",
    "ancas": "Ancas",
    "ombros": "Ombros",
    "coluna": "Coluna",
    "outra": "Outra",
}
LIMITACOES = {
    "joelhos": "Joelhos",
    "ancas": "Ancas",
    "ombros": "Ombros",
    "coluna": "Coluna",
    "equilibrio": "Equilíbrio",
    "outra": "Outra",
    "nenhuma": "Nenhuma",
}
GRAVIDADE_PERGUNTA = "{limitacao}: qual é o impacto no seu dia a dia?"
GRAVIDADE = {"ligeira": "Ligeira", "importante": "Importante"}
GRAVIDADE_AJUDA = (
    "Ligeira — incomoda, mas não o impede de fazer o dia a dia. "
    "Importante — impede ou limita atividades do dia a dia."
)
GRAVIDEZ_TITULO = "Questionário terminado"
GRAVIDEZ_NADA_GUARDADO = "Não guardámos nenhuma das respostas que deu."

# ---------------------------------------------------------------- Passo 3

EQUIPAMENTO = {
    "nenhum": "Nenhum",
    "bandas_elasticas": "Bandas elásticas",
    "halteres": "Halteres",
    "step": "Step",
    "eliptica": "Elíptica",
    "passadeira": "Passadeira",
    "cadeira_firme": "Cadeira firme",
    "outro": "Outro",
}
PREFERENCIAS = {
    "caminhada": "Caminhada",
    "tai_chi": "Tai Chi",
    "danca": "Dança",
    "forca": "Força",
    "natacao": "Natação",
    "outro": "Outra",
}
MINUTOS = "{n} min"

# ---------------------------------------------------------------- Passo 4a e 4b

REFEICOES_INTRO = (
    "Marque as refeições que costuma fazer. Se quiser, diga o que come habitualmente: "
    "ajuda a adaptar as sugestões."
)
FACO_REFEICAO = "Faço esta refeição"
O_QUE_COME = "O que costuma comer? (opcional)"
RESTRICOES = {
    "vegetariano": "Vegetariano",
    "sem_lactose": "Sem lactose",
    "sem_gluten": "Sem glúten",
    "outra": "Outra",
}
AGUA = {
    "<0,5": "Menos de 0,5 litros",
    "0,5-1": "0,5 a 1 litro",
    "1-1,5": "1 a 1,5 litros",
    "1,5-2": "1,5 a 2 litros",
    ">2": "Mais de 2 litros",
}
BEBIDAS_ACUCARADAS = {
    "nenhuma": "Nenhuma",
    "<0,33": "Menos de uma lata (0,33 litros)",
    "0,33-1": "Entre uma lata e 1 litro",
    ">1": "Mais de 1 litro",
}
PAO = {"nenhum": "Nenhum", "1": "1", "2": "2", "3": "3", "4+": "4 ou mais"}

# ---------------------------------------------------------------- Passo 5

PROGRAMA_16_SEMANAS = (
    "O programa tem sempre **16 semanas**, em 4 fases de 4 semanas cada, seguidas de uma fase "
    "de manutenção."
)
OBJETIVO_MUSCULAR = {
    "aumentar_forca_tonus": "Aumentar força e tónus",
    "kg": "Ganhar um valor em kg",
}
OBJETIVO_MUSCULAR_KG = "Quantos kg de massa muscular? (até 2 kg)"
NOTA_GANHO_MUSCULAR = (
    "O músculo ganha-se devagar: uma referência realista é até 0,5 kg por cada 4 semanas."
)
INTENSIDADE = {"ligeira": "Ligeira", "media": "Média", "alta": "Alta"}
INTENSIDADE_DESCRICAO = {
    "ligeira": (
        "Introdução gradual. Pão ao pequeno-almoço e numa refeição adicional; doces até 2 vezes "
        "por semana; álcool reduzido em cerca de um terço; 3 sessões de exercício por semana."
    ),
    "media": (
        "Ajuste consistente. Pão só ao pequeno-almoço; doces até 1 vez por semana; álcool "
        "reduzido para metade; sem refrigerantes; 4 a 5 sessões de exercício por semana."
    ),
    "alta": (
        "Mudança estrita. Pão eliminado ou mínimo ao pequeno-almoço; sem doces; só água, sem "
        "álcool nem refrigerantes; exercício diário."
    ),
}
INTENSIDADE_NOTA = (
    "Se as suas respostas de saúde ou o tempo disponível o pedirem, o plano pode usar uma "
    "intensidade mais baixa. Mostramos-lhe sempre porquê."
)

# ---------------------------------------------------------------- Passo 6

FREQUENCIA = {"semanal": "Semanal", "a_cada_4_semanas": "A cada 4 semanas"}
ACOMPANHAMENTO_NOTA = "Pode mudar estas opções mais tarde."

# ---------------------------------------------------------------- Passo 7

REVISAO_INTRO = "Confirme as suas respostas. Pode alterar qualquer secção antes de continuar."
DECISOES_TITULO = "O que decidimos a partir das suas respostas"
DECISOES_INTRO = (
    "Antes de preparar o plano, mostramos-lhe as decisões, para nada aparecer de surpresa."
)
MODO = {
    Modo.BASE: "Versão-base do programa.",
    Modo.PRUDENTE: (
        "Modo prudente: o plano começa com mais cuidado, por causa de algumas respostas de saúde."
    ),
    Modo.NAO_ELEGIVEL: "Não é possível preparar um plano com estas respostas.",
}
MOTIVOS_PRUDENTE = "Porquê:"
INTENSIDADE_DECISAO = "Intensidade do plano: **{efetiva}** (pediu {pedida})."
INTENSIDADE_IGUAL = "Intensidade do plano: **{efetiva}**, como pediu."
OBJETIVO_REALISTA = "Objetivo de peso: {alvo} kg. É realista em 16 semanas, ao ritmo recomendado."
OBJETIVO_AJUSTADO = (
    "Objetivo de peso: o plano aponta para cerca de **{alvo_16} kg à semana 16**. "
    "Os {alvo} kg que indicou são alcançáveis por volta da semana {semana}, ao mesmo ritmo seguro."
)
OBJETIVO_SEM_PERDA = "Objetivo de peso: manter o peso e ganhar força."
MODULO_VISCERAL = (
    "Inclui o módulo de gordura visceral — a gordura que se acumula à volta dos órgãos "
    "abdominais —, porque a cintura está acima do valor de referência."
)
ESFORCO_PERCEBIDO = (
    "O esforço é medido pelo que sente (escala de 0 a 10 e teste da fala), em vez da "
    "frequência cardíaca."
)
SESSOES_CURTAS = "Com sessões curtas, o treino concentra-se no essencial e junta caminhada diária."
CAMINHADA_EXTRA = "Com poucos dias de treino, o plano junta uma caminhada diária fora das sessões."
AVISOS_TITULO = "Avisos que vão constar do plano"
GERAR = "Gerar o meu plano"
A_PREPARAR = "A preparar o seu plano… pode demorar até 2 minutos."
NAO_PODE_GERAR = "Não é possível preparar um plano com estas respostas."

RESUMO_SECOES = {
    "1": ("1", "2a", "2b"),
    "3": ("3",),
    "4a": ("4a", "4b"),
    "5": ("5", "6"),
}
TITULOS_RESUMO = {
    "1": "Sobre si e saúde",
    "3": "Exercício",
    "4a": "Alimentação",
    "5": "Objetivos e acompanhamento",
}

ERROS_GERACAO = {
    TipoErroUtilizador.QUOTA_DIARIA: (
        "O serviço que prepara os planos atingiu o limite de utilização de hoje. As suas "
        "respostas continuam aqui: tente de novo amanhã."
    ),
    TipoErroUtilizador.MUITOS_PEDIDOS: (
        "O serviço que prepara os planos está com muitos pedidos neste momento. Aguarde "
        "alguns minutos e tente de novo; as suas respostas continuam aqui."
    ),
    TipoErroUtilizador.INDISPONIVEL: (
        "O serviço que prepara os planos não está disponível neste momento. Tente de novo "
        "daqui a pouco; as suas respostas continuam aqui."
    ),
    TipoErroUtilizador.RECUSADO: (
        "Preparámos o plano, mas ele não passou nas nossas verificações de segurança e não "
        "o vamos mostrar. Tente de novo; se voltar a acontecer, a falha é nossa e vamos "
        "corrigi-la."
    ),
    TipoErroUtilizador.OUTRO: (
        "Não foi possível preparar o plano por um erro inesperado. Tente de novo daqui a pouco."
    ),
}
ERRO_GERACAO_TITULO = "Não foi possível preparar o plano"
TENTAR_DE_NOVO = "Tentar de novo"

# Opções de cada campo (resumo do passo 7) e unidades dos números.
OPCOES = {
    "sexo": SEXO,
    "atividade_atual": ATIVIDADE,
    "condicoes": CONDICOES,
    "osteoporose_risco": SIM_NAO_NAO_SEI,
    "dor_articular_zonas": ARTICULACOES,
    "medicacao_afeta_fc": SIM_NAO_NAO_SEI,
    "limitacoes": LIMITACOES,
    "equipamento": EQUIPAMENTO,
    "preferencias": PREFERENCIAS,
    "restricoes_alimentares": RESTRICOES,
    "agua_litros": AGUA,
    "bebidas_acucaradas_litros": BEBIDAS_ACUCARADAS,
    "pao_por_dia": PAO,
    "intensidade_pedida": INTENSIDADE,
    "frequencia_registo": FREQUENCIA,
}
UNIDADES = {
    "idade": " anos",
    "altura_cm": " cm",
    "peso_kg": " kg",
    "sono_horas": " h",
    "cintura_cm": " cm",
    "halteres_kg": " kg",
    "minutos_dia": " min",
    "espirituosas_dl_dia": " dl",
    "peso_alvo_kg": " kg",
    "cintura_alvo_cm": " cm",
    "objetivo_muscular": " kg",
}

# ---------------------------------------------------------------- Plano

SEM_PLANO = "Ainda não tem um plano. Responda ao questionário para o preparar."
PLANO_SIMULADO = "Plano simulado (persona de teste)"
PLANO_SIMULADO_NOTA = (
    "Este plano não foi escrito pela IA: é a resposta guardada da persona de teste."
)
NUMEROS_PLANO = {
    "objetivo": "Objetivo à semana 16",
    "intensidade": "Intensidade",
    "dias": "Dias de treino por semana",
}
FASES_TITULO = "As 4 fases do programa"
CINTURA_FASES = "**{rotulo}**, no fim de cada fase: {texto}"
FASE_SEMANAS = "Fase {n} · Semanas {min} a {max}"
MINUTOS = "{n} min"
SECCAO_PLANO = "Secção do plano"
SECCOES_PLANO = {
    "resumo": ":material/summarize: Resumo",
    "treino": ":material/fitness_center: Treino",
    "alimentacao": ":material/restaurant: Alimentação",
    "habitos": ":material/self_improvement: Hábitos",
    "acompanhamento": ":material/monitoring: Acompanhamento",
}
ESCOLHER_FASE = "Fase"
ESCOLHER = "Escolha uma opção"
MINUTOS_COLUNA = "Minutos"
DETALHES_SEMANA = "Ver o que fazer em cada dia"
NOTA_SESSAO_PLANO = "Plano de {data}, guardado na sua conta."
FREQUENCIA_PLANO = {"semanal": "Registo semanal", "a_cada_4_semanas": "Registo a cada 4 semanas"}
PERGUNTAS_REVISAO = "Perguntas para cada revisão"
VOLTAR_QUESTIONARIO = "Voltar ao questionário"


# ---------------------------------------------------------------- Mensagens de validação


def mensagem_erro(erro: ErroCampo) -> str:
    """Mensagem PT-EU para um erro de validação."""
    match erro.codigo:
        case CodigoErro.OBRIGATORIO:
            return "Responda a esta pergunta para continuar."
        case CodigoErro.INTERVALO if erro.minimo is not None and erro.maximo is not None:
            return f"Indique um valor entre {_n(erro.minimo)} e {_n(erro.maximo)}."
        case CodigoErro.INTERVALO if erro.maximo is not None:
            return f"Indique um valor até {_n(erro.maximo)}."
        case CodigoErro.INTERVALO:
            return f"Indique um valor de pelo menos {_n(erro.minimo or 0)}."
        case CodigoErro.MULTIPLO:
            return "Indique as horas de meia em meia hora (por exemplo, 6,5)."
        case CodigoErro.DEMASIADO_LONGO:
            return f"Escreva no máximo {_n(erro.maximo or 0)} caracteres."
        case CodigoErro.NENHUMA_EXCLUSIVA:
            return "Se escolher «Nenhuma» (ou «Nenhum»), não marque outras opções."
        case _:
            return "Esta resposta não é válida."


def _n(valor: float) -> str:
    return f"{valor:g}".replace(".", ",")
