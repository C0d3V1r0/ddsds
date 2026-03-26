// - Карточка RAM с отображением использования в ГБ
import { Card } from '../ui/Card';
import { t } from '../../lib/i18n';

interface Props { used: number; total: number }

export function RamCard({ used, total }: Props) {
  const percent = total > 0 ? (used / total) * 100 : 0;
  const color = percent > 80 ? 'var(--color-accent-red)' : percent > 60 ? 'var(--color-accent-yellow)' : 'var(--color-accent-purple)';
  const usedGB = (used / 1024 / 1024 / 1024).toFixed(1);
  const totalGB = (total / 1024 / 1024 / 1024).toFixed(1);
  return (
    <Card title={t.dashboard.ram}>
      <div className="text-2xl font-bold" style={{ color }}>{percent.toFixed(1)}%</div>
      <div className="text-xs text-text-secondary mt-1">{usedGB} / {totalGB} ГБ</div>
      <div className="mt-2 h-1.5 rounded-full bg-border/50" role="progressbar" aria-valuenow={percent} aria-valuemax={100}>
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(percent, 100)}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)` }} />
      </div>
    </Card>
  );
}
