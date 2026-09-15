import { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Building2,
  ChevronLeft,
  ChevronRight,
  Download,
  Eye,
  FileUp,
  FilterX,
  Linkedin,
  ListPlus,
  LoaderCircle,
  Mail,
  MapPin,
  Phone,
  Plus,
  Search,
  UserRound,
  X,
} from 'lucide-react';
import { api } from '../api';
import AddToListModal from '../components/AddToListModal';
import CreateLeadSetModal from '../components/CreateLeadSetModal';
import EvidenceBadge from '../components/EvidenceBadge';
import ExportModal from '../components/ExportModal';
import LeadDetailsModal from '../components/LeadDetailsModal';
import UploadEnrichModal from '../components/UploadEnrichModal';
import { useLeadStream } from '../LeadStreamContext';
import type {
  CreateDatasetInput,
  EvidenceStatus,
  ImportResult,
  Lead,
  LeadSearchResponse,
} from '../types';

interface SearchLeadsProps {
  initialSetFilterId?: string | null;
  onClearSetFilter?: () => void;
}

const states = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MT', 'MS', 'MG',
  'PA', 'PB', 'PR', 'PE', 'PI', 'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
];

const emptyPage: LeadSearchResponse = {
  count: 0,
  page: 1,
  pageSize: 25,
  totalPages: 0,
  nextPage: null,
  previousPage: null,
  facets: { PJ: 0, PF: 0 },
  results: [],
};

function initialQuery() {
  const params = new URLSearchParams(window.location.search);
  const leadType = params.get('lead_type');
  return {
    q: params.get('q') || '',
    leadType: leadType === 'PJ' || leadType === 'PF' ? leadType : 'ALL',
    uf: params.get('uf') || '',
    cnae: params.get('cnae') || '',
    companySize: params.get('company_size') || '',
    emailStatus: params.get('email_status') || 'all',
    hasPhone: params.get('has_phone') === 'true',
    page: Math.max(Number(params.get('page')) || 1, 1),
  } as const;
}

