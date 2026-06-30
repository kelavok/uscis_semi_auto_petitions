# Petitions

Локальная, файлово-управляемая система для поэтапной подготовки иммиграционных меморандумов и независимой сборки PDF-пакетов доказательств.

Сейчас репозиторий находится на **Stage 1 (project skeleton)**. Команды существуют как проверяемые CLI-каркасы, но еще не генерируют юридический текст, не изменяют DOCX и не собирают PDF.

## Основной принцип

Код отвечает за порядок действий, загрузку файлов, валидацию и воспроизводимость. Содержательные правила находятся в редактируемых файлах `instructions/`, `workflows/` и `templates/` и должны загружаться при каждом запуске. После изменения такого файла следующий запуск должен использовать новую версию без изменения Python-кода.

Существующие материалы в `templates/`, `examples/` и `algorythms/` сохранены без изменений. На следующих этапах они будут подключаться через явные пути в workflow, а не зашиваться в код.

## Предлагаемая верхнеуровневая структура

```text
petitions/
  app/                    # Python CLI и нейтральная инфраструктура
  workflows/              # отдельный алгоритм для каждого task type
  instructions/           # универсальные, task-specific и section-specific правила
  schemas/                # редактируемые табличные схемы/примеры
  case_workspace/         # рабочие папки кейсов и модель `_template`
  templates/              # предоставленные шаблоны документов
  examples/               # предоставленные примеры кейсов
  algorythms/              # исходные пользовательские заметки об алгоритмах
  tests/                   # автоматические проверки
```

Верхний уровень предполагается стабильным. Внутренняя структура конкретного кейса может отличаться: фактические пути задаются в `case_config.yaml`, а workflow ссылается на логические роли (`document_index`, `generated_prompts`, `draft_sections`), а не на случайные имена папок.

## Два независимых процесса

### A. Controlled drafting

```powershell
python -m app.draft init-case --case case_001 --task-type eb1a_petition
python -m app.draft build-prompt --case case_001 --step STEP_ID
python -m app.draft import-output --case case_001 --step STEP_ID --file output.json
python -m app.draft insert-section --case case_001 --step STEP_ID
```

Планируемая цепочка: workflow → инструкции → шаблон секции → одобренный индекс → extracted text → prompt → ручной LLM output → валидация → draft section.

Первый provider для MVP — `ManualProvider`: система сохраняет полный prompt в файл и ждет, пока пользователь вручную положит структурированный ответ в case folder. Автоматизация веб-интерфейса ChatGPT не планируется.

API-provider не является обязательной частью проекта. Основной сценарий — без API:
скрипт готовит полный prompt-пакет, пользователь вставляет его в LLM вручную,
сохраняет JSON-ответ локально, а скрипт валидирует и раскладывает результат.

### B. Evidence bundle

```powershell
python -m app.bundle build --case case_001
```

Этот процесс должен читать только одобренные индексы, детерминированно создавать separator pages и собирать PDF. Он не должен вызывать LLM и не зависит от drafting-команд.

## Приоритет инструкций

```text
runtime user instruction
> case-specific instruction
> task-type instruction
> section-specific instruction
> visa/RFE-specific instruction
> universal instruction
> templates/examples
```

На Stage 2 для каждого загруженного фрагмента будет храниться источник и уровень приоритета. Потенциальные содержательные конфликты должны попадать в отчет и останавливать соответствующий drafting step до решения пользователя.

## Модель кейса

Черновик находится в `case_workspace/_template/`. Ключевой файл — `case_config.yaml`; в нем задаются task type, данные заявителя, workflow и относительные пути. Пустые каталоги закреплены файлами `.gitkeep`.

Индексы считаются пользовательскими данными. Будущий re-scan сможет добавлять новые строки и обновлять только автоматически управляемые поля. Поля с ручным управлением (`display_title`, категории, exhibit numbering, порядок и approval) не должны перезаписываться.

## Текущий MVP

