# Estado do projeto Vigoria

> Atualizado pelo Claude Code no fim de cada fase (e sempre que um prompt mudar de versão). Mais recente em cima.

## Fase atual

**Fase 1 — Fundações do código: concluída a 27/10/2026.** Estrutura de pastas, dependências fixadas (testadas em Python 3.14 no Windows), `config.py`, modelo `Questionario` com validações e testes, página de boas-vindas com o tema da marca. Próximo passo: Fase 2 (regras determinísticas).

## Decisões tomadas

- 22/10/2026 — Stack: Python 3.14 + Streamlit + Gemini (Flash) + SQLite/PostgreSQL + Railway. Sem CrewAI no MVP: pipeline de 5 papéis com 3 determinísticos e no máximo 3 chamadas à LLM por plano.
- 24/10/2026 — Autenticação via Auth0 (`st.login("auth0")`): Google ou email e palavra-passe, login obrigatório antes do questionário, utilizador identificado pelo `sub`. Plano gratuito do Auth0 (até 25 000 utilizadores ativos/mês). Substitui a decisão de 22/10 (só Google).
- 22/10/2026 — Email de lembretes via Brevo (empresa europeia, plano gratuito de 300 emails/dia).
- 22/10/2026 — Nenhum dado identificativo é enviado à LLM.
- 24/10/2026 — Python 3.14 (versão instalada). CrewAI não suporta oficialmente 3.14, mas não é usado no MVP.
- 24/10/2026 — PWA desde o início: desenho mobile-first; camada PWA (Caddy + manifest + service worker) à frente do Streamlit no Railway. Sem modo offline.
- 25/10/2026 — Regras de domínio fechadas: gravidez fora do âmbito; teto «Média» em modo prudente (que condições levam a modo prudente: REGRAS §1.1); proteína 1,0–1,2 g/kg em todas as idades; perda de peso máxima 0,4 / 0,5 / 0,6 %/semana (61+ / 45–60 / 18–44); programa sempre de 16 semanas, sem meses; Fase 4 do Vol. 2 resolvida com variantes-base (REGRAS_DOMINIO §6); prazos dos lembretes confirmados.
- 25/10/2026 — Volume 2 em Word revisto segundo REGRAS_DOMINIO §6 (variantes-base nas tabelas, avançadas por baixo, Fase 4 «Integração», cardio finalizador sem corrida).
- 25/10/2026 — Telemóvel opcional: Portugal (+351) por omissão, outros países por lista com indicativos; validado e guardado em E.164; sem SMS/WhatsApp no MVP.
- 25/10/2026 — Ajustes após a revisão da Fase 0 pelo Claude Code: tabela de condições e limitações (REGRAS §1.1), sem variantes avançadas no MVP, disponibilidade → intensidade, contactos fora do Questionario, máximo de 3 chamadas à LLM clarificado, testes com a LLM real só pelo José.
- 26/10/2026 — Segunda revisão do Claude Code (pontos A–H): CLI só autorizada com --so-estrategia; conftest lê só os.environ; verificação só aceita `nivel: base`; «outra» ⇒ prudente; hidratação e proteína com doença renal/cardiovascular; proteína nunca acima de 1,2 g/kg; subpassos 2a/2b e 4a/4b; regra de .env simplificada.
- 27/10/2026 — Git: trabalho direto no `main`, sem ramos por fase (simplicidade).
- 27/10/2026 — Questionário: halteres como `"halteres"` + campo `halteres_kg`; refeições com as cinco chaves fixas e texto vazio = «não faz»; o modelo aceita gravidez (é a estratégia, na Fase 2, que impede o plano); campos começados por «_» são ignorados e campos desconhecidos são rejeitados.
- 24/10/2026 — Demonstrações online possíveis no Streamlit Community Cloud (`AMBIENTE=demo`), só com dados fictícios; beta com pessoas reais apenas no Railway (UE).

## Decisões pendentes

Nenhuma decisão de domínio pendente. Os valores das regras de domínio aguardam revisão por um profissional de saúde antes do beta.

## Registo das fases

| Fase | Estado | Data | Notas |
|---|---|---|---|
| 0 — Ambiente | concluída | 26/10/2026 | |
| 1 — Fundações | concluída | 27/10/2026 | 51 testes; letra base de 17 px no tema |
| 2 — Regras determinísticas | por iniciar | | Persona de teste deve disparar o aviso de realismo (94 → 85 kg em 16 semanas excede 0,4 %/semana; alvo realista ≈ 88 kg) |
| 3 — Conteúdo editorial | por iniciar | | Variantes da Fase 4 definidas em REGRAS_DOMINIO §6.4 |
| 4 — Motor de geração | por iniciar | | |
| 5 — Interface | por iniciar | | |
| 6 — Contas e dados | por iniciar | | |
| 7 — Acompanhamento | por iniciar | | |
| 8 — Lembretes | por iniciar | | |
| 9 — Exportação | por iniciar | | |
| 10 — Publicação e beta | por iniciar | | Definir `STREAMLIT_SERVER_HEADLESS=true` no Railway (em local, o config.toml tem `headless = false` para abrir o browser) |

## Versões dos prompts

| Ficheiro | Versão | Data | Alteração |
|---|---|---|---|
| — | — | — | — |
