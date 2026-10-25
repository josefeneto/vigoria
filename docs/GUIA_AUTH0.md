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
| Allowed Logout URLs | `http://localhost:8501` | `https://<app>.up.railway.app` |
| Allowed Web Origins | `http://localhost:8501` | `https://<app>.up.railway.app` |

Vários valores no mesmo campo separam-se por vírgulas. Guardar (*Save*) no fundo da página.

4. Copiar **Domain**, **Client ID** e **Client Secret** para o `.streamlit/secrets.toml` (modelo em `.streamlit/secrets.toml.example`). O *Client Secret* nunca vai para o chat nem para o GitHub.

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

Serve para mostrar a app a algumas pessoas durante as Fases 5 a 7, antes do Railway.

1. Em share.streamlit.io, entrar com o GitHub e criar a app a partir do repositório `vigoria`, ramo `main`, ficheiro `app.py`. Escolher um nome curto; o endereço fica `https://<nome>.streamlit.app`. Se o repositório for privado, aceitar a permissão extra que o Streamlit pede ao GitHub. Em *Advanced settings*, escolher **Python 3.14**.
2. No Auth0 (*Applications → Vigoria → Settings*), juntar aos valores locais, separados por vírgulas:
   - Allowed Callback URLs: `https://<nome>.streamlit.app/oauth2callback`
   - Allowed Logout URLs e Allowed Web Origins: `https://<nome>.streamlit.app`
3. Na app do Community Cloud, *Settings → Secrets*: colar o conteúdo do `secrets.toml` local com o `redirect_uri` trocado para `https://<nome>.streamlit.app/oauth2callback`, e juntar no topo as variáveis do `.env` que a app precisa (por exemplo `GEMINI_API_KEY = "..."`, `GEMINI_MODEL = "..."`, `AMBIENTE = "demo"`). O `secrets.toml` local fica como está.
4. Guardar, esperar que a app reinicie e repetir a verificação rápida da secção 6.

**Limitações (por isso só dados fictícios):**
- Os servidores ficam nos Estados Unidos e não é configurável. Dados de saúde reais exigiriam uma transferência internacional que não queremos no beta.
- O disco é temporário: a base SQLite perde-se em cada reinício ou nova publicação. Para guardar dados entre sessões, usar uma base PostgreSQL externa via `DATABASE_URL` (por exemplo, a do Railway com acesso público).
- A app adormece após algum tempo sem uso; o primeiro acesso a seguir é lento.
- Não há tarefas agendadas: os lembretes por email não correm lá.

Quando a app passar para o Railway (Fase 10), retirar do Auth0 os endereços `streamlit.app`.

## Pontos de atenção

- **Duas contas com o mesmo email.** Quem se regista com email e palavra-passe e mais tarde entra com Google (mesmo email) fica com duas contas distintas no Auth0. A app não as junta: mostra uma mensagem a pedir que use o método da primeira vez. Juntar contas automaticamente é possível, mas traz riscos de segurança; fica para depois do MVP, se fizer falta.
- **Terminar sessão.** Só `st.logout()` não basta, porque o Auth0 mantém a sua própria sessão. A app redireciona também para o logout do Auth0 (está no prompt da Fase 6).
- **Apagar conta.** Apagar na app tem de apagar também o utilizador no Auth0 (RGPD). O Claude Code propõe a forma na Fase 6.
- **Registos (logs) do Auth0** guardam IPs e entradas durante 1 dia no plano gratuito; referir o Auth0 como subcontratante na política de privacidade.
