// Хуки для загрузки security-событий и управления блокировками IP
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';

export function useSecurityEvents(eventType?: string) {
  return useQuery({
    queryKey: ['securityEvents', eventType],
    queryFn: () => api.securityEvents(eventType),
    refetchInterval: 10000,
  });
}

export function useBlockedIPs() {
  return useQuery({
    queryKey: ['blockedIPs'],
    queryFn: api.blockedIPs,
    refetchInterval: 10000,
  });
}

export function useBlockIP() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ip, reason, duration }: { ip: string; reason: string; duration?: number }) =>
      api.blockIP(ip, reason, duration),
    onSuccess: () => {
      // После ручного блока нам важно сразу обновить и список блокировок, и ленту событий.
      qc.invalidateQueries({ queryKey: ['blockedIPs'] });
      qc.invalidateQueries({ queryKey: ['securityEvents'] });
    },
  });
}

export function useUnblockIP() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ip: string) => api.unblockIP(ip),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['blockedIPs'] });
    },
  });
}
