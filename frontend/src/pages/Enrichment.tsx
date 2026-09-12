import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  LoaderCircle,
  Search,
  Sparkles,
  WandSparkles,
  X,
  Zap,
  Info,
  SlidersHorizontal,
  ShieldCheck,
} from 'lucide-react';
import { api } from '../api';
import { useLeadStream } from '../LeadStreamContext';
import type {
  CompanyEnrichmentResult,
  EnrichmentCatalog,
  EnrichmentRun,
  EnrichmentStatus,
  PixLookupStatus,
} from '../types';

interface EnrichmentProps {
  onNavigate: (route: string) => void;
}

interface CnpjBatchProgress {
  batchId?: string;
  id?: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'PARTIAL' | 'FAILED';
  totalRequested?: number;
  totalUnique?: number;
  totalValidCnpjs?: number;
  invalidCnpjs?: number;
  duplicatesRemoved?: number;
  totalCnpjs?: number;
  processedCnpjs?: number;
  successCount?: number;
  partialCount?: number;
  failedCount?: number;
  invalidItems?: Array<{ raw: string; formatted: string; reason: string; digits?: string; digitCount?: number }>;
}

interface PreflightInvalidItem {
  raw: string;
  digits: string;
  digitCount: number;
  reason: string;
}

const terminalBatchStatuses = new Set<CnpjBatchProgress['status']>(['COMPLETED', 'PARTIAL', 'FAILED']);

const CNPJ_WEIGHTS_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
const CNPJ_WEIGHTS_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];

function cnpjCharacterValue(character: string) {
  return character.charCodeAt(0) - 48;
}

function mod11Cnpj(characters: string[], weights: number[]) {
  const sum = characters.reduce((acc, character, index) => (
    acc + cnpjCharacterValue(character) * weights[index]
  ), 0);
  const r = sum % 11;
  return r < 2 ? 0 : 11 - r;
}

function preflightCnpj(raw: string): { digits: string; valid: boolean; reason?: string } {
  const trimmed = String(raw || '').trim();
  const digits = trimmed.toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (digits.length !== 14) {
    return {
      digits,
      valid: false,
      reason: `Comprimento inválido (${digits.length} caracteres; são necessários 14).`,
    };
  }
  if (!/^[A-Z0-9]{12}\d{2}$/.test(digits)) {
    return { digits, valid: false, reason: 'Os 12 primeiros caracteres podem ser alfanuméricos; os dois verificadores devem ser números.' };
  }
  if (/^([A-Z0-9])\1{11}\d{2}$/.test(digits)) {
    return { digits, valid: false, reason: 'A base do CNPJ não pode repetir o mesmo caractere em todas as posições.' };
  }
  const first12 = digits.slice(0, 12).split('');
  const dv1 = mod11Cnpj(first12, CNPJ_WEIGHTS_1);
  if (dv1 !== Number(digits[12])) {
    return { digits, valid: false, reason: `Primeiro dígito verificador inválido (esperado ${dv1}, encontrado ${digits[12]}).` };
  }
  const dv2 = mod11Cnpj([...first12, String(dv1)], CNPJ_WEIGHTS_2);
  if (dv2 !== Number(digits[13])) {
    return { digits, valid: false, reason: `Segundo dígito verificador inválido (esperado ${dv2}, encontrado ${digits[13]}).` };
  }
  return { digits, valid: true };
}

