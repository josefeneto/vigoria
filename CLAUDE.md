# Vigoria — instruções para o Claude Code

<!-- Ficheiro carregado em todas as sessões. Manter abaixo de ~200 linhas.
     Detalhe de domínio: docs/dominio/. Regras por pasta: .claude/rules/. -->

## O projeto em duas frases

A Vigoria é uma aplicação web progressiva (PWA), desenhada de raiz para telemóvel e para computador, que gera planos pessoais de saúde e vitalidade — perda de gordura, preservação ou ganho de massa muscular, mais energia — para adultos 45+ que treinam em casa. O plano nasce de um questionário estruturado (Prompt Universal v2) e de conteúdo editorial já validado (Projeto Vitalidade Sénior, volumes 1 a 3), com a IA a personalizar e não a inventar.

Estado atual e próximos passos: ver `docs/ESTADO.md` (atualizar no fim de cada fase).
Plano completo por fases: `docs/PLANO_IMPLEMENTACAO.md`.

## Como trabalhar comigo (José)

- Responde sempre em **Português Europeu (AO90)**. Nada de brasileirismos: ficheiro, ecrã, utilizador, guardar, descarregar, executar/correr, registo, telemóvel, equipa.
- Tenho pouca prática de programação recente. Explica o que vais fazer em linguagem simples, em poucos passos, e diz-me que comando correr quando for eu a fazê-lo (indica se é PowerShell ou Git Bash).
- Para qualquer tarefa que mexa em mais de um ficheiro, apresenta primeiro um plano curto e espera pela minha aprovação.
- Prefiro avaliações honestas a otimistas. Se uma abordagem tiver riscos ou limitações, diz-mo logo.
- Nunca apagues ficheiros, faças `git push`, alteres dados em produção ou mudes dependências principais sem confirmação explícita.
- No fim de cada tarefa: resume em 3–5 linhas o que mudou, que testes correram e o que falta.

## Ambiente

- Windows 11, VS Code com a extensão Claude Code, terminal PowerShell; Git for Windows instalado (Git Bash disponível).
- Python 3.14 (versão instalada no PC; produção usa a mesma), ambiente virtual em `.venv` (ativar: `.venv\Scripts\Activate.ps1`).
- Pasta local: `C:\Users\HP\My_Documents\_Projects\vigoria`. Repositório GitHub: `josefeneto/vigoria`.
- Produção: Railway (região europeia), com Docker. Base de dados: SQLite em local, PostgreSQL em produção.
- Segredos só em `.env` (local) e `.streamlit/secrets.toml` (autenticação). **Nunca** os leias, copies para o chat, registes em logs ou incluas em commits. Modelo de variáveis: `.env.example`.

## Comandos

```powershell
python -m venv .venv ; .venv\Scripts\Activate.ps1   # criar/ativar ambiente
pip install -r requirements-dev.txt                  # dependências (inclui as de produção)
streamlit run app.py                                 # app em http://localhost:8501
pytest -q                                            # todos os testes
pytest -q -m "not llm"                               # testes sem chamadas reais à LLM (por omissão)
# Testes com a LLM real: só o José os corre, à mão (ver «Testes»). O Claude Code nunca os executa.
ruff check . --fix ; ruff format .                   # lint e formatação
python -m vigoria.motor.cli exemplos/persona_teste.json   # gerar plano sem interface
```

Antes de dar uma tarefa por concluída: `ruff check .` e `pytest -q -m "not llm"` têm de passar.

## Arquitetura

