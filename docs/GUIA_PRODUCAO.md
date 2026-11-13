# Guia de produção — app.vigoria.pt (Fase 10)

Passos que o José faz à mão para pôr a Vigoria em produção: Railway (EU West, Amesterdão), Neon (Frankfurt), Auth0 de produção, Google, Brevo e Groq. O código já está preparado; aqui só há configuração.

**Regras deste guia**
- Os valores secretos (chaves, palavras-passe, segredos) vão **só** para as variáveis do Railway. Nunca para o chat, o GitHub, ficheiros do projeto ou capturas de ecrã.
- Neste guia só aparecem **nomes** de variáveis. Os valores que não são secretos (endereços, nomes de modelos) aparecem por extenso.
- Os nomes dos menus podem mudar ligeiramente com o tempo. Se não encontrares um menu, diz-me o que vês no ecrã.

**Ordem recomendada:** cada passo precisa do anterior.

1. Neon (base de dados de produção)
2. Fornecedor de IA: Gemini pago (principal, com teto de gasto) e Groq (reserva)
3. Auth0 de produção, Google e Brevo
4. Railway: serviço web
5. Domínio app.vigoria.pt (CNAME no cPanel)
6. Railway: serviço cron dos lembretes
7. Logótipo no Auth0
8. Abrir o beta fechado

---

## 1. Neon — base de dados de produção

Os dados reais não se misturam com os fictícios da demo.

1. Em console.neon.tech, cria um projeto **novo**: `vigoria-producao`, região **AWS Europe Central 1 (Frankfurt)**, PostgreSQL na versão mais recente.
   - Porquê um projeto novo, e não um ramo (*branch*): o ramo copia os dados do projeto da demo e partilha a conta de acesso. Um projeto separado tem credenciais próprias.
2. Em *Dashboard → Connect*, escolhe a base `neondb` (ou cria uma `vigoria`). **Desliga** a opção *Connection pooling*, porque as migrações correm melhor com a ligação direta. Copia o endereço `postgresql://…` diretamente para o Railway no passo 4 (`DATABASE_URL`).
3. As tabelas criam-se sozinhas no primeiro arranque do serviço web (migrações Alembic).

## 2. Fornecedor de IA: Gemini pago (principal) e Groq (reserva)

**Decisão do José (13/11/2026), com base na comparação de 12/11:**

| Papel | Fornecedor | Modelo |
|---|---|---|
| Principal | Google, Gemini API, **nível pago**, projeto próprio | `gemini-3.5-flash-lite` |
| Reserva | Groq | `openai/gpt-oss-120b` |

A reserva só entra quando o Gemini falha de vez: indisponível depois das repetições, sem resposta em 120 s ou quota esgotada. Os planos ficam sempre com o registo de quem os gerou. O Gemini **gratuito** continua recusado em produção: o arranque só aceita o Gemini com `VIGORIA_GEMINI_PAGO=true`. A variável `VIGORIA_MODELO_RESERVA` (reserva com o mesmo fornecedor e outro modelo) continua no código, mas não se usa em produção.

### 2.1 Gemini: projeto pago «vigoria-producao»

1. Em aistudio.google.com, cria um **projeto novo** chamado `vigoria-producao` (*Dashboard → Projects → Create project*). Não uses o projeto da chave gratuita.
2. **Faturação:** liga a esse projeto uma conta de faturação (*Billing → Set up billing*). Só com faturação ativa o projeto passa ao nível pago, em que a Google **não usa os pedidos para treinar** os seus modelos.
3. **Teto de gasto: 5 $ por mês.** No projeto, em *Billing → Monthly spend cap*, define **5 $**. No Google Cloud Console, em *Billing → Budgets & alerts*, cria um orçamento de 5 $ com alertas aos **50 %, 75 % e 90 %**. O teto bloqueia o serviço; o orçamento só avisa. A Google aplica o teto com cerca de **10 a 15 minutos de atraso**, por isso o gasto pode passar ligeiramente dos 5 $.
4. **Chave própria:** em *API Keys → Create API key*, no projeto `vigoria-producao`, cria a chave `vigoria-producao`. Copia-a **só para o Railway** (`GEMINI_API_KEY`), nunca para o teu `.env`.
5. **A chave gratuita fica para desenvolvimento e demo:** o teu `.env` local e os Secrets do Streamlit Cloud continuam com a chave do projeto gratuito, só com dados fictícios.
6. **A CONFIRMAR (revisão jurídica):** os termos do Gemini API pago para dados de utilizadores do EEE, a transferência para os EUA e o prazo em que a Google guarda os pedidos para prevenir abusos.

