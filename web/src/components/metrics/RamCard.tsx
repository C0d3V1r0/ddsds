// - Карточка RAM с отображением использования в ГБ
import { Card } from '../ui/Card';
import { t } from '../../lib/i18n';
import { formatBytes } from '../../lib/format';

interface Props { used: number; total: number }

export function RamCard({ used, total }: Props) {
  const percent = total > 0 ? (used / total) * 100 : 0;
  const color = percent > 80 ? 'var(--color-accent-red)' : percent > 60 ? 'var(--color-accent-yellow)' : 'var(--color-accent-purple)';
  return (
    <Card title={t.dashboard.ram} testId="metric-ram-card">
      <div data-testid="metric-ram-value" className="text-2xl font-bold" style={{ color }}>{percent.toFixed(1)}%</div>
      <div data-testid="metric-ram-bytes" className="text-xs text-text-secondary mt-1">{formatBytes(used)} / {formatBytes(total)}</div>
      <div className="mt-2 h-1.5 rounded-full bg-border/50" role="progressbar" aria-valuenow={percent} aria-valuemax={100}>
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(percent, 100)}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)` }} />
      </div>
    </Card>
  );
}
