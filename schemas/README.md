# Draft index schemas

`document_index.csv` — одна строка на физический или логический документ. `source_fingerprint` и `last_scanned_at` предназначены для re-scan; `manual_edit_lock` должен запрещать автоматическую замену пользовательских полей.

`exhibit_index.csv` — одна строка на exhibit/group/sub-exhibit. `document_ids` временно предлагается хранить как список ID через `|`; до реализации следует решить, нужен ли нормализованный отдельный relation-файл.

Обе схемы — предложения для согласования, не финальный контракт.
