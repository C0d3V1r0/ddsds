// - Бейдж для отображения severity и status с цветовой кодировкой
import { t } from '../../lib/i18n';

const severityColors: Record<string, string> = {
  low: 'bg-blue-500/15 text-blue-400',
  medium: 'bg-yellow-500/15 text-yellow-400',
  high: 'bg-red-500/15 text-red-400',
  critical: 'bg-red-600/20 text-red-300 animate-pulse',
};

const statusColors: Record<string, string> = {
  running: 'bg-green-500/15 text-green-400',
  stopped: 'bg-gray-500/15 text-gray-400',
  failed: 'bg-red-500/15 text-red-400',
  pending: 'bg-yellow-500/15 text-yellow-300',
};

const FALLBACK_COLOR = 'bg-gray-500/15 text-gray-400';

interface BadgeProps {
  variant: 'severity' | 'status';
  value: string;
}

export function Badge({ variant, value }: BadgeProps) {
  const colorMap = variant === 'severity' ? severityColors : statusColors;
  const colors = colorMap[value] || FALLBACK_COLOR;
  const statusLabels: Record<string, string> = {
    running: t.status.running,
    stopped: t.status.stopped,
    failed: t.status.failed,
    pending: t.status.pending,
  };
  const severityLabels: Record<string, string> = {
    low: t.severity.low,
    medium: t.severity.medium,
    high: t.severity.high,
    critical: t.severity.critical,
  };
  const label = variant === 'status'
    ? (statusLabels[value] || value)
    : (severityLabels[value] || value);

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
      {label}
    </span>
  );
}
