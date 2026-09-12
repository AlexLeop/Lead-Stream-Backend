import { useEffect, useRef, useState, type ComponentType } from 'react';
import {
  Activity,
  FolderKanban,
  LayoutDashboard,
  ListOrdered,
  LogOut,
  MailCheck,
  Menu,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Wallet as WalletIcon,
  X,
} from 'lucide-react';
import Dashboard from './Dashboard';
import SearchPage from './Search';
import ListsPage from './Lists';
import DatasetsPage from './Datasets';
import DataHealth from './DataHealth';
import Enrichment from './Enrichment';
import { Wallet } from './Wallet';
import { EmailValidation } from './EmailValidation';
import AdminCenter from './AdminCenter';
import { useLeadStream } from '../LeadStreamContext';
import { useBranding } from '../components/BrandingProvider';

interface AppShellProps {
  currentRoute: string;
  onNavigate: (route: string) => void;
}

interface NavItem {
  id: string;
  label: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
}

const navigation: Array<{ label: string; items: NavItem[] }> = [
  {
    label: 'Operações e Lotes',
    items: [
      { id: 'dashboard', label: 'Painel Geral', description: 'Visão executiva', icon: LayoutDashboard },
      { id: 'enrichment', label: 'Lotes de Enriquecimento', description: 'Processamento assíncrono', icon: Sparkles },
      { id: 'wallet', label: 'Carteira & Ledger', description: 'Custódia e Pay-per-Value', icon: WalletIcon },
      { id: 'validation', label: 'Validação Zero-Bounce', description: 'Probe SMTP profundo', icon: MailCheck },
    ],
  },
  {
    label: 'Inteligência & Contas',
    items: [
      { id: 'search', label: 'Mercado & Contas', description: 'Descoberta de empresas', icon: Search },
      { id: 'datasets', label: 'Bases de Dados', description: 'Segmentos e arquivos', icon: FolderKanban },
      { id: 'lists', label: 'Listas Comerciais', description: 'Exportação e CRM', icon: ListOrdered },
      { id: 'data-health', label: 'Qualidade da Base', description: 'Confiabilidade e evidência', icon: ShieldCheck },
    ],
  },
];

const pageTitles: Record<string, { title: string; description: string }> = {
  dashboard: { title: 'Painel Geral', description: 'Visão executiva de processamento, taxas de acerto e economia por estornos.' },
  enrichment: { title: 'Lotes de Enriquecimento', description: 'Processamento assíncrono em chunks de alta escala com controle de custos.' },
  wallet: { title: 'Carteira & Ledger Contábil', description: 'Registro imutável de dupla entrada com garantia de estorno de leads ausentes.' },
  validation: { title: 'Validação Zero-Bounce', description: 'Handshake SMTP em tempo real no protocolo RFC 5321 com probe catch-all.' },
  search: { title: 'Mercado & Contas', description: 'Consulte registros empresariais e decisores atribuíveis com evidências.' },
  datasets: { title: 'Bases de Dados', description: 'Arquivos brutos, snapshots e segmentações.' },
  lists: { title: 'Listas Comerciais', description: 'Conjuntos selecionados para ativação em vendas e CRM.' },
  'data-health': { title: 'Qualidade da Base', description: 'Indicadores de precisão, frescor e cobertura cadastral.' },
  admin: {
    title: 'Administração do Sistema',
    description: 'Gerenciamento de workspaces, planos de preços, usuários, provedores e marca.',
  },
};

function BrandMark({ logoUrl, platformName }: { logoUrl?: string; platformName?: string }) {
  if (logoUrl) {
    return (
      <img
        src={logoUrl}
        alt={platformName || 'LeadStream'}
        className="h-7 w-7 rounded-lg object-contain p-0.5 border border-slate-200 bg-white"
      />
    );
  }
  const initials = (platformName || 'LeadStream')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();
  return (
    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-xs font-mono font-bold text-white shadow-xs">
      {initials || 'LS'}
    </div>
  );
}

