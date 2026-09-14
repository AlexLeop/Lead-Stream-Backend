import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleGauge,
  FileWarning,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  WandSparkles,
  Zap,
} from 'lucide-react';
import { api } from '../api';
import type { DataHealthData } from '../types';

interface DataHealthProps {
  onNavigate: (route: string) => void;
}

const dimensionLabels: Record<keyof DataHealthData['dimensions'], string> = {
  identityScore: 'Identidade empresarial',
  contactabilityScore: 'Contactabilidade',
  profileScore: 'Perfil profissional',
  verificationScore: 'Verificação',
  lineageScore: 'Atualização dos dados',
};

function scoreColor(value: number) {
  if (value >= 80) return 'bg-emerald-500';
  if (value >= 55) return 'bg-amber-500';
  return 'bg-red-500';
}

function severityStyle(severity: string) {
  if (severity === 'high') return { dot: 'bg-red-500', badge: 'bg-red-50 text-red-800', label: 'Alta' };
  if (severity === 'medium') return { dot: 'bg-amber-500', badge: 'bg-amber-50 text-amber-800', label: 'Média' };
  if (severity === 'low') return { dot: 'bg-blue-500', badge: 'bg-blue-50 text-blue-800', label: 'Baixa' };
  return { dot: 'bg-emerald-500', badge: 'bg-emerald-50 text-emerald-800', label: 'Resolvido' };
}

