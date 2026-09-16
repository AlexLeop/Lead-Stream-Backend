export type EmailStatus = 'Não verificado' | 'Verificado' | 'Catch-all' | 'Inválido';
export type DecisionLevel = 'C-Level' | 'VP' | 'Diretoria' | 'Gerência' | 'Especialista' | 'Autônomo / Consultor' | 'Profissional Liberal';
export type LeadType = 'PJ' | 'PF';
export type EvidenceStatus =
  | 'ABSENT'
  | 'OBSERVED'
  | 'INFERRED'
  | 'TECHNICALLY_VALIDATED'
  | 'CONFIRMED'
  | 'CONFLICTING'
  | 'REJECTED';

export interface Lead {
  id: string;
  leadType: LeadType; // 'PJ' (Pessoa Jurídica) ou 'PF' (Pessoa Física)
  name: string;
  title: string;
  seniority: DecisionLevel;
  company: string;
  domain: string;
  location: string;
  city: string;
  state: string;
  country: string;
  email: string;
  phone: string;
  phoneRevealed?: boolean;
  status: EmailStatus;
  companySize: string;
  employeeCount: number;
  industry: string;
  annualRevenue: string;
  fundingStage: string;
  technologies: string[];
  intentScore: number;
  fitScore?: number;
  opportunityScore?: number;
  dataConfidenceScore?: number;
  freshnessScore?: number;
  intentTopic: string;
  avatar?: string;
  initials: string;
  linkedinUrl: string;
  enriched: boolean;
  listIds?: string[];
  setId?: string; // ID do Conjunto ao qual pertence
  setName?: string; // Nome do Conjunto
  notes?: string;
  source?: string;
  observedAt?: string;
  verifiedAt?: string;
  identityEvidenceStatus: EvidenceStatus;
  emailEvidenceStatus: EvidenceStatus;
  phoneEvidenceStatus: EvidenceStatus;
  whatsappEvidenceStatus: EvidenceStatus;
  createdAt?: string;
  updatedAt?: string;
  
