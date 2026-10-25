# Regras de domínio da Vigoria

> Fonte única dos valores, limiares e decisões que o motor aplica. Derivado do Prompt Universal v2 e dos volumes 1 a 3 do Projeto Vitalidade Sénior, com as decisões do José de 25/10/2026.
> Tudo o que aqui está é calculado em `src/vigoria/regras/` — **nunca** pela LLM.
> Quando este documento e os volumes de referência divergirem, prevalece este documento. O Volume 2 já foi revisto para coincidir com a secção 6.
> As decisões estão tomadas, mas os valores ainda não foram revistos por um profissional de saúde. Essa revisão é condição para o lançamento público.

---

## 1. Âmbito e elegibilidade

| Situação | Decisão do motor |
|---|---|
| Idade < 18 | Não gera plano. Mensagem: «A Vigoria destina-se a maiores de 18 anos.» |
| Gravidez declarada (4.C) | Não gera plano. Mensagem: «A Vigoria não é recomendável para situações de gravidez.» Acrescenta uma frase cordial a sugerir que fale com o seu médico ou obstetra sobre atividade física nesta fase. |
| IMC < 35 e sem condições sinalizadas | Versão-base. Todas as intensidades disponíveis. |
| IMC ≥ 35 kg/m² | **Modo prudente**: intensidade efetiva máxima «Ligeira», sem exercícios de impacto, aviso destacado de orientação individualizada antes de iniciar. (Critério editorial do Vol. 1: cerca de 40 % acima de 24,9; não é um limite médico universal.) |
| Doença cardiovascular, hipertensão não controlada, diabetes, doença respiratória relevante, doença renal, osteoporose com risco de fratura, dor persistente ou limitação funcional importante | **Modo prudente**: intensidade efetiva máxima «Média», sem intervalos nem exercícios de impacto, aviso destacado de orientação individualizada antes de iniciar (Vol. 1). |
| Hipertensão controlada com medicação | Versão-base, mas qualquer intensificação (intervalos, ritmo vigoroso) exige nota de validação médica prévia. |
| Medicação que altera a resposta cardíaca (ex.: betabloqueantes) | Intensidade por escala de esforço percebido e teste da fala; o plano **não** usa a frequência cardíaca como referência. |

Se se aplicarem várias linhas, vale a mais restritiva.

Deteção das condições: a partir de escolhas fechadas no questionário (lista de condições comuns + «outra»), nunca por interpretação livre de texto. O texto livre vai para a LLM apenas como contexto; quando contém algo que o motor não reconhece, aplica-se o modo prudente por defeito.

## 2. Cálculos

| Indicador | Fórmula / regra | Origem |
|---|---|---|
| IMC | peso (kg) / altura (m)², arredondado a 1 casa decimal | Vol. 1 |
| Classe de IMC | < 18,5 baixo peso; 18,5–24,9 normal; 25–29,9 excesso de peso; 30–34,9 obesidade I; ≥ 35 fora da versão-base | Vol. 1 / OMS |
| Cintura de risco | > 94 cm (H) ou > 80 cm (M) ⇒ ativa o módulo de gordura visceral | Prompt v2, 1.F |
| Hidratação diária | 25 a 35 ml × peso (kg); valor central 30 ml/kg; mostrar o intervalo | Prompt v2, ponto 4 |
| Proteína diária | 1,0 a 1,2 g × peso (kg), em todas as idades | Prompt v2, ponto 3; decisão de 25/10 |
| Proteína com doença crónica | até 1,5 g/kg, sempre com nota de acompanhamento clínico | Prompt v2, ponto 3 |
| Proteína por refeição principal | 25 a 30 g | Prompt v2 (metodologia) |
| Ganho de massa muscular | máximo 0,5 kg por cada 4 semanas (cerca de 2 kg nas 16 semanas), em qualquer intensidade | Prompt v2, 5.C |
| Ritmo máximo de perda de peso | **0,4 %** do peso atual por semana a partir dos 61 anos; **0,5 %**/semana entre os 45 e os 60; **0,6 %**/semana entre os 18 e os 44 | Decisão de 25/10 |

