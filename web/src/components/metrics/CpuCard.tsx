// - Карточка CPU с цветовой индикацией нагрузки
import { Card } from '../ui/Card';
import { t } from '../../lib/i18n';

interface Props { value: number }

export function CpuCard({ value }: Props) {
  const color = value > 80 ? 'var(--color-accent-red)' : value > 60 ? 'var(--color-accent-yellow)' : 'var(--color-accent-blue)';
  return (
    <Card title={t.dashboard.cpu}>
      <div className="text-2xl font-bold" style={{ color }}>{value.toFixed(1)}%</div>
      <div className="mt-2 h-1.5 rounded-full bg-border/50" role="progressbar" aria-valuenow={value} aria-valuemax={100}>
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(value, 100)}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)` }} />
      </div>
    </Card>
  );
}