  // Campos específicos de Pessoa Jurídica (PJ)
  cnpj?: string;
  nomeFantasia?: string;
  razaoSocial?: string;
  cnae?: string;
  cnaesSecundarios?: Array<{ codigo: string; descricao: string }>;
  capitalSocial?: string;
  naturezaJuridica?: string;
  opcaoSimples?: string;
  opcaoMei?: string;
  logradouro?: string;
  numero?: string;
  complemento?: string;
  bairro?: string;
  cep?: string;
  municipio?: string;
  uf?: string;
  socios?: string[];
  sociosDetails?: Array<{
    nome: string;
    cargo: string;
    qualificacao: string;
    papelCompra: string;
    faixaEtaria?: string;
    dataEntrada?: string;
    cpfMascarado?: string;
    regiaoFiscal?: string;
    telefone?: string;
    telefoneSecundario?: string;
    whatsappLink?: string;
    whatsappAtivo?: boolean;
    email?: string;
    linkedinUrl?: string;
    instagramUrl?: string;
    facebookUrl?: string;
    twitterUrl?: string;
  }>;
  situacaoCadastral?: string;
  dataAbertura?: string;
  companyLinkedinUrl?: string;
  companyInstagramUrl?: string;
  companyFacebookUrl?: string;
  companyTwitterUrl?: string;
  instagramDecisorUrl?: string;
  pgfnStatus?: string;
  instituicaoBancaria?: string;
  chavePix?: string;
  pixKeyCandidates?: Array<{
    id: string;
    keyType: 'CNPJ' | 'CPF' | 'EMAIL' | 'PHONE' | 'EVP';
    maskedValue: string;
    evidenceStatus: 'CANDIDATE' | 'OBSERVED' | 'VALIDATED' | 'REJECTED';
    subjectScope: 'COMPANY' | 'DECISION_MAKER';
    sourceField: string;
    sourceProvider: string;
    sourceUrl?: string;
    observedAt: string;
  }>;
  bankRelationships?: Array<{
    id: string;
    institutionName?: string;
    ispb?: string;
    compe?: string;
    scope: 'COMPANY' | 'DECISION_MAKER' | 'UNKNOWN';
    relationshipType: 'PUBLIC_BANK_MENTION' | 'PIX_KEY_OWNER' | 'BOLETO_ISSUER' | 'PROVIDER_REPORTED';
    evidenceStatus: 'OBSERVED' | 'TECHNICALLY_VALIDATED' | 'CONFIRMED' | 'CONFLICTING';
    provider: string;
    sourceUrl?: string;
    ownerName?: string;
    ownerDocumentMasked?: string;
    ownerDocumentMatch: boolean;
    confidence: number;
    observedAt: string;
    expiresAt?: string;
  }>;
  governmentRisk?: {
    status?: 'MATCH_FOUND' | 'NO_MATCH_ON_CHECKED_SOURCES' | 'NOT_QUERIED_NO_PROFILE_FLAG';
    has_matches?: boolean;
    match_count?: number;
    checked_sources?: string[];
    pagination?: string;
    records?: Array<{
      source: string;
      record_id?: number | string;
      sanctioned_name?: string;
      document?: string;
      sanction_type?: string;
      reason?: string;
      status?: string;
      sanctioning_organ?: string;
      responsible_organ?: string;
      starts_on?: string;
      ends_on?: string;
      published_on?: string;
      publication_url?: string;
      process_number?: string;
      fine_value?: string;
    }>;
  };
  governmentRiskObservedAt?: string;
  governmentIntelligence?: {
    indexed_in_portal?: boolean;
    profile?: {
      name?: string;
      professional_flags?: Record<string, boolean>;
    };
    pep?: {
      has_matches?: boolean;
      match_count?: number;
      records?: Array<Record<string, unknown>>;
    };
    coverage?: Record<string, { records?: number; pages_checked?: number; truncated?: boolean }>;
    executed_endpoints?: string[];
    skipped_endpoints?: Array<{ endpoint: string; reason: string }>;
    strategy?: string;
    sensitive_sources_excluded?: string[];
  };
  publicSectorProfile?: {
    indexed_in_portal?: boolean;
    profile?: {
      legal_name?: string;
      trade_name?: string;
      flags?: Record<string, boolean>;
    };
    has_federal_contracts?: boolean;
    contract_count?: number;
    contracts?: Array<{
      record_id?: number | string;
      number?: string;
      object?: string;
      process_number?: string;
      status?: string;
      signed_on?: string;
      starts_on?: string;
      ends_on?: string;
      managing_unit?: string;
      initial_value?: number;
      final_value?: number;
      details?: Record<string, unknown>;
    }>;
    invoice_count?: number;
    invoices?: Array<Record<string, unknown>>;
    tax_waivers?: {
      values?: Array<Record<string, unknown>>;
      immune_or_exempt?: Array<Record<string, unknown>>;
      enabled_benefits?: Array<Record<string, unknown>>;
    };
    resources_received_count?: number;
    resources_received?: Array<Record<string, unknown>>;
    expense_document_count?: number;
    expense_documents?: Array<Record<string, unknown>>;
    card_transaction_count?: number;
    card_transactions?: Array<Record<string, unknown>>;
    server_records?: Array<Record<string, unknown>>;
    permission_records?: Array<Record<string, unknown>>;
    travel_records?: Array<Record<string, unknown>>;
    card_records?: Array<Record<string, unknown>>;
    unresolved_signals?: {
      agreements?: boolean;
      procurement_participant?: boolean;
    };
    coverage?: Record<string, { records?: number; pages_checked?: number; truncated?: boolean }>;
    executed_endpoints?: string[];
    skipped_endpoints?: Array<{ endpoint: string; reason: string }>;
    strategy?: string;
  };
  publicSectorObservedAt?: string;
  commercialPhoneSecondary?: string;

  // Campos específicos de Pessoa Física (PF)
  cpf?: string; // Mascarado ex: 284.***.***-12
  profissao?: string;
  faixaRenda?: string;
  escolaridade?: string;
  scoreCredito?: number;
  qualificacaoRfb?: string;
  papelCompra?: string;
  faixaEtaria?: string;
  dataEntradaSociedade?: string;
  regiaoFiscal?: string;
  facebookUrl?: string;
}

export interface LeadSearchParams {
  page?: number;
  pageSize?: number;
  q?: string;
  leadType?: 'PJ' | 'PF';
  datasetId?: string;
  uf?: string;
  city?: string;
  cnae?: string;
  companySize?: string;
  registrationStatus?: string;
  seniority?: string;
  title?: string;
  emailStatus?: 'all' | 'verified' | 'catchall' | 'invalid';
  hasEmail?: boolean;
  hasPhone?: boolean;
}

