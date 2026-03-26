import { t } from '../../lib/i18n';

interface StateBlockProps {
  title: string;
  description?: string;
  tone?: 'neutral' | 'error';
  testId?: string;
}

export function StateBlock({
  title,
  description,
  tone = 'neutral',
  testId,
}: StateBlockProps) {
  const toneClass = tone === 'error'
    ? 'border-accent-red/30 bg-accent-red/8 text-accent-red'
    : 'border-border bg-bg-card text-text-secondary';

  return (
    <div
      data-testid={testId}
      className={`rounded-lg border px-4 py-3 text-sm ${toneClass}`}
    >
      <div className="font-medium">{title}</div>
      {description && (
        <div className={`mt-1 text-xs ${tone === 'error' ? 'text-accent-red/80' : 'text-text-secondary/80'}`}>
          {description}
        </div>
      )}
    </div>
  );
}

export function LoadingBlock({ testId }: { testId?: string }) {
  return (
    <StateBlock
      testId={testId}
      title={t.common.loading}
      description={t.common.loadingHint}
    />
  );
}

export function ErrorBlock({ testId }: { testId?: string }) {
  return (
    <StateBlock
      testId={testId}
      title={t.common.error}
      description={t.common.errorHint}
      tone="error"
    />
  );
}