- Task type: `eb1a_petition`.
- Первый drafting step: еще не выбран пользователем.
- Юридические критерии и правила не добавлены в workflow от имени системы.
- `templates/EB1A/EB1A_unified_template_LLM.txt` рассматривается как предоставленный источник, но его части еще не размечены по шагам.
- `examples/Kashurin EB1A memorandum.docx` рассматривается как пример результата, не как нормативная инструкция.

## Что будет на Stage 2

После согласования структуры:

1. определить схему и валидатор `case_config.yaml`;
2. утвердить первый EB-1A drafting step;
3. разметить источники инструкций для этого шага;
4. реализовать загрузчик workflow и иерархии инструкций;
5. формализовать поля document/exhibit indexes и правила сохранения ручных правок.

До такого согласования CLI намеренно завершается сообщением `Stage 1 scaffold only`.

## Что уже работает после Stage 2

Минимальный ручной цикл для EB1A уже включен.

1. Создать рабочую папку кейса:

```powershell
python -m app.draft init-case --case case_001 --task-type eb1a_petition
```

Команда создает `case_workspace/case_001`, копирует модельную структуру из
`case_workspace/_template` и добавляет EB1A-папки из
`templates/EB1A/case_folders_template` в `source_documents/originals`.
Если такая папка кейса уже есть, команда останавливается и не перезаписывает ее.

2. Отредактировать `case_config.yaml` внутри папки кейса и положить документы в
нужные подпапки `source_documents/originals`.

3. Просканировать документы, обновить `document_index.csv` и извлечь читаемый
текст:

```powershell
python -m app.draft scan-documents --case case_001
```

Сейчас извлекается текст из `.txt`, `.md`, `.csv`, `.json`, `.yaml`, `.docx`.
PDF поддерживаются как optional layer: если установлен `pdfplumber` или `pypdf`,
система попробует извлечь текст; если зависимостей нет или PDF image-only,
документ останется в индексе, но будет помечен соответствующим
`extraction_status`. Фото и изображения индексируются как `image_or_photo`; для
них нужна ручная расшифровка, описание или читаемый перевод.

Строки с `manual_edit_lock=true` не перезаписываются scanner'ом.

### Manual descriptions для фото, сканов и нечитаемых PDF

Если документ не является машинно-читаемым, `scan-documents` создает заготовку:

```text
manual_descriptions/DOC0001.md
```

В этот файл можно вручную вписать фактическое описание документа. Например:

```markdown
# Manual description for DOC0001

## Description for LLM

The photo shows an award certificate bearing the beneficiary name and the award title.
```

После заполнения нужно снова запустить:

```powershell
python -m app.draft scan-documents --case case_001
```

Если описание заполнено, `document_index.csv` получит
`extraction_status=manual_description_available`, а `build-prompt` будет
вставлять это описание в prompt как доступный текст документа.

Это не OCR и не автоматическое распознавание. Это контролируемый ручной слой для
случаев, когда документ важен, но сам файл не читается LLM.

### Original / translation links

Порядок для bundle: сначала оригинал, потом перевод.

После `scan-documents` можно запустить:

```powershell
python -m app.draft link-translations --case case_001
```

Команда ищет документы в `source_documents/translations` и пытается связать их
с оригиналами из `source_documents/originals` по такой логике:

- та же подпапка роли/эпизода;
- совпадающее имя файла или имя с маркерами вроде `translation`, `english`,
  `перевод`;
- уникальное нормализованное имя внутри того же критерия, даже если перевод
  перемещен или структура подпапок сокращена;
- сопоставление папок эпизодов по сокращениям, транслитерации и сходству
  (`МАП` ↔ `Московская ассоциация предпринимателей`, `NBA_eng` ↔ `NBA_...`);
- консервативное fuzzy-сопоставление имен внутри уже установленного эпизода;
- только однозначные совпадения.

Если пара найдена, в `document_index.csv` у перевода выставляется:

```text
parent_document_id=<document_id оригинала>
relationship_type=translation
translation_status=translation
```

У оригинала сохраняется `translation_status=original`. Если строка залочена
через `manual_edit_lock=true`, автоматическая связка ее не меняет. Если
совпадение неоднозначное или не найдено, команда добавляет note и ждет ручной
правки `parent_document_id`.

