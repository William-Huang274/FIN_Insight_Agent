from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, replace
import re
import unicodedata
from typing import Any, Mapping, Sequence

from .dell_report_graph_schema_r14 import (
    EventArgumentGraphR14,
    EventNodeR14,
    GRAPH_SCHEMA_VERSION,
    LocalScopeNodeR14,
    MentionNodeR14,
    NominalEdgeR14,
    PRICE_GRAPH_SCHEMA_VERSION,
    PriceAttachmentGraphR14,
    PricePathProofR14,
    ProofRecordR14,
    RoleEdgeR14,
    SubjectShareEdgeR14,
    TemporalScopeEdgeR14,
    TokenR14,
    TypedTargetBridgeEdgeR14,
    assertion_attribution_signal_tokens_r14,
    canonical_assertion_speech_mode_r14,
    canonical_event_inference_barrier_ids_r14,
    canonical_predicate_operator_identity_ids_r14,
    canonical_semantic_identity_ids_r14,
    normalize_structural_text_r14,
    validate_event_argument_graph_r14,
    validate_price_attachment_graph_r14,
)
from .dell_report_price_graph_r14 import build_price_attachment_graph_r14
from .dell_report_r14_common import canonical_digest, require, sha256_bytes
from .dell_report_r14_contracts import R14ContractBundle


_MONEY = re.compile(
    r"(?:[$€£¥]\s*[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s*(?:million|billion|mn|bn))?"
    r"|(?:USD|EUR|GBP|JPY|US\$)\s*[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s*(?:million|billion|mn|bn))?"
    r"|[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:US\s+)?dollars?)",
    re.IGNORECASE,
)
_PERCENT = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)\s*%")
_NUMBER = re.compile(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_WORD = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")

_NEGATION = frozenset({"no", "not", "never", "neither", "without"})
_FORWARD = frozenset({"expect", "expects", "expected", "plan", "plans", "will"})
_MODALS = frozenset({"can", "could", "may", "might", "must", "should", "would"})
_NOMINAL_REPORTING_HEADS = frozenset(
    {
        "announce",
        "announced",
        "claim",
        "claimed",
        "report",
        "reported",
        "said",
        "says",
        "state",
        "stated",
    }
)
_INACTIVE = frozenset({"discontinue", "discontinued", "suspend", "suspended", "withdraw", "withdrawn"})
_PERIOD_WORDS = frozenset(
    {
        "currently", "now", "today", "yesterday", "january", "february",
        "march", "april", "may", "june", "july", "august", "september",
        "october", "november", "december", "quarter", "year", "month", "week",
    }
)


def normalize_proof_text(value: str, grammar: Mapping[str, Any]) -> str:
    del grammar
    return normalize_structural_text_r14(value)


@dataclass
class _ScopeDraft:
    key: int
    scope_type: str
    parent_key: int | None
    document_start: int
    content_start: int
    opener_span: tuple[int, int] | None
    document_end: int | None = None
    content_end: int | None = None
    closer_span: tuple[int, int] | None = None
    state: str = "PROVED"


@dataclass(frozen=True)
class _ClauseR14:
    scope_id: str
    clause_span: tuple[int, int]
    sentence_span: tuple[int, int]


@dataclass(frozen=True)
class _PredicateR14:
    token: TokenR14
    semantic_labels: tuple[str, ...]
    event_types: tuple[str, ...]
    proof_type: str


@dataclass(frozen=True)
class _EventSegmentR14:
    start: int
    end: int
    coordinator_span: tuple[int, int] | None
    ambiguous: bool


def _normalization_clusters(raw: str) -> tuple[tuple[int, int], ...]:
    """Return conservative raw clusters across which NFKC may compose."""
    if not raw:
        return ()
    output: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(raw)):
        character = raw[index]
        previous = raw[index - 1]
        combines = bool(unicodedata.combining(character))
        hangul_continuation = (
            "\u1100" <= previous <= "\u1112" and "\u1161" <= character <= "\u1175"
        ) or (
            "\u1161" <= previous <= "\u1175" and "\u11a8" <= character <= "\u11c2"
        )
        if combines or hangul_continuation:
            continue
        output.append((start, index))
        start = index
    output.append((start, len(raw)))
    return tuple(output)


def _normalized_stream(
    raw: str,
) -> tuple[str, dict[int, int], dict[int, int]]:
    clusters = _normalization_clusters(raw)
    characters: list[str] = []
    raw_to_normalized: dict[int, int] = {}
    normalized_boundary_to_raw: dict[int, int] = {0: 0}
    for raw_start, raw_end in clusters:
        normalized_start = len(characters)
        for raw_index in range(raw_start, raw_end):
            raw_to_normalized[raw_index] = normalized_start
        normalized = normalize_structural_text_r14(raw[raw_start:raw_end])
        characters.extend(normalized)
        raw_to_normalized[raw_end] = len(characters)
        normalized_boundary_to_raw[len(characters)] = raw_end
    whole = normalize_structural_text_r14(raw)
    require(
        "".join(characters) == whole,
        "R14_tokenizer_normalization_cluster_mapping_failed",
    )
    raw_to_normalized[len(raw)] = len(characters)
    normalized_boundary_to_raw[len(characters)] = len(raw)
    return (
        whole,
        raw_to_normalized,
        normalized_boundary_to_raw,
    )


def _tokenize_without_scope(text: str) -> tuple[TokenR14, ...]:
    raw = str(text or "")
    (
        normalized,
        raw_to_normalized,
        normalized_boundary_to_raw,
    ) = _normalized_stream(raw)
    patterns = (
        ("MONEY", _MONEY),
        ("PERCENT", _PERCENT),
        ("NUMBER", _NUMBER),
        ("WORD", _WORD),
        ("PUNCT", _PUNCT),
        ("WHITESPACE", _WHITESPACE),
    )
    root_scope = f"SCOPE-DRAFT::ROOT::{sha256_bytes(raw.encode('utf-8'))[:24].upper()}"
    tokens: list[TokenR14] = []
    raw_position = 0
    while raw_position < len(raw):
        normalized_position = raw_to_normalized[raw_position]
        matches: list[tuple[int, int, str, re.Match[str]]] = []
        for priority, (kind, pattern) in enumerate(patterns):
            match = pattern.match(normalized, normalized_position)
            if match and match.end() in normalized_boundary_to_raw:
                raw_end = normalized_boundary_to_raw[match.end()]
                matches.append((raw_end - raw_position, -priority, kind, match))
        if not matches:
            cluster_end = min(
                raw_boundary
                for raw_boundary in normalized_boundary_to_raw.values()
                if raw_boundary > raw_position
            )
            surface = raw[raw_position:cluster_end]
            kind = "PUNCT" if len(surface) else "MALFORMED"
            tokens.append(
                TokenR14(
                    kind=kind,
                    raw=surface,
                    normalized=normalize_structural_text_r14(surface),
                    start=raw_position,
                    end=cluster_end,
                    local_scope_id=root_scope,
                )
            )
            raw_position = cluster_end
            continue
        length, _, kind, match = max(matches, key=lambda row: (row[0], row[1]))
        require(length > 0, "R14_tokenizer_zero_length_match")
        raw_end = raw_position + length
        surface = raw[raw_position:raw_end]
        tokens.append(
            TokenR14(
                kind=kind,
                raw=surface,
                normalized=normalize_structural_text_r14(surface),
                start=raw_position,
                end=raw_end,
                local_scope_id=root_scope,
            )
        )
        raw_position = raw_end
    require("".join(row.raw for row in tokens) == raw, "R14_tokenizer_not_lossless")
    return tuple(tokens)


