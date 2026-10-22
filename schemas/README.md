# Index schemas

`document_index.csv` — одна строка на физический или логический документ. `source_fingerprint` и `last_scanned_at` используются при повторном сканировании; `manual_edit_lock` сохраняет пользовательские поля. Изменение или исчезновение locked-источника отражается в `extraction_status`.

`text_extraction_fingerprint` — SHA-256 сохранённого extracted text. У старых кейсов поле может отсутствовать: scanner проверит источник и добавит checksum. `translation_link_mode` хранит `auto`, `manual` или `unlinked`; последнее запрещает восстановление явно отменённой связи автоматическим matcher. Пустое значение сохраняет историческое поведение.

`exhibit_index.csv` — одна строка на exhibit/group/sub-exhibit. `document_ids` содержит список document IDs через `;`. Новые технические CSV-поля обратно совместимы с индексами старых кейсов; JSON-контракт LLM не менялся.
