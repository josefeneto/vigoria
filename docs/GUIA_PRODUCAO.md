# Guia de produção — app.vigoria.pt (Fase 10)

Passos que o José faz à mão para pôr a Vigoria em produção: Railway (EU West, Amesterdão), Neon (Frankfurt), Auth0, Google, Brevo e Groq. O código já está preparado; aqui só há configuração.

**Dois ambientes:** local (o teu PC, para desenvolver) e produção (Railway, app.vigoria.pt). A demo no Streamlit Cloud é desligada no passo 6, logo que a produção responde.

**Regras deste guia**
- Os valores secretos (chaves, palavras-passe, segredos) vão **só** para as variáveis do Railway. Nunca para o chat, o GitHub, ficheiros do projeto ou capturas de ecrã.
- Neste guia só aparecem **nomes** de variáveis. Os valores que não são secretos (endereços, nomes de modelos) aparecem por extenso.
- Os nomes dos menus podem mudar ligeiramente com o tempo. Se não encontrares um menu, diz-me o que vês no ecrã.

**Ordem recomendada:** cada passo precisa do anterior.

1. Neon (base de dados de produção)
2. Fornecedor de IA: Gemini pago (principal, com teto de gasto) e Groq (reserva)
3. Auth0 (a aplicação atual, mais app.vigoria.pt), Google e Brevo
4. Railway: serviço web
5. Domínio app.vigoria.pt (CNAME no cPanel)
6. Desligar a demo (Streamlit Cloud)
7. Railway: serviço cron dos lembretes
8. Logótipo no Auth0
9. Abrir o beta fechado (e, mais tarde, passar a beta aberto)
10. Testes manuais antes de convidar pessoas

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
5. **A chave gratuita fica para desenvolvimento:** o teu `.env` local continua com a chave do projeto gratuito, só com dados fictícios.
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

## 3. Auth0, Google e Brevo

O plano gratuito do Auth0 só permite **um tenant** (o segundo custa 35 $/mês). Fica o tenant atual, na região UE, com a aplicação `Vigoria` e a aplicação M2M que já existem. Acrescentam-se os endereços de app.vigoria.pt e o Railway usa **as mesmas credenciais**.

| Aplicação | Para quê | Endereços, depois do passo 6 |
|---|---|---|
| `Vigoria` (*Regular Web Application*) | entrar na app | `http://localhost:8501`, `http://localhost:8080` e `https://app.vigoria.pt` |
| a M2M atual (secção 8 do `GUIA_AUTH0.md`) | apagar a conta de entrada quando a pessoa apaga a conta | — |

**O que fica partilhado e o que não fica:** as contas do Auth0 (quem se registou) são as mesmas em local e em produção. Os dados da Vigoria não: em local ficam no SQLite do teu PC, em produção no Neon (passo 1). Além disso, a produção só deixa entrar os convidados (`VIGORIA_ACESSO=convidados` e `VIGORIA_EMAILS_PERMITIDOS`, passo 9).

### 3.1 Acrescentar app.vigoria.pt à aplicação atual

1. No Auth0, em *Applications → Applications → Vigoria → Settings*, acrescenta aos valores que já lá estão, separados por vírgulas (não apagues nenhum agora; os da demo saem no passo 6):

| Campo | Acrescentar |
|---|---|
| Allowed Callback URLs | `https://app.vigoria.pt/oauth2callback` |
| Allowed Logout URLs | `https://app.vigoria.pt/oauth2callback` |
| Allowed Web Origins | `https://app.vigoria.pt` |

   Carrega em *Save*.
2. Em *Settings → Advanced → Login and Logout*, confirma que **RP-Initiated Logout End Session Endpoint Discovery** está ligado (já devia estar, desde a Fase 6).
3. **Aplicação M2M** (apaga a conta de entrada quando a pessoa apaga a conta na Vigoria). Em *Applications → Applications*, procura uma aplicação do tipo *Machine to Machine* (por exemplo `Vigoria gestão`).
   - **Se não existir** (no teu `secrets.toml` local, `[auth0_gestao]` está vazio): *+ Create Application* → nome `Vigoria gestão`, tipo **Machine to Machine Applications** → *Create*. Em *Select an API*, escolhe **Auth0 Management API**; em *Permissions*, filtra por `delete:users`, marca só essa e carrega em *Authorize*.
   - **Se existir:** no separador *APIs*, a *Auth0 Management API* tem de estar *Authorized* só com `delete:users`.
   - **Só no Railway, nunca em local:** deixa `[auth0_gestao]` vazio no teu `secrets.toml`. Como o tenant é um só, as contas do Auth0 são as mesmas em local e em produção: com a M2M em local, apagar a conta num teste apagava também a tua conta de entrada real, a de app.vigoria.pt. Sem ela, em local, «Apagar a conta» apaga só os dados do SQLite, sem erro, e o terminal regista «conta Auth0 por apagar».
