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
import { useLeadStream } from '../LeadStreamContext';

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
};

function BrandMark() {
  return (
    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-xs font-mono font-bold text-white shadow-md shadow-emerald-950/50">
      LS
    </div>
  );
}

export default function AppShell({ currentRoute, onNavigate }: AppShellProps) {
  const [selectedSetFilterId, setSelectedSetFilterId] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileMenuCloseRef = useRef<HTMLButtonElement>(null);
  const { user, tenant, wallet, loading, error, refresh, logout } = useLeadStream();
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
      <div className="flex h-16 items-center justify-between border-b border-white/10 px-5 bg-[#0D1117]">
        <button
          onClick={() => navigate('dashboard')}
          className="flex items-center gap-3 text-left focus-visible:outline-none cursor-pointer"
          aria-label="Ir para o painel geral"
        >
          <BrandMark />
          <span>
            <span className="block text-sm font-bold tracking-tight text-white">LeadStream</span>
            <span className="block text-[10px] font-mono text-slate-400 uppercase tracking-wider">Data Intelligence</span>
          </span>
        </button>
        <button
          ref={mobileMenuCloseRef}
          onClick={() => setMobileNavOpen(false)}
          className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white lg:hidden cursor-pointer"
          aria-label="Fechar navegação"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Nav Groups */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6" aria-label="Navegação principal">
        {navigation.map((group) => (
          <div key={group.label}>
            <p className="mb-2 px-3 text-[10px] font-mono font-medium text-slate-500 uppercase tracking-wider">
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
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : 'text-slate-300 hover:bg-white/5 hover:text-white border border-transparent'
                    }`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-emerald-400' : 'text-slate-500 group-hover:text-slate-300'}`} />
                    <span className="min-w-0">
                      <span className="block text-xs font-medium">{item.label}</span>
                      <span className={`block truncate text-[10px] ${active ? 'text-emerald-500/70' : 'text-slate-500'}`}>
                        {item.description}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom Tenant & User Footer */}
      <div className="border-t border-white/10 p-3 bg-[#0D1117] space-y-2">
        <div className="px-2 py-1.5 rounded-lg bg-white/[0.03] border border-white/5 flex items-center justify-between text-[11px] font-mono">
          <span className="text-slate-400 truncate">{tenant?.name || 'Workspace Padrão'}</span>
          <span className="px-1.5 py-0.5 rounded bg-white/5 text-[10px] text-slate-300">
            {tenant?.slug || 'internal'}
          </span>
        </div>
        <div className="flex items-center justify-between px-2 text-xs">
          <span className="text-slate-400 truncate font-sans text-[11px]">
            {user?.username || 'Administrador'}
          </span>
          <button
            onClick={logout}
            title="Encerrar Sessão"
            className="text-slate-500 hover:text-rose-400 transition-colors p-1 cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[#090A0F] text-[#F8FAFC]">
      {/* Desktop Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[250px] flex-col bg-[#12141C] border-r border-white/10 lg:flex">
        {sidebar}
      </aside>

      {/* Mobile Drawer */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navegação principal">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative flex h-full w-[280px] flex-col bg-[#12141C] border-r border-white/10">{sidebar}</aside>
        </div>
      )}

      {/* Main Content Area */}
      <div className="lg:pl-[250px]">
        {/* Top Sticky Header */}
        <header className="sticky top-0 z-20 flex min-h-[64px] items-center justify-between border-b border-white/10 bg-[#090A0F]/90 px-4 backdrop-blur-md sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              ref={mobileMenuButtonRef}
              onClick={() => setMobileNavOpen(true)}
              className="rounded-lg border border-white/10 p-2 text-slate-300 hover:text-white lg:hidden cursor-pointer"
              aria-label="Abrir navegação"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-sm font-semibold tracking-tight text-white">{page.title}</h1>
              <p className="hidden truncate text-[11px] text-slate-400 sm:block">{page.description}</p>
            </div>
          </div>

          {/* Right Header: Wallet Balance Pill & Status */}
          <div className="flex items-center gap-3">
            {/* Live Wallet Balance Pill */}
            <button
              onClick={() => navigate('wallet')}
              className="px-3 py-1.5 rounded-lg bg-[#12141C] border border-white/10 hover:border-emerald-500/40 transition-colors flex items-center gap-2.5 text-xs font-mono cursor-pointer"
              title="Clique para abrir a Carteira & Ledger Contábil"
            >
              <div className="flex items-center gap-1.5 text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-bold">{formatCredits(wallet?.available_balance ?? wallet?.balance)}</span>
                <span className="text-[10px] text-emerald-500/70">disp.</span>
              </div>
              {Number(wallet?.reserved_balance || 0) > 0 && (
                <div className="flex items-center gap-1 text-amber-400 pl-2 border-l border-white/10">
                  <span className="font-semibold">{formatCredits(wallet?.reserved_balance)}</span>
                  <span className="text-[10px] text-amber-500/70">hold</span>
                </div>
              )}
            </button>

            {/* API Status Dot */}
            <div className="hidden sm:flex items-center gap-1.5 text-[11px] font-mono text-slate-400 px-2 py-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              <span>API Conectada</span>
            </div>
          </div>
        </header>

        {/* View Port */}
        <main className="px-4 py-6 sm:px-6 lg:px-8 max-w-7xl mx-auto">
          {error && (
            <div className="mb-6 flex items-center justify-between gap-4 rounded-lg bg-rose-500/10 border border-rose-500/20 px-4 py-3 text-xs text-rose-300" role="alert">
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
        </main>
      </div>
    </div>
  );
}
