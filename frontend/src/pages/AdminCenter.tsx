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
  RefreshCw,
  Plus,
  Trash2,
  Copy,
  Check,
  Send,
  Sliders,
  Server,
  Lock,
} from 'lucide-react';
import { api } from '../api';
import { useBranding } from '../components/BrandingProvider';
import {
  ensureArray,
  type AdminTenant,
  type AdminUser,
  type AdminAPIKey,
  type AdminPriceBook,
  type AdminWallet,
  type AdminProvidersData,
  type AdminSuppression,
  type AdminAuditLog,
  type AdminSMTPConfig,
  type SMTPProbeResult,
  type AdminBatch,
  type AdminCeleryQueuesData,
  type DjangoCreditTransaction,
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
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const showFeedback = (type: 'success' | 'error', message: string) => {
    setFeedback({ type, message });
    setTimeout(() => setFeedback(null), 4500);
  };

  return (
    <div className="space-y-6 max-w-[1440px] mx-auto pb-8">
      {/* Top Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 tracking-tight">
            Administração do Sistema
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Gerenciamento de workspaces, planos de preços, usuários, provedores e personalização.
          </p>
        </div>
      </div>

      {feedback && (
        <div
          className={`flex items-center gap-2.5 px-4 py-2.5 rounded-lg text-xs font-medium border ${
            feedback.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-rose-50 text-rose-800 border-rose-200'
          } animate-in fade-in duration-200 shadow-xs`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
          ) : (
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-600" />
          )}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Clean Horizontal Sub-Nav */}
      <div className="flex items-center gap-1 overflow-x-auto border-b border-slate-200 scrollbar-none -mb-2">
        <TabButton active={activeTab === 'tenants'} onClick={() => setActiveTab('tenants')} icon={Building2} label="Workspaces & Clientes" />
        <TabButton active={activeTab === 'users'} onClick={() => setActiveTab('users')} icon={Users} label="Usuários & Chaves" />
        <TabButton active={activeTab === 'pricing'} onClick={() => setActiveTab('pricing')} icon={Sliders} label="Planos & Preços (BRL)" />
        <TabButton active={activeTab === 'wallets'} onClick={() => setActiveTab('wallets')} icon={CreditCard} label="Carteiras & Ledger" />
        <TabButton active={activeTab === 'batches'} onClick={() => setActiveTab('batches')} icon={Layers} label="Lotes & Celery" />
        <TabButton active={activeTab === 'providers'} onClick={() => setActiveTab('providers')} icon={Cpu} label="Provedores & Custos" />
        <TabButton active={activeTab === 'governance'} onClick={() => setActiveTab('governance')} icon={ShieldCheck} label="Governança & LGPD" />
        <TabButton active={activeTab === 'smtp_brand'} onClick={() => setActiveTab('smtp_brand')} icon={Palette} label="Zero-Bounce & Marca" />
      </div>

      {/* Tab Panels */}
      <div className="mt-4">
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
      className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-medium border-b-2 transition-colors whitespace-nowrap cursor-pointer -mb-px ${
        active
          ? 'border-blue-600 text-blue-600 font-semibold'
          : 'border-transparent text-slate-500 hover:text-slate-900 hover:border-slate-300'
      }`}
    >
      <Icon className={`w-3.5 h-3.5 shrink-0 ${active ? 'text-blue-600' : 'text-slate-400'}`} />
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
      setTenants(ensureArray<AdminTenant>(res));
    } catch {
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
      await api.impersonateTenant(t.id);
      onSuccess(`Sessão alternada para o inquilino "${t.name}".`);
      window.location.reload();
    } catch {
      onError('Não foi possível alternar para o inquilino.');
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newSlug.trim()) {
      onError('Nome e slug são obrigatórios.');
      return;
    }
    try {
      await api.createAdminTenant({
        name: newName.trim(),
        slug: newSlug.trim().toLowerCase().replace(/[^a-z0-9_-]/g, '-'),
        max_users: maxUsers,
        max_leads_monthly: maxLeads,
        max_storage_mb: maxStorage,
        initial_credits: initialCredits,
        initial_admin_username: adminUsername || undefined,
        initial_admin_email: adminEmail || undefined,
        initial_admin_password: adminPassword || undefined,
      });
      onSuccess(`Workspace "${newName}" provisionado com sucesso!`);
      setShowCreateModal(false);
      setNewName('');
      setNewSlug('');
      setAdminUsername('');
      setAdminEmail('');
      setAdminPassword('');
      loadTenants();
    } catch {
      onError('Falha ao criar novo workspace.');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">
          Workspaces Registrados ({tenants.length})
        </span>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-xs shadow-xs transition-all flex items-center gap-2 cursor-pointer w-fit"
        >
          <Plus className="w-4 h-4" />
          <span>Novo Workspace</span>
        </button>
      </div>

      <div className="bg-white border border-slate-200/90 rounded-[12px] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="px-4 py-3">Workspace</th>
                <th className="px-4 py-3">Slug</th>
                <th className="px-4 py-3">Limites Operacionais</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Criado em</th>
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {tenants.map((t) => (
                <tr key={t.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="px-4 py-3 font-bold text-slate-900">{t.name}</td>
                  <td className="px-4 py-3 font-mono text-slate-500 text-[11px]">{t.slug}</td>
                  <td className="px-4 py-3 text-[11px] text-slate-600 font-semibold">
                    <span title="Usuários">{t.max_users} usr</span> ·{' '}
                    <span title="Leads / Mês">{((t.max_leads_monthly || 50000) / 1000).toFixed(0)}k leads</span> ·{' '}
                    <span title="Storage">{t.max_storage_mb || 2048} MB</span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleToggleActive(t)}
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold cursor-pointer border ${
                        t.is_active
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : 'bg-rose-50 text-rose-700 border-rose-200'
                      }`}
                    >
                      {t.is_active ? 'Ativo' : 'Inativo'}
                    </button>
                  </td>
                  <td className="px-4 py-3 text-slate-500 font-medium text-[11px]">
                    {new Date(t.created_at).toLocaleDateString('pt-BR')}
                  </td>
                  <td className="px-4 py-3 text-right space-x-2">
                    <button
                      onClick={() => handleImpersonate(t)}
                      title="Alternar contexto de sessão para este inquilino"
                      className="px-3 py-1 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-[11px] font-bold text-slate-700 hover:text-slate-900 transition-all cursor-pointer shadow-2xs"
                    >
                      Acessar
                    </button>
                  </td>
                </tr>
              ))}
              {tenants.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400 font-medium text-xs">
                    Nenhum workspace cadastrado no sistema.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Creation Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-[12px] border border-slate-200 bg-white p-6 shadow-2xl space-y-4 text-slate-900">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-extrabold text-slate-900">Provisionar Novo Workspace</h3>
              <button onClick={() => setShowCreateModal(false)} className="text-slate-400 hover:text-slate-600 font-bold cursor-pointer">
                ✕
              </button>
            </div>
            <form onSubmit={handleCreate} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-700 font-bold mb-1">Nome da Empresa / Workspace</label>
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
                  placeholder="Acionista Capital"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs font-medium focus:border-blue-600 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-700 font-bold mb-1">Slug do Workspace (Identificador de Domínio)</label>
                <input
                  type="text"
                  required
                  value={newSlug}
                  onChange={(e) => setNewSlug(e.target.value)}
                  placeholder="acionista-capital"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 font-mono text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-3 gap-2.5">
                <div>
                  <label className="block text-slate-700 font-bold text-[11px] mb-1">Max Usuários</label>
                  <input
                    type="number"
                    value={maxUsers}
                    onChange={(e) => setMaxUsers(Number(e.target.value))}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-slate-900 text-xs font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-bold text-[11px] mb-1">Max Leads/Mês</label>
                  <input
                    type="number"
                    value={maxLeads}
                    onChange={(e) => setMaxLeads(Number(e.target.value))}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-slate-900 text-xs font-semibold"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-bold text-[11px] mb-1">Créditos Iniciais (BRL)</label>
                  <input
                    type="number"
                    value={initialCredits}
                    onChange={(e) => setInitialCredits(Number(e.target.value))}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-emerald-700 text-xs font-extrabold"
                  />
                </div>
              </div>
              <div className="border-t border-slate-100 pt-3">
                <span className="block text-slate-500 font-bold text-[11px] mb-2 uppercase tracking-wider">
                  Usuário Administrador Inicial (Opcional)
                </span>
                <div className="space-y-2">
                  <input
                    type="text"
                    value={adminUsername}
                    onChange={(e) => setAdminUsername(e.target.value)}
                    placeholder="Username admin (ex: gestor)"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs font-medium"
                  />
                  <input
                    type="email"
                    value={adminEmail}
                    onChange={(e) => setAdminEmail(e.target.value)}
                    placeholder="Email comercial"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs font-medium"
                  />
                  <input
                    type="password"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    placeholder="Senha provisória"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs font-medium"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 font-bold cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer shadow-xs"
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
      const usersList = ensureArray<AdminUser>(uRes);
      const keysList = ensureArray<AdminAPIKey>(kRes);
      const tenantsList = ensureArray<AdminTenant>(tRes);

      setUsers(usersList);
      setKeys(keysList);
      setTenants(tenantsList);
      if (tenantsList.length && !keyTenant) {
        setKeyTenant(tenantsList[0].id);
        setNewUserTenant(tenantsList[0].id);
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
    <div className="space-y-4">
      {/* Subnav */}
      <div className="flex items-center justify-between gap-3 border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveSubTab('users')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all ${
              activeSubTab === 'users'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            Usuários ({users.length})
          </button>
          <button
            onClick={() => setActiveSubTab('keys')}
            className={`px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all ${
              activeSubTab === 'keys'
                ? 'bg-blue-600 text-white shadow-xs'
                : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}
          >
            Chaves de API Criptográficas ({keys.length})
          </button>
        </div>

        {activeSubTab === 'users' ? (
          <button
            onClick={() => setShowUserModal(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-xs shadow-xs transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            <span>Novo Usuário</span>
          </button>
        ) : (
          <button
            onClick={() => {
              setGeneratedKey(null);
              setShowKeyModal(true);
            }}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-xs shadow-xs transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <Key className="w-4 h-4" />
            <span>Gerar Nova Chave</span>
          </button>
        )}
      </div>

      {activeSubTab === 'users' ? (
        <div className="bg-white border border-slate-200/90 rounded-[12px] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Usuário</th>
                  <th className="px-4 py-3">E-mail</th>
                  <th className="px-4 py-3">Workspaces Vinculados</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Superadmin</th>
                  <th className="px-4 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-4 py-3 font-bold text-slate-900">{u.username}</td>
                    <td className="px-4 py-3 text-slate-600 font-medium">{u.email}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {ensureArray<{ tenant_name: string; role: string }>(u.memberships).map((m, i) => (
                          <span
                            key={i}
                            className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[10px] font-semibold border border-slate-200"
                          >
                            {m.tenant_name} ({m.role})
                          </span>
                        ))}
                        {(!u.memberships || u.memberships.length === 0) && (
                          <span className="text-slate-400 text-[11px] font-medium">Sem workspace</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold ${
                          u.is_active
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}
                      >
                        {u.is_active ? 'Ativo' : 'Inativo'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {u.is_superuser ? (
                        <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-extrabold">
                          SUPER
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[11px] font-medium">Comum</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleToggleUserActive(u)}
                        className="px-3 py-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-[11px] font-bold transition-all cursor-pointer shadow-2xs"
                      >
                        {u.is_active ? 'Inativar' : 'Ativar'}
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-400 font-medium text-xs">
                      Nenhum usuário cadastrado.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-slate-200/90 rounded-[12px] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Nome / Identificador</th>
                  <th className="px-4 py-3">Prefixo Criptográfico</th>
                  <th className="px-4 py-3">Workspace</th>
                  <th className="px-4 py-3">Escopo</th>
                  <th className="px-4 py-3">Último Uso</th>
                  <th className="px-4 py-3 text-right">Ação</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {keys.map((k) => (
                  <tr key={k.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-4 py-3 font-bold text-slate-900">{k.name}</td>
                    <td className="px-4 py-3 font-mono text-slate-600 text-[11px]">
                      <span className="bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                        {k.prefix}...
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700 font-semibold">{k.tenant_name}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 text-[10px] font-extrabold">
                        {k.scope}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500 font-medium text-[11px]">
                      {k.last_used_at ? new Date(k.last_used_at).toLocaleDateString('pt-BR') : 'Nunca utilizada'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => handleRevokeKey(k.id, k.name)}
                        className="px-2.5 py-1 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 hover:bg-rose-100 text-[11px] font-bold transition-all cursor-pointer"
                      >
                        Revogar
                      </button>
                    </td>
                  </tr>
                ))}
                {keys.length === 0 && !loading && (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-slate-400 font-medium text-xs">
                      Nenhuma chave de API gerada.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Key Creation Modal */}
      {showKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-[12px] border border-slate-200 bg-white p-6 shadow-2xl space-y-4 text-slate-900">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-extrabold text-slate-900">Gerar Nova Chave de API Criptográfica</h3>
              <button onClick={() => setShowKeyModal(false)} className="text-slate-400 hover:text-slate-600 font-bold cursor-pointer">
                ✕
              </button>
            </div>
            {generatedKey ? (
              <div className="space-y-4">
                <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs font-medium">
                  <strong>Atenção:</strong> Copie sua chave de API agora. Ela não será exibida novamente por segurança.
                </div>
                <div className="flex items-center gap-2 p-3 rounded-xl bg-slate-50 border border-slate-200">
                  <code className="text-xs font-mono text-slate-900 break-all flex-1 select-all">{generatedKey}</code>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(generatedKey);
                      onSuccess('Chave copiada para a área de transferência!');
                    }}
                    className="p-2 rounded-lg bg-white border border-slate-200 text-slate-700 hover:bg-slate-100 cursor-pointer shadow-2xs"
                    title="Copiar"
                  >
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
                <button
                  onClick={() => setShowKeyModal(false)}
                  className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-xs cursor-pointer shadow-xs"
                >
                  Concluir
                </button>
              </div>
            ) : (
              <form onSubmit={handleCreateKey} className="space-y-3.5 text-xs">
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Nome Identificador</label>
                  <input
                    type="text"
                    required
                    value={keyName}
                    onChange={(e) => setKeyName(e.target.value)}
                    placeholder="Ex: Integração CRM Hubspot / Produção"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs font-medium focus:border-blue-600 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Workspace de Destino</label>
                  <select
                    value={keyTenant}
                    onChange={(e) => setKeyTenant(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 text-xs font-medium focus:border-blue-600 focus:outline-none"
                  >
                    {tenants.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.name} ({t.slug})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Escopo de Acesso</label>
                  <select
                    value={keyScope}
                    onChange={(e) => setKeyScope(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 text-xs font-medium focus:border-blue-600 focus:outline-none"
                  >
                    <option value="FULL">Acesso Total (Leitura, Enriquecimento e Disparo)</option>
                    <option value="READ_ONLY">Apenas Leitura (Consulta Cadastral)</option>
                    <option value="ENRICH_ONLY">Apenas Enriquecimento de Lotes</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
                  <button
                    type="button"
                    onClick={() => setShowKeyModal(false)}
                    className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 font-bold cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer shadow-xs"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-[12px] border border-slate-200 bg-white p-6 shadow-2xl space-y-4 text-slate-900">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-extrabold text-slate-900">Cadastrar Novo Usuário</h3>
              <button onClick={() => setShowUserModal(false)} className="text-slate-400 hover:text-slate-600 font-bold cursor-pointer">
                ✕
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-700 font-bold mb-1">Nome de Usuário (Username)</label>
                <input
                  type="text"
                  required
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="Ex: joao.silva"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 font-mono text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-700 font-bold mb-1">Email Corporativo</label>
                <input
                  type="email"
                  required
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  placeholder="joao@empresa.com.br"
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-slate-700 font-bold mb-1">Senha Provisória</label>
                <input
                  type="password"
                  required
                  value={newUserPassword}
                  onChange={(e) => setNewUserPassword(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs focus:border-blue-600 focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-slate-700 font-bold mb-1">Workspace</label>
                  <select
                    value={newUserTenant}
                    onChange={(e) => setNewUserTenant(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 text-xs focus:border-blue-600 focus:outline-none"
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
                  <label className="block text-slate-700 font-bold mb-1">Papel (Role)</label>
                  <select
                    value={newUserRole}
                    onChange={(e) => setNewUserRole(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 text-xs focus:border-blue-600 focus:outline-none"
                  >
                    <option value="ADMIN">ADMIN</option>
                    <option value="OPERATOR">OPERATOR</option>
                    <option value="READ_ONLY">READ_ONLY</option>
                  </select>
                </div>
              </div>
              <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowUserModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 font-bold cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer shadow-xs"
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
// TAB 3: PLANOS & PREÇOS BRL (MATRIZ DE BLOCOS)
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
    CONTACT_EMAILS: 'Emails Corporativos Verificados RFC 5321',
    CONTACT_PHONES: 'Telefones & WhatsApp Validado',
    CREDIT_FINANCIAL: 'Capital Social & Regime Tributário',
    DIGITAL_PRESENCE: 'Presença Digital (Web, Redes Sociais)',
    LOCATION_GEO: 'Geolocalização & Endereço Completo',
    PIX_BANKING: 'Chaves Pix & Domicílio Bancário',
    GOVERNMENT_RISK: 'Sanções e Acordos (Portal da Transparência)',
    PUBLIC_SECTOR: 'Contratos com o Governo Federal',
  };

  const loadPricing = useCallback(async () => {
    try {
      const data = await api.adminPricing();
      const list = ensureArray<AdminPriceBook>(data);
      setBooks(list);
      if (list.length > 0) {
        setSelectedBook(list[0]);
        const bookRules = ensureArray<{ block: string; unit_price_cents: number; minimum_confidence?: number; refresh_window_days?: number }>(list[0].rules);
        setRules(
          bookRules.map((r) => ({
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
    const bookRules = ensureArray<{ block: string; unit_price_cents: number; minimum_confidence?: number; refresh_window_days?: number }>(b.rules);
    setRules(
      bookRules.map((r) => ({
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
      onSuccess(`Tabela de preços "${selectedBook.name}" salva com sucesso.`);
      loadPricing();
    } catch {
      onError('Falha ao salvar valores da matriz.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-slate-700 uppercase tracking-wider">Tabela de Preços Ativa:</span>
          <div className="flex gap-1.5 flex-wrap">
            {books.map((b) => (
              <button
                key={b.id}
                onClick={() => handleSelectBook(b)}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all ${
                  selectedBook?.id === b.id
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                {b.name} (v{b.version}) - {b.tenant_name || 'Padrão'}
              </button>
            ))}
          </div>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold rounded-xl cursor-pointer disabled:opacity-50 flex items-center gap-1.5 shadow-xs w-fit"
        >
          <Check className="w-4 h-4" />
          <span>{saving ? 'Salvando...' : 'Salvar Alterações de Preço'}</span>
        </button>
      </div>

      <div className="bg-white border border-slate-200/90 rounded-[12px] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="px-4 py-3">Bloco de Dados</th>
                <th className="px-4 py-3">Preço Unitário (Centavos)</th>
                <th className="px-4 py-3">Valor em Reais (R$)</th>
                <th className="px-4 py-3">Confiança Mínima (%)</th>
                <th className="px-4 py-3">Janela de Frescor (Dias)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {rules.map((r, idx) => (
                <tr key={r.block} className="hover:bg-slate-50/70 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-bold text-slate-900">{blockLabels[r.block] || r.block}</div>
                    <div className="font-mono text-[10px] text-slate-400 font-semibold">{r.block}</div>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      min="0"
                      value={r.unit_price_cents}
                      onChange={(e) => handleRuleChange(idx, 'unit_price_cents', Number(e.target.value))}
                      className="w-24 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-slate-900 font-mono text-xs font-bold focus:border-blue-600 focus:outline-none"
                    />
                    <span className="text-slate-400 text-[11px] ml-1">¢</span>
                  </td>
                  <td className="px-4 py-3 font-extrabold text-emerald-700 text-xs">
                    R$ {(r.unit_price_cents / 100).toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      min="0"
                      max="100"
                      value={r.minimum_confidence}
                      onChange={(e) => handleRuleChange(idx, 'minimum_confidence', Number(e.target.value))}
                      className="w-20 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-slate-900 font-mono text-xs font-semibold focus:border-blue-600 focus:outline-none"
                    />
                    <span className="text-slate-400 text-xs ml-1">%</span>
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      min="1"
                      value={r.refresh_window_days}
                      onChange={(e) => handleRuleChange(idx, 'refresh_window_days', Number(e.target.value))}
                      className="w-20 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-slate-900 font-mono text-xs font-semibold focus:border-blue-600 focus:outline-none"
                    />
                    <span className="text-slate-400 text-xs ml-1">dias</span>
                  </td>
                </tr>
              ))}
              {rules.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-400 font-medium text-xs">
                    Nenhuma regra cadastrada nesta tabela de preços.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// =========================================================================
// TAB 4: CARTEIRAS & LEDGER CONTÁBIL (BRL)
// =========================================================================
function WalletsTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [wallets, setWallets] = useState<AdminWallet[]>([]);
  const [selectedTenant, setSelectedTenant] = useState<string>('');
  const [transactions, setTransactions] = useState<DjangoCreditTransaction[]>([]);
  const [loadingTx, setLoadingTx] = useState(false);
  const [showInjectModal, setShowInjectModal] = useState(false);
  const [injectTenantId, setInjectTenantId] = useState('');
  const [injectAmount, setInjectAmount] = useState(1000);
  const [injectReason, setInjectReason] = useState('');

  const loadWallets = useCallback(async () => {
    try {
      const res = await api.adminWallets();
      const list = ensureArray<AdminWallet>(res);
      setWallets(list);
      if (list.length && !selectedTenant) {
        setSelectedTenant(list[0].tenant);
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
        setTransactions(ensureArray<DjangoCreditTransaction>(res));
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
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
        {wallets.map((w) => {
          const isSelected = selectedTenant === w.tenant;
          return (
            <div
              key={w.id}
              onClick={() => setSelectedTenant(w.tenant)}
              className={`p-4 rounded-[12px] border transition-all cursor-pointer shadow-xs ${
                isSelected
                  ? 'bg-blue-50/50 border-blue-500 shadow-sm'
                  : 'bg-white border-slate-200/90 hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 text-xs">{w.tenant_name}</span>
                <span className="font-extrabold text-[10px] text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full uppercase">
                  {w.currency || 'BRL'}
                </span>
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <div>
                  <span className="text-2xl font-extrabold text-slate-900 tracking-tight">
                    {new Intl.NumberFormat('pt-BR').format(w.balance)}
                  </span>
                  <span className="text-xs text-slate-500 font-semibold ml-1.5">créditos</span>
                  <div className="text-[11px] text-emerald-700 font-bold mt-0.5">
                    Equiv. R$ {(w.balance / 100).toFixed(2)}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setInjectTenantId(w.tenant);
                    setShowInjectModal(true);
                  }}
                  className="px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-[11px] font-bold transition-all cursor-pointer shadow-xs"
                >
                  + Injetar
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Ledger Transactions for Selected Tenant */}
      <div className="bg-white border border-slate-200/90 rounded-[12px] overflow-hidden shadow-xs space-y-0">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 bg-slate-50/70">
          <span className="text-xs font-bold text-slate-700">
            Trilha de Auditoria Imutável (Ledger de Dupla Entrada)
          </span>
          <span className="text-xs font-bold text-slate-500">
            {transactions.length} lançamentos encontrados
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/40 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Variação</th>
                <th className="px-4 py-3">Saldo Resultante</th>
                <th className="px-4 py-3">Referência / Justificativa</th>
                <th className="px-4 py-3">Data & Hora</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="px-4 py-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                        tx.transaction_type === 'DEPOSIT'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : tx.transaction_type === 'CAPTURE'
                          ? 'bg-blue-50 text-blue-700 border border-blue-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {tx.transaction_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-extrabold text-slate-900">
                    {tx.amount > 0 ? `+${tx.amount}` : tx.amount}
                  </td>
                  <td className="px-4 py-3 font-bold text-slate-600 text-[11px]">{tx.balance_after}</td>
                  <td className="px-4 py-3 text-slate-700 text-[11px] truncate max-w-xs font-medium">
                    {tx.reference_id}
                  </td>
                  <td className="px-4 py-3 text-slate-500 font-medium text-[11px]">
                    {new Date(tx.created_at).toLocaleString('pt-BR')}
                  </td>
                </tr>
              ))}
              {transactions.length === 0 && !loadingTx && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-400 font-medium text-xs">
                    Nenhum lançamento no ledger para o workspace selecionado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Credit Injection Modal */}
      {showInjectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md rounded-[12px] border border-slate-200 bg-white p-6 shadow-2xl space-y-4 text-slate-900">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-extrabold text-slate-900">Injetar Crédito Manual com Auditoria</h3>
              <button onClick={() => setShowInjectModal(false)} className="text-slate-400 hover:text-slate-600 font-bold cursor-pointer">
                ✕
              </button>
            </div>
            <form onSubmit={handleInject} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-700 font-bold mb-1">Quantidade de Créditos (BRL)</label>
                <input
                  type="number"
                  min="1"
                  required
                  value={injectAmount}
                  onChange={(e) => setInjectAmount(Number(e.target.value))}
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 font-mono text-sm font-bold focus:border-blue-600 focus:outline-none"
                />
                <span className="text-[11px] text-emerald-700 font-semibold mt-1 block">
                  Equivalente contábil: R$ {(injectAmount / 100).toFixed(2)}
                </span>
              </div>
              <div>
                <label className="block text-slate-700 font-bold mb-1">
                  Justificativa Obrigatória (Auditoria Contábil LGPD)
                </label>
                <textarea
                  required
                  rows={3}
                  value={injectReason}
                  onChange={(e) => setInjectReason(e.target.value)}
                  placeholder="Ex: Pagamento Pix recebido via fatura #9012 — contrato anual."
                  className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs font-medium focus:border-blue-600 focus:outline-none"
                />
              </div>
              <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowInjectModal(false)}
                  className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50 font-bold cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer shadow-xs"
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
      setBatches(ensureArray<AdminBatch>(bRes));
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

  const queuesList = ensureArray<{ queue_name: string; messages_count: number }>(queuesData?.queues);

  return (
    <div className="space-y-4">
      {/* Celery Telemetry Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
        <div className="p-4 rounded-[12px] border border-slate-200/90 bg-white shadow-xs">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Workers Ativos</span>
          <span className="text-2xl font-extrabold text-slate-900 mt-1 block">
            {queuesData?.active_workers ?? 1}
          </span>
        </div>
        <div className="p-4 rounded-[12px] border border-slate-200/90 bg-white shadow-xs">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">Throughput / Hora</span>
          <span className="text-2xl font-extrabold text-emerald-700 mt-1 block">
            {queuesData?.total_throughput_hour ?? 0}
          </span>
        </div>
        <div className="p-4 rounded-[12px] border border-slate-200/90 bg-white shadow-xs col-span-2">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
            Filas RabbitMQ & Mensagens Pendentes
          </span>
          <div className="flex flex-wrap gap-2">
            {queuesList.map((q) => (
              <span
                key={q.queue_name}
                className="px-2.5 py-1 rounded-lg bg-slate-50 border border-slate-200 text-xs font-semibold text-slate-700"
              >
                {q.queue_name}: <strong className="text-slate-900 font-extrabold">{q.messages_count}</strong> msgs
              </span>
            ))}
            {queuesList.length === 0 && (
              <span className="text-xs text-slate-400">Filas ociosas (sem mensagens pendentes)</span>
            )}
          </div>
        </div>
      </div>

      {/* Global Batches Table */}
      <div className="bg-white border border-slate-200/90 rounded-[12px] overflow-hidden shadow-xs">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                <th className="px-4 py-3">Lote</th>
                <th className="px-4 py-3">Workspace</th>
                <th className="px-4 py-3">Progresso Linhas</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Criado em</th>
                <th className="px-4 py-3 text-right">Ações de Controle</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-xs">
              {batches.map((b) => {
                const percent = b.total_rows > 0 ? Math.round((b.processed_rows / b.total_rows) * 100) : 0;
                return (
                  <tr key={b.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-4 py-3">
                      <div className="font-bold text-slate-900">{b.name}</div>
                      <div className="font-mono text-[10px] text-slate-400 font-semibold">{b.source_type}</div>
                    </td>
                    <td className="px-4 py-3 font-semibold text-slate-700">{b.tenant_name}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-24 h-2 rounded-full bg-slate-100 overflow-hidden">
                          <div
                            className="h-full bg-blue-600 rounded-full transition-all"
                            style={{ width: `${percent}%` }}
                          />
                        </div>
                        <span className="text-[11px] font-bold text-slate-700">
                          {b.processed_rows} / {b.total_rows} ({percent}%)
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold ${
                          b.status === 'SUCCEEDED'
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : b.status === 'PROCESSING'
                            ? 'bg-blue-50 text-blue-700 border border-blue-200 animate-pulse'
                            : b.status === 'PAUSED'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500 font-medium text-[11px]">
                      {new Date(b.created_at).toLocaleString('pt-BR')}
                    </td>
                    <td className="px-4 py-3 text-right space-x-1.5">
                      {b.status === 'PROCESSING' && (
                        <button
                          onClick={() => handleAction(b.id, 'pause')}
                          className="px-2.5 py-1 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] font-bold hover:bg-amber-100 transition-all cursor-pointer"
                        >
                          Pausar
                        </button>
                      )}
                      {b.status === 'PAUSED' && (
                        <button
                          onClick={() => handleAction(b.id, 'resume')}
                          className="px-2.5 py-1 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 text-[11px] font-bold hover:bg-blue-100 transition-all cursor-pointer"
                        >
                          Retomar
                        </button>
                      )}
                      {['PROCESSING', 'PAUSED', 'PENDING'].includes(b.status) && (
                        <button
                          onClick={() => handleAction(b.id, 'cancel')}
                          className="px-2.5 py-1 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-[11px] font-bold hover:bg-rose-100 transition-all cursor-pointer"
                        >
                          Cancelar
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {batches.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-400 font-medium text-xs">
                    Nenhum lote assíncrono encontrado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// =========================================================================
// TAB 6: PROVEDORES & ORÇAMENTO BRL
// =========================================================================
function ProvidersTab({
  onError,
  onSuccess,
}: {
  onError: (msg: string) => void;
  onSuccess: (msg: string) => void;
}) {
  const [providersData, setProvidersData] = useState<AdminProvidersData | null>(null);
  const [dailyLimitBrl, setDailyLimitBrl] = useState(500);
  const [circuitRate, setCircuitRate] = useState(0.15);
  const [saving, setSaving] = useState(false);

  const loadProviders = useCallback(async () => {
    try {
      const data = await api.adminProviders();
      setProvidersData(data);
      if (data.budget) {
        setDailyLimitBrl(data.budget.daily_limit_brl ?? Number(data.budget.daily_limit_usd || 100) * 5.0);
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
        daily_limit_brl: dailyLimitBrl,
        daily_limit_usd: Math.round(dailyLimitBrl / 5.0),
        circuit_breaker_rate: circuitRate,
      });
      onSuccess('Orçamento diário em Reais (BRL) e circuit breaker salvos com sucesso.');
      loadProviders();
    } catch {
      onError('Falha ao salvar limites de orçamento.');
    } finally {
      setSaving(false);
    }
  };

  const providersList = ensureArray<{
    name: string;
    is_active?: boolean;
    status?: string;
    latency_ms?: number;
    success_rate?: number;
    success_rate_24h?: number;
  }>(providersData?.providers);

  return (
    <div className="space-y-4">
      {/* Providers Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3.5">
        {providersList.map((p) => {
          const isOnline = p.status === 'ONLINE' || p.is_active === true;
          const rate = p.success_rate_24h !== undefined ? (p.success_rate_24h * 100).toFixed(1) : (p.success_rate ?? 99.0).toFixed(1);
          return (
            <div key={p.name} className="p-4 rounded-[12px] border border-slate-200/90 bg-white shadow-xs space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 text-xs">{p.name}</span>
                <span
                  className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold ${
                    isOnline
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-rose-50 text-rose-700 border border-rose-200'
                  }`}
                >
                  {isOnline ? 'ONLINE' : 'OFFLINE'}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] border-t border-slate-100 pt-2 font-medium">
                <div>
                  <span className="text-[10px] block text-slate-400 font-bold uppercase tracking-wider">Latência</span>
                  <span className="text-slate-900 font-extrabold">{p.latency_ms ?? 350} ms</span>
                </div>
                <div>
                  <span className="text-[10px] block text-slate-400 font-bold uppercase tracking-wider">Taxa 24h</span>
                  <span className="text-emerald-700 font-extrabold">{rate}%</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Budget & Circuit Breaker Settings in BRL */}
      <div className="rounded-[12px] border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
        <div>
          <h3 className="text-sm font-extrabold text-slate-900 tracking-tight">
            Controle de Orçamento Diário (R$ BRL) & Circuit Breaker
          </h3>
          <p className="text-xs text-slate-500 font-medium mt-0.5">
            Interrompe automaticamente chamadas de enriquecimento aos parceiros externos caso o limite de custo diário ou taxa de falhas seja violado.
          </p>
        </div>

        <form onSubmit={handleSaveBudget} className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs items-end">
          <div>
            <label className="block text-slate-700 font-bold mb-1.5">
              Limite Diário Global (R$ BRL)
            </label>
            <div className="flex items-center gap-2">
              <span className="text-slate-500 font-bold text-sm">R$</span>
              <input
                type="number"
                step="1"
                min="0"
                value={dailyLimitBrl}
                onChange={(e) => setDailyLimitBrl(Number(e.target.value))}
                className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 font-mono text-sm font-bold focus:border-blue-600 focus:outline-none"
              />
            </div>
          </div>
          <div>
            <label className="block text-slate-700 font-bold mb-1.5">
              Circuit Breaker - Taxa de Erro (0.01 a 1.0)
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              max="1"
              value={circuitRate}
              onChange={(e) => setCircuitRate(Number(e.target.value))}
              className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 font-mono text-xs font-bold focus:border-blue-600 focus:outline-none"
            />
          </div>
          <div>
            <button
              type="submit"
              disabled={saving}
              className="w-full px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer text-xs shadow-xs"
            >
              {saving ? 'Gravando...' : 'Aplicar Limites de Custos BRL'}
            </button>
          </div>
        </form>

        <div className="pt-3 border-t border-slate-100 flex items-center gap-4 text-xs font-medium text-slate-600">
          <span>Consumo de Hoje: <strong className="text-slate-900 font-extrabold">R$ {Number(providersData?.budget?.current_spend_brl ?? ((providersData?.budget?.current_spend_usd ?? 0) * 5)).toFixed(2)}</strong></span>
          <span>·</span>
          <span>Status do Circuit Breaker: <strong className="text-emerald-700 font-extrabold">Armado / Normal</strong></span>
        </div>
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
      setSuppressions(ensureArray<AdminSuppression>(sRes));
      setAuditLogs(ensureArray<AdminAuditLog>(aRes));
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
      <div className="flex items-center gap-2 border-b border-slate-200 pb-3">
        <button
          onClick={() => setActiveSubTab('suppression')}
          className={`px-3.5 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all ${
            activeSubTab === 'suppression' ? 'bg-blue-600 text-white shadow-xs' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
          }`}
        >
          Lista Negra de Supressão (Opt-Out LGPD) ({suppressions.length})
        </button>
        <button
          onClick={() => setActiveSubTab('audit')}
          className={`px-3.5 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all ${
            activeSubTab === 'audit' ? 'bg-blue-600 text-white shadow-xs' : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-50'
          }`}
        >
          Logs de Auditoria de Segurança ({auditLogs.length})
        </button>
      </div>

      {activeSubTab === 'suppression' ? (
        <div className="space-y-4">
          <form
            onSubmit={handleAddSuppression}
            className="p-5 rounded-[12px] border border-slate-200/90 bg-white shadow-xs grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs items-end"
          >
            <div>
              <label className="block text-slate-700 font-bold mb-1">Tipo</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as 'CNPJ' | 'EMAIL' | 'DOMAIN')}
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 text-xs font-medium focus:border-blue-600 focus:outline-none"
              >
                <option value="EMAIL">EMAIL</option>
                <option value="CNPJ">CNPJ</option>
                <option value="DOMAIN">DOMAIN</option>
              </select>
            </div>
            <div>
              <label className="block text-slate-700 font-bold mb-1">Identificador Alvo</label>
              <input
                type="text"
                required
                value={val}
                onChange={(e) => setVal(e.target.value)}
                placeholder="email@empresa.com ou CNPJ"
                className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs font-medium focus:border-blue-600 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-slate-700 font-bold mb-1">Motivo Legal (LGPD)</label>
              <input
                type="text"
                required
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Titular solicitou exclusão"
                className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs font-medium focus:border-blue-600 focus:outline-none"
              />
            </div>
            <div>
              <button
                type="submit"
                className="w-full px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold cursor-pointer text-xs shadow-xs"
              >
                Bloquear Identificador
              </button>
            </div>
          </form>

          <div className="bg-white border border-slate-200/90 rounded-[12px] overflow-hidden shadow-xs">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    <th className="px-4 py-3">Tipo</th>
                    <th className="px-4 py-3">Identificador</th>
                    <th className="px-4 py-3">Justificativa</th>
                    <th className="px-4 py-3">Data</th>
                    <th className="px-4 py-3 text-right">Ação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {suppressions.map((s) => (
                    <tr key={s.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200 text-slate-700 font-extrabold text-[10px]">
                          {s.identifier_type}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-mono font-bold text-slate-900 text-[11px]">{s.identifier_value}</td>
                      <td className="px-4 py-3 text-slate-600 font-medium text-xs">{s.reason}</td>
                      <td className="px-4 py-3 text-slate-500 font-medium text-[11px]">
                        {new Date(s.created_at).toLocaleDateString('pt-BR')}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleDeleteSuppression(s.id)}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all cursor-pointer"
                          title="Remover supressão"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {suppressions.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-slate-400 font-medium text-xs">
                        Nenhum registro na lista negra de supressão.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-slate-200/90 rounded-[12px] overflow-hidden shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Ação</th>
                  <th className="px-4 py-3">Entidade</th>
                  <th className="px-4 py-3">IP / Origem</th>
                  <th className="px-4 py-3">Metadados</th>
                  <th className="px-4 py-3">Data & Hora</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs font-mono">
                {auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-4 py-3 text-blue-700 font-extrabold text-[11px]">{log.action}</td>
                    <td className="px-4 py-3 text-slate-800 font-bold text-[11px]">{log.entity_type}</td>
                    <td className="px-4 py-3 text-slate-500 text-[11px]">{log.ip_address || '-'}</td>
                    <td className="px-4 py-3 text-slate-600 text-[10px] truncate max-w-xs">
                      {JSON.stringify(log.metadata)}
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-[11px]">
                      {new Date(log.created_at).toLocaleString('pt-BR')}
                    </td>
                  </tr>
                ))}
                {auditLogs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-400 font-medium text-xs font-sans">
                      Nenhum log de auditoria recente.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
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
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
      {/* White-Label Customization Form */}
      <div className="rounded-[12px] border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Palette className="w-5 h-5 text-blue-600" />
          <h3 className="text-sm font-extrabold text-slate-900">
            Personalização de Marca White-Label
          </h3>
        </div>

        <form onSubmit={handleSaveBranding} className="space-y-3.5 text-xs">
          <div>
            <label className="block text-slate-700 font-bold mb-1">Nome da Plataforma</label>
            <input
              type="text"
              value={platformName}
              onChange={(e) => setPlatformName(e.target.value)}
              placeholder="Ex: LeadStream Pro"
              className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 font-medium text-xs focus:border-blue-600 focus:outline-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-2.5">
            <div>
              <label className="block text-slate-700 font-bold mb-1">Logo URL (Tema Escuro)</label>
              <input
                type="text"
                value={logoDark}
                onChange={(e) => setLogoDark(e.target.value)}
                placeholder="https://.../logo-dark.svg"
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-slate-900 text-[11px] font-mono focus:border-blue-600 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-slate-700 font-bold mb-1">Logo URL (Tema Claro)</label>
              <input
                type="text"
                value={logoLight}
                onChange={(e) => setLogoLight(e.target.value)}
                placeholder="https://.../logo-light.svg"
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-slate-900 text-[11px] font-mono focus:border-blue-600 focus:outline-none"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2.5">
            <div>
              <label className="block text-slate-700 font-bold text-[11px] mb-1">Favicon URL</label>
              <input
                type="text"
                value={faviconUrl}
                onChange={(e) => setFaviconUrl(e.target.value)}
                placeholder="https://.../favicon.ico"
                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-slate-900 text-[11px] font-mono focus:border-blue-600 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-slate-700 font-bold text-[11px] mb-1">Cor Accent</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={accentColor}
                  onChange={(e) => setAccentColor(e.target.value)}
                  className="w-8 h-8 rounded-lg border border-slate-200 cursor-pointer"
                />
                <input
                  type="text"
                  value={accentColor}
                  onChange={(e) => setAccentColor(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-slate-900 font-mono text-[11px]"
                />
              </div>
            </div>
            <div>
              <label className="block text-slate-700 font-bold text-[11px] mb-1">Cor Primária</label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-8 h-8 rounded-lg border border-slate-200 cursor-pointer"
                />
                <input
                  type="text"
                  value={primaryColor}
                  onChange={(e) => setPrimaryColor(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 bg-white px-2.5 py-1 text-slate-900 font-mono text-[11px]"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-slate-700 font-bold mb-1">Email de Suporte</label>
            <input
              type="email"
              value={supportEmail}
              onChange={(e) => setSupportEmail(e.target.value)}
              placeholder="suporte@suamarca.com.br"
              className="w-full rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 text-xs focus:border-blue-600 focus:outline-none font-medium"
            />
          </div>

          <button
            type="submit"
            disabled={savingBrand}
            className="w-full px-4 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold cursor-pointer text-xs shadow-xs"
          >
            {savingBrand ? 'Atualizando Marca...' : 'Salvar Configurações de Marca'}
          </button>
        </form>
      </div>

      {/* SMTP Zero-Bounce Engine Interactive Probe */}
      <div className="rounded-[12px] border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
          <Mail className="w-5 h-5 text-blue-600" />
          <h3 className="text-sm font-extrabold text-slate-900">
            Motor Zero-Bounce (Probe SMTP RFC 5321)
          </h3>
        </div>

        <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-200 space-y-1 text-xs text-slate-600 font-medium">
          <div>
            HELO Domain: <strong className="text-slate-900 font-mono">{smtpConfig?.helo_domain || 'mx.leadstream.io'}</strong>
          </div>
          <div>
            Timeout Conexão: <strong className="text-slate-900 font-mono">{smtpConfig?.timeout_seconds || 8}s</strong> ·
            Estratégia Catch-All:{' '}
            <strong className="text-blue-700 font-bold">{smtpConfig?.catch_all_strategy || 'PROBE'}</strong>
          </div>
        </div>

        <form onSubmit={handleProbe} className="space-y-2.5">
          <label className="block text-slate-700 font-bold text-xs">Teste Interativo de Validação Direta</label>
          <div className="flex gap-2">
            <input
              type="email"
              required
              value={probeEmail}
              onChange={(e) => setProbeEmail(e.target.value)}
              placeholder="contato@empresa.com.br"
              className="flex-1 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-slate-900 font-mono text-xs focus:border-blue-600 focus:outline-none"
            />
            <button
              type="submit"
              disabled={probeLoading}
              className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs cursor-pointer disabled:opacity-50 flex items-center gap-1.5 shadow-xs"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{probeLoading ? 'Sondando...' : 'Sondar MX'}</span>
            </button>
          </div>
        </form>

        {probeResult && (
          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-2 text-xs font-mono">
            <div className="flex items-center justify-between">
              <span className="text-slate-800 font-bold">{probeResult.email}</span>
              <span
                className={`px-2.5 py-0.5 rounded-full text-[10px] font-extrabold ${
                  probeResult.status === 'DELIVERABLE'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : probeResult.status === 'CATCH_ALL'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-rose-50 text-rose-700 border border-rose-200'
                }`}
              >
                {probeResult.status}
              </span>
            </div>
            <div className="text-[11px] text-slate-600 space-y-1 font-medium">
              <div>Host MX: <strong>{probeResult.mx_host || '-'}</strong></div>
              <div>Código SMTP: <strong>{probeResult.smtp_code || '-'}</strong></div>
              <div>Latência de Handshake: <strong>{probeResult.latency_ms} ms</strong></div>
              {probeResult.raw_response && (
                <div className="p-2.5 rounded-lg bg-white text-[10px] text-slate-700 border border-slate-200 break-all">
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