```
app.py                  ponto de entrada Streamlit (navegação, tema, autenticação)
paginas/                páginas Streamlit: questionário, plano, progresso, conta, privacidade
src/vigoria/
  modelos/              Pydantic: Questionario, Perfil, Estrategia, Plano, Registo
  regras/               cálculos e decisões determinísticas — SEM LLM (IMC, cintura, hidratação, proteína, elegibilidade, intensidade)
  conteudo/             YAML editorial: exercicios.yaml, fases.yaml, alimentacao.yaml, avisos.yaml
  motor/                pipeline de geração (ver abaixo) + cli.py
  llm/                  interface ProvedorLLM; gemini.py (principal), groq.py (reserva)
  dados/                SQLAlchemy 2.x, repositórios, migrações Alembic
  notificacoes/         envio de email (Brevo)
  exportacao/           plano em PDF/DOCX
  tarefas/              lembretes (executado por cron no Railway)
pwa/                    manifest.webmanifest, sw.js, ícones, página offline, Caddyfile (camada PWA à frente do Streamlit)
prompts/                prompts de sistema versionados (.md) — nunca embutidos no código
tests/                  pytest; fixtures em tests/fixtures/
docs/                   plano, estado, domínio, referência
```

Desenho **mobile-first**: cada ecrã é pensado primeiro para telemóvel (cerca de 390 px) e depois alargado para computador.

Princípio central: **a interface não tem lógica de negócio**. Tudo o que decide ou calcula vive em `src/vigoria/` e é testável sem Streamlit.

## Pipeline de geração (os cinco papéis)

1. **Acolhimento** (`motor/acolhimento.py`, determinístico): valida e normaliza o questionário, calcula indicadores, deteta incoerências.
2. **Estratégia** (`motor/estrategia.py`, determinístico): decide intensidade efetiva, ênfase, módulos condicionais (gordura visceral), avisos obrigatórios e se o plano pode ser gerado.
3. **Gerador** (`motor/gerador.py`, LLM): uma chamada ao Gemini com saída JSON estruturada (schema Pydantic `Plano`), alimentada pela estratégia e pelo conteúdo editorial. A voz de marca está no prompt de sistema.
4. **Verificação** (`motor/verificacao.py`, híbrido): verificações determinísticas obrigatórias + revisão crítica opcional por LLM. Se falhar, uma única regeneração com o motivo; se voltar a falhar, devolve erro claro ao utilizador.
5. **Voz de marca** (`motor/voz.py`): pós-processamento leve (termos técnicos explicados, deteção de brasileirismos, formatação para a interface).

Máximo de 3 chamadas à LLM por plano: geração, revisão crítica e, se preciso, uma regeneração. A regeneração passa só pelas verificações em código, sem nova revisão pela LLM. Sem CrewAI no MVP (decisão registada em `docs/PLANO_IMPLEMENTACAO.md`, secção 2).

## Regras de segurança do domínio (inegociáveis)

O detalhe e os valores estão em `docs/dominio/REGRAS_DOMINIO.md`. Em resumo:

- Os números (IMC, limiares de cintura, proteína, hidratação, ritmo máximo de perda de peso por idade, 0,5 kg de músculo por cada 4 semanas) são calculados em `regras/`, **nunca** pela LLM. A LLM recebe-os já calculados.
- IMC ≥ 35 ⇒ modo prudente com teto «Ligeira». As condições e limitações do questionário levam ou não a modo prudente segundo a tabela 1.1 das REGRAS_DOMINIO (por exemplo, hipertensão controlada fica na versão-base).
- Disclaimer e sinais para interromper o exercício presentes em **todos** os planos (testado).
- Proibido recomendar produtos, chás ou suplementos «queima-gordura»; suplementos só com a ressalva de validação clínica.
- Exercícios só da biblioteca em `conteudo/exercicios.yaml`; a LLM escolhe e adapta, não inventa. No MVP, sempre a variante-base; as variantes avançadas nunca entram no plano (REGRAS_DOMINIO §6.3).
- Programa sempre de 16 semanas (4 fases); tudo em semanas, nunca em meses.
- A app não diagnostica nem trata. Linguagem de bem-estar, nunca de diagnóstico.
- Só maiores de 18 anos. Gravidez: não gera plano.

## Contas e acesso aos dados

