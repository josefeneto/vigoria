# Questionário da Vigoria — especificação para o formulário

> Traduz o Prompt Universal v2 (`docs/referencia/Prompt_Universal_Saude_Vitalidade_v2.md`) em campos de formulário e no modelo Pydantic `Questionario`.
> Diferenças face ao Prompt v2 (decisões de 25/10/2026): o campo 5.D (duração em meses) desaparece — o programa tem sempre 16 semanas; em 6.B, «mensal» passa a «a cada 4 semanas»; a gravidez impede a geração do plano.
> Os passos agrupam secções do Prompt por tema; prevalece esta organização. Máximo de cerca de 6 perguntas por ecrã; se um passo crescer, divide-se em subpassos.
> Regra geral: preferir escolhas fechadas a texto livre. Texto livre só onde o contexto pessoal importa, e com limite de caracteres.

## Antes do passo 0 — Entrar ou criar conta

Página de entrada com o botão «Entrar ou criar conta», que abre a página do Auth0 com duas opções: «Continuar com Google» ou email e palavra-passe. Não há formulário de registo na app: a conta é criada no primeiro login. Quem escolher email e palavra-passe tem de confirmar o email antes de continuar (a app mostra «Confirme o seu email — enviámos-lhe uma ligação»).

## Passo 0 — Boas-vindas e consentimento (antes de qualquer dado de saúde)

| Campo | Tipo | Obrigatório | Notas |
|---|---|---|---|
| `aceita_termos` | caixa | sim | Termos de utilização + política de privacidade (ligações) |
| `consentimento_saude` | caixa | sim | Consentimento explícito para tratar dados de saúde com a finalidade de gerar e acompanhar o plano (RGPD art. 9.º, n.º 2, al. a) |
| `confirma_maior_idade` | caixa | sim | Bloqueia se não marcada |

Data e versão do texto de consentimento ficam registadas.

## Passo 1 — Sobre si (Prompt 1.A–1.G)

Números pedidos sem casas decimais (decidido a 31/10/2026): não se exige esse rigor a quem responde (cintura 113 chega). Os cálculos internos continuam com decimais. A única exceção são as bebidas espirituosas, escolhidas de uma lista com vírgula decimal.

| Campo | Prompt | Tipo | Validação |
|---|---|---|---|
| `sexo` | 1.A | escolha: masculino / feminino | obrigatório (necessário para os limiares de cintura) |
| `idade` | 1.B | inteiro | 18–100 |
| `altura_cm` | 1.C | inteiro | 120–220 |
| `peso_kg` | 1.D | inteiro na interface | 35–250 |
| `sono_horas` | 1.E | inteiro na interface | 3–12 |
| `cintura_cm` | 1.F | inteiro na interface | 50–200; ajuda com «como medir» (ao nível do umbigo, a expirar, fita sem apertar) |
| `atividade_atual` | 1.G | escolha: sedentário / ligeiro / moderado / ativo | descrição curta de cada opção |

Ao concluir o passo, mostrar o IMC calculado com uma frase de contexto (nunca alarmista).

## Passo 2a — Saúde (4.A–4.D)

| Campo | Prompt | Tipo | Notas |
|---|---|---|---|
| `condicoes` | 4.A–4.C | escolha múltipla | hipertensão; diabetes; doença cardiovascular; doença respiratória; doença renal; osteoporose; doença inflamatória intestinal; dor articular persistente; prótese articular ou cirurgia nos últimos 6 meses; gravidez; nenhuma; outra. Consequência de cada uma: REGRAS_DOMINIO §1.1 |
| — | 4.C | regra | Se `gravidez` for escolhida, o questionário para de imediato e mostra: «A Vigoria não é recomendável para situações de gravidez.», com uma sugestão cordial de falar com o médico ou obstetra. Os dados já introduzidos não são guardados. |
| `condicoes_controladas` | 4.A | sim / não, só para hipertensão, diabetes e doença inflamatória intestinal | «Está controlada com o tratamento atual?» |
| `osteoporose_risco` | 4.A | sim / não / não sei, só se escolher osteoporose | «Já teve alguma fratura por fragilidade, ou o seu médico indicou risco elevado de fratura?» («não sei» = sim) |
| `dor_articular_zonas` | 4.A | escolha múltipla, só se escolher dor articular persistente (pelo menos uma) | «Em que articulações?»: joelhos, ancas, ombros, coluna, outra. Regressão nas zonas indicadas; «outra» aplica regressão geral (REGRAS_DOMINIO §1.1). Decisão de 28/10/2026 |
| `dor_articular_outra` | 4.A | texto (200), só se escolher «outra» nas articulações | o texto nunca é interpretado pelo motor; segue para a LLM só como contexto |
| `condicoes_outras` | 4.B | texto (200), só se escolher «outra» | «outra» leva sempre a modo prudente; o texto nunca é interpretado pelo motor |
| `medicacao_afeta_fc` | 4.D | sim / não / não sei | pergunta simples: «Toma medicação para o coração ou tensão que baixe o ritmo cardíaco (ex.: betabloqueantes)?» («não sei» = sim) |
| `medicacao_notas` | 4.D | texto (200), opcional | |

## Passo 2b — Limitações (1.H)

| Campo | Prompt | Tipo | Notas |
|---|---|---|---|
| `limitacoes` | 1.H | escolha múltipla | joelhos, ancas, ombros, coluna, equilíbrio, outra, nenhuma |
| `limitacoes_gravidade` | 1.H | por limitação: ligeira / importante | ligeira = «incomoda, mas não me impede de fazer o dia a dia»; importante = «impede ou limita atividades do dia a dia» |
| `limitacoes_outra` | 1.H | texto (200), só se escolher «outra» | «outra» leva sempre a modo prudente (REGRAS_DOMINIO §1.1) |

