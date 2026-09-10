# Phase 4 Research

- BigQuery usa cliente oficial, credenciais por ambiente e parâmetros nomeados; o template SQL
  fica configurável porque o schema OpenCNPJ pode evoluir.
- BigDataCorp autentica com `AccessToken` e `TokenId` e recebe consultas `doc{...}` nas APIs de
  empresas/pessoas.
- Apify inicia actor pela API v2 e lê o `defaultDatasetId`; execução longa é assíncrona.
- Adaptadores usam `httpx`, timeout explícito e payloads validados, sem importar respostas brutas
  diretamente ao domínio.

Referências oficiais: https://docs.cloud.google.com/python/docs/reference/bigquery/latest/
https://docs.bigdatacorp.com.br/plataforma/reference/primeira-consulta
https://docs.apify.com/api/v2/getting-started
