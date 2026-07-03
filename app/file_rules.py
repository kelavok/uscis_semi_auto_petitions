from pathlib import Path


PROMPT_SIDECAR_NAMES = {"extracts", "info"}


def prompt_sidecar_kind(path: Path) -> str:
    """Return the prompt-only sidecar kind, or an empty string for normal evidence."""
    if not path.is_file() or path.suffix.lower() != ".txt":
        return ""
    stem = path.stem.casefold()
    return stem if stem in PROMPT_SIDECAR_NAMES else ""


def is_prompt_sidecar(path: Path) -> bool:
    return bool(prompt_sidecar_kind(path))


def is_office_temporary_file(path: Path) -> bool:
    """Microsoft Office owner/lock files are not source documents."""
    return path.is_file() and path.name.startswith("~$")


def is_auxiliary_extract(path: Path) -> bool:
    """Backward-compatible predicate for extracts.txt specifically."""
    return prompt_sidecar_kind(path) == "extracts"
