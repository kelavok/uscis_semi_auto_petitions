from pathlib import Path


PROMPT_CONTEXT_SIDECAR_NAMES = {"info", "readme"}
PROMPT_CONTEXT_SIDECAR_SUFFIXES = {".txt", ".md"}


def prompt_sidecar_kind(path: Path) -> str:
    """Return the prompt-only sidecar kind, or an empty string for normal evidence."""
    stem = path.stem.casefold()
    suffix = path.suffix.casefold()
    if stem == "extracts" and suffix == ".txt":
        return "extracts"
    if stem in PROMPT_CONTEXT_SIDECAR_NAMES and suffix in PROMPT_CONTEXT_SIDECAR_SUFFIXES:
        return stem
    return ""


def is_prompt_sidecar(path: Path) -> bool:
    return bool(prompt_sidecar_kind(path))


def is_office_temporary_file(path: Path) -> bool:
    """Microsoft Office owner/lock files are not source documents."""
    return path.is_file() and path.name.startswith("~$")


def is_auxiliary_extract(path: Path) -> bool:
    """Backward-compatible predicate for extracts.txt specifically."""
    return prompt_sidecar_kind(path) == "extracts"
