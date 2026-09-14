import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowRight,
  Building2,
  CheckCircle2,
  CircleGauge,
  FileUp,
  ListChecks,
  MailCheck,
  PlugZap,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Users,
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

function scoreTone(value: number) {
  if (value >= 80) return { bar: 'bg-emerald-500', text: 'text-emerald-700', label: 'Saudável' };
  if (value >= 55) return { bar: 'bg-amber-500', text: 'text-amber-700', label: 'Em atenção' };
  return { bar: 'bg-red-500', text: 'text-red-700', label: 'Crítica' };
}

export default function Dashboard({ onNavigate }: DashboardProps) {
  const { activities, datasets, lists, workspace } = useLeadStream();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [health, setHealth] = useState<DataHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
  }, [workspace.companies, workspace.contacts]);

  const primaryIssue = useMemo(
    () => health?.issues.filter((issue) => issue.count > 0).sort((a, b) => b.count - a.count)[0],
    [health],
  );
  const score = health?.summary.overallScore ?? 0;
  const tone = scoreTone(score);
  const hasData = (health?.summary.totalEntities ?? 0) > 0;
  const validEmails = dashboard?.summary.validEmails ?? 0;
  const deliverabilityRate = dashboard?.summary.deliverabilityRate ?? 0;

  if (loading) {
    return (
      <div className="mx-auto max-w-[1440px] space-y-5" aria-busy="true">
        <div className="h-40 animate-pulse rounded-[12px] bg-slate-200" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3].map((item) => <div key={item} className="h-28 animate-pulse rounded-[12px] bg-slate-200" />)}
        </div>
        <div className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
          <div className="h-80 animate-pulse rounded-[12px] bg-slate-200" />
          <div className="h-80 animate-pulse rounded-[12px] bg-slate-200" />
        </div>
      </div>
    );
  }

  if (error || !health || !dashboard) {
    return (
      <div className="mx-auto max-w-[1440px] rounded-[12px] bg-red-50 p-6 text-red-950" role="alert">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5" />
          <div>
            <h2 className="font-bold">A central de dados está indisponível</h2>
            <p className="mt-1 text-sm text-red-800">{error}</p>
            <button onClick={() => void load()} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-red-700 px-4 py-2 text-xs font-bold text-white">
              <RefreshCw className="h-3.5 w-3.5" /> Tentar novamente
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1440px] space-y-5">
      <section className="overflow-hidden rounded-[12px] border border-slate-200 bg-white">
        <div className="grid lg:grid-cols-[minmax(0,1.15fr)_minmax(340px,0.85fr)]">
          <div className="p-5 sm:p-7">
            <div className="flex items-center gap-2 text-xs font-semibold text-blue-700">
              <CircleGauge className="h-4 w-4" /> Visão geral da sua base
            </div>
            <h2 className="mt-3 max-w-2xl text-2xl font-bold tracking-[-0.035em] text-slate-950 sm:text-[28px]">
              {hasData ? 'Sua operação começa pela confiança nos dados.' : 'Comece com uma base. A LeadStream mede o resto.'}
            </h2>
            <p className="mt-2 max-w-[68ch] text-sm leading-6 text-slate-600">
              {hasData
                ? 'Veja a cobertura dos seus dados, identifique lacunas e escolha o próximo passo com base no que foi realmente observado.'
                : 'Importe um arquivo CSV ou TXT para identificar lacunas, duplicidades e campos que precisam de revisão.'}
            </p>
            <div className="mt-5 flex flex-wrap gap-2">
              <button
                onClick={() => onNavigate(hasData ? 'data-health' : 'datasets')}
                className="inline-flex items-center gap-2 rounded-[10px] bg-blue-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-blue-700"
              >
                {hasData ? <ShieldCheck className="h-4 w-4" /> : <FileUp className="h-4 w-4" />}
                {hasData ? 'Abrir diagnóstico' : 'Importar primeira base'}
              </button>
              <button
                onClick={() => onNavigate('enrichment')}
                className="inline-flex items-center gap-2 rounded-[10px] border border-slate-300 bg-white px-4 py-2.5 text-xs font-bold text-slate-800 hover:bg-slate-50"
              >
                <Sparkles className="h-4 w-4" /> Enriquecimento
              </button>
            </div>
          </div>

          <div className="border-t border-slate-200 bg-slate-50 p-5 sm:p-7 lg:border-l lg:border-t-0">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs font-semibold text-slate-500">Índice de qualidade</p>
                <div className="mt-1 flex items-baseline gap-2">
                  <strong className="text-4xl font-extrabold tracking-[-0.04em] text-slate-950">{score}</strong>
                  <span className="text-sm font-semibold text-slate-400">/ 100</span>
                </div>
              </div>
              <span className={`rounded-full bg-white px-2.5 py-1 text-[10px] font-bold ${tone.text}`}>{tone.label}</span>
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200">
              <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${score}%` }} />
            </div>
            <div className="mt-5 border-t border-slate-200 pt-4">
              <p className="text-[11px] font-semibold text-slate-700">Próxima melhor ação</p>
              <button
                onClick={() => onNavigate(primaryIssue?.actionRoute ?? (hasData ? 'lists' : 'datasets'))}
                className="mt-2 flex w-full items-start justify-between gap-3 text-left"
              >
                <span>
                  <strong className="block text-xs text-slate-950">
                    {primaryIssue ? primaryIssue.label : hasData ? 'Preparar exportação' : 'Importar uma base'}
                  </strong>
                  <span className="mt-1 block text-[11px] leading-5 text-slate-500">
                    {primaryIssue
                      ? `${primaryIssue.count.toLocaleString('pt-BR')} ${primaryIssue.count === 1 ? 'registro precisa' : 'registros precisam'} de atenção.`
                      : hasData ? 'A base não possui pendências detectadas.' : 'O diagnóstico depende de dados reais.'}
                  </span>
                </span>
                <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-blue-600" />
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="grid overflow-hidden rounded-[12px] border border-slate-200 bg-white sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: 'Empresas e contatos', value: metricValue(health.summary.totalEntities), note: `${health.summary.companies} ${health.summary.companies === 1 ? 'empresa' : 'empresas'} · ${health.summary.contacts} ${health.summary.contacts === 1 ? 'contato' : 'contatos'}`, icon: Building2 },
          { label: 'Registros com canal utilizável', value: metricValue(health.summary.actionableRecords), note: 'Com empresa, pessoa e telefone ou caixa validada', icon: ListChecks },
          { label: 'Caixas validadas tecnicamente', value: metricValue(validEmails), note: `${deliverabilityRate.toLocaleString('pt-BR')}% dos e-mails presentes`, icon: MailCheck },
          { label: 'Registros com data', value: metricValue(health.summary.lineageCoverage, '%'), note: 'Com data de observação ou atualização registrada', icon: ShieldCheck },
        ].map((item, index) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className={`p-5 ${index > 0 ? 'border-t border-slate-200 sm:border-t-0 sm:border-l' : ''} ${index === 2 ? 'sm:border-t xl:border-t-0' : ''}`}>
              <div className="flex items-center justify-between gap-3">
                <span className="text-[11px] font-semibold text-slate-500">{item.label}</span>
                <Icon className="h-4 w-4 text-slate-400" />
              </div>
              <strong className="mt-2 block text-2xl font-extrabold tracking-[-0.035em] text-slate-950">{item.value}</strong>
              <span className="mt-1 block text-[10px] leading-4 text-slate-500">{item.note}</span>
            </div>
          );
        })}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
        <section className="overflow-hidden rounded-[12px] border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="text-sm font-bold text-slate-950">Fluxo operacional</h2>
              <p className="mt-0.5 text-[11px] text-slate-500">Da importação à revisão e exportação controlada.</p>
            </div>
            <Activity className="h-5 w-5 text-slate-400" />
          </div>
          <div className="grid sm:grid-cols-2">
            {[
              { label: 'Importar', value: datasets.length, singular: 'base', plural: 'bases', icon: FileUp, route: 'datasets', state: datasets.length ? 'active' : 'empty' },
              { label: 'Organizar empresas', value: health.summary.companies, singular: 'empresa', plural: 'empresas', icon: Building2, route: 'search', state: health.summary.companies ? 'active' : 'empty' },
              { label: 'Validar qualidade', value: health.summary.actionableRecords, singular: 'acionável', plural: 'acionáveis', icon: ShieldCheck, route: 'data-health', state: health.summary.actionableRecords ? 'active' : 'empty' },
              { label: 'Selecionar e exportar', value: lists.length, singular: 'lista', plural: 'listas', icon: PlugZap, route: 'lists', state: lists.length ? 'active' : 'empty' },
            ].map((stage, index) => {
              const Icon = stage.icon;
              return (
                <button
                  key={stage.label}
                  onClick={() => onNavigate(stage.route)}
                  className={`flex items-center gap-4 p-5 text-left hover:bg-slate-50 ${
                    index % 2 === 1 ? 'sm:border-l sm:border-slate-200' : ''
                  } ${index > 1 ? 'border-t border-slate-200' : index === 1 ? 'border-t border-slate-200 sm:border-t-0' : ''}`}
                >
                  <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[10px] ${
                    stage.state === 'active' ? 'bg-blue-50 text-blue-700' : 'bg-slate-100 text-slate-400'
                  }`}>
                    <Icon className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-bold text-slate-900">{stage.label}</span>
                    <span className="mt-0.5 block text-[11px] text-slate-500">{stage.value.toLocaleString('pt-BR')} {stage.value === 1 ? stage.singular : stage.plural}</span>
                  </span>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400" />
                </button>
              );
            })}
          </div>
        </section>

        <section className="overflow-hidden rounded-[12px] border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-sm font-bold text-slate-950">Próximas ações</h2>
            <p className="mt-0.5 text-[11px] text-slate-500">Ações recomendadas conforme a cobertura registrada.</p>
          </div>
          <div className="divide-y divide-slate-100">
            <button onClick={() => onNavigate('enrichment')} className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-slate-50">
              <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-blue-50 text-blue-700">
                <Sparkles className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <strong className="block text-xs text-slate-900">Consultar dados complementares</strong>
                <span className="block text-[10px] text-slate-500">Veja quais fontes estão configuradas antes de iniciar</span>
              </span>
              <ArrowRight className="h-4 w-4 text-blue-600" />
            </button>
            <button onClick={() => onNavigate('lists')} className="flex w-full items-center gap-3 px-5 py-4 text-left hover:bg-slate-50">
              <span className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-blue-50 text-blue-700">
                <ListChecks className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <strong className="block text-xs text-slate-900">Criar uma lista revisada</strong>
                <span className="block text-[10px] text-slate-500">Organize registros adequados ao objetivo da campanha</span>
              </span>
              <ArrowRight className="h-4 w-4 text-blue-600" />
            </button>
          </div>
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section className="overflow-hidden rounded-[12px] border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="text-sm font-bold text-slate-950">Lacunas prioritárias</h2>
              <p className="mt-0.5 text-[11px] text-slate-500">Cobertura dos campos que mais afetam o uso comercial.</p>
            </div>
            <button onClick={() => onNavigate('data-health')} className="text-[11px] font-bold text-blue-700">Ver todas</button>
          </div>
          <div className="divide-y divide-slate-100 px-5">
            {health.coverage
              .filter((item) => ['cnpj', 'domain', 'email', 'verified-email', 'phone'].includes(item.id))
              .sort((a, b) => a.value - b.value)
              .slice(0, 5)
              .map((item) => (
                <div key={item.id} className="grid grid-cols-[minmax(110px,0.7fr)_1fr_42px] items-center gap-3 py-3">
                  <span className="truncate text-[11px] font-medium text-slate-700">{item.label}</span>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full ${scoreTone(item.value).bar}`} style={{ width: `${item.value}%` }} />
                  </div>
                  <span className="text-right text-[11px] font-bold text-slate-900">{item.value}%</span>
                </div>
              ))}
          </div>
        </section>

        <section className="overflow-hidden rounded-[12px] border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
            <div>
              <h2 className="text-sm font-bold text-slate-950">Atividade recente</h2>
              <p className="mt-0.5 text-[11px] text-slate-500">Acompanhe as ações mais recentes da sua equipe.</p>
            </div>
            <Activity className="h-5 w-5 text-slate-400" />
          </div>
          {activities.length ? (
            <div className="divide-y divide-slate-100">
              {activities.slice(0, 5).map((item) => (
                <div key={item.id} className="flex items-start gap-3 px-5 py-3.5">
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                  <span className="min-w-0 flex-1">
                    <strong className="block truncate text-xs text-slate-900">{item.title}</strong>
                    <span className="mt-0.5 block truncate text-[10px] text-slate-500">{item.subtitle || item.type}</span>
                  </span>
                  <span className="shrink-0 text-[10px] text-slate-400">{item.time}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex min-h-[210px] flex-col items-center justify-center px-6 text-center">
              <CheckCircle2 className="h-6 w-6 text-slate-300" />
              <p className="mt-3 text-xs font-semibold text-slate-700">Nenhuma atividade registrada</p>
              <p className="mt-1 max-w-xs text-[10px] leading-4 text-slate-500">Importações, enriquecimentos e alterações aparecerão aqui.</p>
            </div>
          )}
        </section>
      </div>

      {!hasData && (
        <section className="flex flex-col items-start justify-between gap-4 rounded-[12px] bg-blue-600 p-5 text-white sm:flex-row sm:items-center sm:p-6">
          <div className="flex items-start gap-3">
            <Users className="mt-0.5 h-5 w-5" />
            <div>
              <h2 className="text-sm font-bold">Primeiro marco: uma base diagnosticada</h2>
              <p className="mt-1 text-xs text-blue-100">Importe registros reais e use o relatório de qualidade como baseline comercial.</p>
            </div>
          </div>
          <button onClick={() => onNavigate('datasets')} className="inline-flex shrink-0 items-center gap-2 rounded-[10px] bg-white px-4 py-2.5 text-xs font-bold text-blue-700">
            Começar agora <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </section>
      )}
    </div>
  );
}
