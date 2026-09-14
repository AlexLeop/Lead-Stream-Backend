import { useEffect, useRef, useState, type ComponentType } from 'react';
import {
  Activity,
  FolderKanban,
  LayoutDashboard,
  ListOrdered,
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
    label: 'Dados e qualidade',
    items: [
      { id: 'dashboard', label: 'Central de dados', description: 'Visão operacional', icon: LayoutDashboard },
      { id: 'data-health', label: 'Qualidade da base', description: 'Cobertura e confiança', icon: ShieldCheck },
      { id: 'enrichment', label: 'Enriquecimento', description: 'Consulte fontes configuradas', icon: Sparkles },
    ],
  },
  {
    label: 'Prospecção e ativação',
    items: [
      { id: 'search', label: 'Mercado & Contas', description: 'Empresas e pessoas observadas', icon: Search },
      { id: 'datasets', label: 'Bases', description: 'Arquivos e segmentos', icon: FolderKanban },
      { id: 'lists', label: 'Listas', description: 'Seleção e exportação', icon: ListOrdered },
    ],
  },
  {
    label: 'Operações e gestão',
    items: [
      { id: 'wallet', label: 'Carteira & Ledger', description: 'Custódia e Pay-per-Value', icon: WalletIcon },
      { id: 'validation', label: 'Validação Zero-Bounce', description: 'Probe RFC 5321 profundo', icon: MailCheck },
      { id: 'admin', label: 'Administração', description: 'Workspaces, planos e sistema', icon: ShieldAlert },
    ],
  },
];

const pageTitles: Record<string, { title: string; description: string }> = {
  dashboard: { title: 'Central de dados', description: 'Qualidade, cobertura e próximos passos para sua operação.' },
  'data-health': { title: 'Qualidade da base', description: 'Descubra lacunas e oportunidades de melhoria.' },
  enrichment: { title: 'Enriquecimento', description: 'Consulte dados cadastrais e preserve a evidência de cada resultado.' },
  search: { title: 'Mercado & Contas', description: 'Revise empresas e pessoas observadas antes do uso comercial.' },
  datasets: { title: 'Bases', description: 'Organize arquivos, segmentos e campanhas.' },
  lists: { title: 'Listas', description: 'Selecione e exporte somente registros adequados ao seu fluxo.' },
  wallet: { title: 'Carteira & Ledger Contábil', description: 'Registro contábil de dupla entrada em BRL com garantia de estorno de dados ausentes.' },
  validation: { title: 'Validação Zero-Bounce', description: 'Handshake SMTP atômico em tempo real com resolução MX de DNS e detecção catch-all.' },
  admin: { title: 'Administração do Sistema', description: 'Gerenciamento de workspaces, planos de preços, usuários e provedores.' },
};

function BrandMark() {
  return (
    <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-blue-600 text-sm font-extrabold text-white shadow-xs">
      LS
    </div>
  );
}

