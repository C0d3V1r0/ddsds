// Страница безопасности: события, заблокированные IP, управление блокировками
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSecurityEvents, useSecurityIncidents, useBlockedIPs, useBlockIP, useUnblockIP, useSecurityAudit } from '../hooks/useSecurity';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Table } from '../components/ui/Table';
import { ErrorBlock, LoadingBlock, StateBlock } from '../components/ui/StateBlock';
import { t } from '../lib/i18n';
import { formatActionTaken, formatAuditStage, formatAuditStatus, formatAuditSummary, formatConfidence, formatDateTime, formatEventDescription, formatEventExplanation, formatEventSource, formatEventType, formatIncidentStatus, formatRecommendedAction, formatSignalSource } from '../lib/format';
import type { SecurityEvent, SecurityIncident, BlockedIP, ResponseAuditEntry } from '../types';

const EVENT_TYPES = ['ssh_brute_force', 'sqli', 'xss', 'path_traversal', 'port_scan', 'anomaly'];

// Валидация IPv4 и IPv6 адресов
const IP_RE = /^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-fA-F:]+$/;

export function Security() {
  const navigate = useNavigate();
  const [filterType, setFilterType] = useState('');
  const [blockIp, setBlockIp] = useState('');
  const [blockReason, setBlockReason] = useState('');
  const [selectedTraceId, setSelectedTraceId] = useState('');
  const { data: incidents, isError: incidentsError, isLoading: incidentsLoading } = useSecurityIncidents(filterType || undefined);
  const { data: events, isError: eventsError, isLoading: eventsLoading } = useSecurityEvents(filterType || undefined);
  const { data: auditEntries, isError: auditError, isLoading: auditLoading } = useSecurityAudit(selectedTraceId || undefined);
  const { data: blocked, isError: blockedError, isLoading: blockedLoading } = useBlockedIPs();
  const blockMutation = useBlockIP();
  const unblockMutation = useUnblockIP();
  const normalizedIp = blockIp.trim();
  const isIpValid = !normalizedIp || IP_RE.test(normalizedIp);

  const openRelatedLogs = (params: { sourceIp?: string; type: string; timestamp: number }) => {
    const query = new URLSearchParams();
    if (params.sourceIp) query.set('ip', params.sourceIp);
    query.set('event_type', params.type);
    const from = new Date((params.timestamp - 300) * 1000).toISOString().slice(0, 16);
    const to = new Date((params.timestamp + 300) * 1000).toISOString().slice(0, 16);
    query.set('from', from);
    query.set('to', to);
    if (params.type === 'ssh_brute_force') query.set('source', 'auth');
    if (['sqli', 'xss', 'path_traversal'].includes(params.type)) query.set('source', 'nginx');
    navigate(`/logs?${query.toString()}`);
  };

  const eventColumns = [
    { key: 'severity', header: t.security.severity, render: (row: SecurityEvent) => <Badge variant="severity" value={row.severity} /> },
    { key: 'type', header: t.security.type, render: (row: SecurityEvent) => formatEventType(row.type) },
    { key: 'source_ip', header: t.security.sourceIp, render: (row: SecurityEvent) => formatEventSource(row.source_ip) },
    { key: 'signal_source', header: t.security.signalSource, render: (row: SecurityEvent) => formatSignalSource(row.signal_source) },
    { key: 'confidence', header: t.security.confidence, render: (row: SecurityEvent) => formatConfidence(row.confidence) },
    { key: 'description', header: t.security.description, render: (row: SecurityEvent) => (
      <div className="space-y-1">
        <div>{formatEventDescription(row.description, row.type)}</div>
        <div className="text-xs text-text-secondary/80">{formatEventExplanation(row)}</div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-text-secondary/70">
          <span>{formatRecommendedAction(row.recommended_action)}</span>
          <button
            type="button"
            onClick={() => openRelatedLogs({ sourceIp: row.source_ip, type: row.type, timestamp: row.timestamp })}
            className="text-accent-blue hover:text-blue-300 transition-colors"
          >
            {t.logs.relatedLogs}
          </button>
          {row.trace_id && (
            <button
              type="button"
              onClick={() => setSelectedTraceId(row.trace_id || '')}
              className="text-accent-blue hover:text-blue-300 transition-colors"
            >
              {t.security.responseTrail}
            </button>
          )}
        </div>
      </div>
    )},
    { key: 'action_taken', header: t.security.action, render: (row: SecurityEvent) => formatActionTaken(row.action_taken) },
    { key: 'timestamp', header: t.security.time, render: (row: SecurityEvent) => (
      <span className="text-xs text-text-secondary">{formatDateTime(row.timestamp)}</span>
    )},
  ];

  const blockedColumns = [
    { key: 'ip', header: 'IP' },
    { key: 'reason', header: t.security.reason },
    { key: 'blocked_at', header: t.security.blocked, render: (row: BlockedIP) => (
      <span className="text-xs text-text-secondary">{formatDateTime(row.blocked_at)}</span>
    )},
    { key: 'expires_at', header: t.security.expires, render: (row: BlockedIP) => (
      <span className="text-xs text-text-secondary">{row.expires_at ? formatDateTime(row.expires_at) : t.security.never}</span>
    )},
    { key: 'auto', header: t.security.auto, render: (row: BlockedIP) => (
      <Badge variant="status" value={row.auto ? 'running' : 'stopped'} />
    )},
    { key: 'actions', header: '', render: (row: BlockedIP) => (
      <button
        onClick={() => unblockMutation.mutate(row.ip)}
        className="text-xs text-accent-red hover:text-red-300 focus:text-red-300 transition-colors"
      >
        {t.security.unblock}
      </button>
    )},
  ];

  const handleBlock = () => {
    const ip = blockIp.trim();
    if (!ip || !IP_RE.test(ip)) return;
    blockMutation.mutate({ ip, reason: blockReason.trim() || t.security.manualBlock });
    setBlockIp('');
    setBlockReason('');
  };

  return (
    <div data-testid="page-security" className="space-y-6">
      {/* Фильтр по типу события */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold">{t.security.title}</h1>
          <p className="mt-1 text-sm text-text-secondary">{t.security.summary}</p>
        </div>
        <select
          data-testid="security-event-filter"
          value={filterType}
          onChange={(evt) => setFilterType(evt.target.value)}
          className="bg-bg-card border border-border rounded px-3 py-1.5 text-sm text-text-primary"
          aria-label={t.security.allTypes}
        >
          <option value="">{t.security.allTypes}</option>
          {EVENT_TYPES.map((tp) => (
            <option key={tp} value={tp}>{formatEventType(tp)}</option>
          ))}
        </select>
      </div>

      <Card title={t.security.incidents} testId="security-incidents-card">
        {incidentsLoading ? (
          <LoadingBlock testId="security-incidents-loading" />
        ) : incidentsError ? (
          <ErrorBlock testId="security-incidents-error" />
        ) : !incidents || incidents.length === 0 ? (
          <StateBlock title={t.security.noIncidents} testId="security-incidents-empty" />
        ) : (
          <div className="space-y-3">
            {incidents.map((incident: SecurityIncident) => (
              <div key={incident.id} className="rounded-lg border border-border/60 bg-bg-primary/40 p-3">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="severity" value={incident.severity} />
                      <span className="font-medium text-text-primary">{formatEventType(incident.type)}</span>
                      <span className="text-xs text-text-secondary">{formatIncidentStatus(incident.status)}</span>
                    </div>
                    <div className="mt-1 text-sm text-text-secondary">{incident.summary}</div>
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-text-secondary/80">
                      <span>{formatEventSource(incident.source_ip)}</span>
                      <span>{formatSignalSource(incident.signal_source)}</span>
                      <span>{formatConfidence(incident.confidence)}</span>
                      <span>{t.security.incidentEventsCount(incident.event_count)}</span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-text-secondary/80">
                      <span>{formatRecommendedAction(incident.recommended_action)}</span>
                      <button
                        type="button"
                        onClick={() => openRelatedLogs({ sourceIp: incident.source_ip, type: incident.type, timestamp: incident.last_seen })}
                        className="text-accent-blue hover:text-blue-300 transition-colors"
                      >
                        {t.logs.relatedLogs}
                      </button>
                      {incident.latest_trace_id && (
                        <button
                          type="button"
                          onClick={() => setSelectedTraceId(incident.latest_trace_id || '')}
                          className="text-accent-blue hover:text-blue-300 transition-colors"
                        >
                          {t.security.responseTrail}
                        </button>
                      )}
                    </div>
                  </div>
                  <div className="shrink-0 text-xs text-text-secondary/80 space-y-1">
                    <div>{t.security.incidentFirstSeen}: {formatDateTime(incident.first_seen)}</div>
                    <div>{t.security.incidentLastSeen}: {formatDateTime(incident.last_seen)}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Таблица событий */}
      <Card title={t.security.events} testId="security-events-card">
        {eventsLoading ? (
          <LoadingBlock testId="security-events-loading" />
        ) : eventsError ? (
          <ErrorBlock testId="security-events-error" />
        ) : (
        <Table testId="security-events-table" columns={eventColumns} data={events ?? []} keyField="id" />
        )}
      </Card>

      <Card title={t.security.responseTrail} testId="security-audit-card">
        <div className="mb-4 flex flex-wrap items-center gap-3 text-xs text-text-secondary">
          <span>
            {selectedTraceId ? t.security.auditFiltered(selectedTraceId) : t.security.auditRecent}
          </span>
          {selectedTraceId && (
            <button
              type="button"
              onClick={() => setSelectedTraceId('')}
              className="text-accent-blue hover:text-blue-300 transition-colors"
            >
              {t.security.auditReset}
            </button>
          )}
        </div>
        {auditLoading ? (
          <LoadingBlock testId="security-audit-loading" />
        ) : auditError ? (
          <ErrorBlock testId="security-audit-error" />
        ) : !auditEntries || auditEntries.length === 0 ? (
          <StateBlock title={t.security.auditEmpty} testId="security-audit-empty" />
        ) : (
          <div className="space-y-3">
            {auditEntries.map((entry: ResponseAuditEntry) => (
              <div key={entry.id} className="rounded-lg border border-border/60 bg-bg-primary/40 p-3">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-text-primary">{formatAuditStage(entry.stage)}</span>
                      <span className="text-xs text-text-secondary">{formatAuditStatus(entry.status)}</span>
                    </div>
                    <div className="mt-1 text-sm text-text-secondary">{formatAuditSummary(entry)}</div>
                    <div className="mt-2 text-xs text-text-secondary/80">{entry.trace_id}</div>
                  </div>
                  <div className="shrink-0 text-xs text-text-secondary/80">
                    {formatDateTime(entry.timestamp)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Блокировка IP вручную */}
      <Card title={t.security.blockIp} testId="security-block-card">
        <p className="mb-4 text-sm text-text-secondary">{t.security.blockHint}</p>
        <div className="flex gap-3 items-end">
          <div>
            <label htmlFor="security-block-ip-input" className="text-xs text-text-secondary block mb-1">{t.security.ipAddress}</label>
            <input
              id="security-block-ip-input"
              data-testid="security-block-ip"
              value={blockIp}
              onChange={(evt) => setBlockIp(evt.target.value)}
              placeholder="192.168.1.1"
              className="bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-primary w-48"
              aria-invalid={!isIpValid}
              aria-describedby={!isIpValid ? 'security-block-ip-error' : undefined}
            />
            {!isIpValid && (
              <div id="security-block-ip-error" className="mt-1 text-xs text-accent-red">{t.security.invalidIp}</div>
            )}
          </div>
          <div>
            <label htmlFor="security-block-reason-input" className="text-xs text-text-secondary block mb-1">{t.security.reason}</label>
            <input
              id="security-block-reason-input"
              data-testid="security-block-reason"
              value={blockReason}
              onChange={(evt) => setBlockReason(evt.target.value)}
              placeholder={t.security.manualBlock}
              className="bg-bg-primary border border-border rounded px-3 py-1.5 text-sm text-text-primary w-64"
            />
          </div>
          <button
            type="button"
            data-testid="security-block-submit"
            onClick={handleBlock}
            disabled={!normalizedIp || !isIpValid || blockMutation.isPending}
            className="bg-accent-red/20 text-accent-red hover:bg-accent-red/30 disabled:opacity-50 disabled:cursor-not-allowed px-4 py-1.5 rounded text-sm transition-colors"
            aria-busy={blockMutation.isPending}
          >
            {blockMutation.isPending ? t.common.loading : t.security.block}
          </button>
        </div>
        {(blockMutation.isError || unblockMutation.isError) && (
          <div className="mt-3">
            <StateBlock title={t.security.mutationError} tone="error" />
          </div>
        )}
      </Card>

      {/* Таблица заблокированных IP */}
      <Card title={t.security.blockedIps} testId="security-blocked-card">
        {blockedLoading ? (
          <LoadingBlock testId="security-blocked-loading" />
        ) : blockedError ? (
          <ErrorBlock testId="security-blocked-error" />
        ) : (
          <Table testId="security-blocked-table" columns={blockedColumns} data={blocked ?? []} keyField="id" />
        )}
      </Card>
    </div>
  );
}
