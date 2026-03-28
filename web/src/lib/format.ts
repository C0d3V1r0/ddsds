import { getCurrentLocale, getLocaleTag, t } from './i18n';
import type { Metrics, ResponseAuditEntry, RiskFactor, SecurityEvent } from '../types';

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
    sqli: { ru: 'SQL injection', en: 'SQL injection' },
    xss: { ru: 'Cross-site scripting', en: 'Cross-site scripting' },
    path_traversal: { ru: 'Обход путей', en: 'Path traversal' },
    port_scan: { ru: 'Сканирование портов', en: 'Port scan' },
    anomaly: { ru: 'Аномалия метрик', en: 'Metrics anomaly' },
  };

  const locale = getCurrentLocale();
  return map[value]?.[locale] ?? value.replace(/_/g, ' ');
}

export function formatEventDescription(description: string, type?: string) {
  const locale = getCurrentLocale();
  const normalizedType = type ? formatEventType(type) : '';

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

  return description;
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
    case 'web_attack_pattern':
      return t.security.explanationWebAttackPattern;
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
  const command = entry.command ? ` · ${entry.command}` : '';
  const source = entry.source_ip ? ` · ${formatEventSource(entry.source_ip)}` : '';
  const type = entry.event_type ? formatEventType(entry.event_type) : '';
  const head = type || t.security.auditGeneric;
  return `${head}${source}${command}`;
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

export function formatRelativeAge(timestamp?: number | null) {
  if (!timestamp) return '—';

  const diffSeconds = Math.max(0, Math.floor(Date.now() / 1000) - timestamp);
  if (diffSeconds <= 5) return t.dashboard.justUpdated;
  if (diffSeconds < 60) return t.time.secondsAgo(diffSeconds);

  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) return t.time.minutesAgo(minutes);

  return t.time.hoursAgo(Math.floor(minutes / 60));
}
