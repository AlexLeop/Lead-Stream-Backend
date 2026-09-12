import type { LucideIcon } from 'lucide-react';
import {
  BadgeCheck,
  CircleHelp,
  CircleSlash2,
  Eye,
  FlaskConical,
  TriangleAlert,
  XCircle,
} from 'lucide-react';
import type { EvidenceStatus } from './types';

export interface EvidencePresentation {
  label: string;
  description: string;
  className: string;
  icon: LucideIcon;
}

export const evidencePresentation: Record<EvidenceStatus, EvidencePresentation> = {
  ABSENT: {
    label: 'Não encontrado',
    description: 'Nenhuma evidência disponível.',
    className: 'border-slate-200 bg-slate-50 text-slate-700',
    icon: CircleSlash2,
  },
  OBSERVED: {
    label: 'Observado',
    description: 'Valor visto em uma fonte identificada.',
    className: 'border-blue-200 bg-blue-50 text-blue-800',
    icon: Eye,
  },
  INFERRED: {
    label: 'Inferido',
    description: 'Valor derivado por regra; requer confirmação.',
    className: 'border-amber-200 bg-amber-50 text-amber-900',
    icon: CircleHelp,
  },
  TECHNICALLY_VALIDATED: {
    label: 'Validado tecnicamente',
    description: 'Um teste técnico específico passou; não prova posse ou identidade.',
    className: 'border-cyan-200 bg-cyan-50 text-cyan-900',
    icon: FlaskConical,
  },
  CONFIRMED: {
    label: 'Confirmado',
    description: 'Evidências suficientes corroboram valor e vínculo.',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    icon: BadgeCheck,
  },
  CONFLICTING: {
    label: 'Conflitante',
    description: 'Fontes relevantes discordam; requer revisão.',
    className: 'border-orange-200 bg-orange-50 text-orange-900',
    icon: TriangleAlert,
  },
  REJECTED: {
    label: 'Rejeitado',
    description: 'Evidência ou teste invalida o valor.',
    className: 'border-red-200 bg-red-50 text-red-800',
    icon: XCircle,
  },
};