### 2.2 Groq: a reserva

1. Em console.groq.com, usa a organização da Vigoria (ou a tua) e cria a chave `vigoria-producao` (*API Keys → Create API Key*). Copia-a só para o Railway (`GROQ_API_KEY`).
2. **Zero Data Retention:** ativa-o **antes de entrarem dados reais**, em *Settings → Data Controls* (ou equivalente). Confirma na página que os pedidos não ficam guardados nem são usados para treino. Se o plano gratuito não permitir ativá-lo, diz-me antes de continuar: nesse caso, ou passas ao Developer, ou ficamos sem reserva até lá.
3. **Plano:** fica no gratuito enquanto a reserva for pouco usada. No gratuito, o limite é de 8000 tokens por minuto, e cada chamada gastou cerca de 7000 no teste de 12/11: na prática, uma chamada por minuto. Passa ao **Developer** (pago por utilização, sem mensalidade) **só se a reserva for usada com frequência**. Para saber se é, procura nos registos do Railway as linhas «a usar a reserva groq». Nesse caso, define logo um teto de **5 $ por mês** em *Settings → Billing → Spend limit*, com alertas aos **50 %, 75 % e 90 %**. Quando o teto é atingido, a Groq bloqueia a conta com o erro `blocked_api_access`, também com cerca de 10 a 15 minutos de atraso.
4. **Esforço de raciocínio (opcional):** `GROQ_REASONING_EFFORT=low` reduz os tokens de saída do gpt-oss. Fica vazio até a medição com uma persona mostrar que a qualidade se mantém (ver «Medir o reasoning_effort», no fim do passo 2).
5. **A CONFIRMAR (revisão jurídica):** o acordo de tratamento de dados (DPA) da Groq e a base da transferência para os EUA (cláusulas-tipo ou EU-US Data Privacy Framework).

### Quando o teto de gasto é atingido

A app trata o erro como serviço temporariamente indisponível e não faz novas tentativas nem usa a reserva. A Groq aplica o teto à organização inteira, por isso a reserva também estaria bloqueada. Quem está a gerar um plano vê «O serviço que prepara os planos não está disponível neste momento…», e as respostas ficam guardadas. Nos registos do Railway aparece:

```
limite de gasto mensal atingido (groq, openai/gpt-oss-120b): subir o teto na consola ou esperar pelo mês seguinte
```

Para resolver: sobe o teto na consola ou espera pelo mês seguinte.

### Comparação de qualidade (feita a 12/11/2026)

O `scripts/comparar_fornecedores.py` gera 10 planos (5 personas fictícias × Gemini e Groq 120b) e compara-os: falhas da verificação, menções a meses, palavras desconhecidas, tempo e tokens.

**Chama a LLM real:** corre-o só tu, à mão. Os planos gratuitos do Gemini e do Groq chegam, desde que haja uma pausa de 60 s entre personas. O script só usa as 5 personas fictícias de `exemplos/`. No PowerShell, na pasta do projeto, com o `.venv` ativo:

```powershell
python scripts/comparar_fornecedores.py --modelo-groq openai/gpt-oss-120b --pausa 60
```

