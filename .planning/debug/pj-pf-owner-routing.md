---
status: resolved
trigger: "Teste de CNPJ sem contatos ou decisores, MEI apresentado de forma ambígua com Simples, dossiê PF incompleto com mensagens operacionais e usuário proprietário roteado para a tela do cliente."
created: 2026-09-16
updated: 2026-09-16
---

## Symptoms

- expected: Enriquecimento PJ entrega contatos disponíveis, resolve decisores, apresenta MEI/Simples corretamente; PF mostra o dossiê contratado sem telemetria; proprietário acessa a administração global.
- actual: CNPJ retorna cadastro sem contatos/decisores; MEI e Simples aparecem como duas adesões independentes; PF está incompleto e exibe mensagens internas; proprietário cai na experiência do cliente.
- errors: Nenhuma mensagem técnica de erro foi apresentada nos prints.
- timeline: Reproduzido no teste realizado após o deploy atual.
- reproduction: Enriquecer um CNPJ MEI, abrir o dossiê e autenticar com o usuário proprietário.

## Current Focus

- hypothesis: Confirmada.
- test: Regressões backend, suíte completa, lint, tipos e build do frontend.
- expecting: Consulta individual executa cascata durável, PF solicita o preset completo e proprietário global entra na administração isolada.
- next_action: publicar a branch validada e promover a conta proprietária via variáveis de deploy.
- reasoning_checkpoint: Todos os sintomas foram rastreados até caminhos distintos e corrigidos sem inventar dados ausentes.
- tdd_checkpoint: 249 testes passaram; 2 testes de integração externa permanecem ignorados por design.

## Evidence

- `enrich_company_live` retornava após BrasilAPI/Minha Receita e nunca chamava `run_enrichment_cascade`; somente lotes usavam BigQuery, BigDataCorp, Apify e fallbacks.
- O seletor PF enviava apenas `cpf_cadastral` e o identificador obsoleto `phones_whatsapp_garantido`; `government_intelligence` não fazia parte do preset enviado.
- O frontend imprimia nomes de provedores, credenciais e variáveis do EasyPanel dentro das seções públicas do dossiê.
- O login sempre navegava para `dashboard`; a opção administrativa era apenas um item condicional dentro da mesma navegação do cliente.
- A branch `main` estava em `9d48758`, enquanto as correções anteriores do Portal/PF estavam em `codex/production-hardening` (`7137139`).

## Eliminated

- O cadastro MEI não estava factualmente errado: SIMEI é modalidade vinculada ao Simples Nacional. O defeito era a apresentação como duas adesões independentes.
- A ausência de contatos não era causada pelo componente de renderização: os arrays já chegavam vazios porque os provedores complementares não eram acionados no fluxo individual.

## Resolution

- root_cause: Divergência entre os pipelines individual e em lote, preset PF incompleto/obsoleto, cópia operacional exposta no DTO público e ausência de roteamento por escopo global.
- fix: A consulta PJ individual ganhou contexto durável idempotente e cascata completa; decisores, contatos e redes são consolidados por pessoa; políticas permitem WhatsApp; MEI é exibido como SIMEI; PF padrão inclui dados governamentais e ganhou resumo cadastral; mensagens internas foram removidas; superusuário entra em uma navegação global isolada.
- verification: `249 passed, 2 skipped`; Ruff sem achados; mypy sem erros em 6 módulos; build Vite/TypeScript concluído.
- files_changed: `live_enrichment.py`, `live_enrichment_person.py`, `orchestrator.py`, `registry.py`, `enrichment_jobs.py`, catálogo de analytics, App/Context/Login/AppShell/Enrichment/types, ambiente e testes de regressão.
