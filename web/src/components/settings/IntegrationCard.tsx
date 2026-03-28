import type { ReactNode } from 'react';

interface IntegrationCardProps {
  title: string;
  hint: string;
  status: string;
  meta?: ReactNode;
  error?: string;
  children: ReactNode;
}

export function IntegrationCard({
  title,
  hint,
  status,
  meta,
  error,
  children,
}: IntegrationCardProps) {
  return (
    <div className="rounded-lg border border-border bg-bg-primary/40 px-4 py-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-sm font-semibold text-text-primary">{title}</div>
          <div className="text-xs text-text-secondary">{hint}</div>
        </div>
        <div className="text-xs text-text-secondary">{status}</div>
      </div>

      {meta && <div className="mt-3 text-xs text-text-secondary">{meta}</div>}
      {error && (
        <div className="mt-3 rounded border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-xs text-red-200">
          {error}
        </div>
      )}

      <div className="mt-4 space-y-4">{children}</div>
    </div>
  );
}
