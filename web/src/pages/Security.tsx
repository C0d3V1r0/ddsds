// Страница безопасности: события, заблокированные IP, управление блокировками
import { useState } from 'react';
import { useSecurityEvents, useBlockedIPs, useBlockIP, useUnblockIP } from '../hooks/useSecurity';
import { Card } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Table } from '../components/ui/Table';
import { ErrorBlock, LoadingBlock, StateBlock } from '../components/ui/StateBlock';
import { t } from '../lib/i18n';
import type { SecurityEvent, BlockedIP } from '../types';

const EVENT_TYPES = ['ssh_brute_force', 'sqli', 'xss', 'path_traversal', 'port_scan', 'anomaly'];

// Валидация IPv4 и IPv6 адресов
const IP_RE = /^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-fA-F:]+$/;

export function Security() {
  const [filterType, setFilterType] = useState('');
  const [blockIp, setBlockIp] = useState('');
  const [blockReason, setBlockReason] = useState('');
  const { data: events, isError: eventsError, isLoading: eventsLoading } = useSecurityEvents(filterType || undefined);
  const { data: blocked, isError: blockedError, isLoading: blockedLoading } = useBlockedIPs();
  const blockMutation = useBlockIP();
  const unblockMutation = useUnblockIP();
  const normalizedIp = blockIp.trim();
  const isIpValid = !normalizedIp || IP_RE.test(normalizedIp);

  const eventColumns = [
    { key: 'severity', header: t.security.severity, render: (row: SecurityEvent) => <Badge variant="severity" value={row.severity} /> },
    { key: 'type', header: t.security.type },
    { key: 'source_ip', header: t.security.sourceIp },
    { key: 'description', header: t.security.description },
    { key: 'action_taken', header: t.security.action },
    { key: 'timestamp', header: t.security.time, render: (row: SecurityEvent) => (
      <span className="text-xs text-text-secondary">{new Date(row.timestamp * 1000).toLocaleString('ru-RU')}</span>
    )},
  ];

  const blockedColumns = [
    { key: 'ip', header: 'IP' },
    { key: 'reason', header: t.security.reason },
    { key: 'blocked_at', header: t.security.blocked, render: (row: BlockedIP) => (
      <span className="text-xs text-text-secondary">{new Date(row.blocked_at * 1000).toLocaleString('ru-RU')}</span>
    )},
    { key: 'expires_at', header: t.security.expires, render: (row: BlockedIP) => (
      <span className="text-xs text-text-secondary">{row.expires_at ? new Date(row.expires_at * 1000).toLocaleString('ru-RU') : t.security.never}</span>
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
            <option key={tp} value={tp}>{tp}</option>
          ))}
        </select>
      </div>

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
