import React from 'react';
import { Sparkles, ArrowRight, Building2, TrendingUp, UserPlus, ExternalLink, ChevronRight } from 'lucide-react';
import { Lead } from '../types';
import EvidenceBadge from './EvidenceBadge';

interface BuyingIntentRadarProps {
  leads: Lead[];
  onSelectLead: (lead: Lead) => void;
  onNavigateSearch: () => void;
}

export default function BuyingIntentRadar({ leads, onSelectLead, onNavigateSearch }: BuyingIntentRadarProps) {
  // Sort leads by highest intentScore
  const highIntentLeads = [...leads]
    .filter((lead) => lead.intentScore > 0)
    .sort((a, b) => b.intentScore - a.intentScore)
    .slice(0, 4);

  return (
    <div className="bg-white p-6 rounded-2xl border border-slate-200/90 shadow-xs flex flex-col justify-between">
      <div>
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-5">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900">Radar de Intenção Ativa de Compra</h2>
                <span className="px-2 py-0.5 bg-amber-100/70 text-amber-800 rounded-full text-[10px] font-bold">
                  In-Market Signals
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">Scores de intenção presentes nos dados importados</p>
            </div>
          </div>
          <button
            onClick={onNavigateSearch}
            className="text-blue-600 hover:text-blue-700 text-xs font-bold flex items-center gap-1 hover:underline"
          >
            Ver todos no filtro de intenção <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {highIntentLeads.length === 0 && (
            <div className="rounded-xl bg-slate-50 p-5 text-sm text-slate-600 md:col-span-2">
              Nenhum sinal de intenção está disponível. Importe ou enriqueça empresas para começar a identificar prioridades.
            </div>
          )}
          {highIntentLeads.map((lead) => (
            <div
              key={lead.id}
              onClick={() => onSelectLead(lead)}
              className="p-4 rounded-xl border border-slate-200/80 bg-slate-50/40 hover:bg-white hover:border-blue-300 hover:shadow-xs transition-all cursor-pointer group flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-2.5">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-white border border-slate-200 flex items-center justify-center font-bold text-slate-700 text-xs overflow-hidden shrink-0 shadow-2xs group-hover:scale-105 transition-transform">
                      {lead.avatar ? (
                        <img src={lead.avatar} alt={lead.name} className="w-full h-full object-cover" />
                      ) : (
                        lead.initials
                      )}
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-slate-900 group-hover:text-blue-600 transition-colors flex items-center gap-1.5">
                        {lead.name}
                      </h3>
                      <p className="text-xs font-medium text-slate-500 truncate max-w-[200px]">{lead.title}</p>
                    </div>
                  </div>

                  <div className="text-right shrink-0">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-700 border border-blue-100">
                      {lead.intentScore}% Score
                    </span>
                  </div>
                </div>

                <div className="bg-white p-2.5 rounded-lg border border-slate-100 mt-2 text-xs space-y-1.5">
                  <div className="flex items-center justify-between text-slate-600 font-medium">
                    <span className="flex items-center gap-1 font-semibold text-slate-900">
                      <Building2 className="w-3 h-3 text-slate-400" /> {lead.company}
                    </span>
                    <span className="text-[11px] text-slate-500">{lead.industry}</span>
                  </div>
                  <div className="text-[11px] text-blue-700 font-medium bg-blue-50/60 px-2 py-1 rounded">
                    Sinal: <span className="font-semibold">{lead.intentTopic}</span>
                  </div>
                </div>
              </div>

              <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[11px]">
                <EvidenceBadge status={lead.emailEvidenceStatus} compact />
                <span className="text-slate-400 group-hover:text-blue-600 font-bold flex items-center gap-0.5">
                  Ver detalhes <ArrowRight className="w-3 h-3" />
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
