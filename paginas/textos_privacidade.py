"""Texto da política de privacidade por ambiente.

Produção (e local): POLITICA_PRODUCAO, revista à luz do RGPD e da Lei 58/2019 e completada
pelo José (16/11/2026). Enquanto houver campos «[PREENCHER», a página mostra a faixa
«RASCUNHO» (em_rascunho). Demonstração: os textos antigos, a retirar com a demo.
Se o texto de produção mudar, atualizar VERSAO_CONSENTIMENTO em paginas/textos.py.
"""

PREENCHER = "[PREENCHER"

INICIO = """
### Quem somos

A Vigoria é uma aplicação que prepara planos pessoais de saúde e vitalidade de 16 semanas
e recomendações de manutenção na continuidade.
O responsável pelo tratamento dos dados será identificado aqui antes do lançamento
comercial efetivo da aplicação.

### Que dados são tratados

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
explícito**, dado na adesão, e apenas para preparar e acompanhar o seu plano.
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


FIM = """
Guardamos os dados enquanto tiver conta. Em «A minha conta», pode descarregá-los ou apagar a
conta: ao apagá-la, apagamos as respostas, os planos e os registos, e também a conta de
entrada no Auth0. O prazo exato de conservação será indicado aqui antes do lançamento.

### Os seus direitos

Pode, a qualquer momento, aceder aos seus dados, corrigi-los, descarregá-los, apagar a conta
e retirar o consentimento. Pode também apresentar reclamação à Comissão Nacional de Proteção
de Dados (CNPD).

### Contacto

O contacto para questões de privacidade é privacidade@vigoria.pt.
"""


POLITICA_PRODUCAO = """
### Quem somos

A Vigoria prepara planos pessoais de saúde e vitalidade de 16 semanas, seguidos de
recomendações de manutenção, para adultos, sobretudo a partir dos 45 anos. O responsável
pelo tratamento dos seus dados é a **Vigoria**. Para qualquer questão de privacidade,
escreva para **privacidade@vigoria.pt**.

### Que dados tratamos e porquê

- **Conta:** o email com que entra, através do Auth0. Serve para criar e gerir a sua conta,
  ao abrigo do contrato de utilização. A Vigoria nunca vê a sua palavra-passe.
- **Questionário e progresso:** idade, sexo, medidas do corpo, sono, atividade física,
  condições de saúde, limitações, medicação, alimentação, objetivos e os registos que fizer.
  São dados de saúde e só os tratamos com o seu **consentimento explícito** (artigo 9.º do
  RGPD), para preparar e acompanhar o seu plano. Sem eles não é possível gerar o plano.
- **Lembretes por email:** só se os ativar, com o seu consentimento.
- **Dados técnicos:** registos de acesso e o número de planos pedidos por dia, para manter
  o serviço seguro e evitar abusos (interesse legítimo).

Não pedimos o número de telemóvel. Nunca usamos dados de saúde para publicidade.

### Como é feito o plano

O plano é gerado automaticamente. Os números (peso, proteína, hidratação) e os avisos de
segurança são calculados por regras da própria Vigoria; parte do texto é escrita por
inteligência artificial. É uma orientação de bem-estar e não substitui o seu médico.

### Quem recebe os dados

Usamos estes subcontratantes, obrigados por contrato a proteger os dados e a usá-los só ao
serviço da Vigoria:

- **Railway** (servidores em Amesterdão, Países Baixos) e **Neon** (base de dados em
  Frankfurt, Alemanha): alojamento da aplicação e dos dados.
- **Auth0** (região europeia): entrada na conta.
- **Brevo** (empresa da União Europeia): envio dos lembretes. Recebe só o seu email e o texto
  do lembrete, que nunca tem dados de saúde.
- **Google** (Gemini API, nível pago) e, só quando esta falha, **Groq**: escrevem parte do
  texto do plano. Recebem apenas as respostas necessárias, sem o seu nome nem o seu email, e
  não as usam para treinar os seus modelos. A Google guarda-as até 55 dias para detetar
  abusos; a Groq **não as guarda**. Mesmo sem nome, estas respostas continuam a ser dados
  pessoais protegidos.

### Transferências para fora da União Europeia

A Google e a Groq podem tratar os pedidos nos **Estados Unidos**. A Railway, a Neon e o
Auth0 são empresas norte-americanas, ainda que guardem os dados na Europa. Estas
transferências estão protegidas pelo Quadro de Privacidade de Dados UE-EUA, no caso das
empresas certificadas, ou por cláusulas contratuais-tipo aprovadas pela Comissão Europeia.

### Durante quanto tempo

Guardamos os dados enquanto tiver conta. Quando a conta é apagada, apagamos as respostas, os
planos, os registos e a conta no Auth0.

### Cookies

Usamos apenas os cookies necessários para manter a sessão iniciada. Não usamos cookies de
análise nem de publicidade.

### Segurança

As ligações são cifradas e o acesso aos dados é restrito a quem está obrigado a sigilo. Se
houver uma violação de dados com risco para si, informamos a CNPD e, quando a lei o exige,
também as pessoas afetadas.

### Os seus direitos

Pode aceder aos seus dados, corrigi-los, apagá-los, levá-los consigo, limitar ou opor-se ao
seu tratamento e retirar o consentimento a qualquer momento, sem afetar o que foi feito
antes. Em «A minha conta» pode descarregar os dados, desligar os lembretes e apagar a conta
(o que retira também o consentimento). Para o resto, escreva para o contacto acima:
respondemos no prazo de um mês. Pode ainda reclamar junto da Comissão Nacional de Proteção
de Dados (CNPD, www.cnpd.pt).

### Alterações

Versão de **20/11/2026**. Avisamos na aplicação de qualquer alteração relevante e, se mudar
o que consentiu, voltamos a pedir o seu consentimento.
"""


def privacidade(ambiente: str) -> str:
    """A política em Markdown: a versão da demonstração ou a de produção (também em local)."""
    if ambiente == "demo":
        return INICIO + IA_DEMO + ONDE_DEMO + FIM
    return POLITICA_PRODUCAO


def em_rascunho(texto: str) -> bool:
    """Ainda há campos por preencher: a página mostra a faixa «RASCUNHO»."""
    return PREENCHER in texto
