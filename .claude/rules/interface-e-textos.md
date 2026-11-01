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

- Público principal com 45–75 anos, muitas vezes no telemóvel. Letra base de pelo menos 17 px, contraste AA, botões grandes, poucas perguntas por ecrã.
- Questionário em passos tal como definidos em `docs/dominio/QUESTIONARIO.md` (agrupados por tema, cerca de 6 perguntas por ecrã no máximo), com barra de progresso, botão «Anterior» e respostas guardadas na sessão para não se perderem.
- Explicar termos técnicos na própria frase («gordura visceral — a gordura que se acumula à volta dos órgãos abdominais»).
- **Mobile-first**: desenhar primeiro para telemóvel (cerca de 390 px) e só depois alargar para computador. Testar as duas larguras antes de dar um ecrã por terminado.
- Evitar componentes que dependam de rato (passar o cursor por cima, tabelas largas com deslocamento horizontal). Em telemóvel, tabelas largas passam a cartões.
- A app tem de funcionar bem instalada como PWA (ecrã inteiro, sem barra do browser): nada de ligações que abram separadores novos sem necessidade, e o botão «Voltar» da própria app sempre visível.

## Tom de voz Vigoria

- Direto e honesto: diz quando um objetivo é pouco realista.
- Caloroso, não clínico. Nunca alarmista, mas nunca vago nos avisos de segurança.
- Trata o utilizador por «você» implícito com verbo na 3.ª pessoa («Indique o seu peso»), registo cordial e respeitoso — é o mais natural para este público em Portugal.
- Português Europeu, AO90: facto, contacto, ação, ótimo; «estar a + infinitivo», nunca gerúndio progressivo; pronomes em ênclise nas afirmativas («Envie-nos»).

## Identidade visual (Fase 5B)

- Principal: petróleo `#1F5C63`. Texto: grafite `#2E3338`. Fundo: branco-osso `#F7F3EC`. Terracota `#C2693E` só em ícones e formas; em texto e botões de destaque, cobre `#A3532D`. Paleta completa em `paginas/estilos.py` (`CORES`).
- Cores no tema (`.streamlit/config.toml`) e em `CORES`, nunca soltas no código; o CSS (`paginas/estilos.css`) usa as variáveis `--v-*`. Um teste confirma que os dois sítios coincidem e que cada par de texto e fundo tem pelo menos 4,5:1: um par novo entra em `PARES_TEXTO`.
- Componentes visuais em `paginas/componentes.py`, com `html.escape` em todo o texto. Ícones próprios em `assets/icones/` (SVG 24×24, desenhados de raiz); nunca copiar elementos de outras apps.
- CSS só com `.st-key-*`, classes `.v-*` e atributos estáveis dos widgets; nunca classes `st-emotion-cache-*`. Depois de mexer na interface: `python scripts/capturas.py depois` e comparar com `saidas/capturas/antes/`.
- Fotografias em `assets/img/` (webp, até 200 KB, `scripts/converter_fotos.py`), com origem e licença em `docs/CREDITOS_IMAGENS.md`. Nada de «antes e depois» nem de mensagens de transformação corporal.

## Emails

- Remetente e assunto em PT-EU, curtos. Todos os emails com ligação para desativar lembretes.
- Nunca incluir dados de saúde (peso, cintura, doenças) no corpo do email — só o convite para registar na app.
