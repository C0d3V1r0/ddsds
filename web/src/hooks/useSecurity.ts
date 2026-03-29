// Хуки для загрузки security-событий и управления блокировками IP
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';

const SECURITY_REFRESH_MS = 10_000;

function invalidateSecurityQueries(qc: ReturnType<typeof useQueryClient>, includeBlocked = false) {
  if (includeBlocked) qc.invalidateQueries({ queryKey: ['blockedIPs'] });
  qc.invalidateQueries({ queryKey: ['securityEvents'] });
  qc.invalidateQueries({ queryKey: ['securityIncidents'] });
}

export function useSecurityEvents(eventType?: string, sourceIp?: string, limit = 100) {
  return useQuery({
    queryKey: ['securityEvents', eventType, sourceIp, limit],
    queryFn: () => api.securityEvents(eventType, sourceIp, limit),
    refetchInterval: SECURITY_REFRESH_MS,
  });
}

export function useSecurityIncidents(eventType?: string) {
  return useQuery({
    queryKey: ['securityIncidents', eventType],
    queryFn: () => api.securityIncidents(eventType),
    refetchInterval: SECURITY_REFRESH_MS,
  });
}

export function useSecurityIncidentDetail(incidentId?: string) {
  return useQuery({
    queryKey: ['securityIncidentDetail', incidentId],
    queryFn: () => api.securityIncidentDetail(incidentId || ''),
    enabled: !!incidentId,
    refetchInterval: SECURITY_REFRESH_MS,
  });
}

export function useIncidentNotes(incidentId?: string, limit = 20) {
  return useQuery({
    queryKey: ['incidentNotes', incidentId, limit],
    queryFn: () => api.securityIncidentNotes(incidentId || '', limit),
    enabled: !!incidentId,
    refetchInterval: SECURITY_REFRESH_MS,
  });
}

export function useSecurityAudit(traceId?: string) {
  return useQuery({
    queryKey: ['securityAudit', traceId],
    queryFn: () => api.securityAudit(traceId),
    refetchInterval: SECURITY_REFRESH_MS,
  });
}

export function useBlockedIPs() {
  return useQuery({
    queryKey: ['blockedIPs'],
    queryFn: api.blockedIPs,
    refetchInterval: SECURITY_REFRESH_MS,
  });
}

export function useBlockIP() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ ip, reason, duration }: { ip: string; reason: string; duration?: number }) =>
      api.blockIP(ip, reason, duration),
    onSuccess: () => {
      // После ручного блока нам важно сразу обновить и список блокировок, и ленту событий.
      invalidateSecurityQueries(qc, true);
    },
  });
}

export function useUnblockIP() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ip: string) => api.unblockIP(ip),
    onSuccess: () => {
      invalidateSecurityQueries(qc, true);
    },
  });
}

export function useUpdateIncidentStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ incidentId, status }: { incidentId: string; status: 'new' | 'investigating' | 'resolved' }) =>
      api.updateSecurityIncidentStatus(incidentId, status),
    onSuccess: (_, variables) => {
      invalidateSecurityQueries(qc, true);
      qc.invalidateQueries({ queryKey: ['securityIncidentDetail', variables.incidentId] });
      qc.invalidateQueries({ queryKey: ['incidentNotes', variables.incidentId] });
    },
  });
}

export function useAddIncidentNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ incidentId, note }: { incidentId: string; note: string }) =>
      api.addSecurityIncidentNote(incidentId, note),
    onSuccess: (_, variables) => {
      qc.invalidateQueries({ queryKey: ['incidentNotes', variables.incidentId] });
      qc.invalidateQueries({ queryKey: ['securityIncidents'] });
      qc.invalidateQueries({ queryKey: ['securityIncidentDetail', variables.incidentId] });
    },
  });
}
