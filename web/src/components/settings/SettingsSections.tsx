import type { Dispatch, SetStateAction } from 'react';
import { Card } from '../ui/Card';
import { IntegrationCard } from './IntegrationCard';
import { t } from '../../lib/i18n';
import type { SecurityModeSettings, SlackIntegrationSettings, TelegramIntegrationSettings } from '../../types';

type SeverityLevel = 'low' | 'medium' | 'high' | 'critical';

interface MutationState {
  isError: boolean;
  isSuccess: boolean;
  mutate: () => void;
}

interface AppearanceSettingsCardProps {
  locale: 'ru' | 'en';
  theme: string;
  toggleTheme: () => void;
  setLocale: (locale: 'ru' | 'en') => void;
}

export function AppearanceSettingsCard({
  locale,
  theme,
  toggleTheme,
  setLocale,
}: AppearanceSettingsCardProps) {
  return (
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
  );
}

interface OperationModeSettingsCardProps {
  operationMode: SecurityModeSettings['operation_mode'];
  setOperationMode: Dispatch<SetStateAction<SecurityModeSettings['operation_mode']>>;
  saveMutation: MutationState;
}

export function OperationModeSettingsCard({
  operationMode,
  setOperationMode,
  saveMutation,
}: OperationModeSettingsCardProps) {
  const options = [
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
  ];

  return (
    <Card title={t.settings.operationMode} testId="settings-operation-mode-card">
      <p className="mb-4 text-sm text-text-secondary">{t.settings.operationModeHint}</p>
      <div className="space-y-3">
        {options.map((item) => (
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
          onClick={() => saveMutation.mutate()}
          className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
        >
          {t.settings.integrationSave}
        </button>
        {saveMutation.isError ? <div className="text-xs text-red-300">{t.settings.operationModeSaveError}</div> : null}
        {saveMutation.isSuccess ? <div className="text-xs text-accent-green">{t.settings.operationModeSaved}</div> : null}
      </div>
    </Card>
  );
}

interface DeliveryPolicyState {
  notifyAutoBlock: boolean;
  setNotifyAutoBlock: Dispatch<SetStateAction<boolean>>;
  notifyHighSeverity: boolean;
  setNotifyHighSeverity: Dispatch<SetStateAction<boolean>>;
  notifyMinSeverity: SeverityLevel;
  setNotifyMinSeverity: Dispatch<SetStateAction<SeverityLevel>>;
  quietHoursStart: string;
  setQuietHoursStart: Dispatch<SetStateAction<string>>;
  quietHoursEnd: string;
  setQuietHoursEnd: Dispatch<SetStateAction<string>>;
}

function IntegrationDeliveryFields({
  state,
}: {
  state: DeliveryPolicyState;
}) {
  return (
    <div className="space-y-2">
      <div className="text-xs text-text-secondary">{t.settings.integrationNotifications}</div>
      <label className="flex items-center gap-2 text-sm text-text-secondary">
        <input
          type="checkbox"
          checked={state.notifyAutoBlock}
          onChange={(evt) => state.setNotifyAutoBlock(evt.target.checked)}
        />
        <span>{t.settings.notifyAutoBlock}</span>
      </label>
      <label className="flex items-center gap-2 text-sm text-text-secondary">
        <input
          type="checkbox"
          checked={state.notifyHighSeverity}
          onChange={(evt) => state.setNotifyHighSeverity(evt.target.checked)}
        />
        <span>{t.settings.notifyHighSeverity}</span>
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1 text-sm text-text-secondary">
          <span className="block text-xs">{t.settings.integrationMinSeverity}</span>
          <select
            value={state.notifyMinSeverity}
            onChange={(evt) => state.setNotifyMinSeverity(evt.target.value as SeverityLevel)}
            className="w-full rounded border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
          >
            <option value="low">{t.severity.low}</option>
            <option value="medium">{t.severity.medium}</option>
            <option value="high">{t.severity.high}</option>
            <option value="critical">{t.severity.critical}</option>
          </select>
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="space-y-1 text-sm text-text-secondary">
            <span className="block text-xs">{t.settings.integrationQuietHoursStart}</span>
            <input
              type="time"
              value={state.quietHoursStart}
              onChange={(evt) => state.setQuietHoursStart(evt.target.value)}
              className="w-full rounded border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
            />
          </label>
          <label className="space-y-1 text-sm text-text-secondary">
            <span className="block text-xs">{t.settings.integrationQuietHoursEnd}</span>
            <input
              type="time"
              value={state.quietHoursEnd}
              onChange={(evt) => state.setQuietHoursEnd(evt.target.value)}
              className="w-full rounded border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
            />
          </label>
        </div>
      </div>
    </div>
  );
}

interface TelegramIntegrationSectionProps {
  settings?: TelegramIntegrationSettings;
  token: string;
  setToken: Dispatch<SetStateAction<string>>;
  delivery: DeliveryPolicyState;
  saveMutation: MutationState;
  testMutation: MutationState;
  disconnectMutation: MutationState;
}

function TelegramIntegrationSection({
  settings,
  token,
  setToken,
  delivery,
  saveMutation,
  testMutation,
  disconnectMutation,
}: TelegramIntegrationSectionProps) {
  return (
    <IntegrationCard
      title={t.settings.telegram}
      hint={t.settings.telegramHint}
      status={settings?.configured ? t.settings.telegramConfigured : t.settings.telegramNotConfigured}
      meta={
        <div className="space-y-1">
          <div>
            {settings?.chat_bound ? t.settings.telegramChatBound : t.settings.telegramChatWaiting}
            {settings?.bot_username ? ` · @${settings.bot_username}` : ''}
          </div>
          {settings?.chat_title ? <div>{t.settings.telegramChatLabel}: {settings.chat_title}</div> : null}
          <div>{t.settings.telegramStartHint}</div>
          <div>{t.settings.telegramCommands}: {t.settings.telegramCommandsList}</div>
          <div>{t.settings.integrationQuietHoursHint}</div>
        </div>
      }
      error={settings?.last_error ? `${t.settings.integrationLastError}: ${settings.last_error}` : ''}
    >
      <div className="space-y-2">
        <label htmlFor="telegram-token" className="block text-xs text-text-secondary">{t.settings.telegramToken}</label>
        <input
          id="telegram-token"
          type="password"
          value={token}
          onChange={(evt) => setToken(evt.target.value)}
          placeholder={t.settings.telegramTokenPlaceholder}
          className="w-full rounded border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
        />
      </div>
      <IntegrationDeliveryFields state={delivery} />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
        >
          {t.settings.integrationSave}
        </button>
        <button
          type="button"
          onClick={() => testMutation.mutate()}
          disabled={!settings?.configured || !settings?.chat_bound}
          className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors disabled:opacity-50"
        >
          {t.settings.integrationSendTest}
        </button>
        <button
          type="button"
          onClick={() => disconnectMutation.mutate()}
          disabled={!settings?.configured}
          className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors disabled:opacity-50"
        >
          {t.settings.integrationDisconnect}
        </button>
      </div>
      {saveMutation.isError || testMutation.isError ? (
        <div className="text-xs text-red-300">
          {saveMutation.isError ? t.settings.telegramSaveError : t.settings.telegramTestError}
        </div>
      ) : null}
      {saveMutation.isSuccess || testMutation.isSuccess ? (
        <div className="text-xs text-accent-green">
          {saveMutation.isSuccess ? t.settings.telegramSaved : t.settings.telegramTestSent}
        </div>
      ) : null}
    </IntegrationCard>
  );
}

interface SlackIntegrationSectionProps {
  settings?: SlackIntegrationSettings;
  webhookUrl: string;
  setWebhookUrl: Dispatch<SetStateAction<string>>;
  delivery: DeliveryPolicyState;
  saveMutation: MutationState;
  testMutation: MutationState;
  disconnectMutation: MutationState;
}

function SlackIntegrationSection({
  settings,
  webhookUrl,
  setWebhookUrl,
  delivery,
  saveMutation,
  testMutation,
  disconnectMutation,
}: SlackIntegrationSectionProps) {
  return (
    <IntegrationCard
      title={t.settings.slack}
      hint={t.settings.slackHint}
      status={settings?.configured ? t.settings.slackConfigured : t.settings.slackNotConfigured}
      error={settings?.last_error ? `${t.settings.integrationLastError}: ${settings.last_error}` : ''}
    >
      <div className="space-y-2">
        <label htmlFor="slack-webhook" className="block text-xs text-text-secondary">{t.settings.slackWebhook}</label>
        <input
          id="slack-webhook"
          type="password"
          value={webhookUrl}
          onChange={(evt) => setWebhookUrl(evt.target.value)}
          placeholder={t.settings.slackWebhookPlaceholder}
          className="w-full rounded border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary"
        />
      </div>
      <IntegrationDeliveryFields state={delivery} />
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => saveMutation.mutate()}
          className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors"
        >
          {t.settings.integrationSave}
        </button>
        <button
          type="button"
          onClick={() => testMutation.mutate()}
          disabled={!settings?.configured}
          className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors disabled:opacity-50"
        >
          {t.settings.integrationSendTest}
        </button>
        <button
          type="button"
          onClick={() => disconnectMutation.mutate()}
          disabled={!settings?.configured}
          className="rounded border border-border px-4 py-2 text-sm text-text-primary hover:bg-bg-card-hover transition-colors disabled:opacity-50"
        >
          {t.settings.integrationDisconnect}
        </button>
      </div>
      {saveMutation.isError || testMutation.isError ? (
        <div className="text-xs text-red-300">
          {saveMutation.isError ? t.settings.slackSaveError : t.settings.slackTestError}
        </div>
      ) : null}
      {saveMutation.isSuccess || testMutation.isSuccess ? (
        <div className="text-xs text-accent-green">
          {saveMutation.isSuccess ? t.settings.slackSaved : t.settings.slackTestSent}
        </div>
      ) : null}
    </IntegrationCard>
  );
}

interface IntegrationsSettingsCardProps {
  telegramSettings?: TelegramIntegrationSettings;
  telegramToken: string;
  setTelegramToken: Dispatch<SetStateAction<string>>;
  telegramDelivery: DeliveryPolicyState;
  saveTelegramMutation: MutationState;
  testTelegramMutation: MutationState;
  disconnectTelegramMutation: MutationState;
  slackSettings?: SlackIntegrationSettings;
  slackWebhookUrl: string;
  setSlackWebhookUrl: Dispatch<SetStateAction<string>>;
  slackDelivery: DeliveryPolicyState;
  saveSlackMutation: MutationState;
  testSlackMutation: MutationState;
  disconnectSlackMutation: MutationState;
}

export function IntegrationsSettingsCard(props: IntegrationsSettingsCardProps) {
  return (
    <Card title={t.settings.integrations} testId="settings-integrations-card">
      <p className="mb-4 text-sm text-text-secondary">{t.settings.integrationsHint}</p>
      <div className="space-y-4">
        <TelegramIntegrationSection
          settings={props.telegramSettings}
          token={props.telegramToken}
          setToken={props.setTelegramToken}
          delivery={props.telegramDelivery}
          saveMutation={props.saveTelegramMutation}
          testMutation={props.testTelegramMutation}
          disconnectMutation={props.disconnectTelegramMutation}
        />
        <SlackIntegrationSection
          settings={props.slackSettings}
          webhookUrl={props.slackWebhookUrl}
          setWebhookUrl={props.setSlackWebhookUrl}
          delivery={props.slackDelivery}
          saveMutation={props.saveSlackMutation}
          testMutation={props.testSlackMutation}
          disconnectMutation={props.disconnectSlackMutation}
        />
      </div>
    </Card>
  );
}
