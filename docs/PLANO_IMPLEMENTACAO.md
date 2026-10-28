# Vigoria — Plano de implementação com Claude Code

*Versão 1.0 — 22 de outubro de 2026*

Este plano leva a Vigoria do conteúdo já validado (Prompt Universal v2, volumes 1 a 3 do Projeto Vitalidade Sénior, briefing de marca) até uma primeira versão pública em beta fechado. Está escrito para ser seguido fase a fase dentro do VS Code, com o Claude Code a escrever o código e o José a decidir, testar e aprovar.

Cada fase tem o mesmo formato: o que se pretende, o que o José tem de fazer à mão, o prompt a colar no Claude Code e como saber que a fase ficou bem feita.

---

## 1. O que entra no MVP — e o que fica para depois

**Entra:**
- Questionário em passos, baseado no Prompt Universal v2, com consentimento explícito.
- Geração do plano personalizado (16 semanas) com regras de segurança determinísticas e conteúdo editorial dos três volumes.
- Visualização do plano por separadores (resumo, treino, alimentação, hábitos, acompanhamento) e descarga em PDF.
- Conta de utilizador obrigatória (Google ou email e palavra-passe, via Auth0), histórico de planos, dados de cada pessoa isolados.
- Registo de progresso (semanal ou a cada 4 semanas) com gráficos face aos objetivos.
- Lembretes por email quando o registo está em falta.
- Aplicação web progressiva (PWA) desde o início: desenho mobile-first, instalável no ecrã inicial do telemóvel (Android e iPhone) e utilizável no computador.
- Publicação no Railway, região europeia.

**Fica para depois:**
- Aplicação móvel nativa nas lojas (Google Play, App Store). A PWA cobre o essencial; uma app nativa só se justifica se faltar algo que a PWA não consiga dar.
- Publicidade (só depois de existir política clara e base de utilizadores).
- SMS/WhatsApp, vídeos dos exercícios, reajuste automático do plano com base no progresso.
- Manual de utilizador independente da aplicação (previsto no documento de continuidade) — escreve-se no fim da fase 10, com a app estável.

---

## 2. Decisões de arquitetura — e porquê

**Streamlit continua a ser a escolha certa para o MVP.** O José já o conhece, o Claude Code domina-o, e traz autenticação nativa por OpenID Connect (`st.login`), o que resolve contas sem a app gerir palavras-passe. O preço a pagar é uma experiência no telemóvel menos fina do que a de uma app nativa.

**PWA com Streamlit: possível, mas com limites a conhecer.** O Streamlit não traz suporte a PWA de origem, e as tentativas de injetar o *service worker* a partir da própria app falham, porque esse código corre dentro de um iframe. A solução robusta é uma camada fina à frente do Streamlit, no mesmo contentor Docker: um servidor Caddy que entrega o `manifest.webmanifest`, os ícones, o `sw.js` e uma página «sem ligação», e acrescenta ao HTML do Streamlit a ligação ao manifesto. O resultado é uma app instalável, com ícone próprio, a abrir em ecrã inteiro. **Não funciona sem internet**: o Streamlit precisa de ligação permanente ao servidor, por isso o modo offline limita-se a uma página a explicar que é preciso ligação. Para este produto chega, porque gerar e registar planos exige sempre o servidor. Esta camada só existe no Railway (onde controlamos o contentor); no Streamlit Community Cloud a app funciona no browser do telemóvel, mas não é instalável. Para não ficar preso, toda a lógica vive em `src/vigoria/`, separada da interface: se um dia se migrar para FastAPI com uma interface própria, o motor mantém-se.

**Sem CrewAI nesta fase — e esta é a mudança mais importante face ao desenho de julho.** Os cinco agentes (acolhimento, estratégia, gerador, verificação, voz de marca) mantêm-se como *papéis*, mas três deles passam a ser código determinístico. A razão é de segurança, não de gosto: decisões como «IMC ≥ 35 limita a intensidade» ou «nunca mais de 0,5 kg de músculo por cada 4 semanas» têm de dar sempre o mesmo resultado e ser testáveis. Uma LLM não garante isso. Há também uma razão prática: com o nível gratuito do Gemini, cinco chamadas por plano esgotam a quota depressa. O desenho final faz no máximo três chamadas por plano. Se mais tarde fizer sentido, o pipeline encaixa num orquestrador sem reescrever as regras.

