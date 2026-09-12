import type {
  DjangoAuthMeResponse,
  DjangoAuthTokens,
  DjangoBatch,
  DjangoCreditTransaction,
  DjangoCreditWallet,
  DjangoEmailValidationResult,
  PaginatedResponse,
  Activity,
  CampaignList,
  CnaeItem,
  CreateDatasetInput,
  CreateListInput,
  CRMConnection,
  CompanyEnrichmentResult,
  DataHealthData,
  DataHealthRepairResult,
  DashboardData,
  DiscoveryFilterInput,
  DiscoverySearchResult,
  EnrichmentRun,
  EnrichmentCatalog,
  EnrichmentStatus,
  ImportPayload,
  ImportResult,
  Lead,
  LeadSet,
  WorkspaceSummary,
  BatchExtractInput,
  BatchExtractResult,
  PixLookupStatus,
  PlatformBranding,
  AdminTenant,
  AdminUser,
  AdminAPIKey,
  AdminPriceBook,
  AdminWallet,
  AdminProvidersData,
  AdminProviderBudget,
  AdminSuppression,
  AdminAuditLog,
  AdminSMTPConfig,
  SMTPProbeResult,
  AdminBatch,
  AdminCeleryQueuesData,
} from './types';

function resolveBaseUrl(): string {
  const envUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
  // Se veio URL interna de docker ou localhost em produção, ignorar
  if (envUrl && !envUrl.includes('lead_stream_backend') && !envUrl.includes('localhost') && envUrl.startsWith('http')) {
    return `${envUrl.replace(/\/$/, '')}/api/v1`;
  }
  // Se estiver acessando pelo domínio do EasyPanel, usar o backend público em HTTPS
  if (typeof window !== 'undefined' && window.location.hostname.includes('easypanel.host')) {
    return 'https://lead-stream-backend.a3rpjn.easypanel.host/api/v1';
  }
  return '/api/v1';
}

const BASE_URL = resolveBaseUrl();

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function getStoredTokens(): DjangoAuthTokens | null {
  const access = localStorage.getItem('leadstream_access_token');
  const refresh = localStorage.getItem('leadstream_refresh_token');
  if (access && refresh) {
    return { access, refresh };
  }
  return null;
}

export function setStoredTokens(tokens: DjangoAuthTokens | null): void {
  if (tokens) {
    localStorage.setItem('leadstream_access_token', tokens.access);
    localStorage.setItem('leadstream_refresh_token', tokens.refresh);
  } else {
    localStorage.removeItem('leadstream_access_token');
    localStorage.removeItem('leadstream_refresh_token');
  }
}

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

