# Nullius Release Checklist

Минимальный чек-лист перед тем, как считать сборку готовой к MVP-использованию.

## 1. Локальные проверки

```bash
cd server && ./venv/bin/pytest -q
cd ../agent && go test ./...
cd ../web && npm run build
```

Ожидаемо:
- все тесты зелёные
- frontend build проходит без ошибок

## 2. Сборка релиза

```bash
./deploy/build.sh
```

Ожидаемо:
- в `dist/` появились `install.sh`, `uninstall.sh`, `server.tar.gz`, frontend assets и оба бинарника агента

## 3. Чистая переустановка

```bash
cd dist
./uninstall.sh
./install.sh
```

Ожидаемо:
- установка завершается без ручных hotfix
- пароль администратора сохранён в `/opt/nullius/config/.initial_password`
- если в конфиге включён `api.require_bearer_auth`, задан отдельный `api.token` или `NULLIUS_API_TOKEN`
- если включён `api.require_ws_token`, задан отдельный `api.ws_token` / `NULLIUS_WS_TOKEN` или осознанно используется UI API token
- nginx применяет rate limiting через `conf.d/nullius-limits.conf`
- `/ws/agent` закрыт allowlist'ом в `snippets/nullius-agent-allowlist.conf`; если нужен внешний агент, туда явно добавлена только доверенная подсеть

## 4. Runtime health

```bash
curl http://127.0.0.1:8000/api/health ; echo
systemctl status nullius-api nullius-agent --no-pager -l
```

Ожидаемо:

```json
{"status":"ok","agent":"connected","db":"ok"}
```

- оба systemd-сервиса активны

## 5. Smoke + E2E

```bash
python3 testing/smoke/mvp_smoke.py
./testing/run_mvp_suite.sh
```

Ожидаемо:
- `=== Smoke passed ===`
- `=== MVP suite passed ===`

Если нужен полный destructive acceptance на живом стенде:

```bash
sudo ./testing/run_release_acceptance.sh --destructive
```

## 6. Ручная проверка UI

Проверить:
- `Обзор`: графики и host-метрики читаются без наложения подписей
- `Система`: статусы API/agent/db, ML-состояния и причины ожидания/обучения показываются корректно
- `Безопасность`: события, блокировка/разблокировка IP, корректные action labels (`logged`, `review_required`, `auto_block`)
- `Процессы`: список процессов, `Завершить` и `Убить` доступны только для обычных процессов
- `Логи`: новые записи появляются, фильтр по диапазону времени работает
- `Настройки`: переключение темы и языка

## 7. Перезагрузка сервера

```bash
reboot
```

После перезагрузки снова проверить:

```bash
curl http://127.0.0.1:8000/api/health ; echo
./testing/run_mvp_suite.sh
```

Если все пункты зелёные, сборку можно считать release-ready на уровне MVP.
