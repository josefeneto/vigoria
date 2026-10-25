---
paths:
  - "src/vigoria/regras/**"
  - "src/vigoria/motor/**"
  - "src/vigoria/conteudo/**"
  - "prompts/**"
  - "tests/**"
---

# Regras ao trabalhar no motor, nas regras de domínio e nos prompts

- Lê `docs/dominio/REGRAS_DOMINIO.md` antes de alterar qualquer cálculo, limiar ou decisão. Os valores vêm de lá; se precisares de um valor que lá não está, pergunta-me em vez de o escolher.
- Cada função em `regras/` é pura (sem I/O, sem LLM, sem datas «de agora» implícitas) e tem testes com casos-limite: valores exatamente nos limiares, ausência de dados opcionais, unidades erradas.
- Qualquer alteração a um prompt em `prompts/` exige: (1) incrementar a versão no cabeçalho do ficheiro, (2) correr `pytest -m llm -k persona` com a chave real **só se eu autorizar**, (3) registar a alteração em `docs/ESTADO.md`.
- A verificação (`motor/verificacao.py`) tem de confirmar, no mínimo: disclaimer presente; sinais de interrupção presentes; ganho muscular ≤ 0,5 kg por cada 4 semanas; ritmo de perda de peso dentro do limite da faixa etária (0,4 / 0,5 / 0,6 %/semana); nenhum exercício fora da biblioteca; nenhum termo da lista negra de suplementos; texto sem brasileirismos da lista em `conteudo/avisos.yaml`.
- Exercícios de nível intermédio ou avançado do Vol. 2 só entram no plano se a estratégia cumprir todos os critérios de REGRAS_DOMINIO §6.3. Por omissão, usa sempre a variante-base da tabela §6.4. Onde o Vol. 2 e as REGRAS_DOMINIO divergirem, prevalecem as REGRAS_DOMINIO.
- A persona de teste (`exemplos/persona_teste.json`) é fictícia. Não uses dados reais de ninguém em fixtures, exemplos ou commits.
