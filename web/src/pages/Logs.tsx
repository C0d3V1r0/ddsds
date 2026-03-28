// Страница логов: live-стрим с фильтрацией, поиском и подсветкой подозрительных строк
import { useState, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useLogs } from '../hooks/useLogs';
import { Card } from '../components/ui/Card';
import { t } from '../lib/i18n';
import { formatDateTime } from '../lib/format';

const LOG_SOURCES = ['', 'auth', 'nginx', 'firewall', 'syslog'];
const SUSPICIOUS_PATTERNS = /failed password|invalid user|union select|<script|\.\.\/\.\.\//i;

function getSuspiciousFragments(line: string, search: string) {
  const fragments = new Set<string>();
  if (search.trim()) fragments.add(search.trim());
  const matches = line.match(/failed password|invalid user|union select|<script|onerror=|onload=|\.\.\/\.\.\//gi) ?? [];
  matches.forEach((match) => fragments.add(match));
  return [...fragments].filter(Boolean);
}

function renderHighlightedLine(line: string, search: string) {
  const fragments = getSuspiciousFragments(line, search);
  if (fragments.length === 0) return line;

  const pattern = new RegExp(`(${fragments.map((fragment) => fragment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi');
  const parts = line.split(pattern);
  const matcher = new RegExp(pattern.source, pattern.flags);
  return parts.map((part, index) => (
    matcher.test(part)
      ? <mark key={`${part}-${index}`} className="rounded bg-accent-yellow/20 px-0.5 text-accent-yellow">{part}</mark>
      : <span key={`${part}-${index}`}>{part}</span>
  ));
}

export function Logs() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [source, setSource] = useState('');
  const [search, setSearch] = useState('');
  const [fromDateTime, setFromDateTime] = useState('');
  const [toDateTime, setToDateTime] = useState('');
  const [ipFilter, setIpFilter] = useState('');
  const [eventTypeFilter, setEventTypeFilter] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const fromTimestamp = fromDateTime ? Math.floor(new Date(fromDateTime).getTime() / 1000) : null;
  const toTimestamp = toDateTime ? Math.floor(new Date(toDateTime).getTime() / 1000) : null;
  const { data: logs, clearLive, isError: logsError } = useLogs({
    source: source || undefined,
    limit: 200,
    fromTs: fromTimestamp,
    toTs: toTimestamp,
    query: search || undefined,
    ip: ipFilter || undefined,
    eventType: eventTypeFilter || undefined,
  });

  useEffect(() => {
    setSource(searchParams.get('source') || '');
    setSearch(searchParams.get('q') || '');
    setIpFilter(searchParams.get('ip') || '');
    setEventTypeFilter(searchParams.get('event_type') || '');
    setFromDateTime(searchParams.get('from') || '');
    setToDateTime(searchParams.get('to') || '');
  }, [searchParams]);

  useEffect(() => {
    const next = new URLSearchParams();
    if (source) next.set('source', source);
    if (search) next.set('q', search);
    if (ipFilter) next.set('ip', ipFilter);
    if (eventTypeFilter) next.set('event_type', eventTypeFilter);
    if (fromDateTime) next.set('from', fromDateTime);
    if (toDateTime) next.set('to', toDateTime);
    setSearchParams(next, { replace: true });
  }, [source, search, ipFilter, eventTypeFilter, fromDateTime, toDateTime, setSearchParams]);

  // Автоскролл при получении новых логов
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs?.length, autoScroll]);

  const normalizedSearch = search.trim().toLowerCase();
  const filtered = (logs ?? []).filter((log) => {
    if (normalizedSearch && !log.line.toLowerCase().includes(normalizedSearch)) return false;
    return true;
  });

  return (
    <div data-testid="page-logs" className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <h1 className="text-xl font-bold">{t.logs.title}</h1>
        <select
          data-testid="logs-source-filter"
          value={source}
          onChange={(e) => { setSource(e.target.value); clearLive(); }}
          className="bg-bg-card border border-border rounded px-3 py-1.5 text-sm text-text-primary"
        >
          <option value="">{t.logs.allSources}</option>
          {LOG_SOURCES.filter(Boolean).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <input
          data-testid="logs-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t.logs.searchPlaceholder}
          className="bg-bg-card border border-border rounded px-3 py-1.5 text-sm text-text-primary w-64"
        />
        <input
          data-testid="logs-ip-filter"
          value={ipFilter}
          onChange={(e) => setIpFilter(e.target.value)}
          placeholder={t.logs.ipPlaceholder}
          className="bg-bg-card border border-border rounded px-3 py-1.5 text-sm text-text-primary w-52"
        />
        <label className="flex items-center gap-2 text-xs text-text-secondary">
          <span>{t.logs.from}</span>
          <input
            data-testid="logs-from-datetime"
            type="datetime-local"
            value={fromDateTime}
            onChange={(e) => setFromDateTime(e.target.value)}
            aria-label={t.logs.fromPlaceholder}
            className="bg-bg-card border border-border rounded px-3 py-1.5 text-sm text-text-primary"
          />
        </label>
        <label className="flex items-center gap-2 text-xs text-text-secondary">
          <span>{t.logs.to}</span>
          <input
            data-testid="logs-to-datetime"
            type="datetime-local"
            value={toDateTime}
            onChange={(e) => setToDateTime(e.target.value)}
            aria-label={t.logs.toPlaceholder}
            className="bg-bg-card border border-border rounded px-3 py-1.5 text-sm text-text-primary"
          />
        </label>
        {(fromDateTime || toDateTime) && (
          <button
            type="button"
            data-testid="logs-reset-datetime"
            onClick={() => {
              setFromDateTime('');
              setToDateTime('');
            }}
            className="text-xs text-text-secondary hover:text-text-primary transition-colors"
          >
            {t.logs.resetRange}
          </button>
        )}
        {(ipFilter || eventTypeFilter) && (
          <button
            type="button"
            onClick={() => {
              setIpFilter('');
              setEventTypeFilter('');
            }}
            className="text-xs text-text-secondary hover:text-text-primary transition-colors"
          >
            {t.logs.resetInvestigation}
          </button>
        )}
        {eventTypeFilter && (
          <span className="rounded-full border border-border px-2 py-1 text-[11px] text-text-secondary">
            {t.logs.investigatingEvent(eventTypeFilter.replace(/_/g, ' '))}
          </span>
        )}
        <label className="flex items-center gap-2 text-xs text-text-secondary cursor-pointer">
          <input
            data-testid="logs-autoscroll"
            type="checkbox"
            checked={autoScroll}
            onChange={(e) => setAutoScroll(e.target.checked)}
            className="rounded"
          />
          {t.logs.autoScroll}
        </label>
        <span className="text-xs text-text-secondary">{t.logs.lineCount(filtered.length)}</span>
      </div>

      {logsError && <div data-testid="logs-error" className="text-sm text-accent-red py-2 text-center">{t.common.error}</div>}
      <Card gradient={false} testId="logs-card" className="h-[calc(100vh-200px)] overflow-y-auto font-mono text-xs">
        {filtered.map((log, i) => {
          const isSuspicious = SUSPICIOUS_PATTERNS.test(log.line);
          return (
            <div
              data-testid="log-entry"
              key={`${log.timestamp}-${i}`}
              className={`py-0.5 px-2 flex gap-3 ${isSuspicious ? 'bg-accent-red/10 text-accent-red' : 'hover:bg-bg-card-hover'}`}
            >
              <span className="text-text-secondary shrink-0 w-44">
                {formatDateTime(log.timestamp)}
              </span>
              <span className="text-accent-blue shrink-0 w-16">{log.source}</span>
              <span className="break-all">{renderHighlightedLine(log.line, search || ipFilter)}</span>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div data-testid="logs-empty" className="text-text-secondary text-center py-8">
            <div>{t.logs.noLogs}</div>
            <div className="mt-1 text-xs text-text-secondary/80">{t.common.noDataHint}</div>
          </div>
        )}
        <div ref={logsEndRef} />
      </Card>
    </div>
  );
}
