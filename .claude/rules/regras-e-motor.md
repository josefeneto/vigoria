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
- Qualquer alteração a um prompt em `prompts/` exige: (1) incrementar a versão no cabeçalho do ficheiro, (2) pedir-me que corra o teste real com a persona (eu defino `VIGORIA_TESTES_LLM_REAIS=1` e corro `python -m pytest -m llm -k persona`; tu nunca), (3) registar a alteração em `docs/ESTADO.md`.
- A verificação (`motor/verificacao.py`) tem de confirmar, no mínimo: disclaimer presente; sinais de interrupção presentes; ganho muscular ≤ 0,5 kg por cada 4 semanas; ritmo de perda de peso dentro do limite da faixa etária (0,4 / 0,5 / 0,6 %/semana); nenhum exercício fora da biblioteca; nenhum termo da lista negra de suplementos; texto sem brasileirismos da lista em `conteudo/avisos.yaml`.
- No MVP, só entram no plano exercícios com `nivel: base` (REGRAS_DOMINIO §6.3); a verificação rejeita qualquer outro. Cada condição e limitação do questionário segue a tabela §1.1 — se encontrares uma opção sem regra, para e pergunta-me. Onde o Vol. 2 e as REGRAS_DOMINIO divergirem, prevalecem as REGRAS_DOMINIO.
- A persona de teste (`exemplos/persona_teste.json`) é fictícia. Não uses dados reais de ninguém em fixtures, exemplos ou commits.
