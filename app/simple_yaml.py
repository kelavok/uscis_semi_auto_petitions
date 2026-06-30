from __future__ import annotations

from typing import Any


def load_yaml_subset(text: str) -> Any:
    """Parse the small YAML subset used by this project.

    This is intentionally conservative. If PyYAML is installed, app.workflow
    uses it instead. The fallback exists so the MVP works on a clean Windows
    Python where PyYAML is not yet installed.
    """

    lines = text.splitlines()
    return _parse_block(lines, 0, 0)[0]


def _parse_block(lines: list[str], index: int, indent: int) -> tuple[Any, int]:
    index = _skip_ignorable(lines, index)
    if index >= len(lines):
        return {}, index
    current_indent = _indent_of(lines[index])
    if current_indent < indent:
        return {}, index
    if lines[index].lstrip().startswith("- "):
        return _parse_list(lines, index, current_indent)
    return _parse_dict(lines, index, current_indent)


def _parse_dict(lines: list[str], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        index = _skip_ignorable(lines, index)
        if index >= len(lines):
            break
        line = lines[index]
        current_indent = _indent_of(line)
        if current_indent < indent:
            break
        if current_indent > indent:
            break
        stripped = line.strip()
        if stripped.startswith("- "):
            break
        key, raw_value = _split_key_value(stripped)
        if raw_value in {">", "|"}:
            value, index = _collect_block_scalar(lines, index + 1, current_indent, folded=raw_value == ">")
        elif raw_value == "":
            child_index = _skip_ignorable(lines, index + 1)
            if (
                child_index < len(lines)
                and _indent_of(lines[child_index]) == current_indent
                and lines[child_index].lstrip().startswith("- ")
            ):
                value, index = _parse_list(lines, child_index, current_indent)
            else:
                value, index = _parse_block(lines, child_index, current_indent + 2)
        else:
            value = _parse_scalar(raw_value)
            index += 1
        result[key] = value
    return result, index


def _parse_list(lines: list[str], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        index = _skip_ignorable(lines, index)
        if index >= len(lines):
            break
        line = lines[index]
        current_indent = _indent_of(line)
        if current_indent < indent:
            break
        if current_indent != indent or not line.lstrip().startswith("- "):
            break
        rest = line.strip()[2:].strip()
        if rest == "":
            value, index = _parse_block(lines, index + 1, indent + 2)
            result.append(value)
            continue
        if ":" in rest and not rest.startswith(("'", '"')):
            key, raw_value = _split_key_value(rest)
            item: dict[str, Any] = {}
            if raw_value in {">", "|"}:
                item[key], index = _collect_block_scalar(
                    lines, index + 1, current_indent, folded=raw_value == ">"
                )
            elif raw_value == "":
                item[key], index = _parse_block(lines, index + 1, indent + 2)
            else:
                item[key] = _parse_scalar(raw_value)
                index += 1
            extra, index = _parse_dict(lines, index, indent + 2)
            item.update(extra)
            result.append(item)
        else:
            result.append(_parse_scalar(rest))
            index += 1
    return result, index


def _collect_block_scalar(
    lines: list[str], index: int, parent_indent: int, *, folded: bool
) -> tuple[str, int]:
    collected: list[str] = []
    while index < len(lines):
        line = lines[index]
        if line.strip() == "":
            collected.append("")
            index += 1
            continue
        current_indent = _indent_of(line)
        if current_indent <= parent_indent:
            break
        collected.append(line[parent_indent + 2 :].rstrip())
        index += 1
    if folded:
        return " ".join(part.strip() for part in collected if part.strip()), index
    return "\n".join(collected).strip(), index


def _skip_ignorable(lines: list[str], index: int) -> int:
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped == "" or stripped.startswith("#"):
            index += 1
            continue
        break
    return index


def _split_key_value(stripped_line: str) -> tuple[str, str]:
    if ":" not in stripped_line:
        raise ValueError(f"Expected YAML key/value line, got: {stripped_line}")
    key, value = stripped_line.split(":", 1)
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    if value in {"[]", "null", "Null", "NULL", "~"}:
        return [] if value == "[]" else None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))