**Gemini (modelo Flash) como LLM principal, Groq como reserva.** Três factos a ter presentes:
- A família Gemini 2.5 foi descontinuada a 16 de outubro de 2026 e os modelos Pro saíram do nível gratuito em abril. O nome do modelo fica numa variável de ambiente (`GEMINI_MODEL`), a confirmar no AI Studio no arranque.
- Os termos do Gemini pedem para não enviar dados pessoais ou sensíveis ao serviço gratuito; para quem está no Espaço Económico Europeu aplicam-se as regras de tratamento de dados dos serviços pagos mesmo no nível gratuito. Ainda assim, a app nunca envia nome, email ou identificadores — só os dados do questionário, pseudonimizados.
- O nível gratuito serve para desenvolver e para o beta. **Antes do lançamento público, passar ao nível pago** (o Flash custa cêntimos por plano) — por limites de quota e porque os termos do nível gratuito não são pensados para uso comercial com publicidade.

**Auth0 para contas.** O `st.login` só fala com fornecedores de identidade externos. O Auth0 junta numa única página «Continuar com Google» e «Email e palavra-passe», e trata do registo, da verificação do email, da recuperação de palavra-passe e da proteção contra ataques. O plano gratuito cobre até 25 000 utilizadores ativos por mês. Programar palavras-passe dentro da app foi posto de parte: muito código sensível numa app que já guarda dados de saúde.

**Brevo para email.** Empresa europeia, plano gratuito com 300 emails por dia e API transacional — suficiente para lembretes durante muito tempo. A alternativa (Resend) tem boa experiência de programação, mas é americana; para dados de utilizadores europeus de uma app de saúde, a Brevo simplifica a conversa sobre RGPD.

**Railway, como nos projetos anteriores**, mas com duas diferenças: região europeia (confirmar no painel do serviço) e PostgreSQL gerido em vez de SQLite, porque os dados dos utilizadores têm de sobreviver a cada nova publicação. Os lembretes correm num segundo serviço com agendamento (cron) do próprio Railway.

---

## 3. Riscos a ter presentes desde o início

1. **Dados de saúde (RGPD, art. 9.º).** É o risco principal. Consentimento explícito, minimização, exportação e eliminação de conta, servidores na UE e política de privacidade clara. Antes do lançamento público, vale a pena uma revisão jurídica curta.
2. **Fronteira com dispositivo médico.** Uma app de bem-estar que não diagnostica nem trata fica, em regra, fora do Regulamento de Dispositivos Médicos. O que a pode empurrar para dentro é a linguagem: nunca «trata», «cura», «diagnostica»; sempre «sugere», «apoia», «orienta». Está nas regras do CLAUDE.md, mas a responsabilidade final é editorial.
3. **Incoerência no conteúdo editorial — resolvida na app.** A Fase 4 do Volume 2 incluía exercícios de impacto (agachamento com salto, escaladores, thrusters) que contrariavam o «baixo impacto» do Volume 1. A resolução está em `docs/dominio/REGRAS_DOMINIO.md`, secção 6: prevalece o Volume 1, variantes-base por omissão, avançadas só com critérios estritos. O Volume 2 em Word já foi revisto em conformidade.
4. **Valores clínicos ainda sem revisão profissional.** As decisões das `REGRAS_DOMINIO.md` estão tomadas (25/10/2026), mas os valores — ritmos de perda de peso, proteína, tetos de intensidade, variantes dos exercícios — devem ser revistos por um médico ou nutricionista antes do beta com pessoas reais.
5. **Quotas gratuitas.** Gemini e Brevo têm limites. O código trata erros de quota (HTTP 429) com espera e nova tentativa, e mostra ao utilizador uma mensagem honesta em vez de falhar em silêncio.
6. **Marca.** A confirmação dos domínios `vigoria.pt` / `vigoria.com` e a pesquisa no INPI continuam por fazer (briefing de marca, secção 7). Convém tratar disso antes de investir em identidade visual.

