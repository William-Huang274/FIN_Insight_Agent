from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping, Sequence


class BoundedSemanticAnchorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BoundedSemanticAnchorError(code)


@dataclass(frozen=True)
class _Occurrence:
    group_index: int
    group_id: str
    phrase: str
    start: int
    end: int


def _normalized_text_with_offsets(text: str) -> tuple[str, list[int]]:
    normalized: list[str] = []
    offsets: list[int] = []
    previous_was_space = False
    for source_index, character in enumerate(text):
        if character.isspace():
            if normalized and not previous_was_space:
                normalized.append(" ")
                offsets.append(source_index)
            previous_was_space = True
            continue
        folded = character.casefold()
        for folded_character in folded:
            normalized.append(folded_character)
            offsets.append(source_index)
        previous_was_space = False
    normalized_text = "".join(normalized)
    while normalized_text.endswith(" "):
        normalized_text = normalized_text[:-1]
        offsets.pop()
    return normalized_text, offsets


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def _all_literal_occurrences(
    normalized_text: str,
    offsets: Sequence[int],
    *,
    phrase: str,
    group_index: int,
    group_id: str,
) -> list[_Occurrence]:
    normalized_phrase = _normalize_phrase(phrase)
    values: list[_Occurrence] = []
    cursor = 0
    while True:
        position = normalized_text.find(normalized_phrase, cursor)
        if position < 0:
            break
        last = position + len(normalized_phrase) - 1
        values.append(
            _Occurrence(
                group_index=group_index,
                group_id=group_id,
                phrase=phrase,
                start=offsets[position],
                end=offsets[last] + 1,
            )
        )
        cursor = position + 1
    return values


def validate_literal_anchor_groups(
    groups: Sequence[Mapping[str, Any]],
    *,
    maximum_groups: int = 12,
    maximum_phrases_per_group: int = 6,
    maximum_anchor_chars: int = 160,
) -> list[dict[str, Any]]:
    _require(
        0 < len(groups) <= maximum_groups,
        "semantic_anchor_contract_invalid",
    )
    compiled: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in groups:
        group_id = str(raw.get("group_id") or "")
        phrases = [str(value) for value in raw.get("literal_phrases") or ()]
        _require(
            bool(group_id)
            and group_id not in seen_ids
            and 0 < len(phrases) <= maximum_phrases_per_group,
            "semantic_anchor_contract_invalid",
        )
        normalized_phrases = [_normalize_phrase(value) for value in phrases]
        _require(
            all(
                phrase
                and len(phrase) <= maximum_anchor_chars
                and "\x00" not in phrase
                for phrase in normalized_phrases
            ),
            "semantic_anchor_contract_invalid",
        )
        seen_ids.add(group_id)
        compiled.append(
            {
                "group_id": group_id,
                "literal_phrases": phrases,
                "normalized_phrases": normalized_phrases,
            }
        )
    return compiled