export interface LeadSearchResponse {
  count: number;
  page: number;
  pageSize: number;
  totalPages: number;
  nextPage: number | null;
  previousPage: number | null;
  facets: { PJ: number; PF: number };
  results: Lead[];
}

export interface PixLookupStatus {
  enabled: boolean;
  termsApproved: boolean;
  purpose: string;
  payerConfigured: boolean;
  lookupReady: boolean;
  automaticEligibility: 'ONLY_EXPLICIT_PUBLIC_PIX_KEY';
  providers: Array<{
    name: string;
    priority: number;
    configured: boolean;
  }>;
}

export type LeadSetCategory = 
  | 'Prospecção Outbound'
  | 'Enriquecimento Cadastral'
  | 'Campanha ABM & Enterprise'
  | 'Eventos & Feiras'
  | 'Validação de Base'
  | 'Reativação de Churn'
  | 'Base Inbound'
  | 'Geral';

export interface LeadSet {
  id: string;
  name: string;
  category: string;
  description?: string;
  leadType: 'PJ' | 'PF' | 'MISTO';
  totalLeads: number;
  enrichedFields: EnrichmentFieldId[];
  status: 'Processando' | 'Enriquecido' | 'Pronto' | 'Parcial';
  enrichmentRate: number; // Porcentagem (ex: 98)
  createdAt: string;
  leadIds: string[];
  fileOriginName?: string;
  costCredits?: number;
  lastUpdated?: string;
  tags?: string[];
}


export type EnrichmentFieldId = 
  | 'emails_smtp'
  | 'phones_whatsapp'
  | 'cnpj_qsa'
  | 'cpf_cadastral'
  | 'technologies'
  | 'intent_signals'
  | 'linkedin_job'
  | 'revenue_size'
  | 'income_bracket';

export interface EnrichmentFieldOption {
  id: EnrichmentFieldId;
  label: string;
  description: string;
  applicableFor: 'ALL' | 'PJ' | 'PF';
  creditsCost: number;
  matchRate: string;
  iconName: string;
  category: 'Contato' | 'Cadastral' | 'Inteligência';
}

export interface Activity {
  id: string;
  type: string;
  title: string;
  subtitle: string;
  time: string;
  badgeColor?: string;
}

export interface CampaignList {
  id: string;
  name: string;
  description?: string;
  leadCount: number;
  lastSynced: string;
  crmTarget: 'HubSpot' | 'Salesforce' | 'RD Station' | 'Pipedrive' | 'Não configurado' | string;
  crmStatus: string;
  validCount: number;
  catchAllCount: number;
  invalidCount: number;
  leadIds: string[];
  createdAt: string;
  updatedAt?: string;
  isArchived?: boolean;
}

export interface ListLeadsResponse {
  count: number;
  results: Lead[];
  truncated: boolean;
}

export interface CRMConnection {
  id: string;
  name: string;
  code: string;
  iconBg: string;
  status: string;
}

export interface GrowthDataPoint {
  day: string;
  leads: number;
  validados: number;
  enriquecidos: number;
}

export interface WorkspaceSummary {
  companies: number;
  contacts: number;
  datasets: number;
  lists: number;
}

export interface DashboardSummary {
  contacts: number;
  companies: number;
  datasets: number;
  lists: number;
  validEmails: number;
  deliverabilityRate: number;
  phones: number;
  inMarketAccounts: number;
  actionableRecords: number;
}

export interface BreakdownDataPoint {
  name: string;
  value: number;
  count: number;
  color?: string;
}

export interface DashboardData {
  summary: DashboardSummary;
  chartData: GrowthDataPoint[];
  industryBreakdown: BreakdownDataPoint[];
  seniorityBreakdown: BreakdownDataPoint[];
}

export interface CreateDatasetInput {
  name: string;
  category: string;
  description?: string;
  leadType: 'PJ' | 'PF' | 'MISTO';
  tags?: string[];
}

export interface CreateListInput {
  name: string;
  description?: string;
  crmTarget?: string;
  leadIds?: string[];
}

export interface ImportPayload {
  sourceFileName: string;
  datasetId?: string;
  dataset?: CreateDatasetInput;
  records: Array<Record<string, string | number | string[] | null>>;
}

