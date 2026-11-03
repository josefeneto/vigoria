# Guia Auth0 — contas da Vigoria

Passos manuais da **Fase 6**. Ao fim, a app aceita entradas com Google ou com email e palavra-passe, e o Auth0 trata do registo, da confirmação do email e da recuperação de palavra-passe.

Plano gratuito do Auth0: até 25 000 utilizadores ativos por mês, ligação de base de dados (email e palavra-passe), ligações sociais e um domínio personalizado (este último exige validação de cartão de crédito). Confirmar em auth0.com/pricing antes do lançamento público.

---

## 1. Criar a conta e o tenant

1. Em auth0.com, criar conta (pode entrar com a conta Google).
2. Ao criar o primeiro *tenant*, escolher a região **EU (Europe)**. Não se muda depois: se ficar noutra região, é preciso criar outro tenant.
3. Nome sugerido do tenant: `vigoria` (fica no domínio `vigoria.eu.auth0.com`).

## 2. Criar a aplicação

1. *Applications → Applications → Create Application*.
2. Nome: `Vigoria`. Tipo: **Regular Web Applications**. Ignorar a escolha de tecnologia.
3. No separador *Settings*, preencher:

| Campo | Valor em local | Acrescentar em produção (Fase 10) |
|---|---|---|
| Allowed Callback URLs | `http://localhost:8501/oauth2callback` | `https://<app>.up.railway.app/oauth2callback` |
| Allowed Logout URLs | `http://localhost:8501/oauth2callback` | `https://<app>.up.railway.app/oauth2callback` |
| Allowed Web Origins | `http://localhost:8501` | `https://<app>.up.railway.app` |

Vários valores no mesmo campo separam-se por vírgulas. Guardar (*Save*) no fundo da página.

4. Copiar **Domain**, **Client ID** e **Client Secret** para o `.streamlit/secrets.toml` (modelo em `.streamlit/secrets.toml.example`). O *Client Secret* nunca vai para o chat nem para o GitHub.
5. No `secrets.toml`:
   - `server_metadata_url`: `https://{tenant}.eu.auth0.com/.well-known/openid-configuration`, com `{tenant}` trocado pelo nome do tenant (o mesmo do *Domain*).
   - `cookie_secret`: um texto aleatório longo, que assina o cookie da sessão. Gerar no PowerShell com `python -c "import secrets; print(secrets.token_hex(32))"` e colar o resultado. Usar um diferente em cada ambiente (local, Cloud, Railway).
   - `redirect_uri`: **é diferente em cada ambiente** — `http://localhost:8501/oauth2callback` em local e `https://<nome>.streamlit.app/oauth2callback` no Cloud. Tem de constar das *Allowed Callback URLs* e das *Allowed Logout URLs*.

**Terminar sessão.** O `st.logout()` do Streamlit (1.66) termina também a sessão no Auth0 e volta ao endereço `/oauth2callback` (por isso é esse que entra nas *Allowed Logout URLs*). Para isso, o Auth0 tem de anunciar o seu endpoint de logout: em *Settings → Advanced → Login and Logout*, confirmar que **RP-Initiated Logout End Session Endpoint Discovery** está ligado (nos tenants recentes já vem ligado).

## 3. Ligações (métodos de entrada)

*Authentication → Database → Username-Password-Authentication*:
- No separador *Applications*, confirmar que a `Vigoria` está ligada.
- *Password Policy*: escolher **Good** ou superior.
- Deixar ativa a opção de permitir registos (*Disable Sign Ups* desligado).

*Authentication → Social → Google*:
- Ativar e ligar à aplicação `Vigoria`.
- Para testar em local, as chaves de desenvolvimento do Auth0 bastam (aparece um aviso). **Antes do lançamento público** é obrigatório criar um cliente OAuth próprio no Google Cloud Console e colar aqui o Client ID e o Secret. O Auth0 indica nessa página o URI de redirecionamento a usar no Google.

Na aplicação `Vigoria`, separador *Connections*, desligar tudo o que não sejam estas duas.

## 4. Língua e aparência

- *Settings → General → Languages*: idioma por omissão **Portuguese (Portugal)**, se estiver disponível na lista; confirmar que a página de entrada aparece em PT-EU e não em português do Brasil.
- *Branding → Universal Login*: logótipo (quando existir), cor principal `#1F5C63`, fundo `#F7F3EC`.

