# Промпт для начала реализации Nullius v2

Скопируй это сообщение и отправь ИИ, чтобы начать реализацию:

---

Мы разработали полную спецификацию и план реализации проекта **Nullius v2** — self-hosted security-платформы для Ubuntu/Debian серверов. Все документы лежат в проекте:

## Документация

- **Спецификация:** `docs/superpowers/specs/2026-03-25-nullius-v2-design.md`
- **Phase 1 — FastAPI Backend:** `docs/superpowers/plans/2026-03-25-nullius-v2-phase1-backend.md`
- **Phase 2 — Go Agent:** `docs/superpowers/plans/2026-03-25-nullius-v2-phase2-go-agent.md`
- **Phase 3 — React Frontend:** `docs/superpowers/plans/2026-03-25-nullius-v2-phase3-frontend.md`
- **Phase 4 — ML Module:** `docs/superpowers/plans/2026-03-25-nullius-v2-phase4-ml.md`
- **Phase 5 — Deployment:** `docs/superpowers/plans/2026-03-25-nullius-v2-phase5-deployment.md`

## Что нужно сделать

1. Прочитай спецификацию и план Phase 1 (Backend)
2. Начни реализацию Phase 1 строго по плану — task за task, step за step
3. Используй TDD: сначала тест, потом реализация
4. Коммить после каждого task
5. После завершения Phase 1 перейди к Phase 2 и так далее

## Важные правила

- **Не отклоняйся от плана** — все решения уже приняты в спеке
- **Код пиши в директории проекта:** `/Users/t00r1/Desktop/Projects /Nullius/`
- **Старый код в проекте удали** — мы начинаем с нуля
- **Стиль кода:** функциональный, без ООП (кроме ML-моделей и Pydantic)
- **Комментарии на русском** с форматом `# - описание`
- **Язык общения:** русский
- **Фазы выполнять последовательно**, каждая зависит от предыдущей

Начинай с Phase 1, Task 1. Поехали.
