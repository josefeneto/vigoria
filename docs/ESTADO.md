# Estado do projeto Vigoria

> Atualizado pelo Claude Code no fim de cada fase (e sempre que um prompt mudar de versão). Mais recente em cima.

## Fase atual

**Fase 4 — Motor de geração: parte 1 concluída a 29/10/2026.** `motor/selecao.py` (exercícios permitidos por fase, REGRAS §6.6), `llm/base.py` (interface `ProvedorLLM`, só métricas nos registos) e `llm/gemini.py` (google-genai, JSON por schema Pydantic, 429 repetido com tenacity até 3 tentativas), `modelos/plano.py` (`PlanoGerado` da LLM, sem números; `Plano` final com os números da Estrategia e os avisos), `prompts/gerador_sistema.md` v1 e `motor/gerador.py` (pedido e montagem do plano). Nova persona fictícia `persona_osteoporose.json`. CLI com `--so-pedido` (mostra o pedido sem chamar a LLM). Testes só com a LLM simulada. Revisão (29/10): regra das zonas por gravidade, campo `de_pe` e limpeza do texto livre. **Por fazer:** o José correr o teste real (`test_gerador_llm_real.py`); parte 2: `motor/verificacao.py` (verificações em código + revisão crítica), regeneração única e `motor/voz.py`.

**Anterior — Fase 3 — Conteúdo editorial: concluída a 28/10/2026.** Parte 1: `exercicios.yaml` (45 exercícios), `fases.yaml` (4 fases e estrutura da sessão) e `regras/regressao.py` (§6.6). Parte 2: `alimentacao.yaml` (Vol. 3: princípios, refeição simples, «quando a evolução abranda») e `avisos.yaml` (todos os textos das regras, com id; obrigatórios de §7; lista negra e brasileirismos de §8). `regras/textos.py` passou a ler os textos de `avisos.yaml`, sem mudar uma palavra (fotografias da CLI das 4 personas e de todos os textos em `tests/fixtures/`). `carregar_conteudo()` carrega e valida os 4 ficheiros. Próximo passo: Fase 4 (motor de geração).

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
- 28/10/2026 — Ferramentas Python sempre com `python -m` (`python -m pytest`, `python -m ruff`, `python -m streamlit run app.py`, `python -m pip`): o Smart App Control do Windows bloqueia os executáveis do `.venv`. Atualizados CLAUDE.md, README, guia de arranque, plano, regras e `.claude/settings.json`.
- 28/10/2026 — Git: só o ramo `main`, sem ramos por fase; commits pequenos, um ou mais por fase; lint e testes têm de passar antes de cada commit; push só depois de o José confirmar.
- 27/10/2026 — Questionário: halteres como `"halteres"` + campo `halteres_kg`; refeições com as cinco chaves fixas e texto vazio = «não faz»; o modelo aceita gravidez (é a estratégia, na Fase 2, que impede o plano); campos começados por «_» são ignorados e campos desconhecidos são rejeitados.
- 28/10/2026 — Fase 2 (registadas na REGRAS_DOMINIO): marcos de peso lineares com o ritmo usado (iguais ao objetivo depois de o atingir), cintura sem número (só o limiar como referência), marcos de força pela LLM; nova pergunta «Em que articulações?» (`dor_articular_zonas`, `dor_articular_outra`) para a dor articular persistente; incoerências nos objetivos como avisos (peso-alvo com IMC < 18,5 limitado a IMC 18,5; cintura-alvo ≥ atual; peso-alvo ≥ atual).
- 28/10/2026 — Revisão da estratégia da persona: aviso de disponibilidade separado para 1 e 2 dias; no MVP, sem impacto para todos (REGRAS §6.3, ponto 6); equilíbrio com apoio só segundo a tabela 1.1; `.gitattributes` com `* text=auto eol=lf` (quebras de linha LF no repositório).
- 28/10/2026 — Fase 3, parte 2: lista negra em termos (verificados pelo código, palavra inteira) e ideias (revisão pela LLM), para o aviso de diabetes («jejum prolongado») não chumbar; «baixar» só como brasileirismo no sentido de descarregar (REGRAS §8). `Zona` passou para `modelos/zonas.py` (evita um ciclo de importações). Alterar um texto de `avisos.yaml` muda a saída da CLI: atualizar as fotografias em `tests/fixtures/`.
- 28/10/2026 — Fase 3, parte 1: mantêm-se `impacto` (baixo/medio/alto) e `nivel` (base/intermedio/avancado) de §6.1; novos campos `zonas`, `flexao_tronco_carga` (só o crunch) e `apoio_equilibrio`; zonas e regressões aprovadas; regra de aplicação das regressões (REGRAS §6.6); aquecimento, cardio finalizador e retorno à calma em `fases.yaml`; corrida estática e Tai Chi fora da biblioteca; esforço 3–6 em todas as fases (o V2 só dá esse valor). Dois pontos «A CONFIRMAR» na REGRAS (osteoporose de risco elevado; Tai Chi).
- 29/10/2026 — Fase 4, parte 1: uma regressão pode ser usada em qualquer fase, mesmo com `fase_minima` posterior (REGRAS §6.6, ponto 4); ordem dos filtros da seleção e filtro de equipamento (halteres, passadeira e elíptica só se declarados; cadeira, parede, bancada e degrau existem em casa); «regressão geral» = um passo na cadeia, sem limite de esforço. `Restricoes` ganha `contraindicacoes` (condições e zonas escolhidas) e `equipamento`. Nota «Sempre com apoio por perto» em `avisos.yaml` (`apoio_por_perto`). A LLM devolve `PlanoGerado`, sem campos para peso, proteína ou hidratação; o código junta os números. Com `sem_intervalos`, o prompt manda usar ritmo contínuo também no cardio finalizador (a verificação da parte 2 tem de o confirmar).
- 29/10/2026 — Revisão da Fase 4, parte 1: (1) regra das zonas por gravidade (REGRAS §6.6, «A CONFIRMAR»). Limitação ligeira: no máximo um passo, só nos exercícios de fase 2 a 4; fase 1 e cardio mantêm-se, sem limite de esforço, com «amplitude confortável, sem dor». Dor articular persistente **e limitação importante**: regra completa. O questionário já distinguia as duas situações (gravidade em 1.H; zonas da dor em «Em que articulações?»); só a `Estrategia` mudou: `zonas_regressao` (completa) e `zonas_regressao_ligeira`. A linha das zonas na CLI mudou e as fotografias foram atualizadas. (2) Campo `de_pe` obrigatório em todos os exercícios; com equilíbrio com apoio, o motor põe a nota de apoio em todos os de pé (as inclinadas contam como de pé). (3) Texto livre: emails e números de telefone (9 ou mais algarismos) passam a «[removido]» e o total dos campos fica limitado a 500 caracteres, antes de montar o pedido. O prompt não mudou (continua na versão 1).
- 24/10/2026 — Demonstrações online possíveis no Streamlit Community Cloud (`AMBIENTE=demo`), só com dados fictícios; beta com pessoas reais apenas no Railway (UE).