Каждый запуск также создает `reports/translation_link_report.csv`: в нем
сохраняются метод и confidence автоматической связи, а для неоднозначных строк
— до трех предлагаемых оригиналов. Один оригинал автоматически связывается не
более чем с одним переводом. Составные переводы, объединяющие несколько
оригиналов, намеренно остаются на ручную проверку.

`build-prompt` показывает LLM эту связь и добавляет подсказку:

```text
bundle_order_hint: original first, then this translation
```

### Exhibit index

После того как в `document_index.csv` вручную проставлены `exhibit_number`,
можно собрать `exhibit_index.csv`:

```powershell
python -m app.bundle build-index --case case_001
```

Команда группирует документы по `exhibit_number` и создает/обновляет строки в
`indexes/exhibit_index.csv`.

Она не назначает exhibit numbers сама. Это намеренно: юридическая структура
пакета остается под ручным контролем.

Внутри каждого exhibit документы упорядочиваются так:

```text
original -> linked translation
```

То есть если `DOC0002` является переводом `DOC0001`, в поле `document_ids`
будет:

```text
DOC0001;DOC0002
```

`manual_edit_lock=true` в `exhibit_index.csv` защищает строку exhibit от
автообновления. В `document_index.csv` команда заполняет `final_bundle_order`
только там, где поле еще пустое и строка не залочена.

### Separator pages

После `build-index` можно сгенерировать технические страницы-разделители:

```powershell
python -m app.bundle separators --case case_001
```

Сейчас они создаются как Markdown-файлы в:

```text
bundle/separators/generated/
```

Для каждого exhibit создается:

```text
001_exhibit_E-1.md
```

Для каждого документа внутри exhibit создается отдельная страница:

```text
001_001_DOC0001.md
001_002_DOC0002.md
```

Exhibit separator содержит список документов exhibit. Document separator
содержит document ID, exhibit number, source file, translation relationship,
описание и notes из `document_index.csv`.

Файлы в `bundle/separators/generated/` считаются автогенерируемыми. Если нужно
ручное редактирование дизайна или текста, лучше копировать их в отдельную папку,
чтобы следующий запуск `separators` не перезаписал изменения.

### Separator PDFs

Markdown-разделители можно отрендерить в PDF:

```powershell
python -m app.bundle separator-pdfs --case case_001
```

Команда читает:

```text
bundle/separators/generated/*.md
```

и пишет:

```text
bundle/separators/pdf/*.pdf
bundle/separators/pdf/manifest.md
```

Для этой команды нужен `reportlab`. В обычном Python его можно поставить через:

```powershell
pip install .[pdf]
```

В Codex bundled runtime `reportlab` уже доступен. Если Poppler (`pdfinfo`,
`pdftoppm`) не работает из-за путей с кириллицей, PDF всё равно можно проверить
через `pypdf`; для визуального рендера лучше использовать ASCII temp path.

### Bundle plan and final PDF merge

Перед финальной сборкой можно построить dry-run plan:

```powershell
python -m app.bundle build --case case_001 --dry-run
```

Команда пишет:

```text
bundle/plan/bundle_plan.csv
bundle/plan/bundle_plan.md
```

План показывает точный порядок:

```text
exhibit separator PDF
document separator PDF
source document
document separator PDF
source translation
```

Если какие-то separator PDFs отсутствуют, source file не найден или формат не
поддержан, это будет отражено в плане. Merge не должен молча пропускать такие
элементы.

Финальная сборка:

```powershell
python -m app.bundle build --case case_001
```

Результат:

```text
bundle/final/evidence_bundle.pdf
```

Сейчас merge поддерживает:

- existing PDF source documents;
- common image files (`jpg`, `png`, `tif`, `bmp`, `webp`) через PDF conversion;
- text/markdown/CSV/JSON/YAML/DOCX через text-to-PDF rendering;
- generated separator PDFs.