---

## 4. Como trabalhar com o Claude Code — o ritual de cada sessão

O Claude Code funciona melhor com sessões curtas e focadas. Para cada fase:

1. **Abrir a pasta do projeto no VS Code** e o painel do Claude Code (ícone ✱ na barra lateral).
2. **Trabalhar sempre no `main`** — sem ramos por fase. Confirmar com `git status` que se está no `main` e sem alterações pendentes.
3. **Começar em modo de planeamento.** No painel, escolher o modo *Plan* (no terminal: `Shift+Tab` até aparecer «plan mode»). O Claude Code lê os ficheiros e propõe um plano sem alterar nada.
4. **Colar o prompt da fase** (secção 5) e ler o plano com atenção. Corrigir o que não estiver bem antes de aprovar. É aqui que se poupa mais tempo.
5. **Aprovar e acompanhar.** O Claude Code pede autorização para editar ficheiros e correr comandos; o `.claude/settings.json` já autoriza os comandos seguros (testes, lint, git status) e bloqueia os perigosos.
6. **Testar à mão** o que a fase produziu (os critérios de aceitação dizem como).
7. **Commit no `main`** — commits pequenos, um ou mais por fase; antes de cada commit, lint e testes têm de passar (`python -m ruff check .` e `python -m pytest -q -m "not llm"`). O `git push` só depois de o José confirmar. Atualizar o `docs/ESTADO.md` (pedir ao Claude Code: «Atualiza o ESTADO.md com o que fizemos nesta fase»).
8. **Limpar o contexto antes da fase seguinte:** `/clear`. O CLAUDE.md e o ESTADO.md voltam a ser lidos automaticamente; a conversa anterior não é precisa.

Comandos úteis dentro do Claude Code:
- `/context` — ver o que está carregado (confirmar que o CLAUDE.md entrou).
- `/compact` — resumir a conversa quando uma sessão fica longa.
- `/memory` — abrir e editar o CLAUDE.md.
- `Esc` interrompe; `Esc Esc` permite voltar atrás a um ponto anterior (checkpoint) se algo correr mal.
- Para referir um ficheiro no prompt: `@docs/dominio/REGRAS_DOMINIO.md`.

Regra de ouro: **quando o Claude Code fizer o mesmo erro duas vezes, acrescenta-se uma linha ao CLAUDE.md.** É assim que o projeto «aprende».

---

## 5. Fases

### Fase 0 — Preparação do ambiente *(1 sessão, sobretudo manual)*

**Objetivo:** máquina pronta, repositório criado, kit no sítio.

**O José faz:** seguir `docs/GUIA_ARRANQUE_WINDOWS.md` do princípio ao fim.

**Prompt (primeira conversa no Claude Code, já dentro da pasta):**
```
Olá. Lê o CLAUDE.md, o docs/ESTADO.md e o docs/PLANO_IMPLEMENTACAO.md.
Não escrevas código ainda. Quero que:
1. Me confirmes, numa lista curta, o que entendeste do projeto e da arquitetura.
2. Verifiques o ambiente: versão do Python, se o .venv existe, se o git está configurado e qual o remoto.
3. Me digas se encontras alguma contradição entre o CLAUDE.md, as regras em .claude/rules e os documentos de domínio.
```

**Fica bem feita quando:** o Claude Code descreve o projeto corretamente, `/context` mostra o CLAUDE.md carregado e o primeiro commit (só com o kit) está no GitHub.

---

### Fase 1 — Fundações do código *(1–2 sessões)*

**Objetivo:** estrutura de pastas, dependências, configuração, modelos de dados do questionário e primeira página Streamlit vazia mas com o tema da marca.

