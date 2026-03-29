# Nullius Failover Runbook

Этот runbook описывает первый честный сценарий `warm standby`, а не полноценный multi-node HA-кластер.

## Что уже умеет продукт

- `primary`-узел:
  - выполняет active response
  - запускает mutating background loops
  - удерживает `primary lock`
- `standby`-узел:
  - остаётся доступным для чтения и health-check
  - не выполняет `block/kill/restart`
  - не запускает mutating background loops

## Предварительные условия

- у обоих узлов одинаковая версия релиза
- backup и restore path проверены заранее
- `deployment.primary_lock_path` указывает на контролируемый путь
- для пары `primary/standby` желательно использовать один и тот же shared lock path, если нужен реальный anti-split-brain guard

## Регулярная проверка готовности

На standby-узле:

```bash
sudo nullius-failover-drill
```

Ожидаемо:

- health API отвечает
- свежий backup создаётся
- backup проходит `nullius-verify-backup`
- `nullius-promote-standby --dry-run` проходит без ошибок

## Осторожный auto-failover

Для standby можно включить оркестратор:

```yaml
failover:
  enabled: true
  primary_api_url: http://10.0.0.10:8000
  failure_threshold: 3
  cooloff_seconds: 600
```

Что он делает:

- запускается по `nullius-failover-orchestrator.timer`
- проверяет `/api/health` у primary
- копит подряд неудачные проверки
- не делает promote, если `primary lock` всё ещё удерживается
- вызывает обычный `nullius-promote-standby`, когда выполнены безопасные условия

Что он не делает:

- не форсирует promote поверх живого lock
- не заменяет quorum / consensus
- не обещает “магический” кластерный failover

## Failover при отказе primary

1. Убедиться, что исходный primary действительно недоступен или изолирован.
2. На standby-узле создать safety snapshot:

```bash
sudo nullius-backup
```

3. Выполнить promote:

```bash
sudo nullius-promote-standby
```

Если lock всё ещё удерживается, а исходный primary гарантированно изолирован, допускается осознанный promote:

```bash
sudo nullius-promote-standby --force
```

4. Проверить роль и health:

```bash
curl http://127.0.0.1:8000/api/health ; echo
curl http://127.0.0.1:8000/api/deployment ; echo
```

Ожидаемо:

- `/api/health` возвращает `status=ok`
- `/api/deployment` показывает `role=primary`

## Что защищает от split-brain

- `primary lock` удерживается только active-узлом
- если lock уже удерживается, второй `primary` не должен стартовать
- `nullius-promote-standby` по умолчанию откажется от promote, если lock всё ещё удерживается
- standby по дизайну не выполняет active response даже при наличии событий

## Чего здесь пока нет

- автоматического сетевого failover
- quorum / consensus
- автоматического выбора нового primary
- multi-node shared database

Это осознанно: текущий этап даёт безопасный `warm standby`, а не декоративное обещание полного HA.
