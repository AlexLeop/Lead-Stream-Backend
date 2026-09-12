import React, { useEffect, useState, useCallback } from 'react';
import {
  Building2,
  Users,
  Key,
  CreditCard,
  Layers,
  Cpu,
  ShieldCheck,
  Mail,
  Palette,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Plus,
  Trash2,
  Copy,
  Check,
  Send,
  Pause,
  Play,
  RotateCcw,
  Sliders,
  DollarSign,
  Activity,
  Server,
  Lock,
} from 'lucide-react';
import { api } from '../api';
import { useBranding } from '../components/BrandingProvider';
import type {
  AdminTenant,
  AdminUser,
  AdminAPIKey,
  AdminPriceBook,
  AdminWallet,
  AdminProvidersData,
  AdminSuppression,
  AdminAuditLog,
  AdminSMTPConfig,
  SMTPProbeResult,
  AdminBatch,
  AdminCeleryQueuesData,
  DjangoCreditTransaction,
} from '../types';

type TabKey =
  | 'tenants'
  | 'users'
  | 'pricing'
  | 'wallets'
  | 'batches'
  | 'providers'
  | 'governance'
  | 'smtp_brand';

export default function AdminCenter() {
  const [activeTab, setActiveTab] = useState<TabKey>('tenants');
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showFeedback = (type: 'success' | 'error', message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 4500);
  };

  return (
    <div className="space-y-4">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              SUPERADMIN PRIVILEGED
            </span>
            <span className="text-xs text-slate-400 font-mono">DRF 5.2 / Master Core</span>
          </div>
          <h1 className="text-lg font-bold tracking-tight text-white mt-1">
            Torre Master de Governança & White-Label
          </h1>
          <p className="text-xs text-slate-400">
            Controle total de multi-inquilinos, limites operacionais, ledger contábil, provedores e motor Zero-Bounce.
          </p>
        </div>
      </div>

      {feedback && (
        <div
          className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-mono border ${
            feedback.type === 'success'
              ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
              : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
          }`}
        >
          {feedback.type === 'success' ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* High-density Nav Tabs */}
      <div className="flex items-center gap-1 overflow-x-auto border-b border-white/10 pb-2 scrollbar-none">
        <TabButton active={activeTab === 'tenants'} onClick={() => setActiveTab('tenants')} icon={Building2} label="Workspaces & Clientes" />
        <TabButton active={activeTab === 'users'} onClick={() => setActiveTab('users')} icon={Users} label="Usuários & Chaves API" />
        <TabButton active={activeTab === 'pricing'} onClick={() => setActiveTab('pricing')} icon={Sliders} label="Planos & Preços" />
        <TabButton active={activeTab === 'wallets'} onClick={() => setActiveTab('wallets')} icon={CreditCard} label="Carteiras & Ledger" />
        <TabButton active={activeTab === 'batches'} onClick={() => setActiveTab('batches')} icon={Layers} label="Lotes & Filas Celery" />
        <TabButton active={activeTab === 'providers'} onClick={() => setActiveTab('providers')} icon={Cpu} label="Provedores & Orçamento" />
        <TabButton active={activeTab === 'governance'} onClick={() => setActiveTab('governance')} icon={ShieldCheck} label="Governança & Supressão" />
        <TabButton active={activeTab === 'smtp_brand'} onClick={() => setActiveTab('smtp_brand')} icon={Palette} label="Zero-Bounce & Marca" />
      </div>

      {/* Tab Panels */}
      <div className="mt-2">
        {activeTab === 'tenants' && <TenantsTab onError={(m) => showFeedback('error', m)} onSuccess={(m) => showFeedback('success', m)} />}
        {activeTab === 'users' && <UsersTab onError={(m) => showFeedback('error', m)} onSuccess={(m) => showFeedback('success', m)} />}
        {activeTab === 'pricing' && <PricingTab onError={(m) => showFeedback('error', m)} onSuccess={(m) => showFeedback('success', m)} />}
        {activeTab === 'wallets' && <WalletsTab onError={(m) => showFeedback('error', m)} onSuccess={(m) => showFeedback('success', m)} />}
        {activeTab === 'batches' && <BatchesTab onError={(m) => showFeedback('error', m)} onSuccess={(m) => showFeedback('success', m)} />}
        {activeTab === 'providers' && <ProvidersTab onError={(m) => showFeedback('error', m)} onSuccess={(m) => showFeedback('success', m)} />}
        {activeTab === 'governance' && <GovernanceTab onError={(m) => showFeedback('error', m)} onSuccess={(m) => showFeedback('success', m)} />}
        {activeTab === 'smtp_brand' && <SmtpBrandTab onError={(m) => showFeedback('error', m)} onSuccess={(m) => showFeedback('success', m)} />}
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-[11px] font-medium transition-colors whitespace-nowrap cursor-pointer ${
        active
          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/25'
          : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.03] border border-transparent'
      }`}
    >
      <Icon className={`w-3.5 h-3.5 shrink-0 ${active ? 'text-emerald-400' : 'text-slate-500'}`} />
      <span>{label}</span>
    </button>
  );
}

