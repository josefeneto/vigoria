# Guia de arranque — Windows, VS Code e Claude Code

Passos da **Fase 0**. Faça-os por ordem; cada um termina com uma verificação. Os comandos são para o **PowerShell** (o terminal do VS Code abre em PowerShell por omissão — a linha começa por `PS C:\...`).

---

## 1. Confirmar as ferramentas de base

Abra o PowerShell e corra:

```powershell
git --version
python --version
code --version
```

- **Git** em falta → instalar o Git for Windows (git-scm.com/downloads/win), opções por omissão. Traz o Git Bash, que o Claude Code usa para correr comandos.
- **Python**: o projeto usa o **3.14** (o que já está instalado). Se faltar, instalar a partir de python.org. No primeiro ecrã do instalador, **marcar «Add python.exe to PATH»**.
- **VS Code** em falta → code.visualstudio.com.

Feche e volte a abrir o terminal depois de cada instalação.

## 2. Instalar o Claude Code

Precisa de uma subscrição Claude Pro ou Max (o plano gratuito não inclui o Claude Code).

1. No VS Code: barra lateral → Extensões (`Ctrl+Shift+X`) → procurar **Claude Code** (editor: Anthropic) → Instalar.
2. Aparece um ícone ✱ na barra lateral. Clique e inicie sessão com a sua conta Claude.
3. Opcional, para usar também no terminal:
   ```powershell
   irm https://claude.ai/install.ps1 | iex
   ```
   Abra um terminal novo e confirme com `claude --version`. Diagnóstico completo: `claude doctor`.

## 3. Identidade no Git (só na primeira vez neste PC)

```powershell
git config --global user.name "José Neto"
git config --global user.email "o-seu-email-do-github"
git config --global init.defaultBranch main
```

## 4. Criar o repositório e a pasta do projeto

1. No GitHub, criar um repositório **privado** chamado `vigoria`, sem README (o kit já traz os ficheiros).
2. No PowerShell:
   ```powershell
   cd C:\Users\HP\My_Documents\_Projects
   git clone https://github.com/josefeneto/vigoria.git
   cd vigoria
   ```
   O Git avisa que o repositório está vazio — é normal.

## 5. Copiar o kit para a pasta

Descompacte o `vigoria-kit.zip` e copie **todo o conteúdo** para `C:\Users\HP\My_Documents\_Projects\vigoria`.

Atenção às pastas e ficheiros que começam por ponto (`.claude`, `.streamlit`, `.gitignore`, `.env.example`): no Explorador do Windows ficam visíveis em *Ver → Mostrar → Itens ocultos*. Confirme no PowerShell:

```powershell
Get-ChildItem -Force
```

Deve ver `.claude`, `.streamlit`, `.gitignore`, `.env.example`, `CLAUDE.md`, `docs` e `exemplos`.

**Documentos com dados pessoais reais** (por exemplo, o plano de validação de julho) vão para `docs\privado\` — a pasta está no `.gitignore` e o Claude Code está proibido de a ler.

## 6. Ambiente virtual Python

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Se aparecer um erro sobre «execution of scripts is disabled», corra uma vez:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

e repita a ativação. Com o ambiente ativo, a linha do terminal começa por `(.venv)`.

No VS Code: `Ctrl+Shift+P` → «Python: Select Interpreter» → escolher o que está em `.venv`.

## 7. Chave da LLM e ficheiro .env

1. Em aistudio.google.com, iniciar sessão com a conta Google → *Get API key* → criar chave.
2. Na mesma página, ver qual o modelo **Flash** disponível (a família 2.5 foi descontinuada a 16/10/2026).
3. Criar o `.env`:
   ```powershell
   Copy-Item .env.example .env
   code .env
   ```
   Preencher `GEMINI_API_KEY` e confirmar `GEMINI_MODEL`. Guardar.

Nunca cole a chave no chat do Claude Code. O `.env` está protegido: o Git ignora-o e o Claude Code não o pode ler.

## 8. Primeiro commit

```powershell
git add .
git status
```

Confirme que **não** aparecem `.env` nem `.venv`. Depois:

```powershell
git commit -m "Adiciona kit inicial: CLAUDE.md, regras e documentação"
git push -u origin main
```

## 9. Primeira conversa com o Claude Code

1. No VS Code, *Ficheiro → Abrir Pasta* → `C:\Users\HP\My_Documents\_Projects\vigoria`.
2. Abrir o painel do Claude Code (✱). Quando perguntar se confia na pasta, responder que sim.
3. Escrever `/context` e confirmar que `CLAUDE.md` aparece em *Memory files*.
4. Colar o prompt da Fase 0 (em `docs/PLANO_IMPLEMENTACAO.md`).

## Problemas frequentes

| Sintoma | Solução |
|---|---|
| `python` abre a Microsoft Store | Definições → Aplicações → Definições avançadas → *Aliases de execução de aplicações* → desligar os dois de Python; reinstalar o Python com «Add to PATH» |
| `claude` não é reconhecido | Abrir um terminal novo; se persistir, `claude doctor` ou reinstalar |
| O Claude Code diz que não encontra o Git Bash | Instalar o Git for Windows; em último caso, definir `CLAUDE_CODE_GIT_BASH_PATH` com `C:\Program Files\Git\bin\bash.exe` no `settings.json` do utilizador |
| Erro de autenticação no `git push` | O Git abre o browser para autorizar o GitHub; aceitar e repetir |
| O Streamlit não abre no browser | Abrir manualmente `http://localhost:8501` |