**Realismo dos objetivos.** O motor calcula o ritmo necessário: `(peso atual − peso-alvo) / 16 semanas`. Se ultrapassar o máximo da faixa etária, o plano não promete o objetivo: propõe um alvo realista para a semana 16 (peso atual − ritmo máximo × 16) e estima em quantas semanas o objetivo completo seria alcançável. O mesmo para o ganho muscular pedido em 5.C. É o tom «direto e honesto» do briefing aplicado a números.

Exemplo (persona de teste, 68 anos, 94 kg → 85 kg): ritmo máximo 0,4 % × 94 ≈ 0,38 kg/semana ⇒ alvo realista à semana 16 ≈ 88 kg; objetivo de 85 kg estimado para cerca da semana 24.

## 3. Intensidade

| Nível | Alimentação | Álcool | Exercício |
|---|---|---|---|
| **Ligeira** | pão ao pequeno-almoço e numa refeição adicional, porção moderada; doces até 2×/semana; refrigerantes só ocasionalmente | reduzir cerca de 1/3 | 3 sessões/semana (caminhada + força ligeira + Tai Chi ou alongamentos) |
| **Média** | pão só ao pequeno-almoço; doces até 1×/semana; refrigerantes eliminados | reduzir para metade | 4 a 5 sessões/semana (força, cardio, flexibilidade) |
| **Alta** | pão eliminado ou mínimo ao pequeno-almoço; sem doces; só água | eliminar | diário, progressão de carga/volume a cada 2 semanas |

**Intensidade efetiva** = a menor entre: a pedida (5.E), o máximo permitido pela secção 1 e a compatível com a disponibilidade declarada (1.J). Se for reduzida, o plano explica porquê numa frase.

## 4. Módulo de gordura visceral

Ativa quando a cintura ultrapassa o limiar da secção 2. O plano:
- reforça a componente aeróbia (caminhada mais rápida, intervalos ligeiros de ritmo alternado, elíptica ou passadeira) — intervalos só se a secção 1 o permitir;
- reduz mais os açúcares refinados e o álcool;
- explica, numa frase, que a gordura visceral tende a reduzir-se proporcionalmente mais depressa do que a subcutânea com o mesmo plano;
- **não** recomenda produtos, chás ou suplementos «queima-gordura»;
- com hipertensão ou doença cardiovascular, exige validação médica antes de qualquer intensificação.

Nota obrigatória (Vol. 1): o perímetro da cintura é um indicador de adiposidade central; não mede diretamente a gordura visceral.

## 5. Estrutura temporal e progressão

- **Tudo em semanas.** O programa tem sempre **16 semanas**; o questionário não pergunta a duração. Objetivos, marcos e registos contam-se em semanas, nunca em meses.
- 4 fases: Adaptação (semanas 1–4), Construção (5–8), Consolidação (9–12), Integração (13–16).
- Marcos de objetivos no fim de cada fase: semanas 4, 8, 12 e 16 (peso indicativo, cintura, marcos de força ou resistência).
- A partir da semana 17: manutenção (Vol. 1) — 2 a 3 sessões de força por semana, atividade aeróbia regular, equilíbrio e mobilidade. O utilizador pode gerar um novo ciclo de 16 semanas com dados atualizados.
- Semana-base (Vol. 1): segunda força A + mobilidade; terça cardio + mobilidade; quarta força B + equilíbrio; quinta cardio leve + mobilidade; sexta força A/B alternada; sábado cardio; domingo recuperação ativa ou descanso. Ajustada ao número de dias de 1.J.
- Ordem de progressão: técnica → duração → séries/repetições → carga → intensidade. **Nunca** aumentar duas variáveis em simultâneo.
- Esforço percebido 0–10; entre 3 e 6 em todas as fases da versão-base (ver secção 6). No cardio moderado, conseguir falar em frases curtas.
- Força: 2 a 3 dias não consecutivos, 8 a 10 exercícios, 10 a 15 repetições.
- Medições principais repetidas a cada 4 semanas.
- A alimentação acompanha as fases (Vol. 3): organizar → consolidar hábitos → ajustar quantidades → transformar em rotina. Uma alteração de cada vez quando a evolução abranda.