4. Os valores vão para o Railway (passo 4). Copia-os do painel do Auth0 diretamente para o Railway:
   - *Client ID* e *Client Secret* da aplicação `Vigoria` → `AUTH0_CLIENT_ID` e `AUTH0_CLIENT_SECRET`;
   - o endereço `https://<tenant>.eu.auth0.com/.well-known/openid-configuration` (o mesmo de hoje) → `AUTH0_SERVER_METADATA_URL`. O arranque recusa o endereço sem `https://` ou sem o fim `/.well-known/openid-configuration`;
   - *Client ID* e *Client Secret* da aplicação M2M (separador *Settings*) → `AUTH0_GESTAO_CLIENT_ID` e `AUTH0_GESTAO_CLIENT_SECRET`, só no Railway. Definem-se as duas ou nenhuma: só uma faz falhar o arranque.

### 3.2 Google — cliente OAuth próprio (obrigatório)

As chaves de desenvolvimento do Auth0 (as que a ligação Google usa por omissão) **não servem para utilizadores reais**: mostram um aviso no login e têm limites. Este passo é obrigatório antes do beta.

1. Em console.cloud.google.com, cria o projeto `Vigoria`.
2. Em *Google Auth Platform → Branding* (antigo *OAuth consent screen*), preenche:
   - nome `Vigoria`;
   - email de apoio `geral@vigoria.pt`;
   - logótipo (opcional; obriga a uma verificação da Google, por isso podes deixá-lo para depois);
   - domínio autorizado `vigoria.pt`;
   - ligações para a página inicial e para a política de privacidade de `https://app.vigoria.pt`.
3. Em *Audience*, escolhe **External** e publica a app (*Publish app*). Os âmbitos `openid`, `email` e `profile` não precisam de verificação.
4. Em *Clients → Create client → Web application*, em *Authorized redirect URIs*, põe `https://<tenant>.eu.auth0.com/login/callback`. O Auth0 mostra o endereço exato na página da ligação Google.
5. No Auth0, em *Authentication → Social → google-oauth2*, troca as chaves de desenvolvimento pelo *Client ID* e pelo *Client Secret* do Google. Confirma, no separador *Applications* da ligação, que está ligada à aplicação `Vigoria`. Como há um só tenant, a mudança vale para local e para produção.

### 3.3 Brevo como SMTP do Auth0

Os emails de verificação e de recuperação da palavra-passe saem de `geral@vigoria.pt`. Como o Google (3.2) e o branding (passo 8), configura-se uma vez no tenant e serve local e produção.

