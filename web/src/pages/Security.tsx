// Страница безопасности: события, заблокированные IP, управление блокировками
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSecurityEvents, useSecurityIncidents, useSecurityIncidentDetail, useBlockedIPs, useBlockIP, useUnblockIP, useSecurityAudit, useUpdateIncidentStatus, useAddIncidentNote } from '../hooks/useSecurity';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Table } from '../components/ui/Table';
import { ErrorBlock, LoadingBlock, StateBlock } from '../components/ui/StateBlock';
import { t } from '../lib/i18n';
import { formatActionTaken, formatAuditStage, formatAuditStatus, formatAuditSummary, formatBlockedReason, formatConfidence, formatDateTime, formatEventDescription, formatEventExplanation, formatEventSource, formatEventType, formatIncidentResolutionHeadline, formatIncidentStatus, formatRecommendedAction, formatSignalSource } from '../lib/format';
import type { SecurityEvent, SecurityIncident, BlockedIP, ResponseAuditEntry } from '../types';

const EVENT_TYPES = [
  'ssh_brute_force',
  'ssh_user_enum',
  'sqli',
  'xss',
  'path_traversal',
  'command_injection',
  'sensitive_path_probe',
  'scanner_probe',
  'web_login_bruteforce',
  'port_scan',
  'anomaly',
];
const EVENTS_PER_PAGE = 10;

// Валидация IPv4 и IPv6 адресов
const IP_RE = /^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-fA-F:]+$/;