def compile_bounded_semantic_anchor_window(
    text: str,
    *,
    required_anchor_groups: Sequence[Mapping[str, Any]],
    max_anchor_span: int,
    maximum_anchor_chars: int = 160,
) -> tuple[int, int, dict[str, Any]]:
    """Select the smallest source window containing one literal from every group.

    The contract intentionally accepts literal phrase groups instead of arbitrary
    regular expressions.  Cross-phrase distance belongs to this bounded window
    selector, so a single policy pattern cannot consume an entire long document.
    """

    _require(bool(text), "anchor_missing")
    _require(0 < max_anchor_span <= 4000, "semantic_anchor_contract_invalid")
    groups = validate_literal_anchor_groups(
        required_anchor_groups,
        maximum_anchor_chars=maximum_anchor_chars,
    )
    normalized_text, offsets = _normalized_text_with_offsets(text)
    _require(bool(normalized_text) and bool(offsets), "anchor_missing")

    occurrences: list[_Occurrence] = []
    occurrence_counts: dict[str, int] = {}
    for group_index, group in enumerate(groups):
        group_occurrences: list[_Occurrence] = []
        for phrase in group["literal_phrases"]:
            group_occurrences.extend(
                _all_literal_occurrences(
                    normalized_text,
                    offsets,
                    phrase=phrase,
                    group_index=group_index,
                    group_id=str(group["group_id"]),
                )
            )
        _require(
            bool(group_occurrences),
            f"anchor_missing:{group['group_id']}",
        )
        occurrence_counts[str(group["group_id"])] = len(group_occurrences)
        occurrences.extend(group_occurrences)

    occurrences.sort(
        key=lambda row: (row.start, row.end, row.group_index, row.phrase)
    )
    counts: dict[int, int] = {}
    left = 0
    best_key: tuple[int, int, int] | None = None
    best_rows: tuple[_Occurrence, ...] = ()
    for right, occurrence in enumerate(occurrences):
        counts[occurrence.group_index] = counts.get(occurrence.group_index, 0) + 1
        while len(counts) == len(groups):
            window = tuple(occurrences[left : right + 1])
            start = window[0].start
            end = max(row.end for row in window)
            key = (end - start, start, end)
            if best_key is None or key < best_key:
                best_key = key
                best_rows = window
            removed = occurrences[left]
            counts[removed.group_index] -= 1
            if counts[removed.group_index] == 0:
                del counts[removed.group_index]
            left += 1

    _require(best_key is not None, "multi_anchor_window_too_wide")
    _require(best_key[0] <= max_anchor_span, "multi_anchor_window_too_wide")
    selected: list[dict[str, Any]] = []
    for group_index, group in enumerate(groups):
        candidates = [row for row in best_rows if row.group_index == group_index]
        chosen = min(candidates, key=lambda row: (row.end - row.start, row.start, row.phrase))
        selected.append(
            {
                "group_id": str(group["group_id"]),
                "matched_literal": chosen.phrase,
                "start": chosen.start,
                "end": chosen.end,
            }
        )
    receipt = {
        "compiler": "bounded_literal_phrase_groups_v1",
        "anchor_group_count": len(groups),
        "occurrence_counts": occurrence_counts,
        "selected_anchors": selected,
        "anchor_window_start": best_key[1],
        "anchor_window_end": best_key[2],
        "anchor_window_chars": best_key[0],
        "max_anchor_span": max_anchor_span,
    }
    return best_key[1], best_key[2], receipt


def extract_bounded_semantic_excerpt(
    text: str,
    *,
    required_anchor_groups: Sequence[Mapping[str, Any]],
    before: int,
    after: int,
    max_anchor_span: int,
    max_excerpt_chars: int,
) -> tuple[str, dict[str, Any]]:
    _require(
        0 <= before <= 1000
        and 0 <= after <= 2000
        and 0 < max_excerpt_chars <= 4000,
        "semantic_anchor_contract_invalid",
    )
    anchor_start, anchor_end, receipt = compile_bounded_semantic_anchor_window(
        text,
        required_anchor_groups=required_anchor_groups,
        max_anchor_span=max_anchor_span,
    )
    start = max(0, anchor_start - before)
    end = min(len(text), anchor_end + after)
    while start > 0 and text[start - 1] not in ".!?\n":
        start -= 1
        if anchor_start - start > before * 2:
            break
    while end < len(text) and text[end - 1] not in ".!?\n":
        end += 1
        if end - anchor_end > after * 2:
            break
    excerpt = re.sub(r"\s+", " ", text[start:end]).strip()
    _require(bool(excerpt), "final_excerpt_too_large")
    _require(len(excerpt) <= max_excerpt_chars, "final_excerpt_too_large")
    return excerpt, {
        **receipt,
        "excerpt_start": start,
        "excerpt_end": end,
        "excerpt_chars": len(excerpt),
        "max_excerpt_chars": max_excerpt_chars,
    }


def reject_legacy_unbounded_pattern_surface(fragment: Mapping[str, Any]) -> None:
    """Keep arbitrary regex out of the v2 anchor contract.

    Historical v1 policies remain immutable.  Any successor fragment that tries
    to reintroduce required_patterns is rejected before source text is inspected.
    """

    _require(
        "required_patterns" not in fragment,
        "pattern_occurrence_unbounded",
    )


__all__ = [
    "BoundedSemanticAnchorError",
    "compile_bounded_semantic_anchor_window",
    "extract_bounded_semantic_excerpt",
    "reject_legacy_unbounded_pattern_surface",
    "validate_literal_anchor_groups",
]
