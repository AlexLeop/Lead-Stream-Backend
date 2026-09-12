import React, { useEffect, useState } from 'react';
import { Plus, Search, Folder, RefreshCw, Download, CheckCircle2, AlertCircle, XCircle, Trash2, Eye, Sparkles, PlugZap } from 'lucide-react';
import type { Lead } from '../types';
import LeadDetailsModal from '../components/LeadDetailsModal';
import ExportModal from '../components/ExportModal';
import { useLeadStream } from '../LeadStreamContext';

export default function Lists() {
  const { lists, leads, createList, archiveList, refresh } = useLeadStream();
  const [selectedListId, setSelectedListId] = useState<string>('');
  const [searchListQuery, setSearchListQuery] = useState('');
  const [showArchived, setShowArchived] = useState(false);

  // Validation re-check state
  const [isValidating, setIsValidating] = useState(false);

  // New list state
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [newListDesc, setNewListDesc] = useState('');
  const [newListCRM, setNewListCRM] = useState<'HubSpot' | 'Salesforce' | 'RD Station' | 'Pipedrive'>('HubSpot');

  // Modals
  const [activeLead, setActiveLead] = useState<Lead | null>(null);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [operationMessage, setOperationMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedListId && lists.length) setSelectedListId(lists[0].id);
    if (selectedListId && !lists.some((list) => list.id === selectedListId)) {
      setSelectedListId(lists[0]?.id ?? '');
    }
  }, [lists, selectedListId]);

  const selectedList = lists.find(l => l.id === selectedListId) || lists[0];

  // Leads that belong to this list
  const currentLeads = leads.filter(lead => selectedList?.leadIds?.includes(lead.id));

  const filteredLists = lists.filter(l => {
    if (!showArchived && l.isArchived) return false;
    if (showArchived && !l.isArchived) return false;
    if (searchListQuery.trim()) {
      return l.name.toLowerCase().includes(searchListQuery.toLowerCase());
    }
    return true;
  });

  const handleRevalidate = async () => {
    setIsValidating(true);
    try {
      await refresh();
      setOperationMessage('Dados atualizados com sucesso.');
    } finally {
      setIsValidating(false);
    }
  };

  const handleCreateListSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newListName.trim()) return;

    try {
      const newList = await createList({ name: newListName, description: newListDesc, crmTarget: newListCRM });
      setSelectedListId(newList.id);
      setNewListName('');
      setNewListDesc('');
      setIsCreatingNew(false);
      setOperationMessage(`Lista “${newList.name}” criada.`);
    } catch (cause) {
      setOperationMessage(cause instanceof Error ? cause.message : 'Não foi possível criar a lista.');
    }
  };

  const handleDeleteList = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm('Deseja realmente arquivar esta lista?')) {
      try {
        await archiveList(id);
        setOperationMessage('Lista arquivada.');
      } catch (cause) {
        setOperationMessage(cause instanceof Error ? cause.message : 'Não foi possível arquivar a lista.');
      }
    }
  };

  return (
    <div className="h-full max-w-[1440px] mx-auto flex flex-col pb-4">
      {operationMessage && (
        <div className="mb-4 flex items-center justify-between rounded-xl bg-blue-50 px-4 py-3 text-xs font-semibold text-blue-800" role="status">
          <span>{operationMessage}</span>
          <button onClick={() => setOperationMessage(null)} className="font-bold">Fechar</button>
        </div>
      )}
      <LeadDetailsModal lead={activeLead} onClose={() => setActiveLead(null)} />
      <ExportModal 
        isOpen={isExportOpen} 
        onClose={() => setIsExportOpen(false)} 
        leads={currentLeads} 
        selectedIds={[]} 
      />

      <div className="flex-1 flex flex-col xl:flex-row gap-5 min-h-0">
        {/* Left Column: Saved Lists (Matching Image 4) */}
        <div className="w-full xl:w-80 flex-shrink-0 bg-white border border-slate-200 rounded-[12px] flex flex-col max-h-[440px] xl:max-h-none xl:h-[calc(100vh-8.5rem)]">
          <div className="p-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/60 rounded-t-2xl">
            <h2 className="font-bold text-slate-900 text-sm flex items-center gap-2">
              <Folder className="w-4 h-4 text-blue-600" /> Listas Salvas ({lists.filter(l => !l.isArchived).length})
            </h2>
            <button 
              onClick={() => setIsCreatingNew(!isCreatingNew)}
              className="p-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition-colors shadow-2xs"
              title="Nova Lista"
            >
              <Plus className="w-3.5 h-3.5" /> Nova Lista
            </button>
          </div>

          {/* New list form dropdown */}
          {isCreatingNew && (
            <form onSubmit={handleCreateListSubmit} className="p-4 bg-blue-50/50 border-b border-blue-100 space-y-3 animate-in fade-in duration-150">
              <div className="text-xs font-bold text-blue-900">Criar Nova Lista de Prospecção</div>
              <input 
                type="text" 
                value={newListName}
                onChange={(e) => setNewListName(e.target.value)}
                placeholder="Nome da Lista (ex: Varejo SP)" 
                className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-medium"
                autoFocus
              />
              <input 
                type="text" 
                value={newListDesc}
                onChange={(e) => setNewListDesc(e.target.value)}
                placeholder="Descrição rápida da campanha" 
                className="w-full px-3 py-1.5 text-xs bg-white border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="flex gap-2">
                <select 
                  value={newListCRM} 
                  onChange={(e) => setNewListCRM(e.target.value as any)}
                  className="flex-1 text-xs border border-slate-200 bg-white rounded-lg px-2 py-1"
                >
                  <option value="HubSpot">HubSpot CRM</option>
                  <option value="Salesforce">Salesforce</option>
                  <option value="RD Station">RD Station CRM</option>
                  <option value="Pipedrive">Pipedrive</option>
                </select>
                <button type="submit" className="px-3 py-1 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700">
                  Salvar
                </button>
              </div>
            </form>
          )}

          {/* Search box for lists */}
          <div className="p-3 border-b border-slate-100">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input 
                type="text" 
                value={searchListQuery}
                onChange={(e) => setSearchListQuery(e.target.value)}
                placeholder="Buscar listas por nome..." 
                className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Lists Container */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
            {filteredLists.length === 0 && (
              <div className="rounded-xl bg-slate-50 p-4 text-center text-xs font-medium text-slate-600">
                {showArchived ? 'Nenhuma lista arquivada.' : 'Nenhuma lista criada. Use “Nova Lista” para começar.'}
              </div>
            )}
            {filteredLists.map((list) => {
              const isSelected = selectedList?.id === list.id;
              return (
                <div
                  key={list.id}
                  onClick={() => setSelectedListId(list.id)}
                  className={`p-3.5 rounded-xl border transition-all cursor-pointer relative group ${
                    isSelected 
                      ? 'border-blue-600 bg-blue-50/50 shadow-xs' 
                      : 'border-slate-200/80 bg-white hover:border-slate-300 hover:bg-slate-50/50'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="font-bold text-slate-900 text-xs pr-2 line-clamp-1">{list.name}</div>
                    <button 
                      onClick={(e) => handleDeleteList(list.id, e)}
                      className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 p-0.5 rounded transition-opacity"
                      title="Arquivar Lista"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  
                  <div className="flex items-center gap-2 text-[11px] text-slate-500 font-medium mt-1">
                    <span>{list.leadCount} {list.leadCount === 1 ? 'contato' : 'contatos'}</span>
                    <span>•</span>
                    <span className="text-slate-600 font-semibold">{list.crmTarget}</span>
                  </div>

                  <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[10px]">
                    <span className="text-slate-400">CRM: {list.lastSynced}</span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 font-semibold text-slate-600">
                      {list.crmStatus}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="p-3 border-t border-slate-100 bg-slate-50/50 rounded-b-2xl flex items-center justify-between text-xs text-slate-500">
            <button 
              onClick={() => setShowArchived(!showArchived)}
              className="text-blue-600 font-semibold hover:underline"
            >
              {showArchived ? '← Ver Listas Ativas' : 'Ver Listas Arquivadas'}
            </button>
          </div>
        </div>

        {/* Right Column: List Details */}
        {selectedList ? (
        <div className="flex-1 bg-white border border-slate-200 rounded-[12px] flex flex-col min-h-[620px] xl:h-[calc(100vh-8.5rem)] overflow-hidden">
          {/* Header */}
          <div className="p-6 border-b border-slate-100 flex flex-wrap items-start justify-between gap-4 bg-slate-50/40">
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold text-slate-900 tracking-tight">{selectedList?.name}</h1>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-100">
                  {selectedList?.leadCount ?? 0} {(selectedList?.leadCount ?? 0) === 1 ? 'contato' : 'contatos'}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1 max-w-xl">
                {selectedList?.description || 'Sem descrição.'}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button 
                onClick={() => setIsExportOpen(true)}
                disabled={!selectedList}
                className="px-3.5 py-2 bg-white border border-slate-200 hover:border-slate-300 text-slate-700 rounded-xl font-semibold text-xs flex items-center gap-1.5 hover:bg-slate-50 transition-all shadow-2xs"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" /> Exportar CSV
              </button>

              <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-600">
                <PlugZap className="h-3.5 w-3.5" aria-hidden="true" />
                Integração CRM em preparação
              </div>
            </div>
          </div>

          {/* Validation Metric Bar (Matching Image 4) */}
          <div className="p-4 bg-slate-50 border-b border-slate-100 flex flex-wrap items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-blue-600" />
                <span className="text-slate-600 font-medium">Caixas validadas tecnicamente:</span>
                <strong className="text-slate-900 font-bold">
                  {selectedList?.validCount ?? 0} {(selectedList?.validCount ?? 0) === 1 ? 'contato' : 'contatos'} ({selectedList?.leadCount ? Math.round((selectedList.validCount / selectedList.leadCount) * 100) : 0}%)
                </strong>
              </div>

              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-slate-500" />
                <span className="text-slate-600 font-medium">Catch-all:</span>
                <strong className="text-slate-700 font-bold">
                  {selectedList?.catchAllCount ?? 0} {(selectedList?.catchAllCount ?? 0) === 1 ? 'contato' : 'contatos'} ({selectedList?.leadCount ? Math.round((selectedList.catchAllCount / selectedList.leadCount) * 100) : 0}%)
                </strong>
              </div>

              <div className="flex items-center gap-2">
                <XCircle className="w-4 h-4 text-slate-400" />
                <span className="text-slate-600 font-medium">Inválidos:</span>
                <strong className="text-slate-500 font-bold">
                  {selectedList?.invalidCount ?? 0} {(selectedList?.invalidCount ?? 0) === 1 ? 'contato' : 'contatos'} ({selectedList?.leadCount ? Math.round((selectedList.invalidCount / selectedList.leadCount) * 100) : 0}%)
                </strong>
              </div>
            </div>

            <button 
              onClick={handleRevalidate}
              disabled={isValidating}
              className="text-xs font-bold text-blue-600 hover:text-blue-800 flex items-center gap-1.5 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isValidating ? 'animate-spin' : ''}`} />
              {isValidating ? 'Atualizando…' : 'Atualizar dados'}
            </button>
          </div>

          {/* Table of leads in this list */}
          <div className="flex-1 overflow-auto">
            <table className="w-full text-xs text-left">
              <thead className="text-[11px] text-slate-500 uppercase bg-slate-50/80 border-b border-slate-200 sticky top-0 z-10 font-bold tracking-wider">
                <tr>
                  <th className="px-4 py-3">NOME DO DECISOR</th>
                  <th className="px-4 py-3">EMPRESA & SETOR</th>
                  <th className="px-4 py-3">E-MAIL CORPORATIVO</th>
                  <th className="px-4 py-3">TELEFONE / WHATSAPP</th>
                  <th className="px-4 py-3">INTENÇÃO DE COMPRA</th>
                  <th className="px-4 py-3 text-right">AÇÕES</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {currentLeads.map((lead) => (
                  <tr 
                    key={lead.id} 
                    className="hover:bg-blue-50/20 transition-colors cursor-pointer"
                    onClick={() => setActiveLead(lead)}
                  >
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-700 overflow-hidden shrink-0 shadow-2xs">
                          {lead.avatar ? (
                            <img src={lead.avatar} alt={lead.name} className="w-full h-full object-cover" />
                          ) : (
                            lead.initials
                          )}
                        </div>
                        <div>
                          <div className="font-bold text-slate-900">{lead.name}</div>
                          <div className="text-slate-500 text-[11px] font-medium">{lead.title}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="font-bold text-slate-900">{lead.company}</div>
                      <div className="text-slate-500 text-[11px]">{lead.industry} • {lead.city}</div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="font-mono text-slate-800 text-xs">{lead.email}</div>
                      <div className="text-[10px] text-blue-600 font-semibold flex items-center gap-1 mt-0.5">
                        {lead.status === 'Verificado' && <CheckCircle2 className="w-3 h-3" />} {lead.status}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 font-medium text-slate-700">
                      {lead.phone || 'Não informado'}
                    </td>
                    <td className="px-4 py-3.5">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-blue-50 text-blue-700 border border-blue-100">
                        <Sparkles className="w-3 h-3 text-blue-600" /> {lead.intentScore > 0 ? `${lead.intentScore}%` : 'Não calculado'}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-right" onClick={(e) => e.stopPropagation()}>
                      <button 
                        onClick={() => setActiveLead(lead)}
                        className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                        title="Ver Perfil Detalhado"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        ) : (
          <div className="flex-1 bg-white border border-slate-200 rounded-[12px] flex min-h-[620px] xl:h-[calc(100vh-8.5rem)] items-center justify-center p-8">
            <div className="max-w-sm text-center">
              <Folder className="mx-auto h-10 w-10 text-slate-300" />
              <h1 className="mt-4 text-lg font-bold text-slate-900">Crie sua primeira lista</h1>
              <p className="mt-2 text-sm leading-relaxed text-slate-500">
                Agrupe contatos por campanha e exporte os resultados. A integração direta com CRM ainda está em preparação.
              </p>
              <button
                onClick={() => setIsCreatingNew(true)}
                className="mt-5 rounded-xl bg-blue-600 px-4 py-2.5 text-xs font-bold text-white hover:bg-blue-700"
              >
                Nova lista
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