Demora cerca de 6 a 8 minutos. Se aparecer «nova tentativa daqui a … s», é uma espera normal. Com Ctrl+C, guarda as personas já completas.

### Medir o reasoning_effort do Groq (uma persona)

Chama a LLM real duas vezes: corre-o só tu. No PowerShell, na pasta do projeto, com o `.venv` ativo:

```powershell
Remove-Item Env:GROQ_REASONING_EFFORT -ErrorAction SilentlyContinue
python -m vigoria.motor.cli --comparar groq exemplos/persona_osteoporose.json
$env:GROQ_REASONING_EFFORT = "low"
python -m vigoria.motor.cli --comparar groq exemplos/persona_osteoporose.json
Remove-Item Env:GROQ_REASONING_EFFORT
```

Se tiveres `GROQ_REASONING_EFFORT` no `.env`, deixa-o vazio durante a medição: a variável do PowerShell ganha ao `.env`. Compara as duas tabelas: «Tokens de saída», «Tempo», «Falhas na verificação» e «Palavras desconhecidas». Os dois planos ficam em `saidas/comparacao/`, e o segundo substitui o primeiro: copia o primeiro antes de correr o segundo, se o quiseres ler.

A tabela aparece no ecrã e fica em `saidas/comparacao/`. Mostra-me o resumo e eu dou-te a minha recomendação.

## 3. Auth0 de produção, Google e Brevo

Ficam **dois tenants**:

| Tenant | Para quê | Endereços permitidos |
|---|---|---|
| o atual (desenvolvimento) | local e demo | `http://localhost:8501`, `http://localhost:8080`, `https://<demo>.streamlit.app` |
| novo (produção) | só app.vigoria.pt | `https://app.vigoria.pt` |

Assim, uma conta de teste nunca se mistura com contas reais, e uma chave da demo não abre a produção.

### 3.1 Tenant de produção

1. No painel do Auth0, no canto superior esquerdo, clica no nome do tenant e depois em *Create tenant*. Usa o nome `vigoria-pt` (ou outro livre), região **EU**, ambiente **Production**.
2. Repete os passos 2 a 5 do `docs/GUIA_AUTH0.md`, com estes valores na aplicação `Vigoria` (*Regular Web Application*):

| Campo | Valor |
|---|---|
| Allowed Callback URLs | `https://app.vigoria.pt/oauth2callback` |
| Allowed Logout URLs | `https://app.vigoria.pt/oauth2callback` |
| Allowed Web Origins | `https://app.vigoria.pt` |

3. Em *Settings → Advanced → Login and Logout*, confirma que **RP-Initiated Logout End Session Endpoint Discovery** está ligado.
4. Na aplicação Machine to Machine para apagar contas (secção 8 do `GUIA_AUTH0.md`), dá só a permissão `delete:users` na *Auth0 Management API* deste tenant.
5. Os valores vão para o Railway (passo 4):
   - *Client ID* e *Client Secret* da aplicação `Vigoria` → `AUTH0_CLIENT_ID` e `AUTH0_CLIENT_SECRET`.
   - O endereço `https://<tenant>.eu.auth0.com/.well-known/openid-configuration` → `AUTH0_SERVER_METADATA_URL`. O arranque recusa o endereço sem `https://` ou sem o fim `/.well-known/openid-configuration`.
   - *Client ID* e *Client Secret* da aplicação M2M → `AUTH0_GESTAO_CLIENT_ID` e `AUTH0_GESTAO_CLIENT_SECRET`.

### 3.2 Google — cliente OAuth próprio

No tenant de produção, as chaves de desenvolvimento do Auth0 não servem: mostram um aviso e têm limites.

1. Em console.cloud.google.com, cria o projeto `Vigoria`.
2. Em *Google Auth Platform → Branding* (antigo *OAuth consent screen*), preenche:
   - nome `Vigoria`;
   - email de apoio `geral@vigoria.pt`;
   - logótipo (opcional; obriga a uma verificação da Google, por isso podes deixá-lo para depois);
   - domínio autorizado `vigoria.pt`;
   - ligações para a página inicial e para a política de privacidade de `https://app.vigoria.pt`.
