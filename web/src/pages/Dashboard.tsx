// - Главная страница: метрики, графики, сервисы, последние события
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useMetrics, useMetricsHistory } from '../hooks/useMetrics';
import { useWebSocket } from '../hooks/useWebSocket';
import { CpuCard } from '../components/metrics/CpuCard';
import { RamCard } from '../components/metrics/RamCard';
import { DiskCard } from '../components/metrics/DiskCard';
import { NetworkCard } from '../components/metrics/NetworkCard';
import { MetricChart } from '../components/metrics/MetricChart';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { t } from '../lib/i18n';

export function Dashboard() {
  useWebSocket();
  const { data: metrics, isError: metricsError } = useMetrics();
  const { data: history, isError: historyError } = useMetricsHistory('1h');
  const { data: services, isError: servicesError } = useQuery({ queryKey: ['services'], queryFn: api.services, refetchInterval: 10000 });
  const { data: events, isError: eventsError } = useQuery({ queryKey: ['securityEvents', undefined], queryFn: () => api.securityEvents(), refetchInterval: 10000 });

  return (
    <div className="space-y-6">
      {/* - Карточки текущих метрик */}
      {metricsError && <div className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
      <div className="grid grid-cols-4 gap-4">
        <CpuCard value={metrics?.cpu_total ?? 0} />
        <RamCard used={metrics?.ram_used ?? 0} total={metrics?.ram_total ?? 1} />
        <DiskCard disk={metrics?.disk ?? '[]'} />
        <NetworkCard rx={metrics?.network_rx ?? 0} tx={metrics?.network_tx ?? 0} />
      </div>

      {/* - Графики истории метрик */}
      {historyError && <div className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <MetricChart data={history ?? []} dataKey="cpu_total" color="#38bdf8" label={t.dashboard.cpuHistory} />
        </Card>
        <Card>
          <MetricChart data={history ?? []} dataKey="ram_used" color="#a78bfa" label={t.dashboard.ramHistory} />
        </Card>
      </div>

      {/* - Сервисы и последние события */}
      <div className="grid grid-cols-2 gap-4">
        <Card title={t.dashboard.services}>
          {servicesError && <div className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
          <div className="space-y-2">
            {(services ?? []).slice(0, 8).map((svc) => (
              <div key={svc.name} className="flex justify-between items-center text-sm">
                <span>{svc.name}</span>
                <Badge variant="status" value={svc.status} />
              </div>
            ))}
            {(!services || services.length === 0) && !servicesError && (
              <div className="text-sm text-text-secondary">{t.dashboard.noServices}</div>
            )}
          </div>
        </Card>
        <Card title={t.dashboard.recentEvents}>
          {eventsError && <div className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
          <div className="space-y-2">
            {(events ?? []).slice(0, 5).map((evt) => (
              <div key={evt.id} className="flex justify-between items-center text-sm">
                <div className="flex items-center gap-2">
                  <Badge variant="severity" value={evt.severity} />
                  <span className="text-text-secondary">{evt.type}</span>
                </div>
                <span className="text-xs text-text-secondary">{evt.source_ip}</span>
              </div>
            ))}
            {(!events || events.length === 0) && !eventsError && (
              <div className="text-sm text-text-secondary">{t.dashboard.noEvents}</div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
