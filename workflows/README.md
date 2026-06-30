# Workflows

Один YAML-файл описывает один высокоуровневый task type. Workflow определяет последовательность drafting steps и ссылки на редактируемые инструкции/шаблоны, но не должен дублировать большие тексты этих файлов.

Планируемые файлы после EB-1A MVP:

```text
eb1a_petition.yaml
eb2_niw_petition.yaml
o1a_petition.yaml
o1b_petition.yaml
eb1a_rfe.yaml
eb2_niw_rfe.yaml
o1a_rfe.yaml
o1b_rfe.yaml
```

Сейчас активны и проверяются три workflow: `eb1a_petition.yaml`,
`eb1a_rfe_response.yaml` и `o1b_petition.yaml`. Остальные task types остаются планируемыми: создание
кейса для них должно быть включено только после появления и тестирования
соответствующего YAML-файла.
