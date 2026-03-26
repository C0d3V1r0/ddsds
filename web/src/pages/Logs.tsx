// - Страница логов: live-стрим с фильтрацией, поиском и подсветкой подозрительных строк
import { useState, useRef, useEffect } from 'react';
import { useLogs } from '../hooks/useLogs';
import { Card } from '../components/ui/Card';
import { t } from '../lib/i18n';

const LOG_SOURCES = ['', 'auth', 'nginx', 'syslog'];
const SUSPICIOUS_PATTERNS = /failed password|invalid user|union select|<script|\.\.\/\.\.\//i;

export function Logs() {
  const [source, setSource] = useState('');
  const [search, setSearch] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const { data: logs, clearLive, isError: logsError } = useLogs(source || undefined);

  // - Автоскролл при получении новых логов
  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs?.length, autoScroll]);

  const filtered = search
    ? (logs ?? []).filter((l) => l.line.toLowerCase().includes(search.toLowerCase()))
    : (logs ?? []);

  return (
    <div data-testid="page-logs" className="space-y-4">
      <div className="flex items-center gap-4">
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
                {new Date(log.timestamp * 1000).toLocaleString('ru-RU')}
              </span>
              <span className="text-accent-blue shrink-0 w-16">{log.source}</span>
              <span className="break-all">{log.line}</span>
            </div>
          );
        })}
        {filtered.length === 0 && (
          <div data-testid="logs-empty" className="text-text-secondary text-center py-8">{t.logs.noLogs}</div>
        )}
        <div ref={logsEndRef} />
      </Card>
    </div>
  );
}
