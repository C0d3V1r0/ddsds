// Страница процессов: сортируемая таблица с поиском
import { useState, useMemo } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { Card } from '../components/ui/Card';
import { ErrorBlock, LoadingBlock, StateBlock } from '../components/ui/StateBlock';
import { t } from '../lib/i18n';
import type { ProcessInfo } from '../types';

type SortKey = 'name' | 'cpu' | 'ram' | 'pid';
type SortDir = 'asc' | 'desc';

// API возвращает ram в байтах, конвертируем в МБ для отображения
function bytesToMb(bytes: number): number {
  return bytes / 1024 / 1024;
}

const PROTECTED_PROCESS_NAMES = new Set([
  'nullius-agent',
  'nullius-api',
  'sshd',
  'nginx',
  'systemd',
  'systemd-journald',
  'systemd-logind',
]);

function isProtectedProcess(process: ProcessInfo) {
  return PROTECTED_PROCESS_NAMES.has(process.name) || process.name.startsWith('systemd-') || process.name.startsWith('kworker');
}

export function Processes() {
  const queryClient = useQueryClient();
  const { data: processes, isError: processesError, isLoading: processesLoading } = useQuery({ queryKey: ['processes'], queryFn: api.processes, refetchInterval: 5000 });
  const [sortKey, setSortKey] = useState<SortKey>('cpu');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [search, setSearch] = useState('');
  const [selectedProcess, setSelectedProcess] = useState<ProcessInfo | null>(null);
  const [selectedAction, setSelectedAction] = useState<'terminate' | 'force-kill'>('terminate');
  const [actionNotice, setActionNotice] = useState<string>('');
  const terminateMutation = useMutation({
    mutationFn: (pid: number) => api.terminateProcess(pid),
    onSuccess: () => {
      setActionNotice(t.processes.terminateQueued);
      setSelectedProcess(null);
      queryClient.invalidateQueries({ queryKey: ['processes'] });
    },
  });
  const forceKillMutation = useMutation({
    mutationFn: (pid: number) => api.forceKillProcess(pid),
    onSuccess: () => {
      setActionNotice(t.processes.forceKillQueued);
      setSelectedProcess(null);
      queryClient.invalidateQueries({ queryKey: ['processes'] });
    },
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  const sorted = useMemo(() => {
    let list = [...(processes ?? [])];
    if (search) {
      const q = search.toLowerCase();
      list = list.filter((p) => p.name.toLowerCase().includes(q) || String(p.pid).includes(q));
    }
    list.sort((a: ProcessInfo, b: ProcessInfo) => {
      // Строковые поля сравниваем через localeCompare, числовые — вычитанием
      if (sortKey === 'name') {
        const cmp = a.name.localeCompare(b.name);
        return sortDir === 'asc' ? cmp : -cmp;
      }
      const cmp = a[sortKey] - b[sortKey];
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [processes, sortKey, sortDir, search]);

  const SortHeader = ({ label, field }: { label: string; field: SortKey }) => (
    <th
      onClick={() => handleSort(field)}
      className="text-left py-3 px-4 text-xs uppercase tracking-wider text-text-secondary cursor-pointer hover:text-text-primary select-none"
    >
      {label} {sortKey === field ? (sortDir === 'asc' ? '\u2191' : '\u2193') : ''}
    </th>
  );

  const cpuColor = (v: number) => v > 80 ? 'text-accent-red' : v > 50 ? 'text-accent-yellow' : 'text-text-primary';
  // Пороги в МБ: >500 МБ красный, >200 МБ жёлтый
  const ramColor = (mb: number) => mb > 500 ? 'text-accent-red' : mb > 200 ? 'text-accent-yellow' : 'text-text-primary';

  return (
    <div data-testid="page-processes" className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold">{t.processes.title}</h1>
        <p className="text-sm text-text-secondary">{t.processes.summary}</p>
      </div>

      <StateBlock title={t.processes.terminateHint} testId="processes-hint" />
      {actionNotice && <StateBlock title={actionNotice} testId="processes-notice" />}

      <div className="flex items-center gap-4">
        <input
          data-testid="processes-search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t.processes.searchPlaceholder}
          className="bg-bg-card border border-border rounded px-3 py-1.5 text-sm text-text-primary w-64"
        />
        <span className="text-xs text-text-secondary">{t.processes.processCount(sorted.length)}</span>
      </div>

      <Card gradient={false} testId="processes-card">
        {processesLoading ? (
          <LoadingBlock testId="processes-loading" />
        ) : processesError ? (
          <ErrorBlock testId="processes-error" />
        ) : (
          <div className="overflow-x-auto">
            <table data-testid="processes-table" className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <SortHeader label={t.processes.pid} field="pid" />
                  <SortHeader label={t.processes.name} field="name" />
                  <SortHeader label={t.processes.cpuPercent} field="cpu" />
                  <SortHeader label={t.processes.ramMb} field="ram" />
                  <th className="text-left py-3 px-4 text-xs uppercase tracking-wider text-text-secondary">{t.processes.actions}</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((p) => {
                  const ramMb = bytesToMb(p.ram);
                  const protectedProcess = isProtectedProcess(p);
                  return (
                    <tr key={p.pid} className="border-b border-border/30 hover:bg-bg-card-hover transition-colors">
                      <td className="py-2.5 px-4 text-text-secondary font-mono text-xs">{p.pid}</td>
                      <td className="py-2.5 px-4">{p.name}</td>
                      <td className={`py-2.5 px-4 font-mono ${cpuColor(p.cpu)}`}>{p.cpu.toFixed(1)}</td>
                      <td className={`py-2.5 px-4 font-mono ${ramColor(ramMb)}`}>{ramMb.toFixed(1)}</td>
                      <td className="py-2.5 px-4">
                        {protectedProcess ? (
                          <span className="text-xs text-text-secondary">{t.processes.protected}</span>
                        ) : (
                          <button
                            type="button"
                            data-testid={`process-terminate-${p.pid}`}
                            onClick={() => {
                              terminateMutation.reset();
                              forceKillMutation.reset();
                              setActionNotice('');
                              setSelectedAction('terminate');
                              setSelectedProcess(p);
                            }}
                            className="text-xs text-accent-red hover:text-red-300 transition-colors"
                          >
                            {t.processes.terminate}
                          </button>
                        )}
                        {!protectedProcess && (
                          <button
                            type="button"
                            data-testid={`process-force-kill-${p.pid}`}
                            onClick={() => {
                              terminateMutation.reset();
                              forceKillMutation.reset();
                              setActionNotice('');
                              setSelectedAction('force-kill');
                              setSelectedProcess(p);
                            }}
                            className="ml-3 text-xs text-accent-yellow hover:text-yellow-300 transition-colors"
                          >
                            {t.processes.forceKill}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
                {sorted.length === 0 && (
                  <tr><td colSpan={5} className="text-center py-8 text-text-secondary">{t.processes.noProcesses}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {selectedProcess && (
        <Card testId="processes-terminate-confirm" className={selectedAction === 'force-kill' ? 'border-accent-yellow/30' : 'border-accent-red/30'}>
          <div className="space-y-3">
            <div>
              <div className="text-base font-semibold text-text-primary">
                {selectedAction === 'force-kill' ? t.processes.forceKillConfirmTitle : t.processes.terminateConfirmTitle}
              </div>
              <div className="mt-1 text-sm text-text-secondary">
                {selectedAction === 'force-kill' ? t.processes.forceKillConfirmDescription : t.processes.terminateConfirmDescription}
              </div>
              <div className="mt-2 text-xs text-text-secondary">{t.processes.terminateWarning(selectedProcess.name, selectedProcess.pid)}</div>
            </div>
            {(selectedAction === 'terminate' ? terminateMutation.isError : forceKillMutation.isError) && (
              <StateBlock title={selectedAction === 'force-kill' ? t.processes.forceKillError : t.processes.terminateError} tone="error" testId="processes-terminate-error" />
            )}
            {(selectedAction === 'terminate' ? terminateMutation.isSuccess : forceKillMutation.isSuccess) && (
              <StateBlock title={selectedAction === 'force-kill' ? t.processes.forceKillQueued : t.processes.terminateQueued} testId="processes-terminate-success" />
            )}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => selectedAction === 'force-kill' ? forceKillMutation.mutate(selectedProcess.pid) : terminateMutation.mutate(selectedProcess.pid)}
                disabled={terminateMutation.isPending || forceKillMutation.isPending}
                className={`rounded px-4 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50 ${
                  selectedAction === 'force-kill'
                    ? 'bg-accent-yellow/20 text-accent-yellow hover:bg-accent-yellow/30'
                    : 'bg-accent-red/20 text-accent-red hover:bg-accent-red/30'
                }`}
              >
                {(terminateMutation.isPending || forceKillMutation.isPending)
                  ? t.common.loading
                  : (selectedAction === 'force-kill' ? t.processes.forceKill : t.processes.terminate)}
              </button>
              <button
                type="button"
                onClick={() => {
                  setSelectedProcess(null);
                  terminateMutation.reset();
                  forceKillMutation.reset();
                }}
                className="rounded border border-border px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-bg-card-hover"
              >
                {t.processes.cancel}
              </button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
