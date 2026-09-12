import { useState } from 'react';
import { ArrowRight, CheckCircle2, Database, FileSpreadsheet, PlugZap, Search, X } from 'lucide-react';

interface InteractiveDemoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGoToApp: () => void;
}

const steps = [
  {
    title: 'Importe sua base',
    description: 'Envie um CSV com empresas e contatos. O sistema reconhece os cabeçalhos e nunca inventa valores ausentes.',
    icon: FileSpreadsheet,
    points: ['CSV com até 10.000 linhas', 'Normalização de domínio, CNPJ e e-mail', 'Registros incompletos continuam explícitos'],
  },
  {
    title: 'Organize e deduplique',
    description: 'Empresas e contatos são resolvidos por identificadores estáveis e gravados com segurança.',
    icon: Database,
    points: ['Empresas separadas de contatos', 'Deduplicação por CNPJ, domínio e e-mail', 'Bases e listas prontas para uso'],
  },
  {
    title: 'Consulte e ative',
    description: 'Pesquise empresas e contatos, complete perfis e organize listas para sua equipe comercial.',
    icon: PlugZap,
    points: ['Pesquisa por pessoa, empresa, e-mail ou domínio', 'Exportação CSV a partir da base real', 'Integração CRM em preparação'],
  },
];

export default function InteractiveDemoModal({ isOpen, onClose, onGoToApp }: InteractiveDemoModalProps) {
  const [step, setStep] = useState(0);
  if (!isOpen) return null;

  const current = steps[step];
  const Icon = current.icon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <div className="w-full max-w-2xl overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 p-6">
          <div>
            <h2 id="tour-title" className="text-lg font-bold text-slate-900">Como a base operacional funciona</h2>
            <p className="mt-1 text-xs text-slate-600">Um tour pelo fluxo real implementado no projeto</p>
          </div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-200" aria-label="Fechar">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="grid grid-cols-3 border-b border-slate-200">
          {steps.map((item, index) => (
            <button
              key={item.title}
              onClick={() => setStep(index)}
              className={`px-3 py-3 text-xs font-bold ${index === step ? 'bg-blue-50 text-blue-700' : 'text-slate-500 hover:bg-slate-50'}`}
            >
              {index + 1}. {index === 0 ? 'Importar' : index === 1 ? 'Organizar' : 'Ativar'}
            </button>
          ))}
        </div>

        <div className="p-7">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white">
            <Icon className="h-6 w-6" />
          </div>
          <h3 className="mt-5 text-2xl font-extrabold text-slate-900">{current.title}</h3>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-slate-600">{current.description}</p>
          <div className="mt-6 space-y-3">
            {current.points.map((point) => (
              <div key={point} className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-800">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" /> {point}
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 p-4">
          <button
            onClick={() => setStep((currentStep) => Math.max(0, currentStep - 1))}
            disabled={step === 0}
            className="px-3 py-2 text-xs font-bold text-slate-600 disabled:opacity-0"
          >
            Etapa anterior
          </button>
          {step < steps.length - 1 ? (
            <button onClick={() => setStep((currentStep) => currentStep + 1)} className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-bold text-white">
              Próxima etapa <ArrowRight className="h-4 w-4" />
            </button>
          ) : (
            <button
              onClick={() => {
                onClose();
                onGoToApp();
              }}
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-bold text-white"
            >
              Abrir plataforma <Search className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
