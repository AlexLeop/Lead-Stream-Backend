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
  return 'bg-rose-500';
}

function severityStyle(severity: string) {
  if (severity === 'high') return { dot: 'bg-rose-500', badge: 'bg-rose-500/10 text-rose-400 border border-rose-500/20', label: 'Alta' };
  if (severity === 'medium') return { dot: 'bg-amber-500', badge: 'bg-amber-500/10 text-amber-400 border border-amber-500/20', label: 'Média' };
  if (severity === 'low') return { dot: 'bg-sky-500', badge: 'bg-sky-500/10 text-sky-400 border border-sky-500/20', label: 'Baixa' };
  return { dot: 'bg-emerald-500', badge: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20', label: 'Resolvido' };
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
      <div className="space-y-6" aria-busy="true">
        <div className="h-28 animate-pulse rounded-xl bg-[#12141C] border border-white/5" />
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="h-80 animate-pulse rounded-xl bg-[#12141C] border border-white/5" />
          <div className="h-80 animate-pulse rounded-xl bg-[#12141C] border border-white/5" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-xl border border-rose-500/20 bg-[#12141C] p-6 text-rose-300" role="alert">
        <div className="flex items-start gap-4">
          <div className="rounded-lg bg-rose-500/10 p-2.5 border border-rose-500/20 text-rose-400">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div className="space-y-2 flex-1">
            <h2 className="text-base font-bold text-white tracking-tight">O diagnóstico não pôde ser concluído</h2>
            <p className="text-xs text-rose-400/90 leading-relaxed max-w-2xl">{error}</p>
            <button
              onClick={() => void load()}
              className="mt-3 inline-flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-xs font-semibold text-white transition-colors cursor-pointer"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Tentar novamente
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
    <div className="space-y-6">
      {/* Header Diagnostic Strip */}
      <section className="flex flex-col justify-between gap-5 rounded-xl border border-white/10 bg-[#12141C] p-6 sm:flex-row sm:items-center">
        <div className="max-w-2xl space-y-1.5">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <ShieldCheck className="h-3.5 w-3.5" /> Diagnóstico de Confiabilidade Cadastral
          </div>
          <h1 className="text-xl font-bold tracking-tight text-white">Confiança e Linhagem de Dados</h1>
          <p className="text-xs text-slate-400 leading-relaxed">
            Métricas de integridade contínua: identificação CNPJ/QSA, validade RFC 5321, canal móvel observável e trilha de auditoria.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {hasData && (
            <button
              onClick={handleAutoRepair}
              disabled={isRepairing}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs rounded-lg transition-colors flex items-center gap-2 cursor-pointer shadow-md shadow-emerald-950/50"
            >
              <Sparkles className="w-3.5 h-3.5 text-emerald-200" />
              <span>{isRepairing ? 'Revisando...' : 'Revisar Classificação'}</span>
            </button>
          )}
          <span className="text-right text-[11px] font-mono text-slate-500">
            Atualizado
            <strong className="block font-semibold text-slate-300">
              {new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(data.generatedAt))}
            </strong>
          </span>
          <button
            onClick={() => void load()}
            className="rounded-lg border border-white/10 bg-white/[0.03] p-2 text-slate-400 hover:text-white hover:border-white/20 transition-colors cursor-pointer"
            title="Recalcular diagnóstico"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </section>

      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-[#12141C] text-white px-4 py-3 rounded-xl shadow-2xl border border-emerald-500/30 flex items-center gap-2.5 text-xs font-semibold animate-in fade-in slide-in-from-bottom-3 duration-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Quarantine Banner */}
      <section className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5 sm:p-6">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
          <div className="flex max-w-2xl items-start gap-3">
            <div className="rounded-lg bg-amber-500/10 p-2 text-amber-400 border border-amber-500/20">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white tracking-tight">Registros Isolados por Segurança & LGPD</h2>
              <p className="mt-1 text-xs leading-relaxed text-amber-300/80">
                Registros que falharam em validações de consentimento, syntax RFC 5321 ou suspeita de honeypot ficam isolados e não afetam o score.
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-3 gap-3 text-center sm:min-w-[360px]">
            <div className="rounded-lg border border-white/10 bg-[#12141C] px-3 py-2.5">
              <dt className="text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-500">Isolados</dt>
              <dd className="mt-1 text-lg font-mono font-bold text-white">{data.quarantine.quarantined}</dd>
            </div>
            <div className="rounded-lg border border-white/10 bg-[#12141C] px-3 py-2.5">
              <dt className="text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-500">Em Revisão</dt>
              <dd className="mt-1 text-lg font-mono font-bold text-white">{data.quarantine.pendingReview}</dd>
            </div>
            <div className="rounded-lg border border-white/10 bg-[#12141C] px-3 py-2.5">
              <dt className="text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-500">Liberados</dt>
              <dd className="mt-1 text-lg font-mono font-bold text-emerald-400">{data.quarantine.released}</dd>
            </div>
          </dl>
        </div>
      </section>

      {!hasData ? (
        <section className="rounded-xl border border-dashed border-white/10 bg-[#12141C] px-6 py-14 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-white/5 text-slate-400">
            <FileWarning className="h-5 w-5" />
          </div>
          <h2 className="mt-4 text-base font-bold text-white">Importe uma base para receber o primeiro diagnóstico</h2>
          <p className="mx-auto mt-2 max-w-xl text-xs leading-relaxed text-slate-400">
            A LeadStream mapeará campos ausentes, decisores QSA e integridade de e-mails para garantir máxima entregabilidade.
          </p>
          <button
            onClick={() => onNavigate('datasets')}
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-4 py-2.5 text-xs font-semibold text-white transition-colors cursor-pointer"
          >
            Importar Base <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </section>
      ) : (
        <>
          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            {/* Score & Dimensions */}
            <section className="rounded-xl border border-white/10 bg-[#12141C] p-6 space-y-6">
              <div className="flex items-start justify-between border-b border-white/10 pb-4">
                <div>
                  <p className="text-xs font-semibold text-slate-400">Score Geral de Integridade</p>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="text-4xl font-bold font-mono text-emerald-400">{summary.overallScore}</span>
                    <span className="text-sm font-mono text-slate-500">/ 100</span>
                  </div>
                </div>
                <CircleGauge className="h-6 w-6 text-emerald-400" />
              </div>

              <div className="space-y-4 divide-y divide-white/5">
                {(Object.entries(data.dimensions) as Array<[keyof DataHealthData['dimensions'], number]>).map(([key, value]) => (
                  <div key={key} className="pt-3 first:pt-0 grid grid-cols-[1fr_56px] items-center gap-4">
                    <div>
                      <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
                        <span className="font-medium text-slate-300">{dimensionLabels[key]}</span>
                        <span className="font-mono text-slate-400">{value}%</span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/5">
                        <div className={`h-full rounded-full ${scoreColor(value)}`} style={{ width: `${value}%` }} />
                      </div>
                    </div>
                    <span className={`rounded px-2 py-0.5 text-center text-[10px] font-mono font-bold uppercase ${
                      value >= 80 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : value >= 55 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                    }`}>
                      {value >= 80 ? 'Boa' : value >= 55 ? 'Atenção' : 'Crítica'}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            {/* Quality Queue */}
            <section className="rounded-xl border border-white/10 bg-[#12141C] p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <h2 className="text-sm font-bold text-white tracking-tight">Fila de Prioridades Cadastrais</h2>
                  <p className="text-[11px] text-slate-400">Campos sugeridos para enriquecimento complementar</p>
                </div>
                <FileWarning className="h-4 w-4 text-slate-500" />
              </div>

              <div className="space-y-3">
                {data.issues.length ? (
                  data.issues.map((issue) => {
                    const style = severityStyle(issue.severity);
                    return (
                      <button
                        key={issue.id}
                        onClick={() => onNavigate(issue.actionRoute)}
                        className="flex w-full items-start gap-4 p-3 rounded-lg bg-white/[0.02] border border-white/5 hover:border-emerald-500/30 transition-colors text-left cursor-pointer"
                      >
                        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <strong className="text-xs text-white">{issue.label}</strong>
                            <span className={`rounded px-1.5 py-0.5 text-[9px] font-mono uppercase ${style.badge}`}>{style.label}</span>
                          </div>
                          <p className="mt-1 text-[11px] text-slate-400 leading-relaxed">{issue.description}</p>
                        </div>
                        <span className="flex shrink-0 items-center gap-1.5 text-xs font-mono font-bold text-white">
                          {issue.count} <ArrowRight className="h-3.5 w-3.5 text-slate-500" />
                        </span>
                      </button>
                    );
                  })
                ) : (
                  <div className="p-8 text-center text-xs text-slate-400 space-y-1">
                    <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto mb-2" />
                    <p className="font-semibold text-white">Base plenamente saneada</p>
                    <p className="text-[11px] text-slate-500">Nenhuma inconformidade técnica detectada nas contas ativas.</p>
                  </div>
                )}
              </div>
            </section>
          </div>

          {/* Coverage Table */}
          <section className="rounded-xl border border-white/10 bg-[#12141C] p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-white/10 pb-4">
              <div>
                <h2 className="text-sm font-bold text-white tracking-tight">Cobertura por Atributo Chave</h2>
                <p className="text-[11px] text-slate-400">Relação de preenchimento dos campos exigidos para prospecção outbound</p>
              </div>
              <button
                onClick={() => onNavigate('enrichment')}
                className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold text-emerald-400 hover:text-emerald-300 transition-colors cursor-pointer"
              >
                Planejar Enriquecimento <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left font-sans">
                <thead className="text-[10px] font-mono uppercase tracking-wider text-slate-500 border-b border-white/5">
                  <tr>
                    <th className="py-2.5 px-3">Atributo</th>
                    <th className="py-2.5 px-3">Cobertura (%)</th>
                    <th className="py-2.5 px-3">Registros Úteis</th>
                    <th className="py-2.5 px-3">Classificação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-xs">
                  {data.coverage.map((item) => (
                    <tr key={item.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-3 px-3 font-medium text-white">{item.label}</td>
                      <td className="py-3 px-3 w-[40%]">
                        <div className="flex items-center gap-3">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/5">
                            <div className={`h-full rounded-full ${scoreColor(item.value)}`} style={{ width: `${item.value}%` }} />
                          </div>
                          <span className="w-10 text-right font-mono font-bold text-white text-[11px]">{item.value}%</span>
                        </div>
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-400 text-[11px]">
                        {item.count} de {item.total}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`inline-flex rounded px-2 py-0.5 text-[10px] font-mono font-bold uppercase ${
                          item.value >= 80 ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : item.value >= 55 ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
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
        </>
      )}
    </div>
  );
}
