# Vigoria

*O seu plano, à sua medida.*

Aplicação web que gera planos pessoais de saúde e vitalidade — perda de gordura, força e mais energia — para adultos 45+ que treinam em casa, a partir de um questionário estruturado e de conteúdo editorial revisto, com apoio de inteligência artificial.

> A Vigoria sugere e orienta; não diagnostica nem trata. Não substitui o acompanhamento por profissionais de saúde.

## Documentação

- `docs/PLANO_IMPLEMENTACAO.md` — plano por fases
- `docs/ESTADO.md` — onde estamos
- `docs/GUIA_ARRANQUE_WINDOWS.md` — preparar o ambiente
- `docs/GUIA_AUTH0.md` — configurar as contas (Google e email/palavra-passe)
- `docs/GUIA_PRODUCAO.md` — pôr em produção (Railway, Neon, Auth0, Brevo, IA) e testes manuais
- `docs/dominio/` — regras de domínio e especificação do questionário
- `docs/referencia/` — Prompt Universal v2, Projeto Vitalidade Sénior (volumes 1 a 3), briefing de marca

## Arrancar em local

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m streamlit run app.py
```

## Produção (app.vigoria.pt)

```
Railway (EU West, Amesterdão), serviço web, uma réplica:
  Caddy na porta $PORT (HTTPS terminado no Railway; HSTS; manifesto e ícones da PWA)
    ├── /cancelar → Starlette/uvicorn (127.0.0.1:8001): cancelamento num clique (RFC 8058)
    └── resto     → Streamlit (127.0.0.1:8501)
Railway, serviço cron: python -m vigoria.tarefas.lembretes (7 9 * * * UTC) → Brevo
Neon (Frankfurt): PostgreSQL · Auth0 (UE): contas · IA: Gemini pago (principal), Groq (reserva)
```

O arranque (`python -m vigoria.arranque`) gera o `secrets.toml` a partir das variáveis do
Railway e aplica as migrações. Todos os passos manuais estão em `docs/GUIA_PRODUCAO.md`.
A demonstração no Streamlit Community Cloud continua com o mesmo código (`AMBIENTE=demo`).

Prova local da imagem (PowerShell, com o Docker Desktop):

```powershell
docker build -t vigoria .
docker run --rm -p 8080:8080 --env-file .env.docker vigoria
python scripts/fumo.py http://localhost:8080
```

## Fornecedores de LLM

O plano é gerado pelo fornecedor de `VIGORIA_PROVEDOR_LLM` (`gemini` por omissão; em
produção, o Gemini só com `VIGORIA_GEMINI_PAGO=true`). Com `VIGORIA_PROVEDOR_RESERVA`
definido (por exemplo, `groq`, ou o mesmo fornecedor com `VIGORIA_MODELO_RESERVA`), a reserva só entra quando o
principal falha de vez: 503/504 depois de 3 tentativas, sem resposta em 120 s, quota
diária esgotada ou pedido demasiado grande (413). O plano guarda qual dos dois o gerou
(`Plano.provedor`). Cada fornecedor precisa de `<NOME>_API_KEY` e `<NOME>_MODEL` no
`.env` (ver `.env.example`).

Confirmar chaves, modelos e rede (faz uma chamada mínima a cada fornecedor; na Groq e
na Mistral mostra também os limites da conta):

```powershell
python -m vigoria.motor.cli --testar-ligacao
```

Comparar fornecedores com o mesmo pedido (um plano por fornecedor, sem reserva; os planos
ficam em `saidas/comparacao/` e a CLI mostra tempo, tokens e uma pré-verificação):

```powershell
python -m vigoria.motor.cli --comparar gemini,mistral exemplos/persona_teste.json
```

Para acrescentar outro fornecedor com API compatível com a OpenAI (como `llm/mistral.py`):
uma subclasse de `ProvedorCompativelOpenAI` em `src/vigoria/llm/`, o nome em
`NomeProvedor` e as duas variáveis em `config.py`, e uma entrada em `llm/escolha.py`.