**Prompt:**
```
Fase 1 do PLANO_IMPLEMENTACAO. Em modo de planeamento, propõe e depois executa:
- A estrutura de pastas descrita no CLAUDE.md (só com __init__.py e ficheiros mínimos).
- Python 3.14: requires-python ">=3.14" no pyproject.toml. Antes de fixar versões, confirma que todas as dependências instalam sem erros em 3.14 no Windows (pip install num ambiente limpo) e diz-me se alguma falhar.
- tests/conftest.py que salta os testes marcados "llm" se a variável VIGORIA_TESTES_LLM_REAIS não for 1. Lê a variável só de os.environ, nunca do config.py nem do .env.
- pyproject.toml (configuração do ruff e do pytest, com o marcador "llm"), requirements.txt e requirements-dev.txt com versões fixadas: streamlit[auth], pydantic, pydantic-settings, google-genai, sqlalchemy, alembic, psycopg[binary], pyyaml, plotly, httpx, tenacity, phonenumbers, babel; dev: pytest, ruff.
- src/vigoria/config.py a ler o .env com pydantic-settings.
- src/vigoria/modelos/questionario.py com o modelo Questionario completo segundo @docs/dominio/QUESTIONARIO.md, incluindo validações de intervalos. Email e telemóvel ficam fora deste modelo (pertencem ao Utilizador, na Fase 6).
- Testes que carregam @exemplos/persona_teste.json e confirmam que é válido, e testes de casos inválidos.
- app.py com página de boas-vindas "Vigoria" usando o tema de .streamlit/config.toml.
No fim, corre ruff e pytest e mostra-me como arrancar a app.
```

**Fica bem feita quando:** `python -m pytest -q` passa, `python -m streamlit run app.py` abre a página com as cores da marca e o ficheiro de persona é validado sem erros.

---

### Fase 2 — Regras determinísticas: acolhimento e estratégia *(2 sessões)*

**Objetivo:** todos os cálculos e decisões da `REGRAS_DOMINIO.md` em código puro e testado. É a fase mais importante para a segurança — vale a pena não ter pressa.

**Prompt:**
```
Fase 2. Lê com atenção @docs/dominio/REGRAS_DOMINIO.md, secções 1 a 5.
Implementa em src/vigoria/regras/:
- calculos.py: IMC e classe, limiar de cintura, intervalo de hidratação, intervalo de proteína, ritmo de perda de peso necessário vs. máximo permitido, ganho muscular máximo.
- elegibilidade.py: modo base / prudente / não elegível, com a lista de motivos.
- intensidade.py: intensidade efetiva = mínimo entre pedida, permitida e compatível com a disponibilidade, com explicação em PT-EU.
Depois src/vigoria/modelos/estrategia.py (modelo Estrategia) e src/vigoria/motor/acolhimento.py e estrategia.py, que recebem um Questionario e devolvem uma Estrategia.
Testes com casos-limite: IMC exatamente 35,0; cintura 94 e 95 em homens, 80 e 81 em mulheres; idade 17, 18, 44, 45, 60 e 61 (mudança de faixa no ritmo de perda de peso); gravidez (não gera plano); doença cardiovascular com intensidade pedida Alta (fica Média); hipertensão controlada com Alta e 7 dias × 30 min (fica Alta); doença renal sem valores de proteína nem de hidratação; uma linha de teste para cada opção da tabela 1.1; limitação ligeira vs. importante; medicação «não sei»; doença renal sem valor de proteína; disponibilidade 2 dias, 3 dias, 5 dias × 20 min e 7 dias × 30 min; persona de teste (resultado esperado descrito no campo _nota do JSON, incluindo alvo realista ≈ 88 kg à semana 16).
Usa só os valores do documento. O programa é sempre de 16 semanas: nada de meses no código.
Acrescenta um comando de linha python -m vigoria.motor.cli --so-estrategia exemplos/persona_teste.json que imprime a estratégia em texto legível.
```

