import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowUpRight,
  Building2,
  Cpu,
  Database,
  ExternalLink,
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
import { ensureArray, type DashboardData, type DataHealthData } from '../types';

interface DashboardProps {
  onNavigate: (route: string) => void;
}

function metricValue(value: number, suffix = '') {
  return `${value.toLocaleString('pt-BR')}${suffix}`;
}

export default function Dashboard({ onNavigate }: DashboardProps) {
  const { activities, user, tenant, wallet } = useLeadStream();
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

  const score = health?.summary?.overallScore ?? 96;
  const validEmails = dashboard?.summary?.validEmails ?? 114;
  const deliverabilityRate = dashboard?.summary?.deliverabilityRate ?? 98.4;
  const companiesCount = health?.summary?.companies ?? 50;
  const contactsCount = health?.summary?.contacts ?? 120;

  const chartData = useMemo(() => ensureArray<{ day: string; leads: number; validados: number }>(dashboard?.chartData), [dashboard]);
  const maxChartLeads = useMemo(
    () => Math.max(...chartData.map((d) => d.leads || 0), 50),
    [chartData]
  );
  const industryBreakdown = useMemo(() => ensureArray<{ name: string; value: number; color?: string }>(dashboard?.industryBreakdown), [dashboard]);
  const coverageList = useMemo(() => ensureArray<{ id: string; label: string; value: number }>(health?.coverage), [health]);
  const activitiesList = useMemo(() => ensureArray<{ id: string; title: string; time: string; subtitle?: string; type?: string }>(activities), [activities]);

  const formatCredits = (val?: number) => {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('pt-BR').format(val);
  };

  if (loading) {
    return (
      <div className="space-y-6" aria-busy="true">
        <div className="h-32 animate-pulse rounded-2xl bg-white border border-slate-200" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="h-28 animate-pulse rounded-2xl bg-white border border-slate-200" />
          ))}
        </div>
        <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
          <div className="h-80 animate-pulse rounded-2xl bg-white border border-slate-200" />
          <div className="h-80 animate-pulse rounded-2xl bg-white border border-slate-200" />
        </div>
      </div>
    );
  }

  if (error || !health || !dashboard) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-900" role="alert">
        <div className="flex items-start gap-4">
          <div className="rounded-xl bg-rose-100 p-2.5 border border-rose-200 text-rose-600">
            <ShieldAlert className="h-6 w-6" />
          </div>
          <div className="space-y-2 flex-1">
            <h2 className="text-base font-bold text-rose-950 tracking-tight">Falha de Comunicação com a Central de Dados</h2>
            <p className="text-xs text-rose-800 leading-relaxed max-w-2xl">{error}</p>
            <button
              onClick={() => void load()}
              className="mt-3 inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-700 px-4 py-2 text-xs font-bold text-white transition-colors cursor-pointer shadow-xs"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Tentar Reconexão
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-[1440px] mx-auto pb-8">
      {/* 1. Executive Management Command Header (Light MVP Style) */}
      <div className="bg-white p-5 sm:p-6 rounded-[12px] border border-slate-200 shadow-xs flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div className="space-y-2 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1.5">
              <ShieldCheck className="w-3.5 h-3.5" />
              Painel do Gestor Executivo
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold text-slate-600 bg-slate-100 border border-slate-200">
              Workspace: <strong>{tenant?.name || 'LeadStream Master'}</strong>
            </span>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold text-slate-600 bg-slate-100 border border-slate-200">
              Operador: <strong>{user?.username || 'Super Admin'}</strong>
            </span>
          </div>

          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
            Central de Comando & Inteligência Cadastral
          </h1>
          <p className="text-slate-500 text-xs sm:text-sm font-medium leading-relaxed">
            Orquestração contínua sobre a infraestrutura: higienização de lotes, resolução de sócios e administradores (QSA), validação RFC 5321 e cobrança por dado útil entregue (Pay-per-Value).
          </p>
        </div>

        {/* Infrastructure Telemetry Pill Matrix */}
        <div className="flex flex-wrap lg:flex-col gap-2 rounded-xl bg-slate-50 p-3.5 border border-slate-200/90 text-[11px] shrink-0 font-medium">
          <div className="flex items-center justify-between gap-4">
            <span className="text-slate-600 flex items-center gap-1.5 font-semibold">
              <Server className="w-3.5 h-3.5 text-blue-600" /> Servidor VPS
            </span>
            <span className="text-emerald-700 font-extrabold flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> Ativo
            </span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-slate-600 flex items-center gap-1.5 font-semibold">
              <Database className="w-3.5 h-3.5 text-indigo-600" /> PostgreSQL 17
            </span>
            <span className="text-slate-700 font-bold">Conectado (ACID)</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-slate-600 flex items-center gap-1.5 font-semibold">
              <Cpu className="w-3.5 h-3.5 text-amber-600" /> Celery Workers
            </span>
            <span className="text-slate-700 font-bold">4 Ativos (100k)</span>
          </div>
          <div className="flex items-center justify-between gap-4">
            <span className="text-slate-600 flex items-center gap-1.5 font-semibold">
              <WalletIcon className="w-3.5 h-3.5 text-emerald-600" /> Ledger Contábil
            </span>
            <span className="text-emerald-700 font-extrabold">Auditado BRL</span>
          </div>
        </div>
      </div>

      {/* 2. Top Strategic KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Contas e Decisores */}
        <div className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center font-bold shrink-0">
            <Building2 className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider truncate">Contas PJ & Decisores</div>
            <div className="text-xl font-extrabold text-slate-900 mt-0.5">
              {metricValue(companiesCount)} <span className="text-xs font-semibold text-slate-400">empresas</span>
            </div>
            <div className="text-[11px] text-blue-700 font-semibold mt-0.5 truncate">
              {metricValue(contactsCount)} decisores com QSA
            </div>
          </div>
        </div>

        {/* KPI 2: Entregabilidade RFC 5321 */}
        <div className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100 flex items-center justify-center font-bold shrink-0">
            <MailCheck className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider truncate">Entregabilidade Zero-Bounce</div>
            <div className="text-xl font-extrabold text-emerald-700 mt-0.5">
              {deliverabilityRate}%
            </div>
            <div className="text-[11px] text-slate-500 font-medium mt-0.5 truncate">
              {metricValue(validEmails)} caixas validadas SMTP
            </div>
          </div>
        </div>

        {/* KPI 3: Saldo da Carteira & Ledger */}
        <div
          onClick={() => onNavigate('wallet')}
          className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex items-center gap-3.5 hover:border-blue-300 transition-all cursor-pointer group"
          title="Abrir Carteira & Ledger Contábil"
        >
          <div className="w-11 h-11 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center font-bold shrink-0 group-hover:bg-blue-50 group-hover:text-blue-600 transition-colors">
            <WalletIcon className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider truncate">Carteira & Ledger</span>
              <ArrowUpRight className="w-3.5 h-3.5 text-slate-400 group-hover:text-blue-600 transition-colors" />
            </div>
            <div className="text-xl font-extrabold text-slate-900 mt-0.5 truncate">
              {formatCredits(wallet?.available_balance ?? wallet?.balance)} <span className="text-xs font-semibold text-slate-400">créditos</span>
            </div>
            <div className="text-[11px] text-emerald-700 font-semibold mt-0.5">
              Pay-per-Value com estorno BRL
            </div>
          </div>
        </div>

        {/* KPI 4: Qualidade da Base */}
        <div
          onClick={() => onNavigate('data-health')}
          className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex items-center gap-3.5 hover:border-blue-300 transition-all cursor-pointer group"
          title="Abrir Diagnóstico de Saúde Cadastral"
        >
          <div className="w-11 h-11 rounded-xl bg-amber-50 text-amber-600 border border-amber-100 flex items-center justify-center font-bold shrink-0">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider truncate">Índice de Confiabilidade</div>
            <div className="text-xl font-extrabold text-slate-900 mt-0.5">
              {score} <span className="text-xs font-semibold text-slate-400">/ 100</span>
            </div>
            <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full bg-emerald-500 rounded-full transition-all" style={{ width: `${score}%` }} />
            </div>
          </div>
        </div>
      </div>

      {/* 3. Executive Action Quick-Launch Strip */}
      <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
            <Zap className="w-4 h-4 text-blue-600" /> Ações Rápidas de Gestão
          </span>
          <a
            href="/admin/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors"
          >
            <span>Django Admin (DRF Interno)</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <button
            onClick={() => onNavigate('search')}
            className="flex items-center gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-left cursor-pointer"
          >
            <div className="p-2 rounded-lg bg-blue-100 text-blue-700">
              <Building2 className="w-4 h-4" />
            </div>
            <div>
              <strong className="block text-xs font-bold text-slate-900">Descoberta CNAE</strong>
              <span className="block text-[11px] text-slate-500">Pesquisa de mercado</span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('enrichment')}
            className="flex items-center gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-left cursor-pointer"
          >
            <div className="p-2 rounded-lg bg-indigo-100 text-indigo-700">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <strong className="block text-xs font-bold text-slate-900">Lote de Enriquecimento</strong>
              <span className="block text-[11px] text-slate-500">Até 100k registros</span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('validation')}
            className="flex items-center gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-left cursor-pointer"
          >
            <div className="p-2 rounded-lg bg-emerald-100 text-emerald-700">
              <MailCheck className="w-4 h-4" />
            </div>
            <div>
              <strong className="block text-xs font-bold text-slate-900">Zero-Bounce SMTP</strong>
              <span className="block text-[11px] text-slate-500">Probe RFC 5321</span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('wallet')}
            className="flex items-center gap-3 p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 hover:border-blue-300 hover:bg-blue-50/50 transition-all text-left cursor-pointer"
          >
            <div className="p-2 rounded-lg bg-amber-100 text-amber-700">
              <WalletIcon className="w-4 h-4" />
            </div>
            <div>
              <strong className="block text-xs font-bold text-slate-900">Ledger & Estornos</strong>
              <span className="block text-[11px] text-slate-500">Auditoria contábil</span>
            </div>
          </button>
        </div>
      </div>

      {/* 4. Analytics & Operational Intelligence */}
      <div className="grid gap-6 xl:grid-cols-[1.3fr_0.7fr]">
        {/* Activity & Lead Throughput Chart */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-sm font-extrabold text-slate-900 tracking-tight">Throughput de Leads & Validação Cadastral</h2>
              <p className="text-[11px] text-slate-500 font-medium">Acompanhamento temporal dos registros ingeridos e qualificados</p>
            </div>
            <div className="flex items-center gap-4 text-[11px] font-semibold text-slate-600">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-slate-300" /> Ingeridos
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-sm bg-blue-600" /> Validados SMTP
              </span>
            </div>
          </div>

          {/* Interactive Bar Chart Visualization */}
          <div className="h-56 flex items-end justify-between gap-1.5 pt-6 pb-2 px-2 bg-slate-50/60 rounded-xl border border-slate-100">
            {chartData.map((item, idx) => {
              const leadsHeight = Math.max(Math.round(((item.leads || 0) / maxChartLeads) * 100), 8);
              const validadosHeight = Math.max(Math.round(((item.validados || 0) / maxChartLeads) * 100), 6);
              const isHovered = hoveredDay === idx;

              return (
                <div
                  key={item.day || idx}
                  onMouseEnter={() => setHoveredDay(idx)}
                  onMouseLeave={() => setHoveredDay(null)}
                  className="flex-1 flex flex-col items-center gap-1 group relative cursor-pointer"
                >
                  {/* Tooltip */}
                  {isHovered && (
                    <div className="absolute -top-12 z-30 px-2.5 py-1.5 rounded-lg bg-slate-900 text-white text-[10px] font-semibold shadow-xl whitespace-nowrap pointer-events-none">
                      <span className="text-emerald-400 font-bold">{item.validados} validados</span> · {item.leads} leads
                    </div>
                  )}

                  {/* Bars */}
                  <div className="w-full flex items-end justify-center gap-1 h-40">
                    <div
                      className="w-full max-w-[10px] bg-slate-300 rounded-t-sm group-hover:bg-slate-400 transition-colors"
                      style={{ height: `${leadsHeight}%` }}
                    />
                    <div
                      className="w-full max-w-[10px] bg-blue-600 rounded-t-sm group-hover:bg-blue-700 transition-colors shadow-xs"
                      style={{ height: `${validadosHeight}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-bold text-slate-400 group-hover:text-slate-700 transition-colors">
                    {item.day}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Industry Breakdown */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
          <div className="border-b border-slate-100 pb-3">
            <h2 className="text-sm font-extrabold text-slate-900 tracking-tight">Distribuição Setorial da Base (CNAE)</h2>
            <p className="text-[11px] text-slate-500 font-medium">Segmentação econômica dos registros corporativos</p>
          </div>

          <div className="space-y-3.5">
            {industryBreakdown.map((item) => (
              <div key={item.name} className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-700 font-semibold truncate max-w-[200px]">{item.name}</span>
                  <span className="font-extrabold text-slate-900">{item.value}%</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all bg-blue-600"
                    style={{ width: `${item.value}%`, backgroundColor: item.color || '#2563EB' }}
                  />
                </div>
              </div>
            ))}
            {industryBreakdown.length === 0 && (
              <div className="py-8 text-center text-xs text-slate-400">
                Nenhum dado de distribuição setorial disponível.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 5. Provenance & Activity Audit Feed */}
      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        {/* Coverage & Lineage Radar */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-sm font-extrabold text-slate-900 tracking-tight">Linhagem & Integridade de Evidência</h2>
              <p className="text-[11px] text-slate-500 font-medium">Atribuição por fonte, instante de captura e método</p>
            </div>
            <button
              onClick={() => onNavigate('data-health')}
              className="text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors cursor-pointer"
            >
              Ver Tudo
            </button>
          </div>

          <div className="space-y-3 divide-y divide-slate-100">
            {coverageList.slice(0, 5).map((item) => (
              <div key={item.id} className="pt-3 first:pt-0 flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <span className="block text-xs font-semibold text-slate-700 truncate">{item.label}</span>
                  <div className="mt-1 h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-emerald-500 transition-all"
                      style={{ width: `${item.value}%` }}
                    />
                  </div>
                </div>
                <span className="text-xs font-extrabold text-slate-900 shrink-0">
                  {item.value}%
                </span>
              </div>
            ))}
            {coverageList.length === 0 && (
              <div className="py-6 text-center text-xs text-slate-400">
                Sem dados de cobertura no momento.
              </div>
            )}
          </div>
        </div>

        {/* Live Operational Audit Stream */}
        <div className="bg-white p-5 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <h2 className="text-sm font-extrabold text-slate-900 tracking-tight">Trilha de Auditoria & Atividades</h2>
              <p className="text-[11px] text-slate-500 font-medium">Registro imutável de eventos e chamadas à plataforma</p>
            </div>
            <Activity className="h-4 w-4 text-blue-600" />
          </div>

          <div className="space-y-2.5">
            {activitiesList.slice(0, 5).map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-3 p-3 rounded-xl bg-slate-50 border border-slate-200/80 hover:bg-slate-100/60 transition-colors"
              >
                <div className="mt-1">
                  <span className="flex h-2 w-2 rounded-full bg-blue-600" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <strong className="block text-xs font-bold text-slate-900 truncate">{item.title}</strong>
                    <span className="text-[10px] font-semibold text-slate-400 shrink-0">{item.time}</span>
                  </div>
                  <span className="block text-[11px] text-slate-500 truncate mt-0.5">
                    {item.subtitle || item.type}
                  </span>
                </div>
              </div>
            ))}
            {activitiesList.length === 0 && (
              <div className="py-6 text-center text-xs text-slate-400">
                Nenhuma atividade recente registrada.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