// =========================================================================
// TAB 1: WORKSPACES & CLIENTES (TENANTS)
// =========================================================================
function TenantsTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newSlug, setNewSlug] = useState('');
  const [maxUsers, setMaxUsers] = useState(10);
  const [maxLeads, setMaxLeads] = useState(50000);
  const [maxStorage, setMaxStorage] = useState(2048);
  const [initialCredits, setInitialCredits] = useState(1000);
  const [adminUsername, setAdminUsername] = useState('');
  const [adminEmail, setAdminEmail] = useState('');
  const [adminPassword, setAdminPassword] = useState('');

  const loadTenants = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.adminTenants();
      setTenants(res.results || []);
    } catch (e: unknown) {
      onError('Erro ao carregar lista de tenants.');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    loadTenants();
  }, [loadTenants]);

  const handleToggleActive = async (t: AdminTenant) => {
    try {
      await api.updateAdminTenant(t.id, { is_active: !t.is_active });
      onSuccess(`Workspace "${t.name}" ${!t.is_active ? 'ativado' : 'desativado'}.`);
      loadTenants();
    } catch {
      onError('Falha ao atualizar status do workspace.');
    }
  };

  const handleImpersonate = async (t: AdminTenant) => {
    try {
      const res = await api.impersonateTenant(t.id);
      onSuccess(`Sessão alternada para o workspace "${res.tenant_name}". Recarregando...`);
      setTimeout(() => window.location.reload(), 800);
    } catch {
      onError('Erro ao personificar workspace.');
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName || !newSlug) {
      onError('Nome e slug são obrigatórios.');
      return;
    }
    try {
      await api.createAdminTenant({
        name: newName,
        slug: newSlug,
        max_users: maxUsers,
        max_leads_monthly: maxLeads,
        max_storage_mb: maxStorage,
        initial_credits: initialCredits,
        initial_admin_username: adminUsername || undefined,
        initial_admin_email: adminEmail || undefined,
        initial_admin_password: adminPassword || undefined,
      });
      onSuccess(`Workspace "${newName}" criado com sucesso e carteira provisionada.`);
      setShowCreateModal(false);
      setNewName('');
      setNewSlug('');
      setAdminUsername('');
      setAdminEmail('');
      setAdminPassword('');
      loadTenants();
    } catch {
      onError('Falha ao criar workspace.');
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-slate-400">Total: {tenants.length} workspaces registrados</span>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-medium transition cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Novo Workspace</span>
        </button>
      </div>

      <div className="rounded border border-white/10 overflow-hidden bg-[#12141C]">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              <th className="px-3 py-2">Workspace</th>
              <th className="px-3 py-2">Slug</th>
              <th className="px-3 py-2">Limites Operacionais</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Criado em</th>
              <th className="px-3 py-2 text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs">
            {tenants.map((t) => (
              <tr key={t.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-3 py-2 font-medium text-white">{t.name}</td>
                <td className="px-3 py-2 font-mono text-slate-400 text-[11px]">{t.slug}</td>
                <td className="px-3 py-2 text-[11px] font-mono text-slate-300">
                  <span title="Usuários">{t.max_users} usr</span> ·{' '}
                  <span title="Leads / Mês">{(t.max_leads_monthly / 1000).toFixed(0)}k leads</span> ·{' '}
                  <span title="Storage">{t.max_storage_mb} MB</span>
                </td>
                <td className="px-3 py-2">
                  <button
                    onClick={() => handleToggleActive(t)}
                    className={`px-2 py-0.5 rounded text-[10px] font-mono cursor-pointer border ${
                      t.is_active
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                    }`}
                  >
                    {t.is_active ? 'Ativo' : 'Inativo'}
                  </button>
                </td>
                <td className="px-3 py-2 font-mono text-slate-500 text-[11px]">
                  {new Date(t.created_at).toLocaleDateString('pt-BR')}
                </td>
                <td className="px-3 py-2 text-right space-x-2">
                  <button
                    onClick={() => handleImpersonate(t)}
                    title="Alternar contexto de sessão para este inquilino"
                    className="px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-[11px] font-mono text-slate-300 hover:text-white transition cursor-pointer"
                  >
                    Acessar
                  </button>
                </td>
              </tr>
            ))}
            {tenants.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                  Nenhum workspace cadastrado além do padrão.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-lg border border-white/10 bg-[#12141C] p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-semibold text-white">Criar Novo Workspace</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-slate-400 hover:text-white cursor-pointer"
              >
                ✕
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Nome do Workspace</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => {
                    setNewName(e.target.value);
                    if (!newSlug) {
                      setNewSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]/g, '-'));
                    }
                  }}
                  placeholder="Ex: Acionista Capital"
                  className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-sans text-xs focus:border-emerald-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Slug Identificador</label>
                <input
                  type="text"
                  required
                  value={newSlug}
                  onChange={(e) => setNewSlug(e.target.value)}
                  placeholder="acionista-capital"
                  className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-slate-400 font-mono text-[10px] mb-1">Max Usuários</label>
                  <input
                    type="number"
                    value={maxUsers}
                    onChange={(e) => setMaxUsers(Number(e.target.value))}
                    className="w-full rounded border border-white/10 bg-black/40 px-2 py-1 text-white font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-mono text-[10px] mb-1">Max Leads/Mês</label>
                  <input
                    type="number"
                    value={maxLeads}
                    onChange={(e) => setMaxLeads(Number(e.target.value))}
                    className="w-full rounded border border-white/10 bg-black/40 px-2 py-1 text-white font-mono text-xs"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-mono text-[10px] mb-1">Créditos Iniciais</label>
                  <input
                    type="number"
                    value={initialCredits}
                    onChange={(e) => setInitialCredits(Number(e.target.value))}
                    className="w-full rounded border border-white/10 bg-black/40 px-2 py-1 text-emerald-400 font-mono text-xs"
                  />
                </div>
              </div>
              <div className="border-t border-white/10 pt-2">
                <span className="block text-slate-400 font-mono text-[10px] mb-1 uppercase tracking-wider">
                  Usuário Administrador Inicial (Opcional)
                </span>
                <div className="space-y-2">
                  <input
                    type="text"
                    value={adminUsername}
                    onChange={(e) => setAdminUsername(e.target.value)}
                    placeholder="Username admin (ex: gestor)"
                    className="w-full rounded border border-white/10 bg-black/40 px-3 py-1 text-white font-mono text-xs"
                  />
                  <input
                    type="email"
                    value={adminEmail}
                    onChange={(e) => setAdminEmail(e.target.value)}
                    placeholder="Email comercial"
                    className="w-full rounded border border-white/10 bg-black/40 px-3 py-1 text-white font-mono text-xs"
                  />
                  <input
                    type="password"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    placeholder="Senha provisória"
                    className="w-full rounded border border-white/10 bg-black/40 px-3 py-1 text-white font-mono text-xs"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-3 py-1.5 rounded border border-white/10 text-slate-400 hover:text-white cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium cursor-pointer"
                >
                  Provisionar Workspace
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// =========================================================================
// TAB 2: USUÁRIOS & CHAVES DE API
// =========================================================================
function UsersTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [keys, setKeys] = useState<AdminAPIKey[]>([]);
  const [tenants, setTenants] = useState<AdminTenant[]>([]);
  const [activeSubTab, setActiveSubTab] = useState<'users' | 'keys'>('users');
  const [loading, setLoading] = useState(true);

  // Key creation modal
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [keyTenant, setKeyTenant] = useState('');
  const [keyName, setKeyName] = useState('');
  const [keyScope, setKeyScope] = useState('FULL');
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);

  // User creation modal
  const [showUserModal, setShowUserModal] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserPassword, setNewUserPassword] = useState('');
  const [newUserTenant, setNewUserTenant] = useState('');
  const [newUserRole, setNewUserRole] = useState('OPERATOR');

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [uRes, kRes, tRes] = await Promise.all([
        api.adminUsers(),
        api.adminAPIKeys(),
        api.adminTenants(),
      ]);
      setUsers(uRes.results || []);
      setKeys(kRes.results || []);
      setTenants(tRes.results || []);
      if (tRes.results?.length && !keyTenant) {
        setKeyTenant(tRes.results[0].id);
        setNewUserTenant(tRes.results[0].id);
      }
    } catch {
      onError('Erro ao sincronizar usuários e credenciais.');
    } finally {
      setLoading(false);
    }
  }, [onError, keyTenant]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleToggleUserActive = async (u: AdminUser) => {
    try {
      await api.updateAdminUser(u.id, { is_active: !u.is_active });
      onSuccess(`Usuário "${u.username}" ${!u.is_active ? 'ativado' : 'inativado'}.`);
      loadData();
    } catch {
      onError('Falha ao atualizar status do usuário.');
    }
  };

  const handleRevokeKey = async (id: string, name: string) => {
    if (!confirm(`Revogar permanentemente a chave "${name}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await api.revokeAdminAPIKey(id);
      onSuccess(`Chave "${name}" revogada.`);
      loadData();
    } catch {
      onError('Falha ao revogar chave de API.');
    }
  };

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const created = await api.createAdminAPIKey({
        tenant_id: keyTenant,
        name: keyName,
        scope: keyScope,
      });
      setGeneratedKey(created.raw_key || created.prefix);
      onSuccess(`Chave gerada com sucesso! Copie a chave exibida.`);
      loadData();
    } catch {
      onError('Falha ao gerar chave criptográfica.');
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAdminUser({
        username: newUsername,
        email: newUserEmail,
        password: newUserPassword,
        tenant_id: newUserTenant || undefined,
        role: newUserRole,
      });
      onSuccess(`Usuário "${newUsername}" criado com sucesso.`);
      setShowUserModal(false);
      setNewUsername('');
      setNewUserEmail('');
      setNewUserPassword('');
      loadData();
    } catch {
      onError('Falha ao cadastrar usuário.');
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1">
          <button
            onClick={() => setActiveSubTab('users')}
            className={`px-3 py-1 rounded text-xs font-mono cursor-pointer ${
              activeSubTab === 'users' ? 'bg-white/10 text-white font-semibold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Usuários ({users.length})
          </button>
          <button
            onClick={() => setActiveSubTab('keys')}
            className={`px-3 py-1 rounded text-xs font-mono cursor-pointer ${
              activeSubTab === 'keys' ? 'bg-white/10 text-white font-semibold' : 'text-slate-400 hover:text-white'
            }`}
          >
            Chaves de API ({keys.length})
          </button>
        </div>

        {activeSubTab === 'users' ? (
          <button
            onClick={() => setShowUserModal(true)}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-medium transition cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Novo Usuário</span>
          </button>
        ) : (
          <button
            onClick={() => {
              setGeneratedKey(null);
              setShowKeyModal(true);
            }}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-medium transition cursor-pointer"
          >
            <Key className="w-3.5 h-3.5" />
            <span>Gerar Nova Chave</span>
          </button>
        )}
      </div>

      {activeSubTab === 'users' ? (
        <div className="rounded border border-white/10 overflow-hidden bg-[#12141C]">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                <th className="px-3 py-2">Usuário</th>
                <th className="px-3 py-2">Email</th>
                <th className="px-3 py-2">Papel / Workspaces</th>
                <th className="px-3 py-2">Privilégios</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Data Cadastro</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-xs">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-3 py-2 font-medium text-white">{u.username}</td>
                  <td className="px-3 py-2 font-mono text-slate-400 text-[11px]">{u.email || '-'}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {u.memberships?.map((m, idx) => (
                        <span
                          key={idx}
                          className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-[10px] font-mono text-slate-300"
                        >
                          {m.tenant_name}: <strong className="text-emerald-400">{m.role}</strong>
                        </span>
                      ))}
                      {(!u.memberships || u.memberships.length === 0) && (
                        <span className="text-slate-500 text-[11px] italic">Sem vínculos</span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {u.is_superuser && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-500/10 text-purple-300 border border-purple-500/30">
                        SUPERUSER
                      </span>
                    )}
                    {u.is_staff && !u.is_superuser && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-500/10 text-blue-300 border border-blue-500/30">
                        STAFF
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <button
                      onClick={() => handleToggleUserActive(u)}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono cursor-pointer border ${
                        u.is_active
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                      }`}
                    >
                      {u.is_active ? 'Ativo' : 'Inativo'}
                    </button>
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-500 text-[11px]">
                    {new Date(u.date_joined).toLocaleDateString('pt-BR')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="rounded border border-white/10 overflow-hidden bg-[#12141C]">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                <th className="px-3 py-2">Identificador</th>
                <th className="px-3 py-2">Workspace</th>
                <th className="px-3 py-2">Prefixo Chave</th>
                <th className="px-3 py-2">Escopo</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Criada em</th>
                <th className="px-3 py-2 text-right">Ação</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-xs">
              {keys.map((k) => (
                <tr key={k.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-3 py-2 font-medium text-white">{k.name}</td>
                  <td className="px-3 py-2 font-mono text-slate-300 text-[11px]">{k.tenant_name}</td>
                  <td className="px-3 py-2 font-mono text-emerald-400 text-[11px]">{k.prefix}...</td>
                  <td className="px-3 py-2">
                    <span className="px-1.5 py-0.5 rounded bg-white/5 text-[10px] font-mono text-slate-300">
                      {k.scope}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                        k.is_active ? 'text-emerald-400 bg-emerald-500/10' : 'text-slate-500 bg-white/5'
                      }`}
                    >
                      {k.is_active ? 'Ativa' : 'Revogada'}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-500 text-[11px]">
                    {new Date(k.created_at).toLocaleDateString('pt-BR')}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {k.is_active && (
                      <button
                        onClick={() => handleRevokeKey(k.id, k.name)}
                        className="text-rose-400 hover:text-rose-300 text-[11px] font-mono cursor-pointer"
                      >
                        Revogar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {keys.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                    Nenhuma chave de API registrada no sistema.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Key Generation Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-lg border border-white/10 bg-[#12141C] p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-semibold text-white">Gerar Chave de API de Alta Confiabilidade</h3>
              <button onClick={() => setShowKeyModal(false)} className="text-slate-400 hover:text-white cursor-pointer">
                ✕
              </button>
            </div>

            {generatedKey ? (
              <div className="space-y-3">
                <div className="p-3 rounded bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300 font-mono space-y-2">
                  <p className="font-semibold">Chave gerada! Guarde em local seguro agora:</p>
                  <div className="p-2 rounded bg-black/60 select-all break-all text-[11px] border border-emerald-500/20 text-white">
                    {generatedKey}
                  </div>
                  <p className="text-[10px] text-slate-400">
                    O hash SHA-256 foi registrado. O segredo bruto não poderá ser visualizado novamente.
                  </p>
                </div>
                <div className="flex justify-end">
                  <button
                    onClick={() => setShowKeyModal(false)}
                    className="px-3 py-1.5 rounded bg-white/10 hover:bg-white/20 text-white text-xs cursor-pointer font-mono"
                  >
                    Concluído
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleCreateKey} className="space-y-3 text-xs">
                <div>
                  <label className="block text-slate-400 font-mono text-[11px] mb-1">Workspace de Destino</label>
                  <select
                    value={keyTenant}
                    onChange={(e) => setKeyTenant(e.target.value)}
                    className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:outline-none"
                  >
                    {tenants.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.slug})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 font-mono text-[11px] mb-1">Nome / Aplicação</label>
                  <input
                    type="text"
                    required
                    value={keyName}
                    onChange={(e) => setKeyName(e.target.value)}
                    placeholder="Ex: Pipeline N8N Produção"
                    className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white text-xs focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 font-mono text-[11px] mb-1">Escopo de Acesso</label>
                  <select
                    value={keyScope}
                    onChange={(e) => setKeyScope(e.target.value)}
                    className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:outline-none"
                  >
                    <option value="FULL">FULL (Leitura, Ingestão, Enriquecimento)</option>
                    <option value="READ_ONLY">READ_ONLY (Apenas Consultas)</option>
                    <option value="INGEST_ONLY">INGEST_ONLY (Apenas Envio de Lotes)</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-2 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setShowKeyModal(false)}
                    className="px-3 py-1.5 rounded border border-white/10 text-slate-400 hover:text-white cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium cursor-pointer"
                  >
                    Gerar Criptograficamente
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* User Creation Modal */}
      {showUserModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-lg border border-white/10 bg-[#12141C] p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-semibold text-white">Cadastrar Novo Usuário</h3>
              <button onClick={() => setShowUserModal(false)} className="text-slate-400 hover:text-white cursor-pointer">
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Nome de Usuário (Username)</label>
                <input
                  type="text"
                  required
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="Ex: joao.silva"
                  className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Email</label>
                <input
                  type="email"
                  required
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  placeholder="joao@empresa.com.br"
                  className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-sans text-xs focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Senha Provisória</label>
                <input
                  type="password"
                  required
                  value={newUserPassword}
                  onChange={(e) => setNewUserPassword(e.target.value)}
                  className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-slate-400 font-mono text-[11px] mb-1">Workspace</label>
                  <select
                    value={newUserTenant}
                    onChange={(e) => setNewUserTenant(e.target.value)}
                    className="w-full rounded border border-white/10 bg-black/40 px-2 py-1.5 text-white font-mono text-xs focus:outline-none"
                  >
                    <option value="">Sem workspace inicial</option>
                    {tenants.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 font-mono text-[11px] mb-1">Papel (Role)</label>
                  <select
                    value={newUserRole}
                    onChange={(e) => setNewUserRole(e.target.value)}
                    className="w-full rounded border border-white/10 bg-black/40 px-2 py-1.5 text-white font-mono text-xs focus:outline-none"
                  >
                    <option value="ADMIN">ADMIN</option>
                    <option value="OPERATOR">OPERATOR</option>
                    <option value="READ_ONLY">READ_ONLY</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setShowUserModal(false)}
                  className="px-3 py-1.5 rounded border border-white/10 text-slate-400 hover:text-white cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium cursor-pointer"
                >
                  Criar Usuário
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// =========================================================================
// TAB 3: PLANOS & PREÇOS (MATRIZ DE BLOCOS)
// =========================================================================
function PricingTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [books, setBooks] = useState<AdminPriceBook[]>([]);
  const [selectedBook, setSelectedBook] = useState<AdminPriceBook | null>(null);
  const [rules, setRules] = useState<
    Array<{ block: string; unit_price_cents: number; minimum_confidence: number; refresh_window_days: number }>
  >([]);
  const [saving, setSaving] = useState(false);

  const blockLabels: Record<string, string> = {
    COMPANY_REGISTRY: 'Dados Cadastrais (Receita Federal / QSA)',
    DECISION_MAKERS: 'Decisores & Sócios Administradores',
    CONTACT_EMAILS: 'Emails Corporativos Verificados',
    CONTACT_PHONES: 'Telefones & WhatsApp Validado',
    CREDIT_FINANCIAL: 'Capital Social & Regime Tributário',
    DIGITAL_PRESENCE: 'Presença Digital (Web, Redes Sociais)',
    LOCATION_GEO: 'Geolocalização & Endereço Completo',
    PIX_BANKING: 'Chaves Pix & Domicílio Bancário',
  };

  const loadPricing = useCallback(async () => {
    try {
      const data = await api.adminPricing();
      setBooks(data);
      if (data.length > 0) {
        setSelectedBook(data[0]);
        setRules(
          data[0].rules.map((r) => ({
            block: r.block,
            unit_price_cents: r.unit_price_cents,
            minimum_confidence: r.minimum_confidence || 80,
            refresh_window_days: r.refresh_window_days || 30,
          }))
        );
      }
    } catch {
      onError('Erro ao carregar matriz de preços.');
    }
  }, [onError]);

  useEffect(() => {
    loadPricing();
  }, [loadPricing]);

  const handleSelectBook = (b: AdminPriceBook) => {
    setSelectedBook(b);
    setRules(
      b.rules.map((r) => ({
        block: r.block,
        unit_price_cents: r.unit_price_cents,
        minimum_confidence: r.minimum_confidence || 80,
        refresh_window_days: r.refresh_window_days || 30,
      }))
    );
  };

  const handleRuleChange = (index: number, field: string, val: number) => {
    setRules((prev) => {
      const next = [...prev];
      next[index] = { ...next[index], [field]: val };
      return next;
    });
  };

  const handleSave = async () => {
    if (!selectedBook) return;
    try {
      setSaving(true);
      await api.updateAdminPriceBook(selectedBook.id, { rules });
      onSuccess(`Tabela de preços "${selectedBook.name}" atualizada com sucesso.`);
      loadPricing();
    } catch {
      onError('Falha ao salvar valores da matriz.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400">Tabela Ativa:</span>
          <div className="flex gap-1">
            {books.map((b) => (
              <button
                key={b.id}
                onClick={() => handleSelectBook(b)}
                className={`px-2.5 py-1 rounded text-xs font-mono cursor-pointer ${
                  selectedBook?.id === b.id
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : 'text-slate-400 hover:text-white bg-white/5'
                }`}
              >
                {b.name} (v{b.version}) - {b.tenant_name}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium cursor-pointer disabled:opacity-50"
        >
          <Check className="w-3.5 h-3.5" />
          <span>{saving ? 'Salvando...' : 'Salvar Alterações de Preço'}</span>
        </button>
      </div>

      <div className="rounded border border-white/10 overflow-hidden bg-[#12141C]">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              <th className="px-3 py-2">Bloco de Dados</th>
              <th className="px-3 py-2">Preço Unitário (R$ Centavos)</th>
              <th className="px-3 py-2">Preço Formatado</th>
              <th className="px-3 py-2">Confiança Mínima (%)</th>
              <th className="px-3 py-2">Janela de Frescor (Dias)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs">
            {rules.map((r, idx) => (
              <tr key={r.block} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-3 py-2.5">
                  <div className="font-medium text-white">{blockLabels[r.block] || r.block}</div>
                  <div className="font-mono text-[10px] text-slate-500">{r.block}</div>
                </td>
                <td className="px-3 py-2.5">
                  <input
                    type="number"
                    min="0"
                    value={r.unit_price_cents}
                    onChange={(e) => handleRuleChange(idx, 'unit_price_cents', Number(e.target.value))}
                    className="w-24 rounded border border-white/10 bg-black/40 px-2 py-1 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
                  />
                </td>
                <td className="px-3 py-2.5 font-mono text-emerald-400 text-xs font-semibold">
                  R$ {(r.unit_price_cents / 100).toFixed(2)}
                </td>
                <td className="px-3 py-2.5">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    value={r.minimum_confidence}
                    onChange={(e) => handleRuleChange(idx, 'minimum_confidence', Number(e.target.value))}
                    className="w-20 rounded border border-white/10 bg-black/40 px-2 py-1 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
                  />
                  <span className="text-slate-500 font-mono text-xs ml-1">%</span>
                </td>
                <td className="px-3 py-2.5">
                  <input
                    type="number"
                    min="1"
                    value={r.refresh_window_days}
                    onChange={(e) => handleRuleChange(idx, 'refresh_window_days', Number(e.target.value))}
                    className="w-20 rounded border border-white/10 bg-black/40 px-2 py-1 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
                  />
                  <span className="text-slate-500 font-mono text-xs ml-1">dias</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =========================================================================
// TAB 4: CARTEIRAS & LEDGER CONTÁBIL
// =========================================================================
function WalletsTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [wallets, setWallets] = useState<AdminWallet[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<DjangoCreditTransaction[]>([]);
  const [loadingTx, setLoadingTx] = useState(false);

  // Credit injection modal
  const [showInjectModal, setShowInjectModal] = useState(false);
  const [injectTenantId, setInjectTenantId] = useState('');
  const [injectAmount, setInjectAmount] = useState(1000);
  const [injectReason, setInjectReason] = useState('');

  const loadWallets = useCallback(async () => {
    try {
      const res = await api.adminWallets();
      setWallets(res.results || []);
      if (res.results?.length && !selectedTenant) {
        setSelectedTenant(res.results[0].tenant);
      }
    } catch {
      onError('Erro ao carregar saldos das carteiras.');
    }
  }, [onError, selectedTenant]);

  useEffect(() => {
    loadWallets();
  }, [loadWallets]);

  const loadTransactions = useCallback(
    async (tId: string) => {
      try {
        setLoadingTx(true);
        const res = await api.adminWalletTransactions(tId);
        setTransactions(res.results || []);
      } catch {
        onError('Erro ao buscar extrato do ledger.');
      } finally {
        setLoadingTx(false);
      }
    },
    [onError]
  );

  useEffect(() => {
    if (selectedTenant) {
      loadTransactions(selectedTenant);
    }
  }, [selectedTenant, loadTransactions]);

  const handleInject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!injectReason || injectReason.trim().length < 5) {
      onError('A justificativa de auditoria deve ter no mínimo 5 caracteres.');
      return;
    }
    try {
      const res = await api.injectAdminCredit(injectTenantId, {
        amount: injectAmount,
        reason: injectReason,
      });
      onSuccess(`Crédito de ${injectAmount} lançado no ledger. Novo saldo: ${res.balance}.`);
      setShowInjectModal(false);
      setInjectReason('');
      loadWallets();
      if (selectedTenant === injectTenantId) {
        loadTransactions(injectTenantId);
      }
    } catch {
      onError('Falha ao injetar crédito no ledger.');
    }
  };

  return (
    <div className="space-y-4">
      {/* Wallets Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {wallets.map((w) => {
          const isSelected = selectedTenant === w.tenant;
          return (
            <div
              key={w.id}
              onClick={() => setSelectedTenant(w.tenant)}
              className={`p-3 rounded border transition cursor-pointer ${
                isSelected
                  ? 'bg-emerald-500/[0.04] border-emerald-500/40'
                  : 'bg-[#12141C] border-white/10 hover:border-white/20'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white text-xs">{w.tenant_name}</span>
                <span className="font-mono text-[10px] text-slate-500 uppercase">{w.currency}</span>
              </div>
              <div className="mt-2 flex items-baseline justify-between">
                <div>
                  <span className="text-xl font-bold font-mono text-emerald-400">
                    {new Intl.NumberFormat('pt-BR').format(w.balance)}
                  </span>
                  <span className="text-[10px] text-slate-400 font-mono ml-1">créditos</span>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setInjectTenantId(w.tenant);
                    setShowInjectModal(true);
                  }}
                  className="px-2 py-1 rounded bg-white/5 hover:bg-emerald-600 hover:text-white text-slate-300 text-[10px] font-mono transition cursor-pointer"
                >
                  + Injetar
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Ledger Transactions for Selected Tenant */}
      <div className="rounded border border-white/10 overflow-hidden bg-[#12141C] space-y-0">
        <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-white/[0.02]">
          <span className="text-xs font-mono text-slate-300">
            Trilha de Auditoria Imutável (Ledger de Dupla Entrada)
          </span>
          <span className="text-[10px] font-mono text-slate-500">
            {transactions.length} lançamentos encontrados
          </span>
        </div>
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-white/[0.01] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              <th className="px-3 py-2">Tipo</th>
              <th className="px-3 py-2">Valor</th>
              <th className="px-3 py-2">Saldo Após</th>
              <th className="px-3 py-2">Referência / Justificativa</th>
              <th className="px-3 py-2">Data & Hora</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs">
            {transactions.map((tx) => (
              <tr key={tx.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-3 py-2">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                      tx.transaction_type === 'DEPOSIT'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                        : tx.transaction_type === 'CAPTURE'
                        ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                        : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                    }`}
                  >
                    {tx.transaction_type}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono font-semibold text-white">
                  {tx.amount > 0 ? `+${tx.amount}` : tx.amount}
                </td>
                <td className="px-3 py-2 font-mono text-slate-400 text-[11px]">{tx.balance_after}</td>
                <td className="px-3 py-2 font-mono text-slate-300 text-[11px] truncate max-w-xs">
                  {tx.reference_id}
                </td>
                <td className="px-3 py-2 font-mono text-slate-500 text-[11px]">
                  {new Date(tx.created_at).toLocaleString('pt-BR')}
                </td>
              </tr>
            ))}
            {transactions.length === 0 && !loadingTx && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                  Nenhum lançamento no ledger para o workspace selecionado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Credit Injection Modal */}
      {showInjectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-lg border border-white/10 bg-[#12141C] p-5 shadow-xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-sm font-semibold text-white">Injetar Crédito Manual com Auditoria</h3>
              <button onClick={() => setShowInjectModal(false)} className="text-slate-400 hover:text-white cursor-pointer">
                ✕
              </button>
            </div>
            <form onSubmit={handleInject} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">Quantidade de Créditos</label>
                <input
                  type="number"
                  min="1"
                  required
                  value={injectAmount}
                  onChange={(e) => setInjectAmount(Number(e.target.value))}
                  className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-sm focus:border-emerald-500 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-400 font-mono text-[11px] mb-1">
                  Justificativa Obrigatória (Auditoria Contábil)
                </label>
                <textarea
                  required
                  rows={3}
                  value={injectReason}
                  onChange={(e) => setInjectReason(e.target.value)}
                  placeholder="Ex: Pagamento Pix recebido via fatura #9012 — contrato anual."
                  className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-sans text-xs focus:border-emerald-500 focus:outline-none"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2 border-t border-white/10">
                <button
                  type="button"
                  onClick={() => setShowInjectModal(false)}
                  className="px-3 py-1.5 rounded border border-white/10 text-slate-400 hover:text-white cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium cursor-pointer"
                >
                  Confirmar Injeção
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// =========================================================================
// TAB 5: LOTES & FILAS CELERY
// =========================================================================
function BatchesTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [batches, setBatches] = useState<AdminBatch[]>([]);
  const [queuesData, setQueuesData] = useState<AdminCeleryQueuesData | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [bRes, qRes] = await Promise.all([api.adminBatches(), api.adminCeleryQueues()]);
      setBatches(bRes.results || []);
      setQueuesData(qRes);
    } catch {
      onError('Erro ao sincronizar lotes e status do Celery.');
    } finally {
      setLoading(false);
    }
  }, [onError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAction = async (id: string, action: 'pause' | 'resume' | 'cancel') => {
    try {
      await api.actionAdminBatch(id, action);
      onSuccess(`Lote ${action === 'pause' ? 'pausado' : action === 'resume' ? 'retomado' : 'cancelado'}.`);
      loadData();
    } catch {
      onError(`Falha ao executar ação de ${action} no lote.`);
    }
  };

  return (
    <div className="space-y-4">
      {/* Celery Telemetry Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="p-3 rounded border border-white/10 bg-[#12141C]">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Workers Ativos</span>
          <span className="text-xl font-bold font-mono text-white mt-1 block">
            {queuesData?.active_workers ?? 1}
          </span>
        </div>
        <div className="p-3 rounded border border-white/10 bg-[#12141C]">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block">Throughput / Hora</span>
          <span className="text-xl font-bold font-mono text-emerald-400 mt-1 block">
            {queuesData?.total_throughput_hour ?? 0}
          </span>
        </div>
        <div className="p-3 rounded border border-white/10 bg-[#12141C] col-span-2">
          <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider block mb-1">
            Filas RabbitMQ & Mensagens Pendentes
          </span>
          <div className="flex flex-wrap gap-2">
            {queuesData?.queues.map((q) => (
              <span
                key={q.queue_name}
                className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[10px] font-mono text-slate-300"
              >
                {q.queue_name}: <strong className="text-white">{q.messages_count}</strong> msgs
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Global Batches Table */}
      <div className="rounded border border-white/10 overflow-hidden bg-[#12141C]">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
              <th className="px-3 py-2">Lote</th>
              <th className="px-3 py-2">Workspace</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Progresso</th>
              <th className="px-3 py-2">Criado em</th>
              <th className="px-3 py-2 text-right">Controles</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs">
            {batches.map((b) => (
              <tr key={b.id} className="hover:bg-white/[0.02] transition-colors">
                <td className="px-3 py-2">
                  <div className="font-medium text-white">{b.name}</div>
                  <div className="font-mono text-[10px] text-slate-500">{b.source_type}</div>
                </td>
                <td className="px-3 py-2 font-mono text-slate-300 text-[11px]">{b.tenant_name}</td>
                <td className="px-3 py-2">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                      b.status === 'RUNNING'
                        ? 'bg-blue-500/10 text-blue-400 border border-blue-500/30'
                        : b.status === 'COMPLETED'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                        : b.status === 'PAUSED'
                        ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                    }`}
                  >
                    {b.status}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-[11px]">
                  <span className="text-white font-semibold">{b.processed_rows}</span> / {b.total_rows}
                  <div className="w-24 bg-white/10 h-1 rounded mt-1 overflow-hidden">
                    <div
                      className="bg-emerald-400 h-full"
                      style={{
                        width: b.total_rows > 0 ? `${(b.processed_rows / b.total_rows) * 100}%` : '0%',
                      }}
                    />
                  </div>
                </td>
                <td className="px-3 py-2 font-mono text-slate-500 text-[11px]">
                  {new Date(b.created_at).toLocaleString('pt-BR')}
                </td>
                <td className="px-3 py-2 text-right space-x-1">
                  {b.status === 'RUNNING' && (
                    <button
                      onClick={() => handleAction(b.id, 'pause')}
                      title="Pausar Lote"
                      className="p-1 rounded bg-white/5 hover:bg-amber-500/20 text-slate-300 hover:text-amber-300 cursor-pointer"
                    >
                      <Pause className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {b.status === 'PAUSED' && (
                    <button
                      onClick={() => handleAction(b.id, 'resume')}
                      title="Retomar Lote"
                      className="p-1 rounded bg-white/5 hover:bg-emerald-500/20 text-slate-300 hover:text-emerald-300 cursor-pointer"
                    >
                      <Play className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {(b.status === 'RUNNING' || b.status === 'PAUSED') && (
                    <button
                      onClick={() => handleAction(b.id, 'cancel')}
                      title="Cancelar Lote"
                      className="p-1 rounded bg-white/5 hover:bg-rose-500/20 text-slate-300 hover:text-rose-300 cursor-pointer"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {batches.length === 0 && !loading && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                  Nenhum lote assíncrono executado até o momento.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =========================================================================
// TAB 6: PROVEDORES & ORÇAMENTO
// =========================================================================
function ProvidersTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [providersData, setProvidersData] = useState<AdminProvidersData | null>(null);
  const [dailyLimit, setDailyLimit] = useState(100);
  const [circuitRate, setCircuitRate] = useState(0.1);
  const [saving, setSaving] = useState(false);

  const loadProviders = useCallback(async () => {
    try {
      const data = await api.adminProviders();
      setProvidersData(data);
      if (data.budget) {
        setDailyLimit(data.budget.daily_limit_usd);
        setCircuitRate(data.budget.circuit_breaker_rate);
      }
    } catch {
      onError('Erro ao buscar status dos provedores.');
    }
  }, [onError]);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const handleSaveBudget = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      await api.updateAdminProviderBudget({
        daily_limit_usd: dailyLimit,
        circuit_breaker_rate: circuitRate,
      });
      onSuccess('Orçamento diário e circuit breaker salvos.');
      loadProviders();
    } catch {
      onError('Falha ao salvar limites de orçamento.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Providers Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        {providersData?.providers.map((p) => (
          <div key={p.name} className="p-3 rounded border border-white/10 bg-[#12141C] space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-white text-xs">{p.name}</span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                  p.status === 'ONLINE'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                }`}
              >
                {p.status}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono text-slate-400 border-t border-white/5 pt-2">
              <div>
                <span className="text-[10px] block text-slate-500">Latência</span>
                <span className="text-white font-medium">{p.latency_ms} ms</span>
              </div>
              <div>
                <span className="text-[10px] block text-slate-500">Taxa 24h</span>
                <span className="text-emerald-400 font-medium">{(p.success_rate_24h * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Budget & Circuit Breaker Settings */}
      <div className="rounded border border-white/10 bg-[#12141C] p-4 space-y-3">
        <h3 className="text-xs font-mono font-semibold text-white uppercase tracking-wider">
          Controle de Orçamento USD & Circuit Breaker
        </h3>
        <form onSubmit={handleSaveBudget} className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs items-end">
          <div>
            <label className="block text-slate-400 font-mono text-[11px] mb-1">
              Limite Diário Global (USD)
            </label>
            <div className="flex items-center gap-1">
              <span className="text-slate-500 font-mono">$</span>
              <input
                type="number"
                step="0.01"
                min="0"
                value={dailyLimit}
                onChange={(e) => setDailyLimit(Number(e.target.value))}
                className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </div>
          <div>
            <label className="block text-slate-400 font-mono text-[11px] mb-1">
              Circuit Breaker - Taxa de Erro (0.0 a 1.0)
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max="1"
              value={circuitRate}
              onChange={(e) => setCircuitRate(Number(e.target.value))}
              className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
            />
          </div>
          <div>
            <button
              type="submit"
              disabled={saving}
              className="w-full px-3 py-1.5 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium cursor-pointer text-xs"
            >
              {saving ? 'Gravando...' : 'Aplicar Limites de Custos'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// =========================================================================
// TAB 7: GOVERNANÇA & SUPRESSÃO (LGPD)
// =========================================================================
function GovernanceTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [suppressions, setSuppressions] = useState<AdminSuppression[]>([]);
  const [auditLogs, setAuditLogs] = useState<AdminAuditLog[]>([]);
  const [activeSubTab, setActiveSubTab] = useState<'suppression' | 'audit'>('suppression');

  // Add suppression form
  const [type, setType] = useState<'CNPJ' | 'EMAIL' | 'DOMAIN'>('EMAIL');
  const [val, setVal] = useState('');
  const [reason, setReason] = useState('');

  const loadData = useCallback(async () => {
    try {
      const [sRes, aRes] = await Promise.all([api.adminSuppression(), api.adminAuditLogs(50)]);
      setSuppressions(sRes.results || []);
      setAuditLogs(aRes.results || []);
    } catch {
      onError('Erro ao sincronizar dados de governança.');
    }
  }, [onError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAddSuppression = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!val || !reason) {
      onError('Valor e justificativa são obrigatórios.');
      return;
    }
    try {
      await api.createAdminSuppression({
        identifier_type: type,
        identifier_value: val,
        reason,
      });
      onSuccess(`Identificador "${val}" adicionado à lista de supressão (Opt-Out).`);
      setVal('');
      setReason('');
      loadData();
    } catch {
      onError('Falha ao registrar supressão.');
    }
  };

  const handleDeleteSuppression = async (id: string) => {
    try {
      await api.deleteAdminSuppression(id);
      onSuccess('Supressão removida.');
      loadData();
    } catch {
      onError('Falha ao remover item da lista de supressão.');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-1 border-b border-white/10 pb-2">
        <button
          onClick={() => setActiveSubTab('suppression')}
          className={`px-3 py-1 rounded text-xs font-mono cursor-pointer ${
            activeSubTab === 'suppression' ? 'bg-white/10 text-white font-semibold' : 'text-slate-400 hover:text-white'
          }`}
        >
          Lista Negra de Supressão (Opt-Out) ({suppressions.length})
        </button>
        <button
          onClick={() => setActiveSubTab('audit')}
          className={`px-3 py-1 rounded text-xs font-mono cursor-pointer ${
            activeSubTab === 'audit' ? 'bg-white/10 text-white font-semibold' : 'text-slate-400 hover:text-white'
          }`}
        >
          Logs de Auditoria de Segurança ({auditLogs.length})
        </button>
      </div>

      {activeSubTab === 'suppression' ? (
        <div className="space-y-4">
          <form
            onSubmit={handleAddSuppression}
            className="p-3 rounded border border-white/10 bg-[#12141C] grid grid-cols-1 sm:grid-cols-4 gap-2 text-xs items-end"
          >
            <div>
              <label className="block text-slate-400 font-mono text-[11px] mb-1">Tipo</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as 'CNPJ' | 'EMAIL' | 'DOMAIN')}
                className="w-full rounded border border-white/10 bg-black/40 px-2 py-1.5 text-white font-mono text-xs focus:outline-none"
              >
                <option value="EMAIL">EMAIL</option>
                <option value="CNPJ">CNPJ</option>
                <option value="DOMAIN">DOMAIN</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-400 font-mono text-[11px] mb-1">Valor</label>
              <input
                type="text"
                required
                value={val}
                onChange={(e) => setVal(e.target.value)}
                placeholder="email@empresa.com ou CNPJ"
                className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-mono text-[11px] mb-1">Motivo (LGPD)</label>
              <input
                type="text"
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Titular solicitou exclusão"
                className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white text-xs focus:outline-none"
              />
            </div>
            <div>
              <button
                type="submit"
                className="w-full px-3 py-1.5 rounded bg-rose-600 hover:bg-rose-500 text-white font-medium cursor-pointer text-xs"
              >
                Bloquear Identificador
              </button>
            </div>
          </form>

          <div className="rounded border border-white/10 overflow-hidden bg-[#12141C]">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                  <th className="px-3 py-2">Tipo</th>
                  <th className="px-3 py-2">Identificador</th>
                  <th className="px-3 py-2">Justificativa</th>
                  <th className="px-3 py-2">Data</th>
                  <th className="px-3 py-2 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5 text-xs">
                {suppressions.map((s) => (
                  <tr key={s.id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="px-3 py-2 font-mono text-[10px]">
                      <span className="px-1.5 py-0.5 rounded bg-white/5 text-slate-300">{s.identifier_type}</span>
                    </td>
                    <td className="px-3 py-2 font-mono text-white text-[11px]">{s.identifier_value}</td>
                    <td className="px-3 py-2 text-slate-300 text-xs">{s.reason}</td>
                    <td className="px-3 py-2 font-mono text-slate-500 text-[11px]">
                      {new Date(s.created_at).toLocaleDateString('pt-BR')}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        onClick={() => handleDeleteSuppression(s.id)}
                        className="text-slate-400 hover:text-rose-400 cursor-pointer"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
                {suppressions.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                      Nenhum registro na lista negra de supressão.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="rounded border border-white/10 overflow-hidden bg-[#12141C]">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                <th className="px-3 py-2">Ação</th>
                <th className="px-3 py-2">Entidade</th>
                <th className="px-3 py-2">IP / Origem</th>
                <th className="px-3 py-2">Metadados</th>
                <th className="px-3 py-2">Data & Hora</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-xs font-mono">
              {auditLogs.map((log) => (
                <tr key={log.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-3 py-2 text-emerald-400 font-semibold text-[11px]">{log.action}</td>
                  <td className="px-3 py-2 text-slate-300 text-[11px]">{log.entity_type}</td>
                  <td className="px-3 py-2 text-slate-400 text-[11px]">{log.ip_address || '-'}</td>
                  <td className="px-3 py-2 text-slate-400 text-[10px] truncate max-w-xs">
                    {JSON.stringify(log.metadata)}
                  </td>
                  <td className="px-3 py-2 text-slate-500 text-[11px]">
                    {new Date(log.created_at).toLocaleString('pt-BR')}
                  </td>
                </tr>
              ))}
              {auditLogs.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500 font-mono text-xs">
                    Nenhum log de auditoria recente.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// =========================================================================
// TAB 8: ZERO-BOUNCE SMTP & MARCA WHITE-LABEL
// =========================================================================
function SmtpBrandTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const { branding, updateBranding } = useBranding();

  // Branding Form State
  const [platformName, setPlatformName] = useState(branding.platform_name || '');
  const [logoDark, setLogoDark] = useState(branding.logo_url_dark || '');
  const [logoLight, setLogoLight] = useState(branding.logo_url_light || '');
  const [faviconUrl, setFaviconUrl] = useState(branding.favicon_url || '');
  const [accentColor, setAccentColor] = useState(branding.accent_color || '#3B82F6');
  const [primaryColor, setPrimaryColor] = useState(branding.primary_color || '#0F172A');
  const [supportEmail, setSupportEmail] = useState(branding.support_email || '');
  const [termsUrl, setTermsUrl] = useState(branding.terms_url || '');
  const [privacyUrl, setPrivacyUrl] = useState(branding.privacy_url || '');
  const [savingBrand, setSavingBrand] = useState(false);

  // SMTP Probe State
  const [smtpConfig, setSmtpConfig] = useState<AdminSMTPConfig | null>(null);
  const [probeEmail, setProbeEmail] = useState('');
  const [probeLoading, setProbeLoading] = useState(false);
  const [probeResult, setProbeResult] = useState<SMTPProbeResult | null>(null);

  useEffect(() => {
    api.adminSMTPConfig().then(setSmtpConfig).catch(() => {});
  }, []);

  const handleSaveBranding = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSavingBrand(true);
      await updateBranding({
        platform_name: platformName,
        logo_url_dark: logoDark,
        logo_url_light: logoLight,
        favicon_url: faviconUrl,
        accent_color: accentColor,
        primary_color: primaryColor,
        support_email: supportEmail,
        terms_url: termsUrl,
        privacy_url: privacyUrl,
      });
      onSuccess('Identidade visual White-Label atualizada instantaneamente.');
    } catch {
      onError('Falha ao atualizar parâmetros de marca.');
    } finally {
      setSavingBrand(false);
    }
  };

  const handleProbe = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!probeEmail || !probeEmail.includes('@')) {
      onError('Informe um email válido para o probe.');
      return;
    }
    try {
      setProbeLoading(true);
      const res = await api.probeSMTP(probeEmail);
      setProbeResult(res);
      onSuccess(`Probe SMTP RFC 5321 concluído em ${res.latency_ms}ms.`);
    } catch {
      onError('Falha na sondagem SMTP.');
    } finally {
      setProbeLoading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      {/* White-Label Customization Form */}
      <div className="rounded border border-white/10 bg-[#12141C] p-4 space-y-4">
        <div className="flex items-center gap-2 border-b border-white/10 pb-2">
          <Palette className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-mono font-semibold text-white uppercase tracking-wider">
            Personalização de Marca White-Label
          </h3>
        </div>

        <form onSubmit={handleSaveBranding} className="space-y-3 text-xs">
          <div>
            <label className="block text-slate-400 font-mono text-[11px] mb-1">Nome da Plataforma</label>
            <input
              type="text"
              value={platformName}
              onChange={(e) => setPlatformName(e.target.value)}
              placeholder="Ex: LeadStream Pro"
              className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-sans text-xs focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-slate-400 font-mono text-[11px] mb-1">Logo URL (Modo Escuro)</label>
              <input
                type="text"
                value={logoDark}
                onChange={(e) => setLogoDark(e.target.value)}
                placeholder="https://.../logo-dark.svg"
                className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-[11px] focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-mono text-[11px] mb-1">Logo URL (Modo Claro)</label>
              <input
                type="text"
                value={logoLight}
                onChange={(e) => setLogoLight(e.target.value)}
                placeholder="https://.../logo-light.svg"
                className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-[11px] focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-slate-400 font-mono text-[11px] mb-1">Favicon URL</label>
              <input
                type="text"
                value={faviconUrl}
                onChange={(e) => setFaviconUrl(e.target.value)}
                placeholder="https://.../favicon.ico"
                className="w-full rounded border border-white/10 bg-black/40 px-2 py-1.5 text-white font-mono text-[11px] focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-slate-400 font-mono text-[11px] mb-1">Cor Accent</label>
              <div className="flex items-center gap-1.5">
                <input
                  type="color"
                  value={accentColor}
                  onChange={(e) => setAccentColor(e.target.value)}
                  className="w-8 h-8 rounded border-0 cursor-pointer bg-transparent"
                />
                <input
                  type="text"
                  value={accentColor}
                  onChange={(e) => setAccentColor(e.target.value)}
                  className="w-full rounded border border-white/10 bg-black/40 px-2 py-1 text-white font-mono text-[11px]"
                />
              </div>
            </div>
            <div>
              <label className="block text-slate-400 font-mono text-[11px] mb-1">Cor Primária</label>
              <div className="flex items-center gap-1.5">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-8 h-8 rounded border-0 cursor-pointer bg-transparent"
                />
                <input
                  type="text"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-full rounded border border-white/10 bg-black/40 px-2 py-1 text-white font-mono text-[11px]"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-slate-400 font-mono text-[11px] mb-1">Email de Suporte</label>
            <input
              type="email"
              value={supportEmail}
              onChange={(e) => setSupportEmail(e.target.value)}
              placeholder="suporte@suamarca.com.br"
              className="w-full rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={savingBrand}
            className="w-full px-3 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium cursor-pointer text-xs"
          >
            {savingBrand ? 'Atualizando Marca...' : 'Salvar Configurações de Marca'}
          </button>
        </form>
      </div>

      {/* SMTP Zero-Bounce Engine Interactive Probe */}
      <div className="rounded border border-white/10 bg-[#12141C] p-4 space-y-4">
        <div className="flex items-center gap-2 border-b border-white/10 pb-2">
          <Mail className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-mono font-semibold text-white uppercase tracking-wider">
            Motor Zero-Bounce (Probe SMTP RFC 5321)
          </h3>
        </div>

        <div className="p-3 rounded bg-black/40 border border-white/5 space-y-1 text-xs font-mono text-slate-400">
          <div>
            HELO Domain: <strong className="text-white">{smtpConfig?.helo_domain || 'mx.leadstream.io'}</strong>
          </div>
          <div>
            Timeout Conexão: <strong className="text-white">{smtpConfig?.timeout_seconds || 8}s</strong> ·
            Estratégia Catch-All:{' '}
            <strong className="text-emerald-400">{smtpConfig?.catch_all_strategy || 'PROBE'}</strong>
          </div>
        </div>

        <form onSubmit={handleProbe} className="space-y-2">
          <label className="block text-slate-400 font-mono text-[11px]">Teste Interativo de Validação Direta</label>
          <div className="flex gap-2">
            <input
              type="email"
              required
              value={probeEmail}
              onChange={(e) => setProbeEmail(e.target.value)}
              placeholder="contato@empresa.com.br"
              className="flex-1 rounded border border-white/10 bg-black/40 px-3 py-1.5 text-white font-mono text-xs focus:border-emerald-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={probeLoading}
              className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs cursor-pointer disabled:opacity-50 flex items-center gap-1"
            >
              <Send className="w-3 h-3" />
              <span>{probeLoading ? 'Sondando...' : 'Sondar MX'}</span>
            </button>
          </div>
        </form>

        {probeResult && (
          <div className="p-3 rounded border border-white/10 bg-black/50 space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">{probeResult.email}</span>
              <span
                className={`px-2 py-0.5 rounded text-[10px] ${
                  probeResult.status === 'DELIVERABLE'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                    : probeResult.status === 'CATCH_ALL'
                    ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                }`}
              >
                {probeResult.status}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 space-y-1">
              <div>Host MX: {probeResult.mx_host || '-'}</div>
              <div>Código SMTP: {probeResult.smtp_code || '-'}</div>
              <div>Latência de Handshake: {probeResult.latency_ms} ms</div>
              {probeResult.raw_response && (
                <div className="p-2 rounded bg-black/60 text-[10px] text-slate-400 border border-white/5 break-all">
                  {probeResult.raw_response}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
