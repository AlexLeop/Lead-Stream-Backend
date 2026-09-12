import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  Cpu,
  Database,
  ExternalLink,
  Layers,
  ListChecks,
  MailCheck,
  RefreshCw,
  Server,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
  Wallet as WalletIcon,
  Zap,
} from 'lucide-react';
import { api } from '../api';
import { useLeadStream } from '../LeadStreamContext';
import type { DashboardData, DataHealthData } from '../types';

interface DashboardProps {
  onNavigate: (route: string) => void;
}

function metricValue(value: number, suffix = '') {
  return `${value.toLocaleString('pt-BR')}${suffix}`;
}

export default function Dashboard({ onNavigate }: DashboardProps) {
  const { activities, datasets, lists, user, tenant, wallet, refresh } = useLeadStream();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [health, setHealth] = useState<DataHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredDay, setHoveredDay] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextDashboard, nextHealth] = await Promise.all([
        api.dashboard('30days'),
        api.dataHealth(),
      ]);
      setDashboard(nextDashboard);
      setHealth(nextHealth);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível carregar a central de dados.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const score = health?.summary.overallScore ?? 96;
  const validEmails = dashboard?.summary.validEmails ?? 114;
  const deliverabilityRate = dashboard?.summary.deliverabilityRate ?? 98.4;
  const companiesCount = health?.summary.companies ?? 50;
  const contactsCount = health?.summary.contacts ?? 120;
  const chartData = dashboard?.chartData ?? [];
  const maxChartLeads = useMemo(
    () => Math.max(...chartData.map((d) => d.leads), 50),
    [chartData]
  );

  const formatCredits = (val?: number) => {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('pt-BR').format(val);
  };

  if (loading) {
    return (
      <div className="space-y-6" aria-busy="true">
        <div className="h-32 animate-pulse rounded-xl bg-[#12141C] border border-white/5" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-28 animate-pulse rounded-xl bg-[#12141C] border border-white/5" />
          ))}
        </div>
        <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="h-80 animate-pulse rounded-xl bg-[#12141C] border border-white/5" />
          <div className="h-80 animate-pulse rounded-xl bg-[#12141C] border border-white/5" />
        </div>
      </div>
    );
  }

  if (error || !health || !dashboard) {
    return (
      <div className="rounded-xl border border-rose-500/20 bg-[#12141C] p-6 text-rose-300" role="alert">
        <div className="flex items-start gap-4">
          <div className="rounded-lg bg-rose-500/10 p-2.5 border border-rose-500/20 text-rose-400">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <div className="space-y-2 flex-1">
            <h2 className="text-base font-bold text-white tracking-tight">Falha de Comunicação com a Central de Dados</h2>
            <p className="text-xs text-rose-400/90 leading-relaxed max-w-2xl">{error}</p>
            <button
              onClick={() => void load()}
              className="mt-3 inline-flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-xs font-semibold text-white transition-colors cursor-pointer"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Tentar Reconexão
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 1. Executive Management Command Header */}
      <section className="relative overflow-hidden rounded-xl border border-white/10 bg-[#12141C] p-6 lg:p-7 shadow-xl shadow-black/40">
        <div className="absolute top-0 right-0 h-48 w-48 bg-emerald-500/5 blur-3xl pointer-events-none" />
        
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2 max-w-3xl">
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <ShieldCheck className="w-3 h-3" />
                Painel do Gestor Executivo
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-white/5 border border-white/10">
                Tenant: {tenant?.name || 'LeadStream Master'} ({tenant?.slug || 'internal'})
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-white/5 border border-white/10">
                Operador: {user?.username || 'Super Admin'}
              </span>
            </div>

            <h1 className="text-2xl font-bold tracking-tight text-white lg:text-3xl">
              Central de Comando & Inteligência Cadastral
            </h1>
            <p className="text-xs text-slate-400 leading-relaxed">
              Orquestração independente sobre a infraestrutura: processamento de até 100k empresas,
              resolução de sócios e administradores (QSA), verificação RFC 5321 e garantia de cobrança por dado útil (Pay-per-Value).
            </p>
          </div>

          {/* Infrastructure Health Status Matrix */}
          <div className="flex flex-wrap lg:flex-col gap-2 rounded-lg bg-black/40 p-3.5 border border-white/5 font-mono text-[11px] shrink-0">
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Server className="w-3.5 h-3.5 text-emerald-400" /> Cluster VPS
              </span>
              <span className="text-emerald-400 font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Ativo
              </span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-emerald-400" /> PostgreSQL 17
              </span>
              <span className="text-slate-300">Conectado (ACID)</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-400 flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-emerald-400" /> Celery Workers
              </span>
              <span className="text-slate-300">4 Workers (100k)</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-400 flex items-center gap-1.5">
                <WalletIcon className="w-3.5 h-3.5 text-emerald-400" /> Ledger Contábil
              </span>
              <span className="text-emerald-400 font-semibold">Auditado</span>
            </div>
          </div>
        </div>
      </section>

      {/* 2. Top Strategic KPI Cards */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {/* KPI 1: Contas e Decisores */}
        <div className="rounded-xl border border-white/10 bg-[#12141C] p-5 hover:border-emerald-500/30 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Contas PJ & Decisores</span>
            <Building2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white tracking-tight">
              {metricValue(companiesCount)}
            </span>
            <span className="text-xs font-mono text-slate-400">empresas</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400 flex items-center gap-1">
            <span className="text-emerald-400 font-mono font-bold">{metricValue(contactsCount)}</span>
            <span>decisores com evidência pública auditável</span>
          </p>
        </div>

        {/* KPI 2: Entregabilidade RFC 5321 */}
        <div className="rounded-xl border border-white/10 bg-[#12141C] p-5 hover:border-emerald-500/30 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Entregabilidade Técnica</span>
            <MailCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-emerald-400 tracking-tight">
              {deliverabilityRate}%
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              ZERO-BOUNCE
            </span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400">
            <span className="text-white font-mono font-semibold">{metricValue(validEmails)}</span> caixas validadas por handshake SMTP
          </p>
        </div>

        {/* KPI 3: Saldo da Carteira & Ledger */}
        <div
          onClick={() => onNavigate('wallet')}
          className="rounded-xl border border-white/10 bg-[#12141C] p-5 hover:border-emerald-500/30 transition-colors cursor-pointer group"
          title="Abrir Carteira & Ledger Contábil"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Carteira & Ledger</span>
            <ArrowUpRight className="h-4 w-4 text-slate-500 group-hover:text-emerald-400 transition-colors" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white tracking-tight">
              {formatCredits(wallet?.available_balance ?? wallet?.balance)}
            </span>
            <span className="text-xs font-mono text-emerald-400 font-semibold">créditos</span>
          </div>
          <p className="mt-2 text-[11px] text-slate-400 flex items-center justify-between">
            <span>Pay-per-Value com estorno</span>
            <span className="text-emerald-400 font-mono text-[10px]">100% auditado</span>
          </p>
        </div>

        {/* KPI 4: Qualidade da Base */}
        <div
          onClick={() => onNavigate('data-health')}
          className="rounded-xl border border-white/10 bg-[#12141C] p-5 hover:border-emerald-500/30 transition-colors cursor-pointer group"
          title="Abrir Diagnóstico de Saúde Cadastral"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400">Índice de Confiabilidade</span>
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-bold font-mono text-white tracking-tight">
              {score}
            </span>
            <span className="text-xs font-mono text-slate-400">/ 100</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${score}%` }} />
          </div>
        </div>
      </section>

      {/* 3. Executive Action Quick-Launch Strip */}
      <section className="rounded-xl border border-white/10 bg-[#12141C] p-4 lg:p-5">
        <div className="flex items-center justify-between mb-3.5">
          <span className="text-[11px] font-mono font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-emerald-400" /> Ações Rápidas de Gestão
          </span>
          <a
            href="/admin/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-[11px] font-mono text-slate-400 hover:text-white transition-colors"
          >
            <span>Django Admin (DRF Interno)</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <button
            onClick={() => onNavigate('search')}
            className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 hover:border-emerald-500/30 hover:bg-white/[0.04] transition-all text-left cursor-pointer"
          >
            <div className="p-2 rounded-md bg-emerald-500/10 text-emerald-400">
              <Building2 className="w-4 h-4" />
            </div>
            <div>
              <strong className="block text-xs text-white">Descoberta CNAE</strong>
              <span className="block text-[10px] text-slate-400">Pesquisa de mercado</span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('enrichment')}
            className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 hover:border-emerald-500/30 hover:bg-white/[0.04] transition-all text-left cursor-pointer"
          >
            <div className="p-2 rounded-md bg-emerald-500/10 text-emerald-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <strong className="block text-xs text-white">Lote de Enriquecimento</strong>
              <span className="block text-[10px] text-slate-400">Até 100k registros</span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('validation')}
            className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 hover:border-emerald-500/30 hover:bg-white/[0.04] transition-all text-left cursor-pointer"
          >
            <div className="p-2 rounded-md bg-emerald-500/10 text-emerald-400">
              <MailCheck className="w-4 h-4" />
            </div>
            <div>
              <strong className="block text-xs text-white">Zero-Bounce SMTP</strong>
              <span className="block text-[10px] text-slate-400">Probe RFC 5321</span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('wallet')}
            className="flex items-center gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/5 hover:border-emerald-500/30 hover:bg-white/[0.04] transition-all text-left cursor-pointer"
          >
            <div className="p-2 rounded-md bg-emerald-500/10 text-emerald-400">
              <WalletIcon className="w-4 h-4" />
            </div>
            <div>
              <strong className="block text-xs text-white">Ledger & Estornos</strong>
              <span className="block text-[10px] text-slate-400">Auditoria contábil</span>
            </div>
          </button>
        </div>
      </section>

      {/* 4. Analytics & Operational Intelligence */}
      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        {/* Activity & Lead Throughput Chart */}
        <section className="rounded-xl border border-white/10 bg-[#12141C] p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/10 pb-4">
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">Throughput de Leads & Validação Cadastral</h2>
              <p className="text-[11px] text-slate-400">Acompanhamento temporal dos registros ingeridos e qualificados</p>
            </div>
            <div className="flex items-center gap-4 text-[11px] font-mono text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-slate-600" /> Ingeridos
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500" /> Validados SMTP
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-sky-500" /> Decisores QSA
              </span>
            </div>
          </div>

          {/* Interactive Bar Chart Visualization */}
          <div className="h-56 flex items-end justify-between gap-1.5 pt-6 pb-2 px-2">
            {chartData.map((item, idx) => {
              const leadsHeight = Math.max(Math.round((item.leads / maxChartLeads) * 100), 10);
              const validadosHeight = Math.max(Math.round((item.validados / maxChartLeads) * 100), 8);
              const isHovered = hoveredDay === idx;

              return (
                <div
                  key={item.day}
                  onMouseEnter={() => setHoveredDay(idx)}
                  onMouseLeave={() => setHoveredDay(null)}
                  className="flex-1 flex flex-col items-center gap-1 group relative cursor-pointer"
                >
                  {/* Tooltip */}
                  {isHovered && (
                    <div className="absolute -top-14 z-30 px-2 py-1.5 rounded-md bg-black/95 border border-white/20 text-[10px] font-mono text-white shadow-xl whitespace-nowrap pointer-events-none">
                      <span className="text-emerald-400 font-bold">{item.validados} validados</span> · {item.leads} leads
                    </div>
                  )}

                  {/* Bars */}
                  <div className="w-full flex items-end justify-center gap-0.5 h-44">
                    <div
                      className="w-full max-w-[12px] bg-slate-700/60 rounded-t-sm group-hover:bg-slate-500 transition-colors"
                      style={{ height: `${leadsHeight}%` }}
                    />
                    <div
                      className="w-full max-w-[12px] bg-emerald-500 rounded-t-sm group-hover:bg-emerald-400 transition-colors shadow-sm shadow-emerald-500/20"
                      style={{ height: `${validadosHeight}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-mono text-slate-500 group-hover:text-slate-300">
                    {item.day}
                  </span>
                </div>
              );
            })}
          </div>
        </section>

        {/* Industry Breakdown */}
        <section className="rounded-xl border border-white/10 bg-[#12141C] p-6 space-y-4">
          <div className="border-b border-white/10 pb-4">
            <h2 className="text-sm font-bold text-white tracking-tight">Distribuição Setorial da Base (CNAE)</h2>
            <p className="text-[11px] text-slate-400">Segmentação econômica dos registros corporativos</p>
          </div>

          <div className="space-y-3.5">
            {dashboard.industryBreakdown.map((item) => (
              <div key={item.name} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate max-w-[200px]">{item.name}</span>
                  <span className="font-mono text-slate-400">{item.value}%</span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{ width: `${item.value}%`, backgroundColor: item.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* 5. Provenance & Activity Audit Feed */}
      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        {/* Coverage & Lineage Radar */}
        <section className="rounded-xl border border-white/10 bg-[#12141C] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">Linhagem & Integridade de Evidência</h2>
              <p className="text-[11px] text-slate-400">Atribuição por fonte, instante de captura e método</p>
            </div>
            <button
              onClick={() => onNavigate('data-health')}
              className="text-xs font-mono font-semibold text-emerald-400 hover:text-emerald-300 transition-colors cursor-pointer"
            >
              Ver Tudo
            </button>
          </div>

          <div className="space-y-3 divide-y divide-white/5">
            {health.coverage.slice(0, 5).map((item) => (
              <div key={item.id} className="pt-3 first:pt-0 flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <span className="block text-xs font-medium text-slate-200 truncate">{item.label}</span>
                  <div className="mt-1 h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-emerald-500"
                      style={{ width: `${item.value}%` }}
                    />
                  </div>
                </div>
                <span className="font-mono text-xs font-bold text-white shrink-0">
                  {item.value}%
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Live Operational Audit Stream */}
        <section className="rounded-xl border border-white/10 bg-[#12141C] p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-white/10 pb-4">
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">Trilha de Auditoria & Atividades</h2>
              <p className="text-[11px] text-slate-400">Registro imutável de eventos e chamadas à plataforma</p>
            </div>
            <Activity className="h-4 w-4 text-slate-500" />
          </div>

          <div className="space-y-3">
            {activities.slice(0, 5).map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-3 p-2.5 rounded-lg bg-white/[0.02] border border-white/5 hover:border-white/10 transition-colors"
              >
                <div className="mt-0.5">
                  <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <strong className="block text-xs text-white truncate">{item.title}</strong>
                    <span className="font-mono text-[10px] text-slate-500 shrink-0">{item.time}</span>
                  </div>
                  <span className="block text-[11px] font-mono text-slate-400 truncate mt-0.5">
                    {item.subtitle || item.type}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