def _assign_local_scopes(
    text: str, tokens: Sequence[TokenR14], grammar: Mapping[str, Any]
) -> tuple[tuple[TokenR14, ...], tuple[LocalScopeNodeR14, ...]]:
    raw = str(text or "")
    parenthetical_pairs = [tuple(value) for value in grammar["scope"]["parenthetical_pairs"]]
    quotation_pairs = [tuple(value) for value in grammar["scope"]["quotation_pairs"]]
    opener_to_closer = {left: right for left, right in (*parenthetical_pairs, *quotation_pairs)}
    closer_to_opener = {right: left for left, right in (*parenthetical_pairs, *quotation_pairs)}
    symmetric_quotes = {left for left, right in quotation_pairs if left == right}
    quote_openers = {left for left, _ in quotation_pairs}
    parenthetical_openers = {left for left, _ in parenthetical_pairs}

    drafts: dict[int, _ScopeDraft] = {
        0: _ScopeDraft(
            key=0,
            scope_type="root",
            parent_key=None,
            document_start=0,
            content_start=0,
            opener_span=None,
            document_end=len(raw),
            content_end=len(raw),
        )
    }
    stack = [0]
    assignment: list[int] = []
    next_key = 1
    for token in tokens:
        surface = token.raw
        current_key = stack[-1]
        current = drafts[current_key]
        is_symmetric_close = (
            surface in symmetric_quotes
            and current.scope_type == "quotation"
            and current.opener_span is not None
            and raw[current.opener_span[0] : current.opener_span[1]] == surface
        )
        is_typed_close = (
            surface in closer_to_opener
            and current.opener_span is not None
            and raw[current.opener_span[0] : current.opener_span[1]]
            == closer_to_opener[surface]
        )
        if len(stack) > 1 and (is_symmetric_close or is_typed_close):
            assignment.append(current_key)
            current.content_end = token.start
            current.document_end = token.end
            current.closer_span = (token.start, token.end)
            stack.pop()
            continue
        if surface in opener_to_closer and (
            surface not in symmetric_quotes or surface in quote_openers
        ):
            assignment.append(current_key)
            scope_type = "parenthetical" if surface in parenthetical_openers else "quotation"
            drafts[next_key] = _ScopeDraft(
                key=next_key,
                scope_type=scope_type,
                parent_key=current_key,
                document_start=token.start,
                content_start=token.end,
                opener_span=(token.start, token.end),
            )
            stack.append(next_key)
            next_key += 1
            continue
        assignment.append(current_key)

    for key in stack[1:]:
        drafts[key].content_end = len(raw)
        drafts[key].document_end = len(raw)
        drafts[key].state = "AMBIGUOUS"

    nodes_by_key: dict[int, LocalScopeNodeR14] = {}
    for key in sorted(drafts, key=lambda value: (0 if value == 0 else 1, value)):
        draft = drafts[key]
        parent_scope_id = (
            nodes_by_key[draft.parent_key].scope_id
            if draft.parent_key is not None
            else None
        )
        depth = 0
        parent_key = draft.parent_key
        while parent_key is not None:
            depth += 1
            parent_key = drafts[parent_key].parent_key
        nodes_by_key[key] = LocalScopeNodeR14(
            scope_type=draft.scope_type,
            document_span=(draft.document_start, int(draft.document_end)),
            content_span=(draft.content_start, int(draft.content_end)),
            parent_scope_id=parent_scope_id,
            opener_span=draft.opener_span,
            closer_span=draft.closer_span,
            depth=depth,
            proof_state=draft.state,
        )
    scoped_tokens = tuple(
        replace(token, local_scope_id=nodes_by_key[key].scope_id)
        for token, key in zip(tokens, assignment)
    )
    scopes = tuple(
        sorted(
            nodes_by_key.values(),
            key=lambda row: (
                row.document_span,
                row.depth,
                row.scope_type,
                row.node_digest,
            ),
        )
    )
    return scoped_tokens, scopes


def tokenize_r14(text: str, grammar: Mapping[str, Any]) -> tuple[TokenR14, ...]:
    tokens, _ = _assign_local_scopes(
        str(text or ""), _tokenize_without_scope(str(text or "")), grammar
    )
    return tokens


def _content(tokens: Sequence[TokenR14]) -> list[TokenR14]:
    return [row for row in tokens if row.kind not in {"WHITESPACE", "PUNCT"}]


def _abbreviation_at(text: str, end: int, grammar: Mapping[str, Any]) -> bool:
    abbreviations = [
        normalize_structural_text_r14(value)
        for value in grammar["resource_versions"]["abbreviation_policy"]["entries"]
    ]
    prefix = normalize_structural_text_r14(text[:end])
    return any(prefix.endswith(value) for value in abbreviations)


def _build_clauses(
    text: str,
    tokens: Sequence[TokenR14],
    scopes: Sequence[LocalScopeNodeR14],
    grammar: Mapping[str, Any],
) -> tuple[_ClauseR14, ...]:
    normalized_hard = {
        normalize_structural_text_r14(value)
        for value in grammar["scope"]["hard_boundary_surface"]
    }
    sentence_hard = {".", "?", "!"}
    output: list[_ClauseR14] = []
    for scope in scopes:
        scoped = [row for row in tokens if row.local_scope_id == scope.scope_id]
        if not scoped:
            continue
        sentence_ranges: list[tuple[int, int]] = []
        sentence_start = scope.content_span[0]
        for token in scoped:
            sentence_break = (
                token.kind == "WHITESPACE" and "\n" in token.raw
            ) or (
                token.kind == "PUNCT"
                and token.normalized in sentence_hard
                and not _abbreviation_at(text, token.end, grammar)
            )
            if sentence_break:
                if token.end > sentence_start:
                    sentence_ranges.append((sentence_start, token.end))
                sentence_start = token.end
        if sentence_start < scope.content_span[1]:
            sentence_ranges.append((sentence_start, scope.content_span[1]))

        clause_start = scope.content_span[0]
        for token in scoped:
            hard_break = (
                token.kind == "WHITESPACE" and "\n" in token.raw
            ) or (
                token.kind == "PUNCT"
                and token.normalized in normalized_hard
                and not _abbreviation_at(text, token.end, grammar)
            )
            if not hard_break:
                continue
            if text[clause_start:token.end].strip():
                clause = (clause_start, token.end)
                sentence = next(
                    (
                        row
                        for row in sentence_ranges
                        if row[0] <= clause[0] and clause[1] <= row[1]
                    ),
                    clause,
                )
                output.append(_ClauseR14(scope.scope_id, clause, sentence))
            clause_start = token.end
        if clause_start < scope.content_span[1] and text[clause_start : scope.content_span[1]].strip():
            clause = (clause_start, scope.content_span[1])
            sentence = next(
                (
                    row
                    for row in sentence_ranges
                    if row[0] <= clause[0] and clause[1] <= row[1]
                ),
                clause,
            )
            output.append(_ClauseR14(scope.scope_id, clause, sentence))
    return tuple(sorted(output, key=lambda row: (row.clause_span, row.scope_id)))


