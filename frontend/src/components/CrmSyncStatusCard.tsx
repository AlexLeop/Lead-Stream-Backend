import { ArrowUpRight, Clock3, PlugZap } from 'lucide-react';

interface CrmSyncStatusCardProps {
  onNavigateLists: () => void;
}

export default function CrmSyncStatusCard({ onNavigateLists }: CrmSyncStatusCardProps) {
  return (
    <div className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
      <div>
        <div className="mb-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-blue-50 text-blue-600">
              <PlugZap className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Integração CRM em preparação</h2>
              <p className="text-xs text-slate-500">Nenhum conector externo está ativo neste momento</p>
            </div>
          </div>
          <button
            onClick={onNavigateLists}
            className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-bold text-slate-700 hover:bg-slate-200"
          >
            Gerenciar
          </button>
        </div>

        <div className="flex items-start gap-3 rounded-xl bg-slate-50 p-4">
          <Clock3 className="mt-0.5 h-5 w-5 shrink-0 text-slate-500" aria-hidden="true" />
          <div>
            <div className="text-sm font-bold text-slate-900">Exportação CSV continua disponível</div>
            <p className="mt-1 text-xs leading-relaxed text-slate-600">
              As listas podem ser exportadas manualmente. O envio direto será habilitado somente após existir confirmação real do CRM externo.
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
        <span className="flex items-center gap-1.5 font-semibold text-slate-700">
          <PlugZap className="h-3.5 w-3.5 text-slate-500" /> 0 conexões externas ativas
        </span>
        <button onClick={onNavigateLists} className="flex items-center gap-1 font-bold text-blue-600 hover:underline">
          Ver listas <ArrowUpRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
