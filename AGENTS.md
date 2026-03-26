# Codex Team Roles

Этот каталог содержит отдельный набор ролей для Codex, собранный как локальный plugin bundle.

## Что внутри

- `.agents/plugins/marketplace.json` - локальный marketplace для подключения плагина
- `plugins/codex-team-roles/.codex-plugin/plugin.json` - manifest плагина
- `plugins/codex-team-roles/skills/*` - отдельные роли для Codex

## Роли

- `$tech-lead`
- `$senior-fullstack-developer`
- `$senior-fullstack-developer-2`
- `$senior-fullstack-developer-3`
- `$qa`
- `$ux-designer`

## Как использовать

Если подключить этот bundle как локальный plugin marketplace, роли можно вызывать по имени навыка, например:

- `Use $tech-lead to decompose this task and prepare an execution plan.`
- `Use $qa to review the implementation and list findings first.`
- `Use $ux-designer to write a text UI spec for this feature.`

Для параллельной разработки можно адресно звать:

- `$senior-fullstack-developer`
- `$senior-fullstack-developer-2`
- `$senior-fullstack-developer-3`