function formatCnpj(digits: string) {
  if (digits.length !== 14) return digits;
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12, 14)}`;
}

function runStatus(run: EnrichmentRun) {
  if (run.status === 'COMPLETED') return { label: 'Concluído', className: 'bg-emerald-50 text-emerald-800' };
  if (run.status === 'FAILED') return { label: 'Falhou', className: 'bg-red-50 text-red-800' };
  return { label: 'Processando', className: 'bg-blue-50 text-blue-800' };
}

function sectionState(status: CompanyEnrichmentResult['sections'][number]['status']) {
  if (status === 'available') return { label: 'Dados encontrados', className: 'text-emerald-700', dot: 'bg-emerald-500' };
  if (status === 'unavailable') return { label: 'Tente novamente', className: 'text-amber-700', dot: 'bg-amber-500' };
  return { label: 'Sem registros', className: 'text-slate-500', dot: 'bg-slate-300' };
}

function formatRunDate(value: string) {
  const date = new Date(`${value.replace(' ', 'T')}Z`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(date);
}

function toggleAll(
  current: string[],
  ids: string[],
  expected: boolean,
  onChange: (next: string[]) => void,
) {
  const set = new Set(current);
  for (const id of ids) {
    if (expected) set.add(id);
    else set.delete(id);
  }
  onChange([...set]);
}

export default function Enrichment({ onNavigate }: EnrichmentProps) {
  const { refresh } = useLeadStream();
  const [activeTab, setActiveTab] = useState<'INDIVIDUAL' | 'LOTE_360'>('LOTE_360');
  const [status, setStatus] = useState<EnrichmentStatus | null>(null);
  const [catalog, setCatalog] = useState<EnrichmentCatalog | null>(null);
  const [runs, setRuns] = useState<EnrichmentRun[]>([]);
  const [pixStatus, setPixStatus] = useState<PixLookupStatus | null>(null);
  const [query, setQuery] = useState('');
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>([]);
  const [result, setResult] = useState<CompanyEnrichmentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [individualError, setIndividualError] = useState<string | null>(null);
  const [showCapabilities, setShowCapabilities] = useState(true);

  const [batchName, setBatchName] = useState('Lote Prospecção B2B');
  const [batchCnpjsText, setBatchCnpjsText] = useState('');
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [batchResult, setBatchResult] = useState<CnpjBatchProgress | null>(null);
  const [batchSuccessMsg, setBatchSuccessMsg] = useState<string | null>(null);
  const [batchPreflightError, setBatchPreflightError] = useState<string | null>(null);

  const parsedCnpjs = useMemo(() => {
    return batchCnpjsText
      .split(/[\n,;]+/)
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
  }, [batchCnpjsText]);

  const batchPreflight = useMemo<{ valid: string[]; invalid: PreflightInvalidItem[]; duplicates: number }>(() => {
    const seen = new Map<string, string>();
    const valid: string[] = [];
    const invalid: PreflightInvalidItem[] = [];
    let duplicates = 0;
    const rawList = batchCnpjsText
      .split(/[\n,;]+/)
      .map((c) => c.trim())
      .filter((c) => c.length > 0);
    for (const raw of rawList) {
      const { digits, valid: ok, reason } = preflightCnpj(raw);
      if (digits.length === 0) continue;
      if (seen.has(digits)) {
        duplicates++;
        continue;
      }
      seen.set(digits, raw);
      if (ok) {
        valid.push(raw);
      } else {
        invalid.push({ raw, digits, digitCount: digits.length, reason: reason ?? 'CNPJ inválido.' });
      }
    }
    return { valid, invalid, duplicates };
  }, [batchCnpjsText]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextStatus, nextCatalog, nextRuns, nextPixStatus] = await Promise.all([
        api.enrichmentStatus(),
        api.enrichmentCatalog(),
        api.enrichmentRuns(),
        api.pixLookupStatus(),
      ]);
      setStatus(nextStatus);
      setCatalog(nextCatalog);
      setRuns(nextRuns);
      setPixStatus(nextPixStatus);
      setSelectedCapabilities((current) => current.length
        ? current
        : [...(nextCatalog.presets.find((preset: { id: string; capabilityIds: string[] }) => preset.id === 'commercial')?.capabilityIds ?? [])]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível carregar o módulo de enriquecimento.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const batchId = batchResult?.batchId ?? batchResult?.id;
    if (!batchResult || !batchId || terminalBatchStatuses.has(batchResult.status)) return;

    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        const response = await fetch(`/api/cnpj-agent/batches/${encodeURIComponent(batchId)}`);
        if (!response.ok) throw new Error('Não foi possível consultar o andamento do lote.');
        const progress = (await response.json()) as CnpjBatchProgress;
        if (cancelled) return;
        setBatchResult({ ...progress, batchId });
        if (terminalBatchStatuses.has(progress.status)) {
          const hasInvalid = (progress.invalidCnpjs ?? 0) > 0 || (progress.invalidItems?.length ?? 0) > 0;
          setBatchSuccessMsg(
            progress.status === 'FAILED'
              ? `Lote encerrado sem processamento: ${progress.failedCount ?? 0} ${(progress.failedCount ?? 0) === 1 ? 'item processou com falha ou era inválido' : 'itens processaram com falha ou eram inválidos'}.${hasInvalid ? ' Confira a lista de CNPJs inválidos abaixo.' : ''}`
              : `Lote finalizado com status ${progress.status === 'PARTIAL' ? 'parcial' : 'concluído'}: ${progress.processedCnpjs ?? 0} de ${progress.totalCnpjs ?? 0} ${(progress.totalCnpjs ?? 0) === 1 ? 'item processado' : 'itens processados'}.${hasInvalid ? ' Confira os itens inválidos abaixo.' : ''}`,
          );
          await refresh();
          return;
        }
        setBatchSuccessMsg(
          `Lote em processamento: ${progress.processedCnpjs ?? 0} de ${progress.totalCnpjs ?? 0} item(ns).`,
        );
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : 'Falha ao acompanhar o lote.');
        }
      }
      if (!cancelled) timer = window.setTimeout(poll, 3_000);
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [batchResult?.batchId, batchResult?.id]);

  const selectedSet = useMemo(() => new Set(selectedCapabilities), [selectedCapabilities]);
  const activePreset = catalog?.presets.find((preset) =>
    preset.capabilityIds.length === selectedCapabilities.length
    && preset.capabilityIds.every((id) => selectedSet.has(id)),
  )?.id;

  const capabilitiesByGroup = useMemo(() => {
    if (!catalog) return [] as Array<{ group: EnrichmentCatalog['groups'][number]; items: EnrichmentCatalog['capabilities'] }>;
    return catalog.groups.map((group) => ({
      group,
      items: catalog.capabilities.filter((cap) => cap.groupId === group.id),
    }));
  }, [catalog]);

  const submitIndividual = async (event: FormEvent) => {
    event.preventDefault();
    if (!query.trim()) {
      setIndividualError('Informe um CNPJ, domínio ou nome da empresa para a consulta individual.');
      return;
    }
    if (!status?.available) {
      setIndividualError('O motor de enriquecimento não está disponível no momento. Atualize a página.');
      return;
    }
    if (!selectedCapabilities.length) {
      setIndividualError('Selecione ao menos uma dimensão de enriquecimento.');
      return;
    }
    setSubmitting(true);
    setIndividualError(null);
    setError(null);
    setResult(null);
    try {
      const enriched = await api.enrichCompany(query.trim(), selectedCapabilities);
      setResult(enriched);
      setRuns(await api.enrichmentRuns().catch(() => runs));
      await refresh();
    } catch (cause) {
      setIndividualError(cause instanceof Error ? cause.message : 'Não foi possível enriquecer esta empresa.');
      setRuns(await api.enrichmentRuns().catch(() => runs));
    } finally {
      setSubmitting(false);
    }
  };

  const submitBatch360 = async (event: FormEvent) => {
    event.preventDefault();
    setBatchPreflightError(null);
    if (batchPreflight.valid.length === 0 && batchPreflight.invalid.length === 0 && batchPreflight.duplicates === 0) {
      setBatchPreflightError('Cole ao menos um CNPJ para iniciar o lote.');
      return;
    }
    if (batchPreflight.invalid.length > 0) {
      setBatchPreflightError(
        `${batchPreflight.invalid.length} CNPJ(s) inválido(s) foram detectados na validação prévia. Corrija ou remova os itens destacados antes de enviar.`,
      );
      return;
    }
    if (batchPreflight.valid.length === 0) {
      setBatchPreflightError('Nenhum CNPJ válido foi informado. Verifique o formato e os dígitos verificadores.');
      return;
    }

    setBatchSubmitting(true);
    setError(null);
    setBatchSuccessMsg(null);
    setBatchResult(null);

    try {
      const res = await fetch('/api/cnpj-agent/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: batchName || 'Lote Enriquecido 360',
          cnpjs: batchPreflight.valid,
          maxConcurrency: 1,
          smtp: false,
          whatsapp: false,
          social: true,
          website: true,
          pix: pixStatus?.lookupReady === true,
        }),
      });

      const contentType = res.headers.get('content-type') || '';
      const data = contentType.includes('application/json') ? await res.json() : null;
      if (!res.ok) {
        const msg = (data?.error as string | undefined) || 'Erro ao processar lote.';
        const details = data?.details && typeof data.details === 'object' && !Array.isArray(data.details)
          ? (data.details as Record<string, unknown>)
          : null;
        const invalidList = details && Array.isArray((details as { invalidItems?: unknown[] }).invalidItems)
          ? ((details as { invalidItems: PreflightInvalidItem[] }).invalidItems)
          : undefined;
        if (invalidList && invalidList.length > 0) {
          setBatchResult({ status: 'FAILED', invalidItems: invalidList.map((i) => ({ ...i, formatted: formatCnpj(i.digits) })) });
        }
        throw new Error(msg);
      }

      setBatchResult(data);
      if (Array.isArray((data as CnpjBatchProgress).invalidItems) && (data as CnpjBatchProgress).invalidItems!.length > 0) {
        setBatchSuccessMsg(
          (data as CnpjBatchProgress).invalidItems!.length === batchPreflight.valid.length + batchPreflight.invalid.length
            ? 'Todos os itens foram rejeitados na validação do servidor.'
            : `${(data as CnpjBatchProgress).invalidItems!.length} item(ns) não passaram na validação do servidor.`,
        );
      } else if (terminalBatchStatuses.has((data as CnpjBatchProgress).status)) {
        setBatchSuccessMsg(
          (data as CnpjBatchProgress).status === 'FAILED'
            ? `Lote encerrado: nenhum CNPJ válido foi recebido (${(data as CnpjBatchProgress).invalidCnpjs ?? 0} inválido(s)).`
            : `Lote finalizado com status ${String((data as CnpjBatchProgress).status).toLowerCase()}.`,
        );
        await refresh();
      } else {
        setBatchSuccessMsg(
          `Lote recebido: ${(data as CnpjBatchProgress).totalValidCnpjs ?? 0} CNPJ(s) válido(s) aguardam processamento durável.`,
        );
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Falha ao executar o enriquecimento em lote.');
    } finally {
      setBatchSubmitting(false);
    }
  };

  const invalidItemsToDisplay = useMemo<NonNullable<CnpjBatchProgress['invalidItems']>>(() => {
    const fromPoll = batchResult?.invalidItems ?? [];
    if (fromPoll.length > 0) {
      return fromPoll.map((i) => ({
        raw: i.raw,
        formatted: i.formatted || formatCnpj(i.digits ?? ''),
        reason: i.reason,
      }));
    }
    if (batchPreflight.invalid.length > 0) {
      return batchPreflight.invalid.map((i) => ({
        raw: i.raw,
        formatted: formatCnpj(i.digits),
        reason: i.reason,
        digits: i.digits,
        digitCount: i.digitCount,
      }));
    }
    return [];
  }, [batchResult?.invalidItems, batchPreflight.invalid]);

  if (loading) {
    return (
      <div className="mx-auto max-w-[1440px] space-y-5" aria-busy="true">
        <div className="h-28 animate-pulse rounded-[12px] bg-slate-200" />
        <div className="h-[720px] animate-pulse rounded-[12px] bg-slate-200" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1440px] space-y-5">
      <section className="flex flex-col justify-between gap-5 rounded-[12px] border border-slate-200 bg-white p-5 sm:flex-row sm:items-center sm:p-6 shadow-sm">
        <div className="max-w-3xl">
          <div className="flex items-center gap-2 text-xs font-semibold text-blue-700">
            <Sparkles className="h-4 w-4" /> Empresas e vínculos societários
          </div>
          <h2 className="mt-2 text-xl font-bold tracking-[-0.03em] text-slate-950">Motor de Enriquecimento de Dados</h2>
          <p className="mt-1.5 max-w-[72ch] text-sm leading-6 text-slate-600">
            Consulte dados cadastrais e QSA, normalize canais da empresa e preserve evidências e indisponibilidades.
            Cada dimensão processada informa disponibilidade separadamente.
          </p>
        </div>

        <div className="flex bg-slate-100 p-1.5 rounded-xl border border-slate-200 shrink-0">
          <button
            onClick={() => setActiveTab('LOTE_360')}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
              activeTab === 'LOTE_360'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Zap className="w-3.5 h-3.5" /> Enriquecimento em lote
          </button>
          <button
            onClick={() => setActiveTab('INDIVIDUAL')}
            className={`flex items-center gap-2 px-4 py-2 text-xs font-bold rounded-lg transition-all cursor-pointer ${
              activeTab === 'INDIVIDUAL'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Search className="w-3.5 h-3.5" /> Consulta Individual
          </button>
        </div>
      </section>

      {error && (
        <div className="flex items-start gap-3 rounded-[10px] bg-red-50 px-4 py-3 text-sm text-red-900" role="alert">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button
            type="button"
            className="rounded-md p-1 hover:bg-red-100"
            aria-label="Fechar aviso"
            onClick={() => setError(null)}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {batchSuccessMsg && (
        <div className={`flex items-start justify-between gap-4 rounded-[10px] border px-5 py-4 shadow-sm animate-in fade-in ${
          batchResult?.status === 'FAILED'
            ? 'bg-red-50 border-red-200 text-red-900'
            : batchResult?.status === 'PARTIAL'
              ? 'bg-amber-50 border-amber-200 text-amber-900'
              : batchResult?.status === 'COMPLETED'
            ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
            : 'bg-blue-50 border-blue-200 text-blue-900'
        }`}>
          <div className="flex items-start gap-3">
            {batchResult?.status === 'COMPLETED'
              ? <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
              : batchResult && terminalBatchStatuses.has(batchResult.status)
                ? <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                : <LoaderCircle className="h-5 w-5 animate-spin text-blue-600 shrink-0 mt-0.5" />}
            <div>
              <span className="font-bold text-sm block">{batchSuccessMsg}</span>
              <span className="text-xs opacity-80">
                {batchResult && terminalBatchStatuses.has(batchResult.status)
                  ? 'Revise os itens e as evidências antes de usar ou exportar os resultados.'
                  : 'O lote pode continuar após fechar esta página ou reiniciar a aplicação.'}
              </span>
              {batchResult && (batchResult.totalRequested || batchResult.totalValidCnpjs) && (
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] opacity-90">
                  {batchResult.totalRequested !== undefined && (
                    <span>Solicitados: <strong>{batchResult.totalRequested}</strong></span>
                  )}
                  {batchResult.totalUnique !== undefined && (
                    <span>Únicos: <strong>{batchResult.totalUnique}</strong></span>
                  )}
                  {batchResult.duplicatesRemoved !== undefined && batchResult.duplicatesRemoved > 0 && (
                    <span>Duplicatas removidas: <strong>{batchResult.duplicatesRemoved}</strong></span>
                  )}
                  {batchResult.totalValidCnpjs !== undefined && (
                    <span>Válidos: <strong className="text-emerald-700">{batchResult.totalValidCnpjs}</strong></span>
                  )}
                  {batchResult.invalidCnpjs !== undefined && batchResult.invalidCnpjs > 0 && (
                    <span>Inválidos: <strong className="text-red-700">{batchResult.invalidCnpjs}</strong></span>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {batchResult && ['COMPLETED', 'PARTIAL'].includes(batchResult.status) && (
              <button
                onClick={() => onNavigate('search')}
                className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white rounded-lg text-xs font-bold hover:bg-emerald-700 transition-colors shadow-xs cursor-pointer"
              >
                Ver resultados <ArrowRight className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {activeTab === 'LOTE_360' && (
        <form onSubmit={submitBatch360} className="overflow-hidden rounded-[12px] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-4 sm:px-6 bg-slate-50 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-950 flex items-center gap-2">
                <Zap className="w-4 h-4 text-blue-600" /> Pipeline de ingestão e enriquecimento em lote
              </h3>
              <p className="mt-0.5 text-xs text-slate-500">
                Cole até 10 mil CNPJs. Itens inválidos são bloqueados no envio, não processados.
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className="font-bold bg-slate-100 text-slate-700 px-3 py-1 rounded-full border border-slate-200">
                {parsedCnpjs.length} informados
              </span>
              <span className={`font-bold px-3 py-1 rounded-full border ${batchPreflight.valid.length > 0 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-slate-100 text-slate-500 border-slate-200'}`}>
                {batchPreflight.valid.length} válidos
              </span>
              {batchPreflight.duplicates > 0 && (
                <span className="font-bold bg-amber-50 text-amber-700 px-3 py-1 rounded-full border border-amber-200">
                  {batchPreflight.duplicates} duplicatas
                </span>
              )}
              {batchPreflight.invalid.length > 0 && (
                <span className="font-bold bg-red-50 text-red-700 px-3 py-1 rounded-full border border-red-200">
                  {batchPreflight.invalid.length} inválidos
                </span>
              )}
            </div>
          </div>

          <div className="p-6 space-y-6">
            <div className={`rounded-xl border p-4 ${pixStatus?.lookupReady ? 'border-emerald-200 bg-emerald-50/70' : 'border-amber-200 bg-amber-50/60'}`}>
              <div className="flex items-start gap-3">
                <ShieldCheck className={`mt-0.5 h-5 w-5 shrink-0 ${pixStatus?.lookupReady ? 'text-emerald-700' : 'text-amber-700'}`} />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-bold text-slate-900">Descoberta bancária com proteção de titularidade</p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${pixStatus?.lookupReady ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>
                      {pixStatus?.lookupReady ? 'Validação autorizada' : 'Somente candidatos'}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-600">
                    CNPJ, CPF completo, e-mail, telefone e EVP são reconhecidos. O sistema só consulta uma chave publicada explicitamente como Pix;
                    candidatos comuns permanecem mascarados e não são testados.
                  </p>
                  {!pixStatus?.lookupReady && (
                    <p className="mt-1 text-[11px] font-medium text-amber-800">
                      O DICT está desativado até configurar finalidade de pagamento, aceite contratual e ao menos um PSP.
                    </p>
                  )}
                </div>
              </div>
            </div>
            <div>
              <label htmlFor="batch-name" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Identificação do Lote
              </label>
              <input
                id="batch-name"
                value={batchName}
                onChange={(e) => setBatchName(e.target.value)}
                placeholder="Ex: Lote Prospecção B2B"
                className="w-full sm:w-96 h-10 px-3.5 text-sm rounded-xl border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 outline-none"
              />
            </div>

            <div>
              <label htmlFor="batch-cnpjs" className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                Lista de CNPJs (um por linha ou separados por vírgula / ponto e vírgula)
              </label>
              <textarea
                id="batch-cnpjs"
                rows={6}
                value={batchCnpjsText}
                onChange={(e) => {
                  setBatchCnpjsText(e.target.value);
                  setBatchPreflightError(null);
                }}
                placeholder="Exemplos válidos: 33.000.167/0001-01 ou 00.000.000/E08G-12."
                className={`w-full p-4 font-mono text-sm rounded-xl border ${
                  batchPreflight.invalid.length > 0 || batchPreflightError
                    ? 'border-red-300 bg-red-50 focus:bg-white focus:border-red-500 focus:ring-2 focus:ring-red-100'
                    : 'border-slate-300 bg-slate-50 focus:bg-white focus:border-blue-600 focus:ring-2 focus:ring-blue-100'
                } outline-none transition-colors leading-relaxed`}
              />
              {parsedCnpjs.length > 0 && batchPreflight.invalid.length === 0 && batchPreflight.valid.length > 0 && (
                <div className="mt-2 flex items-center gap-2 text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-lg px-3 py-2">
                  <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                  Todos os {batchPreflight.valid.length} CNPJ(s) passaram na validação prévia (verificadores + formato numérico/alfanumérico).
                  {batchPreflight.duplicates > 0 && (
                    <span className="ml-2 text-amber-700">
                      {batchPreflight.duplicates} duplicata(s) serão ignoradas automaticamente.
                    </span>
                  )}
                </div>
              )}
            </div>

            {batchPreflight.invalid.length > 0 && (
              <div className="border border-red-200 bg-red-50 rounded-xl p-4 space-y-3" role="alert" aria-live="polite">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <div className="text-xs font-bold text-red-900 uppercase tracking-wider">
                      CNPJs inválidos detectados antes do envio
                    </div>
                    <p className="text-xs text-red-800 mt-0.5">
                      Os itens abaixo são inválidos e <strong>impedem o envio do lote</strong>.
                      Remova-os da lista ou corrija a digitação.
                    </p>
                  </div>
                </div>
                <div className="overflow-hidden rounded-lg border border-red-200 bg-white">
                  <div className="grid grid-cols-12 gap-2 px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-red-900 bg-red-100">
                    <div className="col-span-3">Valor original</div>
                    <div className="col-span-2">Dígitos</div>
                    <div className="col-span-1 text-center">Tamanho</div>
                    <div className="col-span-6">Motivo</div>
                  </div>
                  <ul className="max-h-60 overflow-auto divide-y divide-red-100 text-xs">
                    {batchPreflight.invalid.map((item, idx) => (
                      <li key={`${item.raw}-${idx}`} className="grid grid-cols-12 gap-2 items-start px-3 py-2 hover:bg-red-50/50">
                        <div className="col-span-3 font-mono break-all">{item.raw || <span className="text-slate-400 italic">(vazio)</span>}</div>
                        <div className="col-span-2 font-mono">{item.digits || <span className="text-slate-400">—</span>}</div>
                        <div className={`col-span-1 text-center tabular-nums ${item.digitCount === 14 ? 'text-amber-700' : 'text-red-700'}`}>{item.digitCount}</div>
                        <div className="col-span-6 text-red-800 pr-2">{item.reason}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {invalidItemsToDisplay.length > 0 && batchPreflight.invalid.length === 0 && (
              <div className="border border-amber-200 bg-amber-50 rounded-xl p-4 space-y-3" role="alert">
                <div className="flex items-start gap-2">
                  <Info className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <div className="text-xs font-bold text-amber-900 uppercase tracking-wider">
                      Itens inválidos reportados pelo servidor
                    </div>
                    <p className="text-xs text-amber-800 mt-0.5">
                      Esses itens não foram processados. Eles aparecem com o status recebido do motor de enriquecimento.
                    </p>
                  </div>
                </div>
                <ul className="text-xs space-y-1.5 max-h-56 overflow-auto">
                  {invalidItemsToDisplay.map((item, idx) => (
                    <li key={`inv-${idx}`} className="flex gap-2 items-start">
                      <span className="font-mono break-all text-amber-900 w-48 shrink-0">
                        {item.formatted || item.raw}
                      </span>
                      <span className="text-amber-800">{item.reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {batchPreflightError && (
              <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-900" role="alert">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-red-600" />
                <div className="flex-1">
                  <div className="font-semibold uppercase tracking-wider">Envio bloqueado</div>
                  <p className="mt-0.5">{batchPreflightError}</p>
                </div>
              </div>
            )}

            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-800 uppercase tracking-wider block">
                  Dimensões habilitadas no lote 360
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 text-xs text-slate-700">
                <div className="flex items-center gap-2 bg-white p-2.5 rounded-lg border border-slate-200">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Cadastro oficial (BrasilAPI, ReceitaWS, MinhaReceita)</span>
                </div>
                <div className="flex items-center gap-2 bg-white p-2.5 rounded-lg border border-slate-200">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Quadro de Sócios + decisores individuais</span>
                </div>
                <div className="flex items-center gap-2 bg-white p-2.5 rounded-lg border border-slate-200">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Dados bancários somente quando observados em fonte explícita</span>
                </div>
                <div className="flex items-center gap-2 bg-white p-2.5 rounded-lg border border-slate-200">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Telefones observados + WhatsApp somente quando declarado</span>
                </div>
                <div className="flex items-center gap-2 bg-white p-2.5 rounded-lg border border-slate-200">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Busca de candidatos sociais, sem confirmação automática</span>
                </div>
                <div className="flex items-center gap-2 bg-white p-2.5 rounded-lg border border-slate-200">
                  <Check className="w-4 h-4 text-emerald-600 shrink-0" />
                  <span>Evidências e status separados (ABSENT/OBSERVED/INFERRED)</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2 gap-4">
              <span className="text-xs text-slate-500 flex-1">
                Processamento com deduplicação e registro de finalidade. Isso não substitui uma avaliação jurídica de conformidade.
              </span>
              <button
                type="submit"
                id="btn-run-batch-360"
                disabled={batchSubmitting || batchPreflight.valid.length === 0 || batchPreflight.invalid.length > 0}
                className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer whitespace-nowrap"
              >
                {batchSubmitting ? (
                  <>
                    <LoaderCircle className="w-4 h-4 animate-spin" />
                    Enfileirando {batchPreflight.valid.length} CNPJ(s)…
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    Iniciar lote 360 ({batchPreflight.valid.length})
                  </>
                )}
              </button>
            </div>
          </div>
        </form>
      )}

      {activeTab === 'INDIVIDUAL' && (
        <form onSubmit={submitIndividual} className="overflow-hidden rounded-[12px] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-5 py-4 sm:px-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-950">Nova consulta individual</h2>
              <p className="mt-0.5 text-[11px] text-slate-500">
                Suporta CNPJ, domínio ou nome da empresa. Selecione as dimensões de dados abaixo.
              </p>
            </div>
            {submitting && (
              <div className="flex items-center gap-2 text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded-lg px-3 py-1.5">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> Consulta em andamento…
              </div>
            )}
          </div>

          <div className="space-y-6 p-5 sm:p-6">
            <div>
              <label htmlFor="enrichment-query" className="text-xs font-semibold text-slate-800">
                Qual empresa você quer analisar?
              </label>
              <div className="mt-1.5 text-[11px] text-slate-500">
                Cole um CNPJ (formatado ou não), o domínio do site institucional ou o nome da empresa.
              </div>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    id="enrichment-query"
                    value={query}
                    onChange={(event) => { setQuery(event.target.value); setIndividualError(null); }}
                    onKeyDown={(e) => { if (e.key === 'Enter') void submitIndividual(e as unknown as FormEvent); }}
                    placeholder="Ex.: 33.000.167/0001-01, petrobras.com.br ou Petrobras"
                    disabled={!status?.available || submitting}
                    className="h-11 w-full rounded-[10px] border border-slate-300 bg-white pl-10 pr-3 text-sm text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!status?.available || submitting || !query.trim() || !selectedCapabilities.length}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-[10px] bg-blue-600 px-5 text-xs font-bold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-300 cursor-pointer"
                >
                  {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
                  {submitting
                    ? 'Consultando…'
                    : selectedCapabilities.length > 0
                      ? `Consultar ${selectedCapabilities.length} dimensões`
                      : 'Selecione dimensões'}
                </button>
              </div>
            </div>

            {individualError && (
              <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs text-red-900" role="alert">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-red-600" />
                <div className="flex-1">
                  <div className="font-semibold uppercase tracking-wider">Falha na consulta individual</div>
                  <p className="mt-0.5">{individualError}</p>
                </div>
                <button
                  type="button"
                  className="rounded-md p-1 hover:bg-red-100"
                  onClick={() => setIndividualError(null)}
                  aria-label="Fechar aviso"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            <fieldset className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <legend className="text-xs font-semibold text-slate-800">Pacotes rápidos</legend>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    Selecione uma composição pronta e ajuste qualquer dimensão abaixo.
                  </p>
                </div>
                <span className="text-[11px] text-slate-500 inline-flex items-center gap-1">
                  <SlidersHorizontal className="h-3.5 w-3.5" />
                  {selectedCapabilities.length} {selectedCapabilities.length === 1 ? 'dimensão selecionada' : 'dimensões selecionadas'}
                </span>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {catalog?.presets.map((preset) => {
                  const selected = activePreset === preset.id;
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => setSelectedCapabilities([...preset.capabilityIds])}
                      disabled={!status?.available || submitting}
                      className={`rounded-[10px] border p-3 text-left transition-colors ${
                        selected
                          ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-100 shadow-sm'
                          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                      } disabled:cursor-not-allowed disabled:opacity-60 cursor-pointer`}
                    >
                      <span className="flex items-center justify-between gap-3">
                        <span className={`text-xs font-bold ${selected ? 'text-blue-800' : 'text-slate-900'}`}>{preset.label}</span>
                        <span className="text-[10px] font-semibold text-slate-500">{preset.capabilityIds.length} itens</span>
                      </span>
                      <span className="mt-1 block text-[10px] leading-4 text-slate-500">{preset.description}</span>
                    </button>
                  );
                })}
              </div>
            </fieldset>

            <fieldset className="border border-slate-200 rounded-xl overflow-hidden">
              <button
                type="button"
                className="w-full flex items-center justify-between gap-3 px-4 py-3 bg-slate-50 hover:bg-slate-100 transition-colors"
                onClick={() => setShowCapabilities((v) => !v)}
                aria-expanded={showCapabilities}
              >
                <div className="text-left">
                  <legend className="text-xs font-bold uppercase tracking-wider text-slate-800">
                    Dimensões personalizadas
                  </legend>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    Marque apenas os campos que você quer processar para reduzir tempo e custo.
                  </p>
                </div>
                <span className="shrink-0 text-slate-500">
                  {showCapabilities ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </span>
              </button>
              {showCapabilities && catalog && (
                <div className="p-4 space-y-5">
                  {capabilitiesByGroup.map(({ group, items }) => {
                    const groupIds = items.map((i) => i.id);
                    const selectedInGroup = groupIds.filter((id) => selectedSet.has(id)).length;
                    const allSelected = selectedInGroup === groupIds.length && groupIds.length > 0;
                    return (
                      <div key={group.id} className="space-y-2">
                        <div className="flex items-center justify-between gap-3 border-b border-slate-100 pb-2">
                          <div>
                            <div className="text-xs font-bold text-slate-800">{group.label}</div>
                            <div className="text-[11px] text-slate-500">{group.description}</div>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                              {selectedInGroup}/{groupIds.length}
                            </span>
                            <button
                              type="button"
                              onClick={() => toggleAll(selectedCapabilities, groupIds, !allSelected, setSelectedCapabilities)}
                              disabled={!status?.available || submitting || items.length === 0}
                              className="text-[11px] font-semibold text-blue-700 hover:text-blue-900 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                              {allSelected ? 'Desmarcar grupo' : 'Selecionar grupo'}
                            </button>
                          </div>
                        </div>
                        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                          {items.map((cap) => {
                            const checked = selectedSet.has(cap.id);
                            return (
                              <label
                                key={cap.id}
                                htmlFor={`cap-${cap.id}`}
                                className={`flex items-start gap-3 p-3 rounded-lg border transition-colors cursor-pointer ${
                                  checked
                                    ? 'border-blue-300 bg-blue-50/60'
                                    : 'border-slate-200 bg-white hover:bg-slate-50'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                              >
                                <input
                                  id={`cap-${cap.id}`}
                                  type="checkbox"
                                  className="mt-0.5 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 disabled:cursor-not-allowed"
                                  disabled={!status?.available || submitting}
                                  checked={checked}
                                  onChange={(e) => {
                                    const next = new Set(selectedCapabilities);
                                    if (e.target.checked) next.add(cap.id);
                                    else next.delete(cap.id);
                                    setSelectedCapabilities([...next]);
                                  }}
                                />
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="text-xs font-semibold text-slate-900 truncate">{cap.label}</span>
                                    <span className={`text-[9px] font-bold uppercase tracking-wider rounded px-1.5 py-0.5 ${
                                      cap.depth === 'Essencial'
                                        ? 'bg-emerald-100 text-emerald-800'
                                        : cap.depth === 'Detalhado'
                                          ? 'bg-blue-100 text-blue-800'
                                          : 'bg-slate-100 text-slate-700'
                                    }`}>
                                      {cap.depth}
                                    </span>
                                  </div>
                                  <p className="mt-0.5 text-[11px] leading-4 text-slate-600">{cap.description}</p>
                                  {cap.highlights.length > 0 && (
                                    <div className="mt-1 flex flex-wrap gap-1">
                                      {cap.highlights.map((h) => (
                                        <span key={h} className="text-[10px] text-slate-500 bg-slate-100 rounded px-1.5 py-0.5">
                                          {h}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              </label>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </fieldset>

            {result && (
              <div className="space-y-3 border border-slate-200 rounded-xl bg-slate-50 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-800">Resultado da consulta</div>
                    <div className="mt-0.5 text-[11px] text-slate-600">
                      {(result.coverage?.available ?? 0)}/{(result.coverage?.requested ?? 0)} dimensões disponíveis ·
                      {(result.coverage?.fieldCount ?? 0)} campos · {(result.coverage?.recordCount ?? 0)} registros secundários
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      if (result.companyId) void navigator.clipboard?.writeText(result.companyId);
                    }}
                    className="text-[11px] font-semibold text-blue-700 hover:text-blue-900 inline-flex items-center gap-1"
                    title="Copiar ID da empresa"
                  >
                    <Copy className="h-3.5 w-3.5" /> Copiar companyId
                  </button>
                </div>
                <div className="rounded-lg border border-slate-200 bg-white divide-y divide-slate-100">
                  {(result.sections || []).map((sec) => {
                    const st = sectionState(sec.status);
                    return (
                      <div key={sec.id} className="p-3 sm:p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className={`inline-block h-2 w-2 rounded-full ${st.dot}`} />
                              <h4 className="text-sm font-semibold text-slate-900">{sec.title}</h4>
                              <span className={`text-[10px] font-semibold uppercase tracking-wider ${st.className}`}>{st.label}</span>
                            </div>
                            <p className="mt-0.5 text-[11px] text-slate-500">{sec.description}</p>
                            {sec.summary && (
                              <p className="mt-1 text-[11px] text-slate-700">{sec.summary}</p>
                            )}
                            {sec.errorMessage && (
                              <p className="mt-1 text-[11px] text-red-700 bg-red-50 border border-red-100 rounded-md px-2 py-1 inline-block">
                                {sec.errorMessage}
                              </p>
                            )}
                          </div>
                        </div>
                        {(sec.fields || []).length > 0 && (
                          <div className="mt-2 grid gap-x-6 gap-y-1.5 text-xs sm:grid-cols-2">
                            {(sec.fields || []).map((f) => (
                              <div key={`${sec.id}-${f.label}`} className="flex gap-2 items-start">
                                <span className="text-slate-500 shrink-0 w-32">{f.label}</span>
                                <span className="text-slate-800 flex-1 break-words">{f.value || <span className="text-slate-400">—</span>}</span>
                              </div>
                            ))}
                          </div>
                        )}
                        {(sec.items || []).length > 0 && (
                          <div className="mt-2 grid gap-2 sm:grid-cols-2">
                            {(sec.items || []).map((it, idx) => (
                              <div key={`${sec.id}-it-${idx}`} className="rounded-md border border-slate-200 bg-slate-50 p-3 space-y-1">
                                {it.title && <div className="text-xs font-semibold text-slate-900">{it.title}</div>}
                                <div className="space-y-0.5">
                                  {(it.fields || []).map((f) => (
                                    <div key={`${sec.id}-${idx}-${f.label}`} className="flex gap-2 text-[11px]">
                                      <span className="text-slate-500 w-24 shrink-0">{f.label}</span>
                                      <span className="text-slate-800 break-words">{f.value || <span className="text-slate-400">—</span>}</span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </form>
      )}

      {runs.length > 0 && (
        <section className="rounded-[12px] border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-200 bg-slate-50">
            <h3 className="text-sm font-bold text-slate-950">Últimas consultas individuais</h3>
            <p className="mt-0.5 text-xs text-slate-500">Histórico das últimas execuções do endpoint de enriquecimento.</p>
          </div>
          <ul className="divide-y divide-slate-100">
            {runs.slice(0, 10).map((run) => {
              const s = runStatus(run);
              return (
                <li key={run.id} className="px-5 py-3 flex items-center justify-between gap-3 text-xs">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${s.className}`}>
                        {s.label}
                      </span>
                      <span className="font-mono text-slate-800 truncate max-w-[50%]">{run.query}</span>
                    </div>
                    <div className="mt-0.5 text-[11px] text-slate-500 flex flex-wrap gap-x-3 gap-y-1">
                      <span>{run.capabilities.length} dimensão(ões)</span>
                      <span>{formatRunDate(run.startedAt)}</span>
                      {run.errorMessage && <span className="text-red-700">Erro: {run.errorMessage}</span>}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => { setQuery(run.query); setActiveTab('INDIVIDUAL'); }}
                    className="text-[11px] font-semibold text-blue-700 hover:text-blue-900"
                  >
                    Reutilizar consulta
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}