def _term_words(term: str) -> tuple[str, ...]:
    normalized = normalize_structural_text_r14(term)
    return tuple(row.group(0) for row in re.finditer(r"[^\W_]+(?:[-'][^\W_]+)*", normalized))


def _find_term_spans(tokens: Sequence[TokenR14], term: str) -> list[tuple[int, int, str]]:
    wanted = _term_words(term)
    if not wanted:
        return []
    visible = [row for row in tokens if row.kind == "WORD"]
    output: list[tuple[int, int, str]] = []
    for index in range(0, len(visible) - len(wanted) + 1):
        rows = visible[index : index + len(wanted)]
        if len({row.local_scope_id for row in rows}) != 1:
            continue
        values = tuple(row.normalized for row in rows)
        exact = values == wanted
        inflected_single = (
            len(wanted) == len(rows) == 1
            and wanted[0] in _lemma_candidates(values[0])
        )
        possessive = (
            len(wanted) == len(rows) == 1
            and values[0] in {wanted[0] + "'s", wanted[0] + "s'"}
        )
        if exact or possessive or inflected_single:
            end = rows[-1].end
            if possessive:
                end = rows[0].start + len(term)
            output.append((rows[0].start, end, rows[0].local_scope_id))
    return output


def _maximal_product_spans(
    text: str,
    tokens: Sequence[TokenR14],
    raw_spans: Sequence[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    by_scope: dict[str, list[tuple[int, int, str]]] = {}
    for row in set(raw_spans):
        by_scope.setdefault(row[2], []).append(row)
    maximal: list[tuple[int, int, str]] = []
    for scope_rows in by_scope.values():
        furthest_end = -1
        for row in sorted(scope_rows, key=lambda value: (value[0], -value[1])):
            if row[1] <= furthest_end:
                continue
            maximal.append(row)
            furthest_end = row[1]
    merged: list[tuple[int, int, str]] = []
    for row in sorted(maximal):
        if (
            merged
            and merged[-1][2] == row[2]
            and not text[merged[-1][1] : row[0]].strip()
        ):
            merged[-1] = (merged[-1][0], row[1], row[2])
        else:
            merged.append(row)
    visible_by_scope: dict[str, list[TokenR14]] = {}
    for token in tokens:
        if token.kind == "WORD":
            visible_by_scope.setdefault(token.local_scope_id, []).append(token)
    extended: list[tuple[int, int, str]] = []
    for start, end, scope_id in merged:
        visible = visible_by_scope.get(scope_id, ())
        next_index = bisect_left(visible, end, key=lambda row: row.start)
        following = visible[next_index] if next_index < len(visible) else None
        if following is not None and text[end : following.start].strip():
            following = None
        if following is not None and any(character.isdigit() for character in following.normalized):
            end = following.end
        normalized = normalize_structural_text_r14(text[start:end])
        next_index = bisect_left(visible, end, key=lambda row: row.start)
        next_word = visible[next_index] if next_index < len(visible) else None
        if normalized == "hardware" and next_word is not None and next_word.normalized == "bundle":
            continue
        extended.append((start, end, scope_id))
    return extended


def _mention_key(row: MentionNodeR14) -> tuple[str, int, int, str, str]:
    return (
        row.mention_type,
        row.start,
        row.end,
        row.normalized_value,
        row.local_scope_id,
    )


def _build_mentions(
    text: str, tokens: Sequence[TokenR14], bundle: R14ContractBundle
) -> tuple[MentionNodeR14, ...]:
    entity_terms: set[str] = set()
    product_terms: set[str] = set()
    for target in bundle.topology["targets"]:
        entity_terms.update(str(value) for value in target["candidate_ontology"]["entity_terms"])
        product_terms.update(str(value) for value in target["candidate_ontology"]["product_terms"])
    output: dict[tuple[str, int, int, str, str], MentionNodeR14] = {}

    def add(
        mention_type: str,
        start: int,
        end: int,
        scope_id: str,
        rule_id: str,
        state: str = "PROVED",
    ) -> MentionNodeR14:
        node = MentionNodeR14(
            mention_type=mention_type,
            raw_value=text[start:end],
            normalized_value=normalize_structural_text_r14(text[start:end]),
            start=start,
            end=end,
            type_proof_rule_id=rule_id,
            local_scope_id=scope_id,
            proof_state=state,
            semantic_identity_ids=canonical_semantic_identity_ids_r14(
                mention_type,
                normalize_structural_text_r14(text[start:end]),
            ),
        )
        output.setdefault(_mention_key(node), node)
        return output[_mention_key(node)]

    for term in sorted(entity_terms):
        for start, end, scope_id in _find_term_spans(tokens, term):
            add("entity", start, end, scope_id, "ONTOLOGY-ENTITY-TYPE")
    product_spans: list[tuple[int, int, str]] = []
    for term in sorted(product_terms):
        product_spans.extend(_find_term_spans(tokens, term))
    for start, end, scope_id in _maximal_product_spans(text, tokens, product_spans):
        add(
            "product_or_hardware",
            start,
            end,
            scope_id,
            "ONTOLOGY-MAXIMAL-PRODUCT-CHUNK",
        )
    for token in tokens:
        if token.kind == "MONEY":
            add("price", token.start, token.end, token.local_scope_id, "TOKEN-MONEY-TYPE")
        elif token.kind == "PERCENT":
            add(
                "quantity_or_percent",
                token.start,
                token.end,
                token.local_scope_id,
                "TOKEN-PERCENT-TYPE",
            )
        elif token.kind == "NUMBER":
            normalized = token.normalized.replace(",", "")
            if re.fullmatch(r"(?:19|20)\d{2}", normalized):
                add("period", token.start, token.end, token.local_scope_id, "TOKEN-YEAR-PERIOD-TYPE")
            else:
                add("quantity", token.start, token.end, token.local_scope_id, "TOKEN-NUMBER-TYPE")
        elif token.kind == "WORD" and (
            token.normalized in _PERIOD_WORDS
            or re.fullmatch(r"(?:q[1-4]|fy\d{2,4})", token.normalized)
        ):
            add("period", token.start, token.end, token.local_scope_id, "TOKEN-PERIOD-TYPE")
    return tuple(
        sorted(
            output.values(),
            key=lambda row: (
                row.start,
                row.end,
                row.mention_type,
                row.type_proof_rule_id,
                row.node_digest,
            ),
        )
    )


def _lemma_candidates(value: str) -> set[str]:
    output = {value}
    irregular = {"sold": "sell", "said": "say", "ran": "run"}
    if value in irregular:
        output.add(irregular[value])
    for suffix in ("ied", "ing", "ed", "en", "es", "s"):
        if not value.endswith(suffix) or len(value) <= len(suffix) + 2:
            continue
        stem = value[: -len(suffix)]
        output.add(stem)
        if suffix == "ied":
            output.add(stem + "y")
        if suffix in {"ing", "ed"} and len(stem) >= 2 and stem[-1] == stem[-2]:
            output.add(stem[:-1])
        output.add(stem + "e")
    return output


def _predicate_resources(
    bundle: R14ContractBundle,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    target_terms = {
        str(target["target_id"]): {
            normalize_structural_text_r14(str(term))
            for term in target["candidate_ontology"]["predicate_terms"]
        }
        for target in bundle.topology["targets"]
    }
    event_types = {
        str(event_type): {
            normalize_structural_text_r14(str(term)) for term in terms
        }
        for event_type, terms in bundle.topology["graph_type_registry"][
            "predicate_event_type_terms"
        ].items()
    }
    return target_terms, event_types


def _predicate_candidates(
    tokens: Sequence[TokenR14], bundle: R14ContractBundle
) -> list[_PredicateR14]:
    visible = [row for row in tokens if row.kind == "WORD"]
    auxiliaries = set(bundle.grammar["structural_resources"]["auxiliaries"])
    suffixes = tuple(bundle.grammar["structural_resources"]["finite_or_participle_suffixes"])
    irregular_finite = set(
        bundle.grammar["structural_resources"]["irregular_finite_forms"]
    )
    target_terms, event_type_terms = _predicate_resources(bundle)
    auxiliary_follow_barriers = {
        *bundle.grammar["scope"]["soft_coordinators"],
        *bundle.grammar["structural_resources"]["function_words"],
    }
    output: list[_PredicateR14] = []
    consumed: set[int] = set()
    for index, original in enumerate(visible):
        if index in consumed:
            continue
        token = original
        candidates = _lemma_candidates(token.normalized)
        labels = tuple(
            sorted(
                target_id
                for target_id, terms in target_terms.items()
                if candidates.intersection(terms)
            )
        )
        event_types = tuple(
            sorted(
                event_type
                for event_type, terms in event_type_terms.items()
                if candidates.intersection(terms)
            )
        )
        proof_type = ""
        if token.normalized in auxiliaries and index + 1 < len(visible):
            following = visible[index + 1]
            intervening = [
                row
                for row in tokens
                if token.end <= row.start
                and row.end <= following.start
                and row.kind != "WHITESPACE"
            ]
            if (
                following.local_scope_id == token.local_scope_id
                and not intervening
                and following.normalized not in auxiliary_follow_barriers
            ):
                following_candidates = _lemma_candidates(following.normalized)
                following_labels = {
                    target_id
                    for target_id, terms in target_terms.items()
                    if following_candidates.intersection(terms)
                }
                following_types = {
                    event_type
                    for event_type, terms in event_type_terms.items()
                    if following_candidates.intersection(terms)
                }
                token = TokenR14(
                    kind="WORD",
                    raw=token.raw + " " + following.raw,
                    normalized=token.normalized + " " + following.normalized,
                    start=token.start,
                    end=following.end,
                    local_scope_id=token.local_scope_id,
                )
                labels = tuple(sorted(set(labels) | following_labels))
                event_types = tuple(sorted(set(event_types) | following_types))
                consumed.add(index + 1)
                proof_type = "AUXILIARY-PREDICATE-CANDIDATE"
        if not proof_type:
            matched_suffixes = {
                value
                for value in suffixes
                if original.normalized.endswith(value)
                and len(original.normalized) > len(value) + 2
            }
            if matched_suffixes.intersection({"ed", "en", "ing"}) or (
                matched_suffixes.intersection({"s", "es"})
                and bool(labels or event_types)
                and "'" not in original.normalized
            ):
                proof_type = "MORPHOLOGICAL-PREDICATE-CANDIDATE"
        if not proof_type and original.normalized in irregular_finite:
            proof_type = "IRREGULAR-FINITE-PREDICATE-CANDIDATE"
        if proof_type:
            output.append(_PredicateR14(token, labels, event_types or ("unknown",), proof_type))
    return output


def _mentions_in(
    mentions: Sequence[MentionNodeR14], span: tuple[int, int], scope_id: str
) -> list[MentionNodeR14]:
    start_index = bisect_left(mentions, span[0], key=lambda row: row.start)
    output: list[MentionNodeR14] = []
    for row in mentions[start_index:]:
        if row.start >= span[1]:
            break
        if row.local_scope_id == scope_id and row.end <= span[1]:
            output.append(row)
    return output


def _tokens_in(
    tokens: Sequence[TokenR14], span: tuple[int, int], scope_id: str
) -> list[TokenR14]:
    start_index = bisect_left(tokens, span[0], key=lambda row: row.start)
    output: list[TokenR14] = []
    for row in tokens[start_index:]:
        if row.start >= span[1]:
            break
        if row.local_scope_id == scope_id and row.end <= span[1]:
            output.append(row)
    return output


def _subject_surface_candidates(
    text: str,
    tokens: Sequence[TokenR14],
    mentions: Sequence[MentionNodeR14],
    span: tuple[int, int],
    scope_id: str,
    grammar: Mapping[str, Any],
    product_spans: Sequence[tuple[int, int]] | None = None,
) -> list[MentionNodeR14]:
    if product_spans is None:
        product_spans = tuple(
            (row.start, row.end)
            for row in mentions
            if row.local_scope_id == scope_id
            and row.mention_type == "product_or_hardware"
        )
    product_start = max(0, bisect_left(product_spans, (span[0], -1)) - 1)
    local_product_spans: list[tuple[int, int]] = []
    for product_span in product_spans[product_start:]:
        if product_span[0] >= span[1]:
            break
        local_product_spans.append(product_span)
    known = [
        row
        for row in _mentions_in(mentions, span, scope_id)
        if row.mention_type == "entity"
        and not any(
            start <= row.start and row.end <= end
            for start, end in local_product_spans
        )
    ]
    output = list(known)
    covered = [(row.start, row.end) for row in output]
    pronouns = set(grammar["structural_resources"]["subject_pronouns"])
    for token in _tokens_in(tokens, span, scope_id):
        if token.kind != "WORD" or any(
            not (token.end <= start or end <= token.start) for start, end in covered
        ) or any(
            not (token.end <= start or end <= token.start)
            for start, end in local_product_spans
        ):
            continue
        proper = bool(token.raw[:1].isupper())
        pronoun = token.normalized in pronouns
        if not proper and not pronoun:
            continue
        output.append(
            MentionNodeR14(
                mention_type="entity",
                raw_value=text[token.start : token.end],
                normalized_value=token.normalized,
                start=token.start,
                end=token.end,
                type_proof_rule_id=(
                    "STRUCTURAL-PRONOUN-SUBJECT-CANDIDATE"
                    if pronoun
                    else "STRUCTURAL-PROPER-SUBJECT-CANDIDATE"
                ),
                local_scope_id=scope_id,
                proof_state="AMBIGUOUS",
                semantic_identity_ids=canonical_semantic_identity_ids_r14(
                    "entity", token.normalized
                ),
            )
        )
    return sorted(
        {row.mention_id: row for row in output}.values(),
        key=lambda row: (row.start, row.end, row.node_digest),
    )


def _event_segments(
    text: str,
    clause: _ClauseR14,
    tokens: Sequence[TokenR14],
    predicates: Sequence[_PredicateR14],
    mentions: Sequence[MentionNodeR14],
    grammar: Mapping[str, Any],
) -> tuple[list[_EventSegmentR14], list[ProofRecordR14]]:
    clause_tokens = _tokens_in(tokens, clause.clause_span, clause.scope_id)
    visible = [row for row in clause_tokens if row.kind == "WORD"]
    coordinators = set(grammar["scope"]["soft_coordinators"])
    coordinator_tokens = [row for row in visible if row.normalized in coordinators]
    clause_product_spans = tuple(
        (row.start, row.end)
        for row in mentions
        if row.mention_type == "product_or_hardware"
    )
    boundaries: list[tuple[TokenR14, bool]] = []
    proofs: list[ProofRecordR14] = []
    for index, coordinator in enumerate(coordinator_tokens):
        next_boundary = (
            coordinator_tokens[index + 1].start
            if index + 1 < len(coordinator_tokens)
            else clause.clause_span[1]
        )
        previous_boundary = (
            coordinator_tokens[index - 1].end
            if index > 0
            else clause.clause_span[0]
        )
        right_span = (coordinator.end, next_boundary)
        left_span = (previous_boundary, coordinator.start)
        predicate_start = bisect_left(
            predicates, right_span[0], key=lambda row: row.token.start
        )
        right_predicates: list[_PredicateR14] = []
        for row in predicates[predicate_start:]:
            if row.token.start >= right_span[1]:
                break
            right_predicates.append(row)
        first_predicate_start = min(
            (row.token.start for row in right_predicates), default=right_span[1]
        )
        right_subjects = _subject_surface_candidates(
            text,
            tokens,
            mentions,
            (right_span[0], first_predicate_start),
            clause.scope_id,
            grammar,
            product_spans=clause_product_spans,
        )
        left_candidates = _mentions_in(mentions, left_span, clause.scope_id)
        right_candidates = _mentions_in(mentions, right_span, clause.scope_id)

        def material(rows: Sequence[MentionNodeR14]) -> list[MentionNodeR14]:
            product_rows = [
                row for row in rows if row.mention_type == "product_or_hardware"
            ]
            return [
                row
                for row in rows
                if row.mention_type
                in {
                    "product_or_hardware",
                    "quantity",
                    "quantity_or_percent",
                    "entity",
                    "price",
                    "period",
                }
                and not (
                    row.mention_type == "entity"
                    and any(
                        product.start <= row.start and row.end <= product.end
                        for product in product_rows
                    )
                )
            ]

        left_material = [
            row
            for row in material(left_candidates)
            if row.mention_type
            in {"product_or_hardware", "quantity", "quantity_or_percent", "entity"}
        ]
        right_material = material(right_candidates)
        left_products = [
            row for row in left_material if row.mention_type == "product_or_hardware"
        ]
        right_products = [
            row for row in right_material if row.mention_type == "product_or_hardware"
        ]
        if left_products and right_products:
            left_anchor = left_products[-1]
            right_anchor = right_products[0]
        elif (
            left_material
            and right_material
            and left_material[-1].mention_type == right_material[0].mention_type
            and left_material[-1].mention_type
            in {"quantity", "quantity_or_percent"}
        ):
            left_anchor = left_material[-1]
            right_anchor = right_material[0]
        else:
            left_anchor = None
            right_anchor = None
        same_role = left_anchor is not None and right_anchor is not None
        covered_right_spans = [
            (row.start, row.end)
            for row in right_candidates
            if row.mention_type
            in {
                "product_or_hardware",
                "quantity",
                "quantity_or_percent",
                "entity",
                "price",
                "period",
            }
        ]
        function_words = set(grammar["structural_resources"]["function_words"])
        object_list_structural_words = {
            "hardware",
            "total",
            "totaled",
            "totaling",
            "totalled",
            "totals",
        }
        unexplained_right_content = [
            row
            for row in _tokens_in(tokens, right_span, clause.scope_id)
            if row.kind == "WORD"
            and row.normalized not in function_words
            and row.normalized not in coordinators
            and row.normalized not in object_list_structural_words
            and not any(
                start <= row.start and row.end <= end
                for start, end in covered_right_spans
            )
        ]
        object_list = (
            same_role
            and not right_predicates
            and not right_subjects
            and not unexplained_right_content
        )
        if object_list:
            proofs.append(
                ProofRecordR14(
                    rule_id="G22-OBJECT-LIST",
                    state="PROVED",
                    conclusion="no_new_event_object_list",
                    premise_spans=(
                        (left_anchor.start, left_anchor.end),
                        (coordinator.start, coordinator.end),
                        (right_anchor.start, right_anchor.end),
                    ),
                    premise_node_ids=(
                        left_anchor.mention_id,
                        right_anchor.mention_id,
                    ),
                )
            )
            continue
        if right_predicates or right_subjects or right_material:
            boundaries.append(
                (
                    coordinator,
                    not bool(right_predicates),
                )
            )

    if not boundaries:
        return [
            _EventSegmentR14(
                clause.clause_span[0], clause.clause_span[1], None, False
            )
        ], proofs
    segments: list[_EventSegmentR14] = []
    start = clause.clause_span[0]
    pending_coordinator: tuple[int, int] | None = None
    pending_ambiguous = False
    for coordinator, ambiguous in boundaries:
        if start < coordinator.start:
            segments.append(
                _EventSegmentR14(
                    start,
                    coordinator.start,
                    pending_coordinator,
                    pending_ambiguous,
                )
            )
        start = coordinator.end
        pending_coordinator = (coordinator.start, coordinator.end)
        pending_ambiguous = ambiguous
    if start < clause.clause_span[1]:
        segments.append(
            _EventSegmentR14(
                start,
                clause.clause_span[1],
                pending_coordinator,
                pending_ambiguous,
            )
        )
    return segments, proofs


def _synthetic_ambiguous_predicate(
    segment: _EventSegmentR14,
    tokens: Sequence[TokenR14],
    scope_id: str,
    grammar: Mapping[str, Any],
) -> _PredicateR14 | None:
    words = [
        row
        for row in _tokens_in(tokens, (segment.start, segment.end), scope_id)
        if row.kind == "WORD"
    ]
    pronouns = set(grammar["structural_resources"]["subject_pronouns"])
    candidates = [
        row
        for index, row in enumerate(words)
        if index > 0 or not (row.raw[:1].isupper() or row.normalized in pronouns)
    ]
    if not candidates:
        return None
    return _PredicateR14(
        token=candidates[0],
        semantic_labels=(),
        event_types=("unknown",),
        proof_type="AMBIGUOUS-NONCE-EVENT-BARRIER",
    )


def _build_target_bridges_r14(
    *,
    events: Sequence[EventNodeR14],
    mentions: Sequence[MentionNodeR14],
    role_edges: Sequence[RoleEdgeR14],
) -> tuple[TypedTargetBridgeEdgeR14, ...]:
    mention_by_id = {row.mention_id: row for row in mentions}
    proved_by_event: dict[str, list[RoleEdgeR14]] = {}
    identities_by_event: dict[str, set[str]] = {}
    for edge in role_edges:
        if edge.proof_state != "PROVED" or edge.mention_id not in mention_by_id:
            continue
        proved_by_event.setdefault(edge.event_id, []).append(edge)
        identities_by_event.setdefault(edge.event_id, set()).update(
            mention_by_id[edge.mention_id].semantic_identity_ids
        )

    output: list[TypedTargetBridgeEdgeR14] = []
    ordered_events = sorted(
        events,
        key=lambda row: (row.sentence_span, row.document_span, row.predicate_span),
    )
    for source, destination in zip(ordered_events, ordered_events[1:]):
            if (
                source.local_scope_id != destination.local_scope_id
                or source.sentence_span != destination.sentence_span
            ):
                continue
            shared = identities_by_event.get(source.event_id, set()).intersection(
                identities_by_event.get(destination.event_id, set())
            )
            shared = {
                value
                for value in shared
                if value.startswith("ENTITY::") or value.startswith("PRODUCT::")
            }
            bridge_type: str | None = None
            direction: str | None = None
            if (
                "supplier_relationship" in source.event_types
                and "delivery" in destination.event_types
                and "ENTITY::DELL" in shared
                and any(
                    value.startswith("ENTITY::") and value != "ENTITY::DELL"
                    for value in shared
                )
            ):
                bridge_type = "SUPPLIER_RELATIONSHIP_TO_DELIVERY"
                direction = "relationship_to_delivery"
            elif (
                "HBM_supply_state" in source.event_types
                and "Dell_configuration_or_delivery" in destination.event_types
                and any(
                    value.startswith("PRODUCT::HBM")
                    for value in shared
                )
            ):
                bridge_type = "HBM_STATE_TO_DELL"
                direction = "upstream_state_to_Dell"
            if bridge_type is None or direction is None:
                continue
            premises = tuple(
                sorted(
                    edge.edge_id
                    for event_id in (source.event_id, destination.event_id)
                    for edge in proved_by_event.get(event_id, ())
                    if set(
                        mention_by_id[edge.mention_id].semantic_identity_ids
                    ).intersection(shared)
                )
            )
            output.append(
                TypedTargetBridgeEdgeR14(
                    source_event_id=source.event_id,
                    destination_event_id=destination.event_id,
                    bridge_type=bridge_type,
                    shared_semantic_identity_ids=tuple(sorted(shared)),
                    direction=direction,
                    proof_rule_id="G30-ROLE-LOCAL",
                    proof_state="PROVED",
                    premise_edge_ids=premises,
                )
            )
    return tuple(
        sorted(
            {row.edge_id: row for row in output}.values(),
            key=lambda row: row.edge_digest,
        )
    )


def build_event_argument_graph_r14(
    *, text: str, bundle: R14ContractBundle
) -> EventArgumentGraphR14:
    raw = str(text or "")
    base_tokens = _tokenize_without_scope(raw)
    tokens, scopes = _assign_local_scopes(raw, base_tokens, bundle.grammar)
    scope_by_id = {row.scope_id: row for row in scopes}
    clauses = _build_clauses(raw, tokens, scopes, bundle.grammar)
    base_mentions = _build_mentions(raw, tokens, bundle)
    mentions_list = list(base_mentions)
    mention_keys = {_mention_key(row) for row in mentions_list}
    target_predicate_terms, event_type_terms = _predicate_resources(bundle)
    events: list[EventNodeR14] = []
    role_edges: list[RoleEdgeR14] = []
    subject_edges: list[SubjectShareEdgeR14] = []
    temporal_edges: list[TemporalScopeEdgeR14] = []
    proofs: list[ProofRecordR14] = []

    for clause_index, clause in enumerate(clauses):
        clause_tokens = _tokens_in(tokens, clause.clause_span, clause.scope_id)
        sentence_tokens = _tokens_in(tokens, clause.sentence_span, clause.scope_id)
        (
            sentence_reporting_tokens,
            sentence_according_present,
        ) = assertion_attribution_signal_tokens_r14(sentence_tokens)
        clause_mentions = _mentions_in(base_mentions, clause.clause_span, clause.scope_id)
        clause_product_spans = tuple(
            (row.start, row.end)
            for row in clause_mentions
            if row.mention_type == "product_or_hardware"
        )
        predicate_rows = _predicate_candidates(clause_tokens, bundle)
        if len(predicate_rows) > 1:
            copular_starts = {
                row.token.start
                for row in predicate_rows
                if row.token.normalized.split()[-1]
                in {"am", "are", "be", "been", "being", "is", "was", "were"}
            }
            predicate_rows = [
                row
                for row in predicate_rows
                if not (
                    row.token.normalized.split()[-1] in _NOMINAL_REPORTING_HEADS
                    and any(start > row.token.end for start in copular_starts)
                    and any(
                        token.normalized in {"price", "cost"}
                        and row.token.end <= token.start < max(copular_starts)
                        for token in clause_tokens
                        if token.kind == "WORD"
                    )
                )
            ]
        segments, list_proofs = _event_segments(
            raw,
            clause,
            tokens,
            predicate_rows,
            clause_mentions,
            bundle.grammar,
        )
        proofs.extend(list_proofs)
        previous_event: EventNodeR14 | None = None
        previous_actor: MentionNodeR14 | None = None
        for segment_index, segment in enumerate(segments):
            segment_predicates = [
                row
                for row in predicate_rows
                if segment.start <= row.token.start < segment.end
            ]
            if not segment_predicates and segment.ambiguous:
                synthetic = _synthetic_ambiguous_predicate(
                    segment, tokens, clause.scope_id, bundle.grammar
                )
                if synthetic is not None:
                    segment_predicates = [synthetic]
            for predicate_index, predicate in enumerate(segment_predicates):
                next_start = (
                    segment_predicates[predicate_index + 1].token.start
                    if predicate_index + 1 < len(segment_predicates)
                    else segment.end
                )
                event_start = segment.start if predicate_index == 0 else predicate.token.start
                event_span = (event_start, next_start)
                subject_span = (event_start, predicate.token.start)
                subject_candidates = _subject_surface_candidates(
                    raw,
                    tokens,
                    clause_mentions,
                    subject_span,
                    clause.scope_id,
                    bundle.grammar,
                    product_spans=clause_product_spans,
                )
                for candidate in subject_candidates:
                    candidate_key = _mention_key(candidate)
                    if candidate_key not in mention_keys:
                        mentions_list.append(candidate)
                        mention_keys.add(candidate_key)
                inherited = False
                actor: MentionNodeR14 | None = None
                if len(subject_candidates) == 1:
                    actor = subject_candidates[0]
                    subject_state = (
                        "explicit"
                        if actor.proof_state == "PROVED"
                        else "explicit_unknown"
                    )
                elif len(subject_candidates) > 1:
                    subject_state = "ambiguous"
                elif (
                    predicate_index == 0
                    and segment.coordinator_span is not None
                    and previous_event is not None
                    and previous_actor is not None
                    and previous_event.subject_state
                    in {"explicit", "inherited_actor_only"}
                    and previous_event.clause_span == clause.clause_span
                    and previous_event.local_scope_id == clause.scope_id
                ):
                    actor = previous_actor
                    inherited = True
                    subject_state = "inherited_actor_only"
                else:
                    subject_state = "unproved"

                event_tokens = _tokens_in(tokens, event_span, clause.scope_id)
                words = {row.normalized for row in event_tokens if row.kind == "WORD"}
                # Target/event semantics belong to the proved predicate head,
                # never to a bag of every word that happens to share its event
                # span.  Material roles remain separate typed edges below.
                semantic_labels = predicate.semantic_labels
                event_types = predicate.event_types
                # A nominal price assertion (for example "said the price of
                # PowerEdge was ...") is an explicit closed structural form,
                # not general target-word bagging.  It may nominate the ASP
                # target only when the same event contains a proved hardware
                # mention and an explicit nominal price head.
                event_mentions = _mentions_in(
                    clause_mentions, event_span, clause.scope_id
                )
                nominal_price_assertion = (
                    bool(words.intersection({"cost", "price", "pricing", "quote"}))
                    and any(
                        row.mention_type == "product_or_hardware"
                        and row.proof_state == "PROVED"
                        for row in event_mentions
                    )
                )
                if nominal_price_assertion:
                    semantic_labels = tuple(
                        sorted(
                            {
                                *semantic_labels,
                                "DELL-RSQ-03A-TARGET-ASP",
                            }
                        )
                    )
                    event_types = tuple(sorted({*event_types, "pricing"}))
                ambiguities: set[str] = set()
                if segment.ambiguous or predicate.proof_type == "AMBIGUOUS-NONCE-EVENT-BARRIER":
                    ambiguities.add("ambiguous_event_barrier")
                if scope_by_id[clause.scope_id].proof_state != "PROVED":
                    ambiguities.add("unclosed_or_mismatched_local_scope")
                if len(subject_candidates) > 1:
                    ambiguities.add("multiple_subject_candidates")
                limitations: set[str] = set()
                if not semantic_labels:
                    limitations.add("predicate_semantic_type_unproved")
                predicate_operator_ids = (
                    canonical_predicate_operator_identity_ids_r14(
                        predicate.token.normalized
                    )
                )
                attribution_mentions = tuple(
                    {
                        row.mention_id: row
                        for row in (*mentions_list, *subject_candidates)
                    }.values()
                )
                speech_mode = canonical_assertion_speech_mode_r14(
                    predicate_span=(predicate.token.start, predicate.token.end),
                    document_span=event_span,
                    sentence_span=clause.sentence_span,
                    local_scope_id=clause.scope_id,
                    assertion_owner_identity_ids=(
                        actor.semantic_identity_ids if actor is not None else ()
                    ),
                    tokens=tokens,
                    mentions=attribution_mentions,
                    reporting_tokens=sentence_reporting_tokens,
                    according_present=sentence_according_present,
                )
                inference_barrier_ids = canonical_event_inference_barrier_ids_r14(
                    tokens=event_tokens,
                    mentions=event_mentions,
                    predicate_operator_ids=predicate_operator_ids,
                    event_types=event_types,
                )
                event = EventNodeR14(
                    event_scope_id=(
                        f"EVENT-SCOPE::R14::{clause_index:05d}:{segment_index:03d}:"
                        f"{predicate_index:03d}"
                    ),
                    local_scope_id=clause.scope_id,
                    document_span=event_span,
                    sentence_span=clause.sentence_span,
                    clause_span=clause.clause_span,
                    predicate_span=(predicate.token.start, predicate.token.end),
                    predicate_surface=raw[predicate.token.start : predicate.token.end],
                    predicate_normalized=predicate.token.normalized,
                    predicate_proof_type=predicate.proof_type,
                    semantic_labels=semantic_labels,
                    event_types=event_types,
                    subject_state=subject_state,
                    assertion_owner_mention_id=actor.mention_id if actor else None,
                    candidate_subject_mention_ids=tuple(
                        row.mention_id for row in subject_candidates
                    ),
                    polarity="negative" if words.intersection(_NEGATION) else "affirmative",
                    modality="modal" if words.intersection(_MODALS) else "asserted",
                    actuality="forward_looking" if words.intersection(_FORWARD) else "actual_or_current",
                    lifecycle="inactive" if words.intersection(_INACTIVE) else "active_or_unspecified",
                    speech_mode=speech_mode,
                    assertion_owner=actor.normalized_value if actor else None,
                    ambiguities=tuple(sorted(ambiguities)),
                    limitations=tuple(sorted(limitations)),
                    semantic_operator_ids=predicate_operator_ids,
                    inference_barrier_ids=inference_barrier_ids,
                )
                events.append(event)

                predicate_mention = MentionNodeR14(
                    mention_type="predicate",
                    raw_value=event.predicate_surface,
                    normalized_value=event.predicate_normalized,
                    start=event.predicate_span[0],
                    end=event.predicate_span[1],
                    type_proof_rule_id=event.predicate_proof_type,
                    local_scope_id=clause.scope_id,
                    proof_state=("AMBIGUOUS" if event.ambiguities else "PROVED"),
                    semantic_identity_ids=tuple(
                        sorted(
                            {
                                *(f"TARGET::{row}" for row in event.semantic_labels),
                                *(f"EVENT_TYPE::{row}" for row in event.event_types),
                                *event.semantic_operator_ids,
                            }
                        )
                    ),
                )
                predicate_key = _mention_key(predicate_mention)
                if predicate_key not in mention_keys:
                    mentions_list.append(predicate_mention)
                    mention_keys.add(predicate_key)
                event_proof = ProofRecordR14(
                    rule_id=("G21-COORD-EVENT" if event.ambiguities else "G20-EXPLICIT-EVENT"),
                    state=("AMBIGUOUS" if event.ambiguities else "PROVED"),
                    conclusion=f"event_candidate:{event.event_scope_id}",
                    premise_spans=(event.predicate_span, event.document_span),
                    premise_node_ids=(predicate_mention.mention_id,),
                )
                proofs.append(event_proof)
                predicate_role_proof = ProofRecordR14(
                    rule_id="G30-ROLE-LOCAL",
                    state=predicate_mention.proof_state,
                    conclusion=f"event_role:predicate:{event.event_scope_id}",
                    premise_spans=(event.predicate_span,),
                    premise_node_ids=(event.event_id, predicate_mention.mention_id),
                )
                proofs.append(predicate_role_proof)
                role_edges.append(
                    RoleEdgeR14(
                        event_scope_id=event.event_scope_id,
                        event_id=event.event_id,
                        role="predicate",
                        mention_id=predicate_mention.mention_id,
                        proof_rule_id="G30-ROLE-LOCAL",
                        proof_state=predicate_mention.proof_state,
                        evidence_spans=(event.predicate_span,),
                        premise_proof_ids=(predicate_role_proof.proof_id,),
                    )
                )

                if actor is not None:
                    actor_state = "PROVED" if inherited or actor.proof_state == "PROVED" else "AMBIGUOUS"
                    actor_rule = "G23-SUBJECT-INHERIT" if inherited else "G30-ROLE-LOCAL"
                    actor_proof = ProofRecordR14(
                        rule_id=actor_rule,
                        state=actor_state,
                        conclusion=f"event_role:actor:{event.event_scope_id}",
                        premise_spans=((actor.start, actor.end), event.predicate_span),
                        premise_node_ids=(event.event_id, actor.mention_id),
                    )
                    proofs.append(actor_proof)
                    role_edges.append(
                        RoleEdgeR14(
                            event_scope_id=event.event_scope_id,
                            event_id=event.event_id,
                            role="actor",
                            mention_id=actor.mention_id,
                            proof_rule_id=actor_rule,
                            proof_state=actor_state,
                            evidence_spans=((actor.start, actor.end), event.predicate_span),
                            premise_proof_ids=(actor_proof.proof_id,),
                        )
                    )
                    if inherited and previous_event is not None and segment.coordinator_span is not None:
                        subject_edges.append(
                            SubjectShareEdgeR14(
                                source_subject_mention_id=actor.mention_id,
                                left_event_id=previous_event.event_id,
                                right_event_id=event.event_id,
                                coordinator_span=segment.coordinator_span,
                            )
                        )

                event_mentions_by_key = {
                    _mention_key(row): row
                    for row in (
                        *_mentions_in(clause_mentions, event_span, clause.scope_id),
                        *subject_candidates,
                        predicate_mention,
                    )
                }
                event_mentions = sorted(
                    event_mentions_by_key.values(),
                    key=lambda row: (
                        row.start,
                        row.end,
                        row.mention_type,
                        row.type_proof_rule_id,
                        row.node_digest,
                    ),
                )
                for mention in event_mentions:
                    if mention.mention_id in {
                        predicate_mention.mention_id,
                        actor.mention_id if actor is not None else "",
                    }:
                        continue
                    role: str | None = None
                    state = (
                        "PROVED"
                        if not event.ambiguities and event.semantic_labels
                        else "AMBIGUOUS"
                        if event.ambiguities
                        else "UNSUPPORTED"
                    )
                    if mention.mention_type == "product_or_hardware":
                        role = "object"
                    elif mention.mention_type == "price":
                        role = "price"
                    elif mention.mention_type == "quantity":
                        role = "quantity"
                    elif mention.mention_type == "quantity_or_percent":
                        role = "measure"
                    elif mention.mention_type == "period":
                        role = "period"
                    elif mention.mention_type == "entity" and mention.start >= event.predicate_span[1]:
                        preceding = [
                            row.normalized
                            for row in event_tokens
                            if row.kind == "WORD" and row.end <= mention.start
                        ]
                        role = (
                            "recipient"
                            if preceding and preceding[-1] in {"to", "for"}
                            else "counterparty"
                        )
                    if role is None:
                        continue
                    rule_id = "G31-TEMPORAL-LOCAL" if role == "period" else "G30-ROLE-LOCAL"
                    relation_nodes = [event.event_id, mention.mention_id]
                    if role in {"quantity", "measure"}:
                        products = [
                            row
                            for row in event_mentions
                            if row.mention_type == "product_or_hardware"
                        ]
                        if len(products) == 1:
                            relation_nodes.append(products[0].mention_id)
                        else:
                            state = "AMBIGUOUS"
                    if mention.start < event.predicate_span[0]:
                        between_words = {
                            row.normalized
                            for row in event_tokens
                            if row.kind == "WORD"
                            and mention.end <= row.start
                            and row.end <= event.predicate_span[0]
                        }
                        pre_predicate_proved = (
                            role == "object"
                            and "pricing" in event.event_types
                            and (
                                event.predicate_normalized.split()[0]
                                in {"was", "were", "is", "are"}
                                or bool(
                                    between_words.intersection(
                                        {"was", "were", "is", "are"}
                                    )
                                )
                            )
                        )
                        if not pre_predicate_proved:
                            state = "UNSUPPORTED"
                    relation_proof = ProofRecordR14(
                        rule_id=rule_id,
                        state=state,
                        conclusion=f"event_role:{role}:{event.event_scope_id}",
                        premise_spans=((mention.start, mention.end), event.predicate_span),
                        premise_node_ids=tuple(relation_nodes),
                    )
                    proofs.append(relation_proof)
                    role_edges.append(
                        RoleEdgeR14(
                            event_scope_id=event.event_scope_id,
                            event_id=event.event_id,
                            role=role,
                            mention_id=mention.mention_id,
                            proof_rule_id=rule_id,
                            proof_state=state,
                            evidence_spans=((mention.start, mention.end), event.predicate_span),
                            premise_proof_ids=(relation_proof.proof_id,),
                        )
                    )
                    if role == "period":
                        temporal_edges.append(
                            TemporalScopeEdgeR14(
                                period_mention_id=mention.mention_id,
                                event_id=event.event_id,
                                scope_type="event_local_single_event",
                                proof_rule_id="G31-TEMPORAL-LOCAL",
                                proof_state=state,
                                evidence_spans=((mention.start, mention.end), event.predicate_span),
                                premise_proof_ids=(relation_proof.proof_id,),
                            )
                        )

                previous_event = event
                if actor is not None and (
                    inherited or actor.proof_state == "PROVED"
                ):
                    previous_actor = actor
                elif subject_candidates:
                    previous_actor = None

    mentions = tuple(
        sorted(
            {_mention_key(row): row for row in mentions_list}.values(),
            key=lambda row: (
                row.start,
                row.end,
                row.mention_type,
                row.type_proof_rule_id,
                row.node_digest,
            ),
        )
    )
    target_bridges = _build_target_bridges_r14(
        events=events,
        mentions=mentions,
        role_edges=role_edges,
    )
    graph = EventArgumentGraphR14(
        raw_text=raw,
        grammar_result_digest=str(bundle.grammar["result_digest"]),
        graph_type_registry_digest=canonical_digest(
            bundle.topology["graph_type_registry"]
        ),
        local_scopes=scopes,
        tokens=tuple(
            sorted(tokens, key=lambda row: (row.start, row.end, row.kind, row.token_digest))
        ),
        events=tuple(
            sorted(
                events,
                key=lambda row: (
                    row.document_span,
                    row.predicate_span,
                    row.event_scope_id,
                    row.node_digest,
                ),
            )
        ),
        mentions=mentions,
        role_edges=tuple(
            sorted(
                role_edges,
                key=lambda row: (
                    row.event_id,
                    row.role,
                    row.mention_id,
                    row.edge_digest,
                ),
            )
        ),
        subject_share_edges=tuple(
            sorted(subject_edges, key=lambda row: row.edge_digest)
        ),
        temporal_edges=tuple(
            sorted(temporal_edges, key=lambda row: row.edge_digest)
        ),
        proofs=tuple(
            sorted(
                {row.proof_id: row for row in proofs}.values(),
                key=lambda row: (
                    row.premise_spans,
                    row.rule_id,
                    row.conclusion,
                    row.proof_digest,
                ),
            )
        ),
        target_bridge_edges=target_bridges,
    )
    validate_event_argument_graph_r14(graph)
    return graph


__all__ = [
    "EventArgumentGraphR14",
    "EventNodeR14",
    "GRAPH_SCHEMA_VERSION",
    "LocalScopeNodeR14",
    "MentionNodeR14",
    "NominalEdgeR14",
    "PRICE_GRAPH_SCHEMA_VERSION",
    "PriceAttachmentGraphR14",
    "PricePathProofR14",
    "ProofRecordR14",
    "RoleEdgeR14",
    "SubjectShareEdgeR14",
    "TemporalScopeEdgeR14",
    "TokenR14",
    "build_event_argument_graph_r14",
    "build_price_attachment_graph_r14",
    "normalize_proof_text",
    "tokenize_r14",
    "validate_event_argument_graph_r14",
    "validate_price_attachment_graph_r14",
]
