// - Локализация интерфейса (русский язык)

export const t = {
  // - Общие
  common: {
    loading: 'Загрузка...',
    error: 'Ошибка загрузки данных',
    retry: 'Повторить',
  },

  // - Навигация
  nav: {
    dashboard: 'Обзор',
    security: 'Безопасность',
    processes: 'Процессы',
    logs: 'Логи',
    settings: 'Настройки',
  },

  // - Dashboard
  dashboard: {
    cpu: 'Процессор',
    ram: 'Память',
    disk: 'Диск',
    network: 'Сеть',
    cpuHistory: 'История CPU',
    ramHistory: 'История RAM',
    services: 'Сервисы',
    recentEvents: 'Последние события',
    noServices: 'Нет сервисов',
    noEvents: 'Нет событий',
  },

  // - Security
  security: {
    title: 'Безопасность',
    allTypes: 'Все типы',
    events: 'События безопасности',
    blockIp: 'Блокировка IP',
    blockedIps: 'Заблокированные IP',
    ipAddress: 'IP-адрес',
    reason: 'Причина',
    manualBlock: 'Ручная блокировка',
    block: 'Заблокировать',
    unblock: 'Разблокировать',
    severity: 'Уровень',
    type: 'Тип',
    sourceIp: 'Источник IP',
    description: 'Описание',
    action: 'Действие',
    time: 'Время',
    blocked: 'Заблокирован',
    expires: 'Истекает',
    auto: 'Авто',
    never: 'Никогда',
  },

  // - Processes
  processes: {
    title: 'Процессы',
    searchPlaceholder: 'Поиск по имени или PID...',
    processCount: (n: number) => `${n} процессов`,
    noProcesses: 'Нет процессов',
    pid: 'PID',
    name: 'Имя',
    cpuPercent: 'CPU %',
    ramMb: 'RAM (МБ)',
  },

  // - Logs
  logs: {
    title: 'Логи',
    allSources: 'Все источники',
    searchPlaceholder: 'Поиск в логах...',
    autoScroll: 'Автопрокрутка',
    lineCount: (n: number) => `${n} строк`,
    noLogs: 'Нет логов',
  },

  // - Settings
  settings: {
    title: 'Настройки',
    systemStatus: 'Статус системы',
    apiServer: 'API Сервер',
    agent: 'Агент',
    database: 'База данных',
    appearance: 'Внешний вид',
    theme: 'Тема',
    switchToLight: 'Светлая тема',
    switchToDark: 'Тёмная тема',
    mlModule: 'ML Модуль',
    anomalyDetector: 'Детектор аномалий',
    attackClassifier: 'Классификатор атак',
    mlNote: 'ML-модели обучаются автоматически при достаточном объёме данных.',
    about: 'О системе',
    version: 'Nullius v2.0.0-dev',
    subtitle: 'Иммунная система сервера',
  },

  // - Header
  header: {
    agentConnected: 'Агент подключён',
    agentDisconnected: 'Агент отключён',
  },

  // - Badge/Status
  status: {
    running: 'работает',
    stopped: 'остановлен',
    failed: 'ошибка',
  },

  // - Table
  table: {
    noData: 'Нет данных',
  },
} as const;