export interface ImportResult {
  dataset: LeadSet;
  imported: number;
  companies: number;
  contacts: number;
  skipped: number;
  leads: Lead[];
}

export interface DataHealthCoverage {
  id: string;
  label: string;
  value: number;
  count: number;
  total: number;
}

export interface DataHealthIssue {
  id: string;
  label: string;
  count: number;
  severity: 'high' | 'medium' | 'low' | 'clear';
  description: string;
  actionRoute: string;
}

export interface DataHealthData {
  generatedAt: string;
  summary: {
    overallScore: number;
    companies: number;
    contacts: number;
    totalEntities: number;
    actionableRecords: number;
    incompleteRecords: number;
    staleRecords: number;
    duplicateCandidates: number;
    lineageCoverage: number;
  };
  coverage: DataHealthCoverage[];
  issues: DataHealthIssue[];
  distribution: { healthy: number; attention: number; critical: number };
  dimensions: {
    identityScore: number;
    contactabilityScore: number;
    profileScore: number;
    verificationScore: number;
    lineageScore: number;
  };
  quarantine: {
    quarantined: number;
    pendingReview: number;
    released: number;
    lastClassifiedAt: string | null;
  };
}

export interface EnrichmentStatus {
  available: boolean;
}

export type EnrichmentCapabilityGroupId = 'company' | 'sales' | 'operations' | 'risk';

export interface EnrichmentCapabilityGroup {
  id: EnrichmentCapabilityGroupId;
  label: string;
  description: string;
}

export interface EnrichmentCapability {
  id: string;
  groupId: EnrichmentCapabilityGroupId;
  label: string;
  description: string;
  highlights: string[];
  depth: 'Essencial' | 'Detalhado' | 'Avançado';
}

export interface EnrichmentPreset {
  id: string;
  label: string;
  description: string;
  capabilityIds: string[];
}

export interface EnrichmentCatalog {
  groups: EnrichmentCapabilityGroup[];
  capabilities: EnrichmentCapability[];
  presets: EnrichmentPreset[];
}

export interface EnrichmentRun {
  id: string;
  entityType: string;
  query: string;
  capabilities: string[];
  status: 'QUEUED' | 'RUNNING' | 'SUCCEEDED' | 'NO_DATA' | 'FAILED';
  matchedEntityId?: string;
  errorMessage?: string;
  costCredits?: number;
  attemptCount?: number;
  startedAt?: string | null;
  completedAt?: string | null;
  createdAt?: string;
  updatedAt?: string;
  purgeAfter?: string;
  purgedAt?: string | null;
}

export interface EnrichmentJob<T> extends EnrichmentRun {
  result?: T | null;
}

export interface EnrichedCompanySummary {
  name: string;
  legalName: string;
  cnpj: string;
  domain: string;
  status: string;
  industry: string;
  cnae: string;
  companySize: string;
  annualRevenue: string;
  capitalSocial?: string;
  city: string;
  state: string;
  technologies: string[];
  branchCount: number | null;
  partnerCount: number;
  emailCount: number;
  phoneCount: number;
  siteCount: number;
  observedAt: string;
}

export interface CompanyEnrichmentResult {
  runId: string;
  capabilities: string[];
  companyId: string;
  company: EnrichedCompanySummary;
  registryEvidence?: {
    source: string;
    observedAt: string;
    method: 'API' | 'CACHE' | 'DATASET';
    status: 'OBSERVED' | 'INFERRED' | 'VALIDATED' | 'CONFIRMED';
  };
  coverage: {
    requested: number;
    available: number;
    fieldCount: number;
    recordCount: number;
  };
  contatosCadastraisEmpresa?: Array<{
    tipo: 'EMAIL' | 'TELEFONE';
    valor: string;
    fonte: string;
  }>;
  sections: Array<{
    id: string;
    title: string;
    description: string;
    status: 'available' | 'empty' | 'unavailable';
    summary: string;
    fields: Array<{ label: string; value: string }>;
    items: Array<{ title: string; fields: Array<{ label: string; value: string }> }>;
    errorMessage?: string;
  }>;
}