## 5. Emails do Auth0 (confirmação e recuperação)

- *Branding → Email Templates*: rever em PT-EU os modelos de **Verification Email** e **Change Password**. Remetente: `Vigoria`.
- O fornecedor de email que o Auth0 traz de origem serve só para testes, com limites baixos. Na Fase 8 (ou na 10, o mais tardar), configurar em *Branding → Email Provider* a **Brevo por SMTP**, com o mesmo remetente dos lembretes.

## 6. Verificação rápida

1. Preencher o `secrets.toml` e arrancar a app (`streamlit run app.py`).
2. «Entrar ou criar conta» → criar uma conta com email e palavra-passe → confirmar a mensagem de verificação de email → abrir o email e confirmar → entrar.
3. Terminar sessão e entrar com Google.
4. No painel do Auth0, *User Management → Users*: devem aparecer os dois utilizadores.

## 7. Testar online no Streamlit Community Cloud (opcional, só com dados fictícios)

Serve para mostrar a app a algumas pessoas convidadas durante as Fases 5 a 7, antes do Railway. A app usa o Gemini real (com a Groq de reserva) e mostra em todas as páginas a faixa «Versão de demonstração — não introduza dados reais de saúde. Os dados são processados em servidores fora da UE.» Depois de criada, **atualiza-se sozinha a cada `git push` para o `main`**.

### 7.1 Criar a app (uma vez)

1. Em share.streamlit.io, entrar com a conta do GitHub. Aceitar a permissão extra para repositórios privados que o Streamlit pede ao GitHub.
2. *Create app* e escolher a opção de publicar a partir de um repositório do GitHub (os nomes dos menus podem mudar; com repositório privado, a app fica privada).
3. Preencher:
   - Repository: `josefeneto/vigoria`
   - Branch: `main`
   - Main file path: `app.py`
   - App URL: um nome curto; o endereço fica `https://<nome>.streamlit.app`.
4. *Advanced settings*:
   - Python version: **3.14** (o projeto exige 3.14; se não aparecer na lista, parar e avisar o Claude Code).
   - Secrets: colar o modelo da secção 7.2 com os valores preenchidos.
5. *Deploy*. A primeira instalação demora alguns minutos (o Cloud instala o `requirements.txt`, que inclui o próprio projeto com `-e .`).
6. Na app, *Settings → Sharing*: confirmar que só as pessoas convidadas podem ver a app e convidá-las por email. Cada plano gerado gasta a quota do Gemini, por isso convidar só quem vai testar.

### 7.2 Modelo dos Secrets (TOML)

Copiar os valores do `.env` local (nunca para o chat nem para o git). Só as chaves de topo: as variáveis do ambiente e do `.env` têm prioridade, por isso este modelo só é usado no Cloud.

```toml
AMBIENTE = "demo"
VIGORIA_PROVEDOR_LLM = "gemini"
VIGORIA_PROVEDOR_RESERVA = "groq"
GEMINI_API_KEY = ""
GEMINI_MODEL = ""
GROQ_API_KEY = ""
GROQ_MODEL = ""
```

A partir da Fase 6 (login), juntar por baixo as secções `[auth]`, `[auth.auth0]` e `[auth0_gestao]` do `secrets.toml` local, com o `redirect_uri` trocado para `https://<nome>.streamlit.app/oauth2callback` e um `cookie_secret` novo. Para os dados não se perderem a cada reinício, juntar também às chaves de topo o `DATABASE_URL` do Neon (secção 9). No Auth0 (*Applications → Vigoria → Settings*) juntar aos valores locais, separados por vírgulas:
- Allowed Callback URLs e Allowed Logout URLs: `https://<nome>.streamlit.app/oauth2callback`
- Allowed Web Origins: `https://<nome>.streamlit.app`

Depois, repetir a verificação rápida da secção 6.

### 7.3 Verificação rápida

1. Abrir `https://<nome>.streamlit.app`: aparece a faixa de demonstração no topo de todas as páginas.
2. Preencher o questionário com dados fictícios e gerar o plano.
3. Se der erro, *Manage app* (canto inferior direito) mostra os registos: copiar para o Claude Code só a mensagem de erro, sem chaves.

