# Guia de produção — app.vigoria.pt (Fase 10)

Passos que o José faz à mão para pôr a Vigoria em produção: Railway (EU West, Amesterdão), Neon (Frankfurt), Auth0 de produção, Google, Brevo e Groq. O código já está preparado; aqui só há configuração.

**Regras deste guia**
- Os valores secretos (chaves, palavras-passe, segredos) vão **só** para as variáveis do Railway. Nunca para o chat, o GitHub, ficheiros do projeto ou capturas de ecrã.
- Neste guia só aparecem **nomes** de variáveis. Os valores que não são secretos (endereços, nomes de modelos) aparecem por extenso.
- Os nomes dos menus podem mudar ligeiramente com o tempo. Se não encontrares um menu, diz-me o que vês no ecrã.

**Ordem recomendada:** cada passo precisa do anterior.

1. Neon (base de dados de produção)
2. Fornecedor de IA (Groq, ou Gemini pago) com teto de gasto
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

## 2. Fornecedor de IA (Groq ou Gemini pago)

**Decisão do fornecedor: depois da comparação** (ver «Comparação de qualidade», mais abaixo). Proposta atual: principal `openai/gpt-oss-120b`, reserva `openai/gpt-oss-20b`, ambos na Groq. O Gemini gratuito fica **desligado** em produção. O código recusa-o no arranque, salvo `VIGORIA_GEMINI_PAGO=true` (o nível gratuito do Gemini não pode servir utilizadores do EEE). Se a escolha for o Gemini pago, os passos equivalentes estão em «2.2 Se a escolha for o Gemini pago».

### 2.1 Groq

1. Em console.groq.com, cria uma organização para a Vigoria (ou usa a tua).
2. **Plano:** no plano gratuito, o limite é de 8000 tokens por minuto, e cada chamada gasta cerca de 7000 (teste de 12/11/2026). Na prática, só passa uma chamada por minuto, e um plano pode precisar de até 3. Antes do primeiro utilizador real, passa ao plano **Developer** (pago por utilização, sem mensalidade) em *Settings → Billing*. Confirma lá os limites dos dois modelos. Custo estimado: menos de 1 cêntimo de dólar por plano.
3. **Teto de gasto: 5 $ por mês.** Em *Settings → Billing → Spend limit* (ou equivalente), define um limite mensal de **5 $** e alertas por email aos **50 %, 75 % e 90 %**. Quando o limite é atingido, a Groq bloqueia a conta (erro `blocked_api_access`). A Groq só aplica o limite com cerca de **10 a 15 minutos de atraso**, por isso o gasto pode passar ligeiramente dos 5 $.
4. **Zero Data Retention:** ativa-o **antes do primeiro utilizador real**, em *Settings → Data Controls* (ou equivalente). Confirma na página que os pedidos não ficam guardados nem são usados para treino.
5. Cria uma chave em *API Keys → Create API Key*, com o nome `vigoria-producao`. Copia-a diretamente para o Railway (`GROQ_API_KEY`). É uma chave diferente da que usas em local.
6. **A CONFIRMAR (revisão jurídica):** o acordo de tratamento de dados (DPA) da Groq e a base da transferência para os EUA (cláusulas-tipo ou EU-US Data Privacy Framework). Ver a lista no fim deste guia.

### 2.2 Se a escolha for o Gemini pago

1. No Google AI Studio, liga uma conta de faturação ao projeto (*Billing*). Sem faturação, é o nível gratuito, e esse fica recusado em produção.
2. **Teto de gasto: 5 $ por mês.** Em *Billing → Monthly spend cap* do projeto, define **5 $**. No Google Cloud Console, em *Billing → Budgets & alerts*, cria um orçamento de 5 $ com alertas aos **50 %, 75 % e 90 %**. O teto bloqueia o serviço; o orçamento só avisa. O Google aplica o teto com cerca de **10 a 15 minutos de atraso**.
3. No Railway: `VIGORIA_PROVEDOR_LLM=gemini`, `GEMINI_MODEL`, `GEMINI_API_KEY` (secreto, chave nova do projeto pago) e `VIGORIA_GEMINI_PAGO=true`. Para a reserva, escolhe outro fornecedor ou outro modelo do Gemini.
4. **A CONFIRMAR (revisão jurídica):** os termos do Gemini pago para dados de utilizadores do EEE e a transferência para os EUA.

### Quando o teto de gasto é atingido

A app trata o erro como serviço temporariamente indisponível e não faz novas tentativas nem usa a reserva. A Groq aplica o teto à organização inteira, por isso a reserva também estaria bloqueada. Quem está a gerar um plano vê «O serviço que prepara os planos não está disponível neste momento…», e as respostas ficam guardadas. Nos registos do Railway aparece:

```
limite de gasto mensal atingido (groq, openai/gpt-oss-120b): subir o teto na consola ou esperar pelo mês seguinte
```

Para resolver: sobe o teto na consola ou espera pelo mês seguinte.

### Comparação de qualidade (antes de abrir o beta)

O `scripts/comparar_fornecedores.py` gera 10 planos (5 personas fictícias × Gemini e Groq 120b) e compara-os: falhas da verificação, menções a meses, palavras desconhecidas, tempo e tokens.

**Chama a LLM real:** corre-o só tu, à mão. Os planos gratuitos do Gemini e do Groq chegam, desde que haja uma pausa de 60 s entre personas. O script só usa as 5 personas fictícias de `exemplos/`. No PowerShell, na pasta do projeto, com o `.venv` ativo:

```powershell
python scripts/comparar_fornecedores.py --modelo-groq openai/gpt-oss-120b --pausa 60
```

Demora cerca de 6 a 8 minutos. Se aparecer «nova tentativa daqui a … s», é uma espera normal. Com Ctrl+C, guarda as personas já completas.

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
| `VIGORIA_PROVEDOR_LLM` | `groq` |
| `GROQ_API_KEY` | secreto (passo 2) |
| `GROQ_MODEL` | `openai/gpt-oss-120b` |
| `VIGORIA_PROVEDOR_RESERVA` | `groq` |
| `VIGORIA_MODELO_RESERVA` | `openai/gpt-oss-20b` |
| `VIGORIA_EMAILS_PERMITIDOS` | os emails do beta, separados por vírgulas |
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
| `VIGORIA_PROVEDOR_LLM` | `groq` (a tarefa não chama a LLM, mas a configuração é validada e recusa o Gemini em produção) |
| `VIGORIA_SEGREDO_LEMBRETES` | referência ao serviço web (tem de ser **o mesmo**) |
| `VIGORIA_EMAILS_PERMITIDOS` | referência ao serviço web |
| `BREVO_API_KEY` | secreto (chave API do Brevo; pode ser uma nova, `lembretes-producao`) |
| `EMAIL_REMETENTE` | `geral@vigoria.pt` |
| `EMAIL_NOME_REMETENTE` | `Vigoria` |

4. Para testar sem esperar pelo dia seguinte, muda **temporariamente** o *Custom Start Command* para `python -m vigoria.tarefas.lembretes --simular`. Carrega em *Deploy* e lê os registos. Depois volta ao comando normal.

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
3. Faz os testes manuais (lista na Fase 10D): iPhone, Android, Gmail e cancelamento num clique.

---

## A CONFIRMAR antes do primeiro utilizador real

| O quê | Onde está | Estado |
|---|---|---|
| Fornecedor de IA escolhido (depois da comparação) | passo 2 | por decidir |
| Teto de gasto de 5 $/mês com alertas aos 50/75/90 % | consola do fornecedor | por fazer |
| Zero Data Retention ativo na Groq | consola da Groq | por fazer |
| DPA da Groq e base da transferência para os EUA | revisão jurídica | por confirmar |
| Texto do consentimento de saúde em produção (tratamento pela IA nos EUA, sem uso para treino) | `paginas/textos.py`, `CONSENTIMENTO_SAUDE_PRODUCAO` | por confirmar (revisão jurídica) |
| Fornecedor de IA na política de privacidade e em «Onde ficam os meus dados?» | Fase 10D | por fazer |
| Segredos novos em produção (`AUTH_COOKIE_SECRET`, `VIGORIA_SEGREDO_LEMBRETES`) | Railway | por fazer |
| Bloqueio de IPs do Brevo desligado | Brevo | por fazer |

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Registos: `arranque: ERRO: Variáveis em falta: …` | Variável do Auth0 por definir no serviço web. |
| Registos: `Configuração inválida: … VIGORIA_GEMINI_PAGO` | `VIGORIA_PROVEDOR_LLM` não está definida (o valor por omissão é o Gemini) ou a reserva é o Gemini. |
| «A entrada com conta ainda não está configurada» | Não devia acontecer em produção, porque o arranque falha antes. Se acontecer, envia-me os registos do arranque. |
| Login volta com erro «Callback URL mismatch» | `AUTH_REDIRECT_URI` diferente das *Allowed Callback URLs* do tenant de produção. |
| «Há muitas pessoas a preparar o plano» | Mais de 3 minutos na fila: várias gerações seguidas. Nos registos, procura `fila:` e `429 por minuto`. |
| Planos falham sempre com «muitos pedidos» | Groq no plano gratuito (limite de tokens por minuto). Ver o passo 2. |
| «O serviço que prepara os planos não está disponível» e, nos registos, `limite de gasto mensal atingido` | Teto de 5 $ atingido. Ver «Quando o teto de gasto é atingido», no passo 2. |
