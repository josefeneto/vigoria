# Vigoria

*O seu plano, à sua medida.*

Aplicação web que gera planos pessoais de saúde e vitalidade — perda de gordura, força e mais energia — para adultos 45+ que treinam em casa, a partir de um questionário estruturado e de conteúdo editorial revisto, com apoio de inteligência artificial.

> A Vigoria sugere e orienta; não diagnostica nem trata. Não substitui o acompanhamento por profissionais de saúde.

## Documentação

- `docs/PLANO_IMPLEMENTACAO.md` — plano por fases
- `docs/ESTADO.md` — onde estamos
- `docs/GUIA_ARRANQUE_WINDOWS.md` — preparar o ambiente
- `docs/GUIA_AUTH0.md` — configurar as contas (Google e email/palavra-passe)
- `docs/dominio/` — regras de domínio e especificação do questionário
- `docs/referencia/` — Prompt Universal v2, Projeto Vitalidade Sénior (volumes 1 a 3), briefing de marca

## Arrancar em local

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m streamlit run app.py
```

## Fornecedores de LLM

O plano é gerado pelo fornecedor de `VIGORIA_PROVEDOR_LLM` (`gemini` por omissão). Com
`VIGORIA_PROVEDOR_RESERVA` definido (por exemplo, `groq`), a reserva só entra quando o
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
