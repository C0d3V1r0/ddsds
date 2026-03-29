import { getCurrentLocale, getLocaleTag, t } from './i18n';
import type { Metrics, ResponseAuditEntry, RiskFactor, RiskHistoryPoint, SecurityEvent } from '../types';

const BYTE_UNITS = ['byte', 'kilobyte', 'megabyte', 'gigabyte'] as const;

function formatNumber(value: number, maximumFractionDigits = 1) {
  return new Intl.NumberFormat(getLocaleTag(), {
    maximumFractionDigits,
  }).format(value);
}

export function formatBytes(value: number, { compact = false, perSecond = false }: { compact?: boolean; perSecond?: boolean } = {}) {
  const abs = Math.abs(value);
  let unitIndex = 0;
  let display = abs;

  while (display >= 1024 && unitIndex < BYTE_UNITS.length - 1) {
    display /= 1024;
    unitIndex += 1;
  }

  const unit = t.units[BYTE_UNITS[unitIndex]];
  const suffix = perSecond ? t.units.bytesPerSecond : '';
  const digits = compact && unitIndex > 0 ? 1 : 0;
  const formatted = formatNumber(display * Math.sign(value), digits);

  return `${formatted} ${unit}${suffix}`;
}

export function formatChartTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleTimeString(getLocaleTag(), {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatChartAxisTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleTimeString(getLocaleTag(), {
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatDateTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString(getLocaleTag());
}

export function formatMetricValue(dataKey: keyof Metrics, value: number) {
  if (dataKey === 'ram_used' || dataKey === 'ram_total') return formatBytes(value);
  if (dataKey === 'network_rx' || dataKey === 'network_tx') return formatBytes(value, { perSecond: true });
  if (String(dataKey).includes('cpu')) return `${formatNumber(value)}%`;
  return formatNumber(value);
}

export function formatMetricTick(dataKey: keyof Metrics, value: number) {
  if (dataKey === 'ram_used' || dataKey === 'ram_total') return formatBytes(value, { compact: true });
  if (dataKey === 'network_rx' || dataKey === 'network_tx') return formatBytes(value, { compact: true, perSecond: true });
  if (String(dataKey).includes('cpu')) return `${formatNumber(value)}%`;
  return formatNumber(value);
}

export function formatCurrentTime(date: Date) {
  return date.toLocaleTimeString(getLocaleTag(getCurrentLocale()), {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function formatEventType(value: string) {
  const map: Record<string, { ru: string; en: string }> = {
    ssh_brute_force: { ru: 'Подбор пароля по SSH', en: 'SSH brute force' },
    ssh_user_enum: { ru: 'Перебор пользователей SSH', en: 'SSH user enumeration' },
    sqli: { ru: 'SQL injection', en: 'SQL injection' },
    xss: { ru: 'Cross-site scripting', en: 'Cross-site scripting' },
    path_traversal: { ru: 'Обход путей', en: 'Path traversal' },
    command_injection: { ru: 'Command injection', en: 'Command injection' },
    sensitive_path_probe: { ru: 'Разведка чувствительных путей', en: 'Sensitive path probing' },
    scanner_probe: { ru: 'Сканирующий инструмент', en: 'Scanner probe' },
    web_login_bruteforce: { ru: 'Подбор пароля в web-логине', en: 'Web login brute force' },
    port_scan: { ru: 'Сканирование портов', en: 'Port scan' },
    recon_chain: { ru: 'Коррелированная разведка', en: 'Correlated reconnaissance' },
    credential_attack_chain: { ru: 'Коррелированная атака на учётные данные', en: 'Correlated credential attack' },
    web_attack_chain: { ru: 'Коррелированная web-атака', en: 'Correlated web attack' },
    anomaly: { ru: 'Аномалия метрик', en: 'Metrics anomaly' },
  };

  const locale = getCurrentLocale();
  return map[value]?.[locale] ?? value.replace(/_/g, ' ');
}

export function formatEventDescription(description: string, type?: string) {
  const locale = getCurrentLocale();
  const normalizedType = type ? formatEventType(type) : '';
  const portScanMatch = description.match(/^(\d+)\s+unique destination ports probed in\s+(\d+)s$/i);
  const sshThresholdMatch = description.match(/^(\d+)\+\s+failed SSH attempts in\s+(\d+)s$/i);
  const sshInvalidUsersMatch = description.match(/^(\d+)\+\s+invalid SSH users in\s+(\d+)s$/i);
  const webLoginBruteforceMatch = description.match(/^(\d+)\+\s+repeated web login attempts in\s+(\d+)s$/i);
  const reconChainMatch = description.match(/^Correlated recon chain:\s+(.+)$/i);
  const credentialChainMatch = description.match(/^Correlated credential chain:\s+(.+)$/i);
  const webChainMatch = description.match(/^Correlated web attack chain:\s+(.+)$/i);

  if (description.startsWith('ML-detected: ')) {
    const label = description.replace('ML-detected: ', '');
    return locale === 'ru'
      ? `${t.system.attackClassifier}: ${formatEventType(label)}`
      : `${t.system.attackClassifier}: ${formatEventType(label)}`;
  }

  if (description.startsWith('Rule+ML confirmed: ')) {
    const label = description.replace('Rule+ML confirmed: ', '');
    return locale === 'ru'
      ? `Rule + ML подтвердили: ${formatEventType(label)}`
      : `Rule + ML confirmed: ${formatEventType(label)}`;
  }

  if (description.startsWith('ML anomaly detected')) {
    return locale === 'ru'
      ? `${t.system.anomalyDetector}: обнаружена аномалия в метриках`
      : `${t.system.anomalyDetector}: anomaly detected in metrics`;
  }

  if (description.endsWith('pattern detected') && type) {
    return locale === 'ru'
      ? `Обнаружен паттерн атаки: ${normalizedType.toLowerCase()}`
      : `${normalizedType} pattern detected`;
  }

  if (portScanMatch) {
    const ports = Number(portScanMatch[1]);
    const window = Number(portScanMatch[2]);
    return t.security.eventPortScanDescription(ports, window);
  }

  if (sshThresholdMatch) {
    const attempts = Number(sshThresholdMatch[1]);
    const window = Number(sshThresholdMatch[2]);
    return t.security.eventSshBruteforceDescription(attempts, window);
  }

  if (sshInvalidUsersMatch) {
    const attempts = Number(sshInvalidUsersMatch[1]);
    const window = Number(sshInvalidUsersMatch[2]);
    return t.security.eventSshUserEnumDescription(attempts, window);
  }

  if (webLoginBruteforceMatch) {
    const attempts = Number(webLoginBruteforceMatch[1]);
    const window = Number(webLoginBruteforceMatch[2]);
    return t.security.eventWebLoginBruteforceDescription(attempts, window);
  }

  if (reconChainMatch) {
    const rawTypes = reconChainMatch[1].split(',').map((item) => item.trim()).filter(Boolean);
    const labels = rawTypes.map((item) => formatEventType(item)).join(', ');
    return t.security.eventReconChainDescription(labels);
  }

  if (credentialChainMatch) {
    const rawTypes = credentialChainMatch[1].split(',').map((item) => item.trim()).filter(Boolean);
    const labels = rawTypes.map((item) => formatEventType(item)).join(', ');
    return t.security.eventCredentialChainDescription(labels);
  }

  if (webChainMatch) {
    const rawTypes = webChainMatch[1].split(',').map((item) => item.trim()).filter(Boolean);
    const labels = rawTypes.map((item) => formatEventType(item)).join(', ');
    return t.security.eventWebAttackChainDescription(labels);
  }

  return description;
}

export function formatBlockedReason(reason: string) {
  return formatEventDescription(reason);
}

export function formatActionTaken(value: string) {
  const map: Record<string, string> = {
    auto_block: t.security.actionAutoBlocked,
    logged: t.security.actionLogged,
    log: t.security.actionLogged,
    review_required: t.security.actionReviewRequired,
    ml_detection: t.security.actionMlDetection,
  };

  return map[value] ?? t.security.actionLogged;
}

export function formatEventSource(sourceIp?: string | null) {
  const value = sourceIp?.trim();
  return value || t.security.sourceHost;
}

export function formatSignalSource(value?: string) {
  const map: Record<string, string> = {
    rule_auth_logs: t.security.signalRuleAuthLogs,
    rule_web_logs: t.security.signalRuleWebLogs,
    rule_firewall_logs: t.security.signalRuleFirewallLogs,
    rule_plus_ml: t.security.signalRulePlusMl,
    ml_log_classifier: t.security.signalMlLogClassifier,
    ml_metrics_detector: t.security.signalMlMetricsDetector,
    generic: t.security.signalGeneric,
  };
  return map[value ?? 'generic'] ?? t.security.signalGeneric;
}

export function formatConfidence(value?: string) {
  if (!value) return '—';
  return t.severity[value as keyof typeof t.severity] ?? value;
}

export function formatRecommendedAction(value?: string) {
  const map: Record<string, string> = {
    review_source_ip: t.security.recommendationReviewIp,
    review_related_logs: t.security.recommendationReviewLogs,
    review_host_metrics: t.security.recommendationReviewMetrics,
    auto_block_applied: t.security.recommendationAutoBlocked,
    monitor_only: t.security.recommendationMonitorOnly,
    review_event: t.security.recommendationGeneric,
  };
  return map[value ?? 'review_event'] ?? t.security.recommendationGeneric;
}

export function formatEventExplanation(event: Pick<SecurityEvent, 'explanation_code' | 'type'>) {
  switch (event.explanation_code) {
    case 'ssh_failed_attempts_threshold':
      return t.security.explanationSshThreshold;
    case 'ssh_invalid_user_threshold':
      return t.security.explanationSshInvalidUserThreshold;
    case 'web_attack_pattern':
      return t.security.explanationWebAttackPattern;
    case 'sensitive_path_probe':
      return t.security.explanationSensitivePathProbe;
    case 'scanner_tool_pattern':
      return t.security.explanationScannerToolPattern;
    case 'web_login_threshold':
      return t.security.explanationWebLoginThreshold;
    case 'rule_ml_confirmed':
      return t.security.explanationRuleMlConfirmed;
    case 'unique_destination_ports_threshold':
      return t.security.explanationPortScanThreshold;
    case 'ml_log_classifier':
      return t.security.explanationMlLogClassifier;
    case 'metrics_anomaly':
      return t.security.explanationMetricsAnomaly;
    default:
      return t.security.explanationGeneric;
  }
}

export function formatIncidentStatus(value: 'new' | 'investigating' | 'resolved') {
  const map = {
    new: t.security.incidentNew,
    investigating: t.security.incidentInvestigating,
    resolved: t.security.incidentResolved,
  };
  return map[value] ?? value;
}

export function formatIncidentResolutionHeadline(value?: string) {
  const map: Record<string, string> = {
    incident_resolved: t.security.incidentResolutionHeadlineIncidentResolved,
    source_blocked: t.security.incidentResolutionHeadlineSourceBlocked,
    decision_recorded: t.security.incidentResolutionHeadlineDecisionRecorded,
    investigation_open: t.security.incidentResolutionHeadlineInvestigationOpen,
    review: t.security.incidentResolutionHeadlineReview,
    contain: t.security.incidentResolutionHeadlineContain,
    block: t.security.incidentResolutionHeadlineBlock,
  };
  return map[value ?? ''] ?? t.security.incidentResolutionOpen;
}

export function formatAuditStage(value: string) {
  const map: Record<string, string> = {
    detected: t.security.auditStageDetected,
    decision: t.security.auditStageDecision,
    command_dispatched: t.security.auditStageDispatched,
    command_result: t.security.auditStageResult,
    manual_action: t.security.auditStageManual,
  };
  return map[value] ?? value;
}

export function formatAuditStatus(value: string) {
  const map: Record<string, string> = {
    event_created: t.security.auditStatusRecorded,
    review: t.security.actionReviewRequired,
    block: t.security.actionAutoBlocked,
    queued: t.security.auditStatusQueued,
    success: t.security.auditStatusSuccess,
    error: t.security.auditStatusError,
    failed: t.security.auditStatusError,
    blocked: t.security.auditStatusBlocked,
    unblocked: t.security.auditStatusUnblocked,
  };
  return map[value] ?? value;
}

export function formatAuditSummary(entry: ResponseAuditEntry) {
  const details = entry.details ?? {};
  const source = entry.source_ip ? formatEventSource(entry.source_ip) : '';
  const type = entry.event_type ? formatEventType(entry.event_type) : t.security.auditGeneric;
  const origin = String(details.origin ?? '');
  const reason = String(details.reason ?? '');
  const operationMode = String(details.operation_mode ?? '');
  const policyStage = String(details.policy_stage ?? '');
  const operatorPriority = String(details.operator_priority ?? '');
  const recentEventsCount = Number(details.recent_events_count ?? 0);
  const stageLabelMap: Record<string, string> = {
    observe: t.security.auditPolicyStageObserve,
    review: t.security.auditPolicyStageReview,
    contain: t.security.auditPolicyStageContain,
    block: t.security.auditPolicyStageBlock,
  };
  const priorityLabelMap: Record<string, string> = {
    low: t.security.auditPriorityLow,
    normal: t.security.auditPriorityNormal,
    high: t.security.auditPriorityHigh,
    urgent: t.security.auditPriorityUrgent,
  };

  if (entry.stage === 'detected') {
    const parts = [type];
    if (source) parts.push(source);
    if (recentEventsCount > 0) parts.push(t.security.auditRecentEvents(recentEventsCount));
    return parts.join(' · ');
  }

  if (entry.stage === 'decision') {
    const parts = [type];
    if (source) parts.push(source);
    if (operationMode) parts.push(t.security.auditMode(operationMode));
    if (policyStage) parts.push(t.security.auditPolicyStage(stageLabelMap[policyStage] ?? policyStage));
    if (operatorPriority) parts.push(t.security.auditPriority(priorityLabelMap[operatorPriority] ?? operatorPriority));
    if (reason === 'cooldown_active') parts.push(t.security.auditReasonCooldownActive);
    if (reason === 'already_blocked_followup') parts.push(t.security.auditReasonAlreadyBlockedFollowup);
    if (reason === 'recent_duplicate_event') parts.push(t.security.auditReasonRecentDuplicate);
    if (reason === 'critical_severity') parts.push(t.security.auditReasonCriticalSeverity);
    if (reason === 'high_severity_containment') parts.push(t.security.auditReasonHighSeverityContainment);
    if (reason === 'active_attack_high_confidence') parts.push(t.security.auditReasonActiveAttackContainment);
    if (reason === 'credential_attack_first_seen') parts.push(t.security.auditReasonCredentialFirstSeen);
    if (reason === 'credential_attack_escalation') parts.push(t.security.auditReasonCredentialEscalation);
    if (reason === 'reconnaissance_escalation') parts.push(t.security.auditReasonReconEscalation);
    if (reason === 'reconnaissance_review') parts.push(t.security.auditReasonReconReview);
    if (reason === 'manual_containment_required') parts.push(t.security.auditReasonManualContainment);
    if (reason === 'standby_passive_node') parts.push(t.security.auditReasonStandbyPassiveNode);
    return parts.join(' · ');
  }

  if (entry.stage === 'command_dispatched') {
    const parts = [type];
    if (source) parts.push(source);
    if (entry.command) parts.push(entry.command);
    parts.push(t.security.auditCommandQueued);
    return parts.join(' · ');
  }

  if (entry.stage === 'command_result') {
    const parts = [type];
    if (source) parts.push(source);
    if (entry.command) parts.push(entry.command);
    parts.push(entry.status === 'success' ? t.security.auditCommandOutcomeSuccess : t.security.auditCommandOutcomeError);
    return parts.join(' · ');
  }

  if (entry.stage === 'manual_action') {
    const parts = [type];
    if (source) parts.push(source);
    if (origin === 'telegram_bot') parts.push(t.security.auditOriginTelegram);
    else parts.push(t.security.auditOriginOperator);
    if (entry.action === 'incident_note') parts.push(t.security.auditNoteAdded);
    if (entry.action === 'incident_status_update') parts.push(t.security.auditIncidentStatusUpdated);
    return parts.join(' · ');
  }

  const parts = [type];
  if (source) parts.push(source);
  if (origin === 'auto_response') parts.push(t.security.auditOriginAutoResponse);
  return parts.join(' · ');
}

export function formatRiskLevel(level: 'low' | 'medium' | 'high' | 'critical') {
  const map = {
    low: t.system.riskLow,
    medium: t.system.riskMedium,
    high: t.system.riskHigh,
    critical: t.system.riskCritical,
  };
  return map[level] ?? level;
}

export function formatRiskFactor(factor: RiskFactor) {
  switch (factor.code) {
    case 'agent_disconnected':
      return t.system.riskFactorAgent;
    case 'api_unhealthy':
      return t.system.riskFactorApi;
    case 'db_unhealthy':
      return t.system.riskFactorDb;
    case 'failed_services':
      return t.system.riskFactorFailedServices(factor.count ?? 0);
    case 'stopped_services':
      return t.system.riskFactorStoppedServices(factor.count ?? 0);
    case 'metrics_missing':
      return t.system.riskFactorMetricsMissing;
    case 'metrics_stale':
      return t.system.riskFactorMetricsStale(factor.age_seconds ?? 0);
    case 'metrics_aging':
      return t.system.riskFactorMetricsAging(factor.age_seconds ?? 0);
    case 'recent_security_pressure':
      return t.system.riskFactorSecurityPressure(factor.count ?? 0);
    default:
      return factor.code;
  }
}

export function formatRiskExplanation(
  level: 'low' | 'medium' | 'high' | 'critical',
  factors: RiskFactor[],
) {
  if (factors.length === 0) {
    return t.system.riskExplanationHealthy;
  }

  // Берём самые весомые причины, чтобы коротко объяснить текущий уровень риска.
  const sortedFactors = [...factors].sort((left, right) => right.weight - left.weight);
  const primary = formatRiskFactor(sortedFactors[0]);
  const secondary = sortedFactors[1] ? formatRiskFactor(sortedFactors[1]) : '';

  if (!secondary) {
    return t.system.riskExplanationSingle(primary);
  }

  if (level === 'high' || level === 'critical') {
    return t.system.riskExplanationDouble(primary, secondary);
  }

  return t.system.riskExplanationSingle(primary);
}

export function formatRiskTrend(history: RiskHistoryPoint[]) {
  if (history.length < 2) {
    return t.system.riskTrendStable;
  }

  const previous = history[Math.max(0, history.length - 2)];
  const latest = history[history.length - 1];
  const delta = latest.score - previous.score;

  if (delta > 0) return t.system.riskTrendUp(delta);
  if (delta < 0) return t.system.riskTrendDown(Math.abs(delta));
  return t.system.riskTrendStable;
}

export function formatRiskTopContributors(factors: RiskFactor[], limit = 3) {
  return [...factors]
    .sort((left, right) => right.weight - left.weight)
    .slice(0, limit)
    .map((factor) => ({
      ...factor,
      label: formatRiskFactor(factor),
    }));
}

export function formatRiskChangeSummary(
  currentFactors: RiskFactor[],
  history: RiskHistoryPoint[],
  currentScore: number,
) {
  if (history.length < 2 || currentFactors.length === 0) {
    return t.system.riskChangeSummaryStable;
  }

  const previous = history[history.length - 2];
  const previousMap = new Map(previous.factors.map((factor) => [factor.code, factor.weight]));
  const currentTop = formatRiskTopContributors(currentFactors, 1)[0];
  if (!currentTop) {
    return t.system.riskChangeSummaryStable;
  }

  const previousWeight = previousMap.get(currentTop.code) ?? 0;
  if (previousWeight === 0) {
    return t.system.riskChangeSummaryNewFactor(currentTop.label);
  }
  if (currentScore > previous.score && currentTop.weight >= previousWeight) {
    return t.system.riskChangeSummaryIncrease(currentTop.label);
  }
  if (currentScore < previous.score) {
    return t.system.riskChangeSummaryDecrease(currentTop.label);
  }
  return t.system.riskChangeSummaryStable;
}

export function formatRelativeAge(timestamp?: number | null) {
  if (!timestamp) return '—';

  const diffSeconds = Math.max(0, Math.floor(Date.now() / 1000) - timestamp);
  if (diffSeconds <= 5) return t.dashboard.justUpdated;
  if (diffSeconds < 60) return t.time.secondsAgo(diffSeconds);

  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) return t.time.minutesAgo(minutes);

  return t.time.hoursAgo(Math.floor(minutes / 60));
}
