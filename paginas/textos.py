"""Textos visíveis da interface (questionário, plano e mensagens de erro).

Os textos de segurança, os avisos e os rótulos do plano não estão aqui: vêm de
conteudo/avisos.yaml, através de vigoria.regras.textos e de carregar_avisos().rotulos.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from vigoria.dados.repositorios import Recusa
from vigoria.interface.erros import TipoErroUtilizador
from vigoria.interface.passos import MINUTOS_QUESTIONARIO, CodigoErro, ErroCampo
from vigoria.modelos.registo import Comparacao
from vigoria.notificacoes.lembrete import textos_cancelar
from vigoria.regras.calculos import ClasseImc
from vigoria.regras.elegibilidade import Modo

# ---------------------------------------------------------------- Geral

MARCA = "Vigoria"
CONTACTO = "geral@vigoria.pt"  # rodapé e mensagens sem menu (convite, base de dados)
# Espaço não separável antes do travessão: «— para…» nunca começa uma linha.
PROMESSA = (
    "O seu plano, à sua medida\u00a0— para ganhar e manter força e energia, sem sair de casa."
)
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
    "progresso": "O meu progresso",
    "conta": "A minha conta",
    "sair": "Terminar sessão",
    "privacidade": "Privacidade",
    "ajuda": "Ajuda",
    "cancelar_lembretes": "Lembretes por email",
}

# Ajuda (Fase 8B): as perguntas e respostas estão em src/vigoria/conteudo/ajuda.yaml.
AJUDA_TITULO = "Ajuda"
AJUDA_INTRO = (
    "Respostas curtas sobre como a Vigoria funciona. Se não encontrar o que procura, escreva-nos."
)
COMO_FUNCIONA_LIGACAO = "Como funciona?"
SECCAO_CONTA = "Conta"  # grupo do menu com «A minha conta» e «Terminar sessão»
# Navegação (Fase 8D): rótulos curtos na barra; os títulos das páginas (separador) não mudam.
NAV = {
    "inicio": "Início",
    "plano": "Plano",
    "progresso": "Progresso",
    "ajuda": "Ajuda",
    "conta": "Conta",
}
NAV_TITULO = "Navegação principal"
ENTRAR_CURTO = "Entrar"

# ---------------------------------------------------------------- Conta e sessão

ENTRAR = "Entrar ou criar conta"
BD_INDISPONIVEL = (
    "Não foi possível ligar à base de dados. Tente de novo dentro de momentos: "
    f"os seus dados estão guardados. Se o problema continuar, escreva para {CONTACTO}."
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
    "A Vigoria está em fase de testes, apenas por convite. Se quiser participar, escreva para "
    f"{CONTACTO}."
)
UTILIZADOR_LOCAL = "Sessão de desenvolvimento (utilizador fictício, sem Auth0)."
# Muda sempre que o texto do passo 0 (ROTULOS_CONSENTIMENTO) ou a privacidade mudarem.
VERSAO_CONSENTIMENTO = "2026-11-12"
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
    "Apagar o plano de {data} e os registos de progresso dele? Não é possível recuperá-los. "
    "As suas respostas ficam guardadas."
)
CONTA_APAGAR_PLANO_SIM = "Sim, apagar o plano"
CONTA_APAGAR_PLANO_NAO = "Cancelar"
CONTA_PLANO_APAGADO = "O plano foi apagado."
CONTA_EXPORTAR_TITULO = "Os meus dados"
CONTA_EXPORTAR_TEXTO = (
    "Descarregue tudo o que guardámos sobre si (conta, consentimentos, respostas, planos e "
    "registos de progresso) num ficheiro JSON."
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
    "para fazer em casa, hábitos simples para o dia a dia e orientações para continuar depois."
)
COMO_FUNCIONA = (
    (
        "lista",
        "Responda ao questionário",
        f"Cerca de {MINUTOS_QUESTIONARIO} minutos sobre si, a sua saúde e a sua rotina.",
    ),
    (
        "intensidade",
        "Veja as nossas decisões",
        "Explicamos o que adaptámos e porquê, antes de preparar o plano.",
    ),
    (
        "calendario",
        "Receba o seu plano",
        "16 semanas em 4 fases, com treino em casa, alimentação, hábitos e orientações "
        "para continuar.",
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
INICIO_SELO = "Para quem tem 45 anos ou mais"
INICIO_DURACAO = f"Cerca de {MINUTOS_QUESTIONARIO} minutos · sem compromisso"
INICIO_AVISO = "A Vigoria orienta; não substitui o seu médico."
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
# Em produção (AMBIENTE=producao), o consentimento de saúde nomeia o tratamento pela IA.
# A CONFIRMAR (revisão jurídica): transferência para os EUA e a garantia de não-treino,
# com o fornecedor escolhido (Groq com Zero Data Retention; docs/GUIA_PRODUCAO.md).
CONSENTIMENTO_SAUDE_PRODUCAO = (
    "Autorizo o tratamento dos meus dados de saúde para gerar e acompanhar o meu plano, "
    "incluindo por um fornecedor de inteligência artificial que pode tratar os dados nos "
    "Estados Unidos. Recebe só as respostas necessárias ao plano, sem o meu nome nem o meu "
    "email, e não as usa para treinar os seus modelos."
)
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
# Fase 10C: à espera da vez na fila ou de um limite por minuto do serviço (429).
A_ESPERA = "Estamos a preparar o seu plano, pode demorar um minuto."
# Fase 10D: VIGORIA_PLANOS_POR_DIA (dia de Lisboa).
LIMITE_DIARIO = (
    "Hoje já chegou ao máximo de planos por dia ({n}). Amanhã pode pedir outro; as suas "
    "respostas continuam aqui."
)
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
    TipoErroUtilizador.FILA_CHEIA: (
        "Há muitas pessoas a preparar o plano neste momento. Tente de novo daqui a alguns "
        "minutos; as suas respostas continuam aqui."
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
SECCOES_PLANO = {  # em pastilhas, sem ícone (maqueta Resumo.dc.html)
    "resumo": "Resumo",
    "treino": "Treino",
    "alimentacao": "Alimentação",
    "habitos": "Hábitos",
    "acompanhamento": "Acompanhamento",
    "manutencao": "Manutenção",
}
# Topo do plano (Fase 8D): semana do programa, números e cartão «Hoje».
DIAS_VALOR = {1: "1 dia"}  # os outros: «{n} dias»
DIAS_VALOR_N = "{n} dias"
SEMANA_DE = "Semana {s} de 16"
SEMANA_FASE = "Fase {n} · {nome}"
SEMANA_MARCO = "Próximo marco: semana {m} · peso indicativo {kg} kg"
SEMANA_MANUTENCAO = "Manutenção"
SEMANA_MANUTENCAO_TEXTO = "Terminou as 16 semanas do programa (semana atual: {s})."
SEMANAS_ARIA = "Semana {s} de 16 do programa"
HOJE_DIA = "Hoje · {dia}"
HOJE_SESSAO = "{min} min · esforço {a} a {b} em 10"
HOJE_DESCANSO = "Hoje é dia de descanso"
HOJE_DESCANSO_SEM_TREINO = "Sem sessão de treino."
HOJE_MANUTENCAO = "Depois das 16 semanas"
HOJE_MANUTENCAO_TEXTO = "Veja em «Manutenção» como continuar ao seu ritmo."
HOJE_VER = "Ver a sessão de hoje"
HOJE_VER_MANUTENCAO = "Ver a manutenção"
# Treino (maqueta Fase)
ESFORCO = "Esforço"
SEMANAS_FASE = "Semanas {min} a {max}"
# Depois das 16 semanas (Fase 6B): textos aprovados a 05/11/2026 (P8).
RESUMO_MANUTENCAO = "Depois da semana 16, veja em «Manutenção» como continuar."
RECOMECAR_QUESTIONARIO = "Responder de novo ao questionário"
ESCOLHER_FASE = "Fase"
ESCOLHER = "Escolha uma opção"
MINUTOS_COLUNA = "Minutos"
DETALHES_SEMANA = "Ver o que fazer em cada dia"
NOTA_SESSAO_PLANO = "Plano de {data}, guardado na sua conta."
FREQUENCIA_PLANO = {"semanal": "Registo semanal", "a_cada_4_semanas": "Registo a cada 4 semanas"}
PERGUNTAS_REVISAO = "Perguntas para cada revisão"
VOLTAR_QUESTIONARIO = "Voltar ao questionário"
ACOMPANHAMENTO_LIGACAO = "Registar o meu progresso"
# R15: REGRAS_DOMINIO §9, tabela aprovada a 05/11/2026.
CONVITE_NOVO_PLANO = (
    "Chegou à semana 16 do plano. Quando quiser, responda de novo ao questionário para receber "
    "um plano novo, a partir do seu ponto atual. Não é obrigatório: pode continuar com as "
    "orientações de «Manutenção»."
)

# ---------------------------------------------------------------- O meu progresso (Fase 7)
# Mensagens aprovadas a 05/11/2026 (tabela em REGRAS_DOMINIO §9).

PROGRESSO_TITULO = "O meu progresso"
PROGRESSO_SEM_PLANO = "Para registar o seu progresso, comece por responder ao questionário."
PROGRESSO_SEMANA = "Está na semana {s} de 16 — fase {n}, {nome}."
PROGRESSO_MARCO = "Próximo marco: semana {m} (peso indicativo: {kg} kg)."
PROGRESSO_MANUTENCAO = "Está em manutenção desde a semana 17 (semana atual: {s})."
PROGRESSO_DESLIGADO = "O acompanhamento está desligado. Pode ligá-lo em «A minha conta»."

ALERTA_EM_FALTA = (
    "Ainda não tem registo {periodo}. Se quiser, pode registá-lo agora, com uma data desse período."
)
ALERTA_ABAIXO = (
    "Nos dois últimos registos, o peso desceu menos do que a linha indicativa do plano. É normal: "
    "a evolução raramente é linear. Antes de mudar tudo, veja estes pontos e escolha uma só "
    "alteração de cada vez."
)
ALERTA_ABAIXO_LISTA = "Quando a evolução abranda"
ALERTA_PERDA_RAPIDA = (
    "Nos dois últimos registos, o peso desceu mais depressa do que o ritmo máximo indicado para a "
    "sua idade ({pct} % do peso por semana). Não há vantagem em acelerar: mantenha as quantidades "
    "do plano. Se a perda não tiver explicação, ou se se sentir com menos energia, fale com o seu "
    "médico."
)
ALERTA_ESFORCO = (
    "No último registo, o esforço foi {e} em 10, acima do indicado para esta fase (entre {min} e "
    "{max}). Nas próximas sessões, alivie um pouco: menos repetições, mais descanso ou um ritmo "
    "mais calmo. No cardio, deve conseguir falar em frases curtas."
)
ALERTA_SUBIDA = (
    "Nos dois últimos registos, {medida} está acima do valor do início da manutenção ({ref}). "
    "Veja «O que vigiar» na secção Manutenção do plano."
)
ALERTA_VER_VIGIAR = "Ver «O que vigiar»"
MEDIDA_PESO = "o peso"
MEDIDA_CINTURA = "o perímetro da cintura"

REGISTAR_TITULO = "Registar"
POR_FAZER_TITULO = "Registo {periodo} por fazer"
POR_FAZER_TEXTO = "Leva cerca de 2 minutos."
POR_FAZER_BOTAO = "Registar"
MEDIA_SESSOES = "Sessões por semana"
MEDIA_SESSOES_DE = "de {d}"
MEDIA_CARDIO = "Cardio por semana"
REGISTAR_FEITO = "Já tem o registo {periodo}."
REGISTAR_OUTRO = "Registar outro período"
ROTULOS_REGISTO = {
    "data": "Data",
    "peso_kg": "Peso (kg)",
    "cintura_cm": "Perímetro da cintura (cm)",
    "sessoes": "Sessões feitas",
    "cardio_min": "Minutos de cardio",
    "energia": "Energia (0 a 10)",
    "esforco": "Esforço (0 a 10)",
    "sono_h": "Sono médio (horas)",
    "forca": "Força",
    "mobilidade_equilibrio": "Mobilidade e equilíbrio",
    "observacoes": "Observações (opcional)",
}
REGISTO_SESSOES_4 = "Sessões feitas (numa semana normal)"
REGISTO_CARDIO_4 = "Minutos de cardio (numa semana normal)"
REGISTO_FORCA = "Comparando com o registo anterior, os exercícios de força estão…"
REGISTO_MOBILIDADE = "Comparando com o registo anterior, a mobilidade e o equilíbrio estão…"
COMPARACAO = {
    Comparacao.MAIS_DIFICIL: "Mais difícil",
    Comparacao.IGUAL: "Igual",
    Comparacao.MAIS_FACIL: "Mais fácil",
}
REGISTO_OBSERVACOES_AJUDA = (
    "Só para si. Fica guardado na sua conta, mas a Vigoria não o analisa nem o envia a terceiros."
)
REGISTO_NOTA_MANUTENCAO = "Na manutenção, basta um registo a cada 4 semanas."
REGISTO_GUARDAR = "Guardar o registo"
REGISTO_CANCELAR = "Cancelar"
REGISTO_GUARDADO = "O registo foi guardado."
REGISTO_REPETIDO = "Já tem um registo {periodo}. Pode editá-lo na lista abaixo."
REGISTO_DATA_FUTURA = "A data não pode ser posterior a hoje."
REGISTO_DATA_ANTES = "A data não pode ser anterior ao início do plano."
REGISTO_VAZIO = "Preencha pelo menos um campo para guardar o registo."
REGISTO_INVALIDO = "Reveja: {campos}."

GRAFICOS_TITULO = "A minha evolução"
GRAFICOS_SEM_REGISTOS = "Os gráficos aparecem depois do primeiro registo."
GRAFICO_PESO = "Peso"
GRAFICO_CINTURA = "Perímetro da cintura"
GRAFICO_SESSOES = "Sessões por semana"
GRAFICO_CARDIO = "Minutos de cardio por semana"
GRAFICO_SEMANA = "Semana do plano"
GRAFICO_REGISTOS = "Os seus registos"
GRAFICO_LINHA = "Linha indicativa"
GRAFICO_LIMIAR = "Referência de risco"
GRAFICO_PREVISTO = "Previsto no plano"
GRAFICO_DICA = "Semana %{{x}}: %{{y}} {unidade}"
UNIDADE_SESSOES = "sessões"
UNIDADE_MINUTOS = "minutos"
RESUMO_PESO = "Último registo: {p} kg na semana {s}. Linha indicativa nessa semana: {l} kg."
RESUMO_PESO_MANUTENCAO = "Último registo: {p} kg na semana {s}."
RESUMO_CINTURA = "Último registo: {c} cm na semana {s} (no início: {c0} cm)."
RESUMO_CINTURA_LIMIAR = "A linha tracejada marca {limiar} cm, a referência de risco."
RESUMO_SESSOES = "{registos}, fez em média {x} sessões por semana (o plano prevê {d})."
RESUMO_CARDIO = "{registos}, fez em média {m} minutos de cardio por semana."

REGISTOS_TITULO = "Registos anteriores"
REGISTOS_VAZIO = "Ainda não tem registos neste plano."
REGISTO_SEMANA = "Semana {s}"
REGISTO_EDITAR = "Editar"
REGISTO_APAGAR = "Apagar"
REGISTO_APAGAR_PERGUNTA = "Apagar o registo da semana {s}? Não é possível recuperá-lo."
REGISTO_APAGAR_SIM = "Sim, apagar o registo"
REGISTO_APAGAR_NAO = "Cancelar"
REGISTO_APAGADO = "O registo foi apagado."

CONTA_ACOMPANHAMENTO = "Acompanhamento"
CONTA_ACOMPANHAMENTO_ATIVO = "Quero acompanhar o meu progresso"
ROTULOS_QUESTIONARIO_FREQUENCIA = "Com que frequência quer registar o seu progresso?"
CONTA_ACOMPANHAMENTO_GUARDADO = "As suas preferências foram guardadas."
CONTA_LEMBRETES_EMAIL = "Enviar-me um lembrete por email quando faltar um registo"

# Deixar de receber lembretes (ligação dos emails, sem sessão iniciada; Fase 8). Os textos
# estão em notificacoes/modelos/cancelar.yaml, partilhados com o serviço de produção (Fase 10).
_CANCELAR = textos_cancelar()
CANCELAR_TITULO = _CANCELAR.titulo
CANCELAR_PERGUNTA = _CANCELAR.pergunta
CANCELAR_BOTAO = _CANCELAR.botao
CANCELAR_FEITO = _CANCELAR.feito
CANCELAR_REATIVAR = _CANCELAR.reativar
CANCELAR_INVALIDA = _CANCELAR.invalida
CANCELAR_EXPIRADA = _CANCELAR.expirada
CANCELAR_INICIO = _CANCELAR.inicio


def periodo_de(primeira: int, ultima: int) -> str:
    """«da semana 5» ou «das semanas 5 a 8»."""
    return f"da semana {primeira}" if primeira == ultima else f"das semanas {primeira} a {ultima}"


def periodo_para(primeira: int, ultima: int) -> str:
    """«para a semana 5» ou «para as semanas 5 a 8»."""
    return (
        f"para a semana {primeira}"
        if primeira == ultima
        else f"para as semanas {primeira} a {ultima}"
    )


def medias_de(n: int) -> str:
    """Legenda dos cartões das médias no progresso (Fase 8D)."""
    return "Média do último registo" if n == 1 else f"Médias dos últimos {n} registos"


def ultimos_registos(n: int) -> str:
    return "No último registo" if n == 1 else f"Nos últimos {n} registos"


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
