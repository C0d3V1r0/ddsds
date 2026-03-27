// Хуки для загрузки метрик с автообновлением
import { useQuery } from '@tanstack/react-query';
import { api } from '../lib/api';

export function useMetrics() {
  // Текущие метрики нужны почти на каждом экране, поэтому держим короткий polling.
  return useQuery({ queryKey: ['metrics'], queryFn: api.metrics, refetchInterval: 5000 });
}

export function useMetricsHistory(period: string = '1h') {
  return useQuery({
    // История меняется заметно реже, здесь можно опрашивать спокойнее.
    queryKey: ['metricsHistory', period],
    queryFn: () => api.metricsHistory(period),
    refetchInterval: 30000,
  });
}
