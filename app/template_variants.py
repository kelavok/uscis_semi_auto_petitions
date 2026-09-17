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


EB1A_RFE_TEMPLATE_VARIANTS: dict[str, dict[str, str]] = {
    "base": {
        "label": "Базовый",
        "human_template_file": "templates/RFE/EB1/rfe draft template.docx",
        "llm_template_file": "templates/RFE/EB1/EB1A_RFE_response_unified_LLM_template.yaml",
        "strategy_schema_file": "schemas/rfe_strategy_output.schema.json",
        "bootstrap_instructions_file": "instructions/task_types/eb1a_rfe_response/strategy_bootstrap.md",
        "task_rules_file": "instructions/task_types/eb1a_rfe_response/task_rules.md",
    },
    "migrator": {
        "label": "Мигратор",
        "human_template_file": "templates/RFE/EB1/Шаблон ответа на RFE EB-1A ver.1.0.docx",
        "llm_template_file": "templates/RFE/EB1/EB1A_RFE_response_migrator_LLM_template.yaml",
        "strategy_schema_file": "schemas/rfe_migrator_strategy_output.schema.json",
        "bootstrap_instructions_file": "instructions/task_types/eb1a_rfe_response/strategy_bootstrap_migrator.md",
        "task_rules_file": "instructions/task_types/eb1a_rfe_response/task_rules_migrator.md",
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


def normalize_eb1a_rfe_template_variant(value: object) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized in {"migrator", "мигратор"}:
        return "migrator"
    return "base"


def eb1a_rfe_template_variant(config: dict[str, Any]) -> str:
    if str(config.get("task_type", "")) != "eb1a_rfe_response":
        return "base"
    explicit = str(config.get("eb1a_rfe_template_variant", "")).strip()
    if explicit:
        return normalize_eb1a_rfe_template_variant(explicit)
    response = config.get("rfe_response", {})
    if isinstance(response, dict):
        template = " ".join(
            str(response.get(key, "")) for key in ("template_file", "human_template_file")
        ).casefold()
        if "migrator" in template or "шаблон ответа на rfe eb-1a" in template:
            return "migrator"
    return "base"


def apply_eb1a_rfe_template_variant(config: dict[str, Any], variant_value: object) -> int:
    if str(config.get("task_type", "")) != "eb1a_rfe_response":
        return 0
    variant = normalize_eb1a_rfe_template_variant(variant_value)
    selected = EB1A_RFE_TEMPLATE_VARIANTS[variant]
    changed = 0
    if config.get("eb1a_rfe_template_variant") != variant:
        config["eb1a_rfe_template_variant"] = variant
        changed += 1
    response = config.get("rfe_response")
    if not isinstance(response, dict):
        response = {}
        config["rfe_response"] = response
        changed += 1
    for key, source_key in (
        ("template_file", "llm_template_file"),
        ("human_template_file", "human_template_file"),
    ):
        value = selected[source_key]
        if response.get(key) != value:
            response[key] = value
            changed += 1
    return changed


def eb1a_rfe_machine_template_file(config: dict[str, Any]) -> str:
    variant = eb1a_rfe_template_variant(config)
    return EB1A_RFE_TEMPLATE_VARIANTS[variant]["llm_template_file"]


def eb1a_rfe_variant_source_path(config: dict[str, Any], path_value: str) -> str:
    """Return the EB-1A RFE instruction/template source for the selected variant."""
    if str(config.get("task_type", "")) != "eb1a_rfe_response":
        return path_value
    selected = EB1A_RFE_TEMPLATE_VARIANTS[eb1a_rfe_template_variant(config)]
    normalized = path_value.replace("\\", "/").casefold()
    if normalized.endswith("templates/rfe/eb1/eb1a_rfe_response_unified_llm_template.yaml"):
        return selected["llm_template_file"]
    if normalized.endswith("instructions/task_types/eb1a_rfe_response/task_rules.md"):
        return selected["task_rules_file"]
    return path_value