export default function AppShell({ currentRoute, onNavigate }: AppShellProps) {
  const [selectedSetFilterId, setSelectedSetFilterId] = useState<string | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileMenuCloseRef = useRef<HTMLButtonElement>(null);
  const { workspace, tenant, wallet, loading, error, refresh } = useLeadStream();
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

  const sidebar = (
    <>
      {/* Brand Header */}
      <div className="flex h-[72px] items-center justify-between border-b border-slate-800 px-5">
        <button
          onClick={() => navigate('dashboard')}
          className="flex items-center gap-3 rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 cursor-pointer"
          aria-label="Ir para a central de dados"
        >
          <BrandMark />
          <span>
            <span className="block text-sm font-bold tracking-tight text-white">LeadStream</span>
            <span className="block text-[11px] font-medium text-slate-400">Inteligência B2B</span>
          </span>
        </button>
        <button
          ref={mobileMenuCloseRef}
          onClick={() => setMobileNavOpen(false)}
          className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-white lg:hidden cursor-pointer"
          aria-label="Fechar navegação"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Main Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-5" aria-label="Navegação principal">
        {navigation.map((group) => (
          <div key={group.label} className="mb-6">
            <p className="mb-2 px-3 text-[11px] font-semibold text-slate-500">{group.label}</p>
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = currentRoute === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => navigate(item.id)}
                    aria-current={active ? 'page' : undefined}
                    className={`group flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left transition-colors cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                      active ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                    }`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${active ? 'text-white' : 'text-slate-500 group-hover:text-slate-300'}`} />
                    <span className="min-w-0">
                      <span className="block text-xs font-semibold">{item.label}</span>
                      <span className={`block truncate text-[10px] ${active ? 'text-blue-100' : 'text-slate-500'}`}>
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

      {/* Footer Metrics */}
      <div className="border-t border-slate-800 p-4">
        <div className="rounded-[12px] bg-slate-900 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="flex items-center gap-2 text-[11px] font-semibold text-slate-200">
              <Activity className="h-3.5 w-3.5 text-blue-400" /> Sua base
            </span>
            <span className="rounded-full bg-blue-400/10 px-2 py-0.5 text-[10px] font-bold text-blue-300">
              {tenant?.slug || 'Banco local'}
            </span>
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400">
            <span>{(workspace.companies || 0).toLocaleString('pt-BR')} {(workspace.companies || 0) === 1 ? 'empresa' : 'empresas'}</span>
            <span>{(workspace.contacts || 0).toLocaleString('pt-BR')} {(workspace.contacts || 0) === 1 ? 'contato' : 'contatos'}</span>
          </div>
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-[var(--ls-bg)] text-slate-950">
      {/* Desktop Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] flex-col bg-[#0b1220] lg:flex">
        {sidebar}
      </aside>

      {/* Mobile Drawer */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Navegação principal">
          <div
            className="absolute inset-0 bg-slate-950/55"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />
          <aside className="relative flex h-full w-[286px] flex-col bg-[#0b1220]">{sidebar}</aside>
        </div>
      )}

      {/* Main View Area */}
      <div className="lg:pl-[248px]">
        <header className="sticky top-0 z-20 flex min-h-[72px] items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur-sm sm:px-6 lg:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              ref={mobileMenuButtonRef}
              onClick={() => setMobileNavOpen(true)}
              className="rounded-lg border border-slate-200 p-2 text-slate-700 hover:bg-slate-50 lg:hidden cursor-pointer"
              aria-label="Abrir navegação"
            >
              <Menu className="h-4 w-4" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-base font-bold tracking-[-0.02em] text-slate-950">{page.title}</h1>
              <p className="hidden truncate text-[11px] text-slate-500 sm:block">{page.description}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 text-[11px] font-medium text-slate-600">
            {/* Real BRL Wallet Badge */}
            <button
              onClick={() => navigate('wallet')}
              className="flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 hover:bg-slate-100 hover:border-blue-400 transition-all cursor-pointer shadow-2xs"
              title="Gerenciar Carteira & Ledger Contábil"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <span className="font-semibold text-slate-900">
                {wallet
                  ? `R$ ${(Number(wallet.available_balance ?? wallet.balance ?? 0)).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                  : 'R$ 0,00'}
              </span>
              <span className="text-[10px] text-slate-500">disp.</span>
            </button>

            <span className="hidden items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 sm:flex">
              <Activity className="h-3.5 w-3.5 text-blue-600" /> Dados do workspace
            </span>

            <button
              onClick={() => void refresh()}
              disabled={loading}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-wait disabled:opacity-60 cursor-pointer"
            >
              {loading ? 'Atualizando…' : 'Atualizar'}
            </button>
          </div>
        </header>

        <main className="px-4 py-5 sm:px-6 lg:px-8 lg:py-7 max-w-[1440px] mx-auto">
          {error && (
            <div className="mx-auto mb-5 flex max-w-[1440px] items-center justify-between gap-4 rounded-[10px] bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-900" role="alert">
              <span>{error}</span>
              <button onClick={() => void refresh()} className="shrink-0 font-bold underline underline-offset-2 cursor-pointer">
                Tentar novamente
              </button>
            </div>
          )}
          {currentRoute === 'dashboard' && <Dashboard onNavigate={navigate} />}
          {currentRoute === 'data-health' && <DataHealth onNavigate={navigate} />}
          {currentRoute === 'enrichment' && <Enrichment onNavigate={navigate} />}
          {currentRoute === 'search' && (
            <SearchPage
              initialSetFilterId={selectedSetFilterId}
              onClearSetFilter={() => setSelectedSetFilterId(null)}
            />
          )}
          {currentRoute === 'datasets' && <DatasetsPage onNavigateToSearchWithSet={handleNavigateToSearchWithSet} />}
          {currentRoute === 'lists' && <ListsPage />}
          {currentRoute === 'wallet' && <Wallet />}
          {currentRoute === 'validation' && <EmailValidation />}
          {currentRoute === 'admin' && <AdminCenter />}
        </main>
      </div>
    </div>
  );
}
