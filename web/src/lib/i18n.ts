// Локализация интерфейса (русский язык)

export const t = {
  // Общие
  common: {
    loading: 'Загрузка...',
    loadingHint: 'Обычно это занимает несколько секунд после открытия страницы.',
    error: 'Ошибка загрузки данных',
    errorHint: 'Проверь статус API и агента, затем обнови страницу.',
    retry: 'Повторить',
    noDataHint: 'Данные появятся автоматически, когда агент отправит следующий снимок.',
  },

  // Навигация
  nav: {
    dashboard: 'Обзор',
    security: 'Безопасность',
    processes: 'Процессы',
    logs: 'Логи',
    settings: 'Настройки',
  },

  // Dashboard
  dashboard: {
    title: 'Обзор системы',
    summary: 'Ключевые метрики, состояние сервисов и последние события безопасности.',
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
    systemState: 'Состояние системы',
    systemHealthy: 'Система работает штатно',
    systemAttention: 'Требуется внимание',
    systemStateHint: 'Проверь статус агента, live-канала и наличие свежих данных.',
  },

  // Безопасность
  security: {
    title: 'Безопасность',
    summary: 'События безопасности, ручные блокировки и список уже заблокированных адресов.',
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
    invalidIp: 'Укажи корректный IPv4 или IPv6 адрес.',
    blockHint: 'Ручная блокировка полезна, когда нужно быстро перекрыть доступ до автодетекта.',
    mutationError: 'Операция не выполнилась. Проверь IP и повтори попытку.',
  },

  // Процессы
  processes: {
    title: 'Процессы',
    summary: 'Текущий снимок активных процессов с сортировкой по CPU, RAM и PID.',
    searchPlaceholder: 'Поиск по имени или PID...',
    processCount: (n: number) => `${n} процессов`,
    noProcesses: 'Нет процессов',
    pid: 'PID',
    name: 'Имя',
    cpuPercent: 'CPU %',
    ramMb: 'RAM (МБ)',
  },

  // Логи
  logs: {
    title: 'Логи',
    allSources: 'Все источники',
    searchPlaceholder: 'Поиск в логах...',
    autoScroll: 'Автопрокрутка',
    lineCount: (n: number) => `${n} строк`,
    noLogs: 'Нет логов',
  },

  // Настройки
  settings: {
    title: 'Настройки',
    summary: 'Сводка по состоянию платформы, внешнему виду и ML-модулю.',
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
    systemStatusHint: 'Если какой-то компонент не работает, сначала проверь его systemd-статус и health API.',
    appearanceHint: 'Переключение темы сохраняется локально в интерфейсе.',
  },

  // Header
  header: {
    statusLabel: 'Статус контура',
    agentConnected: 'Агент подключён',
    agentDisconnected: 'Агент отключён',
    liveConnected: 'Live-канал подключён',
    liveDisconnected: 'Live-канал отключён',
  },

  // Статусы
  status: {
    running: 'работает',
    stopped: 'остановлен',
    failed: 'ошибка',
  },

  // Таблица
  table: {
    noData: 'Нет данных',
    noDataHint: 'Попробуй обновить страницу или подожди следующий цикл сбора.',
  },
} as const;
