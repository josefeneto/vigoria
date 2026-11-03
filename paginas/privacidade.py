"""Política de privacidade — RASCUNHO (Fases 5 e 6), a rever juridicamente antes do beta."""

import streamlit as st

st.title("Política de privacidade")
st.warning(
    "Este texto é um rascunho, ainda não revisto por um jurista. Não está em vigor.",
    title="RASCUNHO",
    icon=":material/edit_note:",
)

st.markdown(
    """
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

### Inteligência artificial

Parte do texto do plano é escrita por um serviço de inteligência artificial. Esse serviço
recebe apenas as respostas necessárias ao plano, **sem** o seu nome, email ou qualquer
identificador. Os números do plano (peso, proteína, hidratação) e os avisos de segurança são
calculados pela própria Vigoria, não pela inteligência artificial. O fornecedor desse serviço
e o local onde trata os pedidos (que pode ser fora da União Europeia) serão indicados aqui
antes do lançamento.

### Onde ficam e durante quanto tempo

As respostas, os planos e os registos ficam guardados numa base de dados na União Europeia
(Frankfurt, Alemanha). A entrada na conta é tratada pelo Auth0, um serviço de autenticação
que usamos como subcontratante, num servidor da região europeia.

A versão de demonstração da Vigoria corre em servidores fora da União Europeia: nessa
versão, não introduza dados reais de saúde.

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
)
