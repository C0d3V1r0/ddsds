// - Карточка Disk с парсингом JSON-строки дисков
import { Card } from '../ui/Card';
import { t } from '../../lib/i18n';

interface Props { disk: string }

export function DiskCard({ disk }: Props) {
  let percent = 0;
  try {
    const disks = JSON.parse(disk || '[]') as Array<{ used: number; total: number }>;
    const main = disks[0];
    if (main && main.total > 0) percent = (main.used / main.total) * 100;
  } catch {
    // - Невалидный JSON — показываем 0%
  }
  const color = percent > 80 ? 'var(--color-accent-red)' : percent > 60 ? 'var(--color-accent-yellow)' : 'var(--color-accent-blue)';
  return (
    <Card title={t.dashboard.disk}>
      <div className="text-2xl font-bold" style={{ color }}>{percent.toFixed(1)}%</div>
      <div className="mt-2 h-1.5 rounded-full bg-border/50" role="progressbar" aria-valuenow={percent} aria-valuemax={100}>
        <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(percent, 100)}%`, background: `linear-gradient(90deg, ${color}, ${color}cc)` }} />
      </div>
    </Card>
  );
}