**Fica bem feita quando:** todos os testes passam, o comando de linha mostra uma estratégia que o José lê e concorda («sim, era isto que eu diria a esta pessoa»).

---

### Fase 3 — Conteúdo editorial estruturado *(2 sessões, com trabalho editorial do José)*

**Objetivo:** transformar os volumes 1 a 3 em ficheiros YAML que o motor usa: biblioteca de exercícios, fases, princípios alimentares, textos obrigatórios e listas negras.

**Prompt:**
```
Fase 3. A partir de @docs/referencia/Projeto_Vitalidade_Senior_Volume_1_Manual_Geral.md, @docs/referencia/Projeto_Vitalidade_Senior_Volume_2_Caderno_de_Treino_e_Acompanhamento.md e @docs/referencia/Projeto_Vitalidade_Senior_Volume_3_Alimentacao_e_Habitos.md, cria em src/vigoria/conteudo/:
- exercicios.yaml com os campos definidos em REGRAS_DOMINIO §6 (todos os exercícios dos volumes 1 e 2, mobilidade e equilíbrio incluídos);
- fases.yaml com as 4 fases (foco de treino, foco alimentar do Vol. 3, séries, repetições, descanso);
- alimentacao.yaml com os princípios, a construção de uma refeição simples e a lista "quando a evolução abranda";
- avisos.yaml com os textos obrigatórios (REGRAS_DOMINIO §7), a lista negra e a lista de brasileirismos (§8).
Copia o texto editorial tal como está nos volumes; não reescrevas nem inventes exercícios. Aplica a resolução da Fase 4 de @docs/dominio/REGRAS_DOMINIO.md, secção 6: impacto, nível e variante-base de cada exercício segundo a tabela 6.4 (as variantes-base entram como exercícios próprios na biblioteca), parâmetros da Fase 4 da secção 6.3, nome da Fase 4 «Integração». Mostra-me no fim a tabela final de exercícios com impacto, nível e variante.
Cria src/vigoria/conteudo/carregar.py com validação Pydantic de cada ficheiro e testes que garantam que todos os exercícios referidos em fases.yaml existem na biblioteca.
```

**Fica bem feita quando:** os YAML validam, o José reviu a tabela final de exercícios e nada foi inventado face aos volumes e à tabela 6.4.

---

### Fase 4 — Motor de geração: gerador, verificação e voz *(2–3 sessões)*

**Objetivo:** plano completo gerado a partir da persona de teste, pela linha de comando, sem interface.

**O José faz:** cria a chave no AI Studio, coloca-a no `.env`, confirma no AI Studio o nome do modelo Flash disponível e atualiza `GEMINI_MODEL`.

**Prompt:**
```
Fase 4. Implementa o motor de geração conforme o CLAUDE.md (secção "Pipeline de geração"):
1. src/vigoria/llm/: interface ProvedorLLM e gemini.py com o SDK google-genai, saída JSON estruturada via schema Pydantic, tratamento de erro 429 com tenacity (espera exponencial, máximo 3 tentativas) e registo apenas de métricas (tempo, tokens), nunca de conteúdo.
2. src/vigoria/modelos/plano.py: modelo Plano (resumo, marcos às semanas 4, 8, 12 e 16, semana-tipo, treino por fase com ids de exercícios, orientação alimentar, hidratação, hábitos, indicadores de acompanhamento, notas personalizadas).
3. prompts/gerador_sistema.md (versão 1): papel, tom de voz Vigoria a partir de @docs/referencia/Vigoria_Briefing_Marca.md, regras do que a LLM pode e não pode decidir. Os números chegam calculados pela estratégia.
4. motor/gerador.py: monta o pedido com a Estrategia, os dados do questionário SEM identificadores e o excerto relevante do conteúdo YAML.
5. motor/verificacao.py com as verificações de .claude/rules/regras-e-motor.md, incluindo a rejeição de qualquer exercício que não tenha nivel: base; uma regeneração com o motivo se falhar.
6. motor/voz.py: insere os textos obrigatórios de avisos.yaml e deteta brasileirismos.
7. motor/pipeline.py que junta tudo, e o cli.py a gerar o plano em Markdown para saidas/.
Testes com a LLM simulada (respostas JSON de exemplo em tests/fixtures/), incluindo uma resposta "má" que a verificação tem de chumbar. Um único teste marcado @pytest.mark.llm que corre a sério com a persona — nunca o executes; diz-me o comando para eu o correr.
Na verificação: a regeneração passa só pelas verificações em código, sem nova revisão pela LLM (máximo de 3 chamadas).
```