## 6. Biblioteca de exercícios e resolução da incoerência da Fase 4

### 6.1 Campos da biblioteca

Fonte: Vol. 1 (secções 6–8) e Vol. 2 (biblioteca e tabelas das 4 fases). Cada exercício em `conteudo/exercicios.yaml` tem: `id`, `nome`, `descricao`, `grupo`, `fase_minima`, `equipamento`, `impacto` (baixo/medio/alto), `nivel` (base/intermedio/avancado), `variante_halteres`, `regressao` (id da versão mais fácil), `contraindicacoes`.

### 6.2 O problema

A Fase 4 do Vol. 2 («Integração e Desafio de Alta Intensidade») prescreve saltos, escaladores e movimentos explosivos em 4 séries com descansos curtos. Isto contradiz o Vol. 1, que define a Fase 4 como consolidação de hábitos e preparação da manutenção, com cardio de baixo impacto e esforço 3–6 para o público-alvo.

### 6.3 A resolução

1. **Prevalece o Vol. 1.** A Fase 4 chama-se «Integração» e mantém o foco do Vol. 1: consolidar hábitos e preparar a manutenção.
2. **Variante-base por omissão.** Em todas as fases, o plano usa a variante-base da tabela 6.4. A variante avançada (a do Vol. 2) só entra quando se cumprem **todos** os critérios: idade ≤ 60; IMC < 30; sem nenhuma condição da secção 1 nem limitação articular em 1.H; intensidade efetiva Alta; registo de progresso das semanas anteriores sem dor nem sinais de alerta.
3. **Parâmetros da Fase 4 na versão-base:** 3 séries (em vez de 4), descanso de 45 a 60 s (em vez de 30 a 45 s), esforço até 6. Na versão avançada: os valores do Vol. 2, com esforço até 7.
4. **Cardio finalizador** (Vol. 2, estrutura da sessão): na versão-base, «corrida estática» passa a **marcha rápida no lugar**, alternando 30 s mais vivos com 30 s calmos.
5. **Osteoporose:** sem flexão do tronco com carga (abdominal crunch) em nenhuma fase; usa-se o bird-dog.

### 6.4 Tabela de variantes

| Fase | Exercício no Vol. 2 (avançado) | Impacto / nível | Variante-base (por omissão) |
|---|---|---|---|
| 2 | Lunge alternado atrás | médio / intermédio | Lunge atrás com apoio numa cadeira ou bancada |
| 2 | Flexões populares (chão, sem joelhos) | médio / intermédio | Flexão com joelhos apoiados ou flexão inclinada (mãos numa bancada estável) |
| 2 | Abdominal crunch | baixo / base | Mantém-se; com osteoporose, bird-dog |
| 3 | Agachamento búlgaro | médio / avançado | Agachamento dividido com os dois pés no chão e apoio na parede ou numa cadeira |
| 3 | Flexões diamante | médio / avançado | Flexão inclinada com as mãos mais próximas |
| 3 | Prancha lateral | baixo / intermédio | Prancha lateral com joelhos apoiados |
| 4 | Agachamento com salto | alto / avançado | Agachamento para cadeira com elevação dos calcanhares no topo, sem saltar |
| 4 | Lunge caminhando | médio / intermédio | Subida a um degrau baixo com apoio no corrimão |
| 4 | Flexão + toque no ombro | médio / avançado | Prancha alta inclinada (mãos numa bancada) com toque alternado no ombro |
| 4 | Remada em prancha | médio / avançado | Remada unilateral com apoio (a da Fase 3) |
| 4 | Thruster (agacha + empurra) | médio / avançado | Agachamento para cadeira seguido de prensa de ombros com halteres leves, em dois movimentos separados e sem pressa |
| 4 | Escaladores (mountain climbers) | alto / avançado | Marcha rápida no lugar com elevação dos joelhos, sem saltar |

Os restantes exercícios do Vol. 1 e do Vol. 2 são baixo impacto / nível base e usam-se como estão, sempre com regressão para quem tenha limitações em 1.H.

