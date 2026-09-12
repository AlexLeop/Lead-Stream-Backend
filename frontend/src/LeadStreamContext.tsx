import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, getStoredTokens, setStoredTokens } from './api';
import type {
  Activity,
  CampaignList,
  CreateDatasetInput,
  CreateListInput,
  CRMConnection,
  DjangoCreditWallet,
  DjangoTenant,
  DjangoUser,
  ImportPayload,
  ImportResult,
  Lead,
  LeadSet,
  WorkspaceSummary,
} from './types';

interface LeadStreamContextValue {
  isAuthenticated: boolean;
  user: DjangoUser | null;
  tenant: DjangoTenant | null;
  wallet: DjangoCreditWallet | null;
  leads: Lead[];
  datasets: LeadSet[];
  lists: CampaignList[];
  activities: Activity[];
  crmConnections: CRMConnection[];
  workspace: WorkspaceSummary;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  refreshWorkspace: () => Promise<void>;
  refreshWallet: () => Promise<void>;
  createDataset: (input: CreateDatasetInput) => Promise<LeadSet>;
  deleteDataset: (id: string) => Promise<void>;
  importRecords: (input: ImportPayload) => Promise<ImportResult>;
  createList: (input: CreateListInput) => Promise<CampaignList>;
  archiveList: (id: string) => Promise<CampaignList>;
  addLeadsToList: (id: string, leadIds: string[]) => Promise<CampaignList>;
  revealPhone: (id: string) => Promise<Lead>;
}

const emptyWorkspace: WorkspaceSummary = { companies: 0, contacts: 0, datasets: 0, lists: 0 };
const LeadStreamContext = createContext<LeadStreamContextValue | null>(null);

export function LeadStreamProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(() => !!getStoredTokens());
  const [user, setUser] = useState<DjangoUser | null>(null);
  const [tenant, setTenant] = useState<DjangoTenant | null>(null);
  const [wallet, setWallet] = useState<DjangoCreditWallet | null>(null);

  const [leads, setLeads] = useState<Lead[]>([]);
  const [datasets, setDatasets] = useState<LeadSet[]>([]);
  const [lists, setLists] = useState<CampaignList[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [crmConnections, setCrmConnections] = useState<CRMConnection[]>([]);
  const [workspace, setWorkspace] = useState<WorkspaceSummary>(emptyWorkspace);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const logout = useCallback(() => {
    setStoredTokens(null);
    setIsAuthenticated(false);
    setUser(null);
    setTenant(null);
    setWallet(null);
  }, []);

  const refreshWallet = useCallback(async () => {
    try {
      const data = await api.wallet();
      setWallet(data);
    } catch {
      // Carteira indisponível temporariamente
    }
  }, []);

  const loadAuthUser = useCallback(async () => {
    if (!getStoredTokens()) {
      setIsAuthenticated(false);
      setLoading(false);
      return;
    }
    try {
      const me = await api.me();
      if (me?.user) {
        setUser(me.user);
      }
      const activeTenant = me?.active_workspace || me?.tenant || null;
      if (activeTenant) {
        setTenant(activeTenant);
      }
      setIsAuthenticated(true);
      await refreshWallet().catch(() => {});
    } catch (err) {
      console.warn('Não foi possível obter dados completos do perfil, mantendo sessão ativa:', err);
      // Mantém a sessão autenticada com os tokens armazenados
      setIsAuthenticated(true);
    } finally {
      setLoading(false);
    }
  }, [refreshWallet]);

  const login = useCallback(
    async (username: string, password: string) => {
      await api.login(username, password);
      setIsAuthenticated(true);
      await loadAuthUser();
    },
    [loadAuthUser],
  );

  const refresh = useCallback(async () => {
    if (!getStoredTokens()) return;
    setError(null);
    try {
      await Promise.allSettled([
        refreshWallet(),
        api.leads().then(setLeads),
        api.datasets().then(setDatasets),
        api.lists().then(setLists),
        api.activities().then(setActivities),
        api.crmConnections().then(setCrmConnections),
        api.workspace().then(setWorkspace),
      ]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Falha ao sincronizar dados da plataforma.');
    }
  }, [refreshWallet]);

  useEffect(() => {
    loadAuthUser();

    const handleUnauthorized = () => logout();
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [loadAuthUser, logout]);

  useEffect(() => {
    if (isAuthenticated) {
      void refresh();
    }
  }, [isAuthenticated, refresh]);

  const mutations = useMemo(
    () => ({
      async createDataset(input: CreateDatasetInput) {
        const result = await api.createDataset(input);
        await refresh();
        return result;
      },
      async deleteDataset(id: string) {
        await api.deleteDataset(id);
        await refresh();
      },
      async importRecords(input: ImportPayload) {
        const result = await api.importRecords(input);
        await refresh();
        return result;
      },
      async createList(input: CreateListInput) {
        const result = await api.createList(input);
        await refresh();
        return result;
      },
      async archiveList(id: string) {
        const result = await api.archiveList(id);
        await refresh();
        return result;
      },
      async addLeadsToList(id: string, leadIds: string[]) {
        const result = await api.addLeadsToList(id, leadIds);
        await refresh();
        return result;
      },
      async revealPhone(id: string) {
        const result = await api.revealPhone(id);
        setLeads((current) => current.map((lead) => (lead.id === id ? result : lead)));
        return result;
      },
    }),
    [refresh],
  );

  const value = useMemo<LeadStreamContextValue>(
    () => ({
      isAuthenticated,
      user,
      tenant,
      wallet,
      leads,
      datasets,
      lists,
      activities,
      crmConnections,
      workspace,
      loading,
      error,
      login,
      logout,
      refresh,
      refreshWorkspace: refresh,
      refreshWallet,
      ...mutations,
    }),
    [activities, crmConnections, datasets, error, isAuthenticated, leads, lists, loading, login, logout, mutations, refresh, refreshWallet, tenant, user, wallet, workspace],
  );

  return <LeadStreamContext.Provider value={value}>{children}</LeadStreamContext.Provider>;
}

export function useLeadStream() {
  const context = useContext(LeadStreamContext);
  if (!context) throw new Error('useLeadStream deve ser usado dentro de LeadStreamProvider.');
  return context;
}