**Fica bem feita quando:** os testes simulados passam; com autorização, o teste real gera um plano para a persona que o José lê de ponta a ponta e aprova como «seguro e em bom português». Comparar com o plano de validação de julho, que serve de referência de formato.

---

### Fase 5 — Interface: questionário e apresentação do plano *(2–3 sessões)*

**Objetivo:** o fluxo completo no browser, ainda sem contas (os dados vivem só na sessão). É um passo intermédio de desenvolvimento: a app nunca é publicada assim; o login obrigatório entra na Fase 6.

**Prompt:**
```
Fase 5. Constrói a interface Streamlit seguindo @docs/dominio/QUESTIONARIO.md e .claude/rules/interface-e-textos.md:
- paginas/questionario.py: passos 0 a 7, um por ecrã, barra de progresso, botões Anterior/Seguinte, respostas em st.session_state, validação ao avançar com mensagens claras em PT-EU.
- No passo 6, o telemóvel opcional segundo a secção «Contactos» do QUESTIONARIO.md: lista de países com pesquisa (Portugal +351 por omissão, nomes em pt-PT via babel) e número validado com phonenumbers; lógica de validação em src/vigoria/regras/contactos.py, com testes (número português válido, fixo recusado, internacional válido, número colado com +44, campo vazio aceite).
- No passo 7, mostrar as decisões da estratégia antes de gerar.
- paginas/plano.py: plano em separadores (Resumo, Treino, Alimentação, Hábitos, Acompanhamento), com a semana-tipo em tabela e os avisos de segurança sempre visíveis.
- Indicador de progresso durante a geração ("A preparar o seu plano…") e mensagem honesta se a quota da LLM esgotar.
- paginas/privacidade.py com um rascunho de política de privacidade, marcado como RASCUNHO.
Desenho mobile-first: constrói cada ecrã para 390 px e só depois confirma a 1280 px. Em telemóvel, tabelas largas (semana-tipo, progressão) passam a cartões empilhados.
```

**Fica bem feita quando:** o José preenche o questionário primeiro no telemóvel e depois no computador, e em ambos (mesma rede Wi-Fi: `python -m streamlit run app.py` mostra o endereço «Network URL») e obtém um plano legível sem ajuda.

---

### Fase 6 — Contas, base de dados e RGPD *(2 sessões)*

**Objetivo:** login obrigatório (Google ou email e palavra-passe, via Auth0), planos guardados por utilizador, consentimento registado, exportar e apagar conta.

**O José faz:** segue `docs/GUIA_AUTH0.md` (conta Auth0 na região europeia, aplicação, ligações Google e email/palavra-passe, língua portuguesa) e preenche `.streamlit/secrets.toml` a partir de `.streamlit/secrets.toml.example`. O Claude Code não lê esse ficheiro.

