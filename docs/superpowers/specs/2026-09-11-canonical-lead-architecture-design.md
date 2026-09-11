# Especificação Técnica de Arquitetura: Canonical Lead Payload 2.4.0

> **Documento de Design Arquitetural**  
> **Data:** 11/09/2026  
> **Status:** Proposto para Aprovação  
> **Módulo:** `leadstream.canonical`, `leadstream.intelligence`, `leadstream.validation`  

---

## 1. Visão Geral e Objetivos

O **LeadStream** passa a produzir e exportar uma representação enriquecida de alta fidelidade estruturada no formato **Canonical Lead Payload v2.4.0** (definido pelo contrato de referência `payload.json`).

O objetivo é transformar os dados brutos de provedores públicos (BigQuery/OpenCNPJ, Receita Federal, IBGE) e comerciais (Apify, BigDataCorp) em um objeto consolidado, enriquecido com inteligência econômica local, validações técnicas em tempo real e score comercial acionável.

### Metas Principais:
1. **Fidelidade Contratual:** O payload emitido pelo backend deve seguir 100% da tipagem, nomenclatura e estrutura das 14 seções do `payload.json`.
2. **Alta Performance em Escala:** Processar lotes de até 100.000 leads com persistência de snapshot em campo `JSONB` indexado no PostgreSQL (`BatchItem.canonical_payload`), permitindo consultas em < 5ms e exportações massivas em streaming.
3. **Inteligência Local Autônoma:** Resolução instantânea de CNAEs (descrição, setor, grau de risco), Naturezas Jurídicas, Porte Sebrae, Estimativa de Faturamento e Colaboradores sem chamadas externas lentas.
4. **Validação Técnica de Contatos:** Checagem assíncrona de registros DNS MX, SPF, DMARC, sintaxe RFC de e-mails, normalização E.164 e classificação ANATEL de telefones (fixo vs celular/WhatsApp).
5. **Qualificação Determinística:** Cálculo automático de `lead_score` (0-100), `lead_temperature` (`HOT`, `WARM`, `COLD`), `ideal_customer_profile_fit` e atribuição de `tags` comerciais.

---

## 2. Arquitetura de Componentes

```
+-----------------------------------------------------------------------------------+
|                              LEADSTREAM BACKEND CORE                              |
+-----------------------------------------------------------------------------------+
                                          |
          +-------------------------------+-------------------------------+
          |                               |                               |
          v                               v                               v
+-------------------+           +-------------------+           +-------------------+
|  leadstream.      |           |  leadstream.      |           |  leadstream.      |
|  intelligence     |           |  validation       |           |  canonical        |
+-------------------+           +-------------------+           +-------------------+
| - cnae.py         |           | - dns_mx.py       |           | - contracts.py    |
|   (IBGE/CONCLA)   |           |   (MX/SPF/DMARC)  |           |   (Pydantic v2)   |
| - natureza.py     |           | - email_check.py  |           | - builder.py      |
|   (CONCLA RFB)    |           |   (RFC/Disposable)|           |   (Compiler)      |
| - economics.py    |           | - phone_check.py  |           | - serializers.py  |
|   (Porte/Fat/Colab|           |   (E.164/ANATEL)  |           |   (DRF Exporter)  |
| - scoring.py      |           +-------------------+           +-------------------+
|   (Score/ICP/Tags)|                     |                               |
+-------------------+                     |                               |
          |                               |                               |
          +-------------------------------+-------------------------------+
                                          |
                                          v
                         +---------------------------------+
                         |      CanonicalLeadBuilder       |
                         +---------------------------------+
                                          |
                      +-------------------+-------------------+
                      |                                       |
                      v                                       v
        +---------------------------+           +---------------------------+
        |  PostgreSQL (Persistência)|           |  API REST & Exportação    |
        +---------------------------+           +---------------------------+
        | BatchItem.canonical_payload|           | GET /api/v1/leads/<id>/   |
        | (JSONB com GIN Index)     |           | Parquet / CSV / JSON Lote |
        +---------------------------+           +---------------------------+
```

---

## 3. Detalhamento dos Módulos

### 3.1. `leadstream.canonical.contracts` (Contrato de Tipos Pydantic v2)
Define o schema completo validado, compatível com `payload.json`:
* `MetaPayload`: `schema_version` ("2.4.0"), `canon_id`, `generated_at`, `tenant_id`, `pipeline_run_id`, `confidence_score_global`.
* `IdentificationPayload`: `lead_id`, `status`, `lead_score`, `lead_temperature`, `ideal_customer_profile_fit`, `tags`.
* `CompanyPayload`: Dados cadastrais completos da matriz/filial, situação cadastral, idade em anos, natureza jurídica, portes, regimes tributários, capital social formatado, faturamento estimado e faixas.
* `CnaePayload`: `principal` (código formatado, descrição, setor, grau de risco) e `secundarios` (lista de códigos e descrições).
* `AddressPayload`: Logradouro, número, complemento, bairro, cidade, UF, CEP, código IBGE, coordenadas e precisão.
* `ContactsPayload`: Listas de `telefones` (com status WhatsApp e operadora) e `emails` (com status técnico de entrega).
* `DecisionMakerPayload`: QSA detalhado com cargo executivo de mercado, nível hierárquico, poder de decisão e contatos diretos.
* `FinancialPayload`, `FiscalPayload`, `ForeignTradePayload`, `LegalPayload`, `DigitalPresencePayload`, `GovernancePayload`, `CrmOutboxPayload`: Seções prontas no schema, populadas pelas inteligências nativas e fontes conectadas.

