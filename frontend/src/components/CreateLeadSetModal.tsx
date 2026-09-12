import React, { useState } from 'react';
import { 
  X, 
  FolderPlus, 
  Tag, 
  Sparkles, 
  Building2, 
  UserCheck, 
  Layers, 
  Check, 
  HelpCircle,
  FolderKanban
} from 'lucide-react';
import type { CreateDatasetInput, LeadSet } from '../types';
import { leadSetCategories } from '../config';

interface CreateLeadSetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreateSet: (input: CreateDatasetInput) => Promise<LeadSet>;
}

export default function CreateLeadSetModal({
  isOpen,
  onClose,
  onCreateSet
}: CreateLeadSetModalProps) {
  const [setName, setSetName] = useState('');
  const [category, setCategory] = useState('Prospecção Outbound');
  const [customCategory, setCustomCategory] = useState('');
  const [description, setDescription] = useState('');
  const [leadType, setLeadType] = useState<'PJ' | 'PF' | 'MISTO'>('PJ');
  const [tagsInput, setTagsInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!setName.trim()) return;

    const finalCategory = category === 'Outro' && customCategory.trim() 
      ? customCategory.trim() 
      : category;

    const tags = tagsInput
      .split(',')
      .map(t => t.trim())
      .filter(Boolean);

    const newSet: CreateDatasetInput = {
      name: setName.trim(),
      category: finalCategory,
      description: description.trim() || undefined,
      leadType,
      tags: tags.length > 0 ? tags : [leadType, finalCategory]
    };

    setSaving(true);
    setError(null);
    try {
      await onCreateSet(newSet);
      onClose();
      setSetName('');
      setDescription('');
      setTagsInput('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível criar o dataset.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
      <div 
        className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-lg w-full overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-100 border border-blue-200 flex items-center justify-center text-blue-700 font-bold shadow-2xs">
              <FolderPlus className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-slate-900 tracking-tight">
                Criar Novo Conjunto de Leads
              </h2>
              <p className="text-xs text-slate-500 font-medium">
                Organize suas bases por categoria, objetivo comercial ou campanha.
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="rounded-xl bg-red-50 px-3 py-2 text-xs font-semibold text-red-700" role="alert">
              {error}
            </div>
          )}
          {/* Nome do Conjunto */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Nome do Conjunto <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={setName}
              onChange={(e) => setSetName(e.target.value)}
              placeholder="Ex: Clínicas Médicas SP Q3, Diretores TI SaaS, etc."
              className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs sm:text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all shadow-2xs"
            />
          </div>

          {/* Categoria do Conjunto */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5 flex items-center justify-between">
              <span>Categoria Estratégica</span>
              <span className="text-[11px] font-normal text-slate-400">Classificação de uso</span>
            </label>
            <div className="grid grid-cols-2 gap-1.5 mb-2">
              {leadSetCategories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setCategory(cat)}
                  className={`text-left px-3 py-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer flex items-center justify-between ${
                    category === cat
                      ? 'bg-blue-50 border-blue-600 text-blue-700 shadow-2xs font-bold'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  <span className="truncate">{cat}</span>
                  {category === cat && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                </button>
              ))}
            </div>

            {/* Categoria personalizada */}
            <div className="mt-2">
              <input
                type="text"
                value={customCategory}
                onChange={(e) => {
                  setCustomCategory(e.target.value);
                  setCategory('Outro');
                }}
                placeholder="Ou digite outra categoria personalizada..."
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all"
              />
            </div>
          </div>

          {/* Natureza da Base (PJ vs PF) */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Natureza Predominante da Base
            </label>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setLeadType('PJ')}
                className={`py-2 px-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                  leadType === 'PJ'
                    ? 'bg-indigo-50 border-indigo-600 text-indigo-700 shadow-2xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <Building2 className="w-3.5 h-3.5" /> Pessoa Jurídica (PJ)
              </button>

              <button
                type="button"
                onClick={() => setLeadType('PF')}
                className={`py-2 px-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                  leadType === 'PF'
                    ? 'bg-emerald-50 border-emerald-600 text-emerald-700 shadow-2xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <UserCheck className="w-3.5 h-3.5" /> Pessoa Física (PF)
              </button>

              <button
                type="button"
                onClick={() => setLeadType('MISTO')}
                className={`py-2 px-3 rounded-xl border text-xs font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
                  leadType === 'MISTO'
                    ? 'bg-blue-50 border-blue-600 text-blue-700 shadow-2xs'
                    : 'bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <Layers className="w-3.5 h-3.5" /> Misto (PJ + PF)
              </button>
            </div>
          </div>

          {/* Descrição Opcional */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Descrição / Anotações Internas (Opcional)
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Ex: Base coletada para cadência outbound de setembro..."
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all resize-none"
            />
          </div>

          {/* Tags */}
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5 flex items-center gap-1">
              <Tag className="w-3.5 h-3.5 text-slate-400" /> Tags de Identificação (separadas por vírgula)
            </label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="Ex: SaaS, São Paulo, C-Level, Alta Intenção"
              className="w-full px-3.5 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all"
            />
          </div>

          {/* Actions */}
          <div className="pt-3 border-t border-slate-100 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold rounded-xl transition-colors cursor-pointer"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={!setName.trim() || saving}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-extrabold rounded-xl transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
            >
              <FolderPlus className="w-3.5 h-3.5" /> {saving ? 'Criando…' : 'Criar Conjunto'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
