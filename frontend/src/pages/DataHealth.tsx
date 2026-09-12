import { useEffect, useMemo, useState } from 'react';
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
import { ensureArray, type DataHealthData } from '../types';

interface DataHealthProps {
  onNavigate: (route: string) => void;
}

const dimensionLabels: Record<keyof DataHealthData['dimensions'], string> = {
  identityScore: 'Identidade empresarial (Receita Federal)',
  contactabilityScore: 'Contactabilidade (Email / Telefone)',
  profileScore: 'Perfil profissional & Decisores',
  verificationScore: 'Verificação Zero-Bounce RFC 5321',
  lineageScore: 'Atualização & Linhagem dos dados',
};

function scoreColor(value: number) {
  if (value >= 80) return 'bg-emerald-500';
  if (value >= 55) return 'bg-amber-500';
  return 'bg-rose-500';
}

function severityStyle(severity: string) {
  if (severity === 'high') return { dot: 'bg-rose-500', badge: 'bg-rose-50 text-rose-700 border border-rose-200', label: 'Alta' };
  if (severity === 'medium') return { dot: 'bg-amber-500', badge: 'bg-amber-50 text-amber-700 border border-amber-200', label: 'Média' };
  if (severity === 'low') return { dot: 'bg-blue-500', badge: 'bg-blue-50 text-blue-700 border border-blue-200', label: 'Baixa' };
  return { dot: 'bg-emerald-500', badge: 'bg-emerald-50 text-emerald-700 border border-emerald-200', label: 'Resolvido' };
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

  const issuesList = useMemo(() => ensureArray<{ id: string; label: string; description: string; severity: string; count: number; actionRoute: string }>(data?.issues), [data]);
  const coverageList = useMemo(() => ensureArray<{ id: string; label: string; value: number; count: number; total: number }>(data?.coverage), [data]);

  const handleAutoRepair = async () => {
    setIsRepairing(true);
    try {
      const result = await api.repairDataHealth();
      setData(result.health);
      setToastMessage('Revisão concluída: nenhum dado foi promovido sem evidência técnica auditável.');
      setTimeout(() => setToastMessage(null), 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha ao executar o reparo da base.');
    } finally {
      setIsRepairing(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 max-w-[1440px] mx-auto pb-8" aria-busy="true">
        <div className="h-28 animate-pulse rounded-2xl bg-white border border-slate-200" />
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="h-80 animate-pulse rounded-2xl bg-white border border-slate-200" />
          <div className="h-80 animate-pulse rounded-2xl bg-white border border-slate-200" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-rose-900 max-w-[1440px] mx-auto" role="alert">
        <div className="flex items-start gap-4">
          <div className="rounded-xl bg-rose-100 p-2.5 border border-rose-200 text-rose-600">
            <AlertTriangle className="h-6 w-6" />
          </div>
          <div className="space-y-2 flex-1">
            <h2 className="text-base font-bold text-rose-950 tracking-tight">O diagnóstico não pôde ser concluído</h2>
            <p className="text-xs text-rose-800 leading-relaxed max-w-2xl">{error}</p>
            <button
              onClick={() => void load()}
              className="mt-3 inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-700 px-4 py-2 text-xs font-bold text-white transition-colors cursor-pointer shadow-xs"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Tentar novamente
            </button>
          </div>
        </div>
      </div>
    );
  }

  const { summary } = data;
  const hasData = (summary?.totalEntities ?? 0) > 0;

  return (
    <div className="space-y-6 max-w-[1440px] mx-auto pb-8">
      {/* Toast */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-2xl border border-slate-800 flex items-center gap-2.5 text-xs font-semibold animate-in fade-in slide-in-from-bottom-3 duration-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Header Diagnostic Strip (Light MVP Style) */}
      <div className="bg-white p-5 sm:p-6 rounded-[12px] border border-slate-200 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-5">
        <div className="max-w-2xl space-y-1.5">
          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-700 border border-blue-200">
            <ShieldCheck className="h-3.5 w-3.5" /> Diagnóstico de Confiabilidade Cadastral
          </div>
          <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
            Confiança e Linhagem de Dados
          </h1>
          <p className="text-slate-500 text-xs sm:text-sm font-medium leading-relaxed">
            Métricas de integridade contínua: identificação CNPJ/QSA, validade RFC 5321, canal móvel observável e trilha de auditoria técnica.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {hasData && (
            <button
              onClick={handleAutoRepair}
              disabled={isRepairing}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold text-xs rounded-xl transition-all flex items-center gap-2 cursor-pointer shadow-xs"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-200" />
              <span>{isRepairing ? 'Revisando...' : 'Revisar Classificação'}</span>
            </button>
          )}
          <span className="text-right text-[11px] text-slate-400 font-medium">
            Atualizado
            <strong className="block font-bold text-slate-700">
              {new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(data.generatedAt || Date.now()))}
            </strong>
          </span>
          <button
            onClick={() => void load()}
            className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-600 hover:text-slate-900 hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs"
            title="Recalcular diagnóstico"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Quarantine Banner */}
      <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5 sm:p-6 text-amber-950">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
          <div className="flex max-w-2xl items-start gap-3.5">
            <div className="rounded-xl bg-amber-100 p-2.5 text-amber-700 border border-amber-200 shrink-0">
              <ShieldAlert className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-sm font-extrabold text-amber-950 tracking-tight">
                Registros Isolados por Segurança & LGPD
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-amber-800 font-medium">
                Registros que falharam em validações de consentimento, sintaxe RFC 5321 ou suspeita de honeypot ficam isolados e não afetam o score da sua base ativa.
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-3 gap-3 text-center sm:min-w-[360px]">
            <div className="rounded-xl border border-amber-200/80 bg-white p-3 shadow-2xs">
              <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Isolados</dt>
              <dd className="mt-1 text-lg font-extrabold text-slate-900">{data.quarantine?.quarantined ?? 0}</dd>
            </div>
            <div className="rounded-xl border border-amber-200/80 bg-white p-3 shadow-2xs">
              <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Em Revisão</dt>
              <dd className="mt-1 text-lg font-extrabold text-slate-900">{data.quarantine?.pendingReview ?? 0}</dd>
            </div>
            <div className="rounded-xl border border-amber-200/80 bg-white p-3 shadow-2xs">
              <dt className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Liberados</dt>
              <dd className="mt-1 text-lg font-extrabold text-emerald-700">{data.quarantine?.released ?? 0}</dd>
            </div>
          </dl>
        </div>
      </div>

      {!hasData ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-14 text-center shadow-xs">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 border border-blue-100">
            <FileWarning className="h-6 w-6" />
          </div>
          <h2 className="mt-4 text-base font-extrabold text-slate-900">Importe uma base para receber o primeiro diagnóstico</h2>
          <p className="mx-auto mt-2 max-w-xl text-xs leading-relaxed text-slate-500">
            A LeadStream mapeará campos ausentes, decisores QSA e integridade de e-mails para garantir máxima entregabilidade.
          </p>
          <button
            onClick={() => onNavigate('datasets')}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-blue-600 hover:bg-blue-700 px-4 py-2.5 text-xs font-bold text-white transition-all cursor-pointer shadow-xs"
          >
            Importar Base <ArrowRight className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <>
          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            {/* Score & Dimensions */}
            <div className="bg-white p-5 sm:p-6 rounded-2xl border border-slate-200/90 shadow-xs space-y-5">
              <div className="flex items-start justify-between border-b border-slate-100 pb-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Score Geral de Integridade</p>
                  <div className="mt-1 flex items-baseline gap-2">
                    <span className="text-4xl font-extrabold text-slate-900">{summary?.overallScore ?? 0}</span>
                    <span className="text-sm font-semibold text-slate-400">/ 100</span>
                  </div>
                </div>
                <div className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100 flex items-center justify-center font-bold">
                  <CircleGauge className="h-6 w-6" />
                </div>
              </div>

              <div className="space-y-4 divide-y divide-slate-100">
                {data.dimensions && (Object.entries(data.dimensions) as Array<[keyof DataHealthData['dimensions'], number]>).map(([key, value]) => (
                  <div key={key} className="pt-3.5 first:pt-0 grid grid-cols-[1fr_70px] items-center gap-4">
                    <div>
                      <div className="mb-1.5 flex items-center justify-between gap-3 text-xs">
                        <span className="font-semibold text-slate-700">{dimensionLabels[key] || key}</span>
                        <span className="font-extrabold text-slate-900">{value}%</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div className={`h-full rounded-full transition-all ${scoreColor(value)}`} style={{ width: `${value}%` }} />
                      </div>
                    </div>
                    <span className={`rounded-full px-2.5 py-0.5 text-center text-[10px] font-extrabold uppercase ${
                      value >= 80 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : value >= 55 ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-rose-50 text-rose-700 border border-rose-200'
                    }`}>
                      {value >= 80 ? 'Boa' : value >= 55 ? 'Atenção' : 'Crítica'}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Quality Queue */}
            <div className="bg-white p-5 sm:p-6 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                <div>
                  <h2 className="text-sm font-extrabold text-slate-900 tracking-tight">Fila de Prioridades Cadastrais</h2>
                  <p className="text-[11px] text-slate-500 font-medium">Campos sugeridos para enriquecimento complementar</p>
                </div>
                <FileWarning className="h-5 w-5 text-slate-400" />
              </div>

              <div className="space-y-2.5">
                {issuesList.length > 0 ? (
                  issuesList.map((issue) => {
                    const style = severityStyle(issue.severity);
                    return (
                      <button
                        key={issue.id}
                        onClick={() => onNavigate(issue.actionRoute)}
                        className="flex w-full items-start gap-3.5 p-3.5 rounded-xl bg-slate-50 border border-slate-200/80 hover:border-blue-300 hover:bg-blue-50/40 transition-all text-left cursor-pointer group"
                      >
                        <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <strong className="text-xs font-bold text-slate-900 group-hover:text-blue-700 transition-colors">{issue.label}</strong>
                            <span className={`rounded-full px-2 py-0.5 text-[9px] font-extrabold uppercase ${style.badge}`}>{style.label}</span>
                          </div>
                          <p className="mt-1 text-[11px] text-slate-500 font-medium leading-relaxed">{issue.description}</p>
                        </div>
                        <span className="flex shrink-0 items-center gap-1 text-xs font-extrabold text-slate-900">
                          {issue.count} <ArrowRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-blue-600 transition-colors" />
                        </span>
                      </button>
                    );
                  })
                ) : (
                  <div className="p-8 text-center text-xs text-slate-500 space-y-1">
                    <CheckCircle2 className="w-7 h-7 text-emerald-500 mx-auto mb-2" />
                    <p className="font-extrabold text-slate-900">Base plenamente saneada</p>
                    <p className="text-[11px] text-slate-500">Nenhuma inconformidade técnica detectada nas contas ativas.</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Coverage Table */}
          <div className="bg-white p-5 sm:p-6 rounded-2xl border border-slate-200/90 shadow-xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
              <div>
                <h2 className="text-sm font-extrabold text-slate-900 tracking-tight">Cobertura por Atributo Chave</h2>
                <p className="text-[11px] text-slate-500 font-medium">Relação de preenchimento dos campos exigidos para prospecção outbound</p>
              </div>
              <button
                onClick={() => onNavigate('enrichment')}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors cursor-pointer"
              >
                Planejar Enriquecimento <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left font-sans">
                <thead className="text-[11px] font-bold uppercase tracking-wider text-slate-400 border-b border-slate-200 bg-slate-50/50">
                  <tr>
                    <th className="py-2.5 px-3">Atributo</th>
                    <th className="py-2.5 px-3">Cobertura (%)</th>
                    <th className="py-2.5 px-3">Registros Úteis</th>
                    <th className="py-2.5 px-3">Classificação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-xs">
                  {coverageList.map((item) => (
                    <tr key={item.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-3 font-semibold text-slate-800">{item.label}</td>
                      <td className="py-3 px-3 w-[40%]">
                        <div className="flex items-center gap-3">
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
                            <div className={`h-full rounded-full transition-all ${scoreColor(item.value)}`} style={{ width: `${item.value}%` }} />
                          </div>
                          <span className="w-10 text-right font-extrabold text-slate-900 text-[11px]">{item.value}%</span>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-slate-500 font-medium text-[11px]">
                        {item.count} de {item.total}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[10px] font-extrabold uppercase ${
                          item.value >= 80 ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : item.value >= 55 ? 'bg-amber-50 text-amber-700 border border-amber-200' : 'bg-rose-50 text-rose-700 border border-rose-200'
                        }`}>
                          {item.value >= 80 ? 'Confiável' : item.value >= 55 ? 'Parcial' : 'Lacuna'}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {coverageList.length === 0 && (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-xs text-slate-400">
                        Nenhum registro de cobertura disponível.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