Неподдерживаемые форматы блокируют merge и остаются в `bundle_plan.md` как
`unsupported`.

### Проверка состояния кейса

Чтобы не теряться в ручном конвейере:

```powershell
python -m app.draft status --case case_001
```

Команда показывает:

- сколько документов проиндексировано;
- сколько документов уже читаемы для LLM;
- сколько manual descriptions еще ждут заполнения;
- какие fixed draft sections уже имеют prompt / validated output / inserted draft;
- какие repeatable outputs уже валидированы.

### Manual session navigator

Для ручной LLM-сессии есть команда-навигатор:

```powershell
python -m app.draft run-next --case case_001
```

Она не вызывает API и не пишет в LLM. Она смотрит на case workspace и говорит,
что делать дальше:

- заполнить `case_config.yaml`;
- создать prompt;
- скопировать уже созданный prompt в LLM и импортировать JSON;
- вставить validated output в draft section;
- перейти к bundle/status review.

Если следующий шаг — создание prompt, можно сразу создать его:

```powershell
python -m app.draft run-next --case case_001 --build-prompt
```

Для repeatable-шагов команда предлагает только те шаги, которые явно включены в
`enabled_steps` в `case_config.yaml`. Это защита от того, чтобы система сама
решала, какие EB1A-критерии заявлять. Пример:

```yaml
enabled_steps:
  - criterion_awards_episode
  - criterion_original_contribution_fact
  - criterion_original_contribution_significance
```

Если repeatable step включен, `run-next` ищет первую evidence episode folder,
для которой еще нет prompt/output/draft, и показывает точную команду с
`--episode-id` и `--episode-folder`.

4. Собрать prompt для конкретного шага:

```powershell
python -m app.draft build-prompt --case case_001 --step professional_biography
```

Команда создает два файла в `generated_prompts`:

- timestamped prompt, например `professional_biography.20260625_143656.prompt.md`;
- latest prompt, `professional_biography.latest.prompt.md`.

Этот prompt вручную копируется в LLM-чат.

5. Сохранить ответ LLM как JSON в `llm_outputs`, затем импортировать:

```powershell
python -m app.draft import-output --case case_001 --step professional_biography --file llm_outputs/professional_biography.json
```

Команда проверяет обязательные поля, `case_id`, `task_type`, `step_id`,
структуру `used_documents` и сохраняет валидированный JSON в `validated_outputs`.

6. Перенести валидированный текст секции в `draft_sections`:

```powershell
python -m app.draft insert-section --case case_001 --step professional_biography
```

Сейчас `insert-section` работает для шагов с фиксированным `destination`.
Repeatable episode steps для критериев уже поддерживают `--episode-id`.

### Критерий по одному эпизоду

Для repeatable-шагов один prompt должен соответствовать одному эпизоду или
одной фазе эпизода.

Пример для Awards:

```powershell
python -m app.draft build-prompt --case case_001 --step criterion_awards_episode --episode-id 1 --episode-folder "1 episode"
```

`--episode-folder` указывает подпапку внутри evidence role folder. Например:

```text
source_documents/originals/1. Награды/1 episode/
```

Если `--episode-folder` не указан, система попробует подобрать подпапку по
`--episode-id`: `1`, `1 episode`, `1. ...`, `1_...`, `1-...`.

Ответ LLM для repeatable step должен включать `episode_id`:

```json
{
  "case_id": "case_001",
  "task_type": "eb1a_petition",
  "step_id": "criterion_awards_episode",
  "episode_id": "1",
  "draft_text": "...",
  "used_documents": [],
  "unsupported_claims": [],
  "questions_for_user": [],
  "quality_flags": [],
  "revision_notes": []
}
```

Импорт и вставка:

```powershell
python -m app.draft import-output --case case_001 --step criterion_awards_episode --episode-id 1 --file llm_outputs/criterion_awards_episode.1.json
python -m app.draft insert-section --case case_001 --step criterion_awards_episode --episode-id 1
```

Результат сохраняется по `destination_pattern` из workflow, например:

```text
draft_sections/criteria/awards/1.md
```

