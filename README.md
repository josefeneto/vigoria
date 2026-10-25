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
pip install -r requirements-dev.txt
streamlit run app.py
```
