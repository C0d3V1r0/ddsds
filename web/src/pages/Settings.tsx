// Страница настроек: только реальные пользовательские настройки интерфейса
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AppearanceSettingsCard,
  IntegrationsSettingsCard,
  OperationModeSettingsCard,
} from '../components/settings/SettingsSections';
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
  const [telegramNotifyMinSeverity, setTelegramNotifyMinSeverity] = useState<'low' | 'medium' | 'high' | 'critical'>('high');
  const [telegramQuietHoursStart, setTelegramQuietHoursStart] = useState('');
  const [telegramQuietHoursEnd, setTelegramQuietHoursEnd] = useState('');
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
    setTelegramNotifyMinSeverity(telegramSettings.notify_min_severity);
    setTelegramQuietHoursStart(telegramSettings.quiet_hours_start);
    setTelegramQuietHoursEnd(telegramSettings.quiet_hours_end);
  }, [telegramSettings]);

  const [slackNotifyAutoBlock, setSlackNotifyAutoBlock] = useState(true);
  const [slackNotifyHighSeverity, setSlackNotifyHighSeverity] = useState(false);
  const [slackNotifyMinSeverity, setSlackNotifyMinSeverity] = useState<'low' | 'medium' | 'high' | 'critical'>('high');
  const [slackQuietHoursStart, setSlackQuietHoursStart] = useState('');
  const [slackQuietHoursEnd, setSlackQuietHoursEnd] = useState('');

  useEffect(() => {
    if (!slackSettings) return;
    setSlackNotifyAutoBlock(slackSettings.notify_auto_block);
    setSlackNotifyHighSeverity(slackSettings.notify_high_severity);
    setSlackNotifyMinSeverity(slackSettings.notify_min_severity);
    setSlackQuietHoursStart(slackSettings.quiet_hours_start);
    setSlackQuietHoursEnd(slackSettings.quiet_hours_end);
  }, [slackSettings]);

  const saveTelegramMutation = useMutation({
    mutationFn: () => api.saveTelegramSettings(
      telegramToken.trim(),
      telegramNotifyAutoBlock,
      telegramNotifyHighSeverity,
      telegramNotifyMinSeverity,
      telegramQuietHoursStart,
      telegramQuietHoursEnd,
    ),
    onSuccess: (data) => {
      setTelegramToken('');
      setTelegramNotifyAutoBlock(data.notify_auto_block);
      setTelegramNotifyHighSeverity(data.notify_high_severity);
      setTelegramNotifyMinSeverity(data.notify_min_severity);
      setTelegramQuietHoursStart(data.quiet_hours_start);
      setTelegramQuietHoursEnd(data.quiet_hours_end);
      qc.invalidateQueries({ queryKey: ['telegramSettings'] });
    },
  });

  const testTelegramMutation = useMutation({
    mutationFn: api.sendTelegramTest,
  });

  const disconnectTelegramMutation = useMutation({
    mutationFn: () => api.saveTelegramSettings('', true, false, 'high', '', ''),
    onSuccess: () => {
      setTelegramToken('');
      setTelegramNotifyAutoBlock(true);
      setTelegramNotifyHighSeverity(false);
      setTelegramNotifyMinSeverity('high');
      setTelegramQuietHoursStart('');
      setTelegramQuietHoursEnd('');
      qc.invalidateQueries({ queryKey: ['telegramSettings'] });
    },
  });

  const saveSlackMutation = useMutation({
    mutationFn: () => api.saveSlackSettings(
      slackWebhookUrl.trim(),
      slackNotifyAutoBlock,
      slackNotifyHighSeverity,
      slackNotifyMinSeverity,
      slackQuietHoursStart,
      slackQuietHoursEnd,
    ),
    onSuccess: (data) => {
      setSlackWebhookUrl('');
      setSlackNotifyAutoBlock(data.notify_auto_block);
      setSlackNotifyHighSeverity(data.notify_high_severity);
      setSlackNotifyMinSeverity(data.notify_min_severity);
      setSlackQuietHoursStart(data.quiet_hours_start);
      setSlackQuietHoursEnd(data.quiet_hours_end);
      qc.invalidateQueries({ queryKey: ['slackSettings'] });
    },
  });

  const testSlackMutation = useMutation({
    mutationFn: api.sendSlackTest,
  });

  const disconnectSlackMutation = useMutation({
    mutationFn: () => api.saveSlackSettings('', true, false, 'high', '', ''),
    onSuccess: () => {
      setSlackWebhookUrl('');
      setSlackNotifyAutoBlock(true);
      setSlackNotifyHighSeverity(false);
      setSlackNotifyMinSeverity('high');
      setSlackQuietHoursStart('');
      setSlackQuietHoursEnd('');
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
      <AppearanceSettingsCard locale={locale} theme={theme} toggleTheme={toggleTheme} setLocale={setLocale} />
      <OperationModeSettingsCard
        operationMode={operationMode}
        setOperationMode={setOperationMode}
        saveMutation={saveSecurityModeMutation}
      />
      <IntegrationsSettingsCard
        telegramSettings={telegramSettings}
        telegramToken={telegramToken}
        setTelegramToken={setTelegramToken}
        telegramDelivery={{
          notifyAutoBlock: telegramNotifyAutoBlock,
          setNotifyAutoBlock: setTelegramNotifyAutoBlock,
          notifyHighSeverity: telegramNotifyHighSeverity,
          setNotifyHighSeverity: setTelegramNotifyHighSeverity,
          notifyMinSeverity: telegramNotifyMinSeverity,
          setNotifyMinSeverity: setTelegramNotifyMinSeverity,
          quietHoursStart: telegramQuietHoursStart,
          setQuietHoursStart: setTelegramQuietHoursStart,
          quietHoursEnd: telegramQuietHoursEnd,
          setQuietHoursEnd: setTelegramQuietHoursEnd,
        }}
        saveTelegramMutation={saveTelegramMutation}
        testTelegramMutation={testTelegramMutation}
        disconnectTelegramMutation={disconnectTelegramMutation}
        slackSettings={slackSettings}
        slackWebhookUrl={slackWebhookUrl}
        setSlackWebhookUrl={setSlackWebhookUrl}
        slackDelivery={{
          notifyAutoBlock: slackNotifyAutoBlock,
          setNotifyAutoBlock: setSlackNotifyAutoBlock,
          notifyHighSeverity: slackNotifyHighSeverity,
          setNotifyHighSeverity: setSlackNotifyHighSeverity,
          notifyMinSeverity: slackNotifyMinSeverity,
          setNotifyMinSeverity: setSlackNotifyMinSeverity,
          quietHoursStart: slackQuietHoursStart,
          setQuietHoursStart: setSlackQuietHoursStart,
          quietHoursEnd: slackQuietHoursEnd,
          setQuietHoursEnd: setSlackQuietHoursEnd,
        }}
        saveSlackMutation={saveSlackMutation}
        testSlackMutation={testSlackMutation}
        disconnectSlackMutation={disconnectSlackMutation}
      />
    </div>
  );
}
