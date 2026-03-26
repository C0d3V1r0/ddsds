// - Карточка Network с форматированием байт/с
import { Card } from '../ui/Card';
import { t } from '../../lib/i18n';
import { formatBytes } from '../../lib/format';

interface Props { rx: number; tx: number }

export function NetworkCard({ rx, tx }: Props) {
  return (
    <Card title={t.dashboard.network} testId="metric-network-card">
      <div className="flex gap-4">
        <div>
          <div className="text-xs text-text-secondary">{t.dashboard.incomingTraffic}</div>
          <div data-testid="metric-network-rx" className="text-lg font-bold text-accent-green">{formatBytes(rx, { perSecond: true })}</div>
        </div>
        <div>
          <div className="text-xs text-text-secondary">{t.dashboard.outgoingTraffic}</div>
          <div data-testid="metric-network-tx" className="text-lg font-bold text-accent-blue">{formatBytes(tx, { perSecond: true })}</div>
        </div>
      </div>
    </Card>
  );
}