### 3.2. `leadstream.intelligence` (Motores de Inferência Local)
* **`cnae.py`**:
  - Dicionário interno contendo a hierarquia completa de divisões e subclasses do IBGE CONCLA.
  - Normaliza códigos (ex: `8599603` -> `85.99-6-03`).
  - Mapeia o Setor Macro (ex: `Tecnologia da Informação`, `Educação`, `Comércio`) e o Grau de Risco de Acidente de Trabalho (NR-04: graus 1 a 4).
* **`natureza_juridica.py`**:
  - Tabela completa da Receita Federal (ex: `206-2` -> `Sociedade Empresária Limitada`, `213-5` -> `Empresário (Individual)`, `205-4` -> `Sociedade Anônima Fechada`).
* **`economics.py`**:
  - **Porte Sebrae:** Classifica em `MEI`, `MICRO_EMPRESA`, `PEQUENA_EMPRESA`, `MEDIA_EMPRESA` ou `GRANDE_EMPRESA` com base no faturamento estimado e setor (Indústria vs Comércio/Serviços).
  - **Regime Tributário:** Detecta se é `SIMEI`, `SIMPLES_NACIONAL`, `LUCRO_PRESUMIDO` ou `LUCRO_REAL` com base nos dados oficiais do Simples/MEI e capital.
  - **Faturamento Estimado & Faixas:** Modelo econométrico baseado em capital social declarado, porte RFB e multiplicador de giro setorial do CNAE principal.
  - **Estimativa de Funcionários:** Faixa inferida por regressão setorial (CNAE + Porte Sebrae).
* **`scoring.py`**:
  - **Lead Score (0-100):**
    - Empresa ATIVA: +30 pts
    - Decisor identificado (C-Level/Sócio): +25 pts
    - E-mail direto verificado (MX ativo): +25 pts
    - Telefone móvel/WhatsApp ativo: +20 pts
  - **Lead Temperature:** `HOT` (≥ 80), `WARM` (50–79), `COLD` (< 50).
  - **Tags Automáticas:** Ex: `Tier 1`, `WhatsApp Ativo`, `Simples Nacional`, `MEI`, `Decisor Encontrado`.

### 3.3. `leadstream.validation` (Validação Técnica de Contatos & DNS)
* **`dns_mx.py`**:
  - Verificação assíncrona de registros DNS `MX`, `SPF` e `DMARC` do domínio do e-mail.
  - Cache local no Redis com TTL de 24 horas (evita re-consultar `gmail.com`, `outlook.com`, etc.).
  - Retorna `mx_found: bool`, `smtp_check: bool`, `spf_status: str`, `dmarc_status: str`.
* **`email_check.py`**:
  - Validação estrita de sintaxe RFC 5322.
  - Detecção de domínios descartáveis/temporários (`disposable`).
  - Classificação do e-mail: `GENERICO_RECEITA`, `DEPARTAMENTAL`, `DIRETO_DECISOR` ou `GRATUITO`.
* **`phone_check.py`**:
  - Validação e normalização E.164 brasileira (`+55...`).
  - Classificação precisa: `FIXO` (8 dígitos + DDD) vs `MOVEL` (9 dígitos iniciando com 9 + DDD).
  - Mapeamento de DDD para Estado/Região e identificação da operadora por faixa de prefixo da ANATEL.
  - Indicação de probabilidade de WhatsApp (`tem_whatsapp: true` para números móveis válidos).

### 3.4. `leadstream.canonical.builder` (`CanonicalLeadBuilder`)
Compilador central que:
1. Coleta a identidade da empresa (`Company`, `Establishment`).
2. Agrega as observações auditadas de maior confiança (`CanonicalDecision`).
3. Recupera os sócios e relacionamentos (`Person`, `Relationship`, `ContactPoint`).
4. Executa os motores de inferência (`leadstream.intelligence`) e validações de contato (`leadstream.validation`).
5. Instancia e valida o `CanonicalLeadPayload` via Pydantic.
6. Salva o snapshot em `BatchItem.canonical_payload` e atualiza a pontuação do lead.

---

## 4. Mudanças no Banco de Dados

### Migração no app `batches`:
Adicionar ao modelo `BatchItem`:
```python
canonical_payload = models.JSONField(
    default=dict,
    blank=True,
    help_text="Snapshot consolidado do payload canônico v2.4.0."
)
```
Índice de busca:
```python
models.Index(fields=["tenant", "id"], name="batch_item_tenant_id_idx")
```

---

## 5. Endpoints e Contratos de API

1. **Consulta Individual do Lead Canônico:**
   - `GET /api/v1/leads/{id}/`
   - Retorna o JSON completo formatado no padrão v2.4.0.
2. **Exportação do Lote com Payload Canônico:**
   - `GET /api/v1/lotes/{id}/export/?format=json`
   - Exporta streaming com todos os leads do lote no formato do `payload.json`.

---

## 6. Plano de Testes & Verificação

1. **Testes Unitários:**
   - Teste do validador de CNAE (formatação, setor e grau de risco).
   - Teste do mapeador de Natureza Jurídica.
   - Teste do motor de estimativa econômica (porte sebrae, faturamento estimado, faixas).
   - Teste do validador de e-mail e DNS MX com mock assíncrono.
   - Teste do normalizador de telefone e classificação ANATEL.
   - Teste do motor de Lead Score e temperatura.
2. **Teste de Integração End-to-End:**
   - Executar o `CanonicalLeadBuilder` contra o CNPJ `48.944.179/0001-61` e comparar o resultado gerado com o `payload.json` de referência.
   - Validar performance de compilação (< 10ms por lead).
   - Executar a suite completa do `pytest` assegurando 100% de aprovação.
