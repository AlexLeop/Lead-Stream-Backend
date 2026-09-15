import React, { useState, useMemo } from 'react';
import { 
  FolderKanban, 
  FolderPlus, 
  Upload, 
  Search, 
  Building2, 
  UserCheck, 
  Layers, 
  Filter, 
  CheckCircle2, 
  ArrowUpRight, 
  Download, 
  MoreVertical, 
  Trash2, 
  Edit3, 
  Calendar, 
  Database, 
  Plus, 
  ChevronRight, 
  Check, 
  FileText,
  Tag,
  ShieldCheck,
  TrendingUp,
  Mail,
  Phone
} from 'lucide-react';
import type { CreateDatasetInput, ImportResult, LeadSet } from '../types';
import { leadSetCategories } from '../config';
import { useLeadStream } from '../LeadStreamContext';
import CreateLeadSetModal from '../components/CreateLeadSetModal';
import UploadEnrichModal from '../components/UploadEnrichModal';
import ExportModal from '../components/ExportModal';

interface DatasetsProps {
  onNavigateToSearchWithSet?: (setId: string) => void;
}

export default function DatasetsPage({ onNavigateToSearchWithSet }: DatasetsProps) {
  const { datasets: sets, leads, createDataset, deleteDataset } = useLeadStream();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('Todas as Categorias');
  const [selectedLeadType, setSelectedLeadType] = useState<'ALL' | 'PJ' | 'PF' | 'MISTO'>('ALL');

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isExportModalOpen, setIsExportModalOpen] = useState(false);
  const [selectedSetForExport, setSelectedSetForExport] = useState<LeadSet | null>(null);

  // Toast
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleCreateSet = async (input: CreateDatasetInput) => {
    const newSet = await createDataset(input);
    triggerToast(`Dataset "${newSet.name}" criado com sucesso.`);
    return newSet;
  };

  const handleUploadSuccess = (result: ImportResult) => {
    setIsUploadModalOpen(false);
    triggerToast(`${result.imported} linha(s) recebida(s) no lote "${result.dataset.name}". O processamento continuará em segundo plano.`);
  };

  const handleDeleteSet = async (setId: string, setName: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Tem certeza que deseja excluir o conjunto "${setName}"?`)) {
      try {
        await deleteDataset(setId);
        triggerToast(`Dataset "${setName}" removido com sucesso.`);
      } catch (cause) {
        triggerToast(cause instanceof Error ? cause.message : 'Não foi possível remover o dataset.');
      }
    }
  };

  // Filtered sets
  const filteredSets = useMemo(() => {
    return sets.filter(s => {
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesName = s.name.toLowerCase().includes(q);
        const matchesDesc = s.description?.toLowerCase().includes(q);
        const matchesCat = s.category.toLowerCase().includes(q);
        const matchesTag = s.tags?.some(t => t.toLowerCase().includes(q));
        if (!matchesName && !matchesDesc && !matchesCat && !matchesTag) return false;
      }

      if (selectedCategory !== 'Todas as Categorias' && s.category !== selectedCategory) {
        return false;
      }

      if (selectedLeadType !== 'ALL' && s.leadType !== selectedLeadType) {
        return false;
      }

      return true;
    });
  }, [sets, searchQuery, selectedCategory, selectedLeadType]);

  // Overall statistics
  const totalSets = sets.length;
  const totalLeadsInSets = sets.reduce((acc, s) => acc + s.totalLeads, 0);
  const avgEnrichmentRate = sets.length > 0 
    ? Math.round(sets.reduce((acc, s) => acc + s.enrichmentRate, 0) / sets.length) 
    : 0;

  return (
    <div className="h-full flex flex-col pb-6 max-w-[1440px] mx-auto relative space-y-5">
      {/* Toast */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-slate-900 text-white px-4 py-3 rounded-xl shadow-2xl border border-slate-800 flex items-center gap-2.5 text-xs font-semibold animate-in fade-in slide-in-from-bottom-3 duration-300">
          <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Modals */}
      <CreateLeadSetModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreateSet={handleCreateSet}
      />

      <UploadEnrichModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onSuccess={handleUploadSuccess}
        existingSets={sets}
      />

      {selectedSetForExport && (
        <ExportModal
          isOpen={isExportModalOpen}
          onClose={() => {
            setIsExportModalOpen(false);
            setSelectedSetForExport(null);
          }}
          leads={leads.filter(l => l.setId === selectedSetForExport.id || selectedSetForExport.leadIds.includes(l.id))}
          selectedIds={[]}
        />
      )}

      {/* Top Header Card */}
      <div className="bg-white p-5 sm:p-6 rounded-[12px] border border-slate-200 flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
              Suas bases
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-700 border border-blue-200">
              {totalSets} {totalSets === 1 ? 'base ativa' : 'bases ativas'}
            </span>
          </div>
          <p className="text-slate-500 text-xs sm:text-sm mt-1 font-medium max-w-2xl">
            Importe arquivos, organize segmentos e acompanhe os dados disponíveis para suas campanhas.
          </p>
        </div>

        <div className="flex items-center gap-3 w-full lg:w-auto flex-wrap">
          {/* Create Set Button */}
          <button
            onClick={() => setIsCreateModalOpen(true)}
            className="px-4 py-2.5 bg-white border border-slate-200 hover:border-slate-300 hover:bg-slate-50 text-slate-800 rounded-xl font-bold text-xs shadow-2xs transition-all flex items-center gap-2 cursor-pointer"
          >
            <FolderPlus className="w-4 h-4 text-blue-600" />
            <span>+ Novo Conjunto</span>
          </button>

          {/* Upload & Enrich Base Button */}
          <button
            onClick={() => setIsUploadModalOpen(true)}
            className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-[10px] font-bold text-xs transition-colors flex items-center gap-2 cursor-pointer"
          >
            <Upload className="w-4 h-4" />
            <span>Importar Base</span>
          </button>
        </div>
      </div>

      {/* KPI Metrics Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-600 border border-blue-100 flex items-center justify-center font-bold">
            <FolderKanban className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Total de Conjuntos</div>
            <div className="text-xl font-extrabold text-slate-900 mt-0.5">{totalSets}</div>
          </div>
        </div>

        <div className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-indigo-50 text-indigo-600 border border-indigo-100 flex items-center justify-center font-bold">
            <Database className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Leads Indexados</div>
            <div className="text-xl font-extrabold text-slate-900 mt-0.5">{totalLeadsInSets.toLocaleString('pt-BR')}</div>
          </div>
        </div>

        <div className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-emerald-50 text-emerald-600 border border-emerald-100 flex items-center justify-center font-bold">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Cobertura Média</div>
            <div className="text-xl font-extrabold text-emerald-700 mt-0.5">{avgEnrichmentRate}%</div>
          </div>
        </div>

        <div className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-xs flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-xl bg-amber-50 text-amber-600 border border-amber-100 flex items-center justify-center font-bold">
            <UserCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Contatos disponíveis</div>
            <div className="text-xl font-extrabold text-slate-900 mt-0.5">{leads.length.toLocaleString('pt-BR')}</div>
          </div>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200/90 shadow-xs flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Search */}
        <div className="relative w-full md:w-80">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
            <Search className="w-4 h-4" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Buscar por nome do conjunto, categoria ou tag..."
            className="w-full pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-semibold text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all"
          />
        </div>

        {/* Category Pills & Lead Type */}
        <div className="flex items-center gap-2 overflow-x-auto w-full md:w-auto pb-1 md:pb-0">
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="px-3 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs font-bold text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option>Todas as Categorias</option>
            {leadSetCategories.map(cat => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>

          <div className="flex items-center bg-slate-100 p-0.5 rounded-xl text-xs font-bold text-slate-600 shrink-0">
            <button
              onClick={() => setSelectedLeadType('ALL')}
              className={`px-2.5 py-1 rounded-lg transition-all ${
                selectedLeadType === 'ALL' ? 'bg-white text-slate-900 shadow-2xs font-extrabold' : 'hover:text-slate-900'
              }`}
            >
              Todos
            </button>
            <button
              onClick={() => setSelectedLeadType('PJ')}
              className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1 ${
                selectedLeadType === 'PJ' ? 'bg-indigo-600 text-white shadow-2xs font-extrabold' : 'hover:text-indigo-700'
              }`}
            >
              <Building2 className="w-3 h-3" /> PJ
            </button>
            <button
              onClick={() => setSelectedLeadType('PF')}
              className={`px-2.5 py-1 rounded-lg transition-all flex items-center gap-1 ${
                selectedLeadType === 'PF' ? 'bg-emerald-600 text-white shadow-2xs font-extrabold' : 'hover:text-emerald-700'
              }`}
            >
              <UserCheck className="w-3 h-3" /> PF
            </button>
          </div>
        </div>
      </div>

      {/* Grid of Sets */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        {filteredSets.length === 0 ? (
          <div className="col-span-full py-16 text-center bg-white rounded-2xl border border-slate-200/90 p-8 space-y-4">
            <div className="w-12 h-12 rounded-2xl bg-slate-100 flex items-center justify-center text-slate-400 mx-auto">
              <FolderKanban className="w-6 h-6" />
            </div>
            <div className="space-y-1 max-w-sm mx-auto">
              <h3 className="font-extrabold text-slate-900 text-sm">Nenhum conjunto encontrado</h3>
              <p className="text-xs text-slate-500 font-medium">
                Crie um novo conjunto de leads ou faça o upload de um arquivo para começar.
              </p>
            </div>
            <button
              onClick={() => setIsCreateModalOpen(true)}
              className="px-4 py-2 bg-blue-600 text-white font-bold text-xs rounded-xl shadow-xs hover:bg-blue-700 transition-all cursor-pointer inline-flex items-center gap-1.5"
            >
              <FolderPlus className="w-4 h-4" /> Criar Primeiro Conjunto
            </button>
          </div>
        ) : (
          filteredSets.map((set) => {
            const isPJ = set.leadType === 'PJ';
            const isPF = set.leadType === 'PF';

            return (
              <div
                key={set.id}
                className="bg-white rounded-2xl border border-slate-200/90 shadow-xs hover:shadow-md hover:border-slate-300 transition-all p-5 flex flex-col justify-between space-y-4 group"
              >
                <div>
                  {/* Top bar: Category Badge + Type + Options */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      {/* Category Tag */}
                      <span className="px-2.5 py-1 rounded-lg text-[11px] font-extrabold bg-blue-50 text-blue-700 border border-blue-200 flex items-center gap-1">
                        <Tag className="w-3 h-3 text-blue-600" /> {set.category}
                      </span>

                      {/* Lead Type Pill */}
                      <span className={`px-2 py-0.5 rounded-lg text-[10px] font-extrabold flex items-center gap-1 ${
                        isPJ 
                          ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' 
                          : isPF
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-purple-50 text-purple-700 border border-purple-200'
                      }`}>
                        {isPJ && <Building2 className="w-3 h-3" />}
                        {isPF && <UserCheck className="w-3 h-3" />}
                        {!isPJ && !isPF && <Layers className="w-3 h-3" />}
                        {set.leadType}
                      </span>
                    </div>

                    <button
                      onClick={(e) => handleDeleteSet(set.id, set.name, e)}
                      className="text-slate-400 hover:text-red-600 p-1 rounded-lg transition-colors cursor-pointer"
                      title="Excluir Conjunto"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Set Name and Description */}
                  <div className="mt-3 space-y-1">
                    <h3 className="text-base font-extrabold text-slate-900 group-hover:text-blue-600 transition-colors">
                      {set.name}
                    </h3>
                    <p className="text-xs text-slate-500 font-medium line-clamp-2 leading-relaxed">
                      {set.description || 'Conjunto de prospecção e inteligência comercial.'}
                    </p>
                  </div>

                  {/* Tags */}
                  {set.tags && set.tags.length > 0 && (
                    <div className="flex items-center gap-1.5 flex-wrap mt-3">
                      {set.tags.map((tag, idx) => (
                        <span key={idx} className="text-[10px] font-semibold px-2 py-0.5 bg-slate-100 text-slate-600 rounded-md">
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Stats Box */}
                  <div className="mt-4 p-3 bg-slate-50 rounded-xl space-y-2 border border-slate-100 text-xs">
                    <div className="flex justify-between items-center font-semibold">
                      <span className="text-slate-600">Volume de Leads:</span>
                      <span className="font-extrabold text-slate-900">{set.totalLeads} {set.totalLeads === 1 ? 'contato' : 'contatos'}</span>
                    </div>

                    <div className="space-y-1">
                      <div className="flex justify-between text-[11px] font-bold">
                        <span className="text-slate-500">Taxa de Enriquecimento:</span>
                        <span className="text-emerald-700">{set.enrichmentRate}% assertivo</span>
                      </div>
                      <div className="w-full bg-slate-200 h-1.5 rounded-full overflow-hidden">
                        <div 
                          className="bg-emerald-500 h-full rounded-full" 
                          style={{ width: `${set.enrichmentRate}%` }} 
                        />
                      </div>
                    </div>

                    {set.fileOriginName && (
                      <div className="pt-1.5 border-t border-slate-200/80 flex items-center justify-between text-[11px] text-slate-500">
                        <span className="flex items-center gap-1 truncate max-w-[170px]">
                          <FileText className="w-3 h-3 text-slate-400" /> {set.fileOriginName}
                        </span>
                        <span>{set.createdAt}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Footer Action Buttons */}
                <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                  <button
                    onClick={() => {
                      setSelectedSetForExport(set);
                      setIsExportModalOpen(true);
                    }}
                    className="p-2 bg-slate-50 hover:bg-slate-100 text-slate-600 hover:text-slate-900 rounded-xl text-xs font-bold transition-all border border-slate-200 flex items-center gap-1.5 cursor-pointer"
                    title="Exportar base deste conjunto"
                  >
                    <Download className="w-3.5 h-3.5" /> Exportar
                  </button>

                  <button
                    onClick={() => {
                      if (onNavigateToSearchWithSet) {
                        onNavigateToSearchWithSet(set.id);
                      }
                    }}
                    className="flex-1 py-2 px-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-extrabold transition-all shadow-xs flex items-center justify-center gap-1.5 cursor-pointer"
                  >
                    <span>Ver Leads</span>
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
