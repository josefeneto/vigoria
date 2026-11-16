"""Texto da política de privacidade, o mesmo em todos os ambientes (decisão do José, 16/11/2026).

Revisto à luz do RGPD e da Lei 58/2019 e completado pelo José (16/11/2026). Enquanto houver
campos «[PREENCHER», a página mostra a faixa «RASCUNHO» (em_rascunho).
Se o texto mudar, atualizar VERSAO_CONSENTIMENTO em paginas/textos.py.
"""

PREENCHER = "[PREENCHER"

POLITICA = """
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


def privacidade() -> str:
    """A política em Markdown, igual em todos os ambientes."""
    return POLITICA


def em_rascunho(texto: str) -> bool:
    """Ainda há campos por preencher: a página mostra a faixa «RASCUNHO»."""
    return PREENCHER in texto