export interface FiltroPerdaData {
  status: 'REGULAR' | 'EXPURGADO_OBITO' | 'EXPURGADO_RECEITA_IRREGULAR' | 'SUSPEITO';
  is_deceased: boolean;
  death_date?: string | null;
  tax_status: string;
  elegivel_consignado: boolean;
  motivo_expurgo?: string | null;
  deve_cobrar_credito: boolean;
  badge_texto: string;
  badge_variante: 'success' | 'warning' | 'danger' | 'secondary';
}

export interface ConsignadoData {
  elegivel: boolean;
  vinculoPrincipal: string;
  numeroBeneficio: string;
  especieCodigo: string;
  especieDescricao: string;
  categoriaElegibilidade: string;
  alerta?: string | null;
  salarioBase: number;
  margemEmprestimo35: number;
  margemRmcCartao5: number;
  margemRccBeneficio5: number;
  margemTotal45: number;
  percentualTotal: number;
}

export interface NaoMePerturbeStatus {
  inscrito_nao_me_perturbe: boolean;
  entidade: string;
  data_bloqueio?: string | null;
  motivo: string;
  seguro_para_discagem_fria: boolean;
  risco_multa: 'ALTO' | 'BAIXO';
  badge_texto: string;
  badge_variante: 'success' | 'danger' | 'secondary';
}

export interface MailingPhone {
  ordemRecomendada: number;
  numeroFormatado: string;
  numeroRaw: string;
  numeroE164: string;
  ddd: string;
  tipo: 'Celular' | 'Fixo';
  operadora: string;
  whatsappDisponivel: boolean;
  tipoConta: string;
  linkWhatsApp?: string | null;
  naoMePerturbe: NaoMePerturbeStatus;
  scoreAssertividade: number;
  recomendacao: string;
  rotuloCanal: string;
}

export interface EnrichedPersonSummary {
  id: string;
  name: string;
  cpf: string;
  cpfDigits: string;
  birthDate?: string | null;
  age?: number | null;
  motherName?: string | null;
  gender?: string | null;
  taxStatus: string;
  isDeceased?: boolean;
  deathDate?: string | null;
  phone: string;
  whatsapp?: string | null;
  hasWhatsApp: boolean;
  observedAt: string;
}

export interface PersonEnrichmentResult {
  runId: string;
  personId: string;
  entityType: 'PERSON';
  capabilities: string[];
  person: EnrichedPersonSummary | null;
  filtroPerda?: FiltroPerdaData | null;
  consignado?: ConsignadoData | null;
  mailingTop3?: MailingPhone[];
  coverage: {
    requested: number;
    available: number;
    fieldCount: number;
    recordCount: number;
  };
  sections: Array<{
    id: string;
    title: string;
    description: string;
    status: 'available' | 'empty' | 'unavailable';
    summary: string;
    fields: Array<{ label: string; value: string }>;
    items: Array<{ title: string; fields: Array<{ label: string; value: string }> }>;
    errorMessage?: string;
  }>;
  telefonesAtribuiveis?: Array<{
    numero: string;
    numeroE164: string;
    tipo: string;
    whatsappDisponivel: boolean;
    tipoConta: string;
    jid?: string | null;
    fotoPerfil?: string | null;
    linkWhatsApp?: string | null;
    atribuicao: string;
    scoreBureau?: number;
  }>;
  whatsappGarantido?: {
    garantido: boolean;
    numero: string;
    numeroE164: string;
    tipoConta: string;
    jid?: string;
    fotoPerfil?: string | null;
    linkDireto: string;
    verificadoEm?: string;
    provedorProbe?: string;
  } | null;
  costCredits?: number;
}


export interface CnaeItem {
  code: string;
  codeRaw: string;
  description: string;
  codigo?: string;
  descricao?: string;
  section: string;
  sectionDescription: string;
  division: string;
  group: string;
  industry: string;
  typicalPorte: 'ME' | 'EPP' | 'Médio' | 'Grande';
  averageTicket: string;
  defaultBuyingGroup: Array<{
    role: string;
    department: string;
    seniority: 'C-Level' | 'Diretoria' | 'Gerência' | 'Especialista';
    influence: 'Econômico' | 'Técnico' | 'Operacional' | 'Champion';
  }>;
}

export interface DiscoveryFilterInput {
  cnaePrincipal?: string;
  cnaesSecundarios?: string[];
  uf?: string;
  porte?: 'TODOS' | 'ME' | 'EPP' | 'DEMAIS';
  situacaoCadastral?: 'ATIVA' | 'TODAS';
  termoBusca?: string;
  limiteAmostra?: number;
}

