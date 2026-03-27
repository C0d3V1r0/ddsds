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
import { formatDateTime, formatEventDescription, formatEventType, formatRelativeAge } from '../lib/format';
import { useStore } from '../stores/store';

const MetricChart = lazy(async () => import('../components/metrics/MetricChart').then((module) => ({ default: module.MetricChart })));

export function Dashboard() {
  useWebSocket();
  const locale = useStore((state) => state.locale);
  const { data: metrics, isError: metricsError } = useMetrics();
  const { data: history, isError: historyError } = useMetricsHistory('1h');
  const { data: services, isError: servicesError } = useQuery({ queryKey: ['services'], queryFn: api.services, refetchInterval: 10000 });
  const { data: events, isError: eventsError } = useQuery({ queryKey: ['securityEvents', undefined], queryFn: () => api.securityEvents(), refetchInterval: 10000 });
  const hasCriticalIssue = metricsError || historyError || servicesError || eventsError;
  const lastMetricsTimestamp = metrics?.timestamp ?? history?.[history.length - 1]?.timestamp ?? null;

  return (
    <div data-testid="page-dashboard" className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-text-primary">{t.dashboard.title}</h1>
          <p className="mt-1 text-sm text-text-secondary">{t.dashboard.summary}</p>
        </div>
        <Card testId="dashboard-system-state-card" className="w-full xl:w-[26rem]">
          <div className="text-xs uppercase tracking-wider text-text-secondary mb-2">{t.dashboard.systemState}</div>
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${hasCriticalIssue ? 'bg-accent-yellow' : 'bg-accent-green'}`}
              aria-hidden="true"
            />
            <div className={`text-sm font-medium ${hasCriticalIssue ? 'text-accent-yellow' : 'text-accent-green'}`}>
              {hasCriticalIssue ? t.dashboard.systemAttention : t.dashboard.systemHealthy}
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-text-secondary">{t.dashboard.lastUpdate}</div>
              <div className="mt-1 text-sm text-text-primary">{lastMetricsTimestamp ? formatDateTime(lastMetricsTimestamp) : '—'}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-text-secondary">{t.dashboard.dataFreshness}</div>
              <div className="mt-1 text-sm text-text-primary">{formatRelativeAge(lastMetricsTimestamp)}</div>
            </div>
          </div>
        </Card>
      </div>

      {/* Карточки текущих метрик */}
      {metricsError && <div data-testid="dashboard-metrics-error" className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <CpuCard value={metrics?.cpu_total ?? 0} />
        <RamCard used={metrics?.ram_used ?? 0} total={metrics?.ram_total ?? 1} />
        <DiskCard disk={metrics?.disk ?? '[]'} />
        <NetworkCard rx={metrics?.network_rx ?? 0} tx={metrics?.network_tx ?? 0} />
      </div>

      {/* Графики истории метрик */}
      {historyError && <div data-testid="dashboard-history-error" className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
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
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
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
              <div key={evt.id} className="flex flex-col gap-2 text-sm sm:flex-row sm:items-start sm:justify-between">
                <div className="flex items-start gap-2 min-w-0">
                  <Badge variant="severity" value={evt.severity} />
                  <div className="min-w-0">
                    <div className="text-text-secondary">{formatEventType(evt.type)}</div>
                    {evt.description && (
                      <div className="mt-0.5 text-xs text-text-secondary/70">{formatEventDescription(evt.description, evt.type)}</div>
                    )}
                  </div>
                </div>
                <div className="flex items-center justify-between gap-3 sm:block sm:text-right">
                  <span className="text-xs text-text-secondary shrink-0">{evt.source_ip || (locale === 'ru' ? 'локально' : 'local')}</span>
                  <div className="mt-0 sm:mt-1 text-[11px] text-text-secondary/70">{formatRelativeAge(evt.timestamp)}</div>
                </div>
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
