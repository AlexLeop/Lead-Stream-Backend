# Phase 4 Context — Descoberta e Enriquecimento Real

## Objective

Executar uma cascata Brasil-first que parte do CNPJ, encontra o decisor e adiciona somente
contatos/perfis atribuíveis à pessoa, sob orçamento, proveniência e limites globais.

## Locked Decisions

- OpenCNPJ consultado seletivamente no BigQuery; nenhuma base nacional na VPS.
- BigDataCorp complementa empresa/pessoa; Apify executa actors explicitamente configurados.
- Open Enrich e provedor premium são fallbacks, nunca fontes silenciosas de verdade.
- Tokens ficam no ambiente; SQL, datasets e actor IDs são configuração versionável sem segredo.
- Provedor retorna observações/candidatos. Só o domínio canônico decide fatos.
- Toda chamada gera custo, latência, resultado e chave idempotente.
- Circuit breaker, rate limit e orçamento são globais entre workers.
- Conteúdo privado, login, CAPTCHA, paywall ou violação de robots não são permitidos.
