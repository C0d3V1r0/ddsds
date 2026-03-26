// - Карточка Network с форматированием байт/с
import { Card } from '../ui/Card';
import { t } from '../../lib/i18n';

interface Props { rx: number; tx: number }

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б/с`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ/с`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ/с`;
}

export function NetworkCard({ rx, tx }: Props) {
  return (
    <Card title={t.dashboard.network} testId="metric-network-card">
      <div className="flex gap-4">
        <div>
          <div className="text-xs text-text-secondary">RX</div>
          <div data-testid="metric-network-rx" className="text-lg font-bold text-accent-green">{formatBytes(rx)}</div>
        </div>
        <div>
          <div className="text-xs text-text-secondary">TX</div>
          <div data-testid="metric-network-tx" className="text-lg font-bold text-accent-blue">{formatBytes(tx)}</div>
        </div>
      </div>
    </Card>
  );
}