function formatDocument(value?: string) {
  const digits = (value || '').replace(/\D/g, '');
  if (digits.length !== 14) return value || 'Não informado';
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

function formatDate(value?: string) {
  if (!value) return 'Sem data de atualização';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Data não informada';
  return new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short' }).format(date);
}

function bestEvidence(lead: Lead): EvidenceStatus {
  const order: EvidenceStatus[] = [
    'CONFIRMED',
    'TECHNICALLY_VALIDATED',
    'OBSERVED',
    'INFERRED',
    'CONFLICTING',
    'REJECTED',
    'ABSENT',
  ];
  return order.find((status) => (
    lead.emailEvidenceStatus === status || lead.phoneEvidenceStatus === status
  )) || 'ABSENT';
}

export default function SearchEnterprise({
  initialSetFilterId = null,
  onClearSetFilter,
}: SearchLeadsProps) {
  const {
    datasets,
    lists,
    createDataset,
    createList,
    addLeadsToList,
    revealPhone,
  } = useLeadStream();
  const initial = useMemo(initialQuery, []);
  const [queryInput, setQueryInput] = useState(initial.q);
  const [query, setQuery] = useState(initial.q);
  const [leadType, setLeadType] = useState<'ALL' | 'PJ' | 'PF'>(initial.leadType);
  const [uf, setUf] = useState(initial.uf);
  const [cnae, setCnae] = useState(initial.cnae);
  const [companySize, setCompanySize] = useState(initial.companySize);
  const [emailStatus, setEmailStatus] = useState(initial.emailStatus);
  const [hasPhone, setHasPhone] = useState(initial.hasPhone);
  const [datasetId, setDatasetId] = useState<string | null>(initialSetFilterId);
  const [pageNumber, setPageNumber] = useState(initial.page);
  const [page, setPage] = useState<LeadSearchResponse>(emptyPage);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [selected, setSelected] = useState<Record<string, Lead>>({});
  const [activeLead, setActiveLead] = useState<Lead | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [showCreateDataset, setShowCreateDataset] = useState(false);
  const [showAddToList, setShowAddToList] = useState(false);
  const [showExport, setShowExport] = useState(false);

  const selectedLeads = Object.values(selected);
  const selectedIds = Object.keys(selected);
  const activeDataset = datasets.find((dataset) => dataset.id === datasetId);
  const hasActiveFilters = Boolean(
    query || leadType !== 'ALL' || uf || cnae || companySize || emailStatus !== 'all' || hasPhone,
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPageNumber(1);
      setQuery(queryInput.trim());
    }, 320);
    return () => window.clearTimeout(timer);
  }, [queryInput]);

  useEffect(() => {
    setDatasetId(initialSetFilterId);
    setPageNumber(1);
  }, [initialSetFilterId]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3500);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const params = new URLSearchParams();
    if (query) params.set('q', query);
    if (leadType !== 'ALL') params.set('lead_type', leadType);
    if (uf) params.set('uf', uf);
    if (cnae) params.set('cnae', cnae);
    if (companySize) params.set('company_size', companySize);
    if (emailStatus !== 'all') params.set('email_status', emailStatus);
    if (hasPhone) params.set('has_phone', 'true');
    if (pageNumber > 1) params.set('page', String(pageNumber));
    window.history.replaceState({}, '', `${window.location.pathname}${params.size ? `?${params}` : ''}`);
  }, [cnae, companySize, emailStatus, hasPhone, leadType, pageNumber, query, uf]);

  useEffect(() => {
    let current = true;
    setLoading(true);
    setError(null);
    void api.leads({
      page: pageNumber,
      pageSize: 25,
      q: query || undefined,
      leadType: leadType === 'ALL' ? undefined : leadType,
      datasetId: datasetId || undefined,
      uf: uf || undefined,
      cnae: cnae || undefined,
      companySize: companySize || undefined,
      emailStatus: emailStatus as 'all' | 'verified' | 'catchall' | 'invalid',
      hasPhone: hasPhone || undefined,
    }).then((result) => {
      if (current) setPage(result);
    }).catch((cause) => {
      if (current) setError(cause instanceof Error ? cause.message : 'Não foi possível carregar os leads.');
    }).finally(() => {
      if (current) setLoading(false);
    });
    return () => {
      current = false;
    };
  }, [cnae, companySize, datasetId, emailStatus, hasPhone, leadType, pageNumber, query, reloadToken, uf]);

  const clearFilters = () => {
    setQueryInput('');
    setQuery('');
    setLeadType('ALL');
    setUf('');
    setCnae('');
    setCompanySize('');
    setEmailStatus('all');
    setHasPhone(false);
    setPageNumber(1);
  };

  const togglePage = (checked: boolean) => {
    setSelected((current) => {
      const next = { ...current };
      for (const lead of page.results) {
        if (checked) next[lead.id] = lead;
        else delete next[lead.id];
      }
      return next;
    });
  };

  const toggleLead = (lead: Lead) => {
    setSelected((current) => {
      const next = { ...current };
      if (next[lead.id]) delete next[lead.id];
      else next[lead.id] = lead;
      return next;
    });
  };

  const handleReveal = async (lead: Lead) => {
    try {
      const updated = await revealPhone(lead.id);
      setPage((current) => ({
        ...current,
        results: current.results.map((item) => item.id === updated.id ? updated : item),
      }));
      setToast('Telefone disponibilizado com o nível de evidência registrado.');
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : 'Não foi possível disponibilizar o telefone.');
    }
  };

  const handleAdd = async (listId: string, leadIds: string[]) => {
    try {
      const target = await addLeadsToList(listId, leadIds);
      setSelected({});
      setToast(`${leadIds.length} registro(s) adicionado(s) à lista “${target.name}”.`);
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : 'Não foi possível atualizar a lista.');
    }
  };

  const handleCreateList = async (name: string, description: string) => {
    try {
      const created = await createList({ name, description, leadIds: selectedIds });
      setSelected({});
      setToast(`Lista “${created.name}” criada com ${selectedIds.length} registro(s).`);
    } catch (cause) {
      setToast(cause instanceof Error ? cause.message : 'Não foi possível criar a lista.');
    }
  };

  const handleImport = (result: ImportResult) => {
    setDatasetId(result.dataset.id);
    setPageNumber(1);
    setReloadToken((value) => value + 1);
    setShowUpload(false);
    setToast(`${result.imported} linha(s) recebida(s); o processamento continua em segundo plano.`);
  };

  const handleCreateDataset = async (input: CreateDatasetInput) => {
    const created = await createDataset(input);
    setDatasetId(created.id);
    setPageNumber(1);
    return created;
  };

  return (
    <section className="mx-auto flex h-full max-w-[1500px] flex-col gap-4 pb-8" aria-label="Consulta de leads">
      {toast && (
        <div className="fixed bottom-5 right-5 z-[var(--z-toast)] max-w-md rounded-[10px] bg-slate-900 px-4 py-3 text-sm font-medium text-white shadow-lg" role="status">
          {toast}
        </div>
      )}

      <LeadDetailsModal
        lead={activeLead}
        onClose={() => setActiveLead(null)}
        onAddToList={(lead) => {
          setSelected((current) => ({ ...current, [lead.id]: lead }));
          setShowAddToList(true);
        }}
      />
      <ExportModal isOpen={showExport} onClose={() => setShowExport(false)} leads={selectedLeads} selectedIds={selectedIds} />
      <AddToListModal
        isOpen={showAddToList}
        onClose={() => setShowAddToList(false)}
        lists={lists}
        leadsToAdd={selectedLeads}
        onAdd={handleAdd}
        onCreateNewList={handleCreateList}
      />
      <UploadEnrichModal
        isOpen={showUpload}
        onClose={() => setShowUpload(false)}
        onSuccess={handleImport}
        existingSets={datasets}
      />
      <CreateLeadSetModal
        isOpen={showCreateDataset}
        onClose={() => setShowCreateDataset(false)}
        onCreateSet={handleCreateDataset}
      />

      {activeDataset && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] bg-slate-900 px-4 py-3 text-white">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">Base: {activeDataset.name}</p>
            <p className="mt-0.5 text-xs text-slate-300">A consulta está restrita aos registros desta base.</p>
          </div>
          <button
            type="button"
            onClick={() => {
              setDatasetId(null);
              onClearSetFilter?.();
            }}
            className="inline-flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-slate-100 hover:bg-slate-800 focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <X className="h-4 w-4" /> Remover filtro
          </button>
        </div>
      )}

      <div className="flex flex-col gap-3 rounded-[12px] border border-slate-200 bg-white p-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
          <label className="relative min-w-0 flex-1">
            <span className="sr-only">Buscar por nome, empresa, cargo, CNPJ ou CPF mascarado</span>
            <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-500" aria-hidden="true" />
            <input
              value={queryInput}
              onChange={(event) => setQueryInput(event.target.value)}
              className="min-h-10 w-full rounded-lg border border-slate-300 bg-white py-2 pl-10 pr-3 text-sm text-slate-900 placeholder:text-slate-500 hover:border-slate-400 focus:border-blue-600 focus:outline-none"
              placeholder="Buscar nome, empresa, cargo, CNPJ ou CPF mascarado"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => setShowCreateDataset(true)} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-800 hover:bg-slate-50">
              <Plus className="h-4 w-4" /> Nova base
            </button>
            <button type="button" onClick={() => setShowUpload(true)} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700 disabled:bg-slate-300">
              <FileUp className="h-4 w-4" /> Importar e processar
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-3 border-t border-slate-100 pt-3">
          <div className="flex min-h-10 rounded-lg bg-slate-100 p-1" aria-label="Tipo de lead">
            {(['ALL', 'PJ', 'PF'] as const).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => { setLeadType(type); setPageNumber(1); }}
                aria-pressed={leadType === type}
                className={`rounded-md px-3 text-sm font-semibold ${leadType === type ? 'bg-white text-slate-950 shadow-xs' : 'text-slate-600 hover:text-slate-900'}`}
              >
                {type === 'ALL' ? `Todos (${page.facets.PJ + page.facets.PF})` : `${type} (${page.facets[type]})`}
              </button>
            ))}
          </div>
          <label className="min-w-24 text-xs font-semibold text-slate-700">
            Estado
            <select value={uf} onChange={(event) => { setUf(event.target.value); setPageNumber(1); }} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal text-slate-900">
              <option value="">Brasil</option>
              {states.map((state) => <option key={state} value={state}>{state}</option>)}
            </select>
          </label>
          <label className="min-w-36 flex-1 text-xs font-semibold text-slate-700 sm:max-w-48">
            CNAE
            <input value={cnae} onChange={(event) => { setCnae(event.target.value.replace(/\D/g, '').slice(0, 7)); setPageNumber(1); }} inputMode="numeric" className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 px-3 text-sm font-normal" placeholder="Ex.: 6201501" />
          </label>
          <label className="min-w-36 text-xs font-semibold text-slate-700">
            Porte
            <select value={companySize} onChange={(event) => { setCompanySize(event.target.value); setPageNumber(1); }} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal">
              <option value="">Todos</option>
              <option value="MEI">MEI</option>
              <option value="ME">Microempresa</option>
              <option value="EPP">Pequena empresa</option>
              <option value="DEMAIS">Demais</option>
            </select>
          </label>
          <label className="min-w-40 text-xs font-semibold text-slate-700">
            Qualidade do e-mail
            <select value={emailStatus} onChange={(event) => { setEmailStatus(event.target.value); setPageNumber(1); }} className="mt-1 min-h-10 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm font-normal">
              <option value="all">Todos</option>
              <option value="verified">Validado</option>
              <option value="catchall">Catch-all</option>
              <option value="invalid">Inválido</option>
            </select>
          </label>
          <label className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm font-medium text-slate-700">
            <input type="checkbox" checked={hasPhone} onChange={(event) => { setHasPhone(event.target.checked); setPageNumber(1); }} className="h-4 w-4 accent-blue-600" />
            Com telefone
          </label>
          {hasActiveFilters && (
            <button type="button" onClick={clearFilters} className="inline-flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-slate-600 hover:bg-slate-100 hover:text-slate-950">
              <FilterX className="h-4 w-4" /> Limpar
            </button>
          )}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-hidden rounded-[12px] border border-slate-200 bg-white">
        <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-2">
          <div>
            <p className="text-sm font-semibold text-slate-950">{page.count.toLocaleString('pt-BR')} registro(s)</p>
            <p className="text-xs text-slate-600">Dados paginados no servidor · até 25 por página</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {selectedIds.length > 0 && <span className="text-sm font-semibold text-blue-700">{selectedIds.length} selecionado(s)</span>}
            <button type="button" disabled={!selectedIds.length} onClick={() => setShowAddToList(true)} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
              <ListPlus className="h-4 w-4" /> Adicionar à lista
            </button>
            <button type="button" disabled={!selectedIds.length} onClick={() => setShowExport(true)} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm font-semibold text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50">
              <Download className="h-4 w-4" /> Exportar seleção
            </button>
          </div>
        </div>

        {error ? (
          <div className="flex min-h-72 flex-col items-center justify-center px-6 text-center" role="alert">
            <AlertCircle className="h-8 w-8 text-rose-600" />
            <h2 className="mt-3 text-base font-bold text-slate-950">A consulta não pôde ser concluída</h2>
            <p className="mt-1 max-w-[65ch] text-sm text-slate-600">{error}</p>
            <button type="button" onClick={() => setReloadToken((value) => value + 1)} className="mt-4 min-h-10 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700">Tentar novamente</button>
          </div>
        ) : loading ? (
          <div className="flex min-h-72 items-center justify-center gap-3 text-sm font-medium text-slate-600" role="status">
            <LoaderCircle className="h-5 w-5 animate-spin text-blue-600" /> Consultando o índice operacional…
          </div>
        ) : page.results.length === 0 ? (
          <div className="flex min-h-72 flex-col items-center justify-center px-6 text-center">
            <Search className="h-8 w-8 text-slate-400" />
            <h2 className="mt-3 text-base font-bold text-slate-950">Nenhum registro corresponde aos filtros</h2>
            <p className="mt-1 max-w-[65ch] text-sm text-slate-600">Ajuste os filtros ou importe uma base para iniciar a higienização e o enriquecimento.</p>
            <div className="mt-4 flex gap-2">
              {hasActiveFilters && <button type="button" onClick={clearFilters} className="min-h-10 rounded-lg border border-slate-300 px-4 text-sm font-semibold">Limpar filtros</button>}
              <button type="button" onClick={() => setShowUpload(true)} className="min-h-10 rounded-lg bg-blue-600 px-4 text-sm font-semibold text-white">Importar base</button>
            </div>
          </div>
        ) : (
          <div className="overflow-auto">
            <table className="w-full min-w-[1080px] border-collapse text-left text-sm">
              <thead className="sticky top-0 z-[var(--z-sticky)] bg-slate-50 text-xs font-semibold text-slate-700">
                <tr>
                  <th className="w-12 border-b border-slate-200 px-4 py-3">
                    <input type="checkbox" aria-label="Selecionar página" checked={page.results.every((lead) => selected[lead.id])} onChange={(event) => togglePage(event.target.checked)} className="h-4 w-4 accent-blue-600" />
                  </th>
                  <th className="border-b border-slate-200 px-3 py-3">Lead</th>
                  <th className="border-b border-slate-200 px-3 py-3">Empresa e função</th>
                  <th className="border-b border-slate-200 px-3 py-3">Localização</th>
                  <th className="border-b border-slate-200 px-3 py-3">Canais observados</th>
                  <th className="border-b border-slate-200 px-3 py-3">Evidência</th>
                  <th className="border-b border-slate-200 px-3 py-3">Atualização</th>
                  <th className="w-14 border-b border-slate-200 px-3 py-3"><span className="sr-only">Ações</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {page.results.map((lead) => (
                  <tr key={lead.id} className="group hover:bg-slate-50/80">
                    <td className="px-4 py-3 align-top"><input type="checkbox" aria-label={`Selecionar ${lead.name}`} checked={Boolean(selected[lead.id])} onChange={() => toggleLead(lead)} className="mt-1 h-4 w-4 accent-blue-600" /></td>
                    <td className="max-w-[260px] px-3 py-3 align-top">
                      <button type="button" onClick={() => setActiveLead(lead)} className="flex min-w-0 items-start gap-3 text-left">
                        <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${lead.leadType === 'PJ' ? 'bg-blue-50 text-blue-700' : 'bg-violet-50 text-violet-700'}`}>
                          {lead.leadType === 'PJ' ? <Building2 className="h-4 w-4" /> : <UserRound className="h-4 w-4" />}
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate font-semibold text-slate-950" title={lead.name}>{lead.name}</span>
                          <span className="mt-0.5 block text-xs text-slate-600">{lead.leadType} · {lead.leadType === 'PJ' ? formatDocument(lead.cnpj) : lead.cpf || 'CPF não informado'}</span>
                        </span>
                      </button>
                    </td>
                    <td className="max-w-[260px] px-3 py-3 align-top">
                      <p className="truncate font-medium text-slate-900" title={lead.company || lead.razaoSocial}>{lead.company || lead.razaoSocial || 'Sem vínculo empresarial'}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-600" title={lead.title || lead.industry}>{lead.title || lead.industry || 'Função ou atividade não informada'}</p>
                    </td>
                    <td className="px-3 py-3 align-top">
                      <span className="inline-flex items-center gap-1.5 text-slate-700"><MapPin className="h-3.5 w-3.5 text-slate-400" />{lead.city || 'Cidade não informada'}{lead.state ? ` / ${lead.state}` : ''}</span>
                    </td>
                    <td className="max-w-[250px] px-3 py-3 align-top">
                      <div className="space-y-1.5">
                        <p className="flex min-w-0 items-center gap-2 text-xs text-slate-700"><Mail className="h-3.5 w-3.5 shrink-0 text-slate-400" /><span className="truncate">{lead.email || 'E-mail ausente'}</span></p>
                        <p className="flex min-w-0 items-center gap-2 text-xs text-slate-700"><Phone className="h-3.5 w-3.5 shrink-0 text-slate-400" /><span className="truncate">{lead.phone || 'Telefone ausente'}</span>{lead.phone && !lead.phoneRevealed && <button type="button" onClick={() => void handleReveal(lead)} className="font-semibold text-blue-700 hover:underline">ver</button>}</p>
                      </div>
                    </td>
                    <td className="px-3 py-3 align-top"><EvidenceBadge status={bestEvidence(lead)} compact /></td>
                    <td className="px-3 py-3 align-top">
                      <p className="text-xs font-medium text-slate-700">{formatDate(lead.observedAt || lead.updatedAt)}</p>
                      <p className="mt-0.5 max-w-32 truncate text-xs text-slate-500" title={lead.source}>{lead.source || 'Fonte não informada'}</p>
                    </td>
                    <td className="px-3 py-3 align-top">
                      <div className="flex items-center gap-1">
                        {lead.linkedinUrl && <a href={lead.linkedinUrl} target="_blank" rel="noreferrer" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-blue-700" aria-label={`Abrir LinkedIn de ${lead.name}`}><Linkedin className="h-4 w-4" /></a>}
                        <button type="button" onClick={() => setActiveLead(lead)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-950" aria-label={`Ver detalhes de ${lead.name}`}><Eye className="h-4 w-4" /></button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && page.count > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-4 py-3">
            <p className="text-xs text-slate-600">Página {page.page} de {page.totalPages} · {page.count.toLocaleString('pt-BR')} registro(s)</p>
            <div className="flex gap-2">
              <button type="button" disabled={!page.previousPage} onClick={() => setPageNumber(page.previousPage || 1)} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"><ChevronLeft className="h-4 w-4" /> Anterior</button>
              <button type="button" disabled={!page.nextPage} onClick={() => setPageNumber(page.nextPage || pageNumber)} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50">Próxima <ChevronRight className="h-4 w-4" /></button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