## Decisões pendentes

Nenhuma decisão de domínio pendente. Os valores das regras de domínio aguardam revisão por um profissional de saúde antes do beta.

## Registo das fases

| Fase | Estado | Data | Notas |
|---|---|---|---|
| 0 — Ambiente | concluída | 26/10/2026 | |
| 1 — Fundações | concluída | 27/10/2026 | 51 testes; letra base de 17 px no tema |
| 2 — Regras determinísticas | concluída | 28/10/2026 | 262 testes. Persona: versão-base, Média, esforço percebido, módulo visceral, alvo realista 88 kg à semana 16 (85 kg por volta da semana 24), regressão nos joelhos, sem impacto. Textos novos em `regras/textos.py` até à Fase 3 |
| 3 — Conteúdo editorial | concluída | 28/10/2026 | 854 testes. Biblioteca: 24 de força base, 4 de cardio base, 6 de mobilidade e equilíbrio, 11 avançados. 48 textos em `avisos.yaml` (mais os rótulos); CLI das 4 personas igual à fotografia |
| 4 — Motor de geração | em curso | 29/10/2026 | Parte 1 concluída e revista: 957 testes (sem LLM real). Pedido da persona de teste: cerca de 50 KB |
| 5 — Interface | por iniciar | | |
| 6 — Contas e dados | por iniciar | | |
| 7 — Acompanhamento | por iniciar | | |
| 8 — Lembretes | por iniciar | | |
| 9 — Exportação | por iniciar | | |
| 10 — Publicação e beta | por iniciar | | Definir `STREAMLIT_SERVER_HEADLESS=true` no Railway (em local, o config.toml tem `headless = false` para abrir o browser) |

## Versões dos prompts

| Ficheiro | Versão | Data | Alteração |
|---|---|---|---|
| `prompts/gerador_sistema.md` | 1 | 29/10/2026 | Primeira versão: papel, tom de voz (briefing), o que a LLM pode e não pode decidir, intensidades da alimentação (§3), indicadores (§9), texto livre só como contexto. Teste real com a persona por correr (José) |
