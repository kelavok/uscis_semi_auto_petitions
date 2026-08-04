from __future__ import annotations

from typing import Any


EB1A_TEMPLATE_VARIANTS: dict[str, dict[str, str]] = {
    "base": {
        "label": "Базовый",
        "working_document_template": "templates/EB1A/EB1A_working_document_structure.yaml",
        "llm_template_file": "templates/EB1A/EB1A_unified_template_LLM.txt",
        "human_template_file": "templates/EB1A/!Актуальный шаблон EB1.docx",
        "machine_template_file": "templates/EB1A/EB1A_unified_template_LLM.docx",
    },
    "migrator": {
        "label": "Мигратор",
        "working_document_template": "templates/EB1A/EB1A_migrator_working_document_structure.yaml",
        "llm_template_file": "templates/EB1A/EB1A_migrator_template_LLM.txt",
        "human_template_file": "templates/EB1A/Шаблон МЕМО EB-1A, ver. 1.2.docx",
        "machine_template_file": "templates/EB1A/Шаблон МЕМО EB-1A, ver. 1.2.docx",
    },
}


def normalize_eb1a_template_variant(value: object) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized in {"migrator", "мигратор"}:
        return "migrator"
    return "base"


def eb1a_template_variant(config: dict[str, Any]) -> str:
    if str(config.get("task_type", "")) != "eb1a_petition":
        return "base"
    explicit = str(config.get("eb1a_template_variant", "")).strip()
    if explicit:
        return normalize_eb1a_template_variant(explicit)
    working_template = str(config.get("working_document_template", "")).casefold()
    if "migrator" in working_template or "мигратор" in working_template:
        return "migrator"
    return "base"


def apply_eb1a_template_variant(config: dict[str, Any], variant_value: object) -> int:
    if str(config.get("task_type", "")) != "eb1a_petition":
        return 0
    variant = normalize_eb1a_template_variant(variant_value)
    selected = EB1A_TEMPLATE_VARIANTS[variant]
    updates = {
        "eb1a_template_variant": variant,
        "working_document_template": selected["working_document_template"],
        "eb1a_llm_template_file": selected["llm_template_file"],
        "eb1a_human_template_file": selected["human_template_file"],
    }
    changed = 0
    for key, value in updates.items():
        if config.get(key) != value:
            config[key] = value
            changed += 1
    return changed


def eb1a_machine_template_file(config: dict[str, Any]) -> str:
    variant = eb1a_template_variant(config)
    return EB1A_TEMPLATE_VARIANTS[variant]["machine_template_file"]


def eb1a_variant_source_path(config: dict[str, Any], path_value: str) -> str:
    """Return the EB1A template source file appropriate for the case variant."""
    if str(config.get("task_type", "")) != "eb1a_petition":
        return path_value
    variant = eb1a_template_variant(config)
    selected = EB1A_TEMPLATE_VARIANTS[variant]
    normalized = path_value.replace("\\", "/").casefold()
    if normalized.endswith("templates/eb1a/eb1a_unified_template_llm.txt"):
        return selected["llm_template_file"]
    if normalized.endswith("templates/eb1a/eb1a_unified_template_llm.docx"):
        return selected["machine_template_file"]
    if "актуальный шаблон eb1.docx" in normalized:
        return selected["human_template_file"]
    return path_value