## Локальный веб-интерфейс

Для ручной работы без API можно запустить браузерный интерфейс поверх тех же
файлов и команд:

```powershell
python -m app.web --host 127.0.0.1 --port 8000
```

После запуска открыть:

```text
http://localhost:8000/
```

Интерфейс позволяет:

- создать рабочую папку кейса;
- просканировать документы и связать переводы с оригиналами;
- увидеть следующий рекомендуемый шаг workflow;
- собрать prompt и скопировать его в LLM вручную;
- вставить JSON-ответ LLM обратно в форму;
- валидировать output и вставить текст в `draft_sections`;
- собрать exhibit index, separator pages и PDF bundle.

Это не автоматизирует веб-интерфейс ChatGPT и не требует API. Система только
готовит полный prompt-пакет, принимает структурированный ответ и раскладывает
результат по файлам кейса.

### Библиотека кейсов и стадии работы

Главная страница автоматически показывает все папки из `case_workspace` (кроме `_template`).
Список не зависит от открытой браузерной сессии: после перезапуска приложения или компьютера
кейсы снова появятся в библиотеке. Кейсы можно искать по ID, фамилии или имени заявителя.

Для каждого кейса интерфейс вычисляет текущую стадию по фактически созданным файлам:
intake, working memorandum, document scan, translation review, LLM drafting, exhibit index и PDF bundle.
Панель `Case progress` показывает, что уже сделано и какой шаг идет следующим.

### Ручное подтверждение переводов

После `Scan documents` и `Link translations` открыть `Review translation links`. Для каждого
неразрешенного перевода можно:

1. открыть сам файл в Windows Explorer;
2. выбрать предложенный оригинал или найти его по имени/пути;
3. при необходимости вставить document ID, относительный либо полный путь к оригиналу;
4. нажать `Confirm translation link`.

Подтвержденная связь сохраняется в `indexes/document_index.csv` и не теряется при повторном
сканировании. Ручное назначение имеет приоритет: если оригинал уже был связан с другим переводом,
прежний перевод автоматически отвязывается и возвращается в очередь ручной проверки. Флажок
`Keep prior links too` нужен только когда один оригинал намеренно имеет несколько переводов.
Автоматический отчет и варианты для проверки сохраняются в `reports/translation_link_report.csv`.

### Intake в веб-интерфейсе

Сохраненные или автоматически определенные EB1A-критерии отображаются отмеченными. Для
оригиналов, переводов и дополнительных документов предусмотрены отдельные пути импорта;
сохраненные внешние пути снова показываются после перезапуска. Кнопка `Open case folder`
открывает рабочую копию соответствующей папки кейса.

После сохранения intake кнопка неактивна, пока пользователь не изменит поле или критерий.
При применении изменений интерфейс предупреждает, что обновится `case_config.yaml`, а новые
файлы будут скопированы в рабочие папки. Существующие документы и ручные связи переводов
не удаляются. После изменения данных или критериев рабочий меморандум следует пересобрать.

`Check next step` только проверяет готовность и сообщает, что требуется дальше.
`Prepare next LLM prompt` создает следующий prompt-файл, но ничего не отправляет в LLM.

### Первый шаг: intake и рабочий Word-файл

Работа над кейсом должна начинаться не с LLM, а с детерминированного создания
рабочего файла:

```powershell
python -m app.draft apply-intake --case case_001 --beneficiary-full-name "Jane Doe" --field "Arts" --specialization "Film production"
python -m app.draft build-working-memo --case case_001
```

`apply-intake` может принять:

- базовые поля через CLI или веб-форму;
- пол/местоимения и точный набор заявленных EB1A-критериев;
- путь к YAML/TXT файлу с `key: value` данными;
- путь к папке с исходными документами, которую нужно скопировать в выбранную
  ветку `source_documents`.

`build-working-memo`:

- парсит machine/LLM-oriented шаблон из `templates/`;
- отдельно читает редактируемый script-oriented шаблон
  `templates/EB1A/EB1A_working_document_structure.yaml`;
