import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
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
  Building2,
  User,
  PhoneCall,
  Skull,
  CreditCard,
  Landmark,
  Ban,
  Phone,
  MessageSquare,
} from 'lucide-react';
import { api } from '../api';
import { useLeadStream } from '../LeadStreamContext';
import type {
  CompanyEnrichmentResult,
  PersonEnrichmentResult,
  EnrichmentCatalog,
  EnrichmentRun,
  EnrichmentJob,
  EnrichmentStatus,
  PixLookupStatus,
  DjangoBatch,
} from '../types';

interface EnrichmentProps {
  onNavigate: (route: string) => void;
}

interface PreflightInvalidItem {
  raw: string;
  digits: string;
  digitCount: number;
  reason: string;
}

const terminalBatchStatuses = new Set<DjangoBatch['status']>(['COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED']);

function batchIsTerminal(batch: DjangoBatch) {
  if (batch.status === 'FAILED' || batch.status === 'CANCELLED') return true;
  return batch.current_stage === 'ENRICHMENT' && terminalBatchStatuses.has(batch.status);
}

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

function preflightCpf(raw: string): { digits: string; valid: boolean; reason?: string } {
  const trimmed = String(raw || '').trim();
  const digits = trimmed.replace(/\D/g, '');
  if (digits.length !== 11) {
    return {
      digits,
      valid: false,
      reason: `Comprimento inválido (${digits.length} dígitos numéricos; são necessários 11 para o CPF).`,
    };
  }
  if (/^(\d)\1{10}$/.test(digits)) {
    return { digits, valid: false, reason: 'O CPF não pode conter todos os dígitos iguais.' };
  }
  const w1 = [10, 9, 8, 7, 6, 5, 4, 3, 2];
  const s1 = digits.slice(0, 9).split('').reduce((acc, d, i) => acc + Number(d) * w1[i], 0);
  const r1 = s1 % 11;
  const dv1 = r1 < 2 ? 0 : 11 - r1;
  if (dv1 !== Number(digits[9])) {
    return { digits, valid: false, reason: `Primeiro dígito verificador inválido (esperado ${dv1}, encontrado ${digits[9]}).` };
  }
  const w2 = [11, 10, 9, 8, 7, 6, 5, 4, 3, 2];
  const s2 = (digits.slice(0, 9) + String(dv1)).split('').reduce((acc, d, i) => acc + Number(d) * w2[i], 0);
  const r2 = s2 % 11;
  const dv2 = r2 < 2 ? 0 : 11 - r2;
  if (dv2 !== Number(digits[10])) {
    return { digits, valid: false, reason: `Segundo dígito verificador inválido (esperado ${dv2}, encontrado ${digits[10]}).` };
  }
  return { digits, valid: true };
}