**Limitações (por isso só dados fictícios):**
- Os servidores ficam nos Estados Unidos e não é configurável. Dados de saúde reais exigiriam uma transferência internacional que não queremos no beta.
- O disco é temporário: a base SQLite perde-se em cada reinício ou nova publicação. Para guardar dados entre sessões, usar a base PostgreSQL do Neon via `DATABASE_URL` (secção 9).
- A app adormece após algum tempo sem uso; o primeiro acesso a seguir é lento.
- Não há tarefas agendadas: os lembretes por email não correm lá.

Quando a app passar para o Railway (Fase 10), retirar do Auth0 os endereços `streamlit.app`.

## 8. Apagar contas no Auth0 (aplicação Machine to Machine)

Quando a pessoa apaga a conta na Vigoria, a app apaga também a conta de entrada no Auth0, pela *Management API*. Para isso precisa de uma segunda aplicação, só com a permissão de apagar utilizadores.

1. *Applications → Applications → Create Application*. Nome: `Vigoria gestão`. Tipo: **Machine to Machine Applications**.
2. Na pergunta seguinte, escolher a API **Auth0 Management API**.
3. Em *Permissions*, escrever `delete:users` no filtro e marcar **só** essa permissão. Carregar em *Authorize*.
   - Para confirmar mais tarde: *Applications → APIs → Auth0 Management API → Machine To Machine Applications*: a `Vigoria gestão` aparece *Authorized* e, ao abrir a seta, só tem `delete:users`.
4. No separador *Settings* da `Vigoria gestão`, copiar o **Client ID** e o **Client Secret** para a secção `[auth0_gestao]` do `secrets.toml` (local e Cloud). Nunca para o chat nem para o GitHub.
5. Testar: criar uma conta de teste, entrar, «A minha conta» → apagar. Em *User Management → Users*, a conta deve ter desaparecido.

Sem a secção `[auth0_gestao]`, a app continua a apagar os dados da Vigoria e regista o identificador da conta para apagar à mão (ver «Pontos de atenção»).

## 9. Base de dados no Neon (PostgreSQL, Frankfurt)

Em local, a app usa SQLite (`vigoria_local.db`, que não vai para o Git). Para os dados ficarem guardados no Cloud (e mais tarde no Railway, se for essa a escolha), usar o Neon:

1. Em neon.tech, criar conta e um projeto `vigoria` na região **AWS Europe Central 1 (Frankfurt)**.
2. Em *Connection Details*, copiar o endereço de ligação (formato `postgresql://<utilizador>:<palavra-passe>@ep-….eu-central-1.aws.neon.tech/<base>?sslmode=require`).
3. Colar como `DATABASE_URL` nos *Secrets* do Cloud (chave de topo) ou no `.env` local, se quiser testar contra o Neon. A app converte sozinha o início do endereço para o controlador `psycopg`.
4. As tabelas criam-se sozinhas no primeiro arranque (migrações Alembic). Também se podem aplicar à mão no PowerShell: `python -m alembic upgrade head` (usa o `DATABASE_URL` da configuração).

## Pontos de atenção

- **Duas contas com o mesmo email.** Quem se regista com email e palavra-passe e mais tarde entra com Google (mesmo email) fica com duas contas distintas no Auth0. A app não as junta: mostra uma mensagem a pedir que use o método da primeira vez. Juntar contas automaticamente é possível, mas traz riscos de segurança; fica para depois do MVP, se fizer falta.
- **Terminar sessão.** O `st.logout()` termina as duas sessões (Streamlit e Auth0), desde que a opção da secção 2 esteja ligada.
- **Apagar conta.** A app apaga primeiro os dados da Vigoria e depois a conta no Auth0 (secção 8). Se o Auth0 falhar, a pessoa vê que os dados foram apagados e que a conta de entrada será removida em breve; nos registos da app fica a linha «conta Auth0 por apagar», só com o identificador técnico (por exemplo `auth0|65f…`), sem email. Apagar essa conta à mão em *User Management → Users* (procurar pelo identificador).
- **Registos (logs) do Auth0** guardam IPs e entradas durante 1 dia no plano gratuito; referir o Auth0 como subcontratante na política de privacidade.
