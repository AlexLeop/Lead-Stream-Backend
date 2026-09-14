# Design Técnico: Motor Unificado de Leads e API Canônica Escalável (v2.4.0)

**Data**: 2026-09-14  
**Status**: Aprovado para Planejamento  
**Foco**: Backend DRF, Banco de Dados (PostgreSQL), Motor de Busca Polimórfico e Desacoplamento Canônico

---

## 1. Visão Geral e Objetivos

O objetivo deste projeto é transformar o subsistema de consulta e listagem de leads do **LeadStream** em uma engine corporativa de alto desempenho para clientes B2B, eliminando limitações de protótipo (hardcoded `[:50]`, N+1 queries, strings formatadas no backend e ausência de dados cadastrais/econômicos reais).

### Metas Técnicas
1. **Fonte Única de Verdade Canônica**: Utilizar diretamente os contratos canônicos v2.4.0 já existentes ([`CanonicalLeadPayload`](file:///c:/Users/lxleo/Documents/Meus%20projetos/LeadStream-Backend/src/leadstream/canonical/contracts.py) para PJ e [`PersonCanonicalLeadPayload`](file:///c:/Users/lxleo/Documents/Meus%20projetos/LeadStream-Backend/src/leadstream/canonical/contracts.py) para PF).
2. **Separação de Responsabilidades (SoC)**: O backend fornece **apenas dados brutos, primitivos e estruturados** (números puros `float`/`int`, dígitos limpos sem pontuação, booleans, enums e datas ISO 8601). O frontend é 100% responsável por máscaras e formatação visual.
3. **Busca Polimórfica e Paginação Real**: Servir `GET /api/v1/leads/` com paginação padrão DRF (`page`, `page_size`), suportando bases de mais de 100.000 leads com tempo de resposta `< 50ms`.
4. **Eliminação Total de N+1 Queries**: Realizar leitura em lote (`select_related` + `prefetch_related`), garantindo no máximo 2 a 3 queries SQL por página de listagem.
5. **Tratamento Integral de PF e PJ**: Suportar tanto empresas com seus quadros de sócios/decisores (PJ) quanto decisores e pessoas físicas independentes sem vínculo societário (PF direta e crédito consignado).
6. **Conformidade LGPD e Evidência**: Preservar estados de evidência ([`EvidenceStatus`](file:///c:/Users/lxleo/Documents/Meus%20projetos/LeadStream-Backend/src/leadstream/entities/models.py)) e respeitar supressões ativas.

---

## 2. Contrato de Dados da API (Tipagem Primitiva e Desformatada)

O endpoint de listagem (`GET /api/v1/leads/`) e o de detalhe canônico (`GET /api/v1/leads/<id>/canonical/`) retornarão os dados desformatados:

### 2.1 Schema de Pessoa Jurídica (PJ)
* **Identificadores**: `id` (UUID), `lead_type: "PJ"`, `cnpj_raw` (14 dígitos), `cnpj_raiz` (8 dígitos), `cnpj_ordem` (4 dígitos), `cnpj_dv` (2 dígitos).
* **Cadastrais**: `razao_social` (string), `nome_fantasia` (string|null), `situacao_cadastral` (enum: `"ATIVA"`, `"BAIXADA"`, etc.), `data_situacao_cadastral` (ISO date), `data_abertura` (ISO date), `idade_empresa_anos` (float).
* **Econômicos & Porte**:
  * `natureza_juridica`: `{"codigo": "206-2", "descricao": "Sociedade Empresária Limitada"}`
  * `porte`: enum (`"ME"`, `"EPP"`, `"DEMAIS"`)
  * `porte_sebrae`: enum
  * `capital_social`: float (`500000.0`)
  * `faturamento_estimado_anual`: float (`4800000.0`)
  * `faixa_faturamento`: string categórica canônica
  * `quantidade_funcionarios_estimada`: int (`65`)
  * `optante_simples`: bool|null
  * `optante_simei`: bool|null
* **CNAE**:
  * `cnae_principal`: `{"codigo": "6201501", "descricao": "...", "setor": "Tecnologia", "grau_risco": 1}`
  * `cnaes_secundarios`: lista de objetos `{"codigo": "...", "descricao": "..."}`
* **Endereço (Estabelecimento Matriz/Filial)**:
  * `tipo_logradouro`, `logradouro`, `numero`, `complemento`, `bairro`, `municipio`, `uf`, `cep` (8 dígitos limpos), `codigo_ibge_municipio` (7 dígitos).
* **Telecom & Canais Digitais (com evidência)**:
  * `telefones`: lista de objetos `{"tipo": "FIXO_COMERCIAL"|"MOVEL_CELULAR", "ddd": "11", "numero": "33334444", "numero_e164": "+551133334444", "operadora": "VIVO", "validado": true, "whatsapp_ativo": true, "confianca": 0.95}`
  * `emails`: lista de objetos `{"endereco": "contato@empresa.com.br", "tipo": "CORPORATIVO"|"GRATUITO", "status": "ENTREGAVEL"|"Catch-all", "mx_found": true, "smtp_check": true, "confianca": 0.90}`
  * `dominio`: string|null, `website`: string|null
  * `redes_sociais`: `{"linkedin": "...", "instagram": "...", "facebook": "..."}`
* **QSA / Decisores Mapeados**:
  * `decisores`: lista de sócios e administradores com contatos diretos estruturados:
    * `id` (UUID da pessoa)
    * `nome` (string)
    * `cargo_observado` (string)
    * `senioridade` (enum: `"C_LEVEL"`, `"DIRECTOR"`, `"MANAGER"`, `"OWNER"`, etc.)
    * `qualificacao_socio` (enum: `"SOCIO_ADMINISTRADOR"`, `"SOCIO"`, etc.)
    * `cpf_mascarado` (string)
    * `contatos_diretos`: `{"email": "...", "ddd": "11", "numero": "988887777", "whatsapp_ativo": true, "linkedin_url": "..."}`
* **Inteligência Financeira e Fiscal**:
  * `instituicoes_bancarias`: lista de bancos detectados (`Nu Pagamentos`, `Itaú`, `Bradesco`, etc.)
  * `chaves_pix`: lista de chaves com titularidade validada
  * `situacao_pgfn_divida_ativa`: enum (`"REGULAR"`, `"DEVEDOR"`, `"NADA_CONSTA"`)
* **Scores de Inteligência**:
  * `score_confianca_global`: float (0.0 a 1.0)
  * `lead_score`: int (0 a 100)
  * `lead_temperature`: enum (`"COLD"`, `"WARM"`, `"HOT"`)
  * `updated_at`: ISO 8601 datetime

---

### 2.2 Schema de Pessoa Física (PF)
* **Identificadores**: `id` (UUID), `lead_type: "PF"`, `nome` (string), `cpf_mascarado` (string), `cpf_numerico` (11 dígitos).
* **Cadastrais & Demográficos**:
  * `data_nascimento`: ISO date|null
  * `idade`: int|null
  * `genero`: string|null
  * `situacao_cadastral_rfb`: enum (`"REGULAR"`, `"CANCELADA"`, etc.)
  * `score_credito`: int|null
* **Vínculo Empresarial (se houver)**:
  * `empresa_vinculada`: `{"id": UUID, "razao_social": "...", "cnpj_raw": "...", "cargo": "...", "qualificacao": "..."}`
* **Crédito Consignado (INSS / SIAPE)**:
  * `elegivel_consignado`: bool
  * `categoria_aptidao`: enum (`"APTO_CONSIGNAVEL"`, `"RESTRITO_BPC"`, `"BLOQUEADO_TEMPORARIO"`, `"INAPTO"`)
  * `especie_beneficio`: `{"codigo": "41", "descricao": "Aposentadoria por Idade"}`
  * `valor_beneficio_bruto`: float (`3000.0`)
  * `margens`: `{"margem_emprestimo_35": 1050.0, "margem_cartao_rmc_5": 150.0, "margem_cartao_rcc_5": 150.0, "margem_total_45": 1350.0}`
  * `filtro_nao_me_perturbe`: `{"bloqueado_procon": false, "apto_discagem": true}`
  * `filtro_obito`: `{"consta_obito": false}`
* **Telecom & Canais Pessoais**:
  * `telefones`: lista com DDD, número e status WhatsApp.
  * `emails`: lista com endereço e status MX/SMTP.
  * `linkedin_url`: string|null.
* **Scores**:
  * `score_confianca_global`: float
  * `updated_at`: ISO 8601 datetime

---

## 3. Arquitetura de Busca e Resolução de N+1 no PostgreSQL

### 3.1 Desacoplamento do CanonicalLeadBuilder
Atualmente o `CanonicalLeadBuilder` exige um `BatchItem`. Ele será refatorado para suportar duas fontes de entrada:
1. `build_from_batch_item(item: BatchItem) -> CanonicalLeadPayload` (fluxo de importação/processamento assíncrono).
2. `build_from_entity(entity: Entity) -> CanonicalLeadPayload | PersonCanonicalLeadPayload` (fluxo direto de entidades ativas no banco de dados operacional).

### 3.2 Estratégia de Consulta em Lote
A view `LeadsCollectionView` passará a operar em duas etapas otimizadas:
1. **Filtragem & Paginação em Nível de QuerySet**:
   * Aplicação dos filtros indexados (`tenant=request.tenant`, `q`, `uf`, `cnae`, `situacao`, `porte`, flags de contato).
   * Uso de `PageNumberPagination` nativo do DRF, limitando o `QuerySet` aos IDs da página corrente (ex: 25 IDs).
2. **Hidratação em Lote (Prefetch)**:
   * `Company.objects.filter(entity_id__in=page_ids).select_related('entity').prefetch_related('establishments', 'relationships__person__entity', 'entity__contact_points', 'entity__social_profiles')`.
   * `Person.objects.filter(entity_id__in=page_ids).select_related('entity').prefetch_related('relationships__company__entity', 'entity__contact_points', 'entity__social_profiles')`.
   * Montagem dos objetos em memória com custo constante de **3 queries SQL**, independentemente da quantidade de itens na página.

### 3.3 Índices de Suporte a Filtros B2B
* B-Tree em `leadstream_establishment(company_id, is_headquarters)`.
* B-Tree em `leadstream_contact_point(tenant_id, kind, status)`.
* B-Tree em `leadstream_entity(tenant_id, kind, updated_at)`.
* Índice composto em `leadstream_company(registration_status, cnpj_root)`.

---

## 4. Tratamento de Casos de Borda e Segurança (LGPD)

1. **Supressão e Opt-out (LGPD)**: Se um CPF, e-mail ou telefone estiver registrado em `leadstream_suppression` para o tenant, o registro não expõe o dado pessoal suprimido e sinaliza `status: "SUPPRESSED"`.
2. **Dados Ausentes vs Falsos**: Se um lead não possui faturamento ou telefone conhecido, os campos retornam `null` ou `0.0`, sem valores inventados ou deduções sintéticas (aderente ao princípio F-02 e F-03 do projeto).
3. **Idempotência e Segurança de Perímetro**: O endpoint exige autenticação por tenant e rejeita cabeçalhos ou campos de override de tenant.