**Prompt:**
```
Fase 6. Lê a secção "Contas e acesso aos dados" do CLAUDE.md e @docs/GUIA_AUTH0.md. Implementa:
- Autenticação com st.login("auth0"); todas as páginas, exceto entrada, privacidade e termos, exigem st.user.is_logged_in.
- Bloqueio de contas com email por verificar (email_verified falso), com mensagem clara e botão para tentar de novo.
- Terminar sessão: st.logout() + redirecionamento para o logout do Auth0 (domínio e client_id vindos dos segredos).
- src/vigoria/dados/: SQLAlchemy 2.x com tabelas utilizador (sub, fornecedor, email, telemovel em E.164 opcional, criado_em), consentimento (versão do texto + data), questionario, plano (JSON + versão do prompt + modelo usado), registo_progresso. Alembic para migrações. SQLite em local, PostgreSQL via DATABASE_URL em produção.
- Criação automática do utilizador no primeiro login (pelo sub). Se o email já existir com outro sub, mostrar a mensagem definida no CLAUDE.md, sem juntar contas.
- Repositórios em que todas as funções exigem utilizador_id.
- Página "A minha conta": ver, alterar ou remover o telemóvel; planos anteriores, exportar todos os meus dados (JSON), apagar conta e dados (com confirmação dupla), e indicação de que a conta Auth0 também é apagada (via Management API ou instrução manual — propõe-me a opção).
- Garante que nenhuma resposta de saúde vai para os logs.
Testes dos repositórios com SQLite em memória, incluindo o teste de isolamento: o utilizador A não consegue ler nem alterar dados do utilizador B.
```

**Fica bem feita quando:** o José cria uma conta com Google e outra com email e palavra-passe; confirma o email da segunda; gera um plano em cada uma e confirma que nenhuma vê o plano da outra; sai, volta a entrar e encontra o seu; exporta os dados; apaga uma conta de teste e confirma que desapareceu.

---

### Fase 7 — Acompanhamento do progresso *(1–2 sessões)*

**Prompt:**
```
Fase 7. Implementa o acompanhamento segundo REGRAS_DOMINIO §9:
- paginas/progresso.py: formulário de registo (semanal ou a cada 4 semanas, conforme a escolha do utilizador), com os indicadores do Vol. 1 Anexo B e as perguntas de revisão do Vol. 3.
- Gráficos plotly de peso e cintura face à linha de objetivo do plano; sessões e minutos de cardio por semana.
- Lógica em src/vigoria/regras/progresso.py: período em falta, evolução abaixo do esperado em 2 períodos seguidos ⇒ mostrar a lista "Quando a evolução abranda", sem tom de culpa.
- Opção para ligar/desligar o acompanhamento e mudar a frequência.
```

**Fica bem feita quando:** com registos fictícios de 6 semanas, os gráficos fazem sentido e a sugestão aparece quando deve.

**Demonstração online (opcional, entre as Fases 5 e 7).** Para mostrar a app a algumas pessoas antes do Railway, pode publicar-se no Streamlit Community Cloud, seguindo `docs/GUIA_AUTH0.md`, secção 7. Só com dados fictícios ou a persona de teste: os servidores ficam nos EUA, o disco é temporário e não há tarefas agendadas. Prompt para preparar o código:
```
Prepara a app para correr também no Streamlit Community Cloud: config.py deve ler as variáveis primeiro do ambiente/.env e, em alternativa, de st.secrets; com AMBIENTE=demo, mostrar em todas as páginas uma faixa "Versão de demonstração — não introduza dados reais de saúde". Não alteres o comportamento em local nem no Railway.
```

---

### Fase 8 — Lembretes por email *(1–2 sessões)*

**O José faz:** cria conta na Brevo, valida o domínio ou o endereço remetente e coloca a chave no `.env`.

**Prompt:**
```
Fase 8. Implementa:
- src/vigoria/notificacoes/brevo.py (API transacional via httpx) e modelos de email em PT-EU sem dados de saúde, com ligação para desativar lembretes.
- src/vigoria/tarefas/lembretes.py, executável com python -m vigoria.tarefas.lembretes, que encontra registos em falta segundo REGRAS_DOMINIO §9, envia no máximo 2 lembretes por período e regista o envio para não repetir.
- Modo --simular que mostra quem receberia o quê, sem enviar.
- Instruções para configurar este comando como serviço agendado no Railway (diário, 9h de Lisboa).
```

**Fica bem feita quando:** o modo de simulação lista os destinatários certos e um envio real chega à caixa do José.

---

### Fase 9 — Exportação do plano *(1 sessão)*

