# Frontend flow для Codex

8 агентов для frontend-разработки: согласование плана → реализация → проверка UI через Playwright MCP → независимое ревью → исправления → тексты коммита/MR.

## Установка

Нужны Codex с поддержкой пользовательских агентов, навыков, MCP и lifecycle hooks, доступ к моделям ниже, Python 3.11+, Node.js 22+ и `npx` в PATH.

```sh
git clone https://github.com/alekseiTurl/frontend-flow.git
cd frontend-flow
python scripts/install.py --dry-run --configure-playwright
python scripts/install.py --configure-playwright
```

В Windows вместо `python` можно использовать `py -3`, на macOS/Linux — `python3`. Установка выполняется в `CODEX_HOME` или `~/.codex` и сохраняет сторонние настройки.

После установки разрешите хук через `/hooks` в Codex CLI и начните новый чат. Для UI-проверок нужны запускаемый проект и доступные инструменты Playwright MCP; установка не запускает сервер и не загружает браузеры.

[Подробная установка, обновление и настройка](docs/installation.md).

## Обновление установленного frontend-flow

Откройте терминал в ранее клонированной папке `frontend-flow`. Если в ней есть собственные изменения, сохраните их перед переключением ветки и обновлением. Если папка не сохранилась, клонируйте репозиторий по инструкции выше; повторять первоначальную установку не нужно.

Получите свежую версию и посмотрите список файлов, которые будут обновлены:

```sh
git switch main
git pull --ff-only origin main
python scripts/install.py --dry-run --overwrite --configure-playwright
```

После проверки списка и собственных правок в установленных файлах примените обновление:

```sh
python scripts/install.py --overwrite --configure-playwright
```

Используйте тот же каталог назначения, что при установке: `CODEX_HOME` или `~/.codex`; для нестандартного пути добавьте `--codex-home "/path/to/.codex"` к обеим командам установщика. Если ранее устанавливали общие правила ответов, добавьте к обеим командам `--install-style`.

Заменённые файлы сохраняются в `<CODEX_HOME>/frontend-flow-backups/<timestamp>/`. Сторонние настройки и существующая конфигурация Playwright сохраняются. После обновления проверьте хук через `/hooks` в Codex CLI и начните новый чат. Если в нём остались старые модели или инструкции, перезапустите Codex.

## Использование

`@FF` запускает полный процесс, `@FW` — только Writer.

```text
@FF Добавь фильтрацию товаров. Критерии готовности: ...
@FF Исправь баг: [шаги]. Ожидаю: [результат]. Сейчас: [ошибка].
@FF Продолжи сохранённую задачу по фильтрации.
@FW Подготовь сообщение коммита и описание MR по текущим изменениям.
```

Изменения кода начинаются после согласования плана. При изменении интерфейса обязательна проверка UI. Коммиты, push, публикация MR и deploy требуют поручения пользователя.

[Процесс, отдельные вызовы, продолжение и завершение задач](docs/frontend-flow.md).

## Агенты

| Агент | Модель / усилие |
| --- | --- |
| Architect (`frontend_architect`) | `gpt-6-astra / medium` |
| **Junior Dev** (`junior_dev`) | `gpt-5.6-luna / medium` |
| **Middle Dev** (`middle_dev`) | `gpt-5.6-terra / high` |
| **Senior Dev** (`senior_dev`) | `gpt-6-sol / high` |
| Bugfixer (`frontend_bugfixer`) | `gpt-6-sol / high` |
| Tester (`frontend_tester`) | `gpt-5.6-sol / high` |
| Reviewer (`frontend_reviewer`) | `gpt-6.1-sol / high` |
| Writer (`frontend_writer`) | `gpt-6-luna / low` |

## Разработка комплекта

Metadata ролей — [agents/roles.json](agents/roles.json), инструкции — [references](skills/frontend-flow/references). После их изменения выполните `python scripts/generate_agents.py`. При смене моделей синхронизируйте таблицы в README, [SKILL.md](skills/frontend-flow/SKILL.md) и [инструкции](docs/frontend-flow.md), а также ролевые references.

```sh
python scripts/generate_agents.py --check
python scripts/validate.py
python -m unittest discover -s tests -p "test_*.py" -v
node --test tests/flow.test.cjs
```

Тесты установки используют временные каталоги. [Использованные сторонние материалы](THIRD_PARTY_NOTICES.md).