3. Em *Audience*, escolhe **External** e publica a app (*Publish app*). Os âmbitos `openid`, `email` e `profile` não precisam de verificação.
4. Em *Clients → Create client → Web application*, em *Authorized redirect URIs*, põe `https://<tenant>.eu.auth0.com/login/callback`. O Auth0 mostra o endereço exato na página da ligação Google.
5. No Auth0 de produção, em *Authentication → Social → Google*, cola o *Client ID* e o *Client Secret* do Google. Liga a ligação à aplicação `Vigoria`.

### 3.3 Brevo como SMTP do Auth0

Os emails de verificação e de recuperação da palavra-passe saem de `geral@vigoria.pt`.

1. No Brevo, em *SMTP & API → SMTP*, copia o **SMTP login** e gera uma **SMTP key** com o nome `auth0-producao`. Não uses a chave API dos lembretes.
2. No Auth0 de produção, em *Branding → Email Provider → SMTP*, preenche:
   - host `smtp-relay.brevo.com`, porta `587`;
   - utilizador = SMTP login, palavra-passe = SMTP key;
   - remetente `geral@vigoria.pt`.

   Envia o email de teste.
3. Em *Branding → Email Templates*, revê em PT-EU o **Verification Email** e o **Change Password**, com remetente `Vigoria <geral@vigoria.pt>`.
4. **Bloqueio de IPs do Brevo:** fica **desligado** (*Security → Authorized IPs*). O Railway não garante IP fixo, e o Auth0 envia de vários IPs.

## 4. Railway — serviço web

1. Em railway.com, cria o projeto `vigoria` e escolhe *Deploy from GitHub repo* → `josefeneto/vigoria`, ramo `main`. O Railway encontra o `Dockerfile` sozinho.
2. No serviço, *Settings*:
   - **Region:** EU West (Amsterdam).
   - **Replicas:** 1. A fila das gerações (um plano de cada vez) vive na memória de um só processo; com 2 réplicas, haveria 2 filas.
   - **Healthcheck Path:** `/_stcore/health`.
   - **Serverless / App Sleeping:** desligado. Adormecer corta as ligações abertas do Streamlit.
   - **Start command:** vazio. O `Dockerfile` já arranca com `arrancar.sh`.
3. *Variables* do serviço web:

| Variável | Valor |
|---|---|
| `AMBIENTE` | `producao` |
| `APP_URL` | `https://app.vigoria.pt` |
| `DATABASE_URL` | secreto (Neon, passo 1) |
| `VIGORIA_PROVEDOR_LLM` | `gemini` |
| `VIGORIA_GEMINI_PAGO` | `true` (só depois de a faturação do projeto `vigoria-producao` estar ativa) |
| `GEMINI_API_KEY` | secreto (chave do projeto pago, passo 2.1) |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` |
| `VIGORIA_PROVEDOR_RESERVA` | `groq` |
| `GROQ_API_KEY` | secreto (passo 2.2) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `VIGORIA_EMAILS_PERMITIDOS` | os emails do beta, separados por vírgulas |
| `VIGORIA_PLANOS_POR_DIA` | `3` (opcional: é o valor por omissão; `0` = sem limite) |
| `VIGORIA_SEGREDO_LEMBRETES` | secreto **novo** (ver abaixo) |
| `AUTH_REDIRECT_URI` | `https://app.vigoria.pt/oauth2callback` |
| `AUTH_COOKIE_SECRET` | secreto **novo** (ver abaixo) |
| `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` | secretos (passo 3.1) |
| `AUTH0_SERVER_METADATA_URL` | `https://<tenant>.eu.auth0.com/.well-known/openid-configuration` |
| `AUTH0_GESTAO_CLIENT_ID`, `AUTH0_GESTAO_CLIENT_SECRET` | secretos (passo 3.1) |

   `PORT` não se define: é o Railway que a dá.

   **Segredos novos, nunca copiados da demo nem do teu `.env`:** gera cada um no PowerShell e cola-o diretamente no Railway.
   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"        # AUTH_COOKIE_SECRET
   python -c "import secrets; print(secrets.token_urlsafe(48))"    # VIGORIA_SEGREDO_LEMBRETES
   ```

4. Faz o *Deploy*. Nos registos (*Deployments → View logs*), deves ver:
   - `arranque: .streamlit/secrets.toml gerado (AMBIENTE=producao)`
   - `arranque: base de dados atualizada (alembic upgrade head)`

   Se aparecer `arranque: ERRO: …`, a mensagem diz o nome da variável em falta ou mal escrita, nunca o valor.
5. Em *Settings → Networking → Generate Domain*, crias um endereço `…up.railway.app`. No PowerShell:
   ```powershell
   python scripts/fumo.py https://<endereco>.up.railway.app
   ```
   O login ainda não funciona neste endereço: o Auth0 de produção só aceita app.vigoria.pt.

**Cada `git push` para o `main` volta a publicar** o serviço web e o cron, e também a demo no Streamlit Cloud.

## 5. Domínio app.vigoria.pt

1. No Railway, em *Settings → Networking → Custom Domain*, escreve `app.vigoria.pt`. O Railway mostra o destino do **CNAME** e, às vezes, um registo **TXT** de verificação.
2. No cPanel da dominios.pt, em *Domínios → Zone Editor → vigoria.pt → Manage*, faz *+ Add Record*:
   - tipo **CNAME**, nome `app`, destino o que o Railway mostrou;
   - se o Railway pedir o TXT, cria-o com o nome e o valor exatos.
3. Espera que o Railway mostre o domínio como verificado e com certificado. Pode demorar de minutos a algumas horas. Depois, no PowerShell:
   ```powershell
   python scripts/fumo.py https://app.vigoria.pt
   ```
4. Entra em https://app.vigoria.pt com uma conta de email e com Google. Confirma também que «Sair» volta à página inicial.

**HSTS:** o site responde com `Strict-Transport-Security: max-age=31536000`, sem `includeSubDomains` nem `preload`. Os navegadores passam a usar só HTTPS em app.vigoria.pt durante um ano. Os outros subdomínios de vigoria.pt não são afetados.

## 6. Railway — serviço cron dos lembretes

Este serviço usa a mesma imagem, mas **não** corre o `arrancar.sh`: não tem Caddy, Streamlit, migrações nem `secrets.toml`. Só corre a tarefa e termina.

1. No projeto, faz *+ Create → GitHub Repo* → o mesmo repositório. Muda o nome do serviço para `lembretes`.
2. *Settings*:
   - **Region:** EU West (Amsterdam).
   - **Custom Start Command:** `python -m vigoria.tarefas.lembretes`
   - **Cron Schedule:** `7 9 * * *`. O Railway lê o cron em UTC, sem fuso horário: o envio sai às 9h07 em Lisboa no inverno e às 10h07 no verão, nunca antes das 9h.
   - **Restart Policy:** Never.
   - Sem domínio e sem healthcheck.
3. *Variables*. Para não duplicar segredos, usa referências ao serviço web, por exemplo `${{vigoria.DATABASE_URL}}`; o nome antes do ponto é o do serviço web.

| Variável | Valor |
|---|---|
| `AMBIENTE` | `producao` |
| `APP_URL` | `https://app.vigoria.pt` |
| `DATABASE_URL` | referência ao serviço web |
| `VIGORIA_PROVEDOR_LLM` e `VIGORIA_GEMINI_PAGO` | referências ao serviço web (a tarefa não chama a LLM, mas a configuração é validada e recusa o Gemini sem `VIGORIA_GEMINI_PAGO=true`) |
| `VIGORIA_SEGREDO_LEMBRETES` | referência ao serviço web (tem de ser **o mesmo**) |
| `VIGORIA_EMAILS_PERMITIDOS` | referência ao serviço web |
| `BREVO_API_KEY` | secreto (chave API do Brevo; pode ser uma nova, `lembretes-producao`) |
| `EMAIL_REMETENTE` | `geral@vigoria.pt` |
| `EMAIL_NOME_REMETENTE` | `Vigoria` |