async function request<T>(path: string, init?: RequestInit, retry = true): Promise<T> {
  const url = path.startsWith('http') ? path : `${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  const tokens = getStoredTokens();

  const headers: Record<string, string> = {
    ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
    ...(init?.headers as Record<string, string>),
  };

  if (tokens?.access && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${tokens.access}`;
  }

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (response.status === 401 && retry && tokens?.refresh && !path.includes('/auth/token/')) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshResponse = await fetch(`${BASE_URL}/auth/token/refresh/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh: tokens.refresh }),
        });

        if (refreshResponse.ok) {
          const newTokens = (await refreshResponse.json()) as { access: string };
          setStoredTokens({ access: newTokens.access, refresh: tokens.refresh });
          isRefreshing = false;
          onRefreshed(newTokens.access);
          return request<T>(path, init, false);
        } else {
          setStoredTokens(null);
          isRefreshing = false;
          window.dispatchEvent(new Event('auth:unauthorized'));
          throw new ApiError('Sessão expirada. Faça login novamente.', 401);
        }
      } catch (err) {
        setStoredTokens(null);
        isRefreshing = false;
        window.dispatchEvent(new Event('auth:unauthorized'));
        throw err;
      }
    }

    return new Promise((resolve) => {
      refreshSubscribers.push((newToken: string) => {
        const retryHeaders = {
          ...headers,
          Authorization: `Bearer ${newToken}`,
        };
        resolve(request<T>(path, { ...init, headers: retryHeaders }, false));
      });
    });
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMsg = 
      payload.detail || 
      payload.error || 
      payload.message || 
      (typeof payload === 'object' && Object.values(payload).flat().join(', ')) ||
      'Não foi possível concluir a operação.';
    throw new ApiError(errorMsg, response.status, payload);
  }

  return payload as T;
}

export const api = {
  // ==========================================
  // AUTENTICAÇÃO E SESSÃO
  // ==========================================
  login: async (username: string, password: string): Promise<DjangoAuthTokens> => {
    const tokens = await request<DjangoAuthTokens>('/auth/token/', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    setStoredTokens(tokens);
    return tokens;
  },

  logout: () => {
    setStoredTokens(null);
    window.location.href = '/login';
  },

  me: () => request<DjangoAuthMeResponse>('/auth/me/'),

  // ==========================================
  // CARTEIRA E LEDGER CONTÁBIL (PAY-PER-VALUE)
  // ==========================================
  wallet: () => request<DjangoCreditWallet>('/billing/wallet/'),
  transactions: (page = 1) => request<PaginatedResponse<DjangoCreditTransaction>>(`/billing/transactions/?page=${page}`),

  // ==========================================
  // LOTES DE ENRIQUECIMENTO (BATCHES)
  // ==========================================
  batches: (page = 1, status = '') => {
    const query = new URLSearchParams({ page: String(page) });
    if (status) query.set('status', status);
    return request<PaginatedResponse<DjangoBatch>>(`/batches/?${query.toString()}`);
  },

  batchDetail: (batchId: string) => request<DjangoBatch>(`/batches/${batchId}/`),

  uploadBatch: (formData: FormData, idempotencyKey?: string) => {
    const headers: Record<string, string> = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    return request<DjangoBatch>('/batches/', {
      method: 'POST',
      body: formData,
      headers,
    });
  },

  pauseBatch: (batchId: string) => request<DjangoBatch>(`/batches/${batchId}/pause/`, { method: 'POST' }),
  resumeBatch: (batchId: string) => request<DjangoBatch>(`/batches/${batchId}/resume/`, { method: 'POST' }),
  cancelBatch: (batchId: string) => request<DjangoBatch>(`/batches/${batchId}/cancel/`, { method: 'POST' }),
  exportBatch: (batchId: string, format = 'csv') =>
    request<{ download_url: string; format: string }>(`/batches/${batchId}/export/`, {
      method: 'POST',
      body: JSON.stringify({ format }),
    }),

  // ==========================================
  // MOTOR ZERO-BOUNCE (VERIFICAÇÃO SMTP)
  // ==========================================
  verifyEmail: (email: string) =>
    request<DjangoEmailValidationResult>('/validation/email/', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  // ==========================================
  // MÓDULOS DE DADOS E DESCOBERTA
  // ==========================================
  workspace: () => request<WorkspaceSummary>('/workspace'),
  leads: () => request<Lead[]>('/leads'),
  lookupLead: (query: string) => request<Lead>(`/leads/lookup?q=${encodeURIComponent(query)}`),
  revealPhone: (id: string) => request<Lead>(`/leads/${encodeURIComponent(id)}/reveal-phone`, { method: 'PATCH' }),
  datasets: () => request<LeadSet[]>('/datasets'),
  createDataset: (input: CreateDatasetInput) =>
    request<LeadSet>('/datasets', { method: 'POST', body: JSON.stringify(input) }),
  deleteDataset: (id: string) => request<void>(`/datasets/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  importRecords: (input: ImportPayload) =>
    request<ImportResult>('/imports', { method: 'POST', body: JSON.stringify(input) }),
  lists: () => request<CampaignList[]>('/lists'),
  createList: (input: CreateListInput) =>
    request<CampaignList>('/lists', { method: 'POST', body: JSON.stringify(input) }),
  archiveList: (id: string, archived = true) =>
    request<CampaignList>(`/lists/${encodeURIComponent(id)}/archive`, {
      method: 'PATCH',
      body: JSON.stringify({ archived }),
    }),
  addLeadsToList: (id: string, leadIds: string[]) =>
    request<CampaignList>(`/lists/${encodeURIComponent(id)}/leads`, {
      method: 'POST',
      body: JSON.stringify({ leadIds }),
    }),
  activities: () => request<Activity[]>('/activities'),
  crmConnections: () => request<CRMConnection[]>('/crm-connections'),
  dashboard: (period: string) => request<DashboardData>(`/dashboard?period=${encodeURIComponent(period)}`),
  dataHealth: () => request<DataHealthData>('/data-health'),
  repairDataHealth: () => request<DataHealthRepairResult>('/data-health/repair', { method: 'POST' }),
  discoveryCnaes: (query = '', limit = 30) =>
    request<CnaeItem[]>(`/discovery/cnaes?q=${encodeURIComponent(query)}&limit=${limit}`),
  discoverySearch: (filter: DiscoveryFilterInput) =>
    request<DiscoverySearchResult>('/discovery/search', {
      method: 'POST',
      body: JSON.stringify(filter),
    }),
  discoveryExtract: (input: BatchExtractInput) =>
    request<BatchExtractResult>('/discovery/extract', {
      method: 'POST',
      body: JSON.stringify(input),
    }),
  enrichmentStatus: () => request<EnrichmentStatus>('/enrichment/status'),
  enrichmentCatalog: () => request<EnrichmentCatalog>('/enrichment/catalog'),
  enrichmentRuns: () => request<EnrichmentRun[]>('/enrichment/runs'),
  enrichCompany: (query: string, capabilities: string[]) =>
    request<CompanyEnrichmentResult>('/enrichment/company', {
      method: 'POST',
      body: JSON.stringify({ query, capabilities }),
    }),
  enrichmentLookup: (query: string) =>
    request<Lead>(`/enrichment/lookup?q=${encodeURIComponent(query)}`).catch(() => api.lookupLead(query)),
  pixLookupStatus: () =>
    request<PixLookupStatus>('/pix/status').catch(() => ({
      enabled: false,
      termsApproved: false,
      purpose: '',
      payerConfigured: false,
      lookupReady: false,
      automaticEligibility: 'ONLY_EXPLICIT_PUBLIC_PIX_KEY' as const,
      providers: [],
    })),

  // White-Label Branding
  branding: () => request<PlatformBranding>('/system/branding/'),
  updateBranding: (data: Partial<PlatformBranding>) =>
    request<PlatformBranding>('/system/branding/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Admin: Tenants & Workspaces
  adminTenants: () => request<PaginatedResponse<AdminTenant>>('/admin/tenants/'),
  createAdminTenant: (data: {
    name: string;
    slug: string;
    max_users?: number;
    max_leads_monthly?: number;
    max_storage_mb?: number;
    initial_credits?: number;
    initial_admin_username?: string;
    initial_admin_email?: string;
    initial_admin_password?: string;
  }) =>
    request<AdminTenant>('/admin/tenants/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateAdminTenant: (id: string, data: Partial<AdminTenant>) =>
    request<AdminTenant>(`/admin/tenants/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  impersonateTenant: (id: string) =>
    request<{ tenant_id: string; tenant_name: string; tenant_slug: string }>(
      `/admin/tenants/${id}/impersonate/`,
      { method: 'POST' }
    ),

  // Admin: Users & Security
  adminUsers: () => request<PaginatedResponse<AdminUser>>('/admin/users/'),
  createAdminUser: (data: {
    username: string;
    email: string;
    password?: string;
    is_active?: boolean;
    tenant_id?: string;
    role?: string;
  }) =>
    request<AdminUser>('/admin/users/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  updateAdminUser: (
    id: number,
    data: {
      is_active?: boolean;
      memberships?: Array<{ tenant_id: string; role: string; is_active: boolean }>;
    }
  ) =>
    request<AdminUser>(`/admin/users/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  adminAPIKeys: () => request<PaginatedResponse<AdminAPIKey>>('/admin/api-keys/'),
  createAdminAPIKey: (data: { tenant_id: string; name: string; scope: string }) =>
    request<AdminAPIKey>('/admin/api-keys/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  revokeAdminAPIKey: (id: string) =>
    request<{ status: string }>(`/admin/api-keys/${id}/`, {
      method: 'DELETE',
    }),

  // Admin: Pricing & Ledger
  adminPricing: () => request<PaginatedResponse<AdminPriceBook> | AdminPriceBook[]>('/admin/pricing/'),
  updateAdminPriceBook: (
    bookId: string,
    data: {
      rules: Array<{
        block: string;
        unit_price_cents: number;
        minimum_confidence?: number;
        refresh_window_days?: number;
      }>;
    }
  ) =>
    request<{ status: string; updated_rules: number }>(`/admin/pricing/${bookId}/`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  adminWallets: () => request<PaginatedResponse<AdminWallet>>('/admin/wallets/'),
  injectAdminCredit: (tenantId: string, data: { amount: number; reason: string }) =>
    request<{ status: string; balance: number; transaction_id: string }>(
      `/admin/wallets/${tenantId}/credit/`,
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),
  adminWalletTransactions: (tenantId: string) =>
    request<PaginatedResponse<DjangoCreditTransaction>>(
      `/admin/wallets/${tenantId}/transactions/`
    ),

  // Admin: Providers & Budget
  adminProviders: () => request<AdminProvidersData>('/admin/providers/'),
  updateAdminProviderBudget: (data: {
    daily_limit_brl?: number;
    daily_limit_usd?: number;
    circuit_breaker_rate?: number;
  }) =>
    request<AdminProviderBudget>('/admin/providers/budget/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  // Admin: Governance & Suppression
  adminSuppression: () => request<PaginatedResponse<AdminSuppression>>('/admin/suppression/'),
  createAdminSuppression: (data: {
    identifier_type: 'CNPJ' | 'EMAIL' | 'DOMAIN';
    identifier_value: string;
    reason: string;
  }) =>
    request<AdminSuppression>('/admin/suppression/', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  deleteAdminSuppression: (id: string) =>
    request<{ status: string }>(`/admin/suppression/${id}/`, {
      method: 'DELETE',
    }),
  adminAuditLogs: (limit = 50) =>
    request<PaginatedResponse<AdminAuditLog>>(`/admin/audit-logs/?limit=${limit}`),

  // Admin: SMTP Engine & Real-time Probe
  adminSMTPConfig: () => request<AdminSMTPConfig>('/admin/smtp-config/'),
  updateAdminSMTPConfig: (data: Partial<AdminSMTPConfig>) =>
    request<AdminSMTPConfig>('/admin/smtp-config/', {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  probeSMTP: (email: string) =>
    request<SMTPProbeResult>('/admin/smtp-probe/', {
      method: 'POST',
      body: JSON.stringify({ email }),
    }),

  // Admin: Batches & Celery Queues
  adminBatches: () => request<PaginatedResponse<AdminBatch>>('/admin/batches/'),
  actionAdminBatch: (id: string, action: 'pause' | 'resume' | 'cancel') =>
    request<{ status: string; batch_id: string }>(`/admin/batches/${id}/${action}/`, {
      method: 'POST',
    }),
  adminCeleryQueues: () => request<AdminCeleryQueuesData>('/admin/celery/queues/'),
};
