"""Preserve public workpaper fields without making a research acceptance decision."""
import json


def decode_workpaper_arguments(raw: str):
    """Decode complete fields with stdlib JSON; never invent missing text.

    Only one redundant closing brace after a complete object is mechanically
    recoverable for normal validation. Other partial objects are display-only.
    Duplicate keys and non-finite values are never eligible for recovery.
    """
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("non_finite_json_value")

    decoder = json.JSONDecoder(object_pairs_hook=pairs, parse_constant=constant)
    text = raw.lstrip()
    try:
        value, end = decoder.raw_decode(text)
        if not isinstance(value, dict):
            return {}, False, None
        tail = text[end:].strip()
        return value, tail in ("", "}"), "redundant_closing_brace" if tail == "}" else None
    except ValueError:
        pass
    # Save only fully decoded top-level fields preceding a syntax failure.
    # This is not an executable tool call, and cannot pass as a submission.
    if not text.startswith("{"):
        return {}, False, None
    fields, pos = {}, 1
    try:
        while pos < len(text):
            while pos < len(text) and text[pos].isspace():
                pos += 1
            key, pos = decoder.raw_decode(text, pos)
            if not isinstance(key, str) or key in fields:
                return {}, False, None
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if text[pos] != ":":
                break
            pos += 1
            while pos < len(text) and text[pos].isspace():
                pos += 1
            value, pos = decoder.raw_decode(text, pos)
            fields[key] = value
            while pos < len(text) and text[pos].isspace():
                pos += 1
            if text[pos] != ",":
                break
            pos += 1
    except (ValueError, IndexError):
        pass
    return fields, False, None