export function Security() {
  const navigate = useNavigate();
  const auditCardRef = useRef<HTMLDivElement | null>(null);
  const [filterType, setFilterType] = useState('');
  const [blockIp, setBlockIp] = useState('');
  const [blockReason, setBlockReason] = useState('');
  const [selectedTraceId, setSelectedTraceId] = useState('');
  const [selectedIncidentId, setSelectedIncidentId] = useState('');
  const [incidentNote, setIncidentNote] = useState('');
  const [eventsPage, setEventsPage] = useState(1);
  const { data: incidents, isError: incidentsError, isLoading: incidentsLoading } = useSecurityIncidents(filterType || undefined);
  const { data: events, isError: eventsError, isLoading: eventsLoading } = useSecurityEvents(filterType || undefined);
  const selectedIncident = (incidents ?? []).find((incident) => incident.id === selectedIncidentId) ?? (incidents?.[0] ?? null);
  const { data: incidentDetail, isError: incidentDetailError, isLoading: incidentDetailLoading } = useSecurityIncidentDetail(selectedIncident?.id);
  const { data: auditEntries, isError: auditError, isLoading: auditLoading } = useSecurityAudit(selectedTraceId || undefined);
  const { data: blocked, isError: blockedError, isLoading: blockedLoading } = useBlockedIPs();
  const blockMutation = useBlockIP();
  const unblockMutation = useUnblockIP();
  const updateIncidentStatusMutation = useUpdateIncidentStatus();
  const addIncidentNoteMutation = useAddIncidentNote();
  const normalizedIp = blockIp.trim();
  const isIpValid = !normalizedIp || IP_RE.test(normalizedIp);

  useEffect(() => {
    if (!selectedTraceId || !auditCardRef.current) return;
    auditCardRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [selectedTraceId]);

  useEffect(() => {
    setEventsPage(1);
  }, [filterType]);

  useEffect(() => {
    if (!incidents?.length) {
      setSelectedIncidentId('');
      return;
    }
    setSelectedIncidentId((current) =>
      current && incidents.some((incident) => incident.id === current) ? current : incidents[0].id,
    );
  }, [incidents]);

  useEffect(() => {
    setIncidentNote('');
  }, [selectedIncidentId]);

  const totalEventPages = Math.max(1, Math.ceil((events?.length ?? 0) / EVENTS_PER_PAGE));
  const pagedEvents = (events ?? []).slice((eventsPage - 1) * EVENTS_PER_PAGE, eventsPage * EVENTS_PER_PAGE);
  const selectedIncidentBlocked = !!selectedIncident?.source_ip && (blocked ?? []).some((row) => row.ip === selectedIncident.source_ip);
  const selectedBlockedRow = incidentDetail?.blocked_ip ?? (!!selectedIncident?.source_ip ? (blocked ?? []).find((row) => row.ip === selectedIncident.source_ip) : undefined);
  const latestIncidentNote = incidentDetail?.notes?.[0];
  const evidencePreview = (incidentDetail?.related_events ?? []).slice(0, 3);

  useEffect(() => {
    setEventsPage((current) => Math.min(current, totalEventPages));
  }, [totalEventPages]);

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
    if (params.type === 'port_scan') query.set('source', 'firewall');
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
            className="cursor-pointer text-accent-blue hover:text-blue-300 underline-offset-2 hover:underline focus:text-blue-300 focus:underline transition-colors"
          >
            {t.logs.relatedLogs}
          </button>
          {row.trace_id && (
            <button
              type="button"
              onClick={() => setSelectedTraceId(row.trace_id || '')}
              className="cursor-pointer text-accent-blue hover:text-blue-300 underline-offset-2 hover:underline focus:text-blue-300 focus:underline transition-colors"
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
    { key: 'reason', header: t.security.reason, render: (row: BlockedIP) => formatBlockedReason(row.reason) },
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

  const handleIncidentStatus = (status: SecurityIncident['status']) => {
    if (!selectedIncident) return;
    updateIncidentStatusMutation.mutate({ incidentId: selectedIncident.id, status });
  };

  const handleAddIncidentNote = () => {
    const note = incidentNote.trim();
    if (!selectedIncident || !note) return;
    addIncidentNoteMutation.mutate(
      { incidentId: selectedIncident.id, note },
      {
        onSuccess: () => setIncidentNote(''),
      },
    );
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
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
            <div className="space-y-3">
              {incidents.map((incident: SecurityIncident) => (
                <button
                  key={incident.id}
                  type="button"
                  onClick={() => setSelectedIncidentId(incident.id)}
                  className={`w-full rounded-lg border p-3 text-left transition-colors ${
                    selectedIncident?.id === incident.id
                      ? 'border-accent-blue bg-bg-card-hover/60'
                      : 'border-border/60 bg-bg-primary/40 hover:bg-bg-card-hover/40'
                  }`}
                >
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
                        {incident.note_count > 0 && <span>{t.security.incidentNotesCount(incident.note_count)}</span>}
                        {incident.repeat_count > 0 && <span>{t.security.incidentRepeatCount(incident.repeat_count)}</span>}
                        {incident.suppressed_count > 0 && <span>{t.security.incidentSuppressedCount(incident.suppressed_count)}</span>}
                      </div>
                    </div>
                    <div className="shrink-0 text-xs text-text-secondary/80 space-y-1">
                      <div>{t.security.incidentFirstSeen}: {formatDateTime(incident.first_seen)}</div>
                      <div>{t.security.incidentLastSeen}: {formatDateTime(incident.last_seen)}</div>
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {selectedIncident && (
              <Card title={t.security.incidentDetails} gradient={false} className="self-start" testId="security-incident-details-card">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="severity" value={selectedIncident.severity} />
                      <span className="font-medium text-text-primary">{formatEventType(selectedIncident.type)}</span>
                      <span className="text-xs text-text-secondary">{formatIncidentStatus(selectedIncident.status)}</span>
                    </div>
                    <div className="text-sm text-text-secondary">{selectedIncident.summary}</div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded border border-border/60 bg-bg-primary/40 p-3">
                      <div className="text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentEvidence}</div>
                      <div className="mt-2 space-y-2 text-sm text-text-secondary">
                        <div>{formatEventSource(selectedIncident.source_ip)}</div>
                        <div>{formatSignalSource(selectedIncident.signal_source)}</div>
                        <div>{formatConfidence(selectedIncident.confidence)}</div>
                        <div>{formatActionTaken(selectedIncident.latest_action_taken || 'logged')}</div>
                      </div>
                    </div>
                    <div className="rounded border border-border/60 bg-bg-primary/40 p-3">
                      <div className="text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentResponseContext}</div>
                      <div className="mt-2 space-y-2 text-sm text-text-secondary">
                        <div>{t.security.incidentRecommendedNextStep}: {formatRecommendedAction(selectedIncident.recommended_action)}</div>
                        <div>{t.security.incidentBlockedState}: {selectedBlockedRow ? t.security.actionAutoBlocked : t.security.actionReviewRequired}</div>
                        {selectedBlockedRow ? (
                          <div>{t.security.incidentBlockedUntil}: {selectedBlockedRow.expires_at ? formatDateTime(selectedBlockedRow.expires_at) : t.security.never}</div>
                        ) : null}
                        <div>{t.security.incidentTraceAvailable}: {selectedIncident.latest_trace_id || t.security.incidentTraceMissing}</div>
                      </div>
                    </div>
                    <div className="rounded border border-border/60 bg-bg-primary/40 p-3">
                      <div className="text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentTimeline}</div>
                      <div className="mt-2 space-y-2 text-sm text-text-secondary">
                        <div>{t.security.incidentFirstSeen}: {formatDateTime(selectedIncident.first_seen)}</div>
                        <div>{t.security.incidentLastSeen}: {formatDateTime(selectedIncident.last_seen)}</div>
                        <div>{t.security.incidentEventsCount(selectedIncident.event_count)}</div>
                        {selectedIncident.repeat_count > 0 && <div>{t.security.incidentRepeatCount(selectedIncident.repeat_count)}</div>}
                      </div>
                    </div>
                    <div className="rounded border border-border/60 bg-bg-primary/40 p-3">
                      <div className="text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentOperatorContext}</div>
                      <div className="mt-2 space-y-2 text-sm text-text-secondary">
                        <div>{t.security.incidentStatusUpdated}: {formatDateTime(selectedIncident.status_updated_at)}</div>
                        <div>{t.security.incidentNotesCount(selectedIncident.note_count)}</div>
                        <div>{t.security.incidentLatestNote}: {latestIncidentNote?.note || t.security.incidentNoNotesYet}</div>
                      </div>
                    </div>
                    <div className="rounded border border-border/60 bg-bg-primary/40 p-3">
                      <div className="text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentResolutionSummary}</div>
                      <div className="mt-2 space-y-2 text-sm text-text-secondary">
                        <div>{t.security.incidentResolutionState}: {formatIncidentResolutionHeadline(incidentDetail?.resolution_summary?.headline)}</div>
                        <div>{t.security.incidentStatusUpdated}: {formatDateTime(incidentDetail?.resolution_summary?.updated_at || selectedIncident.status_updated_at)}</div>
                        <div>{t.security.reason}: {incidentDetail?.resolution_summary?.note || t.security.incidentNoResolutionNote}</div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentSignals}</div>
                    <div className="flex flex-wrap gap-2">
                      {selectedIncident.evidence_types.map((evidenceType) => (
                        <span key={`${selectedIncident.id}-${evidenceType}`} className="rounded-full border border-border px-2 py-1 text-xs text-text-secondary">
                          {formatEventType(evidenceType)}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentProgression}</div>
                    {incidentDetailLoading ? (
                      <LoadingBlock testId="security-incident-progression-loading" />
                    ) : incidentDetailError ? (
                      <ErrorBlock testId="security-incident-progression-error" />
                    ) : !(incidentDetail?.progression?.length) ? (
                      <StateBlock title={t.security.relatedEventsEmpty} testId="security-incident-progression-empty" />
                    ) : (
                      <div className="space-y-2">
                        {incidentDetail.progression.map((step) => (
                          <div key={`${selectedIncident.id}-step-${step.timestamp}-${step.type}`} className="rounded border border-border/60 bg-bg-primary/40 p-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="text-sm text-text-primary">{formatEventType(step.type)}</div>
                                <div className="mt-1 text-xs text-text-secondary/80">{formatEventDescription(step.description, step.type)}</div>
                              </div>
                              <div className="shrink-0 text-xs text-text-secondary">{formatDateTime(step.timestamp)}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="mb-2 text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentEvidenceSummary}</div>
                    {incidentDetailLoading ? (
                      <LoadingBlock testId="security-incident-evidence-summary-loading" />
                    ) : incidentDetailError ? (
                      <ErrorBlock testId="security-incident-evidence-summary-error" />
                    ) : !(incidentDetail?.evidence_summary?.length) ? (
                      <StateBlock title={t.security.relatedEventsEmpty} testId="security-incident-evidence-summary-empty" />
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {incidentDetail.evidence_summary.map((item) => (
                          <span key={`${selectedIncident.id}-summary-${item.type}`} className="rounded-full border border-border px-2 py-1 text-xs text-text-secondary">
                            {formatEventType(item.type)}: {item.count}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div>
                    <div className="mb-2 text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentRelatedEvidence}</div>
                    {incidentDetailLoading ? (
                      <LoadingBlock testId="security-incident-evidence-loading" />
                    ) : evidencePreview.length === 0 ? (
                      <StateBlock title={t.security.relatedEventsEmpty} testId="security-incident-evidence-empty" />
                    ) : (
                      <div className="space-y-2">
                        {evidencePreview.map((event) => (
                          <div key={`evidence-${event.id}`} className="rounded border border-border/60 bg-bg-primary/40 p-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0 text-sm text-text-primary">{formatEventDescription(event.description, event.type)}</div>
                              <div className="shrink-0 text-xs text-text-secondary">{formatDateTime(event.timestamp)}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {(['new', 'investigating', 'resolved'] as const).map((statusValue) => (
                      <button
                        key={`${selectedIncident.id}-${statusValue}`}
                        type="button"
                        onClick={() => handleIncidentStatus(statusValue)}
                        disabled={selectedIncident.status === statusValue || updateIncidentStatusMutation.isPending}
                        className={`rounded border px-3 py-1.5 text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                          selectedIncident.status === statusValue
                            ? 'border-accent-blue bg-bg-card-hover text-accent-blue'
                            : 'border-border text-text-primary hover:bg-bg-card-hover'
                        }`}
                      >
                        {statusValue === 'new' ? t.security.incidentMarkNew : statusValue === 'investigating' ? t.security.incidentMarkInvestigating : t.security.incidentMarkResolved}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => openRelatedLogs({ sourceIp: selectedIncident.source_ip, type: selectedIncident.type, timestamp: selectedIncident.last_seen })}
                      className="rounded border border-border px-3 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
                    >
                      {t.logs.relatedLogs}
                    </button>
                    {selectedIncident.latest_trace_id && (
                      <button
                        type="button"
                        onClick={() => setSelectedTraceId(selectedIncident.latest_trace_id || '')}
                        className="rounded border border-border px-3 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
                      >
                        {t.security.responseTrail}
                      </button>
                    )}
                    {!!selectedIncident.source_ip && !selectedIncidentBlocked && (
                      <button
                        type="button"
                        onClick={() => blockMutation.mutate({ ip: selectedIncident.source_ip, reason: selectedIncident.summary })}
                      className="rounded border border-accent-red/40 px-3 py-1.5 text-sm text-accent-red hover:bg-accent-red/10 transition-colors"
                    >
                      {t.security.blockSourceIp}
                      </button>
                    )}
                    {!!selectedIncident.source_ip && selectedIncidentBlocked && (
                      <span className="rounded border border-border px-3 py-1.5 text-xs text-text-secondary">
                        {t.security.sourceAlreadyBlocked}
                      </span>
                    )}
                  </div>

                  <div>
                    <div className="mb-2 text-xs uppercase tracking-wider text-text-secondary">{t.security.incidentNotes}</div>
                    <div className="space-y-3">
                      <div className="space-y-2">
                        <textarea
                          value={incidentNote}
                          onChange={(evt) => setIncidentNote(evt.target.value)}
                          placeholder={t.security.incidentNotePlaceholder}
                          className="min-h-24 w-full rounded border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
                        />
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={handleAddIncidentNote}
                            disabled={!incidentNote.trim() || addIncidentNoteMutation.isPending}
                            className="rounded border border-border px-3 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            {t.security.incidentAddNote}
                          </button>
                          {(addIncidentNoteMutation.isError || updateIncidentStatusMutation.isError) && (
                            <span className="text-xs text-accent-red">{t.security.incidentWorkflowError}</span>
                          )}
                        </div>
                      </div>

                      {incidentDetailLoading ? (
                        <LoadingBlock testId="security-incident-notes-loading" />
                      ) : incidentDetailError ? (
                        <ErrorBlock testId="security-incident-notes-error" />
                      ) : !incidentDetail?.notes || incidentDetail.notes.length === 0 ? (
                        <StateBlock title={t.security.incidentNotesEmpty} testId="security-incident-notes-empty" />
                      ) : (
                        <div className="space-y-2">
                          {incidentDetail.notes.map((note) => (
                            <div key={note.id} className="rounded border border-border/60 bg-bg-primary/40 p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-text-secondary">
                                <span>{formatIncidentStatus(note.status_at_time)}</span>
                                <span>{formatDateTime(note.created_at)}</span>
                              </div>
                              <div className="mt-2 text-sm text-text-primary">{note.note}</div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div>
                    <div className="mb-2 text-xs uppercase tracking-wider text-text-secondary">{t.security.relatedEvents}</div>
                    {incidentDetailLoading ? (
                      <LoadingBlock testId="security-incident-events-loading" />
                    ) : incidentDetailError ? (
                      <ErrorBlock testId="security-incident-events-error" />
                    ) : !incidentDetail?.related_events || incidentDetail.related_events.length === 0 ? (
                      <StateBlock title={t.security.relatedEventsEmpty} testId="security-incident-events-empty" />
                    ) : (
                      <div className="space-y-2">
                        {incidentDetail.related_events.map((event) => (
                          <div key={event.id} className="rounded border border-border/60 bg-bg-primary/40 p-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <div className="text-sm text-text-primary">{formatEventDescription(event.description, event.type)}</div>
                                <div className="mt-1 text-xs text-text-secondary/80">{formatEventExplanation(event)}</div>
                              </div>
                              <div className="shrink-0 text-xs text-text-secondary">{formatDateTime(event.timestamp)}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            )}
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
        <div className="space-y-4">
          <Table testId="security-events-table" columns={eventColumns} data={pagedEvents} keyField="id" />
          {(events?.length ?? 0) > EVENTS_PER_PAGE && (
            <div className="flex items-center justify-between gap-3 text-sm text-text-secondary">
              <span>{t.security.eventsPage(eventsPage, totalEventPages)}</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setEventsPage((current) => Math.max(1, current - 1))}
                  disabled={eventsPage === 1}
                  className="rounded border border-border px-3 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t.security.previousPage}
                </button>
                <button
                  type="button"
                  onClick={() => setEventsPage((current) => Math.min(totalEventPages, current + 1))}
                  disabled={eventsPage === totalEventPages}
                  className="rounded border border-border px-3 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t.security.nextPage}
                </button>
              </div>
            </div>
          )}
        </div>
        )}
      </Card>

      <div ref={auditCardRef}>
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
      </div>

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
