---
paths:
  - "app.py"
  - "paginas/**"
  - "src/vigoria/notificacoes/**"
  - "src/vigoria/exportacao/**"
  - ".streamlit/**"
---

# Regras ao trabalhar na interface, emails e exportação

## Público e acessibilidade

- Público principal com 45–75 anos, muitas vezes no telemóvel. Letra base de pelo menos 17 px, contraste AA, botões grandes, uma decisão por ecrã no questionário.
- Questionário em passos (uma secção do Prompt Universal por passo), com barra de progresso, botão «Anterior» e respostas guardadas na sessão para não se perderem.
- Explicar termos técnicos na própria frase («gordura visceral — a gordura que se acumula à volta dos órgãos abdominais»).
- **Mobile-first**: desenhar primeiro para telemóvel (cerca de 390 px) e só depois alargar para computador. Testar as duas larguras antes de dar um ecrã por terminado.
- Evitar componentes que dependam de rato (passar o cursor por cima, tabelas largas com deslocamento horizontal). Em telemóvel, tabelas largas passam a cartões.
- A app tem de funcionar bem instalada como PWA (ecrã inteiro, sem barra do browser): nada de ligações que abram separadores novos sem necessidade, e o botão «Voltar» da própria app sempre visível.

## Tom de voz Vigoria

- Direto e honesto: diz quando um objetivo é pouco realista.
- Caloroso, não clínico. Nunca alarmista, mas nunca vago nos avisos de segurança.
- Trata o utilizador por «você» implícito com verbo na 3.ª pessoa («Indique o seu peso»), registo cordial e respeitoso — é o mais natural para este público em Portugal.
- Português Europeu, AO90: facto, contacto, ação, ótimo; «estar a + infinitivo», nunca gerúndio progressivo; pronomes em ênclise nas afirmativas («Envie-nos»).

## Identidade visual (ponto de partida do briefing)

- Principal: verde-azulado petróleo `#1F5C63`. Destaque: terracota `#C2693E`. Texto: grafite `#2E3338`. Fundo: branco-osso `#F7F3EC`.
- Definidas em `.streamlit/config.toml`; não repetir cores soltas no código.

## Emails

- Remetente e assunto em PT-EU, curtos. Todos os emails com ligação para desativar lembretes.
- Nunca incluir dados de saúde (peso, cintura, doenças) no corpo do email — só o convite para registar na app.
