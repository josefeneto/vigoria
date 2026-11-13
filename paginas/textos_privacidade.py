"""Texto da política de privacidade por ambiente (Fase 10D). RASCUNHO, a rever juridicamente.

Na demonstração (Streamlit Community Cloud) fala do GitHub e dos servidores fora da UE; em
produção (e em local), do Railway na UE e do serviço de lembretes da própria Vigoria.
"""

INICIO = """
### Quem somos

A Vigoria é uma aplicação que prepara planos pessoais de saúde e vitalidade de 16 semanas.
O responsável pelo tratamento dos dados será identificado aqui antes do lançamento.

### Que dados tratamos

- **Dados da conta:** o email com que entra (através do Auth0, o serviço de autenticação).
  A Vigoria nunca guarda a sua palavra-passe.
- **Respostas ao questionário:** idade, sexo, altura, peso, cintura, sono, atividade física,
  condições de saúde, limitações, medicação que afete o ritmo cardíaco, alimentação, bebidas
  e objetivos.
- **Registos de progresso** que decidir fazer (peso, cintura e outros indicadores).

Não pedimos o seu número de telemóvel: os lembretes são enviados apenas por email.

### Dados de saúde

As condições de saúde, a medicação e as medidas do corpo são dados de saúde, uma categoria
especial de dados pessoais (artigo 9.º do RGPD). Só os tratamos com o seu **consentimento
explícito**, dado no início do questionário, e apenas para preparar e acompanhar o seu plano.
Pode retirar o consentimento a qualquer momento; isso não afeta o tratamento feito antes.

### Para que usamos os dados

- Preparar o seu plano e adaptá-lo à sua idade, saúde e disponibilidade.
- Acompanhar o seu progresso e, se o ativar, enviar-lhe lembretes por email.

Nunca usamos os seus dados de saúde para publicidade nem para segmentação de anúncios.
"""

IA_DEMO = """
### Inteligência artificial

Parte do texto do plano é escrita por um serviço de inteligência artificial. Esse serviço
recebe apenas as respostas necessárias ao plano, **sem** o seu nome, email ou qualquer
identificador. Os números do plano (peso, proteína, hidratação) e os avisos de segurança são
calculados pela própria Vigoria, não pela inteligência artificial. O fornecedor desse serviço
e o local onde trata os pedidos (que pode ser fora da União Europeia) serão indicados aqui
antes do lançamento.
"""

# Decisão do José (13/11/2026): principal Google (Gemini API, nível pago), reserva Groq.
# A CONFIRMAR (revisão jurídica): a base da transferência para os EUA dos dois fornecedores,
# o prazo de conservação da Google para prevenir abusos e o Zero Data Retention do Groq.
# Coerente com CONSENTIMENTO_SAUDE_PRODUCAO.
IA_PRODUCAO = """
### Inteligência artificial

Parte do texto do plano é escrita por inteligência artificial:

- **Google** (Gemini API, no nível pago): o fornecedor principal.
- **Groq**: a reserva, usada só quando o serviço da Google falha.

Os dois podem tratar os pedidos nos **Estados Unidos**. Recebem apenas as respostas
necessárias ao plano, **sem** o seu nome, email ou qualquer identificador, e não as usam
para treinar os seus modelos; só as guardam o tempo que os seus termos preveem para
prevenir abusos. Este tratamento faz parte do consentimento que dá no início do
questionário. Os números do plano (peso, proteína, hidratação) e os avisos de segurança são
calculados pela própria Vigoria, não pela inteligência artificial.
"""

ONDE_DEMO = """
### Onde ficam e durante quanto tempo

As respostas, os planos e os registos ficam guardados numa base de dados na União Europeia
(Frankfurt, Alemanha). A entrada na conta é tratada pelo Auth0, um serviço de autenticação
que usamos como subcontratante, num servidor da região europeia.

Se ativar os lembretes por email, usamos dois subcontratantes, nenhum deles com acesso aos
seus dados de saúde:

- **Brevo** (empresa da União Europeia): envia os lembretes. Recebe apenas o seu email e o
  texto do lembrete, que nunca tem dados de saúde.
- **GitHub** (Estados Unidos): agenda o envio diário. Lê o seu email e as semanas em que fez
  registos, nunca os valores registados nem as respostas ao questionário.

Todos os lembretes têm uma ligação para deixar de os receber; pode também desativá-los em
«A minha conta».

A versão de demonstração da Vigoria corre em servidores fora da União Europeia: nessa
versão, não introduza dados reais de saúde.
"""

ONDE_PRODUCAO = """
### Onde ficam e durante quanto tempo

A Vigoria corre em servidores na União Europeia (Railway, em Amesterdão, Países Baixos). As
respostas, os planos e os registos ficam guardados numa base de dados na União Europeia
(Neon, em Frankfurt, Alemanha). A entrada na conta é tratada pelo Auth0, um serviço de
autenticação que usamos como subcontratante, num servidor da região europeia.

Se ativar os lembretes por email, a própria Vigoria decide quando os enviar e usa a
**Brevo** (empresa da União Europeia) para os entregar. A Brevo recebe apenas o seu email e
o texto do lembrete, que nunca tem dados de saúde.

Todos os lembretes têm uma ligação para deixar de os receber; pode também desativá-los em
«A minha conta».
"""

FIM = """
Guardamos os dados enquanto tiver conta. Em «A minha conta», pode descarregá-los ou apagar a
conta: ao apagá-la, apagamos as respostas, os planos e os registos, e também a conta de
entrada no Auth0. O prazo exato de conservação será indicado aqui antes do lançamento.

### Os seus direitos

Pode, a qualquer momento, aceder aos seus dados, corrigi-los, descarregá-los, apagar a conta
e retirar o consentimento. Pode também apresentar reclamação à Comissão Nacional de Proteção
de Dados (CNPD).

### Contacto

O contacto para questões de privacidade será indicado aqui antes do lançamento.
"""


def privacidade(ambiente: str) -> str:
    """A política em Markdown: a versão da demonstração ou a de produção (também em local)."""
    if ambiente == "demo":
        return INICIO + IA_DEMO + ONDE_DEMO + FIM
    return INICIO + IA_PRODUCAO + ONDE_PRODUCAO + FIM