## Passo 3 — Exercício (1.I–1.K)

| Campo | Prompt | Tipo |
|---|---|---|
| `equipamento` | 1.I | escolha múltipla: nenhum, bandas elásticas, halteres (indicar kg), step, elíptica, passadeira, cadeira firme, outro |
| `dias_semana` | 1.J | inteiro 1–7 |
| `minutos_dia` | 1.J | escolha: 15 / 20 / 30 / 45 / 60 |
| `preferencias` | 1.K | escolha múltipla: caminhada, Tai Chi, dança, força, natação, outro |

## Passo 4a — Refeições (2.A–2.F)

Para não cansar, cada refeição tem escolhas rápidas + campo opcional:

| Campo | Prompt | Tipo |
|---|---|---|
| `refeicoes` | 2.A–2.E | por refeição: faz/não faz + texto curto opcional (150). Marcada sem descrição: segue para a LLM como «faz esta refeição (sem descrição)», que dá uma sugestão geral (decisão de 31/10/2026) |
| `restricoes_alimentares` | 2.F | escolha múltipla (vegetariano, sem lactose, sem glúten, outra) + texto |

## Passo 4b — Bebidas e consumos (3.A–3.E)

| Campo | Prompt | Tipo |
|---|---|---|
| `agua_litros` | 3.A | escolha: < 0,5 / 0,5–1 / 1–1,5 / 1,5–2 / > 2 |
| `bebidas_acucaradas_litros` | 3.B | escolha: nenhuma / < 0,33 / 0,33–1 / > 1 |
| `vinho_copos_dia` | 3.C | inteiro 0–10 |
| `espirituosas_dl_dia` | 3.D | lista de 0 a 5 dl, de 0,5 em 0,5 (com vírgula); um cálice ≈ 0,4 dl |
| `pao_por_dia` | 3.E | escolha: nenhum / 1 / 2 / 3 / 4 ou mais (fatias ou papos-secos) |
| `doces_por_semana` | (Vol. 3) | inteiro 0–14 |

## Passo 5 — Objetivos (5.A–5.E)

| Campo | Prompt | Tipo | Notas |
|---|---|---|---|
| `peso_alvo_kg` | 5.A | inteiro na interface | aviso imediato se o ritmo necessário em 16 semanas ultrapassar o limite da faixa etária (REGRAS_DOMINIO §2), com o alvo realista para a semana 16 |
| `cintura_alvo_cm` | 5.B | inteiro na interface, opcional | |
| `objetivo_muscular` | 5.C | escolha: «aumentar força e tónus» / valor em kg inteiros (1 ou 2) | máximo aceite: 2 kg; mostrar a nota «até 0,5 kg por cada 4 semanas» |
| — | 5.D | informação | Sem pergunta: o ecrã explica que o programa tem **16 semanas**, em 4 fases de 4 semanas, seguidas de manutenção |
| `intensidade_pedida` | 5.E | escolha: ligeira / média / alta | cartões com a descrição da secção 7 do Prompt |

## Passo 6 — Acompanhamento (6.A–6.C)

| Campo | Prompt | Tipo | Por omissão |
|---|---|---|---|
| `acompanhamento_ativo` | 6.A | sim/não | **sim** (recomendado) |
| `frequencia_registo` | 6.B | semanal / a cada 4 semanas | semanal |
| `lembretes_email` | 6.C | sim/não | sim |

O telemóvel (1.M) não é pedido no MVP (decisão de 31/10/2026): ver «Contactos».

## Contactos (1.L e 1.M)

- `email` (1.L): vem da autenticação (Auth0, seja Google ou email e palavra-passe); não se pede de novo.
- `telemovel` (1.M): **não recolhido no MVP** (decisão de 31/10/2026): os lembretes são só por email e, por minimização de dados (RGPD), não se pede o que não se usa. A especificação abaixo fica para quando houver lembretes por SMS ou WhatsApp, que exigirão consentimento próprio.
- Especificação futura do telemóvel: **opcional**, pedido no passo 6 e editável ou removível em «A minha conta».
  - Dois campos lado a lado: lista de países com bandeira, nome em português e indicativo (ex.: «🇵🇹 Portugal +351»), com pesquisa por escrita; por omissão, **Portugal (+351)**. A seguir, Portugal; depois os restantes por ordem alfabética.
  - Lista gerada pela biblioteca `phonenumbers` (indicativos; saiu das dependências a 31/10/2026 e volta a entrar nessa altura) e `babel` (nomes dos países em pt-PT), não escrita à mão.
  - Validação com `phonenumbers`: tem de ser um número de telemóvel válido para o país escolhido (em Portugal, 9 algarismos a começar por 9). O utilizador pode escrever com ou sem espaços; se colar um número com `+` ou `00`, o país é detetado automaticamente.
  - Guardado no formato internacional E.164 (ex.: `+3519XXXXXXXX`) e apresentado no formato nacional legível (ex.: «912 345 678»).
  - Texto junto ao campo: «Opcional. Usamos o seu telemóvel apenas para contacto sobre a sua conta e, no futuro, se o ativar, para lembretes por SMS ou WhatsApp. Nunca o partilhamos.»
  - Faz parte do modelo `Utilizador`, não do `Questionario`. Nunca enviado à LLM nem incluído em exportações do plano (PDF); incluído na exportação dos dados da conta (RGPD).

## Passo 7 — Revisão

Resumo de todas as respostas, editável por secção, e botão «Gerar o meu plano». Antes de gerar, a estratégia (determinística) mostra as decisões que tomou: intensidade efetiva, módulos ativos, avisos — para que nada no plano apareça de surpresa.