4. Para testar sem esperar pelo dia seguinte, muda **temporariamente** o *Custom Start Command* e carrega em *Deploy*. Depois de cada teste, volta ao comando normal.
   - `python -m vigoria.tarefas.lembretes --simular`: mostra nos registos quem receberia que lembrete, sem enviar nada.
   - `python -m vigoria.tarefas.lembretes --testar-envio`: envia já um lembrete de exemplo. Se houver mais de uma conta, junta `--utilizador <id>`.

Os emails de produção levam o cabeçalho de cancelamento num clique (RFC 8058). O Gmail mostra «Anular subscrição», e o botão desliga os lembretes sem abrir a app.

## 7. Logótipo no Auth0

Este passo só funciona depois do passo 5, quando o endereço já responde.

No Auth0 de produção, em *Branding → Universal Login → Customization Options*:
- **Logo URL:** `https://app.vigoria.pt/icones/icone-512.png`
- **Primary color:** `#1F5C63`
- **Page background:** `#F7F3EC`

## 8. Abrir o beta fechado

1. Confirma que `VIGORIA_EMAILS_PERMITIDOS` tem só os emails convidados.
2. Confirma a lista «A CONFIRMAR», abaixo.
3. Faz os testes manuais (secção seguinte).

## 9. Testes manuais antes de convidar pessoas

Faz estes testes com uma conta tua, em https://app.vigoria.pt. Anota o que falhar (o quê, em que aparelho) e mostra-me.

### 9.1 iPhone (Safari)

1. Abre https://app.vigoria.pt no Safari, entra e confirma que a página inicial aparece em português de Portugal.
2. *Partilhar → Adicionar ao ecrã principal*. O ícone deve ser o da Vigoria, com fundo petróleo e sem cantos pretos, e o nome «Vigoria».
3. Abre a app a partir do ícone. Deve abrir em ecrã inteiro, sem a barra do Safari.
4. Entra com email e palavra-passe. No fim do login, o Auth0 tem de **voltar à app**, e não ficar no Safari. Se ficar no Safari, anota-o: é uma limitação conhecida das apps instaladas no iPhone.
5. Fecha a app (desliza-a para cima no seletor de apps) e volta a abri-la. A sessão mantém-se, ou pede para entrar outra vez? Anota o que acontece.
6. Responde ao questionário até ao fim e gera um plano. Confirma que aparece «Estamos a preparar o seu plano…» enquanto espera.
7. Descarrega o PDF e abre-o: nenhum título sozinho no fundo de uma página, e no fim «Versão do plano: …».
8. Pede mais planos até ao limite de 3 no mesmo dia. O 4.º deve mostrar «Hoje já chegou ao máximo de planos por dia (3)…».

### 9.2 Android (Chrome)

1. Abre https://app.vigoria.pt no Chrome. Deve aparecer a sugestão «Instalar app», ou então ⋮ → *Adicionar ao ecrã principal* → *Instalar*.
2. Abre a app instalada: ecrã inteiro, com o ícone e as cores da Vigoria.
3. Entra com Google e confirma que voltas à app.
4. Gera um plano e descarrega o PDF.

### 9.3 Lembretes no Gmail