### 6.5 Volume 2 em Word

Resolução aplicada ao Volume 2 em Word (revisão de 25/10/2026): as tabelas mostram a variante-base, as avançadas aparecem por baixo de cada tabela com os critérios, e a Fase 4 chama-se «Integração». A cópia em `docs/referencia/` corresponde a esta revisão.

## 7. Textos obrigatórios (fixos, nunca gerados pela LLM)

**Sinais para interromper imediatamente** (Vol. 1 e 2): dor no peito, falta de ar invulgar ou desproporcionada, desmaio ou sensação de desmaio, confusão, palpitações preocupantes, tonturas, dor articular aguda. Procurar avaliação adequada.

**Aviso** (base Vol. 1 e Prompt v2): «Este plano é uma sugestão de apoio à decisão, preparada com recurso a inteligência artificial e a conteúdo editorial revisto. Não substitui avaliação, diagnóstico, tratamento ou acompanhamento por médico, nutricionista ou profissional de exercício. Antes de iniciar ou intensificar o plano — sobretudo com doenças crónicas, medicação regular ou idade avançada — valide-o com um profissional de saúde.»

Estes textos ficam em `conteudo/avisos.yaml` e são inseridos pelo código depois da geração.

## 8. Lista negra (verificação automática)

Termos e ideias que fazem chumbar o plano na verificação: «queima-gordura», «queima gordura», «detox», «desintoxicação», «chá emagrecedor», «termogénico», «seca barriga», «secante», jejum prolongado sem acompanhamento, dietas com menos de 1200 kcal, promessas de perda localizada («perder barriga em X dias»), qualquer marca comercial de suplementos, e qualquer exercício de nível avançado num plano que não cumpra os critérios da secção 6.3. Lista mantida em `conteudo/avisos.yaml`, com uma lista paralela de brasileirismos frequentes (tela, usuário, celular, café da manhã, academia, arquivo, salvar, baixar, time, registro).

## 9. Acompanhamento e lembretes

- Indicadores semanais (Vol. 1, Anexo B): peso, cintura, sessões feitas, minutos de cardio, força, mobilidade/equilíbrio, sono médio, energia 0–10, esforço 0–10, observações, reflexão («o que correu bem? o que ajustar?»).
- Indicadores de 4 em 4 semanas (Vol. 3): peso, cintura, energia, regularidade do treino, regularidade alimentar, sono, observações + perguntas de revisão.
- Frequência escolhida em 6.B: **semanal** ou **a cada 4 semanas**. Por omissão, acompanhamento **ativo** e semanal (recomendado), mas sempre opcional.
- Lembrete: se o registo do período estiver em falta 2 dias depois do prazo, um email; se continuar em falta 5 dias depois do prazo, um segundo e último.
- O email de lembrete nunca contém dados de saúde e tem sempre ligação para desativar.
- Evolução abaixo do esperado durante 2 períodos seguidos ⇒ a app sugere a lista de verificação do Vol. 3 («Quando a evolução abranda»), uma alteração de cada vez. Sem tom de culpa.

## 10. Contactos

- Email: obrigatório, vem da autenticação.
- Telemóvel: **opcional**, com país por omissão Portugal (+351) e escolha de qualquer outro país; validado como número de telemóvel do país escolhido e guardado em formato E.164. Especificação em `QUESTIONARIO.md`, secção «Contactos».
- Nenhum envio por SMS ou WhatsApp no MVP; o telemóvel fica preparado para essa funcionalidade futura, que exigirá consentimento próprio no momento em que for ativada.

Não há decisões de domínio pendentes.

## Registo de decisões

- 25/10/2026 — Gravidez: não gera plano, com a mensagem da secção 1. Teto «Média» com condições crónicas confirmado. Proteína 1,0–1,2 g/kg em todas as idades. Ritmos máximos de perda de peso 0,4 / 0,5 / 0,6 %/semana. Programa sempre em 16 semanas, sem meses. Incoerência da Fase 4 resolvida (secção 6). Prazos dos lembretes confirmados. Telemóvel opcional, nacional por omissão ou internacional.