export default function AppShell({ currentRoute, onNavigate }: AppShellProps) {
  const [selectedSetFilterId, setSelectedSetFilterId] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileMenuCloseRef = useRef<HTMLButtonElement>(null);
  const { user, tenant, wallet, loading, error, refresh, logout } = useLeadStream();
  const { branding } = useBranding();
  const page = pageTitles[currentRoute] ?? pageTitles.dashboard;

  useEffect(() => {
    if (!mobileNavOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    mobileMenuCloseRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setMobileNavOpen(false);
        mobileMenuButtonRef.current?.focus();
      }
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [mobileNavOpen]);

  const navigate = (route: string) => {
    setMobileNavOpen(false);
    onNavigate(route);
  };

  const handleNavigateToSearchWithSet = (setId: string) => {
    setSelectedSetFilterId(setId);
    navigate('search');
  };

  const formatCredits = (val?: number) => {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('pt-BR').format(val);
  };

  const sidebar = (
    <>
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5 bg-white">
        <button
          onClick={() => navigate('dashboard')}
          className="flex items-center gap-3 text-left focus-visible:outline-none cursor-pointer"
          aria-label="Ir para o painel geral"
        >
          <BrandMark logoUrl={branding.logo_url_light || branding.logo_url_dark} platformName={branding.platform_name} />
          <span>
            <span className="block text-sm font-bold tracking-tight text-slate-900">
              {branding.platform_name || 'LeadStream'}
            </span>
            <span className="block text-[10px] font-mono text-slate-500 uppercase tracking-wider">
              Data Intelligence
            </span>
          </span>
        </button>
        <button
          ref={mobileMenuCloseRef}
          onClick={() => setMobileNavOpen(false)}
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700 lg:hidden cursor-pointer"
          aria-label="Fechar navegação"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav Groups */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6" aria-label="Navegação principal">
        {navigation.map((group) => (
          <div key={group.label}>
            <p className="mb-2 px-3 text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">
              {group.label}
            </p>
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = currentRoute === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => navigate(item.id)}
                    aria-current={active ? 'page' : undefined}
                    className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors cursor-pointer ${
                      active
                        ? 'bg-blue-50 text-blue-700 border border-blue-200 font-bold shadow-2xs'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border border-transparent'
                    }`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
                    <span className="min-w-0">
                      <span className="block text-xs font-semibold">{item.label}</span>
                      <span className={`block truncate text-[10px] ${active ? 'text-blue-600/80' : 'text-slate-400'}`}>
                        {item.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        {/* Master Administration Section (Superadmin & Staff) */}
        {(user?.is_superuser || user?.is_staff) && (
          <div className="pt-2 border-t border-slate-200">
            <p className="mb-2 px-3 text-[10px] font-mono font-bold text-slate-400 uppercase tracking-wider">
              Sistema & Gestão
            </p>
            <div className="space-y-1">
              <button
                onClick={() => navigate('admin')}
                aria-current={currentRoute === 'admin' ? 'page' : undefined}
                className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors cursor-pointer ${
                  currentRoute === 'admin'
                    ? 'bg-blue-50 text-blue-700 border border-blue-200 font-bold shadow-2xs'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 border border-transparent'
                }`}
              >
                <ShieldCheck
                  className={`h-4 w-4 shrink-0 ${
                    currentRoute === 'admin' ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'
                  }`}
                />
                <span className="min-w-0">
                  <span className="block text-xs font-semibold">Administração</span>
                  <span className={`block truncate text-[10px] ${currentRoute === 'admin' ? 'text-blue-600/80' : 'text-slate-400'}`}>
                    Workspaces, planos e marca
                  </span>
                </span>
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* Bottom Tenant & User Footer */}
      <div className="border-t border-slate-200 p-3 bg-slate-50/70 space-y-2">
        <div className="px-2 py-1.5 rounded-lg bg-white border border-slate-200 flex items-center justify-between text-[11px] font-mono shadow-2xs">
          <span className="text-slate-700 truncate font-medium">{tenant?.name || 'Workspace Padrão'}</span>
          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-[10px] text-slate-600 font-semibold">
            {tenant?.slug || 'internal'}
          </span>
        </div>
        <div className="flex items-center justify-between px-2 text-xs">
          <span className="text-slate-700 truncate font-sans text-[11px] font-medium">
            {user?.username || 'Administrador'}
          </span>
          <button
            onClick={logout}
            title="Encerrar Sessão"
            className="text-slate-400 hover:text-rose-600 transition-colors p-1 cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Desktop Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[250px] flex-col bg-white border-r border-slate-200 lg:flex">
        {sidebar}
      </aside>

      {/* Mobile Drawer */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navegação principal">
          <div
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-xs"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative flex h-full w-[280px] flex-col bg-white border-r border-slate-200">{sidebar}</aside>
        </div>
      )}

      {/* Main Content Area */}
      <div className="lg:pl-[250px]">
        {/* Top Sticky Header */}
        <header className="sticky top-0 z-20 flex min-h-[64px] items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur-md sm:px-6 lg:px-8 shadow-2xs">
          <div className="flex min-w-0 items-center gap-3">
            <button
              ref={mobileMenuButtonRef}
              onClick={() => setMobileNavOpen(true)}
              className="rounded-lg border border-slate-200 p-2 text-slate-600 hover:text-slate-900 lg:hidden cursor-pointer"
              aria-label="Abrir navegação"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-bold tracking-tight text-slate-900">{page.title}</h1>
              <p className="hidden truncate text-[11px] text-slate-500 sm:block">{page.description}</p>
            </div>
          </div>

          {/* Right Header: Wallet Balance Pill & Status */}
          <div className="flex items-center gap-3">
            {/* Live Wallet Balance Pill */}
            <button
              onClick={() => navigate('wallet')}
              className="px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 hover:border-blue-400 transition-colors flex items-center gap-2.5 text-xs font-mono cursor-pointer shadow-2xs"
              title="Clique para abrir a Carteira & Ledger Contábil"
            >
              <div className="flex items-center gap-1.5 text-emerald-700">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-bold">{formatCredits(wallet?.available_balance ?? wallet?.balance)}</span>
                <span className="text-[10px] text-emerald-600">disp.</span>
              </div>
              {Number(wallet?.reserved_balance || 0) > 0 && (
                <div className="flex items-center gap-1 text-amber-700 pl-2 border-l border-slate-200">
                  <span className="font-semibold">{formatCredits(wallet?.reserved_balance)}</span>
                  <span className="text-[10px] text-amber-600">hold</span>
                </div>
              )}
            </button>

            {/* API Status Dot */}
            <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-mono text-slate-600 px-2 py-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span>API Conectada</span>
            </div>
          </div>
        </header>

        {/* View Port */}
        <main className="px-4 py-6 sm:px-6 lg:px-8 max-w-7xl mx-auto">
          {error && (
            <div className="mb-6 flex items-center justify-between gap-4 rounded-lg bg-rose-50 border border-rose-200 px-4 py-3 text-xs text-rose-800" role="alert">
              <span>{error}</span>
              <button onClick={() => void refresh()} className="font-semibold underline cursor-pointer">
                Tentar novamente
              </button>
            </div>
          )}

          {currentRoute === 'dashboard' && <Dashboard onNavigate={navigate} />}
          {currentRoute === 'enrichment' && <Enrichment onNavigate={navigate} />}
          {currentRoute === 'wallet' && <Wallet />}
          {currentRoute === 'validation' && <EmailValidation />}
          {currentRoute === 'data-health' && <DataHealth onNavigate={navigate} />}
          {currentRoute === 'search' && (
            <SearchPage
              initialSetFilterId={selectedSetFilterId}
              onClearSetFilter={() => setSelectedSetFilterId(null)}
            />
          )}
          {currentRoute === 'datasets' && <DatasetsPage onNavigateToSearchWithSet={handleNavigateToSearchWithSet} />}
          {currentRoute === 'lists' && <ListsPage />}
          {currentRoute === 'admin' && <AdminCenter />}
        </main>
      </div>
    </div>
  );
}