export interface CanonicalCompanyPreview {
  id: string;
  cnpj: string;
  cnpjFormatted: string;
  razaoSocial: string;
  nomeFantasia: string | null;
  cnaePrincipal: {
    codigo: string;
    descricao: string;
  };
  cnaesSecundarios: Array<{
    codigo: string;
    descricao: string;
  }>;
  uf: string;
  endereco: {
    logradouro?: string;
    numero?: string;
    bairro?: string;
    cep?: string;
  };
  porte: string;
  capitalSocial: number | null;
  situacaoCadastral: string;
  simplesNacional: boolean | null;
  mei: boolean | null;
  telefoneComercial: string | null;
  emailCorporativo: string | null;
  dataConfidenceScore: number;
}

export interface DiscoverySearchResult {
  totalEligibleCompanies: number;
  dryRun: {
    totalBytesProcessed: number;
    totalMegaBytesProcessed: number;
    estimatedCostUsd: number;
    cacheHit: boolean;
  };
  sample: CanonicalCompanyPreview[];
  filterApplied: DiscoveryFilterInput;
}

export interface BatchExtractInput {
  name: string;
  limit: number;
  filter: DiscoveryFilterInput;
}

export interface BatchExtractResult {
  datasetId: string;
  totalImported: number;
  companies: CanonicalCompanyPreview[];
}

export interface DataHealthRepairResult {
  success: boolean;
  repairedContacts: number;
  boostedScores: number;
  health: DataHealthData;
}

// ==========================================
// CONTRATOS REST DJANGO 5.2 (LEADSTREAM BACKEND)
// ==========================================

export interface DjangoTenant {
  id: string;
  name: string;
  slug: string;
}

export interface DjangoUser {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  is_superuser: boolean;
  is_staff: boolean;
}

export interface DjangoAuthTokens {
  access: string;
}

export interface DjangoAuthMeResponse {
  user: DjangoUser;
  active_workspace?: DjangoTenant;
  tenant?: DjangoTenant;
  role?: string;
  is_authenticated?: boolean;
  auth_type?: string;
  permissions?: string[];
  workspaces?: Array<{
    id: string;
    name: string;
    slug: string;
    role: string;
    is_active: boolean;
    is_current: boolean;
  }>;
}

export interface DjangoCreditWallet {
  tenant: DjangoTenant | string;
  balance: number;
  reserved_balance: number;
  available_balance: number;
  is_unlimited: boolean;
  updated_at: string;
}

export interface DjangoCreditTransaction {
  id: string;
  transaction_type: 'DEPOSIT' | 'HOLD' | 'CAPTURE' | 'RELEASE';
  amount: number;
  balance_after: number;
  reference_id: string;
  metadata?: Record<string, unknown>;
  created_at: string;
}

export interface DjangoBatch {
  id: string;
  name: string;
  source_type: 'CSV' | 'DISCOVERY';
  status: 'RECEIVED' | 'INGESTING' | 'QUEUED' | 'RUNNING' | 'PAUSED' | 'CANCEL_REQUESTED' | 'CANCELLED' | 'COMPLETED' | 'PARTIAL' | 'FAILED';
  current_stage: 'INGESTION' | 'HYGIENE' | 'ENRICHMENT' | string;
  input_original_name: string;
  input_size_bytes: number;
  input_sha256: string;
  chunk_size: number;
  total_rows: number;
  processed_rows: number;
  succeeded_rows: number;
  absent_rows: number;
  failed_rows: number;
  duplicate_rows: number;
  corrected_rows: number;
  invalid_rows: number;
  progress_percent: number;
  eta_seconds: number | null;
  cost_cents: number;
  revenue_cents: number;
  gross_profit_cents: number;
  last_error_code: string;
  last_error_message: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
}

export interface DjangoBatchItem {
  id: string;
  batch: string;
  row_number: number;
  raw_payload: Record<string, unknown>;
  status: 'PENDING' | 'PROCESSING' | 'SUCCEEDED' | 'FAILED';
  enrichment_status: 'PENDING' | 'PARTIAL' | 'SUCCEEDED' | 'FAILED';
  error_message?: string;
  entity?: Record<string, unknown>;
}

