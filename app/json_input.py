from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JsonObjectResult:
    data: dict[str, Any]
    repaired: bool
    repair_notes: tuple[str, ...]


def parse_llm_json_object(text: str) -> JsonObjectResult:
    """Parse an LLM JSON object, repairing common transport/escaping defects.

    Repair is intentionally conservative. The returned object is always passed
    through Python's strict JSON parser after cleanup; schema/domain validation
    remains the caller's responsibility.
    """
    original = text.strip().lstrip("\ufeff")
    if not original:
        raise ValueError("JSON output is empty.")
    try:
        return JsonObjectResult(_loads_object(original), False, ())
    except (json.JSONDecodeError, ValueError) as first_error:
        repaired, notes = _repair_json_text(original)
        try:
            return JsonObjectResult(_loads_object(repaired), True, tuple(notes))
        except (json.JSONDecodeError, ValueError) as final_error:
            if isinstance(final_error, json.JSONDecodeError):
                location = f"line {final_error.lineno}, column {final_error.colno}"
            else:
                location = str(final_error)
            raise ValueError(
                f"JSON remains invalid after automatic quote/format repair ({location}). "
                f"Original parser error: {first_error}"
            ) from final_error


def _loads_object(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM output must be one JSON object, not an array or scalar.")
    return data


def _repair_json_text(text: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    cleaned = _extract_json_object(text)
    if cleaned != text:
        notes.append("removed Markdown/prose outside the JSON object")
    normalized = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    escaped, quote_count, newline_count = _escape_string_defects(normalized)
    if quote_count:
        notes.append(f"escaped {quote_count} unescaped internal double quote(s)")
    if newline_count:
        notes.append(f"escaped {newline_count} literal newline(s) inside JSON string(s)")
    without_trailing = _remove_trailing_commas(escaped)
    if without_trailing != escaped:
        notes.append("removed trailing comma(s)")
    return without_trailing, notes


def _extract_json_object(text: str) -> str:
    fenced = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", text, flags=re.I | re.S)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _escape_string_defects(text: str) -> tuple[str, int, int]:
    result: list[str] = []
    in_string = False
    escaped = False
    quote_repairs = 0
    newline_repairs = 0
    length = len(text)
    containers: list[str] = []
    string_role = "value"
    previous_significant = ""
    for index, character in enumerate(text):
        if not in_string:
            result.append(character)
            if character == '"':
                in_string = True
                escaped = False
                string_role = (
                    "key"
                    if containers and containers[-1] == "{" and previous_significant in {"{", ","}
                    else "value"
                )
            elif character in "{[":
                containers.append(character)
                previous_significant = character
            elif character in "}]":
                if containers:
                    containers.pop()
                previous_significant = character
            elif not character.isspace():
                previous_significant = character
            continue
        if escaped:
            result.append(character)
            escaped = False
            continue
        if character == "\\":
            result.append(character)
            escaped = True
            continue
        if character == "\n":
            result.append("\\n")
            newline_repairs += 1
            continue
        if character == '"':
            container = containers[-1] if containers else ""
            if _quote_can_close_string(text, index, length, string_role, container):
                result.append(character)
                in_string = False
                previous_significant = '"'
            else:
                result.append('\\"')
                quote_repairs += 1
            continue
        result.append(character)
    return "".join(result), quote_repairs, newline_repairs


def _quote_can_close_string(
    text: str, index: int, length: int, string_role: str, container: str
) -> bool:
    cursor = index + 1
    while cursor < length and text[cursor].isspace():
        cursor += 1
    if cursor >= length:
        return True
    following = text[cursor]
    if string_role == "key":
        return following == ":"
    if following in "}]":
        return True
    if following != ",":
        return False
    # A comma after a real closing quote must be followed by another JSON
    # value/key or a container close. A normal letter indicates quoted prose.
    cursor += 1
    while cursor < length and text[cursor].isspace():
        cursor += 1
    if cursor >= length:
        return True
    if container == "{":
        if text[cursor] == "}":
            return True
        if text[cursor] != '"':
            return False
        key_end = cursor + 1
        key_escaped = False
        while key_end < length:
            key_character = text[key_end]
            if key_escaped:
                key_escaped = False
            elif key_character == "\\":
                key_escaped = True
            elif key_character == '"':
                after_key = key_end + 1
                while after_key < length and text[after_key].isspace():
                    after_key += 1
                return after_key < length and text[after_key] == ":"
            key_end += 1
        return False
    return text[cursor] in '"{[}]' or text.startswith(
        ("true", "false", "null"), cursor
    ) or text[cursor] in "-0123456789"


def _remove_trailing_commas(text: str) -> str:
    result: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_string:
            result.append(character)
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            index += 1
            continue
        if character == '"':
            in_string = True
            result.append(character)
            index += 1
            continue
        if character == ",":
            cursor = index + 1
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
            if cursor < len(text) and text[cursor] in "}]":
                index += 1
                continue
        result.append(character)
        index += 1
    return "".join(result)