function formatCnpj(digits: string) {
  if (digits.length !== 14) return digits;
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12, 14)}`;
}

function runStatus(run: EnrichmentRun) {
  if (run.status === 'SUCCEEDED') return { label: 'Concluído', className: 'bg-emerald-50 text-emerald-800' };
  if (run.status === 'NO_DATA') return { label: 'Sem resultado', className: 'bg-amber-50 text-amber-800' };
  if (run.status === 'FAILED') return { label: 'Falhou', className: 'bg-red-50 text-red-800' };
  if (run.status === 'QUEUED') return { label: 'Na fila', className: 'bg-slate-100 text-slate-700' };
  return { label: 'Processando', className: 'bg-blue-50 text-blue-800' };
}

function sectionState(status: CompanyEnrichmentResult['sections'][number]['status']) {
  if (status === 'available') return { label: 'Dados encontrados', className: 'text-emerald-700', dot: 'bg-emerald-500' };
  if (status === 'unavailable') return { label: 'Tente novamente', className: 'text-amber-700', dot: 'bg-amber-500' };
  return { label: 'Sem registros', className: 'text-slate-500', dot: 'bg-slate-300' };
}

function formatRunDate(value?: string | null) {
  if (!value) return 'Aguardando início';
  const date = new Date(`${value.replace(' ', 'T')}Z`);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(date);
}

async function waitForEnrichmentJob<T>(initial: EnrichmentJob<T>): Promise<EnrichmentJob<T>> {
  let current = initial;
  const finalStatuses = new Set<EnrichmentRun['status']>(['SUCCEEDED', 'NO_DATA', 'FAILED']);
  for (let attempt = 0; attempt < 150 && !finalStatuses.has(current.status); attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 2_000));
    current = await api.enrichmentJob<T>(current.id);
  }
  if (!finalStatuses.has(current.status)) {
    throw new Error('A consulta continua em processamento. Ela permanecerá no histórico para acompanhamento.');
  }
  if (current.status === 'FAILED') {
    throw new Error(current.errorMessage || 'A consulta falhou após as tentativas automáticas.');
  }
  return current;
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
  const [docType, setDocType] = useState<'CNPJ' | 'CPF'>('CNPJ');
  const [selectedCapabilities, setSelectedCapabilities] = useState<string[]>([]);
  const [result, setResult] = useState<CompanyEnrichmentResult | null>(null);
  const [personResult, setPersonResult] = useState<PersonEnrichmentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [individualError, setIndividualError] = useState<string | null>(null);
  const [showCapabilities, setShowCapabilities] = useState(true);

  const [batchName, setBatchName] = useState('Lote Prospecção B2B');
  const [batchCnpjsText, setBatchCnpjsText] = useState('');
  const [batchSubmitting, setBatchSubmitting] = useState(false);
  const [batchResult, setBatchResult] = useState<DjangoBatch | null>(null);
  const enrichmentStarted = useRef(new Set<string>());
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
    const batchId = batchResult?.id;
    if (!batchResult || !batchId || batchIsTerminal(batchResult)) return;

    let cancelled = false;
    let timer: number | undefined;
    const poll = async () => {
      try {
        let progress = await api.batchDetail(batchId);
        if (cancelled) return;

        if (
          progress.current_stage === 'HYGIENE'
          && terminalBatchStatuses.has(progress.status)
          && !enrichmentStarted.current.has(batchId)
        ) {
          enrichmentStarted.current.add(batchId);
          setBatchSuccessMsg('Higienização concluída. Preparando o enriquecimento com os provedores configurados.');
          await api.startBatchEnrichment(batchId, [
            'COMPANY_REGISTRY',
            'DECISION_MAKER',
            'DIRECT_EMAIL',
            'DIRECT_PHONE',
            'WHATSAPP',
            'SOCIAL_PROFILES',
            'BANKING',
            'GOVERNMENT_RISK',
            'PUBLIC_SECTOR',
          ]);
          progress = await api.batchDetail(batchId);
        }

        setBatchResult(progress);
        if (batchIsTerminal(progress)) {
          const hasInvalid = progress.invalid_rows > 0;
          setBatchSuccessMsg(
            progress.status === 'FAILED'
              ? `Lote encerrado sem processamento: ${progress.failed_rows} ${progress.failed_rows === 1 ? 'item falhou' : 'itens falharam'}.`
              : `Lote ${progress.status === 'PARTIAL' ? 'concluído parcialmente' : 'concluído'}: ${progress.processed_rows} de ${progress.total_rows} ${progress.total_rows === 1 ? 'item processado' : 'itens processados'}.${hasInvalid ? ` ${progress.invalid_rows} item(ns) foram classificados como inválidos.` : ''}`,
          );
          await refresh();
          return;
        }
        setBatchSuccessMsg(
          `Lote em processamento: ${progress.processed_rows} de ${progress.total_rows} item(ns).`,
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
  }, [batchResult?.id]);

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
      setIndividualError(docType === 'CPF' ? 'Informe um CPF para a consulta individual.' : 'Informe um CNPJ, domínio ou nome da empresa para a consulta individual.');
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
    setPersonResult(null);

    if (docType === 'CPF') {
      const { valid, reason } = preflightCpf(query.trim());
      if (!valid) {
        setIndividualError(reason ?? 'CPF inválido perante os algoritmos oficiais da Receita Federal.');
        setSubmitting(false);
        return;
      }
      try {
        const queued = await api.enrichPerson(query.trim(), selectedCapabilities);
        setRuns((current) => [queued, ...current.filter((run) => run.id !== queued.id)]);
        const completed = await waitForEnrichmentJob(queued);
        if (completed.result) setPersonResult(completed.result);
        setRuns(await api.enrichmentRuns().catch(() => runs));
        await refresh();
      } catch (cause) {
        setIndividualError(cause instanceof Error ? cause.message : 'Não foi possível enriquecer este CPF.');
        setRuns(await api.enrichmentRuns().catch(() => runs));
      } finally {
        setSubmitting(false);
      }
      return;
    }

    try {
      const queued = await api.enrichCompany(query.trim(), selectedCapabilities);
      setRuns((current) => [queued, ...current.filter((run) => run.id !== queued.id)]);
      const completed = await waitForEnrichmentJob(queued);
      if (completed.result) setResult(completed.result);
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
      const csvRows = batchPreflight.valid.map((value) => preflightCnpj(value).digits);
      const csv = `\uFEFFcnpj\r\n${csvRows.join('\r\n')}\r\n`;
      const formData = new FormData();
      formData.append('name', batchName || 'Lote Enriquecido 360');
      formData.append('chunk_size', '500');
      formData.append('arquivo', new Blob([csv], { type: 'text/csv;charset=utf-8' }), 'cnpjs.csv');
      const data = await api.uploadBatch(formData, crypto.randomUUID());

      enrichmentStarted.current.delete(data.id);
      setBatchResult(data);
      setBatchSuccessMsg(`Lote recebido: ${batchPreflight.valid.length} CNPJ(s) aguardam higienização.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Falha ao executar o enriquecimento em lote.');
    } finally {
      setBatchSubmitting(false);
    }
  };

  const invalidItemsToDisplay = useMemo(() => {
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
  }, [batchPreflight.invalid]);

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
            {batchResult && batchIsTerminal(batchResult) && batchResult.status === 'COMPLETED'
              ? <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
              : batchResult && batchIsTerminal(batchResult)
                ? <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" />
                : <LoaderCircle className="h-5 w-5 animate-spin text-blue-600 shrink-0 mt-0.5" />}
            <div>
              <span className="font-bold text-sm block">{batchSuccessMsg}</span>
              <span className="text-xs opacity-80">
                {batchResult && batchIsTerminal(batchResult)
                  ? 'Revise os itens e as evidências antes de usar ou exportar os resultados.'
                  : 'O lote pode continuar após fechar esta página ou reiniciar a aplicação.'}
              </span>
              {batchResult && batchResult.total_rows > 0 && (
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs opacity-90">
                  <span>Total: <strong>{batchResult.total_rows}</strong></span>
                  <span>Processados: <strong>{batchResult.processed_rows}</strong></span>
                  {batchResult.duplicate_rows > 0 && (
                    <span>Duplicatas: <strong>{batchResult.duplicate_rows}</strong></span>
                  )}
                  {batchResult.succeeded_rows > 0 && (
                    <span>Com dados: <strong className="text-emerald-700">{batchResult.succeeded_rows}</strong></span>
                  )}
                  {batchResult.invalid_rows > 0 && (
                    <span>Inválidos: <strong className="text-red-700">{batchResult.invalid_rows}</strong></span>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {batchResult && batchIsTerminal(batchResult) && ['COMPLETED', 'PARTIAL'].includes(batchResult.status) && (
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
            {/* Seletor Tipo de Documento: CNPJ vs CPF */}
            <div className="flex items-center gap-2 p-1 bg-slate-100 rounded-xl w-fit">
              <button
                type="button"
                onClick={() => {
                  setDocType('CNPJ');
                  setResult(null);
                  setPersonResult(null);
                  setIndividualError(null);
                  setSelectedCapabilities(['cnpj_qsa', 'emails_smtp', 'phones_whatsapp']);
                }}
                className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                  docType === 'CNPJ'
                    ? 'bg-white text-blue-700 shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Building2 className="w-3.5 h-3.5" />
                Empresa (CNPJ)
              </button>
              <button
                type="button"
                onClick={() => {
                  setDocType('CPF');
                  setResult(null);
                  setPersonResult(null);
                  setIndividualError(null);
                  setSelectedCapabilities(['cpf_cadastral', 'phones_whatsapp_garantido']);
                }}
                className={`inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-bold transition-colors cursor-pointer ${
                  docType === 'CPF'
                    ? 'bg-emerald-600 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <User className="w-3.5 h-3.5" />
                Pessoa Física (CPF & WhatsApp Garantido)
              </button>
            </div>

            <div>
              <label htmlFor="enrichment-query" className="text-xs font-semibold text-slate-800">
                {docType === 'CPF'
                  ? 'Qual CPF você deseja enriquecer com WhatsApp garantido?'
                  : 'Qual empresa você quer analisar?'}
              </label>
              <div className="mt-1.5 text-[11px] text-slate-500">
                {docType === 'CPF'
                  ? 'Informe os 11 dígitos do CPF (com ou sem pontuação). O sistema valida os dados cadastrais e executa probe ativo no WhatsApp.'
                  : 'Cole um CNPJ (formatado ou não), o domínio do site institucional ou o nome da empresa.'}
              </div>
              <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                  <input
                    id="enrichment-query"
                    value={query}
                    onChange={(event) => { setQuery(event.target.value); setIndividualError(null); }}
                    onKeyDown={(e) => { if (e.key === 'Enter') void submitIndividual(e as unknown as FormEvent); }}
                    placeholder={docType === 'CPF' ? 'Ex.: 529.982.247-25 ou 52998224725' : 'Ex.: 33.000.167/0001-01, petrobras.com.br ou Petrobras'}
                    disabled={!status?.available || submitting}
                    className="h-11 w-full rounded-[10px] border border-slate-300 bg-white pl-10 pr-3 text-sm text-slate-950 outline-none placeholder:text-slate-500 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100"
                  />
                </div>
                <button
                  type="submit"
                  disabled={!status?.available || submitting || !query.trim() || !selectedCapabilities.length}
                  className={`inline-flex h-11 items-center justify-center gap-2 rounded-[10px] px-5 text-xs font-bold text-white disabled:cursor-not-allowed disabled:bg-slate-300 cursor-pointer ${
                    docType === 'CPF' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  {submitting ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <WandSparkles className="h-4 w-4" />}
                  {submitting
                    ? 'Consultando…'
                    : selectedCapabilities.length > 0
                      ? docType === 'CPF'
                        ? 'Enriquecer CPF & WhatsApp'
                        : `Consultar ${selectedCapabilities.length} dimensões`
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

            {/* Resultado de Pessoa Física (CPF & Consignado & WhatsApp) */}
            {personResult && (
              <div className="space-y-4">
                {/* 1. Camada 1: Filtro de Perda (Óbito & Expurgo) */}
                {personResult.filtroPerda?.status === 'EXPURGADO_OBITO' ? (
                  <div className="rounded-xl border-2 border-red-500 bg-red-950/20 p-5 shadow-lg">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                      <div className="flex items-center gap-4">
                        <div className="w-14 h-14 rounded-full bg-red-600 text-white flex items-center justify-center font-bold text-xl shadow-md shrink-0">
                          <Skull className="w-8 h-8 text-white" />
                        </div>
                        <div>
                          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-red-600 text-white shadow-sm mb-1">
                            <Ban className="w-3.5 h-3.5" /> Lead Expurgado por Óbito
                          </div>
                          <h3 className="text-base font-extrabold text-red-900 dark:text-red-300">
                            Falecimento Confirmado no Cadastro Central
                          </h3>
                          <p className="text-xs text-red-700 dark:text-red-400 mt-1">
                            {personResult.filtroPerda.death_date
                              ? `Data de Óbito registrada: ${personResult.filtroPerda.death_date}.`
                              : 'Registro de óbito identificado em bases previdenciárias e cartorárias.'}
                            {' '}Este lead foi classificado como <strong>inapto</strong> para operações de crédito consignado.
                          </p>
                        </div>
                      </div>
                      <div className="rounded-lg bg-emerald-100 border border-emerald-300 px-4 py-2 text-center text-xs font-bold text-emerald-800 shadow-sm shrink-0">
                        🛡️ Tarifa Zero Aplicada<br />
                        <span className="font-normal text-[11px] text-emerald-700">0 créditos cobrados</span>
                      </div>
                    </div>
                  </div>
                ) : personResult.filtroPerda?.status === 'EXPURGADO_RECEITA_IRREGULAR' ? (
                  <div className="rounded-xl border border-amber-300 bg-amber-50 p-4 flex items-start gap-3 text-xs text-amber-900 shadow-sm">
                    <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-bold uppercase tracking-wider">Situação Cadastral Irregular na Receita Federal</div>
                      <p className="mt-0.5">
                        O CPF encontra-se com situação <strong>{personResult.filtroPerda.tax_status}</strong>. Inapto para operações financeiras.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 px-4 py-2.5 flex items-center justify-between text-xs text-emerald-900 shadow-xs">
                    <div className="flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span>
                        Filtro de Perda: <strong>Lead Apto & Regular</strong> · Situação RFB:{' '}
                        <strong>{personResult.person?.taxStatus ?? 'REGULAR'}</strong>
                      </span>
                    </div>
                    <span className="text-[11px] font-bold text-emerald-700 bg-emerald-100 border border-emerald-200 px-2 py-0.5 rounded-full">
                      Zero Óbito
                    </span>
                  </div>
                )}

                {/* 2. Destaque do WhatsApp Ativo Garantido */}
                {personResult.whatsappGarantido?.garantido ? (
                  <div className="rounded-xl border border-emerald-300 bg-emerald-50/90 p-5 shadow-sm">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                      <div className="flex items-center gap-4">
                        {personResult.whatsappGarantido.fotoPerfil ? (
                          <img
                            src={personResult.whatsappGarantido.fotoPerfil}
                            alt="Foto WhatsApp"
                            className="w-14 h-14 rounded-full object-cover border-2 border-emerald-500 shadow"
                          />
                        ) : (
                          <div className="w-14 h-14 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-xl shadow">
                            <PhoneCall className="w-6 h-6" />
                          </div>
                        )}
                        <div>
                          <div className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase bg-emerald-200 text-emerald-900 mb-1">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" /> WhatsApp Ativo Garantido (Probe Oficial)
                          </div>
                          <h3 className="text-base font-bold text-slate-900">{personResult.whatsappGarantido.numero}</h3>
                          <p className="text-xs text-slate-600 mt-0.5">
                            Conta: <span className="font-semibold text-slate-800">{personResult.whatsappGarantido.tipoConta}</span> · Titular: <span className="font-semibold text-slate-900">{personResult.person?.name}</span> (CPF: <span className="font-mono font-bold text-slate-900">{personResult.person?.cpf}</span>)
                          </p>
                        </div>
                      </div>
                      <a
                        href={personResult.whatsappGarantido.linkDireto}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-colors shadow cursor-pointer whitespace-nowrap"
                      >
                        <Zap className="w-4 h-4" /> Abrir conversa no WhatsApp
                      </a>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 flex items-start gap-3 text-xs text-slate-700">
                    <Info className="w-5 h-5 text-slate-500 shrink-0 mt-0.5" />
                    <div>
                      <div className="font-bold uppercase tracking-wider text-slate-800">Status do WhatsApp Probe</div>
                      <p className="mt-0.5 text-slate-600">
                        {personResult.telefonesAtribuiveis && personResult.telefonesAtribuiveis.length > 0
                          ? 'Nenhum dos telefones identificados no cadastro possui conta ativa no WhatsApp no momento.'
                          : 'Nenhum número de celular com WhatsApp ativo foi atestado para este CPF.'}
                      </p>
                    </div>
                  </div>
                )}

                {/* 3. Camada 2: Core Consignado (INSS / SIAPE & 4 Cards de Margem) */}
                {personResult.consignado && personResult.consignado.salarioBase > 0 && (
                  <div className="rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/70 via-white to-blue-50/50 p-5 shadow-sm space-y-4">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 border-b border-indigo-100 pb-3">
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <Landmark className="w-5 h-5 text-indigo-600" />
                          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                            Core Consignado · {personResult.consignado.vinculoPrincipal}
                          </h3>
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wider ${
                              personResult.consignado.categoriaElegibilidade === 'APTO_CONSIGNAVEL'
                                ? 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                                : personResult.consignado.categoriaElegibilidade === 'RESTRITO_BPC'
                                ? 'bg-amber-100 text-amber-800 border border-amber-200'
                                : 'bg-slate-100 text-slate-800'
                            }`}
                          >
                            {personResult.consignado.categoriaElegibilidade === 'APTO_CONSIGNAVEL'
                              ? '✅ Apto para Consignado'
                              : personResult.consignado.categoriaElegibilidade === 'RESTRITO_BPC'
                              ? '⚠️ BPC/LOAS (Regras Específicas)'
                              : personResult.consignado.categoriaElegibilidade}
                          </span>
                        </div>
                        <p className="text-xs text-slate-600 mt-1">
                          {personResult.consignado.numeroBeneficio && personResult.consignado.numeroBeneficio !== 'N/A' && (
                            <>
                              NB: <strong className="font-mono text-slate-800">{personResult.consignado.numeroBeneficio}</strong> ·{' '}
                            </>
                          )}
                          Espécie: <strong>{personResult.consignado.especieDescricao}</strong>
                        </p>
                        {personResult.consignado.alerta && (
                          <p className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mt-1.5 inline-block">
                            ℹ️ {personResult.consignado.alerta}
                          </p>
                        )}
                      </div>
                      <div className="text-right">
                        <span className="text-[11px] text-slate-500 block">Salário/Benefício Base</span>
                        <span className="text-base font-extrabold text-slate-900">
                          {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(
                            personResult.consignado.salarioBase
                          )}
                        </span>
                      </div>
                    </div>

                    {/* Os 4 Cards de Margem Consignável (Lei 14.431/2022) */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
                        <div className="flex items-center justify-between text-slate-500 mb-1">
                          <span className="text-[11px] font-semibold">Empréstimo (35%)</span>
                          <CreditCard className="w-4 h-4 text-blue-600" />
                        </div>
                        <div className="text-base font-extrabold text-blue-700">
                          {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(
                            personResult.consignado.margemEmprestimo35
                          )}
                        </div>
                        <span className="text-[10px] text-slate-400">Parcelas fixas mensais</span>
                      </div>

                      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
                        <div className="flex items-center justify-between text-slate-500 mb-1">
                          <span className="text-[11px] font-semibold">Cartão RMC (5%)</span>
                          <CreditCard className="w-4 h-4 text-purple-600" />
                        </div>
                        <div className="text-base font-extrabold text-purple-700">
                          {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(
                            personResult.consignado.margemRmcCartao5
                          )}
                        </div>
                        <span className="text-[10px] text-slate-400">Reserva de margem cartão</span>
                      </div>

                      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-xs">
                        <div className="flex items-center justify-between text-slate-500 mb-1">
                          <span className="text-[11px] font-semibold">Cartão RCC (5%)</span>
                          <CreditCard className="w-4 h-4 text-teal-600" />
                        </div>
                        <div className="text-base font-extrabold text-teal-700">
                          {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(
                            personResult.consignado.margemRccBeneficio5
                          )}
                        </div>
                        <span className="text-[10px] text-slate-400">Benefício consignado</span>
                      </div>

                      <div className="rounded-lg border-2 border-indigo-500 bg-indigo-600 text-white p-3 shadow-sm">
                        <div className="flex items-center justify-between text-indigo-100 mb-1">
                          <span className="text-[11px] font-bold uppercase tracking-wider">Margem Total (45%)</span>
                          <Zap className="w-4 h-4 text-amber-300" />
                        </div>
                        <div className="text-base font-black text-white">
                          {new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(
                            personResult.consignado.margemTotal45
                          )}
                        </div>
                        <span className="text-[10px] text-indigo-200">Total estimada (Lei 14.431)</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* 4. Camada 4: Mailing Higienizado Top 3 com Operadora & Não Me Perturbe */}
                {personResult.mailingTop3 && personResult.mailingTop3.length > 0 && (
                  <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
                    <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 border-b border-slate-100 pb-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <Phone className="w-4 h-4 text-emerald-600" />
                          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                            Mailing Higienizado · Top 3 Telefones Qualificados
                          </h3>
                        </div>
                        <p className="text-[11px] text-slate-500 mt-0.5">
                          Telefones ordenados por probabilidade de conversão, operadora ativa e conformidade regulatória.
                        </p>
                      </div>
                      <span className="text-[10px] font-bold text-slate-500 uppercase bg-slate-100 px-2.5 py-1 rounded-full">
                        Blindagem Anatel & Febraban
                      </span>
                    </div>

                    <div className="grid gap-2.5">
                      {personResult.mailingTop3.map((phone) => (
                        <div
                          key={phone.numeroRaw}
                          className={`rounded-lg border p-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 transition-colors ${
                            phone.naoMePerturbe.inscrito_nao_me_perturbe
                              ? 'border-red-200 bg-red-50/40 hover:bg-red-50/70'
                              : 'border-slate-200 bg-slate-50/60 hover:bg-slate-50'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className="w-6 h-6 rounded-full bg-slate-800 text-white flex items-center justify-center text-xs font-extrabold shrink-0">
                              {phone.ordemRecomendada}º
                            </span>
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="font-mono text-sm font-bold text-slate-900">
                                  {phone.numeroFormatado}
                                </span>
                                <span
                                  className={`px-2 py-0.5 rounded text-[10px] font-extrabold uppercase ${
                                    phone.operadora === 'VIVO'
                                      ? 'bg-purple-100 text-purple-800 border border-purple-200'
                                      : phone.operadora === 'CLARO'
                                      ? 'bg-red-100 text-red-800 border border-red-200'
                                      : phone.operadora === 'TIM'
                                      ? 'bg-blue-100 text-blue-800 border border-blue-200'
                                      : 'bg-slate-200 text-slate-700'
                                  }`}
                                >
                                  {phone.operadora}
                                </span>

                                {phone.naoMePerturbe.inscrito_nao_me_perturbe ? (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase bg-red-600 text-white shadow-xs inline-flex items-center gap-1">
                                    <Ban className="w-3 h-3" /> Não Me Perturbe
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase bg-emerald-100 text-emerald-800 border border-emerald-200 inline-flex items-center gap-1">
                                    <CheckCircle2 className="w-3 h-3 text-emerald-700" /> Liberado p/ Discagem
                                  </span>
                                )}

                                {phone.whatsappDisponivel ? (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-extrabold uppercase bg-emerald-600 text-white inline-flex items-center gap-1 shadow-xs">
                                    <Zap className="w-3 h-3 text-emerald-200" /> WhatsApp Ativo
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-normal text-slate-500 bg-slate-100">
                                    Sem WhatsApp
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-slate-600 mt-1">
                                {phone.rotuloCanal} · Score de Assertividade: <strong>{phone.scoreAssertividade}/100</strong>
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                            <button
                              type="button"
                              onClick={() => void navigator.clipboard?.writeText(phone.numeroFormatado)}
                              className="px-2.5 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 text-[11px] font-semibold text-slate-700 inline-flex items-center gap-1 transition-colors cursor-pointer"
                              title="Copiar número"
                            >
                              <Copy className="w-3.5 h-3.5" /> Copiar
                            </button>
                            {phone.whatsappDisponivel && phone.linkWhatsApp && (
                              <a
                                href={phone.linkWhatsApp}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-[11px] font-bold inline-flex items-center gap-1.5 shadow-sm transition-colors cursor-pointer"
                              >
                                <MessageSquare className="w-3.5 h-3.5" /> Conversar
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Seções de dados de Pessoa Física */}
                <div className="space-y-3 border border-slate-200 rounded-xl bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-slate-800">Dossiê da Pessoa Física</div>
                      <div className="mt-0.5 text-[11px] text-slate-600">
                        Titular: <strong>{personResult.person?.name}</strong> · CPF:{' '}
                        <strong className="font-mono">{personResult.person?.cpf}</strong>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        if (personResult.person?.cpf) void navigator.clipboard?.writeText(personResult.person.cpf);
                      }}
                      className="text-[11px] font-semibold text-emerald-700 hover:text-emerald-900 inline-flex items-center gap-1"
                      title="Copiar CPF"
                    >
                      <Copy className="h-3.5 w-3.5" /> Copiar CPF
                    </button>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-white divide-y divide-slate-100">
                    {(personResult.sections || []).map((sec) => {
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
                              {sec.summary && <p className="mt-1 text-[11px] text-slate-700">{sec.summary}</p>}
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
                                  <span className="text-slate-500 shrink-0 w-36">{f.label}</span>
                                  <span className="text-slate-800 flex-1 font-medium break-words">{f.value || <span className="text-slate-400">—</span>}</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* Resultado de Empresa (CNPJ) */}
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
                    onClick={() => {
                      void api.enrichmentJob<CompanyEnrichmentResult | PersonEnrichmentResult>(run.id)
                        .then((job) => {
                          if (!job.result) return;
                          if (run.entityType === 'PERSON') setPersonResult(job.result as PersonEnrichmentResult);
                          else setResult(job.result as CompanyEnrichmentResult);
                          setActiveTab('INDIVIDUAL');
                        })
                        .catch((cause) => setIndividualError(cause instanceof Error ? cause.message : 'Não foi possível abrir o resultado.'));
                    }}
                    className="text-[11px] font-semibold text-blue-700 hover:text-blue-900"
                  >
                    Ver resultado
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
