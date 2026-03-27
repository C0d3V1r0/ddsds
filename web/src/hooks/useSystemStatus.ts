// Периодический опрос health API и синхронизация статуса агента в стор
import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';

import { api } from '../lib/api';
import { useStore } from '../stores/store';

export function useSystemStatus() {
  const setAgentStatus = useStore((state) => state.setAgentStatus);

  const query = useQuery({
    // health — дешёвый эндпоинт, поэтому именно он синхронизирует глобальный agent status.
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (!query.data) return;
    setAgentStatus(query.data.agent === 'connected' ? 'connected' : 'disconnected');
  }, [query.data, setAgentStatus]);

  return query;
}