1. Em «A minha conta», confirma que os lembretes estão ligados. Faz o envio de teste do serviço cron (passo 6.4, com `--testar-envio`) ou espera pelo envio das 9h07.
2. No **Gmail no telemóvel**, abre o email e toca na ligação para a app. Abre no navegador interno do Gmail: confirma que a página carrega e que consegues entrar. Se o login falhar aí, anota-o; o Google bloqueia por vezes o login com Google dentro de navegadores internos.
3. Confirma que o email **não** tem dados de saúde: nem peso, nem cintura, nem condições.

### 9.4 Cancelamento num clique

1. No Gmail no computador, abre o lembrete. Ao lado do remetente deve aparecer **«Anular subscrição»**. O Gmail pode demorar alguns envios a mostrá-lo a um remetente novo.
2. Carrega em «Anular subscrição» e confirma.
3. Em https://app.vigoria.pt, «A minha conta»: os lembretes têm de estar **desligados**.
4. Volta a ligá-los. Depois, no email, abre a ligação «Deixar de receber lembretes»: deve aparecer só a pergunta e o botão; os lembretes só desligam ao carregar no botão.
5. Nos registos do Railway, procura as linhas `cancelar: POST, utilizador …, valido`. Não podem ter o email nem o token.

---

## A CONFIRMAR antes do primeiro utilizador real

| O quê | Onde está | Estado |
|---|---|---|
| Fornecedor de IA: Gemini pago (principal) e Groq (reserva) | passo 2 | decidido (13/11/2026) |
| Projeto `vigoria-producao` com faturação e teto de 5 $/mês, alertas aos 50/75/90 % | Google AI Studio e Cloud Console | por fazer |
| Zero Data Retention ativo na Groq, antes de dados reais | consola da Groq | por fazer |
| Termos do Gemini API pago para o EEE, transferência para os EUA e prazo de conservação para prevenir abusos | revisão jurídica | por confirmar |
| DPA da Groq e base da transferência para os EUA | revisão jurídica | por confirmar |
| Consentimento de saúde em produção (Google e Groq, EUA, sem uso para treino) | `paginas/textos.py`, `CONSENTIMENTO_SAUDE_PRODUCAO` | por confirmar (revisão jurídica) |
| Política de privacidade e «Onde ficam os meus dados?» (Google principal, Groq reserva) | `paginas/textos_privacidade.py` e `conteudo/ajuda.yaml` | por confirmar (revisão jurídica) |
| Segredos novos em produção (`AUTH_COOKIE_SECRET`, `VIGORIA_SEGREDO_LEMBRETES`) | Railway | por fazer |
| Bloqueio de IPs do Brevo desligado | Brevo | por fazer |

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Registos: `arranque: ERRO: Variáveis em falta: …` | Variável do Auth0 por definir no serviço web. |
| Registos: `Configuração inválida: … VIGORIA_GEMINI_PAGO` | Falta `VIGORIA_GEMINI_PAGO=true` no serviço (web ou cron). Só se põe depois de a faturação do projeto `vigoria-producao` estar ativa. |
| Registos: `groq: HTTP 400 (code=json_validate_failed, …)` | O modelo do Groq gerou um JSON fora do schema. A app repete sozinha; só é preocupante se acontecer muitas vezes seguidas. |
| «A entrada com conta ainda não está configurada» | Não devia acontecer em produção, porque o arranque falha antes. Se acontecer, envia-me os registos do arranque. |
| Login volta com erro «Callback URL mismatch» | `AUTH_REDIRECT_URI` diferente das *Allowed Callback URLs* do tenant de produção. |
| «Há muitas pessoas a preparar o plano» | Mais de 3 minutos na fila: várias gerações seguidas. Nos registos, procura `fila:` e `429 por minuto`. |
| Planos falham sempre com «muitos pedidos» | Groq no plano gratuito (limite de tokens por minuto). Ver o passo 2. |
| «O serviço que prepara os planos não está disponível» e, nos registos, `limite de gasto mensal atingido` | Teto de 5 $ atingido. Ver «Quando o teto de gasto é atingido», no passo 2. |