- **Login obrigatório** antes do questionário. Sem sessão iniciada, só são visíveis a página de entrada, a política de privacidade e os termos.
- Autenticação com `st.login("auth0")` (Streamlit + Auth0). O Auth0 trata do registo, palavras-passe, verificação de email e recuperação; a app **nunca** guarda palavras-passe. Métodos: Google, ou email e palavra-passe. Guia: `docs/GUIA_AUTH0.md`.
- Telemóvel e email pertencem ao modelo `Utilizador`, nunca ao `Questionario`.
- O utilizador é identificado pelo `sub` do token (identificador permanente), **nunca** pelo email. A conta na base de dados cria-se automaticamente no primeiro login.
- Contas com email e palavra-passe só acedem depois de `email_verified` ser verdadeiro.
- Se o mesmo email já existir com outro método de entrada, não juntar contas: mostrar «Já existe uma conta com este email. Entre com o método que usou da primeira vez.»
- Todas as consultas a dados do utilizador passam por funções em `dados/` que recebem o `utilizador_id` obrigatório. Teste obrigatório: o utilizador A nunca consegue ler nem alterar dados do utilizador B.
- `st.logout()` não termina a sessão no Auth0; o terminar sessão tem também de redirecionar para o endpoint de logout do Auth0.

## Dados pessoais e RGPD

- Dados de saúde são categoria especial (art. 9.º RGPD): consentimento explícito antes do questionário, finalidade clara, exportar e apagar conta disponíveis.
- Telemóvel opcional (nacional por omissão, internacional com lista de países), validado com `phonenumbers` e guardado em E.164.
- **Nunca** enviar à LLM nome, email, telemóvel ou identificadores. Só os dados do questionário necessários ao plano, pseudonimizados.
- Não registar respostas de saúde em logs. Logs só com identificadores técnicos.
- Publicidade (futura) nunca pode usar dados de saúde para segmentação.

## Convenções de código

- Python 3.14 (`requires-python = ">=3.14"`), tipagem em todas as funções públicas, Pydantic v2 para modelos, SQLAlchemy 2.x.
- Nomes de módulos, classes e funções de domínio em português sem acentos (`calcular_imc`, `Questionario`); termos técnicos genéricos podem ficar em inglês (`client`, `retry`).
- Docstrings e comentários em PT-EU, curtos. Textos visíveis ao utilizador em `paginas/` ou `prompts/`, nunca espalhados pelo código.
- Testes: cada regra em `regras/` tem testes com casos-limite. Chamadas à LLM marcadas com `@pytest.mark.llm` e simuladas por omissão. Os testes `llm` só correm de verdade com a variável `VIGORIA_TESTES_LLM_REAIS=1`; sem ela, o `conftest.py` salta-os. Nunca definas essa variável nem corras esses testes: pede-me para o fazer.
- Configuração por variáveis de ambiente lidas num único sítio (`src/vigoria/config.py`); em alternativa, de `st.secrets` (Streamlit Community Cloud, `AMBIENTE=demo`, só dados fictícios).
- Modelo da LLM configurável (`GEMINI_MODEL`); não fixar nomes de modelos no código.

## Git

- Um ramo por fase (`fase-02-regras`), commits pequenos com mensagens em PT-EU no imperativo («Adiciona cálculo de hidratação»).
- Antes de commit: lint e testes. Nunca commit de `.env`, `secrets.toml`, bases de dados locais ou ficheiros em `docs/privado/`.
- `git push` e merge para `main` só depois de eu confirmar.

## Documentação de referência

- Questionário: `docs/dominio/QUESTIONARIO.md` (derivado de `docs/referencia/Prompt_Universal_Saude_Vitalidade_v2.md`)
- Regras de domínio: `docs/dominio/REGRAS_DOMINIO.md`
- Conteúdo editorial: `docs/referencia/Projeto_Vitalidade_Senior_Volume_*.md`
- Marca (nome, tom, cores): `docs/referencia/Vigoria_Briefing_Marca.md`