1. No Brevo, em *SMTP & API → SMTP*, copia o **SMTP login** e gera uma **SMTP key** com o nome `auth0`. Não uses a chave API dos lembretes.
2. No Auth0, em *Branding → Email Provider → SMTP*, preenche:
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
| `VIGORIA_ACESSO` | `convidados` (só entram os emails da linha seguinte; ver o passo 9) |
| `VIGORIA_EMAILS_PERMITIDOS` | os emails do beta, separados por vírgulas |
| `VIGORIA_PLANOS_POR_DIA` | `3` (opcional: é o valor por omissão; `0` = sem limite) |
| `VIGORIA_SEGREDO_LEMBRETES` | secreto **novo** (ver abaixo) |
| `AUTH_REDIRECT_URI` | `https://app.vigoria.pt/oauth2callback` |
| `AUTH_COOKIE_SECRET` | secreto **novo** (ver abaixo) |
| `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` | secretos (passo 3.1) |
| `AUTH0_SERVER_METADATA_URL` | `https://<tenant>.eu.auth0.com/.well-known/openid-configuration` (o tenant atual) |
| `AUTH0_GESTAO_CLIENT_ID`, `AUTH0_GESTAO_CLIENT_SECRET` | secretos (passo 3.1) |

   `PORT` não se define: é o Railway que a dá.

   **Segredos novos, nunca copiados da demo nem do teu `.env`** (as credenciais do Auth0 são as mesmas; estes dois não): gera cada um no PowerShell e cola-o diretamente no Railway.
   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"        # AUTH_COOKIE_SECRET
   python -c "import secrets; print(secrets.token_urlsafe(48))"    # VIGORIA_SEGREDO_LEMBRETES
   ```

4. Faz o *Deploy*. Nos registos (*Deployments → View logs*), deves ver:
   - `arranque: .streamlit/secrets.toml gerado (AMBIENTE=producao)`
   - `arranque: base de dados atualizada (alembic upgrade head)`

   Se aparecer `arranque: ERRO: …`, a mensagem diz o nome da variável em falta ou mal escrita, nunca o valor. Se aparecer `arranque: AVISO: VIGORIA_ACESSO=convidados com VIGORIA_EMAILS_PERMITIDOS vazia: ninguém entra`, a app arranca, mas ninguém consegue entrar até preencheres a lista.
5. Em *Settings → Networking → Generate Domain*, crias um endereço `…up.railway.app`. No PowerShell:
   ```powershell
   python scripts/fumo.py https://<endereco>.up.railway.app
   ```
   O login ainda não funciona neste endereço: a aplicação `Vigoria` do Auth0 não tem o endereço `…up.railway.app`, só app.vigoria.pt e os de local (passo 3.1).

**Cada `git push` para o `main` volta a publicar** o serviço web e o cron (e a demo no Streamlit Cloud, até a desligares no passo 6).

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

## 6. Desligar a demo (Streamlit Cloud)

Faz-se logo que app.vigoria.pt responde e o login funciona (passo 5.4), antes do cron e dos testes manuais. A partir daqui ficam só dois ambientes: local e produção.

1. **Streamlit Cloud:** em share.streamlit.io, na app da Vigoria, ⋮ → *Settings → Secrets*: apaga todo o conteúdo e carrega em *Save changes*. Assim, as credenciais do Auth0 e da M2M deixam de lá estar, mesmo que a app demore a ser apagada. Depois, ⋮ → *Delete* e confirma.
2. **Auth0:** em *Applications → Applications → Vigoria → Settings*, retira os endereços `https://<demo>.streamlit.app` (e `…/oauth2callback`) de *Allowed Callback URLs*, *Allowed Logout URLs* e *Allowed Web Origins*. Ficam só `http://localhost:8501`, `http://localhost:8080` e `https://app.vigoria.pt`. Carrega em *Save*.
3. **GitHub (recomendado):** em github.com → repositório `josefeneto/vigoria` → *Settings → Secrets and variables → Actions → Repository secrets*, apaga os da demo: `DATABASE_URL`, `BREVO_API_KEY`, `VIGORIA_SEGREDO_LEMBRETES` e `VIGORIA_EMAILS_PERMITIDOS`. O workflow `lembretes.yml` já só corre à mão; sem estes segredos, deixa de conseguir correr.
4. **Neon da demo:** não tem dados reais. Podes apagá-lo mais tarde, quando quiseres; não é preciso para nada.

O código da demo (`AMBIENTE=demo`, a faixa de demonstração e o workflow do GitHub) fica no repositório por agora. Está registado em `docs/ESTADO.md` como limpeza para uma fase futura.

## 7. Railway — serviço cron dos lembretes

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
| `VIGORIA_ACESSO` e `VIGORIA_EMAILS_PERMITIDOS` | referências ao serviço web (só os convidados recebem lembretes) |
| `BREVO_API_KEY` | secreto (chave API do Brevo; pode ser uma nova, `lembretes-producao`) |
| `EMAIL_REMETENTE` | `geral@vigoria.pt` |
| `EMAIL_NOME_REMETENTE` | `Vigoria` |

4. Para testar sem esperar pelo dia seguinte, muda **temporariamente** o *Custom Start Command* e carrega em *Deploy*. Depois de cada teste, volta ao comando normal.
   - `python -m vigoria.tarefas.lembretes --simular`: mostra nos registos quem receberia que lembrete, sem enviar nada.
   - `python -m vigoria.tarefas.lembretes --testar-envio`: envia já um lembrete de exemplo. Se houver mais de uma conta, junta `--utilizador <id>`.

Os emails de produção levam o cabeçalho de cancelamento num clique (RFC 8058). O Gmail mostra «Anular subscrição», e o botão desliga os lembretes sem abrir a app.

## 8. Logótipo no Auth0

Este passo só funciona depois do passo 5, quando o endereço já responde. Vale também para o login em local (um só tenant).

No Auth0, em *Branding → Universal Login → Customization Options*:
- **Logo URL:** `https://app.vigoria.pt/icones/icone-512.png`
- **Primary color:** `#1F5C63`
- **Page background:** `#F7F3EC`

## 9. Abrir o beta fechado