export default function DataHealth({ onNavigate }: DataHealthProps) {
  const [data, setData] = useState<DataHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [isRepairing, setIsRepairing] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.dataHealth());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível calcular a saúde da base.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleAutoRepair = async () => {
    setIsRepairing(true);
    try {
      const result = await api.repairDataHealth();
      setData(result.health);
      setToastMessage('Revisão concluída: nenhum dado foi promovido sem evidência técnica.');
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao executar o reparo da base.');
    } finally {
      setIsRepairing(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-[1440px] space-y-5" aria-busy="true">
        <div className="h-28 animate-pulse rounded-[12px] bg-slate-200" />
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="h-80 animate-pulse rounded-[12px] bg-slate-200" />
          <div className="h-80 animate-pulse rounded-[12px] bg-slate-200" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-[1440px] rounded-[12px] bg-red-50 p-6 text-red-950" role="alert">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5" />
          <div>
            <h2 className="font-bold">O diagnóstico não pôde ser concluído</h2>
            <p className="mt-1 text-sm text-red-800">{error}</p>
            <button onClick={() => void load()} className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-xs font-bold text-white">
              Tentar novamente
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { summary } = data;
  const hasData = summary.totalEntities > 0;
  const distributionTotal = data.distribution.healthy + data.distribution.attention + data.distribution.critical;

  return (
    <div className="mx-auto max-w-[1440px] space-y-5">
      <section className="flex flex-col justify-between gap-5 rounded-[12px] border border-slate-200 bg-white p-5 sm:flex-row sm:items-center sm:p-6">
        <div className="max-w-2xl">
          <div className="flex items-center gap-2 text-xs font-semibold text-blue-700">
            <ShieldCheck className="h-4 w-4" /> Diagnóstico da sua base
          </div>
          <h2 className="mt-2 text-xl font-bold tracking-[-0.03em] text-slate-950">Confiança começa antes do enriquecimento</h2>
          <p className="mt-1.5 max-w-[68ch] text-sm leading-6 text-slate-600">
            O score considera identificação, meios de contato, perfil, validação e atualização das informações.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {hasData && (
            <button
              onClick={handleAutoRepair}
              disabled={isRepairing}
              className="px-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-md shadow-blue-500/10 transition-all flex items-center gap-2 cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-200" />
              <span>{isRepairing ? 'Revisando…' : 'Revisar classificação segura'}</span>
            </button>
          )}
          <span className="text-right text-[11px] text-slate-500">
            Atualizado
            <strong className="block font-semibold text-slate-800">
              {new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(data.generatedAt))}
            </strong>
          </span>
          <button
            onClick={() => void load()}
            className="rounded-lg border border-slate-200 p-2.5 text-slate-700 hover:bg-slate-50"
            aria-label="Recalcular diagnóstico"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </section>

      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-2xl border border-slate-800 flex items-center gap-2.5 text-xs font-semibold animate-in fade-in slide-in-from-bottom-3 duration-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      <section className="rounded-[12px] border border-amber-200 bg-amber-50/60 p-5 sm:p-6" aria-labelledby="quarantine-title">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
          <div className="flex max-w-2xl items-start gap-3">
            <div className="mt-0.5 rounded-lg bg-amber-100 p-2 text-amber-800">
              <ShieldAlert className="h-5 w-5" aria-hidden="true" />
            </div>
            <div>
              <h2 id="quarantine-title" className="text-sm font-bold text-slate-950">Registros isolados por segurança</h2>
              <p className="mt-1 text-xs leading-5 text-slate-700">
                Registros isolados por segurança não aparecem em busca, métricas ou exportações.
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-3 gap-3 text-center sm:min-w-[360px]">
            <div className="rounded-lg border border-amber-200 bg-white px-3 py-2.5">
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Isolados</dt>
              <dd className="mt-1 text-lg font-extrabold text-slate-950">{data.quarantine.quarantined}</dd>
            </div>
            <div className="rounded-lg border border-amber-200 bg-white px-3 py-2.5">
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Em revisão</dt>
              <dd className="mt-1 text-lg font-extrabold text-slate-950">{data.quarantine.pendingReview}</dd>
            </div>
            <div className="rounded-lg border border-amber-200 bg-white px-3 py-2.5">
              <dt className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Liberados</dt>
              <dd className="mt-1 text-lg font-extrabold text-slate-950">{data.quarantine.released}</dd>
            </div>
          </dl>
        </div>
        {data.quarantine.lastClassifiedAt && (
          <p className="mt-3 text-[10px] text-slate-500">
            Última classificação: {new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(data.quarantine.lastClassifiedAt))}
          </p>
        )}
      </section>

      {!hasData ? (
        <section className="rounded-[12px] border border-dashed border-slate-300 bg-white px-6 py-14 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-[12px] bg-blue-50 text-blue-700">
            <FileWarning className="h-5 w-5" />
          </div>
          <h2 className="mt-4 text-lg font-bold text-slate-950">Importe uma base para receber o primeiro diagnóstico</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-slate-600">
            A LeadStream mostrará campos ausentes, registros acionáveis e possíveis duplicidades para você priorizar as melhorias certas.
          </p>
          <button
            onClick={() => onNavigate('datasets')}
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-blue-700"
          >
            Importar base <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </section>
      ) : (
        <>
          <div className="grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(420px,1.1fr)]">
            <section className="rounded-[12px] border border-slate-200 bg-white p-5 sm:p-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-semibold text-slate-500">Score geral da base</p>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="text-4xl font-extrabold tracking-[-0.04em] text-slate-950">{summary.overallScore}</span>
                    <span className="text-sm font-semibold text-slate-400">/ 100</span>
                  </div>
                </div>
                <CircleGauge className="h-6 w-6 text-blue-600" />
              </div>
              <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100" aria-label={`Score geral: ${summary.overallScore}%`}>
                <div className={`h-full rounded-full ${scoreColor(summary.overallScore)}`} style={{ width: `${summary.overallScore}%` }} />
              </div>

              <div className="mt-7 divide-y divide-slate-100">
                {(Object.entries(data.dimensions) as Array<[keyof DataHealthData['dimensions'], number]>).map(([key, value]) => (
                  <div key={key} className="grid grid-cols-[1fr_48px] items-center gap-4 py-3">
                    <div>
                      <div className="mb-1.5 flex items-center justify-between gap-3">
                        <span className="text-xs font-medium text-slate-700">{dimensionLabels[key]}</span>
                        <span className="text-[11px] font-bold text-slate-900">{value}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                        <div className={`h-full rounded-full ${scoreColor(value)}`} style={{ width: `${value}%` }} />
                      </div>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-center text-[10px] font-bold ${
                      value >= 80 ? 'bg-emerald-50 text-emerald-800' : value >= 55 ? 'bg-amber-50 text-amber-800' : 'bg-red-50 text-red-800'
                    }`}>
                      {value >= 80 ? 'Boa' : value >= 55 ? 'Atenção' : 'Crítica'}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            <section className="overflow-hidden rounded-[12px] border border-slate-200 bg-white">
              <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
                <div>
                  <h2 className="text-sm font-bold text-slate-950">Fila de qualidade</h2>
                  <p className="mt-0.5 text-[11px] text-slate-500">Problemas priorizados por impacto operacional.</p>
                </div>
                <FileWarning className="h-5 w-5 text-slate-400" />
              </div>
              <div className="divide-y divide-slate-100">
                {data.issues.map((issue) => {
                  const style = severityStyle(issue.severity);
                  return (
                    <button
                      key={issue.id}
                      onClick={() => onNavigate(issue.actionRoute)}
                      className="flex w-full items-start gap-4 px-5 py-4 text-left hover:bg-slate-50"
                    >
                      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                      <span className="min-w-0 flex-1">
                        <span className="flex flex-wrap items-center gap-2">
                          <strong className="text-xs text-slate-900">{issue.label}</strong>
                          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${style.badge}`}>{style.label}</span>
                        </span>
                        <span className="mt-1 block text-[11px] leading-5 text-slate-500">{issue.description}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2 text-sm font-extrabold text-slate-950">
                        {issue.count.toLocaleString('pt-BR')} <ArrowRight className="h-3.5 w-3.5 text-slate-400" />
                      </span>
                    </button>
                  );
                })}
              </div>
            </section>
          </div>

          <section className="overflow-hidden rounded-[12px] border border-slate-200 bg-white">
            <div className="flex flex-col justify-between gap-3 border-b border-slate-200 px-5 py-4 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-sm font-bold text-slate-950">Cobertura por campo crítico</h2>
                <p className="mt-0.5 text-[11px] text-slate-500">O denominador respeita o tipo de entidade de cada campo.</p>
              </div>
              <button onClick={() => onNavigate('enrichment')} className="inline-flex items-center gap-2 text-xs font-bold text-blue-700">
                Planejar correção <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[700px] text-left">
                <thead className="bg-slate-50 text-[10px] font-semibold text-slate-500">
                  <tr>
                    <th className="px-5 py-3">Campo</th>
                    <th className="px-5 py-3">Cobertura</th>
                    <th className="px-5 py-3">Encontrados</th>
                    <th className="px-5 py-3">Leitura</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.coverage.map((item) => (
                    <tr key={item.id}>
                      <td className="px-5 py-3.5 text-xs font-semibold text-slate-900">{item.label}</td>
                      <td className="w-[38%] px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                            <div className={`h-full rounded-full ${scoreColor(item.value)}`} style={{ width: `${item.value}%` }} />
                          </div>
                          <span className="w-10 text-right text-[11px] font-bold text-slate-800">{item.value}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-slate-600">
                        {item.count.toLocaleString('pt-BR')} de {item.total.toLocaleString('pt-BR')}
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`inline-flex rounded-full px-2 py-1 text-[10px] font-bold ${
                          item.value >= 80 ? 'bg-emerald-50 text-emerald-800' : item.value >= 55 ? 'bg-amber-50 text-amber-800' : 'bg-red-50 text-red-800'
                        }`}>
                          {item.value >= 80 ? 'Confiável' : item.value >= 55 ? 'Parcial' : 'Lacuna'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
            <section className="rounded-[12px] border border-slate-200 bg-white p-5">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <h2 className="text-sm font-bold text-slate-950">Distribuição operacional dos contatos</h2>
              </div>
              <div className="mt-5 flex h-3 overflow-hidden rounded-full bg-slate-100">
                {distributionTotal > 0 && (
                  <>
                    <div className="bg-emerald-500" style={{ width: `${(data.distribution.healthy / distributionTotal) * 100}%` }} />
                    <div className="bg-amber-500" style={{ width: `${(data.distribution.attention / distributionTotal) * 100}%` }} />
                    <div className="bg-red-500" style={{ width: `${(data.distribution.critical / distributionTotal) * 100}%` }} />
                  </>
                )}
              </div>
              <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-[11px] text-slate-600">
                <span><i className="mr-2 inline-block h-2 w-2 rounded-full bg-emerald-500" />{data.distribution.healthy} {data.distribution.healthy === 1 ? 'acionável' : 'acionáveis'}</span>
                <span><i className="mr-2 inline-block h-2 w-2 rounded-full bg-amber-500" />{data.distribution.attention} em atenção</span>
                <span><i className="mr-2 inline-block h-2 w-2 rounded-full bg-red-500" />{data.distribution.critical} críticos</span>
              </div>
            </section>
            <aside className="rounded-[12px] bg-slate-900 p-5 text-white">
              <p className="text-xs font-bold">Como interpretar</p>
              <p className="mt-2 text-[11px] leading-5 text-slate-300">
                “Acionável” exige vínculo empresarial, cargo e ao menos e-mail com evidência técnica ou telefone observado. Score zero significa ausência de evidência — não reprovação do registro.
              </p>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
