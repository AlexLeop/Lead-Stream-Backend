import React, { useState, useMemo } from 'react';
import { 
  Search, 
  SlidersHorizontal, 
  Download, 
  Plus, 
  Linkedin, 
  Bell, 
  X, 
  Check, 
  Filter, 
  Sparkles, 
  Phone, 
  Mail, 
  Eye, 
  RefreshCw, 
  Building2, 
  MapPin, 
  Layers, 
  LayoutGrid, 
  Table as TableIcon, 
  CheckCircle2, 
  AlertCircle, 
  ExternalLink, 
  Copy, 
  CheckCheck, 
  Flame, 
  TrendingUp, 
  Bookmark, 
  BookmarkCheck, 
  ChevronRight, 
  ChevronDown, 
  Send, 
  ShieldCheck,
  Zap,
  Globe,
  Upload,
  UserCheck,
  Briefcase,
  CreditCard,
  BadgeCheck,
  Users,
  FolderKanban,
  FolderPlus,
  Tag
} from 'lucide-react';
import type { CreateDatasetInput, ImportResult, Lead } from '../types';
import { useLeadStream } from '../LeadStreamContext';
import LeadDetailsModal from '../components/LeadDetailsModal';
import ExportModal from '../components/ExportModal';
import AddToListModal from '../components/AddToListModal';
import UploadEnrichModal from '../components/UploadEnrichModal';
import CreateLeadSetModal from '../components/CreateLeadSetModal';
import CnaeDiscoveryModal from '../components/CnaeDiscoveryModal';
import EvidenceBadge from '../components/EvidenceBadge';

interface SearchLeadsProps {
  initialSetFilterId?: string | null;
  onClearSetFilter?: () => void;
}

