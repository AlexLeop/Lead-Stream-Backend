import { useState, useEffect } from 'react';
import {
  ArrowRight,
  Database,
  Search,
  CheckCircle2,
  AlertCircle,
  Building2,
  MapPin,
  Sparkles,
  Loader2,
  X,
  FilePlus2,
  Layers,
} from 'lucide-react';
import { api } from '../api';
import type {
  CnaeItem,
  DiscoverySearchResult,
  CanonicalCompanyPreview,
} from '../types';
import { useLeadStream } from '../LeadStreamContext';

interface CnaeDiscoveryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccessExtract?: () => void;
  onImport?: () => void;
}

const BRAZILIAN_STATES = [
  'Todos os Estados',
  'SP',
  'RJ',
  'MG',
  'RS',
  'PR',
  'SC',
  'BA',
  'PE',
  'CE',
  'GO',
  'DF',
  'ES',
  'MT',
  'MS',
  'PA',
  'AM',
  'RN',
  'PB',
  'AL',
  'SE',
  'PI',
  'MA',
  'RO',
  'TO',
  'AC',
  'AP',
  'RR',
];

export default function CnaeDiscoveryModal({
  isOpen,
  onClose,
  onSuccessExtract,
}: CnaeDiscoveryModalProps) {
  const { refreshWorkspace } = useLeadStream();

  // Estados de Filtro
  const [cnaeQuery, setCnaeQuery] = useState('');
  const [cnaeOptions, setCnaeOptions] = useState<CnaeItem[]>([]);
  const [selectedCnae, setSelectedCnae] = useState<CnaeItem | null>(null);
  const [selectedSecondaryCnaes, setSelectedSecondaryCnaes] = useState<CnaeItem[]>([]);
  const [selectedUf, setSelectedUf] = useState('SP');
  const [selectedPorte, setSelectedPorte] = useState<'TODOS' | 'ME' | 'EPP' | 'DEMAIS'>('EPP');
  const [situacaoAtiva, setSituacaoAtiva] = useState(true);

  // Estados de Execução & Amostra
  const [isSearching, setIsSearching] = useState(false);
  const [searchResult, setSearchResult] = useState<DiscoverySearchResult | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Estados de Extração
  const [datasetName, setDatasetName] = useState('');
  const [extractLimit, setExtractLimit] = useState(50);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractSuccess, setExtractSuccess] = useState<string | null>(null);

  // Buscar sugestões de CNAE conforme o usuário digita
  useEffect(() => {
    if (!cnaeQuery.trim() || cnaeQuery.length < 2) {
      setCnaeOptions([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const results = await api.discoveryCnaes(cnaeQuery, 10);
        setCnaeOptions(results);
      } catch {
        setCnaeOptions([]);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [cnaeQuery]);

  // Pré-preencher nome do dataset sugerido
  useEffect(() => {
    if (selectedCnae) {
      const cnaeCode = selectedCnae.codigo || selectedCnae.code;
      const ufText = selectedUf !== 'Todos os Estados' ? selectedUf : 'Brasil';
      setDatasetName(`Prospecção ${cnaeCode} - ${ufText}`);
    }
  }, [selectedCnae, selectedUf]);

  if (!isOpen) return null;

  const handleRunSearch = async () => {
    setIsSearching(true);
    setSearchError(null);
    setExtractSuccess(null);

    try {
      const result = await api.discoverySearch({
        cnaePrincipal: selectedCnae ? (selectedCnae.codigo || selectedCnae.code) : undefined,
        cnaesSecundarios: selectedSecondaryCnaes.map((c) => c.codigo || c.code),
        uf: selectedUf !== 'Todos os Estados' ? selectedUf : undefined,
        porte: selectedPorte,
        situacaoCadastral: situacaoAtiva ? 'ATIVA' : 'TODAS',
        limiteAmostra: 10,
      });
      setSearchResult(result);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Falha ao consultar BigQuery';
      setSearchError(msg);
    } finally {
      setIsSearching(false);
    }
  };

  const handleExtractToWorkspace = async () => {
    if (!datasetName.trim()) return;
    setIsExtracting(true);
    setSearchError(null);

    try {
      const res = await api.discoveryExtract({
        name: datasetName.trim(),
        limit: extractLimit,
        filter: {
          cnaePrincipal: selectedCnae ? (selectedCnae.codigo || selectedCnae.code) : undefined,
          cnaesSecundarios: selectedSecondaryCnaes.map((c) => c.codigo || c.code),
          uf: selectedUf !== 'Todos os Estados' ? selectedUf : undefined,
          porte: selectedPorte,
          situacaoCadastral: situacaoAtiva ? 'ATIVA' : 'TODAS',
        },
      });

      setExtractSuccess(`${res.totalImported} empresas observadas na fonte foram importadas para o conjunto.`);
      await refreshWorkspace();
      if (onSuccessExtract) {
        setTimeout(() => {
          onSuccessExtract();
          onClose();
        }, 1200);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Falha ao extrair dataset';
      setSearchError(msg);
    } finally {
      setIsExtracting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-950/70 p-4 backdrop-blur-md"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-3xl border border-slate-700/60 bg-slate-900 shadow-2xl text-slate-100"
        onClick={(event) => event.stopPropagation()}
      >
        {/* Cabeçalho */}
        <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950/60 px-6 py-5">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <Database className="h-5 w-5" aria-hidden="true" />
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">
                  Descoberta Canônica Nacional de Empresas
                </h2>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-950/80 px-2.5 py-0.5 text-xs font-semibold text-emerald-400 border border-emerald-500/30">
                  <Sparkles className="h-3 w-3" /> BigQuery + Base dos Dados
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Consulte o conjunto CNPJ da Receita Federal publicado pela Base dos Dados, com estimativa de bytes antes da extração.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Corpo com Scroll */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Seção 1: Filtros de Busca */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
            {/* Campo CNAE Principal com Autocomplete */}
            <div className="md:col-span-12 relative">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                CNAE Principal (Atividade Econômica)
              </label>
              <div className="relative">
                <Search className="absolute left-3.5 top-3.5 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Ex: 6201, Software, Restaurante, Consultoria, Comércio..."
                  value={selectedCnae ? `${selectedCnae.codigo || selectedCnae.code} - ${selectedCnae.descricao || selectedCnae.description}` : cnaeQuery}
                  onChange={(e) => {
                    setSelectedCnae(null);
                    setCnaeQuery(e.target.value);
                  }}
                  className="w-full rounded-xl border border-slate-700 bg-slate-800/80 pl-10 pr-10 py-2.5 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                {selectedCnae && (
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedCnae(null);
                      setCnaeQuery('');
                    }}
                    className="absolute right-3 top-3 text-slate-400 hover:text-white"
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
              </div>

              {/* Lista flutuante de sugestões de CNAE */}
              {cnaeOptions.length > 0 && !selectedCnae && (
                <div className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-xl border border-slate-700 bg-slate-800 shadow-2xl">
                  {cnaeOptions.map((item) => (
                    <button
                      key={item.codigo || item.code}
                      type="button"
                      onClick={() => {
                        setSelectedCnae(item);
                        setCnaeOptions([]);
                      }}
                      className="flex w-full items-start gap-3 px-4 py-2.5 text-left text-xs hover:bg-slate-700/80 transition-colors border-b border-slate-700/40 last:border-0"
                    >
                      <span className="font-mono font-bold text-blue-400 shrink-0">{item.codigo || item.code}</span>
                      <span className="text-slate-200">{item.descricao || item.description}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Estado (UF) */}
            <div className="md:col-span-4">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Estado / UF
              </label>
              <select
                value={selectedUf}
                onChange={(e) => setSelectedUf(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-2.5 text-sm text-white focus:border-blue-500 focus:outline-none"
              >
                {BRAZILIAN_STATES.map((uf) => (
                  <option key={uf} value={uf}>
                    {uf}
                  </option>
                ))}
              </select>
            </div>

            {/* Porte da Empresa */}
            <div className="md:col-span-4">
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Porte da Empresa
              </label>
              <select
                value={selectedPorte}
                onChange={(e) => setSelectedPorte(e.target.value as any)}
                className="w-full rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-2.5 text-sm text-white focus:border-blue-500 focus:outline-none"
              >
                <option value="TODOS">Todos os Portes</option>
                <option value="EPP">EPP (Pequeno Porte)</option>
                <option value="ME">ME (Microempresa)</option>
                <option value="DEMAIS">Médio / Grande Porte</option>
              </select>
            </div>

            {/* Situação Cadastral */}
            <div className="md:col-span-4 flex items-center pt-6">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={situacaoAtiva}
                  onChange={(e) => setSituacaoAtiva(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-xs font-medium text-slate-300">
                  Somente CNPJ Ativo na Receita
                </span>
              </label>
            </div>
          </div>

          {/* Botão de Dry-Run / Calcular Prévia */}
          <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
            <p className="text-xs text-slate-400 flex items-center gap-1.5">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500"></span>
              A disponibilidade da fonte e da credencial será verificada nesta consulta.
            </p>
            <button
              type="button"
              onClick={handleRunSearch}
              disabled={isSearching}
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50 transition-all shadow-lg shadow-blue-600/30"
            >
              {isSearching ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Consultando BigQuery...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4" />
                  Calcular prévia e amostra
                </>
              )}
            </button>
          </div>

          {/* Mensagens de Erro ou Sucesso */}
          {searchError && (
            <div className="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-950/40 p-4 text-xs text-red-300">
              <AlertCircle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
              <span>{searchError}</span>
            </div>
          )}

          {extractSuccess && (
            <div className="flex items-center gap-3 rounded-2xl border border-emerald-500/30 bg-emerald-950/40 p-4 text-xs text-emerald-300">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              <span className="font-semibold">{extractSuccess}</span>
            </div>
          )}

          {/* Seção 2: Resultados do Dry Run & Tabela de Amostra */}
          {searchResult && (
            <div className="space-y-4 pt-2">
              {/* Card de Métricas do Dry Run */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3.5">
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    Volume Processado
                  </p>
                  <p className="mt-1 text-lg font-bold text-white">
                    {searchResult.dryRun.totalMegaBytesProcessed} MB
                  </p>
                  <p className="text-[10px] text-slate-500">
                    {searchResult.dryRun.estimatedCostUsd > 0
                      ? `Estimativa configurada: US$ ${searchResult.dryRun.estimatedCostUsd.toLocaleString('pt-BR')}`
                      : 'Preço por TiB não configurado; confirme o custo no Google Cloud.'}
                  </p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3.5">
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    Filtro Local
                  </p>
                  <p className="mt-1 text-lg font-bold text-blue-400">
                    {selectedUf} • {selectedPorte}
                  </p>
                  <p className="text-[10px] text-slate-500">{situacaoAtiva ? 'Somente situação ativa' : 'Todas as situações cadastrais'}</p>
                </div>
                <div className="rounded-2xl border border-slate-800 bg-slate-950/60 p-3.5">
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                    Empresas elegíveis
                  </p>
                  <p className="mt-1 text-lg font-bold text-emerald-400">
                    {searchResult.totalEligibleCompanies.toLocaleString('pt-BR')}
                  </p>
                  <p className="text-[10px] text-slate-500">Amostra exibida: {searchResult.sample.length}</p>
                </div>
              </div>

              {/* Tabela com Amostra Real */}
              <div className="rounded-2xl border border-slate-800 overflow-hidden bg-slate-950/40">
                <div className="border-b border-slate-800/80 bg-slate-900/80 px-4 py-2.5 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-300">
                     Amostra retornada pela fonte canônica:
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono">
                    {searchResult.sample.length} registros
                  </span>
                </div>
                <div className="divide-y divide-slate-800/50 max-h-56 overflow-y-auto">
                  {searchResult.sample.map((item) => (
                    <div
                      key={item.cnpj}
                      className="px-4 py-3 hover:bg-slate-800/40 transition-colors flex items-center justify-between gap-4"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-xs text-white truncate">
                            {item.razaoSocial}
                          </span>
                          {item.nomeFantasia && (
                            <span className="text-[11px] text-slate-400 truncate">
                              ({item.nomeFantasia})
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 flex items-center gap-3 text-[11px] text-slate-400">
                          <span className="font-mono text-blue-400">{item.cnpjFormatted}</span>
                          <span>•</span>
                          <span className="truncate">{item.cnaePrincipal.descricao}</span>
                          <span>•</span>
                          <span className="flex items-center gap-0.5">
                            <MapPin className="h-3 w-3" /> {item.uf}
                          </span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <span className="inline-block rounded-md bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-300">
                          {item.porte}
                        </span>
                        {item.telefoneComercial && (
                          <p className="text-[10px] text-emerald-400 mt-0.5">
                            Tel: {item.telefoneComercial}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Seção de Extração / Criar Dataset */}
              <div className="rounded-2xl border border-blue-500/30 bg-blue-950/20 p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <FilePlus2 className="h-4 w-4 text-blue-400" />
                  <span className="text-xs font-bold text-white uppercase tracking-wider">
                    Extrair empresas observadas para o workspace
                  </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
                  <div className="sm:col-span-8">
                    <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                      Nome do Dataset no Workspace:
                    </label>
                    <input
                      type="text"
                      value={datasetName}
                      onChange={(e) => setDatasetName(e.target.value)}
                      className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                  <div className="sm:col-span-4">
                    <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                      Limite de Empresas:
                    </label>
                    <input
                      type="number"
                      min={10}
                       max={10000}
                      step={10}
                      value={extractLimit}
                      onChange={(e) => setExtractLimit(Number(e.target.value))}
                      className="w-full rounded-xl border border-slate-700 bg-slate-800 px-3.5 py-2 text-xs text-white focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Rodapé da Modal */}
        <div className="flex items-center justify-between border-t border-slate-800 bg-slate-950/60 px-6 py-4">
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl px-4 py-2 text-xs font-semibold text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            Fechar
          </button>

          {searchResult && (
            <button
              type="button"
              onClick={handleExtractToWorkspace}
              disabled={isExtracting || !datasetName.trim()}
              className="flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-emerald-500 disabled:opacity-50 transition-all shadow-lg shadow-emerald-600/30"
            >
              {isExtracting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                   Importando empresas observadas...
                </>
              ) : (
                <>
                  <Layers className="h-4 w-4" />
                   Extrair até {extractLimit} empresas para o workspace
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
