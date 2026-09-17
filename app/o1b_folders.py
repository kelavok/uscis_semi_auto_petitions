"""Resolve numbered O-1B criterion folders without changing source files."""
import re
from pathlib import Path


def resolve_o1b_folders(config: dict, case_dir: Path) -> int:
    if config.get("task_type") != "o1b_petition":
        return 0
    roles = config.get("o1b_folder_roles", {})
    roots = [case_dir / config["paths"][key] for key in
             ("source_originals", "source_translations", "source_other")
             if config.get("paths", {}).get(key)]
    changed = 0
    for role, configured in list(roles.items()):
        match = re.match(r"^([1-7])\.(?!\d)", str(configured))
        if not match or any((root / configured).is_dir() for root in roots):
            continue
        candidates = {child.name for root in roots if root.is_dir()
                      for child in root.iterdir() if child.is_dir()
                      and re.match(rf"^{match[1]}\.(?!\d)", child.name)}
        # Ambiguous numbering must never silently select a criterion folder.
        if len(candidates) == 1:
            roles[role] = candidates.pop()
            changed += 1
    return changed
