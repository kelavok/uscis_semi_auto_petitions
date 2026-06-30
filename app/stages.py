from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .workflow import (
    _case_path_value,
    _normalize_path_list,
    _repeatable_episode_candidates,
    destination_for_step,
    determine_next_action,
    load_case,
    output_stem,
    PromptOptions,
)


CRITERION_LABELS = {
    "awards": "Awards",
    "memberships": "Memberships / associations",
    "media": "Published material / media",
    "judging": "Judging",
    "original_contribution": "Original contribution",
    "scholarly_articles": "Scholarly articles",
    "exhibitions": "Exhibitions",
    "leading_critical_role": "Leading / critical role",
    "high_salary": "High salary",
    "commercial_success": "Commercial success",
    "employment_plan": "Employment plan",
    "lead_starring_productions": "O-1B Criterion (i): lead/starring productions or events",
    "published_recognition": "O-1B Criterion (ii): published recognition",
    "organization_role": "O-1B Criterion (iii): organizational role",
    "commercial_critical_success": "O-1B Criterion (iv): commercial/critical success",
    "significant_recognition": "O-1B Criterion (v): significant recognition",
    "comparable_evidence": "O-1B Arts comparable evidence",
}


@dataclass(frozen=True)
class LLMUnit:
    step_id: str
    title: str
    objective: str
    episode_id: str
    episode_folder: str
    criterion: str
    criterion_label: str
    status: str
    current: bool
    complete: bool
    destination: str
    prompt_ids: tuple[str, ...]
    latest_prompt: str
    output_file: str
    validated_file: str

    @property
    def key(self) -> str:
        return output_stem(self.step_id, self.episode_id)


@dataclass(frozen=True)
class LLMStage:
    case_id: str
    units: tuple[LLMUnit, ...]
    completed_units: int
    total_units: int
    percent: int
    complete: bool
    current_action_type: str
    current_step_id: str
    current_episode_id: str
    current_episode_folder: str
    current_reason: str


def build_llm_stage(case_id: str) -> LLMStage:
    loaded = load_case(case_id)
    action = determine_next_action(loaded)
    steps = loaded.workflow.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    claimed = set(_normalize_path_list(loaded.config.get("claimed_criteria", [])))
    enabled_steps = set(_normalize_path_list(loaded.config.get("enabled_steps", [])))
    disabled_steps = set(_normalize_path_list(loaded.config.get("disabled_steps", [])))
    units: list[LLMUnit] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        step_id = str(step.get("step_id", ""))
        execution = str(step.get("execution", ""))
        if not step_id or execution.startswith("deterministic") or step_id in disabled_steps:
            continue
        criterion = _criterion_for_step(step_id, step)
        if (
            str(loaded.config.get("task_type", "")) == "o1b_petition"
            and str(loaded.config.get("o1b_track", "")) == "mptv"
            and criterion == "comparable_evidence"
        ):
            continue
        if criterion and criterion != "employment_plan" and claimed and criterion not in claimed:
            continue
        if "repeatable" in execution:
            if enabled_steps and step_id not in enabled_steps:
                continue
            candidates = _repeatable_episode_candidates(loaded, step)
            for episode_id, episode_folder in candidates:
                units.append(
                    _build_unit(
                        loaded.case_dir,
                        loaded.config,
                        step,
                        episode_id,
                        episode_folder,
                        criterion,
                        action,
                    )
                )
        else:
            units.append(_build_unit(loaded.case_dir, loaded.config, step, "", "", criterion, action))
    completed = sum(unit.complete for unit in units)
    total = len(units)
    percent = round((completed / total) * 100) if total else 100
    return LLMStage(
        case_id=case_id,
        units=tuple(units),
        completed_units=completed,
        total_units=total,
        percent=percent,
        complete=total == completed,
        current_action_type=action.action_type,
        current_step_id=action.step_id,
        current_episode_id=action.episode_id,
        current_episode_folder=action.episode_folder,
        current_reason=action.reason,
    )


def _build_unit(
    case_dir: Path,
    config: dict[str, Any],
    step: dict[str, Any],
    episode_id: str,
    episode_folder: str,
    criterion: str,
    action: Any,
) -> LLMUnit:
    step_id = str(step.get("step_id", ""))
    options = PromptOptions(episode_id=episode_id, episode_folder=episode_folder)
    destination = destination_for_step(step, options)
    destination_path = case_dir / destination if destination else Path("__missing__")
    stem = output_stem(step_id, episode_id)
    prompt_root = case_dir / _case_path_value(config, "generated_prompts")
    output_root = case_dir / _case_path_value(config, "llm_outputs")
    validated_root = case_dir / _case_path_value(config, "validated_outputs")
    prompt_paths = sorted(
        (
            path
            for path in prompt_root.glob(f"{stem}.*.prompt.md")
            if not path.name.endswith(".latest.prompt.md")
        ),
        key=lambda path: path.stat().st_mtime,
    )
    latest_prompt_path = prompt_root / f"{stem}.latest.prompt.md"
    output_path = output_root / f"{stem}.json"
    validated_path = validated_root / f"{stem}.json"
    complete = bool(destination and destination_path.exists())
    if complete:
        status = "completed"
    elif validated_path.exists():
        status = "validated"
    elif output_path.exists():
        status = "output_received"
    elif latest_prompt_path.exists():
        status = "waiting_for_output"
    else:
        status = "pending"
    current = action.step_id == step_id and (action.episode_id or "") == episode_id
    return LLMUnit(
        step_id=step_id,
        title=str(step.get("title", step_id)),
        objective=str(step.get("objective", "")).strip(),
        episode_id=episode_id,
        episode_folder=episode_folder,
        criterion=criterion,
        criterion_label=CRITERION_LABELS.get(criterion, "General memorandum section"),
        status=status,
        current=current,
        complete=complete,
        destination=destination,
        prompt_ids=tuple(path.name for path in prompt_paths),
        latest_prompt=latest_prompt_path.name if latest_prompt_path.exists() else "",
        output_file=output_path.name if output_path.exists() else "",
        validated_file=validated_path.name if validated_path.exists() else "",
    )


def _criterion_for_step(step_id: str, step: dict[str, Any]) -> str:
    mapping = (
        ("o1b_criterion_vi", "high_salary"),
        ("o1b_criterion_iii", "organization_role"),
        ("o1b_criterion_iv", "commercial_critical_success"),
        ("o1b_criterion_v", "significant_recognition"),
        ("o1b_criterion_ii", "published_recognition"),
        ("o1b_criterion_i", "lead_starring_productions"),
        ("o1b_comparable_evidence", "comparable_evidence"),
        ("criterion_original_contribution", "original_contribution"),
        ("criterion_leading_critical_role", "leading_critical_role"),
        ("criterion_scholarly_articles", "scholarly_articles"),
        ("criterion_commercial_success", "commercial_success"),
        ("criterion_memberships", "memberships"),
        ("criterion_high_salary", "high_salary"),
        ("criterion_exhibitions", "exhibitions"),
        ("criterion_awards", "awards"),
        ("criterion_media", "media"),
        ("criterion_judging", "judging"),
        ("employment_plan", "employment_plan"),
    )
    for prefix, criterion in mapping:
        if step_id.startswith(prefix):
            return criterion
    roles = step.get("evidence_folder_roles", [])
    if isinstance(roles, list) and len(roles) == 1 and str(roles[0]) in CRITERION_LABELS:
        return str(roles[0])
    return ""
