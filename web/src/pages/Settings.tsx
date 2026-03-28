// Страница настроек: только реальные пользовательские настройки интерфейса
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Card } from '../components/ui/Card';
import { IntegrationCard } from '../components/settings/IntegrationCard';
import { useStore } from '../stores/store';
import { api } from '../lib/api';
import { t } from '../lib/i18n';

export function Settings() {
  const { theme, toggleTheme, locale, setLocale } = useStore();
  const qc = useQueryClient();
  const [operationMode, setOperationMode] = useState<'observe' | 'assist' | 'auto_defend'>('auto_defend');
  const [telegramToken, setTelegramToken] = useState('');
  const [slackWebhookUrl, setSlackWebhookUrl] = useState('');
  const [telegramNotifyAutoBlock, setTelegramNotifyAutoBlock] = useState(true);
  const [telegramNotifyHighSeverity, setTelegramNotifyHighSeverity] = useState(false);
  const { data: securityMode } = useQuery({
    queryKey: ['securityMode'],
    queryFn: api.securityMode,
  });
  const { data: telegramSettings } = useQuery({
    queryKey: ['telegramSettings'],
    queryFn: api.telegramSettings,
  });
  const { data: slackSettings } = useQuery({
    queryKey: ['slackSettings'],
    queryFn: api.slackSettings,
  });

  useEffect(() => {
    if (!securityMode) return;
    setOperationMode(securityMode.operation_mode);
  }, [securityMode]);

  useEffect(() => {
    if (!telegramSettings) return;
    setTelegramNotifyAutoBlock(telegramSettings.notify_auto_block);
    setTelegramNotifyHighSeverity(telegramSettings.notify_high_severity);
  }, [telegramSettings]);

  const [slackNotifyAutoBlock, setSlackNotifyAutoBlock] = useState(true);
  const [slackNotifyHighSeverity, setSlackNotifyHighSeverity] = useState(false);

  useEffect(() => {
    if (!slackSettings) return;
    setSlackNotifyAutoBlock(slackSettings.notify_auto_block);
    setSlackNotifyHighSeverity(slackSettings.notify_high_severity);
  }, [slackSettings]);

  const saveTelegramMutation = useMutation({
    mutationFn: () => api.saveTelegramSettings(
      telegramToken.trim(),
      telegramNotifyAutoBlock,
      telegramNotifyHighSeverity,
    ),
    onSuccess: (data) => {
      setTelegramToken('');
      setTelegramNotifyAutoBlock(data.notify_auto_block);
      setTelegramNotifyHighSeverity(data.notify_high_severity);
      qc.invalidateQueries({ queryKey: ['telegramSettings'] });
    },
  });

  const testTelegramMutation = useMutation({
    mutationFn: api.sendTelegramTest,
  });

  const disconnectTelegramMutation = useMutation({
    mutationFn: () => api.saveTelegramSettings('', true, false),
    onSuccess: () => {
      setTelegramToken('');
      setTelegramNotifyAutoBlock(true);
      setTelegramNotifyHighSeverity(false);
      qc.invalidateQueries({ queryKey: ['telegramSettings'] });
    },
  });

  const saveSlackMutation = useMutation({
    mutationFn: () => api.saveSlackSettings(
      slackWebhookUrl.trim(),
      slackNotifyAutoBlock,
      slackNotifyHighSeverity,
    ),
    onSuccess: (data) => {
      setSlackWebhookUrl('');
      setSlackNotifyAutoBlock(data.notify_auto_block);
      setSlackNotifyHighSeverity(data.notify_high_severity);
      qc.invalidateQueries({ queryKey: ['slackSettings'] });
    },
  });

  const testSlackMutation = useMutation({
    mutationFn: api.sendSlackTest,
  });

  const disconnectSlackMutation = useMutation({
    mutationFn: () => api.saveSlackSettings('', true, false),
    onSuccess: () => {
      setSlackWebhookUrl('');
      setSlackNotifyAutoBlock(true);
      setSlackNotifyHighSeverity(false);
      qc.invalidateQueries({ queryKey: ['slackSettings'] });
    },
  });

  const saveSecurityModeMutation = useMutation({
    mutationFn: () => api.saveSecurityMode(operationMode),
    onSuccess: (data) => {
      setOperationMode(data.operation_mode);
      qc.invalidateQueries({ queryKey: ['securityMode'] });
    },
  });

  return (
    <div data-testid="page-settings" className="space-y-6">
      <div className="space-y-1">
        <h1 className="text-xl font-bold">{t.settings.title}</h1>
        <p className="text-sm text-text-secondary">{t.settings.summary}</p>
      </div>

      <Card title={t.settings.appearance} testId="settings-appearance-card">
        <p className="mb-4 text-sm text-text-secondary">{t.settings.appearanceHint}</p>
        <div className="space-y-4">
          <div className="flex items-center justify-between text-sm gap-4">
            <span>{t.settings.language}</span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                data-testid="settings-language-ru"
                onClick={() => setLocale('ru')}
                className={`rounded border px-3 py-1.5 text-sm transition-colors ${
                  locale === 'ru'
                    ? 'border-accent-blue bg-bg-card-hover text-accent-blue'
                    : 'border-border text-text-secondary hover:text-text-primary hover:bg-bg-card-hover'
                }`}
              >
                Русский
              </button>
              <button
                type="button"
                data-testid="settings-language-en"
                onClick={() => setLocale('en')}
                className={`rounded border px-3 py-1.5 text-sm transition-colors ${
                  locale === 'en'
                    ? 'border-accent-blue bg-bg-card-hover text-accent-blue'
                    : 'border-border text-text-secondary hover:text-text-primary hover:bg-bg-card-hover'
                }`}
              >
                English
              </button>
            </div>
          </div>
          <div className="flex items-center justify-between text-sm gap-4">
            <span>{t.settings.theme}</span>
            <button
              data-testid="settings-theme-toggle"
              onClick={toggleTheme}
              className="bg-bg-primary border border-border rounded px-4 py-1.5 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
            >
              {theme === 'dark' ? t.settings.switchToLight : t.settings.switchToDark}
            </button>
          </div>
        </div>
      </Card>

      <Card title={t.settings.operationMode} testId="settings-operation-mode-card">
        <p className="mb-4 text-sm text-text-secondary">{t.settings.operationModeHint}</p>
        <div className="space-y-3">
          {[
            {
              value: 'observe' as const,
              label: t.settings.operationModeObserve,
              hint: t.settings.operationModeObserveDescription,
            },
            {
              value: 'assist' as const,
              label: t.settings.operationModeAssist,
              hint: t.settings.operationModeAssistDescription,
            },
            {
              value: 'auto_defend' as const,
              label: t.settings.operationModeAutoDefend,
              hint: t.settings.operationModeAutoDefendDescription,
            },
          ].map((item) => (
            <label
              key={item.value}
              className={`flex items-start gap-3 rounded border px-4 py-3 transition-colors ${
                operationMode === item.value
                  ? 'border-accent-blue bg-bg-card-hover'
                  : 'border-border hover:bg-bg-card-hover'
              }`}
            >
              <input
                type="radio"
                name="operation-mode"
                value={item.value}
                checked={operationMode === item.value}
                onChange={() => setOperationMode(item.value)}
                className="mt-1"
              />
              <div className="space-y-1">
                <div className="text-sm font-medium text-text-primary">{item.label}</div>
                <div className="text-xs text-text-secondary">{item.hint}</div>
              </div>
            </label>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-3">
          <button
            type="button"
            onClick={() => saveSecurityModeMutation.mutate()}
            className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
          >
            {t.settings.integrationSave}
          </button>
          {saveSecurityModeMutation.isError && (
            <div className="text-xs text-red-300">{t.settings.operationModeSaveError}</div>
          )}
          {saveSecurityModeMutation.isSuccess && (
            <div className="text-xs text-accent-green">{t.settings.operationModeSaved}</div>
          )}
        </div>
      </Card>

      <Card title={t.settings.integrations} testId="settings-integrations-card">
        <p className="mb-4 text-sm text-text-secondary">{t.settings.integrationsHint}</p>
        <div className="space-y-4">
          <IntegrationCard
            title={t.settings.telegram}
            hint={t.settings.telegramHint}
            status={telegramSettings?.configured ? t.settings.telegramConfigured : t.settings.telegramNotConfigured}
            meta={
              <div className="space-y-1">
                <div>
                  {telegramSettings?.chat_bound ? t.settings.telegramChatBound : t.settings.telegramChatWaiting}
                  {telegramSettings?.bot_username ? ` · @${telegramSettings.bot_username}` : ''}
                </div>
                {telegramSettings?.chat_title && (
                  <div>{t.settings.telegramChatLabel}: {telegramSettings.chat_title}</div>
                )}
                <div>{t.settings.telegramStartHint}</div>
                <div>{t.settings.telegramCommands}: {t.settings.telegramCommandsList}</div>
              </div>
            }
            error={telegramSettings?.last_error ? `${t.settings.integrationLastError}: ${telegramSettings.last_error}` : ''}
          >
            <div className="space-y-2">
              <label htmlFor="telegram-token" className="block text-xs text-text-secondary">{t.settings.telegramToken}</label>
              <input
                id="telegram-token"
                type="password"
                value={telegramToken}
                onChange={(evt) => setTelegramToken(evt.target.value)}
                placeholder={t.settings.telegramTokenPlaceholder}
                className="w-full rounded border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
              />
            </div>
            <div className="space-y-2">
              <div className="text-xs text-text-secondary">{t.settings.integrationNotifications}</div>
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={telegramNotifyAutoBlock}
                  onChange={(evt) => setTelegramNotifyAutoBlock(evt.target.checked)}
                />
                <span>{t.settings.notifyAutoBlock}</span>
              </label>
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={telegramNotifyHighSeverity}
                  onChange={(evt) => setTelegramNotifyHighSeverity(evt.target.checked)}
                />
                <span>{t.settings.notifyHighSeverity}</span>
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => saveTelegramMutation.mutate()}
                className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
              >
                {t.settings.integrationSave}
              </button>
              <button
                type="button"
                onClick={() => testTelegramMutation.mutate()}
                disabled={!telegramSettings?.configured || !telegramSettings?.chat_bound}
                className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors disabled:opacity-50"
              >
                {t.settings.integrationSendTest}
              </button>
              <button
                type="button"
                onClick={() => disconnectTelegramMutation.mutate()}
                disabled={!telegramSettings?.configured}
                className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors disabled:opacity-50"
              >
                {t.settings.integrationDisconnect}
              </button>
            </div>
            {(saveTelegramMutation.isError || testTelegramMutation.isError) && (
              <div className="text-xs text-red-300">
                {saveTelegramMutation.isError ? t.settings.telegramSaveError : t.settings.telegramTestError}
              </div>
            )}
            {(saveTelegramMutation.isSuccess || testTelegramMutation.isSuccess) && (
              <div className="text-xs text-accent-green">
                {saveTelegramMutation.isSuccess ? t.settings.telegramSaved : t.settings.telegramTestSent}
              </div>
            )}
          </IntegrationCard>

          <IntegrationCard
            title={t.settings.slack}
            hint={t.settings.slackHint}
            status={slackSettings?.configured ? t.settings.slackConfigured : t.settings.slackNotConfigured}
            error={slackSettings?.last_error ? `${t.settings.integrationLastError}: ${slackSettings.last_error}` : ''}
          >
            <div className="space-y-2">
              <label htmlFor="slack-webhook" className="block text-xs text-text-secondary">{t.settings.slackWebhook}</label>
              <input
                id="slack-webhook"
                type="password"
                value={slackWebhookUrl}
                onChange={(evt) => setSlackWebhookUrl(evt.target.value)}
                placeholder={t.settings.slackWebhookPlaceholder}
                className="w-full rounded border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
              />
            </div>
            <div className="space-y-2">
              <div className="text-xs text-text-secondary">{t.settings.integrationNotifications}</div>
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={slackNotifyAutoBlock}
                  onChange={(evt) => setSlackNotifyAutoBlock(evt.target.checked)}
                />
                <span>{t.settings.notifyAutoBlock}</span>
              </label>
              <label className="flex items-center gap-2 text-sm text-text-secondary">
                <input
                  type="checkbox"
                  checked={slackNotifyHighSeverity}
                  onChange={(evt) => setSlackNotifyHighSeverity(evt.target.checked)}
                />
                <span>{t.settings.notifyHighSeverity}</span>
              </label>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => saveSlackMutation.mutate()}
                className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
              >
                {t.settings.integrationSave}
              </button>
              <button
                type="button"
                onClick={() => testSlackMutation.mutate()}
                disabled={!slackSettings?.configured}
                className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors disabled:opacity-50"
              >
                {t.settings.integrationSendTest}
              </button>
              <button
                type="button"
                onClick={() => disconnectSlackMutation.mutate()}
                disabled={!slackSettings?.configured}
                className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors disabled:opacity-50"
              >
                {t.settings.integrationDisconnect}
              </button>
            </div>
            {(saveSlackMutation.isError || testSlackMutation.isError) && (
              <div className="text-xs text-red-300">
                {saveSlackMutation.isError ? t.settings.slackSaveError : t.settings.slackTestError}
              </div>
            )}
            {(saveSlackMutation.isSuccess || testSlackMutation.isSuccess) && (
              <div className="text-xs text-accent-green">
                {saveSlackMutation.isSuccess ? t.settings.slackSaved : t.settings.slackTestSent}
              </div>
            )}
          </IntegrationCard>
        </div>
      </Card>
    </div>
  );
}