export interface DjangoEmailValidationResult {
  email: string;
  syntax_valid: boolean;
  mx_found: boolean;
  smtp_checkable: boolean;
  smtp_handshake_ok: boolean;
  is_catch_all: boolean;
  deliverable: boolean;
  confidence_score: number;
  diagnostics?: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface PlatformBranding {
  platform_name: string;
  logo_url_dark: string;
  logo_url_light: string;
  favicon_url: string;
  accent_color: string;
  primary_color: string;
  support_email: string;
  terms_url: string;
  privacy_url: string;
}

export interface AdminTenant {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  max_users: number;
  max_leads_monthly: number;
  max_storage_mb: number;
  created_at: string;
  updated_at?: string;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_staff: boolean;
  is_superuser: boolean;
  date_joined: string;
  memberships: Array<{
    tenant_id: string;
    tenant_name: string;
    tenant_slug: string;
    role: 'ADMIN' | 'OPERATOR' | 'READ_ONLY';
    is_active: boolean;
  }>;
}

export interface AdminAPIKey {
  id: string;
  tenant: string;
  tenant_name: string;
  name: string;
  prefix: string;
  raw_key?: string;
  scope: 'FULL' | 'READ_ONLY' | 'INGEST_ONLY';
  is_active: boolean;
  created_at: string;
  expires_at: string | null;
  last_used_at?: string | null;
}

export interface AdminPriceRule {
  id: string;
  block: string;
  unit_price_cents: number;
  minimum_confidence: number;
  refresh_window_days: number;
}

export interface AdminPriceBook {
  id: string;
  tenant: string;
  tenant_name: string;
  name: string;
  version: number;
  effective_at: string;
  rules: AdminPriceRule[];
}

export interface AdminWallet {
  id: string;
  tenant: string;
  tenant_name: string;
  balance: number;
  currency: string;
  is_locked: boolean;
  updated_at: string;
}

export interface AdminProviderStatus {
  name: string;
  status: 'ONLINE' | 'DEGRADED' | 'OFFLINE';
  priority: number;
  latency_ms: number;
  success_rate_24h: number;
  error_count_24h: number;
}

export interface AdminProviderBudget {
  daily_limit_brl?: number;
  daily_limit_usd?: number;
  circuit_breaker_rate: number;
  current_spend_brl?: number;
  current_spend_usd?: number;
  spent_today_usd?: number;
  is_tripped?: boolean;
}

export interface AdminProvidersData {
  providers: AdminProviderStatus[];
  budget: AdminProviderBudget;
}

export interface AdminSuppression {
  id: string;
  identifier_type: 'CNPJ' | 'EMAIL' | 'DOMAIN';
  identifier_value: string;
  reason: string;
  created_at: string;
}

export interface AdminAuditLog {
  id: string;
  tenant_id?: string;
  actor_id?: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  ip_address?: string;
  user_agent?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface AdminSMTPConfig {
  helo_domain: string;
  timeout_seconds: number;
  max_retries: number;
  catch_all_strategy: 'PROBE' | 'ASSUME_RISKY' | 'ACCEPT';
  blacklisted_mx_patterns: string[];
}

export interface SMTPProbeResult {
  email: string;
  status: 'DELIVERABLE' | 'UNDELIVERABLE' | 'CATCH_ALL' | 'TIMEOUT' | 'ERROR';
  mx_host?: string;
  smtp_code?: number;
  raw_response?: string;
  latency_ms: number;
}

export interface AdminBatch {
  id: string;
  tenant_id: string;
  tenant_name: string;
  name: string;
  source_type: string;
  status: string;
  total_rows: number;
  processed_rows: number;
  succeeded_rows: number;
  failed_rows: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface AdminQueueStatus {
  queue_name: string;
  messages_count: number;
  consumers_count: number;
  rate_in_per_sec: number;
  rate_out_per_sec: number;
}

export interface AdminCeleryQueuesData {
  queues: AdminQueueStatus[];
  active_workers: number;
  total_throughput_hour: number;
}

export function ensureArray<T>(val: unknown): T[] {
  if (Array.isArray(val)) return val as T[];
  if (val && typeof val === 'object') {
    const obj = val as Record<string, unknown>;
    if (Array.isArray(obj.results)) return obj.results as T[];
    if (Array.isArray(obj.items)) return obj.items as T[];
    if (Array.isArray(obj.data)) return obj.data as T[];
  }
  return [];
}
