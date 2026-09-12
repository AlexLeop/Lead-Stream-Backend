import type { EvidenceStatus } from '../types';
import { evidencePresentation } from '../evidence';

interface EvidenceBadgeProps {
  status: EvidenceStatus;
  compact?: boolean;
  showDescription?: boolean;
  className?: string;
}

export default function EvidenceBadge({
  status,
  compact = false,
  showDescription = false,
  className = '',
}: EvidenceBadgeProps) {
  const presentation = evidencePresentation[status];
  const Icon = presentation.icon;
  const accessibleDescription = `${presentation.label}. ${presentation.description}`;

  if (showDescription) {
    return (
      <span
        className={`inline-flex max-w-[70ch] items-start gap-2 rounded-xl border px-3 py-2 text-xs font-semibold leading-5 ${presentation.className} ${className}`}
        aria-label={accessibleDescription}
        title={presentation.description}
      >
        <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>
          <span className="block">{presentation.label}</span>
          <span className="block font-normal opacity-80">{presentation.description}</span>
        </span>
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-semibold ${
        compact ? 'px-2 py-0.5 text-xs' : 'px-2.5 py-1 text-xs'
      } ${presentation.className} ${className}`}
      aria-label={accessibleDescription}
      title={presentation.description}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span>{presentation.label}</span>
    </span>
  );
}