**Prompt:**
```
Fase 9. Gera o plano em PDF a partir do modelo Plano, com a identidade da marca (cores do config.toml, letra Calibri ou equivalente livre), capa com nome Vigoria e data, semana-tipo e progressão por fase (semanas 1–4, 5–8, 9–12, 13–16) em tabela, avisos no fim. Botão de descarga na página do plano. Testa com a persona e mostra-me o PDF.
```

**Fica bem feita quando:** o PDF se imprime bem em A4 e se lê no telemóvel.

---

### Fase 10 — Publicação e beta fechado *(2 sessões + 3–4 semanas de beta)*

**Prompt:**
```
Fase 10. Prepara a publicação no Railway:
- Dockerfile (imagem python:3.14-slim) e .dockerignore. O Streamlit corre numa porta interna (8501) e o Caddy à frente, na porta $PORT do Railway.
- Camada PWA em pwa/: manifest.webmanifest (nome Vigoria, cores da marca, display standalone, idioma pt-PT), ícones 192/512 px e versão maskable a partir de um ícone provisório, sw.js mínimo (só cache dos ficheiros estáticos e página offline; nunca cache das respostas da app nem de dados), página offline em PT-EU, e Caddyfile que serve estes ficheiros na raiz, injeta a ligação ao manifesto e as meta-tags de ecrã inicial do iPhone no HTML do Streamlit, e encaminha o resto (incluindo websockets) para o Streamlit.
- Testa em local com docker e diz-me como confirmo que é instalável (no Chrome: separador Application → Manifest).
- Migrações Alembic automáticas no arranque.
- Lista de verificação do que tenho de configurar no painel do Railway: região europeia, PostgreSQL, variáveis de ambiente, segredos da autenticação, URLs de callback e de logout do domínio público no Auth0, cliente OAuth Google próprio no Auth0 (não as chaves de teste), envio de emails do Auth0 pela Brevo, serviço agendado dos lembretes.
- Página "Sobre" com a versão da app e do prompt.
Não faças push nem publiques sem eu confirmar cada passo.
```

**Beta:** 5 a 10 pessoas de perfis diferentes (idades, condições, objetivos), durante 3 a 4 semanas. Recolher: onde hesitaram no questionário, se o plano pareceu pessoal, se alguma recomendação pareceu desadequada, se registaram o progresso. Cada problema encontrado vira uma linha no ESTADO.md e, se for repetível, uma regra no CLAUDE.md ou um teste.

**Fica bem feita quando:** a app está acessível pelo endereço público, se instala no ecrã inicial de um Android e de um iPhone e abre em ecrã inteiro, os testadores conseguem completar o ciclo sem ajuda e não há nenhum plano considerado inseguro.

---

## 6. Depois do MVP (por ordem sugerida)

1. Passagem do Gemini ao nível pago e revisão jurídica da política de privacidade — **condições para abrir ao público**.
2. Reajuste do plano com base no progresso (o «repetir o prompt periodicamente» do Prompt Universal, agora automático no fim de cada fase de 4 semanas).
3. Manual de utilizador independente da aplicação.
4. Groq como reserva automática quando o Gemini falhar.
5. Entrada sem palavra-passe por código enviado para o email (o Auth0 já o suporta), pensada para quem se esquece de palavras-passe.
6. Vídeos ou ilustrações dos exercícios.
7. Publicidade, com regras: nada de segmentação por dados de saúde, nada de anúncios a suplementos ou produtos da lista negra.

## 7. Tarefas em paralelo (fora do código)

- Registo dos domínios e pesquisa no INPI.
- Revisão dos valores das `REGRAS_DOMINIO.md` por um profissional de saúde.
- Recrutamento dos testadores do beta.

## 8. Esforço indicativo

Entre 18 e 25 sessões de trabalho de 1 a 2 horas, ou seja, 6 a 10 semanas a um ritmo de duas a três sessões por semana, mais o beta. As fases 2, 3 e 4 são as que mais dependem de decisões do José; atrasos aí são normais e desejáveis — é onde está a qualidade do produto.
