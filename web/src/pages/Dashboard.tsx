// Главная страница: метрики, графики, сервисы, последние события
import { lazy, Suspense } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useMetrics, useMetricsHistory } from '../hooks/useMetrics';
import { useWebSocket } from '../hooks/useWebSocket';
import { CpuCard } from '../components/metrics/CpuCard';
import { RamCard } from '../components/metrics/RamCard';
import { DiskCard } from '../components/metrics/DiskCard';
import { NetworkCard } from '../components/metrics/NetworkCard';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { LoadingBlock } from '../components/ui/StateBlock';
import { t } from '../lib/i18n';

const MetricChart = lazy(async () => import('../components/metrics/MetricChart').then((module) => ({ default: module.MetricChart })));

export function Dashboard() {
  useWebSocket();
  const { data: metrics, isError: metricsError } = useMetrics();
  const { data: history, isError: historyError } = useMetricsHistory('1h');
  const { data: services, isError: servicesError } = useQuery({ queryKey: ['services'], queryFn: api.services, refetchInterval: 10000 });
  const { data: events, isError: eventsError } = useQuery({ queryKey: ['securityEvents', undefined], queryFn: () => api.securityEvents(), refetchInterval: 10000 });
  const hasCriticalIssue = metricsError || historyError || servicesError || eventsError;

  return (
    <div data-testid="page-dashboard" className="space-y-6">
      <div className="flex items-start justify-between gap-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">{t.dashboard.title}</h1>
          <p className="mt-1 text-sm text-text-secondary">{t.dashboard.summary}</p>
        </div>
        <Card testId="dashboard-system-state-card" className="min-w-72">
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">{t.dashboard.systemState}</div>
          <div className={`text-sm font-medium ${hasCriticalIssue ? 'text-accent-yellow' : 'text-accent-green'}`}>
            {hasCriticalIssue ? t.dashboard.systemAttention : t.dashboard.systemHealthy}
          </div>
          <div className="mt-1 text-xs text-text-secondary">{t.dashboard.systemStateHint}</div>
        </Card>
      </div>

      {/* Карточки текущих метрик */}
      {metricsError && <div data-testid="dashboard-metrics-error" className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
      <div className="grid grid-cols-4 gap-4">
        <CpuCard value={metrics?.cpu_total ?? 0} />
        <RamCard used={metrics?.ram_used ?? 0} total={metrics?.ram_total ?? 1} />
        <DiskCard disk={metrics?.disk ?? '[]'} />
        <NetworkCard rx={metrics?.network_rx ?? 0} tx={metrics?.network_tx ?? 0} />
      </div>

      {/* Графики истории метрик */}
      {historyError && <div data-testid="dashboard-history-error" className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
      <div className="grid grid-cols-2 gap-4">
        <Card testId="dashboard-cpu-history-card">
          <Suspense fallback={<LoadingBlock testId="dashboard-cpu-history-loading" />}>
            <MetricChart data={history ?? []} dataKey="cpu_total" color="#38bdf8" label={t.dashboard.cpuHistory} />
          </Suspense>
        </Card>
        <Card testId="dashboard-ram-history-card">
          <Suspense fallback={<LoadingBlock testId="dashboard-ram-history-loading" />}>
            <MetricChart data={history ?? []} dataKey="ram_used" color="#a78bfa" label={t.dashboard.ramHistory} />
          </Suspense>
        </Card>
      </div>

      {/* Сервисы и последние события */}
      <div className="grid grid-cols-2 gap-4">
        <Card title={t.dashboard.services} testId="dashboard-services-card">
          {servicesError && <div data-testid="dashboard-services-error" className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
          <div data-testid="dashboard-services-list" className="space-y-2">
            {(services ?? []).slice(0, 8).map((svc) => (
              <div key={svc.name} className="flex justify-between items-center text-sm">
                <span>{svc.name}</span>
                <Badge variant="status" value={svc.status} />
              </div>
            ))}
            {(!services || services.length === 0) && !servicesError && (
              <div className="text-sm text-text-secondary">
                <div>{t.dashboard.noServices}</div>
                <div className="mt-1 text-xs text-text-secondary/80">{t.common.noDataHint}</div>
              </div>
            )}
          </div>
        </Card>
        <Card title={t.dashboard.recentEvents} testId="dashboard-events-card">
          {eventsError && <div data-testid="dashboard-events-error" className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
          <div data-testid="dashboard-events-list" className="space-y-2">
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
              <div className="text-sm text-text-secondary">
                <div>{t.dashboard.noEvents}</div>
                <div className="mt-1 text-xs text-text-secondary/80">{t.common.noDataHint}</div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
