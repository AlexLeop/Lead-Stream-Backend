import React, { useState } from 'react';
import { X, Download, FileSpreadsheet, Check, CheckSquare, Square } from 'lucide-react';
import { Lead } from '../types';

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  leads: Lead[];
  selectedIds: string[];
}

export default function ExportModal({ isOpen, onClose, leads, selectedIds }: ExportModalProps) {
  const [format, setFormat] = useState<'csv' | 'xlsx'>('csv');
  const [exportScope, setExportScope] = useState<'selected' | 'all'>('selected');
  const [includePhone, setIncludePhone] = useState(true);
  const [includeTech, setIncludeTech] = useState(true);
  const [includeIntent, setIncludeIntent] = useState(true);
  const [isExporting, setIsExporting] = useState(false);
  const [exported, setExported] = useState(false);

  if (!isOpen) return null;

  const leadsToExport = exportScope === 'selected' && selectedIds.length > 0
    ? leads.filter(l => selectedIds.includes(l.id))
    : leads;

  const handleExport = () => {
    setIsExporting(true);

    setTimeout(() => {
      // Build CSV content
      const headers = ['Nome', 'Cargo', 'Senioridade', 'Empresa', 'Domínio', 'Localização', 'E-mail Corporativo', 'Status E-mail'];
      if (includePhone) headers.push('Telefone/WhatsApp');
      if (includeTech) headers.push('Tecnologias');
      if (includeIntent) headers.push('Score de Intenção', 'Tópico de Intenção');

      const rows = leadsToExport.map(l => {
        const row = [
          `"${l.name}"`,
          `"${l.title}"`,
          `"${l.seniority}"`,
          `"${l.company}"`,
          `"${l.domain}"`,
          `"${l.location}"`,
          `"${l.email}"`,
          `"${l.status}"`
        ];
        if (includePhone) row.push(`"${l.phone}"`);
        if (includeTech) row.push(`"${l.technologies.join(', ')}"`);
        if (includeIntent) row.push(`"${l.intentScore}%"`, `"${l.intentTopic}"`);
        return row.join(';');
      });

      const csvString = '\uFEFF' + [headers.join(';'), ...rows].join('\n');
      const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `leadstream_export_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      setIsExporting(false);
      setExported(true);
      setTimeout(() => {
        setExported(false);
        onClose();
      }, 1500);
    }, 600);
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-950/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div 
        className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-6 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
              <Download className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Exportar Leads Qualificados</h2>
              <p className="text-xs text-slate-500">Faça o download dos dados enriquecidos para o seu computador</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Scope selection */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Escopo da Exportação</label>
            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setExportScope('selected')}
                disabled={selectedIds.length === 0}
                className={`p-3 rounded-xl border text-left transition-all ${
                  exportScope === 'selected' && selectedIds.length > 0
                    ? 'border-blue-600 bg-blue-50/50 text-blue-900 ring-2 ring-blue-600/20'
                    : selectedIds.length === 0
                    ? 'opacity-50 cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400'
                    : 'border-slate-200 hover:border-slate-300 text-slate-700'
                }`}
              >
                <div className="text-sm font-bold">Leads Selecionados</div>
                <div className="text-xs text-slate-500 mt-0.5">{selectedIds.length} {selectedIds.length === 1 ? 'contato marcado' : 'contatos marcados'}</div>
              </button>

              <button
                type="button"
                onClick={() => setExportScope('all')}
                className={`p-3 rounded-xl border text-left transition-all ${
                  exportScope === 'all'
                    ? 'border-blue-600 bg-blue-50/50 text-blue-900 ring-2 ring-blue-600/20'
                    : 'border-slate-200 hover:border-slate-300 text-slate-700'
                }`}
              >
                <div className="text-sm font-bold">Todos os Resultados</div>
                <div className="text-xs text-slate-500 mt-0.5">{leads.length} {leads.length === 1 ? 'contato disponível' : 'contatos disponíveis'}</div>
              </button>
            </div>
          </div>

          {/* Format selection */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Formato do Arquivo</label>
            <div className="grid grid-cols-2 gap-3">
              <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${format === 'csv' ? 'border-blue-600 bg-blue-50/40 text-blue-900' : 'border-slate-200'}`}>
                <input type="radio" name="format" checked={format === 'csv'} onChange={() => setFormat('csv')} className="text-blue-600" />
                <div>
                  <div className="text-sm font-bold">CSV (.csv)</div>
                  <div className="text-xs text-slate-500">Universal, compatível com CRMs</div>
                </div>
              </label>

              <label className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all ${format === 'xlsx' ? 'border-blue-600 bg-blue-50/40 text-blue-900' : 'border-slate-200'}`}>
                <input type="radio" name="format" checked={format === 'xlsx'} onChange={() => setFormat('xlsx')} className="text-blue-600" />
                <div>
                  <div className="text-sm font-bold">Planilha Excel (.xlsx)</div>
                  <div className="text-xs text-slate-500">Formatado com abas de dados</div>
                </div>
              </label>
            </div>
          </div>

          {/* Additional fields */}
          <div>
            <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Campos Adicionais de Enriquecimento</label>
            <div className="space-y-2">
              <label className="flex items-center gap-2.5 text-sm text-slate-700 cursor-pointer">
                <button type="button" onClick={() => setIncludePhone(!includePhone)} className="text-blue-600">
                  {includePhone ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4 text-slate-400" />}
                </button>
                Telefone e estado de evidência
              </label>
              <label className="flex items-center gap-2.5 text-sm text-slate-700 cursor-pointer">
                <button type="button" onClick={() => setIncludeTech(!includeTech)} className="text-blue-600">
                  {includeTech ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4 text-slate-400" />}
                </button>
                Stack Tecnológico da Empresa (Technographics)
              </label>
              <label className="flex items-center gap-2.5 text-sm text-slate-700 cursor-pointer">
                <button type="button" onClick={() => setIncludeIntent(!includeIntent)} className="text-blue-600">
                  {includeIntent ? <CheckSquare className="w-4 h-4" /> : <Square className="w-4 h-4 text-slate-400" />}
                </button>
                Sinais de Intenção Ativa & Tópico de Compra
              </label>
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-end gap-3">
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
            Cancelar
          </button>
          <button
            onClick={handleExport}
            disabled={isExporting || exported || leadsToExport.length === 0}
            className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-semibold text-sm rounded-lg shadow-xs transition-colors flex items-center gap-2"
          >
            {isExporting ? (
              <>Gerando Arquivo...</>
            ) : exported ? (
              <><Check className="w-4 h-4" /> Exportado com Sucesso!</>
            ) : (
              <><Download className="w-4 h-4" /> Baixar {leadsToExport.length} Leads</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
