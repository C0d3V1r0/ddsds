# Nullius Product Roadmap

## v1.1

Цель: сделать Nullius заметно умнее и взрослее без тяжёлого переписывания ядра.

1. Explainable detections
- объяснять, почему сработало событие
- показывать источник сигнала
- показывать уровень уверенности
- давать рекомендуемое действие оператору

2. Incident center light
- группировать одиночные события в инциденты
- показывать `first_seen`, `last_seen`, `affected_ip`, `status`
- ввести статусы `new`, `investigating`, `resolved`

3. Smarter response policy
- разделить `log only`, `review`, `auto block`
- добавить escalation и cooldown
- сделать реакцию зависящей от типа угрозы

4. Better logs investigation
- переход от события к связанным логам
- фильтрация по IP, времени и типу атаки
- подсветка подозрительных фрагментов

5. Host risk score
- единый risk score сервера
- breakdown по сигналам: события, аномалии, процессы, сервисы

## v1.2

Цель: превратить Nullius из умного dashboard в действительно понимающую систему.

6. Modes of operation
- `Observe`
- `Assist`
- `Auto-defend`

7. Service-aware protection
- учитывать профиль хоста: web server, db node, docker host, dev server
- адаптировать detection и response под контекст сервера

8. Process intelligence
- новые и редкие процессы
- подозрительные пути запуска
- подозрительные parent-child цепочки
- rapid respawn поведение

9. Correlation engine
- связывать логи, метрики, процессы и события
- показывать не разрозненные сигналы, а единую картину

10. Response audit trail
- хранить историю решения системы
- фиксировать действие оператора
- показывать итоговый outcome

## v2.0

Цель: сделать Nullius серьёзной security-платформой.

11. Full incident investigation workflow
- отдельная страница инцидента
- evidence
- timeline
- linked logs
- remediation workflow

12. Baseline-aware defense
- учитывать нормальное поведение именно этого хоста
- искать drift относительно baseline

13. Adaptive ML
- развить локальный ML в scoring/correlation слой
- per-host learning
- suppression noisy detections

14. Multi-host evolution
- несколько серверов
- единая панель
- host comparison
- fleet visibility

15. Production-grade ops layer
- backup/restore
- upgrade path
- safer co-hosted deployment
- stronger release engineering

## Приоритет прямо сейчас

Стартуем с `Explainable detections`, потому что это:
- быстро поднимает воспринимаемую “умность” продукта
- усиливает и rule-based, и ML-часть
- создаёт фундамент для `Incident center` и `Host risk score`