- извлекает плейсхолдеры и структуру разделов;
- смотрит `case_config.yaml`;
- смотрит структуру папок evidence / RFE issue folders;
- создает `final_memo/working_memo.md`;
- создает human-readable `final_memo/working_memo.docx`;
- сохраняет отчет `reports/template_parse_report.md`.

Для EB1A первая страница, cover letter и нормативные названия критериев
создаются детерминированно из `EB1A_working_document_structure.yaml`. Критерий
считается присутствующим по `claimed_criteria` либо, если список еще не
утвержден, по наличию реальных файлов внутри соответствующей папки. Пустые
подпапки сами по себе критерием или эпизодом не считаются.

Рабочий `.docx` не является финальной версткой. Это контролируемый human-facing
рабочий файл с заголовками, подзаголовками, видимыми placeholders для LLM
секций и script-generated секций. Финальная polished DOCX-верстка будет
следующим слоем поверх этого файла.

PDF-действия (`Render separator PDFs`, `Build final bundle`) требуют optional
зависимостей `reportlab`/`pypdf`. В Codex-среде они доступны через bundled
Python runtime; в обычном окружении их можно поставить как optional extras.

### O-1B petition track

Create an O-1B case from the local UI or with:

```powershell
python -m app.draft init-case --case artist_001 --task-type o1b_petition
```

The case starts from `templates/O1B/case_folders_template`, uses
`templates/O1B/O1B_company_memo_llm_structure.yaml` as the detailed LLM/legal
instruction source, and builds the human working memorandum from
`templates/O1B/O1B_working_document_structure.yaml` in the order required by
`MEMO O-1В_ver.1.0.docx`.

The O-1B intake records the Arts/MPTV track, petitioner or agent, requested
validity period, U.S. position, compensation, location, duties, and claimed
criteria. The first substantive LLM units are a standalone petitioner/agent
support letter and itinerary, followed by biography, optional recommendation
letters, industry context, criteria, advisory opinion, continued work,
overview, and conclusions.

Place each criterion episode in its own folder. For Criterion (iii), optional
phase subfolders such as `1 role and contribution` and
`2 distinguished reputation` route evidence to two prompts with one shared
episode id. For Criterion (vi), use `1 compensation facts` and
`2 comparison sources`. If phase subfolders are absent, both phases remain
available and receive the full episode as a safe fallback.

## EB1A RFE response track

Для ответа на RFE создан отдельный task type:

```powershell
python -m app.draft init-case --case rfe_001 --task-type eb1a_rfe_response
```

В веб-интерфейсе его можно выбрать как `EB1A RFE response`.

Модель папок:

```text
source_documents/
  rfe/
    notice/                         # полный текст RFE
    issues/                         # куски RFE по issue/episode
  initial_filing/
    memorandum/                     # исходный меморандум / petition letter
    issues/                         # текст initial filing по соответствующим issue
    evidence/                       # документы из первоначальной подачи
  rfe_response/
    new_documents/
      issues/                       # новые документы по issue/episode
      evidence/                     # общие новые документы
    strategy/                       # дополнительные strategy notes
```

Главные редактируемые файлы:

- `user_case_instructions.md` — высший приоритет: стиль, стратегия, запреты, порядок;
- `rfe_response_plan.md` — структура ответа, issue IDs, порядок разделов, episode folders;
- `source_documents/rfe_response/strategy/*.md` — дополнительные заметки стратегии.

Для одного RFE issue используется repeatable step:

```powershell
python -m app.draft build-prompt --case rfe_001 --step rfe_issue_response --episode-id awards_1 --episode-folder "1. Награды/1 episode"
```

Prompt по этому шагу включает:

- RFE text из `source_documents/rfe/issues/<episode_folder>`;
- initial filing text/evidence list из `source_documents/initial_filing/issues/<episode_folder>`;
- new RFE documents из `source_documents/rfe_response/new_documents/issues/<episode_folder>`;
- case/user strategy instructions.

Если в критерии несколько эпизодов, сохраняется правило: один prompt — один episode.
