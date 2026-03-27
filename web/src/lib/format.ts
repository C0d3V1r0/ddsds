import { getCurrentLocale, getLocaleTag, t } from './i18n';
import type { Metrics } from '../types';

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

export function formatRelativeAge(timestamp?: number | null) {
  if (!timestamp) return '—';

  const diffSeconds = Math.max(0, Math.floor(Date.now() / 1000) - timestamp);
  if (diffSeconds <= 5) return t.dashboard.justUpdated;
  if (diffSeconds < 60) return t.time.secondsAgo(diffSeconds);

  const minutes = Math.floor(diffSeconds / 60);
  if (minutes < 60) return t.time.minutesAgo(minutes);

  return t.time.hoursAgo(Math.floor(minutes / 60));
}
