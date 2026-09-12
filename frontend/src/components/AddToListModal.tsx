import React, { useState } from 'react';
import { X, Plus, FolderPlus, Check, Folder } from 'lucide-react';
import { CampaignList, Lead } from '../types';

interface AddToListModalProps {
  isOpen: boolean;
  onClose: () => void;
  lists: CampaignList[];
  leadsToAdd: Lead[];
  onAdd: (listId: string, leadIds: string[]) => void;
  onCreateNewList: (name: string, description: string) => void;
}

export default function AddToListModal({
  isOpen,
  onClose,
  lists,
  leadsToAdd,
  onAdd,
  onCreateNewList
}: AddToListModalProps) {
  const [selectedListId, setSelectedListId] = useState<string>(lists[0]?.id || '');
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [newListName, setNewListName] = useState('');
  const [newListDesc, setNewListDesc] = useState('');
  const [success, setSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSave = () => {
    if (isCreatingNew) {
      if (!newListName.trim()) return;
      onCreateNewList(newListName, newListDesc);
    } else {
      if (!selectedListId) return;
      onAdd(selectedListId, leadsToAdd.map(l => l.id));
    }

    setSuccess(true);
    setTimeout(() => {
      setSuccess(false);
      onClose();
    }, 1200);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div 
        className="w-full max-w-md bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Adicionar à Lista de Prospecção</h2>
            <p className="text-xs text-slate-500 mt-0.5">{leadsToAdd.length} contato(s) selecionado(s)</p>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {!isCreatingNew ? (
            <>
              <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider">Escolha a Lista / Campanha de Destino</label>
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {lists.filter(l => !l.isArchived).map((list) => (
                  <button
                    key={list.id}
                    type="button"
                    onClick={() => setSelectedListId(list.id)}
                    className={`w-full p-3 rounded-xl border text-left flex items-center justify-between transition-all ${
                      selectedListId === list.id
                        ? 'border-blue-600 bg-blue-50/50 text-blue-900 ring-2 ring-blue-600/20'
                        : 'border-slate-200 hover:border-slate-300 text-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${selectedListId === list.id ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
                        <Folder className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="text-sm font-bold text-slate-900">{list.name}</div>
                        <div className="text-xs text-slate-500">{list.leadCount} leads existentes • {list.crmTarget}</div>
                      </div>
                    </div>
                    {selectedListId === list.id && <Check className="w-4 h-4 text-blue-600" />}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={() => setIsCreatingNew(true)}
                className="w-full py-2.5 px-3 border border-dashed border-slate-300 hover:border-blue-400 rounded-xl text-xs font-semibold text-blue-600 hover:bg-blue-50/50 flex items-center justify-center gap-2 transition-colors mt-2"
              >
                <FolderPlus className="w-4 h-4" /> Criar uma Nova Lista / Pasta
              </button>
            </>
          ) : (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">Nome da Nova Lista</label>
                <input
                  type="text"
                  value={newListName}
                  onChange={(e) => setNewListName(e.target.value)}
                  placeholder="Ex: Decisores Varejo Rio de Janeiro Q3"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">Descrição / Objetivo da Campanha</label>
                <textarea
                  value={newListDesc}
                  onChange={(e) => setNewListDesc(e.target.value)}
                  placeholder="Ex: Prospecção ativa de Heads de Operações e Logística"
                  rows={2}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="flex justify-start">
                <button
                  type="button"
                  onClick={() => setIsCreatingNew(false)}
                  className="text-xs text-slate-500 hover:text-slate-800 underline"
                >
                  ← Voltar para listas existentes
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={success || (!isCreatingNew && !selectedListId) || (isCreatingNew && !newListName.trim())}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-sm rounded-lg shadow-xs transition-colors flex items-center gap-2"
          >
            {success ? (
              <><Check className="w-4 h-4" /> Adicionado com Sucesso!</>
            ) : isCreatingNew ? (
              <><Plus className="w-4 h-4" /> Criar e Adicionar</>
            ) : (
              <><Check className="w-4 h-4" /> Confirmar Adição</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
