// Хуки для загрузки метрик с автообновлением
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

export function useMetrics() {
  return useQuery({ queryKey: ['metrics'], queryFn: api.metrics, refetchInterval: 5000 });
}

export function useMetricsHistory(period: string = '1h') {
  return useQuery({
    queryKey: ['metricsHistory', period],
    queryFn: () => api.metricsHistory(period),
    refetchInterval: 30000,
  });
}