export default function SearchLeads({ initialSetFilterId = null, onClearSetFilter }: SearchLeadsProps) {
  const {
    leads,
    datasets: sets,
    lists,
    revealPhone,
    addLeadsToList,
    createList,
    createDataset,
  } = useLeadStream();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLeadTypeTab, setSelectedLeadTypeTab] = useState<'ALL' | 'PJ' | 'PF'>('ALL');
  const [selectedSetId, setSelectedSetId] = useState<string | null>(initialSetFilterId);
  const [selectedIndustry, setSelectedIndustry] = useState('Todas as Indústrias');
  const [companySizes, setCompanySizes] = useState<string[]>([]);
  const [seniorityLevels, setSeniorityLevels] = useState<string[]>([]);
  const [jobTitles, setJobTitles] = useState<string[]>([]);
  const [newTitleInput, setNewTitleInput] = useState('');
  const [locationInput, setLocationInput] = useState('');
  const [selectedState, setSelectedState] = useState('Todos os Estados');
  const [emailStatusFilter, setEmailStatusFilter] = useState<'all' | 'verified' | 'catchall'>('all');
  const [phoneOnly, setPhoneOnly] = useState(false);
  const [highIntentOnly, setHighIntentOnly] = useState(false);
  const [selectedTech, setSelectedTech] = useState<string[]>([]);
  
  // View mode: table or cards
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table');
  
  // Selection state
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);
  
  // Modals state
  const [activeLead, setActiveLead] = useState<Lead | null>(null);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [isAddToListOpen, setIsAddToListOpen] = useState(false);
  const [isUploadEnrichModalOpen, setIsUploadEnrichModalOpen] = useState(false);
  const [isCreateSetModalOpen, setIsCreateSetModalOpen] = useState(false);
  const [isCnaeDiscoveryOpen, setIsCnaeDiscoveryOpen] = useState(false);

  // Filter application loading
  const [isFiltering, setIsFiltering] = useState(false);
  
  // Toast notifications
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Saved searches preset state
  const [activePreset, setActivePreset] = useState<string>('all');
  const [savedSearchAlertSet, setSavedSearchAlertSet] = useState(false);

  // Sorting
  const [sortBy, setSortBy] = useState<'intent' | 'name' | 'company' | 'size'>('name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // Counts for tabs
  const countPJ = leads.filter(l => l.leadType === 'PJ').length;
  const countPF = leads.filter(l => l.leadType === 'PF').length;
  const hasIntentData = leads.some((lead) => lead.intentScore > 0 && Boolean(lead.intentTopic));

  // Active Set Info if filtered
  const activeFilteredSet = useMemo(() => {
    if (!selectedSetId) return null;
    return sets.find(s => s.id === selectedSetId) || null;
  }, [selectedSetId, sets]);

  // Show toast utility
  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  };

  // Copy to clipboard
  const copyToClipboard = (text: string, label: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(text);
    triggerToast(`${label} copiado com sucesso!`);
  };

  // Reveal Phone
  const handleRevealPhone = async (leadId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    try {
      await revealPhone(leadId);
      triggerToast('Telefone disponibilizado.');
    } catch (cause) {
      triggerToast(cause instanceof Error ? cause.message : 'Não foi possível disponibilizar o telefone.');
    }
  };

  // Reveal All Selected Phones
  const handleRevealSelectedPhones = async () => {
    if (selectedLeadIds.length === 0) return;
    const candidates = leads.filter((lead) => selectedLeadIds.includes(lead.id) && lead.phone);
    const results = await Promise.allSettled(candidates.map((lead) => revealPhone(lead.id)));
    const completed = results.filter((result) => result.status === 'fulfilled').length;
    triggerToast(`${completed} telefone(s) disponibilizado(s).`);
  };

  const handleUploadSuccess = (result: ImportResult) => {
    setSelectedSetId(result.dataset.id);
    setIsUploadEnrichModalOpen(false);
    triggerToast(`${result.contacts} ${result.contacts === 1 ? 'contato' : 'contatos'} e ${result.companies} ${result.companies === 1 ? 'empresa' : 'empresas'} importados para "${result.dataset.name}".`);
  };

  const handleCreateSetDirect = async (input: CreateDatasetInput) => {
    const newSet = await createDataset(input);
    setSelectedSetId(newSet.id);
    triggerToast(`Dataset "${newSet.name}" criado com sucesso.`);
    return newSet;
  };

  // Clear specific Set filter
  const handleClearSetFilter = () => {
    setSelectedSetId(null);
    if (onClearSetFilter) {
      onClearSetFilter();
    }
  };


  // Quick Preset Filters
  const applyPreset = (presetKey: string) => {
    setActivePreset(presetKey);
    handleClearFilters();

    if (presetKey === 'clevel') {
      setSeniorityLevels(['C-Level', 'VP', 'Diretoria']);
    } else if (presetKey === 'pj_only') {
      setSelectedLeadTypeTab('PJ');
    } else if (presetKey === 'pf_only') {
      setSelectedLeadTypeTab('PF');
    } else if (presetKey === 'saas_sp') {
      setSelectedIndustry('SaaS & Software');
      setSelectedState('SP');
    } else if (presetKey === 'whatsapp') {
      setPhoneOnly(true);
    } else if (presetKey === 'high_intent') {
      setHighIntentOnly(true);
    } else if (presetKey === 'enterprise') {
      setCompanySizes(['1000+ funcionários', '201 - 1000 funcionários']);
    }
  };

  // Filter logic
  const filteredLeads = useMemo(() => {
    return leads.filter((lead) => {
      // Tab PF vs PJ filter
      if (selectedLeadTypeTab !== 'ALL' && lead.leadType !== selectedLeadTypeTab) {
        return false;
      }

      // Conjunto / Lead Set filter
      if (selectedSetId && lead.setId !== selectedSetId) {
        // Also check if set leadIds includes this lead
        const currentSet = sets.find(s => s.id === selectedSetId);
        if (!currentSet || !currentSet.leadIds.includes(lead.id)) {
          return false;
        }
      }

      // Search query (name, company, title, tech, cnpj, cpf, profession)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = lead.name.toLowerCase().includes(q);
        const matchesCompany = lead.company.toLowerCase().includes(q);
        const matchesRole = lead.title.toLowerCase().includes(q);
        const matchesTech = lead.technologies?.some(t => t.toLowerCase().includes(q));
        const matchesCity = lead.city?.toLowerCase().includes(q);
        const matchesCnpj = lead.cnpj?.toLowerCase().includes(q);
        const matchesCpf = lead.cpf?.toLowerCase().includes(q);
        const matchesProfissao = lead.profissao?.toLowerCase().includes(q);
        const matchesRazao = lead.razaoSocial?.toLowerCase().includes(q);

        if (!matchesName && !matchesCompany && !matchesRole && !matchesTech && !matchesCity && !matchesCnpj && !matchesCpf && !matchesProfissao && !matchesRazao) {
          return false;
        }
      }

      // Industry
      if (selectedIndustry !== 'Todas as Indústrias' && lead.industry !== selectedIndustry) {
        return false;
      }

      // Company sizes
      if (companySizes.length > 0 && !companySizes.includes(lead.companySize)) {
        return false;
      }

      // Seniority
      if (seniorityLevels.length > 0 && !seniorityLevels.includes(lead.seniority)) {
        return false;
      }

      // Job titles keywords
      if (jobTitles.length > 0) {
        const matchesAnyTitle = jobTitles.some(jt => lead.title.toLowerCase().includes(jt.toLowerCase()));
        if (!matchesAnyTitle) return false;
      }

      // State
      if (selectedState !== 'Todos os Estados' && lead.state !== selectedState) {
        return false;
      }

      // Location Input
      if (locationInput.trim()) {
        const loc = locationInput.toLowerCase();
        if (!lead.location.toLowerCase().includes(loc) && 
            !lead.city.toLowerCase().includes(loc) && 
            !lead.state.toLowerCase().includes(loc)) {
          return false;
        }
      }

      // Email status
      if (emailStatusFilter === 'verified' && lead.status !== 'Verificado') return false;
      if (emailStatusFilter === 'catchall' && lead.status !== 'Catch-all') return false;

      // Phone only
      if (phoneOnly && !lead.phone) return false;

      // High intent only (> 85%)
      if (highIntentOnly && lead.intentScore < 85) return false;

      // Tech Stack
      if (selectedTech.length > 0) {
        const hasTech = selectedTech.some(t => lead.technologies?.includes(t));
        if (!hasTech) return false;
      }

      return true;
    }).sort((a, b) => {
      if (sortBy === 'intent') {
        return sortOrder === 'desc' ? b.intentScore - a.intentScore : a.intentScore - b.intentScore;
      }
      if (sortBy === 'name') {
        return sortOrder === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
      }
      if (sortBy === 'company') {
        return sortOrder === 'asc' ? a.company.localeCompare(b.company) : b.company.localeCompare(a.company);
      }
      if (sortBy === 'size') {
        return sortOrder === 'desc' ? b.employeeCount - a.employeeCount : a.employeeCount - b.employeeCount;
      }
      return 0;
    });
  }, [
    leads, 
    selectedLeadTypeTab,
    selectedSetId,
    sets,
    searchQuery, 
    selectedIndustry, 
    companySizes, 
    seniorityLevels, 
    jobTitles, 
    selectedState, 
    locationInput, 
    emailStatusFilter, 
    phoneOnly, 
    highIntentOnly, 
    selectedTech,
    sortBy,
    sortOrder
  ]);

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedLeadIds(filteredLeads.map(l => l.id));
    } else {
      setSelectedLeadIds([]);
    }
  };

  const toggleSelectLead = (id: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (selectedLeadIds.includes(id)) {
      setSelectedLeadIds(selectedLeadIds.filter(i => i !== id));
    } else {
      setSelectedLeadIds([...selectedLeadIds, id]);
    }
  };

  const handleAddJobTitle = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && newTitleInput.trim()) {
      e.preventDefault();
      if (!jobTitles.includes(newTitleInput.trim())) {
        setJobTitles([...jobTitles, newTitleInput.trim()]);
      }
      setNewTitleInput('');
    }
  };

  const removeJobTitle = (title: string) => {
    setJobTitles(jobTitles.filter(t => t !== title));
  };

  const toggleCompanySize = (size: string) => {
    if (companySizes.includes(size)) {
      setCompanySizes(companySizes.filter(s => s !== size));
    } else {
      setCompanySizes([...companySizes, size]);
    }
  };

  const toggleSeniority = (level: string) => {
    if (seniorityLevels.includes(level)) {
      setSeniorityLevels(seniorityLevels.filter(s => s !== level));
    } else {
      setSeniorityLevels([...seniorityLevels, level]);
    }
  };

  const toggleTech = (tech: string) => {
    if (selectedTech.includes(tech)) {
      setSelectedTech(selectedTech.filter(t => t !== tech));
    } else {
      setSelectedTech([...selectedTech, tech]);
    }
  };

  const handleClearFilters = () => {
    setSelectedIndustry('Todas as Indústrias');
    setCompanySizes([]);
    setSeniorityLevels([]);
    setJobTitles([]);
    setSelectedState('Todos os Estados');
    setLocationInput('');
    setEmailStatusFilter('all');
    setPhoneOnly(false);
    setHighIntentOnly(false);
    setSelectedTech([]);
    setSearchQuery('');
  };

  const handleAddToList = async (listId: string, leadIds?: string[]) => {
    const idsToAdd = leadIds || selectedLeadIds;
    try {
      const targetList = await addLeadsToList(listId, idsToAdd);
      triggerToast(`${idsToAdd.length} contato(s) adicionado(s) à lista "${targetList.name}".`);
      setSelectedLeadIds([]);
    } catch (cause) {
      triggerToast(cause instanceof Error ? cause.message : 'Não foi possível atualizar a lista.');
    }
  };

  const handleCreateNewList = async (name: string, description: string) => {
    try {
      const newList = await createList({ name, description, leadIds: selectedLeadIds });
      triggerToast(`Lista "${newList.name}" criada com ${selectedLeadIds.length} contato(s).`);
      setSelectedLeadIds([]);
    } catch (cause) {
      triggerToast(cause instanceof Error ? cause.message : 'Não foi possível criar a lista.');
    }
  };

  const availableTechs = Array.from(new Set<string>(leads.flatMap((lead) => lead.technologies))).sort();

  return (
    <div className="h-full flex flex-col pb-6 max-w-[1440px] mx-auto relative">
      {/* Global Floating Toast */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-2xl border border-slate-800 flex items-center gap-2.5 text-xs font-semibold animate-in fade-in slide-in-from-bottom-3 duration-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Modals */}
      <LeadDetailsModal 
        lead={activeLead} 
        onClose={() => setActiveLead(null)}
        onAddToList={(lead) => {
          setSelectedLeadIds([lead.id]);
          setIsAddToListOpen(true);
        }}
      />

      <ExportModal 
        isOpen={isExportModalOpen}
        onClose={() => setIsExportModalOpen(false)}
        leads={filteredLeads}
        selectedIds={selectedLeadIds}
      />

      <AddToListModal
        isOpen={isAddToListOpen}
        onClose={() => setIsAddToListOpen(false)}
        lists={lists}
        leadsToAdd={leads.filter(l => selectedLeadIds.includes(l.id))}
        onAdd={handleAddToList}
        onCreateNewList={handleCreateNewList}
      />

      <UploadEnrichModal
        isOpen={isUploadEnrichModalOpen}
        onClose={() => setIsUploadEnrichModalOpen(false)}
        onSuccess={handleUploadSuccess}
        existingSets={sets}
      />

      <CreateLeadSetModal
        isOpen={isCreateSetModalOpen}
        onClose={() => setIsCreateSetModalOpen(false)}
        onCreateSet={handleCreateSetDirect}
      />

      <CnaeDiscoveryModal
        isOpen={isCnaeDiscoveryOpen}
        onClose={() => setIsCnaeDiscoveryOpen(false)}
        onImport={() => {
          setIsCnaeDiscoveryOpen(false);
          setIsUploadEnrichModalOpen(true);
        }}
      />

      {/* Active Set Banner if filtered */}
      {activeFilteredSet && (
        <div className="bg-slate-900 text-white p-4 rounded-[12px] mb-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in duration-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600/60 border border-blue-400/30 flex items-center justify-center text-white shrink-0 font-bold">
              <FolderKanban className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold text-blue-300">
                  Filtro de base ativo
                </span>
                <span className="px-2 py-0.2 rounded-full text-[10px] font-bold bg-blue-500/30 text-blue-200 border border-blue-400/30">
                  {activeFilteredSet.category}
                </span>
              </div>
              <h2 className="text-sm sm:text-base font-extrabold text-white tracking-tight">
                {activeFilteredSet.name}
              </h2>
            </div>
          </div>

          <div className="flex items-center gap-2 self-end sm:self-center">
            <button
              onClick={() => setIsUploadEnrichModalOpen(true)}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-lg transition-colors flex items-center gap-1.5 cursor-pointer shadow-xs"
            >
              <Upload className="w-3.5 h-3.5" /> + Adicionar Leads
            </button>
            <button
              onClick={handleClearSetFilter}
              className="px-3 py-1.5 bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white text-xs font-bold rounded-lg transition-colors border border-slate-700 cursor-pointer"
            >
              Ver Todos os Leads
            </button>
          </div>
        </div>
      )}

      {/* Header with Search, Upload Button and Presets */}
      <div className="bg-white p-5 rounded-[12px] border border-slate-200 mb-5 space-y-4">
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
          <div>
            <div className="flex items-center gap-2.5 flex-wrap">
              <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
                Contatos e empresas
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-700 border border-blue-100">
                {leads.length} {leads.length === 1 ? 'contato disponível' : 'contatos disponíveis'}
              </span>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 flex items-center gap-1">
                <Building2 className="w-3 h-3" /> {countPJ} PJ
              </span>
              <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                <UserCheck className="w-3 h-3" /> {countPF} PF
              </span>
            </div>
            <p className="text-slate-500 text-xs mt-1 font-medium">
              Encontre empresas e decisores por nome, CNPJ, cargo, setor, tecnologia ou localização.
            </p>
          </div>

          <div className="flex items-center gap-3 w-full lg:w-auto flex-wrap">
            {/* Create Set Action */}
            <button
              onClick={() => setIsCreateSetModalOpen(true)}
              className="px-3.5 py-2 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 rounded-xl font-bold text-xs shadow-2xs transition-all flex items-center gap-1.5 cursor-pointer"
            >
              <FolderPlus className="w-3.5 h-3.5 text-blue-600" />
              <span>+ Novo Conjunto</span>
            </button>

            {/* Pesquisa nacional: estado informativo até a fonte canônica ser conectada */}
            <button
              onClick={() => setIsCnaeDiscoveryOpen(true)}
              className="px-3.5 py-2 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-700 rounded-[10px] font-bold text-xs transition-colors flex items-center gap-2 cursor-pointer"
            >
              <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              <span>Pesquisa nacional</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">Em preparação</span>
            </button>

            {/* Upload action */}
            <button
              onClick={() => setIsUploadEnrichModalOpen(true)}
              className="px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-[10px] font-bold text-xs transition-colors flex items-center gap-2 cursor-pointer"
            >
              <Upload className="w-3.5 h-3.5" />
              <span>Importar arquivo CSV</span>
            </button>

            {/* View mode toggle */}
            <div className="bg-slate-100 p-1 rounded-xl flex items-center gap-1 text-xs font-bold text-slate-600">
              <button
                onClick={() => setViewMode('table')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                  viewMode === 'table' ? 'bg-white text-blue-600 shadow-2xs' : 'hover:text-slate-900'
                }`}
                title="Visualização em Tabela"
              >
                <TableIcon className="w-3.5 h-3.5" /> Tabela
              </button>
              <button
                onClick={() => setViewMode('cards')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                  viewMode === 'cards' ? 'bg-white text-blue-600 shadow-2xs' : 'hover:text-slate-900'
                }`}
                title="Visualização em Cards"
              >
                <LayoutGrid className="w-3.5 h-3.5" /> Cards
              </button>
            </div>
          </div>
        </div>

        {/* Global Search Bar and Set Selector */}
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
              <Search className="h-4 w-4 text-slate-400" />
            </div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="block w-full pl-10 pr-28 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all font-medium"
              placeholder="Buscar por nome, CNPJ, CPF, empresa, cargo, tecnologia (ex: HubSpot, AWS) ou cidade..."
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery('')}
                className="absolute inset-y-0 right-10 pr-2 flex items-center text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            <span className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none text-[11px] font-semibold text-slate-400">
              {filteredLeads.length} de {leads.length}
            </span>
          </div>

          {/* Quick Conjunto Selector */}
          <div className="w-full sm:w-auto shrink-0 flex items-center gap-2">
            <div className="relative">
              <select
                value={selectedSetId || ''}
                onChange={(e) => setSelectedSetId(e.target.value || null)}
                className="px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer shadow-2xs"
              >
                <option value="">Todos os Conjuntos de Leads</option>
                {sets.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.category})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Quick Presets Bar */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 text-xs">
          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider shrink-0 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-blue-600" /> Segmentos Rápidos:
          </span>
          <button
            onClick={() => { setSelectedLeadTypeTab('ALL'); applyPreset('all'); }}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
              activePreset === 'all' && selectedLeadTypeTab === 'ALL' ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            Todos os Leads
          </button>
          <button
            onClick={() => { setSelectedLeadTypeTab('PJ'); applyPreset('pj_only'); }}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 ${
              selectedLeadTypeTab === 'PJ' ? 'bg-indigo-600 text-white' : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
            }`}
          >
            <Building2 className="w-3 h-3" /> Somente PJ ({countPJ})
          </button>
          <button
            onClick={() => { setSelectedLeadTypeTab('PF'); applyPreset('pf_only'); }}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1.5 ${
              selectedLeadTypeTab === 'PF' ? 'bg-emerald-600 text-white' : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
            }`}
          >
            <UserCheck className="w-3 h-3" /> Somente PF ({countPF})
          </button>
          <button
            onClick={() => applyPreset('clevel')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
              activePreset === 'clevel' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            C-Levels & Diretores
          </button>
          {hasIntentData && (
            <button
              onClick={() => applyPreset('high_intent')}
              className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1 ${
                activePreset === 'high_intent' ? 'bg-amber-500 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              <Flame className="w-3 h-3" /> Intenção Alta (&gt; 85%)
            </button>
          )}
          <button
            onClick={() => applyPreset('whatsapp')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer flex items-center gap-1 ${
              activePreset === 'whatsapp' ? 'bg-emerald-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <Phone className="w-3 h-3" /> Com telefone informado
          </button>
          <button
            onClick={() => applyPreset('saas_sp')}
            className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-colors cursor-pointer ${
              activePreset === 'saas_sp' ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            SaaS em SP
          </button>
        </div>
      </div>

      {/* Main Content Layout: Sidebar Filters + Results Panel */}
      <div className="flex-1 flex flex-col lg:flex-row gap-5 items-start">
        {/* Left Sidebar: Advanced Multi-facet Filters */}
        <div className="w-full lg:w-72 flex-shrink-0 bg-white border border-slate-200/90 rounded-2xl shadow-xs flex flex-col overflow-hidden">
          <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
            <div className="font-bold text-slate-900 text-xs sm:text-sm flex items-center gap-2">
              <SlidersHorizontal className="w-4 h-4 text-blue-600" /> Filtros Avançados
            </div>
            <button 
              onClick={handleClearFilters}
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors cursor-pointer"
            >
              Limpar Tudo
            </button>
          </div>
          
          <div className="p-4 space-y-5 max-h-[calc(100vh-16rem)] overflow-y-auto">
            {/* Filter: Lead Type PF vs PJ */}
            <div>
              <label className="block text-[11px] font-bold text-slate-500 tracking-wider mb-2 uppercase">
                Natureza do Lead (PF vs PJ)
              </label>
              <div className="grid grid-cols-3 gap-1 p-1 bg-slate-100 rounded-xl text-xs font-bold">
                <button
                  type="button"
                  onClick={() => setSelectedLeadTypeTab('ALL')}
                  className={`py-1.5 rounded-lg transition-all cursor-pointer ${
                    selectedLeadTypeTab === 'ALL' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Todos
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedLeadTypeTab('PJ')}
                  className={`py-1.5 rounded-lg transition-all cursor-pointer flex items-center justify-center gap-1 ${
                    selectedLeadTypeTab === 'PJ' ? 'bg-indigo-600 text-white shadow-2xs' : 'text-slate-600 hover:text-indigo-700'
                  }`}
                >
                  <Building2 className="w-3 h-3" /> PJ
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedLeadTypeTab('PF')}
                  className={`py-1.5 rounded-lg transition-all cursor-pointer flex items-center justify-center gap-1 ${
                    selectedLeadTypeTab === 'PF' ? 'bg-emerald-600 text-white shadow-2xs' : 'text-slate-600 hover:text-emerald-700'
                  }`}
                >
                  <UserCheck className="w-3 h-3" /> PF
                </button>
              </div>
            </div>

            {/* Industry / Sector */}
            <div>
              <label className="block text-[11px] font-bold text-slate-500 tracking-wider mb-2 uppercase">
                Indústria / Setor Econômico
              </label>
              <select 
                value={selectedIndustry}
                onChange={(e) => setSelectedIndustry(e.target.value)}
                className="w-full border-slate-200 border rounded-xl py-2 px-3 text-xs font-semibold text-slate-700 bg-white focus:ring-2 focus:ring-blue-500 focus:outline-none shadow-2xs"
              >
                <option>Todas as Indústrias</option>
                <option>SaaS & Software</option>
                <option>Fintech & Bancos</option>
                <option>Logística & Supply Chain</option>
                <option>Saúde & MedTech</option>
                <option>Serviços Jurídicos</option>
                <option>E-commerce & Varejo</option>
                <option>Telecom & Conectividade</option>
                <option>Indústria & Manufatura</option>
                <option>Agronegócio & Biotech</option>
              </select>
            </div>

            {/* Seniority Levels */}
            <div>
              <label className="block text-[11px] font-bold text-slate-500 tracking-wider mb-2 uppercase">
                Nível de Decisão / Hierarquia
              </label>
              <div className="space-y-1.5">
                {[
                  { level: 'C-Level', desc: 'CEO, CTO, CMO, CRO, CFO' },
                  { level: 'VP', desc: 'Vice-Presidentes' },
                  { level: 'Diretoria', desc: 'Diretores Executivos' },
                  { level: 'Gerência', desc: 'Heads & Gerentes' },
                  { level: 'Profissional Liberal', desc: 'Médicos, Advogados, Sócios (PF)' },
                  { level: 'Autônomo / Consultor', desc: 'DPOs, Especialistas, Consultores (PF)' }
                ].map((item, i) => (
                  <label key={i} className="flex items-start gap-2.5 cursor-pointer text-xs text-slate-700 hover:text-slate-900 select-none py-0.5">
                    <input 
                      type="checkbox" 
                      checked={seniorityLevels.includes(item.level)}
                      onChange={() => toggleSeniority(item.level)}
                      className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 mt-0.5 cursor-pointer" 
                    />
                    <div>
                      <span className="font-bold text-slate-900 block leading-tight">{item.level}</span>
                      <span className="text-[10px] text-slate-400">{item.desc}</span>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Company Size */}
            <div>
              <label className="block text-[11px] font-bold text-slate-500 tracking-wider mb-2 uppercase">
                Porte da Organização / Estrutura
              </label>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  '1 - 50 funcionários',
                  '51 - 200 funcionários',
                  '201 - 1000 funcionários',
                  '1000+ funcionários'
                ].map((size, i) => {
                  const isChecked = companySizes.includes(size);
                  return (
                    <button
                      key={i}
                      type="button"
                      onClick={() => toggleCompanySize(size)}
                      className={`text-[11px] p-2 rounded-xl border text-left font-semibold transition-all cursor-pointer ${
                        isChecked 
                          ? 'border-blue-600 bg-blue-50/70 text-blue-800 shadow-2xs font-bold' 
                          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                      }`}
                    >
                      {size.replace(' funcionários', '')}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Email deliverability */}
            <div>
              <label className="block text-[11px] font-bold text-slate-500 tracking-wider mb-2 uppercase">
                Status do e-mail
              </label>
              <div className="grid grid-cols-3 gap-1 p-1 bg-slate-100 rounded-xl text-xs font-bold">
                <button
                  type="button"
                  onClick={() => setEmailStatusFilter('all')}
                  className={`py-1.5 rounded-lg transition-colors cursor-pointer ${
                    emailStatusFilter === 'all' ? 'bg-white text-slate-900 shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Todos
                </button>
                <button
                  type="button"
                  onClick={() => setEmailStatusFilter('verified')}
                  className={`py-1.5 rounded-lg transition-colors cursor-pointer ${
                    emailStatusFilter === 'verified' ? 'bg-emerald-600 text-white shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Caixa validada
                </button>
                <button
                  type="button"
                  onClick={() => setEmailStatusFilter('catchall')}
                  className={`py-1.5 rounded-lg transition-colors cursor-pointer ${
                    emailStatusFilter === 'catchall' ? 'bg-slate-700 text-white shadow-2xs' : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Catch-all
                </button>
              </div>
            </div>

            {/* Direct Contact Toggle */}
            <div className="space-y-2 pt-2 border-t border-slate-100">
              <label className="flex items-center justify-between cursor-pointer text-xs font-bold text-slate-700">
                <span className="flex items-center gap-1.5">
                  <Phone className="w-3.5 h-3.5 text-indigo-600" /> Apenas com telefone informado
                </span>
                <input
                  type="checkbox"
                  checked={phoneOnly}
                  onChange={(e) => setPhoneOnly(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
                />
              </label>

              {hasIntentData && (
                <label className="flex items-center justify-between cursor-pointer text-xs font-bold text-slate-700">
                  <span className="flex items-center gap-1.5">
                    <Flame className="w-3.5 h-3.5 text-amber-500" /> Intenção Alta (&gt; 85%)
                  </span>
                  <input
                    type="checkbox"
                    checked={highIntentOnly}
                    onChange={(e) => setHighIntentOnly(e.target.checked)}
                    className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer"
                  />
                </label>
              )}
            </div>

            {/* Installed Tech Stack */}
            <div className="pt-2 border-t border-slate-100">
              <label className="block text-[11px] font-bold text-slate-500 tracking-wider mb-2 uppercase">
                Tecnologias Instaladas
              </label>
              <div className="flex flex-wrap gap-1.5">
                {availableTechs.map((tech, i) => {
                  const isSelected = selectedTech.includes(tech);
                  return (
                    <button
                      key={i}
                      type="button"
                      onClick={() => toggleTech(tech)}
                      className={`text-[11px] px-2.5 py-1 rounded-lg font-semibold border transition-all cursor-pointer ${
                        isSelected
                          ? 'bg-blue-600 text-white border-blue-600'
                          : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
                      }`}
                    >
                      {tech}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="p-4 border-t border-slate-100 bg-slate-50/50">
            <button 
              onClick={() => {
                setIsFiltering(true);
                setTimeout(() => setIsFiltering(false), 300);
                triggerToast('Filtros atualizados!');
              }}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs py-2.5 rounded-xl transition-colors flex items-center justify-center gap-2 shadow-xs cursor-pointer"
            >
              {isFiltering ? (
                <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Atualizando...</>
              ) : (
                <><RefreshCw className="w-3.5 h-3.5" /> Aplicar Filtros ({filteredLeads.length} leads)</>
              )}
            </button>
          </div>
        </div>

        {/* Right Area: Results & Actions */}
        <div className="flex-1 w-full bg-white border border-slate-200/90 rounded-2xl shadow-xs flex flex-col overflow-hidden min-h-[600px]">
          {/* Action Bar Header */}
          <div className="p-4 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3 bg-slate-50/60">
            {/* Left: Tab selectors for PF vs PJ + Select All */}
            <div className="flex items-center gap-3 text-xs text-slate-600 flex-wrap">
              {/* Type Switcher Tabs */}
              <div className="flex items-center bg-slate-200/80 p-0.5 rounded-xl text-xs font-bold">
                <button
                  onClick={() => setSelectedLeadTypeTab('ALL')}
                  className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer ${
                    selectedLeadTypeTab === 'ALL'
                      ? 'bg-white text-slate-900 shadow-2xs font-extrabold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Todos ({leads.length})
                </button>
                <button
                  onClick={() => setSelectedLeadTypeTab('PJ')}
                  className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                    selectedLeadTypeTab === 'PJ'
                      ? 'bg-indigo-600 text-white shadow-2xs font-extrabold'
                      : 'text-slate-600 hover:text-indigo-700'
                  }`}
                >
                  <Building2 className="w-3.5 h-3.5" /> Pessoa Jurídica ({countPJ})
                </button>
                <button
                  onClick={() => setSelectedLeadTypeTab('PF')}
                  className={`px-3 py-1.5 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
                    selectedLeadTypeTab === 'PF'
                      ? 'bg-emerald-600 text-white shadow-2xs font-extrabold'
                      : 'text-slate-600 hover:text-emerald-700'
                  }`}
                >
                  <UserCheck className="w-3.5 h-3.5" /> Pessoa Física ({countPF})
                </button>
              </div>

              <div className="h-4 w-px bg-slate-300 hidden sm:block"></div>

              <label className="flex items-center gap-2 cursor-pointer font-bold text-slate-800 select-none">
                <input 
                  type="checkbox" 
                  onChange={handleSelectAll}
                  checked={selectedLeadIds.length > 0 && selectedLeadIds.length === filteredLeads.length}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer" 
                /> 
                <span>
                  {selectedLeadIds.length > 0 
                    ? `${selectedLeadIds.length} selecionado(s)` 
                    : `Selecionar Todos`
                  }
                </span>
              </label>

              {/* Sorting */}
              <div className="flex items-center gap-1.5 font-medium text-slate-500">
                <span>Ordenar:</span>
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as any)}
                  className="bg-transparent text-slate-900 font-bold text-xs focus:outline-none cursor-pointer"
                >
                  {hasIntentData && <option value="intent">Intenção de compra</option>}
                  <option value="name">Nome do Lead</option>
                  <option value="company">Empresa / Clínica</option>
                  <option value="size">Porte / Estrutura</option>
                </select>
              </div>
            </div>

            {/* Right: Bulk Actions & Import Button */}
            <div className="flex items-center gap-2 flex-wrap">
              {selectedLeadIds.length > 0 && (
                <button
                  onClick={handleRevealSelectedPhones}
                  className="px-3 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl font-bold text-xs flex items-center gap-1.5 transition-all shadow-2xs cursor-pointer animate-in fade-in duration-200"
                >
                  <Phone className="w-3.5 h-3.5" /> Revelar Telefones ({selectedLeadIds.length})
                </button>
              )}

              <button 
                onClick={() => setIsExportModalOpen(true)}
                className="px-3.5 py-1.5 bg-white border border-slate-200 hover:border-slate-300 text-slate-700 rounded-xl font-semibold text-xs flex items-center gap-1.5 hover:bg-slate-50 transition-all shadow-2xs cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" /> Exportar ({selectedLeadIds.length || filteredLeads.length})
              </button>

              <button 
                onClick={() => {
                  if (selectedLeadIds.length === 0 && filteredLeads.length > 0) {
                    setSelectedLeadIds([filteredLeads[0].id]);
                  }
                  setIsAddToListOpen(true);
                }}
                className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold text-xs flex items-center gap-1.5 transition-all shadow-xs cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" /> Adicionar à Lista
              </button>
            </div>
          </div>

          {/* TABLE VIEW */}
          {viewMode === 'table' && (
            <div className="flex-1 overflow-x-auto">
              <table className="w-full text-xs text-left border-collapse">
                <thead className="text-[11px] text-slate-500 uppercase bg-slate-50/80 border-b border-slate-200 sticky top-0 z-10 font-bold tracking-wider">
                  <tr>
                    <th className="px-3.5 py-3 w-10 text-center"></th>
                    <th className="px-3 py-3 w-28">Tipo</th>
                    <th className="px-4 py-3">Decisor / Profissional</th>
                    <th className="px-4 py-3">Empresa / cadastro informado</th>
                    <th className="px-4 py-3">Canais registrados</th>
                    <th className="px-4 py-3">Inteligência & Intenção</th>
                    <th className="px-4 py-3 text-right">Ações</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredLeads.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center py-16 text-slate-500">
                        <div className="max-w-xs mx-auto space-y-3">
                          <AlertCircle className="w-8 h-8 text-slate-400 mx-auto" />
                          <p className="text-sm font-bold text-slate-800">Nenhum lead encontrado com esses filtros.</p>
                          <button
                            onClick={handleClearFilters}
                            className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-bold hover:bg-blue-700"
                          >
                            Limpar Filtros
                          </button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    filteredLeads.map((lead) => {
                      const isSelected = selectedLeadIds.includes(lead.id);
                      const isPJ = lead.leadType === 'PJ';
                      const isPF = lead.leadType === 'PF';

                      return (
                        <tr 
                          key={lead.id} 
                          className={`hover:bg-blue-50/20 transition-colors group cursor-pointer ${
                            isSelected ? 'bg-blue-50/40' : ''
                          }`}
                          onClick={() => setActiveLead(lead)}
                        >
                          {/* Selection Checkbox */}
                          <td className="px-3.5 py-3.5 text-center" onClick={(e) => e.stopPropagation()}>
                            <input 
                              type="checkbox" 
                              checked={isSelected}
                              onChange={(e) => toggleSelectLead(lead.id, e as any)}
                              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer" 
                            />
                          </td>

                          {/* Lead Type Badge (PJ vs PF) */}
                          <td className="px-3 py-3.5">
                            {isPJ ? (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-extrabold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                <Building2 className="w-3.5 h-3.5 text-indigo-600" /> PJ
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                <UserCheck className="w-3.5 h-3.5 text-emerald-600" /> PF
                              </span>
                            )}
                          </td>

                          {/* Lead Profile Info */}
                          <td className="px-4 py-3.5">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-700 font-bold overflow-hidden shrink-0 shadow-2xs group-hover:scale-105 transition-transform">
                                {lead.avatar ? (
                                  <img src={lead.avatar} alt={lead.name} className="w-full h-full object-cover" />
                                ) : (
                                  lead.initials
                                )}
                              </div>
                              <div>
                                <div className="font-bold text-slate-900 flex items-center gap-1.5 text-xs sm:text-sm">
                                  {lead.name}
                                  {lead.linkedinUrl && (
                                    <a 
                                      href={lead.linkedinUrl} 
                                      target="_blank" 
                                      rel="noreferrer"
                                      onClick={(e) => e.stopPropagation()}
                                      className="text-[#0A66C2] hover:opacity-80 inline-flex"
                                      title="Ver no LinkedIn"
                                    >
                                      <Linkedin className="w-3.5 h-3.5 fill-current" />
                                    </a>
                                  )}
                                </div>
                                <div className="text-slate-500 font-medium text-xs flex items-center gap-1.5 mt-0.5 flex-wrap">
                                  <span>{lead.title}</span>
                                  <span className="px-1.5 py-0.2 bg-slate-100 text-slate-600 rounded text-[10px] font-bold">
                                    {lead.seniority}
                                  </span>
                                </div>
                              </div>
                            </div>
                          </td>

                          {/* Company / Registration Info */}
                          <td className="px-4 py-3.5">
                            <div className="font-bold text-slate-900 flex items-center gap-1.5">
                              {isPJ ? <Building2 className="w-3.5 h-3.5 text-indigo-500" /> : <Briefcase className="w-3.5 h-3.5 text-emerald-500" />}
                              {lead.company}
                            </div>
                            
                            {/* Detailed Registration Data according to Type */}
                            {isPJ ? (
                              <div className="text-slate-500 text-[11px] mt-0.5 flex items-center gap-1.5 flex-wrap">
                                <span className="font-mono text-slate-700 font-semibold">{lead.cnpj || 'CNPJ não informado'}</span>
                                {lead.companySize && <><span>•</span><span className="text-blue-600 font-semibold">{lead.companySize}</span></>}
                                {lead.location && <><span>•</span><span className="text-slate-500">{lead.location}</span></>}
                              </div>
                            ) : (
                              <div className="text-slate-500 text-[11px] mt-0.5 flex items-center gap-1.5 flex-wrap">
                                <span className="font-mono text-slate-700 font-semibold">CPF: {lead.cpf || 'não informado'}</span>
                                <span>•</span>
                                <span className="text-emerald-700 font-semibold">{lead.profissao?.split('(')[0] || 'Profissão não informada'}</span>
                                <span>•</span>
                                <span className="text-slate-500">{lead.location}</span>
                              </div>
                            )}
                          </td>

                          {/* Direct Contacts (Email + Phone/WhatsApp) */}
                          <td className="px-4 py-3.5" onClick={(e) => e.stopPropagation()}>
                            <div className="space-y-1.5">
                              {/* Email */}
                              <div className="flex items-center gap-1.5">
                                <EvidenceBadge status={lead.emailEvidenceStatus} compact />
                                <span className="font-medium text-slate-800 text-xs truncate max-w-[150px]">
                                  {lead.email || 'E-mail não informado'}
                                </span>
                                {lead.email && (
                                  <button
                                    onClick={(e) => copyToClipboard(lead.email, 'E-mail', e)}
                                    className="text-slate-400 hover:text-blue-600 p-1"
                                    title="Copiar e-mail"
                                    aria-label="Copiar e-mail"
                                  >
                                    <Copy className="w-3 h-3" />
                                  </button>
                                )}
                              </div>

                              {/* Phone / WhatsApp */}
                              <div className="space-y-1.5">
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <EvidenceBadge status={lead.phoneEvidenceStatus} compact />
                                  <EvidenceBadge status={lead.whatsappEvidenceStatus} compact />
                                </div>
                                {!lead.phone ? (
                                  <span className="text-[11px] text-slate-500">Telefone não informado</span>
                                ) : lead.phoneRevealed ? (
                                  <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                                    <span className="font-semibold text-slate-800">{lead.phone}</span>
                                    <button
                                      onClick={(e) => copyToClipboard(lead.phone, 'Telefone', e)}
                                      className="text-slate-400 hover:text-blue-600 p-1"
                                      title="Copiar telefone"
                                      aria-label="Copiar telefone"
                                    >
                                      <Copy className="w-3 h-3" />
                                    </button>
                                    {lead.whatsappEvidenceStatus !== 'ABSENT' && lead.whatsappEvidenceStatus !== 'REJECTED' && (
                                      <a
                                        href={`https://wa.me/${lead.phone.replace(/[^0-9]/g, '')}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="font-semibold text-blue-700 hover:underline"
                                      >
                                        Tentar no WhatsApp — não confirmado
                                      </a>
                                    )}
                                  </div>
                                ) : (
                                  <button
                                    onClick={(e) => handleRevealPhone(lead.id, e)}
                                    className="inline-flex items-center gap-1 text-[11px] font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 px-2 py-0.5 rounded border border-indigo-200 transition-colors cursor-pointer"
                                  >
                                    <Eye className="w-3 h-3" /> Exibir telefone
                                  </button>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Intelligence & Intent */}
                          <td className="px-4 py-3.5">
                            <div className="space-y-1.5">
                              {/* Intent Score Badge */}
                              {lead.intentScore > 0 && lead.intentTopic ? (
                                <div className="flex items-center gap-1.5">
                                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-extrabold flex items-center gap-1 ${
                                    lead.intentScore >= 90
                                      ? 'bg-amber-100 text-amber-900 border border-amber-200'
                                      : lead.intentScore >= 80
                                      ? 'bg-blue-50 text-blue-800 border border-blue-200'
                                      : 'bg-slate-100 text-slate-700'
                                  }`}>
                                    <Flame className="w-3 h-3 text-amber-500" />
                                    {lead.intentScore}% de intenção
                                  </span>
                                  <span className="text-[11px] text-slate-500 truncate max-w-[140px]" title={lead.intentTopic}>
                                    {lead.intentTopic}
                                  </span>
                                </div>
                              ) : (
                                <span className="text-[11px] text-slate-500">Intenção não disponível</span>
                              )}

                              {/* Tech Stack Pills or Income Bracket */}
                              {isPJ ? (
                                <div className="flex items-center gap-1 flex-wrap">
                                  {lead.technologies?.slice(0, 3).map((tech, i) => (
                                    <span key={i} className="text-[10px] px-1.5 py-0.5 bg-slate-100 border border-slate-200 rounded text-slate-600 font-medium">
                                      {tech}
                                    </span>
                                  ))}
                                  {lead.technologies && lead.technologies.length > 3 && (
                                    <span className="text-[10px] text-slate-400 font-bold">
                                      +{lead.technologies.length - 3}
                                    </span>
                                  )}
                                </div>
                              ) : (
                                <div className="flex items-center gap-1.5 text-[10px] text-slate-600 font-semibold">
                                  <span className="bg-emerald-50 text-emerald-800 px-1.5 py-0.5 rounded border border-emerald-200">
                                    {lead.scoreCredito ? `Score: ${lead.scoreCredito}` : 'Score não informado'}
                                  </span>
                                  {lead.faixaRenda && (
                                    <span className="text-slate-500 truncate max-w-[120px]">
                                      {lead.faixaRenda}
                                    </span>
                                  )}
                                </div>
                              )}
                            </div>
                          </td>

                          {/* Actions */}
                          <td className="px-4 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                            <div className="flex items-center justify-end gap-1">
                              <button
                                onClick={() => setActiveLead(lead)}
                                className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors cursor-pointer"
                                title="Ver Perfil Completo"
                              >
                                <Eye className="w-4 h-4" />
                              </button>
                              <button
                                onClick={() => {
                                  setSelectedLeadIds([lead.id]);
                                  setIsAddToListOpen(true);
                                }}
                                className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors cursor-pointer"
                                title="Adicionar à Lista"
                              >
                                <Plus className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* CARDS VIEW */}
          {viewMode === 'cards' && (
            <div className="flex-1 p-5 overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {filteredLeads.map((lead) => {
                  const isSelected = selectedLeadIds.includes(lead.id);
                  const isPJ = lead.leadType === 'PJ';

                  return (
                    <div
                      key={lead.id}
                      onClick={() => setActiveLead(lead)}
                      className={`p-4 rounded-2xl border transition-all cursor-pointer flex flex-col justify-between ${
                        isSelected 
                          ? 'border-blue-500 bg-blue-50/20 shadow-xs' 
                          : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-xs'
                      }`}
                    >
                      <div>
                        {/* Card Header */}
                        <div className="flex items-start justify-between gap-3 mb-3">
                          <div className="flex items-center gap-3">
                            <div className="w-11 h-11 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-700 overflow-hidden shrink-0 shadow-2xs">
                              {lead.avatar ? (
                                <img src={lead.avatar} alt={lead.name} className="w-full h-full object-cover" />
                              ) : (
                                lead.initials
                              )}
                            </div>
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <h3 className="font-bold text-slate-900 text-sm flex items-center gap-1.5">
                                  {lead.name}
                                </h3>
                                {/* Type Pill */}
                                <span className={`text-[10px] font-extrabold px-1.5 py-0.2 rounded ${
                                  isPJ ? 'bg-indigo-100 text-indigo-800' : 'bg-emerald-100 text-emerald-800'
                                }`}>
                                  {isPJ ? 'PJ' : 'PF'}
                                </span>
                              </div>
                              <p className="text-xs text-slate-500 font-medium line-clamp-1">{lead.title}</p>
                            </div>
                          </div>

                          <div onClick={(e) => e.stopPropagation()}>
                            <input 
                              type="checkbox" 
                              checked={isSelected}
                              onChange={(e) => toggleSelectLead(lead.id, e as any)}
                              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-4 h-4 cursor-pointer" 
                            />
                          </div>
                        </div>

                        {/* Company / Registration Details */}
                        <div className="p-3 bg-slate-50 rounded-xl space-y-2 text-xs mb-3">
                          <div className="flex items-center justify-between font-semibold">
                            <span className="text-slate-900 flex items-center gap-1">
                              {isPJ ? <Building2 className="w-3.5 h-3.5 text-indigo-600" /> : <UserCheck className="w-3.5 h-3.5 text-emerald-600" />}
                              {lead.company}
                            </span>
                            <span className="text-slate-500 text-[11px]">{lead.location}</span>
                          </div>

                          {isPJ ? (
                            <div className="flex items-center justify-between text-[11px] text-slate-600">
                              <span className="font-mono">{lead.cnpj || 'CNPJ não informado'}</span>
                              <span className="font-bold text-blue-600">{lead.companySize}</span>
                            </div>
                          ) : (
                            <div className="flex items-center justify-between text-[11px] text-slate-600">
                              <span className="font-mono">CPF: {lead.cpf || 'não informado'}</span>
                              <span className="font-bold text-emerald-700">{lead.profissao?.split('(')[0] || 'Profissão não informada'}</span>
                            </div>
                          )}

                          <div className="pt-2 border-t border-slate-200/80 flex items-center justify-between text-[11px]">
                            {lead.intentScore > 0 && lead.intentTopic ? (
                              <>
                                <span className="text-amber-800 font-bold flex items-center gap-1">
                                  <Flame className="w-3 h-3 text-amber-500" /> {lead.intentScore}% de intenção
                                </span>
                                <span className="text-slate-500 truncate max-w-[160px]">{lead.intentTopic}</span>
                              </>
                            ) : (
                              <span className="text-slate-500">Intenção não disponível</span>
                            )}
                          </div>
                        </div>

                        {/* Contacts Section */}
                        <div className="space-y-1.5 text-xs">
                          <div className="flex items-center justify-between text-slate-700">
                            <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                              <Mail className="w-3 h-3 text-slate-400" /> E-mail:
                            </span>
                            <span className="font-semibold text-slate-900 truncate max-w-[170px]">{lead.email}</span>
                          </div>
                          <EvidenceBadge status={lead.emailEvidenceStatus} compact />

                          <div className="flex items-center justify-between text-slate-700">
                            <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                              <Phone className="w-3 h-3 text-slate-400" /> Telefone:
                            </span>
                            {!lead.phone ? (
                              <span className="text-[11px] text-slate-500">Não informado</span>
                            ) : lead.phoneRevealed ? (
                              <span className="font-bold text-emerald-700">{lead.phone}</span>
                            ) : (
                              <button
                                onClick={(e) => handleRevealPhone(lead.id, e)}
                                className="text-[11px] text-indigo-600 hover:underline font-bold"
                              >
                                Revelar Número
                              </button>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-1.5">
                            <EvidenceBadge status={lead.phoneEvidenceStatus} compact />
                            <EvidenceBadge status={lead.whatsappEvidenceStatus} compact />
                          </div>
                          {lead.phoneRevealed && lead.phone && lead.whatsappEvidenceStatus !== 'ABSENT' && lead.whatsappEvidenceStatus !== 'REJECTED' && (
                            <a
                              href={`https://wa.me/${lead.phone.replace(/[^0-9]/g, '')}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[11px] font-semibold text-blue-700 hover:underline"
                            >
                              Tentar no WhatsApp — não confirmado
                            </a>
                          )}
                        </div>
                      </div>

                      {/* Card Footer Actions */}
                      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                        <EvidenceBadge status={lead.identityEvidenceStatus} compact />
                        <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                          <button
                            onClick={() => {
                              setSelectedLeadIds([lead.id]);
                              setIsAddToListOpen(true);
                            }}
                            className="px-2.5 py-1 bg-slate-100 hover:bg-blue-50 hover:text-blue-600 text-slate-700 rounded-lg text-xs font-bold transition-colors"
                          >
                            + Lista
                          </button>
                          <button
                            onClick={() => setActiveLead(lead)}
                            className="px-2.5 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-colors"
                          >
                            Ver Perfil
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Results footer */}
          <div className="p-4 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-slate-600 bg-slate-50/60">
            <div className="font-medium">
              Mostrando <strong className="text-slate-900 font-bold">{filteredLeads.length > 0 ? 1 : 0}-{filteredLeads.length}</strong> de{' '}
              <strong className="text-slate-900 font-bold">{filteredLeads.length}</strong> registros encontrados
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