1. No serviço web, confirma `VIGORIA_ACESSO=convidados` e que `VIGORIA_EMAILS_PERMITIDOS` tem só os emails convidados. Com a lista vazia, ninguém entra.
2. Para acrescentar ou retirar um convidado, edita `VIGORIA_EMAILS_PERMITIDOS` e carrega em *Deploy* para aplicar. O email tem de ser o da conta com que a pessoa entra (o do Google, se entrar com Google).
3. Quem não está na lista vê «A Vigoria está em fase de testes, apenas por convite. Se quiser participar, escreva para geral@vigoria.pt.» e não fica com nenhum registo na base de dados.
4. Confirma a lista «A CONFIRMAR», abaixo.
5. Faz os testes manuais (passo 10).

### Passar a beta aberto

Só quando **tudo** isto estiver fechado:

- **Revisão jurídica:** todas as linhas «por confirmar» da tabela «A CONFIRMAR» (consentimento, política de privacidade, «Onde ficam os meus dados?», termos do Gemini pago, DPA da Groq).
- **Política de privacidade completa:** o responsável pelo tratamento, o contacto de privacidade e o prazo de conservação. Hoje dizem «será indicado aqui antes do lançamento».
- **Tetos de gasto:** 5 $/mês e alertas aos 50/75/90 % no Gemini (passo 2.1) e, se tiveres passado ao Developer, também na Groq (passo 2.2).
- **Zero Data Retention** ativo na Groq.
- **Limite diário de planos** (`VIGORIA_PLANOS_POR_DIA`) adequado ao gasto que aceitas.
- **Testes manuais** (passo 10) sem falhas por resolver.
- **Auth0:** confirma o número de utilizadores ativos por mês que o plano gratuito permite.

A mudança: no serviço web, muda `VIGORIA_ACESSO` para `aberto` e carrega em *Deploy*. O cron acompanha, porque a variável é uma referência. A lista `VIGORIA_EMAILS_PERMITIDOS` deixa de contar e pode ficar como está. Na Ajuda, a pergunta «Porque é que não consigo usar a Vigoria?» desaparece sozinha.

Para voltar atrás, põe de novo `convidados`. Quem não estiver na lista deixa de conseguir entrar, mas as contas e os dados ficam guardados.

## 10. Testes manuais antes de convidar pessoas

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

1. Em «A minha conta», confirma que os lembretes estão ligados. Faz o envio de teste do serviço cron (passo 7.4, com `--testar-envio`) ou espera pelo envio das 9h07.
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
| Endereços de app.vigoria.pt na aplicação `Vigoria` do Auth0 | passo 3.1 | por fazer |
| `VIGORIA_ACESSO=convidados` e lista de convidados preenchida | Railway, passo 9 | por fazer |
| Demo desligada: app e Secrets do Streamlit Cloud apagados, endereços streamlit.app retirados do Auth0 | passo 6 | por fazer |
| Bloqueio de IPs do Brevo desligado | Brevo | por fazer |

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Registos: `arranque: ERRO: Variáveis em falta: …` | Variável do Auth0 por definir no serviço web. |
| Registos: `Configuração inválida: … VIGORIA_GEMINI_PAGO` | Falta `VIGORIA_GEMINI_PAGO=true` no serviço (web ou cron). Só se põe depois de a faturação do projeto `vigoria-producao` estar ativa. |
| Registos: `groq: HTTP 400 (code=json_validate_failed, …)` | O modelo do Groq gerou um JSON fora do schema. A app repete sozinha; só é preocupante se acontecer muitas vezes seguidas. |
| «A entrada com conta ainda não está configurada» | Não devia acontecer em produção, porque o arranque falha antes. Se acontecer, envia-me os registos do arranque. |
| Login volta com erro «Callback URL mismatch» | `AUTH_REDIRECT_URI` diferente das *Allowed Callback URLs* da aplicação `Vigoria` no Auth0, ou app.vigoria.pt ainda não foi acrescentado (passo 3.1). |
| Toda a gente vê «apenas por convite» e, nos registos, `VIGORIA_ACESSO=convidados com VIGORIA_EMAILS_PERMITIDOS vazia` | Lista de convidados vazia ou por definir no serviço web (passo 9). |
| Uma pessoa convidada vê «apenas por convite» | O email na lista é diferente do da conta com que entrou (por exemplo, entrou com outro Gmail). |
| O login com Google mostra um aviso de chaves de desenvolvimento | Falta o cliente OAuth próprio (passo 3.2). |
| «Há muitas pessoas a preparar o plano» | Mais de 3 minutos na fila: várias gerações seguidas. Nos registos, procura `fila:` e `429 por minuto`. |
| Planos falham sempre com «muitos pedidos» | Groq no plano gratuito (limite de tokens por minuto). Ver o passo 2. |
| «O serviço que prepara os planos não está disponível» e, nos registos, `limite de gasto mensal atingido` | Teto de 5 $ atingido. Ver «Quando o teto de gasto é atingido», no passo 2. |
