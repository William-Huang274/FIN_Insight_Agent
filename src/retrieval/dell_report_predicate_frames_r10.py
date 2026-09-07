from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Iterable, Mapping, Sequence

from . import dell_report_internal_chain_ceiling_r4 as r4
from . import dell_report_proposition_semantics_r7 as r7
from .query_plan import canonical_digest


ASP_TARGET = r7.ASP_TARGET
SUPPLIER_TARGET = r7.SUPPLIER_TARGET
CAPACITY_TARGET = r7.CAPACITY_TARGET
YIELD_TARGET = r7.YIELD_TARGET
HBM_TARGET = r7.HBM_TARGET
UNITS_TARGET = r7.UNITS_TARGET
TARGET_IDS = r7.TARGET_IDS


@dataclass(frozen=True)
class RoleBinding:
    role: str
    raw_text: str
    normalized_value: str
    span_start: int
    span_end: int
    source_kind: str = "frame_regex_argument"

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "raw_text": self.raw_text,
            "normalized_value": self.normalized_value,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "source_kind": self.source_kind,
        }


@dataclass(frozen=True)
class FrameBoundaryDecision:
    sentence_index: int
    span_start: int
    span_end: int
    raw_text: str
    decision: str
    reason: str
    left_predicate_span: tuple[int, int] | None
    right_subject_span: tuple[int, int] | None
    right_predicate_span: tuple[int, int] | None
    decision_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "sentence_index": self.sentence_index,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "raw_text": self.raw_text,
            "decision": self.decision,
            "reason": self.reason,
            "left_predicate_span": (
                list(self.left_predicate_span)
                if self.left_predicate_span is not None
                else None
            ),
            "right_subject_span": (
                list(self.right_subject_span)
                if self.right_subject_span is not None
                else None
            ),
            "right_predicate_span": (
                list(self.right_predicate_span)
                if self.right_predicate_span is not None
                else None
            ),
            "decision_digest": self.decision_digest,
        }


@dataclass(frozen=True)
class ScopeEdge:
    source_modifier_frame_id: str
    target_assertion_frame_id: str
    relation: str
    evidence_span_start: int
    evidence_span_end: int
    modifier_span_start: int
    modifier_span_end: int
    target_predicate_span_start: int
    target_predicate_span_end: int
    normalized_value: str
    edge_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_modifier_frame_id": self.source_modifier_frame_id,
            "target_assertion_frame_id": self.target_assertion_frame_id,
            "relation": self.relation,
            "evidence_span_start": self.evidence_span_start,
            "evidence_span_end": self.evidence_span_end,
            "modifier_span_start": self.modifier_span_start,
            "modifier_span_end": self.modifier_span_end,
            "target_predicate_span_start": self.target_predicate_span_start,
            "target_predicate_span_end": self.target_predicate_span_end,
            "normalized_value": self.normalized_value,
            "edge_digest": self.edge_digest,
        }


@dataclass(frozen=True)
class ArgumentGroupBinding:
    group_id: str
    span_start: int
    span_end: int
    raw_text: str
    governing_predicate_span: tuple[int, int]
    object_class: str
    object_span: tuple[int, int] | None
    product_span: tuple[int, int] | None
    normalized_product: str | None
    price_span: tuple[int, int]
    normalized_price: str
    attachment: str
    ambiguity: str | None
    group_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "raw_text": self.raw_text,
            "governing_predicate_span": list(self.governing_predicate_span),
            "object_class": self.object_class,
            "object_span": (
                list(self.object_span) if self.object_span is not None else None
            ),
            "product_span": (
                list(self.product_span) if self.product_span is not None else None
            ),
            "normalized_product": self.normalized_product,
            "price_span": list(self.price_span),
            "normalized_price": self.normalized_price,
            "attachment": self.attachment,
            "ambiguity": self.ambiguity,
            "group_digest": self.group_digest,
        }


@dataclass(frozen=True)
class PredicateFrame:
    frame_id: str
    frame_digest: str
    assertion_frame_id: str
    target_id: str
    sentence_index: int
    frame_index: int
    span_start: int
    span_end: int
    predicate_span_start: int
    predicate_span_end: int
    frame_text: str
    role_bindings: tuple[RoleBinding, ...]
    scope_bindings: tuple[RoleBinding, ...]
    scope_edges: tuple[ScopeEdge, ...]
    argument_groups: tuple[ArgumentGroupBinding, ...]
    polarity: str
    actuality: str
    lifecycle_status: str
    assertion_owner: RoleBinding | None
    modality: str
    status: str
    speech_mode: str
    matched_group_ids: tuple[str, ...]
    missing_required_roles: tuple[str, ...]
    ambiguities: tuple[str, ...]
    limitations: tuple[str, ...]
    role_anchors: tuple[str, ...]
    representation_frame_digest: str
    semantic_signature_digest: str
    accepted: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "frame_digest": self.frame_digest,
            "assertion_frame_id": self.assertion_frame_id,
            "target_id": self.target_id,
            "sentence_index": self.sentence_index,
            "frame_index": self.frame_index,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "predicate_span_start": self.predicate_span_start,
            "predicate_span_end": self.predicate_span_end,
            "frame_text": self.frame_text,
            "role_bindings": [row.as_dict() for row in self.role_bindings],
            "scope_bindings": [row.as_dict() for row in self.scope_bindings],
            "scope_edges": [row.as_dict() for row in self.scope_edges],
            "argument_groups": [row.as_dict() for row in self.argument_groups],
            "polarity": self.polarity,
            "actuality": self.actuality,
            "lifecycle_status": self.lifecycle_status,
            "assertion_owner": (
                self.assertion_owner.as_dict()
                if self.assertion_owner is not None
                else None
            ),
            "modality": self.modality,
            "status": self.status,
            "speech_mode": self.speech_mode,
            "matched_group_ids": list(self.matched_group_ids),
            "missing_required_roles": list(self.missing_required_roles),
            "ambiguities": list(self.ambiguities),
            "limitations": list(self.limitations),
            "role_anchors": list(self.role_anchors),
            "representation_frame_digest": self.representation_frame_digest,
            "semantic_signature_digest": self.semantic_signature_digest,
            "accepted": self.accepted,
        }

    def bindings(self, role: str) -> tuple[RoleBinding, ...]:
        return tuple(row for row in self.role_bindings if row.role == role)


@dataclass(frozen=True)
class FrameRecord:
    sentence_index: int
    frame_index: int
    span_start: int
    span_end: int
    text: str
    sentence_text: str


_FRAME_BOUNDARY = re.compile(
    r"\s*;\s*|(?:,\s*|\s+)(?:and|but|while|whereas)\s+|"
    r"\s+alongside\s+",
    re.IGNORECASE,
)
_RESIDUAL_PERIOD_BOUNDARY = re.compile(r"\s*\.\s+")
_ABBREVIATION_SUFFIX = re.compile(
    r"(?:\b(?:inc|corp|ltd|co|no|vs|mr|mrs|ms|dr|st)|\b[a-z]\.[a-z])$",
    re.IGNORECASE,
)

_NEGATIVE = re.compile(
    r"\b(?:not|never|no\s+longer|did\s+not|does\s+not|do\s+not|"
    r"has\s+not|have\s+not|had\s+not|was\s+not|were\s+not|"
    r"is\s+not|are\s+not|cannot|can't|didn't|doesn't|isn't|aren't|"
    r"wasn't|weren't|hasn't|haven't|hadn't|failed?\s+to|unable\s+to|"
    r"declin(?:e|es|ed|ing)\s+to|refus(?:e|es|ed|ing)\s+to|"
    r"den(?:y|ies|ied|ying)|disput(?:e|es|ed|ing)|"
    r"reject(?:s|ed|ing)?|refut(?:e|es|ed|ing)|unavailable|without|"
    r"lack(?:s|ed|ing)?)\b"
)
_ALLEGED = re.compile(
    r"\b(?:alleg(?:e|es|ed|edly|ation|ations)|rumou?r(?:s|ed)?|"
    r"purport(?:s|ed|edly|ing)?|unconfirmed|speculat(?:e|es|ed|ion)|"
    r"reportedly)\b"
)
_MODAL = re.compile(
    r"\b(?:can|could|may|might|would|should|will|"
    r"expect(?:s|ed|ing)?|forecast(?:s|ed|ing)?|"
    r"anticipat(?:e|es|ed|ing)|estimat(?:e|es|ed|ing)|"
    r"plan(?:s|ned|ning)?\s+(?:to|on|for)|propos(?:e|es|ed|ing)|"
    r"intend(?:s|ed|ing)?|aim(?:s|ed|ing)?|target(?:s|ed|ing)?|"
    r"explor(?:e|es|ed|ing)|consider(?:s|ed|ing)?|evaluat(?:e|es|ed|ing)|"
    r"discuss(?:es|ed|ing)?|indicative|preliminary|hypothetical|likely|"
    r"possibly|potentially)\b"
)
_REVOKED = re.compile(
    r"\b(?:revok(?:e|es|ed|ing)|suspend(?:s|ed|ing)?|"
    r"withdraw(?:s|n|ing)?|withdrew|cancel(?:s|l?ed|ling|ing)?|"
    r"terminat(?:e|es|ed|ing)|dissolv(?:e|es|ed|ing)|"
    r"retract(?:s|ed|ing)?|discontinu(?:e|es|ed|ing)|"
    r"expire(?:s|d|ing)?|ended?)\b"
)
_COREFERENTIAL_RETRACTION = re.compile(
    r"^(?:(?:the|this|that|its)\s+)?(?:partnership|collaboration|alliance|relationship|"
    r"allocation|capacity|commitment|quote|price|offer|yield|figure|"
    r"measure|rate|configuration|supply|shipment|delivery|report)\b"
    r"[^.;]{0,96}\b(?:revok(?:e|es|ed|ing)|suspend(?:s|ed|ing)?|"
    r"withdraw(?:s|n|ing)?|withdrew|cancel(?:s|l?ed|ling|ing)?|"
    r"terminat(?:e|es|ed|ing)|dissolv(?:e|es|ed|ing)|"
    r"retract(?:s|ed|ing)?|discontinu(?:e|es|ed|ing)|"
    r"expire(?:s|d|ing)?|ended?)\b",
    re.IGNORECASE,
)
_TRAILING_EPISTEMIC = re.compile(
    r"^\s*(?:[^,;]{0,64},\s*)?(?:allegedly|reportedly|rumou?red|"
    r"according\s+to\s+(?:an?\s+)?(?:unconfirmed|alleged|rumou?red)\s+"
    r"(?:report|source|claim))\b",
    re.IGNORECASE,
)
_WRONG_PROCESS = re.compile(
    r"\b(?:prototype(?:-line)?|pilot(?:\s+line)?|trial|test(?:ing)?|"
    r"simulat(?:e|es|ed|ion)|a14|sram|n2|next\s+process|orange\s+juice)\b"
)
_REPORTING = re.compile(
    r"\b(?P<reporter>(?:a\s+)?(?:customer|analyst|source|report|"
    r"nvidia|dell|[a-z][a-z0-9-]{1,24}))\s+"
    r"(?P<verb>said|reported|claimed|stated|announced|disclosed)\b"
)
_LEADING_ATTRIBUTION = re.compile(
    r"^\s*according\s+to\s+(?P<reporter>(?:an?\s+)?(?:analyst|source|"
    r"report|customer|supplier|industry\s+observer))\s*,",
    re.IGNORECASE,
)

_NAMED_SUPPLIER = re.compile(
    r"\b(nvidia|micron|tsmc|taiwan\s+semiconductor|sk\s+hynix|broadcom)\b"
)
_COMPANY = re.compile(
    r"\b(dell|nvidia|micron|tsmc|taiwan\s+semiconductor|sk\s+hynix|"
    r"broadcom|hp|hpe)\b"
)

_ASP_PREDICATE = re.compile(
    r"\b(quoted?|pricing|priced?|sold|sale|offered?|purchase\s+price|"
    r"configuration\s+price|recommended\s+price|contract\s+amount|"
    r"total\s+contract\s+cost|contract\s+cost)\b"
)
_SUPPLIER_PREDICATE = re.compile(
    r"\b(partner(?:s|ed|ing|ship)?|collaborat(?:e|es|ed|ing|ion)|"
    r"alliance|team(?:s|ed|ing)?\s+up|supplier|"
    r"provid(?:e|es|ed|ing)|suppl(?:y|ies|ied|ying)|"
    r"deliver(?:s|ed|ing|y)?|ship(?:s|ped|ping)?)\b"
)
_CAPACITY_PREDICATE = re.compile(
    r"\b(releas(?:e|es|ed|ing)|allocat(?:e|es|ed|ing)|"
    r"earmark(?:s|ed|ing)?|reserv(?:e|es|ed|ing)|"
    r"commit(?:s|ted|ting)?|dedicat(?:e|es|ed|ing)|"
    r"assign(?:s|ed|ing)?|grant(?:s|ed|ing)?|"
    r"secur(?:e|es|ed|ing)|receiv(?:e|es|ed|ing)|available|"
    r"suppl(?:y|ies|ied|ying))\b"
)
_CAPACITY_SURFACE = re.compile(
    r"\b(?:gpu|hbm|component|production)?\s*"
    r"(?:capacity|allocation|supply)\b"
)
_YIELD_PREDICATE = re.compile(
    r"\b(yield(?:s|ed|ing)?|achiev(?:e|es|ed|ing)|reached?|"
    r"recorded?|reported?|was|is|stood|measured)\b"
)
_HBM_PREDICATE = re.compile(
    r"\b(use(?:s|d|ing)?|allocat(?:e|es|ed|ing)|"
    r"earmark(?:s|ed|ing)?|configur(?:e|es|ed|ing)|"
    r"equip(?:s|ped|ping)?|incorporat(?:e|es|ed|ing)|"
    r"integrat(?:e|es|ed|ing)|power(?:s|ed|ing)?|"
    r"suppl(?:y|ies|ied|ying)|available)\b"
)
_UNITS_PREDICATE = re.compile(
    r"\b(shipped|delivered|sent|dispatch(?:es|ed|ing)?|sold)\b"
)
_FRAME_PREDICATE_HINT = re.compile(
    r"\b(?:quoted?|pricing|priced?|sold|offered?|partner(?:s|ed|ing|ship)?|"
    r"collaborat(?:e|es|ed|ing|ion)|suppl(?:y|ies|ied|ying)|"
    r"provid(?:e|es|ed|ing)|deliver(?:s|ed|ing|y)?|ship(?:s|ped|ping)?|"
    r"releas(?:e|es|ed|ing)|allocat(?:e|es|ed|ing)|available|"
    r"yield(?:s|ed|ing)?|achiev(?:e|es|ed|ing)|use(?:s|d|ing)?|"
    r"configur(?:e|es|ed|ing)|dispatch(?:es|ed|ing)?|"
    r"discontinu(?:e|es|ed|ing)|suspend(?:s|ed|ing)?|"
    r"revok(?:e|es|ed|ing)|withdraw(?:s|n|ing)?|withdrew|"
    r"was|were|is|are|has|have|will|rose|grew|target|announced|received)\b"
)
_FRAME_RIGHT_SUBJECT = re.compile(
    r"^(?:dell|nvidia|micron|tsmc|broadcom|hp|hpe|gpu|hbm|"
    r"poweredge|production|manufacturing|yield|utilization|capacity|"
    r"allocation|solar|orange|next\s+process|another|a\s+separate|"
    r"the\s+\w+)\b"
)

_RIGHT_PREFIX_WITHOUT_OWNER = re.compile(
    r"^(?:later|subsequently|then|also|again|still|reportedly|allegedly)$",
    re.IGNORECASE,
)

_TARGET_CONTRACT = {
    ASP_TARGET: {
        "required": (
            "dell_subject",
            "affirmative_price_quote",
            "price_surface",
            "bounded_object",
        ),
        "complete_role": "bounded_configuration_or_bundle_price_package",
        "partial_role": "price_or_configuration_context",
    },
    SUPPLIER_TARGET: {
        "required": (
            "dell_subject",
            "named_supplier",
            "directional_relationship_delivery",
        ),
        "complete_role": "supplier_to_Dell_relationship_delivery",
        "partial_role": "supplier_or_relationship_context",
    },
    CAPACITY_TARGET: {
        "required": (
            "relevant_supply",
            "capacity_or_availability_event",
            "upstream_Dell_allocation",
            "timing_surface",
        ),
        "complete_role": "upstream_capacity_release_to_Dell",
        "partial_role": "product_availability_or_delivery_context",
    },
    YIELD_TARGET: {
        "required": (
            "relevant_supply",
            "observed_yield_or_utilization",
            "observed_measure",
            "timing_surface",
        ),
        "complete_role": "observed_relevant_supply_yield_or_utilization",
        "partial_role": "yield_or_utilization_context",
    },
    HBM_TARGET: {
        "required": (
            "hbm_subject",
            "supply_state",
            "directional_Dell_bridge",
            "timing_surface",
        ),
        "complete_role": "HBM_supply_with_Dell_configuration_or_allocation_bridge",
        "partial_role": "HBM_supply_context",
    },
    UNITS_TARGET: {
        "required": (
            "dell_subject",
            "physical_server_quantity",
            "Dell_seller_or_shipper_role",
            "timing_surface",
        ),
        "complete_role": "Dell_company_period_physical_server_shipments",
        "partial_role": "qualitative_shipment_or_noncompany_count_context",
    },
}


def normalize_text(value: Any) -> str:
    return r7.normalize_text(value)


def _absolute_match_span(
    match: re.Match[str] | None,
    *,
    sentence_start: int,
    local_start: int,
) -> tuple[int, int] | None:
    if match is None:
        return None
    return (
        sentence_start + local_start + match.start(),
        sentence_start + local_start + match.end(),
    )


def _structural_right_owner_span(
    right: str,
    right_predicate: re.Match[str] | None,
) -> tuple[int, int] | None:
    """Return the lexical prefix before a right-hand predicate.

    This is deliberately open-vocabulary.  The decision is based on clause
    structure rather than a company/entity allowlist.  A predicate at offset
    zero is a shared-subject continuation; a bare discourse adverb is also not
    promoted to an assertion owner.
    """

    if right_predicate is None or right_predicate.start() <= 0:
        return None
    prefix = right[: right_predicate.start()]
    leading = len(prefix) - len(prefix.lstrip())
    trailing = len(prefix.rstrip())
    if trailing <= leading:
        return None
    surface = prefix[leading:trailing]
    if not re.search(r"[A-Za-z0-9]", surface):
        return None
    if _RIGHT_PREFIX_WITHOUT_OWNER.fullmatch(surface):
        return None
    return leading, trailing


def _make_boundary_decision(
    sentence: str,
    boundary: re.Match[str],
    *,
    sentence_index: int,
    sentence_start: int,
    current_start: int,
) -> FrameBoundaryDecision:
    raw = boundary.group(0)
    token = raw.strip().casefold()
    left = sentence[current_start : boundary.start()]
    right = sentence[boundary.end() :]
    left_matches = list(_FRAME_PREDICATE_HINT.finditer(left))
    left_predicate = left_matches[-1] if left_matches else None
    lexical_right_subject = _FRAME_RIGHT_SUBJECT.match(right)
    right_predicate = _FRAME_PREDICATE_HINT.search(right)
    structural_right_owner = _structural_right_owner_span(
        right,
        right_predicate,
    )
    if token.startswith(";") and _COREFERENTIAL_RETRACTION.search(right.strip()):
        decision = "scope_attach"
        reason = "typed_coreferential_state_clause"
    elif token.startswith(";") or "alongside" in token:
        decision = "split"
        reason = "explicit_clause_boundary"
    elif left_predicate and structural_right_owner and right_predicate:
        decision = "split"
        reason = (
            "coordinator_with_left_predicate_and_structural_"
            "right_owner_predicate"
        )
    elif not left_predicate and right_predicate:
        left_companies = list(_COMPANY.finditer(left))
        if left_companies and lexical_right_subject and _COMPANY.fullmatch(
            lexical_right_subject.group(0)
        ):
            decision = "compound_subject"
            reason = "company_coordinator_precedes_shared_predicate"
        else:
            decision = "shared_subject"
            reason = "coordinator_precedes_shared_predicate"
    else:
        decision = "no_split"
        reason = "no_independent_right_subject_predicate_frame"
    body = {
        "sentence_index": sentence_index,
        "span_start": sentence_start + boundary.start(),
        "span_end": sentence_start + boundary.end(),
        "raw_text": raw,
        "decision": decision,
        "reason": reason,
        "left_predicate_span": _absolute_match_span(
            left_predicate,
            sentence_start=sentence_start,
            local_start=current_start,
        ),
        "right_subject_span": (
            (
                sentence_start + boundary.end() + structural_right_owner[0],
                sentence_start + boundary.end() + structural_right_owner[1],
            )
            if structural_right_owner is not None
            else _absolute_match_span(
                lexical_right_subject,
                sentence_start=sentence_start,
                local_start=boundary.end(),
            )
        ),
        "right_predicate_span": _absolute_match_span(
            right_predicate,
            sentence_start=sentence_start,
            local_start=boundary.end(),
        ),
    }
    digest = canonical_digest(body)
    return FrameBoundaryDecision(
        sentence_index=sentence_index,
        span_start=body["span_start"],
        span_end=body["span_end"],
        raw_text=raw,
        decision=decision,
        reason=reason,
        left_predicate_span=body["left_predicate_span"],
        right_subject_span=body["right_subject_span"],
        right_predicate_span=body["right_predicate_span"],
        decision_digest=digest,
    )


def frame_boundary_decisions(text: str) -> list[FrameBoundaryDecision]:
    decisions: list[FrameBoundaryDecision] = []
    normalized_document = normalize_text(text)
    document_cursor = 0
    raw_sentences = [
        sentence
        for chunk in r4._sentence_units(text)  # noqa: SLF001
        for sentence in _residual_sentence_units(chunk)
        if sentence.strip()
    ]
    for sentence_index, raw_sentence in enumerate(raw_sentences):
        sentence = normalize_text(raw_sentence)
        if not sentence:
            continue
        sentence_start = normalized_document.find(sentence, document_cursor)
        if sentence_start < 0:
            raise ValueError("R10_normalized_sentence_provenance_lost")
        document_cursor = sentence_start + len(sentence)
        current_start = 0
        for boundary in _FRAME_BOUNDARY.finditer(sentence):
            decision = _make_boundary_decision(
                sentence,
                boundary,
                sentence_index=sentence_index,
                sentence_start=sentence_start,
                current_start=current_start,
            )
            decisions.append(decision)
            if decision.decision in {"split", "scope_attach"}:
                current_start = boundary.end()
    return decisions


def _residual_sentence_units(chunk: str) -> list[str]:
    """Split malformed residual boundaries without breaking ``U.S.`` etc."""

    pieces: list[str] = []
    cursor = 0
    for boundary in _RESIDUAL_PERIOD_BOUNDARY.finditer(chunk):
        left = chunk[cursor : boundary.start()].rstrip()
        whitespace_before_period = bool(
            chunk[boundary.start() : boundary.end()].lstrip().startswith(".")
            and boundary.start() < len(chunk)
            and chunk[boundary.start()].isspace()
        )
        if (
            not whitespace_before_period
            and _ABBREVIATION_SUFFIX.search(left)
        ):
            continue
        if left:
            pieces.append(left)
        cursor = boundary.end()
    tail = chunk[cursor:].strip()
    if tail:
        pieces.append(tail)
    return pieces or ([chunk.strip()] if chunk.strip() else [])


def _is_frame_boundary(
    sentence: str,
    boundary: re.Match[str],
    *,
    current_start: int,
) -> bool:
    decision = _make_boundary_decision(
        sentence,
        boundary,
        sentence_index=0,
        sentence_start=0,
        current_start=current_start,
    )
    return decision.decision in {"split", "scope_attach"}


def frame_records(text: str) -> list[FrameRecord]:
    records: list[FrameRecord] = []
    normalized_document = normalize_text(text)
    document_cursor = 0
    raw_sentences = [
        sentence
        for chunk in r4._sentence_units(text)  # noqa: SLF001
        for sentence in _residual_sentence_units(chunk)
        if sentence.strip()
    ]
    for sentence_index, raw_sentence in enumerate(raw_sentences):
        sentence = normalize_text(raw_sentence)
        if not sentence:
            continue
        sentence_start = normalized_document.find(sentence, document_cursor)
        if sentence_start < 0:
            raise ValueError("R10_normalized_sentence_provenance_lost")
        document_cursor = sentence_start + len(sentence)
        cursor = 0
        pieces: list[tuple[int, int]] = []
        for boundary in _FRAME_BOUNDARY.finditer(sentence):
            if not _is_frame_boundary(
                sentence,
                boundary,
                current_start=cursor,
            ):
                continue
            if boundary.start() > cursor:
                pieces.append((cursor, boundary.start()))
            cursor = boundary.end()
        if cursor < len(sentence):
            pieces.append((cursor, len(sentence)))
        if not pieces:
            pieces = [(0, len(sentence))]
        for frame_index, (start, end) in enumerate(pieces):
            while start < end and sentence[start] in " ,":
                start += 1
            while end > start and sentence[end - 1] in " ,":
                end -= 1
            if start == end:
                continue
            records.append(
                FrameRecord(
                    sentence_index=sentence_index,
                    frame_index=frame_index,
                    span_start=sentence_start + start,
                    span_end=sentence_start + end,
                    text=sentence[start:end],
                    sentence_text=sentence,
                )
            )
    return records


def _binding(
    record: FrameRecord,
    role: str,
    match: re.Match[str],
    normalized_value: str,
    *,
    source_kind: str = "frame_regex_argument",
) -> RoleBinding:
    return RoleBinding(
        role=role,
        raw_text=match.group(0),
        normalized_value=normalized_value,
        span_start=record.span_start + match.start(),
        span_end=record.span_start + match.end(),
        source_kind=source_kind,
    )


def _literal_binding(
    record: FrameRecord,
    role: str,
    start: int,
    end: int,
    normalized_value: str,
    *,
    source_kind: str = "frame_argument_normalization",
) -> RoleBinding:
    return RoleBinding(
        role=role,
        raw_text=record.text[start:end],
        normalized_value=normalized_value,
        span_start=record.span_start + start,
        span_end=record.span_start + end,
        source_kind=source_kind,
    )


def _first_company_before(
    record: FrameRecord, predicate: re.Match[str]
) -> RoleBinding | None:
    matches = list(_COMPANY.finditer(record.text[: predicate.start()]))
    if not matches:
        return None
    match = matches[-1]
    value = match.group(1)
    return _binding(record, "actor", match, "Dell" if value == "dell" else value.title())


def _dell_binding(record: FrameRecord, role: str = "recipient") -> RoleBinding | None:
    match = re.search(r"\b(?:dell|poweredge)\b", record.text)
    return _binding(record, role, match, "Dell") if match else None


def _product_bindings(record: FrameRecord) -> list[RoleBinding]:
    output: list[RoleBinding] = []
    for product, (start, end) in r7._product_matches(record.text):  # noqa: SLF001
        output.append(
            _literal_binding(record, "product", start, end, product)
        )
    if output:
        return output
    patterns = (
        (r"\b(?:dell\s+)?poweredge(?:\s+(?:ai\s+)?servers?)?\b", "dell_poweredge_server"),
        (r"\b(?:ai|gpu|accelerator)\s+(?:servers?|systems?|nodes?)\b", "ai_server_system"),
        (r"\b(?:hardware|equipment|bundle)\b", "bounded_hardware_configuration"),
    )
    for pattern, value in patterns:
        if match := re.search(pattern, record.text):
            output.append(_binding(record, "product", match, value))
            break
    return output


def _price_bindings(record: FrameRecord) -> list[RoleBinding]:
    candidates: list[tuple[int, re.Match[str]]] = []
    for pattern in (r7._PRICE_PREFIX, r7._PRICE_SUFFIX):  # noqa: SLF001
        candidates.extend((match.start(), match) for match in pattern.finditer(record.text))
    output: list[RoleBinding] = []
    for _, match in sorted(candidates, key=lambda row: (row[0], row[1].end())):
        number = r7._normalized_number(match.group("number"))  # noqa: SLF001
        output.append(_binding(record, "price", match, number))
    return output


def _period_bindings(record: FrameRecord) -> list[RoleBinding]:
    output: list[RoleBinding] = []
    occupied: set[tuple[int, int]] = set()
    for pattern, role in (
        (r7._FY, "period.fiscal_year"),  # noqa: SLF001
        (r7._FISCAL_YEAR, "period.fiscal_year"),  # noqa: SLF001
    ):
        for match in pattern.finditer(record.text):
            span = match.span()
            if span in occupied:
                continue
            occupied.add(span)
            output.append(
                _binding(
                    record,
                    role,
                    match,
                    r7._canonical_year(match.group(1)),  # noqa: SLF001
                )
            )
    for match in r7._QUARTER.finditer(record.text):  # noqa: SLF001
        output.append(_binding(record, "period.quarter", match, match.group(1)))
        if match.group(2):
            output.append(
                _binding(record, "period.calendar_year", match, match.group(2))
            )
        occupied.add(match.span())
    for match in r7._YEAR.finditer(record.text):  # noqa: SLF001
        if any(match.start() >= start and match.end() <= end for start, end in occupied):
            continue
        output.append(
            _binding(record, "period.calendar_year", match, match.group(1))
        )
    return sorted(output, key=lambda row: (row.span_start, row.role))


def _quantity_bindings(record: FrameRecord) -> list[RoleBinding]:
    output: list[RoleBinding] = []
    for match in r7._QUANTITY.finditer(record.text):  # noqa: SLF001
        raw = match.group("number")
        value = r7._NUMBER_WORDS.get(raw, r7._normalized_number(raw))  # noqa: SLF001
        output.append(_binding(record, "quantity.physical_server", match, value))
    return output


def _modifier_frame_id(
    *,
    sentence_index: int,
    span_start: int,
    span_end: int,
    raw_text: str,
) -> str:
    digest = canonical_digest(
        {
            "sentence_index": sentence_index,
            "span_start": span_start,
            "span_end": span_end,
            "raw_text": raw_text,
        }
    )
    return f"MODIFIER::R10::{digest[:24].upper()}"


def _scope_edge(
    *,
    source_modifier_frame_id: str,
    target_assertion_frame_id: str,
    relation: str,
    evidence_span_start: int,
    evidence_span_end: int,
    target_predicate_span_start: int,
    target_predicate_span_end: int,
    normalized_value: str,
) -> ScopeEdge:
    body = {
        "source_modifier_frame_id": source_modifier_frame_id,
        "target_assertion_frame_id": target_assertion_frame_id,
        "relation": relation,
        "evidence_span_start": evidence_span_start,
        "evidence_span_end": evidence_span_end,
        "modifier_span_start": evidence_span_start,
        "modifier_span_end": evidence_span_end,
        "target_predicate_span_start": target_predicate_span_start,
        "target_predicate_span_end": target_predicate_span_end,
        "normalized_value": normalized_value,
    }
    return ScopeEdge(**body, edge_digest=canonical_digest(body))


def _lifecycle_value(raw_text: str) -> str:
    value = normalize_text(raw_text)
    if re.search(r"suspend", value):
        return "suspended"
    if re.search(r"discontinu", value):
        return "discontinued"
    if re.search(r"revok|retract", value):
        return "revoked"
    if re.search(r"expir|ended?", value):
        return "expired"
    return "withdrawn_or_terminated"


def _actuality_value(raw_text: str) -> str:
    value = normalize_text(raw_text)
    if re.search(r"explor|consider|evaluat|discuss", value):
        return "exploratory"
    if re.search(r"\b(?:can|could|may|might|would|should)\b", value):
        return "capability"
    return "forward_looking"


def _scope_state(
    record: FrameRecord,
    *,
    target_id: str,
    predicate: re.Match[str],
    roles: Sequence[RoleBinding],
    assertion_frame_id: str,
) -> tuple[
    str,
    str,
    str,
    str,
    RoleBinding | None,
    tuple[RoleBinding, ...],
    tuple[ScopeEdge, ...],
    tuple[str, ...],
]:
    assertion_end = max(
        [predicate.end()]
        + [row.span_end - record.span_start for row in roles]
    )
    assertion_scope = re.sub(
        r"\b(?:not\s+(?:only|alone)|not\s+previously\s+disclosed|"
        r"not\s+constrained|no\s+later\s+than)\b",
        "",
        record.text[:assertion_end],
    )
    trailing_scope = record.text[assertion_end:]
    bindings: list[RoleBinding] = []
    edges: list[ScopeEdge] = []
    limitations: list[str] = []
    polarity = "affirmative"
    actuality = "actual"
    lifecycle_status = "active"
    speech_mode = "direct"
    assertion_owner: RoleBinding | None = None

    def add_edge(
        match: re.Match[str], relation: str, normalized_value: str
    ) -> None:
        evidence_start = record.span_start + match.start()
        evidence_end = record.span_start + match.end()
        edges.append(
            _scope_edge(
                source_modifier_frame_id=_modifier_frame_id(
                    sentence_index=record.sentence_index,
                    span_start=evidence_start,
                    span_end=evidence_end,
                    raw_text=match.group(0),
                ),
                target_assertion_frame_id=assertion_frame_id,
                relation=relation,
                evidence_span_start=evidence_start,
                evidence_span_end=evidence_end,
                target_predicate_span_start=record.span_start + predicate.start(),
                target_predicate_span_end=record.span_start + predicate.end(),
                normalized_value=normalized_value,
            )
        )
    negative_match = _NEGATIVE.search(assertion_scope)
    if target_id == SUPPLIER_TARGET and not negative_match:
        negative_match = re.search(
            r"\bno\s+(?:partnership|collaboration|alliance|relationship)\b",
            assertion_scope,
        )
    if target_id == SUPPLIER_TARGET and not negative_match and re.search(
        r"\b(?:partnership|collaboration|alliance|relationship|rumou?r)\b"
        r"[^.;]{0,64}\b(?:denied|disputed|refuted|rejected)\b",
        trailing_scope,
    ):
        negative_match = next(
            match
            for match in _NEGATIVE.finditer(record.text)
            if match.start() >= assertion_end
        )
    if negative_match:
        polarity = "negative"
        bindings.append(
            _binding(record, "scope.polarity", negative_match, "negative")
        )
        add_edge(negative_match, "governs_polarity", "negative")
        limitations.append("negative_or_denied_target_frame")
    alleged_match = _ALLEGED.search(assertion_scope)
    if not alleged_match and _TRAILING_EPISTEMIC.search(trailing_scope):
        alleged_match = next(
            (
                match
                for match in _ALLEGED.finditer(record.text)
                if match.start() >= assertion_end
            ),
            None,
        )
    if (
        not alleged_match
        and target_id == SUPPLIER_TARGET
        and re.match(r"^\s+rumou?r\b", trailing_scope)
    ):
        alleged_match = next(
            match
            for match in _ALLEGED.finditer(record.text)
            if match.start() >= assertion_end
        )
    if alleged_match:
        actuality = "alleged"
        bindings.append(
            _binding(
                record,
                "scope.actuality",
                alleged_match,
                actuality,
            )
        )
        add_edge(
            alleged_match,
            "governs_actuality",
            actuality,
        )
        limitations.append("alleged_rumor_or_unconfirmed_target_frame")
    elif match := _MODAL.search(assertion_scope):
        actuality = _actuality_value(match.group(0))
        bindings.append(
            _binding(
                record,
                "scope.actuality",
                match,
                actuality,
            )
        )
        add_edge(match, "governs_actuality", actuality)
        limitations.append(f"{actuality}_target_frame")
    revoked_match = _REVOKED.search(assertion_scope)
    if not revoked_match:
        target_nouns = {
            ASP_TARGET: r"\b(?:quote|price|offer|it|this|that)\b",
            SUPPLIER_TARGET: (
                r"\b(?:partnership|collaboration|alliance|relationship|"
                r"it|this|that)\b"
            ),
            CAPACITY_TARGET: (
                r"\b(?:allocation|capacity|commitment|it|this|that)\b"
            ),
            YIELD_TARGET: r"\b(?:yield|figure|measure|rate|it|this|that)\b",
            HBM_TARGET: (
                r"\b(?:allocation|configuration|supply|bridge|it|this|that)\b"
            ),
            UNITS_TARGET: (
                r"\b(?:shipment|delivery|report|it|this|that)\b"
            ),
        }
        tail_revoked = _REVOKED.search(trailing_scope)
        if tail_revoked and (
            re.search(target_nouns[target_id], trailing_scope)
            or re.match(
                r"^\s*(?:was|were|is|are|has\s+been|had\s+been)\b",
                trailing_scope,
            )
        ):
            revoked_match = next(
                match
                for match in _REVOKED.finditer(record.text)
                if match.start() >= assertion_end
            )
    if revoked_match:
        lifecycle_status = _lifecycle_value(revoked_match.group(0))
        bindings.append(
            _binding(
                record,
                "scope.lifecycle_status",
                revoked_match,
                lifecycle_status,
            )
        )
        add_edge(
            revoked_match,
            "changes_lifecycle_status",
            lifecycle_status,
        )
        limitations.append("target_frame_revoked_suspended_discontinued_or_withdrawn")
    reporter_match = _LEADING_ATTRIBUTION.search(
        record.text[: predicate.start()]
    ) or _REPORTING.search(record.text[: predicate.start()])
    if reporter_match:
        reporter = normalize_text(reporter_match.group("reporter"))
        participants = {
            normalize_text(row.normalized_value)
            for row in roles
            if row.role in {"actor", "counterparty", "recipient", "supplier"}
        }
        speech_mode = (
            "issuer_attributed"
            if reporter in participants
            else "third_party_attributed"
        )
        assertion_owner = _binding(
            record,
            "assertion_owner",
            reporter_match,
            reporter,
        )
        bindings.append(assertion_owner)
        add_edge(reporter_match, "owns_assertion", reporter)
        if reporter not in participants:
            limitations.append("third_party_attributed_target_frame")
    else:
        owner = next(
            (
                row
                for row in roles
                if row.role == "actor"
            ),
            None,
        )
        if owner is None:
            owner = next(
                (
                    row
                    for row in roles
                    if row.role in {"recipient", "counterparty"}
                    and normalize_text(row.normalized_value) == "dell"
                ),
                None,
            )
        if owner is not None:
            assertion_owner = RoleBinding(
                role="assertion_owner",
                raw_text=owner.raw_text,
                normalized_value=owner.normalized_value,
                span_start=owner.span_start,
                span_end=owner.span_end,
                source_kind="frame_assertion_owner",
            )
    if actuality == "alleged" and speech_mode == "direct":
        speech_mode = "unconfirmed"
    return (
        polarity,
        actuality,
        lifecycle_status,
        speech_mode,
        assertion_owner,
        tuple(sorted(bindings, key=lambda row: (row.span_start, row.role))),
        tuple(
            sorted(
                edges,
                key=lambda row: (
                    row.modifier_span_start,
                    row.modifier_span_end,
                    row.relation,
                ),
            )
        ),
        tuple(sorted(set(limitations))),
    )


def _anchors(roles: Sequence[RoleBinding]) -> tuple[str, ...]:
    anchors: set[str] = set()
    for row in roles:
        if row.role == "actor":
            anchors.add(f"actor:{normalize_text(row.normalized_value).replace(' ', '_')}")
        elif row.role in {"recipient", "counterparty"}:
            anchors.add(
                f"{row.role}:{normalize_text(row.normalized_value).replace(' ', '_')}"
            )
        elif row.role == "supplier":
            anchors.add(
                "supplier_entity:"
                f"{normalize_text(row.normalized_value).replace(' ', '_')}"
            )
        elif row.role == "predicate":
            anchors.add(
                f"predicate:{normalize_text(row.normalized_value).replace(' ', '_')}"
            )
        elif row.role == "product":
            prefix = (
                "product_code"
                if row.normalized_value
                not in {
                    "dell_poweredge_server",
                    "ai_server_system",
                    "bounded_hardware_configuration",
                }
                else "product"
            )
            anchors.add(f"{prefix}:{row.normalized_value}")
        elif row.role == "price":
            anchors.add(f"price.hardware.currency_usd:{row.normalized_value}")
        elif row.role == "quantity.physical_server":
            anchors.add(f"quantity.physical_server:{row.normalized_value}")
        elif row.role.startswith("period."):
            anchors.add(f"{row.role}:{row.normalized_value}")
        elif row.role == "yield.percent":
            anchors.add(f"yield.percent:{row.normalized_value}")
        elif row.role == "process":
            anchors.add(f"process:{row.normalized_value}")
    return tuple(sorted(anchors))


_ARGUMENT_SEPARATOR = re.compile(r",|;|\band\b|\bplus\b", re.IGNORECASE)
_HARDWARE_OBJECT = re.compile(
    r"\b(?:poweredge|xe\s*\d|servers?|systems?|nodes?|hardware|"
    r"equipment|bundle)\b",
    re.IGNORECASE,
)
_NON_HARDWARE_OBJECTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("support", re.compile(r"\bsupport(?:\s+package)?\b", re.IGNORECASE)),
    ("service", re.compile(r"\bservices?\b", re.IGNORECASE)),
    ("freight", re.compile(r"\bfreight|shipping\s+fee\b", re.IGNORECASE)),
    ("financing", re.compile(r"\bfinancing|interest\b", re.IGNORECASE)),
)


def _argument_group_bounds(record: FrameRecord, price: RoleBinding) -> tuple[int, int]:
    local_start = price.span_start - record.span_start
    local_end = price.span_end - record.span_start
    separators = list(_ARGUMENT_SEPARATOR.finditer(record.text))
    start = max(
        (match.end() for match in separators if match.end() <= local_start),
        default=0,
    )
    end = min(
        (match.start() for match in separators if match.start() >= local_end),
        default=len(record.text),
    )
    while start < end and record.text[start].isspace():
        start += 1
    while end > start and record.text[end - 1].isspace():
        end -= 1
    return start, end


def _typed_object_mentions(
    text: str,
) -> list[tuple[str, re.Match[str]]]:
    output = [("hardware", match) for match in _HARDWARE_OBJECT.finditer(text)]
    for object_class, pattern in _NON_HARDWARE_OBJECTS:
        output.extend((object_class, match) for match in pattern.finditer(text))
    return sorted(output, key=lambda row: (row[1].start(), row[1].end(), row[0]))


def _attached_object_mention(
    text: str,
    *,
    price_start: int,
    price_end: int,
) -> tuple[str, re.Match[str] | None, str, str | None]:
    mentions = _typed_object_mentions(text)
    preceding: list[tuple[str, re.Match[str]]] = []
    following: list[tuple[str, re.Match[str]]] = []
    for object_class, match in mentions:
        if match.end() <= price_start and re.fullmatch(
            r"(?:\s+package)?\s+(?:for|at)\s*",
            text[match.end() : price_start],
        ):
            preceding.append((object_class, match))
        elif match.start() >= price_end and re.fullmatch(
            r"\s+(?:for|of)\s+(?:(?:one|two|three|four|five|six|"
            r"seven|eight|nine|ten|\d+)\s+)?(?:dell\s+)?",
            text[price_end : match.start()],
        ):
            following.append((object_class, match))

    # A completed ``object for PRICE`` phrase governs before a second
    # ``for object`` phrase.  This is what keeps support USD 150 from being
    # relabelled as a PowerEdge price in a single unsplit argument surface.
    candidates = preceding or following
    if candidates:
        classes = {row[0] for row in candidates}
        if len(classes) == 1:
            selected = (
                max(candidates, key=lambda row: row[1].end())
                if preceding
                else min(candidates, key=lambda row: row[1].start())
            )
            direction = "preceding" if preceding else "following"
            return (
                selected[0],
                selected[1],
                f"price_bound_to_{direction}_typed_object",
                None,
            )
        return (
            "unknown",
            None,
            "conflicting_typed_objects_at_same_attachment_rank",
            "ambiguous_price_object_semantic_class",
        )

    classes = {row[0] for row in mentions}
    if len(classes) == 1:
        object_class = next(iter(classes))
        selected = min(
            (row for row in mentions if row[0] == object_class),
            key=lambda row: min(
                abs(row[1].end() - price_start),
                abs(row[1].start() - price_end),
            ),
        )
        return (
            object_class,
            selected[1],
            "single_typed_object_in_argument_group",
            None,
        )
    if len(classes) > 1:
        return (
            "unknown",
            None,
            "mixed_hardware_and_non_hardware_surface",
            "ambiguous_price_object_semantic_class",
        )
    return (
        "unknown",
        None,
        "no_typed_object_in_argument_group",
        "price_object_attachment_unproved",
    )


def _argument_groups(
    record: FrameRecord,
    *,
    predicate: re.Match[str],
    prices: Sequence[RoleBinding],
    products: Sequence[RoleBinding],
) -> tuple[ArgumentGroupBinding, ...]:
    output: list[ArgumentGroupBinding] = []
    for index, price in enumerate(prices):
        local_start, local_end = _argument_group_bounds(record, price)
        text = record.text[local_start:local_end]
        group_price_start = price.span_start - record.span_start - local_start
        group_price_end = price.span_end - record.span_start - local_start
        (
            object_class,
            object_match,
            attachment,
            ambiguity,
        ) = _attached_object_mention(
            text,
            price_start=group_price_start,
            price_end=group_price_end,
        )
        object_span = (
            (
                record.span_start + local_start + object_match.start(),
                record.span_start + local_start + object_match.end(),
            )
            if object_match is not None
            else None
        )
        product_candidates = (
            [
                row
                for row in products
                if row.span_start >= record.span_start + local_start
                and row.span_end <= record.span_start + local_end
            ]
            if object_class == "hardware"
            else []
        )
        product = (
            product_candidates[0] if len(product_candidates) == 1 else None
        )
        if len(product_candidates) > 1:
            ambiguity = "ambiguous_multiple_products_in_argument_group"
        body = {
            "span_start": record.span_start + local_start,
            "span_end": record.span_start + local_end,
            "raw_text": text,
            "governing_predicate_span": (
                record.span_start + predicate.start(),
                record.span_start + predicate.end(),
            ),
            "object_class": object_class,
            "object_span": object_span,
            "product_span": (
                (product.span_start, product.span_end) if product is not None else None
            ),
            "normalized_product": (
                product.normalized_value if product is not None else None
            ),
            "price_span": (price.span_start, price.span_end),
            "normalized_price": price.normalized_value,
            "attachment": attachment,
            "ambiguity": ambiguity,
        }
        digest = canonical_digest(body)
        output.append(
            ArgumentGroupBinding(
                group_id=f"ARG::R10::{index:02d}::{digest[:20].upper()}",
                span_start=body["span_start"],
                span_end=body["span_end"],
                raw_text=text,
                governing_predicate_span=body["governing_predicate_span"],
                object_class=object_class,
                object_span=object_span,
                product_span=body["product_span"],
                normalized_product=body["normalized_product"],
                price_span=body["price_span"],
                normalized_price=price.normalized_value,
                attachment=attachment,
                ambiguity=ambiguity,
                group_digest=digest,
            )
        )
    return tuple(output)


def _argument_relation_rows(
    argument_groups: Sequence[ArgumentGroupBinding],
) -> tuple[dict[str, Any], ...]:
    """Expose normalized ASP relations plus representation-only spans."""

    rows: list[dict[str, Any]] = []
    for group in argument_groups:
        if (
            group.object_class != "hardware"
            or group.ambiguity is not None
            or group.product_span is None
            or group.normalized_product is None
            or group.normalized_product == "bounded_hardware_configuration"
        ):
            continue
        rows.append(
            {
                "relation_type": "hardware_product_price",
                "object_class": group.object_class,
                "product": group.normalized_product,
                "price": group.normalized_price,
                "attachment": group.attachment,
                "span_start": group.span_start,
                "span_end": group.span_end,
                "product_span": list(group.product_span),
                "price_span": list(group.price_span),
            }
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                row["relation_type"],
                row["product"],
                row["price"],
                row["span_start"],
                row["span_end"],
            ),
        )
    )


def _argument_relation_rows_for_frame(
    frame: PredicateFrame,
) -> tuple[dict[str, Any], ...]:
    return _argument_relation_rows(frame.argument_groups)


def _semantic_argument_relations(
    argument_groups: Sequence[ArgumentGroupBinding],
) -> list[dict[str, str]]:
    return [
        {
            "relation_type": str(row["relation_type"]),
            "object_class": str(row["object_class"]),
            "product": str(row["product"]),
            "price": str(row["price"]),
            "attachment": str(row["attachment"]),
        }
        for row in _argument_relation_rows(argument_groups)
    ]


def _semantic_argument_relations_for_frame(
    frame: PredicateFrame,
) -> list[dict[str, str]]:
    return _semantic_argument_relations(frame.argument_groups)


def _finalize(
    *,
    record: FrameRecord,
    target_id: str,
    predicate: re.Match[str],
    roles: Iterable[RoleBinding],
    groups: Iterable[str],
    missing: Iterable[str],
    ambiguities: Iterable[str] = (),
    limitations: Iterable[str] = (),
    argument_groups: Iterable[ArgumentGroupBinding] = (),
) -> PredicateFrame:
    role_rows = tuple(
        sorted(
            roles,
            key=lambda row: (row.span_start, row.span_end, row.role, row.normalized_value),
        )
    )
    assertion_frame_body = {
        "target_id": target_id,
        "sentence_index": record.sentence_index,
        "frame_index": record.frame_index,
        "span_start": record.span_start,
        "span_end": record.span_end,
        "predicate_span_start": record.span_start + predicate.start(),
        "predicate_span_end": record.span_start + predicate.end(),
        "frame_text": record.text,
        "roles": [
            {
                "role": row.role,
                "normalized_value": row.normalized_value,
                "span_start": row.span_start,
                "span_end": row.span_end,
            }
            for row in role_rows
        ],
    }
    assertion_frame_id = (
        "ASSERTION::R10::"
        f"{canonical_digest(assertion_frame_body)[:24].upper()}"
    )
    (
        polarity,
        actuality,
        lifecycle_status,
        speech_mode,
        assertion_owner,
        scope,
        scope_edges,
        scope_limitations,
    ) = _scope_state(
        record,
        target_id=target_id,
        predicate=predicate,
        roles=role_rows,
        assertion_frame_id=assertion_frame_id,
    )
    argument_group_rows = tuple(argument_groups)
    missing_rows = tuple(sorted(set(missing)))
    ambiguity_rows = tuple(sorted(set(ambiguities)))
    limitation_rows = tuple(sorted(set(limitations) | set(scope_limitations)))
    role_anchors = _anchors(role_rows)
    accepted = (
        not missing_rows
        and not ambiguity_rows
        and not limitation_rows
        and polarity == "affirmative"
        and actuality == "actual"
        and lifecycle_status == "active"
    )
    body = {
        "assertion_frame_id": assertion_frame_id,
        "target_id": target_id,
        "sentence_index": record.sentence_index,
        "frame_index": record.frame_index,
        "span_start": record.span_start,
        "span_end": record.span_end,
        "predicate_span_start": record.span_start + predicate.start(),
        "predicate_span_end": record.span_start + predicate.end(),
        "frame_text": record.text,
        "role_bindings": [row.as_dict() for row in role_rows],
        "scope_bindings": [row.as_dict() for row in scope],
        "scope_edges": [row.as_dict() for row in scope_edges],
        "argument_groups": [row.as_dict() for row in argument_group_rows],
        "polarity": polarity,
        "actuality": actuality,
        "lifecycle_status": lifecycle_status,
        "assertion_owner": (
            assertion_owner.as_dict() if assertion_owner is not None else None
        ),
        # Compatibility aliases are intentionally explicit in the R10 public IR.
        "modality": actuality,
        "status": lifecycle_status,
        "speech_mode": speech_mode,
        "matched_group_ids": sorted(set(groups)),
        "missing_required_roles": list(missing_rows),
        "ambiguities": list(ambiguity_rows),
        "limitations": list(limitation_rows),
        "role_anchors": list(role_anchors),
        "accepted": accepted,
    }
    semantic_signature_body = {
        "target_id": target_id,
        "roles": sorted(
            [
            {
                "role": row.role,
                "normalized_value": row.normalized_value,
            }
            for row in role_rows
            ],
            key=lambda row: (row["role"], row["normalized_value"]),
        ),
        "scope": {
            "polarity": polarity,
            "actuality": actuality,
            "lifecycle_status": lifecycle_status,
            "speech_mode": speech_mode,
            "assertion_owner": (
                assertion_owner.normalized_value
                if assertion_owner is not None
                else None
            ),
        },
        "argument_relations": _semantic_argument_relations(
            argument_group_rows
        ),
    }
    semantic_signature_digest = canonical_digest(semantic_signature_body)
    body["semantic_signature_digest"] = semantic_signature_digest
    digest = canonical_digest(body)
    return PredicateFrame(
        frame_id=f"FRAME::R10::{digest[:24].upper()}",
        frame_digest=digest,
        assertion_frame_id=assertion_frame_id,
        target_id=target_id,
        sentence_index=record.sentence_index,
        frame_index=record.frame_index,
        span_start=record.span_start,
        span_end=record.span_end,
        predicate_span_start=body["predicate_span_start"],
        predicate_span_end=body["predicate_span_end"],
        frame_text=record.text,
        role_bindings=role_rows,
        scope_bindings=scope,
        scope_edges=scope_edges,
        argument_groups=argument_group_rows,
        polarity=polarity,
        actuality=actuality,
        lifecycle_status=lifecycle_status,
        assertion_owner=assertion_owner,
        modality=actuality,
        status=lifecycle_status,
        speech_mode=speech_mode,
        matched_group_ids=tuple(sorted(set(groups))),
        missing_required_roles=missing_rows,
        ambiguities=ambiguity_rows,
        limitations=limitation_rows,
        role_anchors=role_anchors,
        representation_frame_digest=digest,
        semantic_signature_digest=semantic_signature_digest,
        accepted=accepted,
    )


def _asp_frame(record: FrameRecord) -> PredicateFrame | None:
    predicate = _ASP_PREDICATE.search(record.text)
    prices = _price_bindings(record)
    if not predicate and not prices:
        return None
    predicate = predicate or re.search(r"\b(?:usd|us\$|dollars?)\b|\$", record.text)
    if predicate is None:
        return None
    roles: list[RoleBinding] = [_binding(record, "predicate", predicate, predicate.group(0))]
    groups: list[str] = []
    missing: list[str] = []
    ambiguities: list[str] = []
    actor = _first_company_before(record, predicate)
    if actor and actor.normalized_value == "Dell":
        roles.append(actor)
        groups.append("dell_subject")
    else:
        missing.append("Dell_seller_or_quoter")
    if _ASP_PREDICATE.fullmatch(predicate.group(0)):
        groups.append("affirmative_price_quote")
    else:
        missing.append("affirmative_price_predicate")
    products = _product_bindings(record)
    argument_groups = _argument_groups(
        record,
        predicate=predicate,
        prices=prices,
        products=products,
    )
    price_by_span = {
        (row.span_start, row.span_end): row
        for row in prices
    }
    product_by_span = {
        (row.span_start, row.span_end): row
        for row in products
    }
    qualified_relations = [
        (
            row,
            product_by_span[row.product_span],
            price_by_span[row.price_span],
        )
        for row in argument_groups
        if row.object_class == "hardware"
        and row.ambiguity is None
        and row.product_span is not None
        and row.product_span in product_by_span
        and product_by_span[row.product_span].normalized_value
        != "bounded_hardware_configuration"
        and row.price_span in price_by_span
    ]
    selected_relation = (
        qualified_relations[0] if len(qualified_relations) == 1 else None
    )
    if len(qualified_relations) > 1:
        ambiguities.append(
            "ambiguous_multiple_hardware_product_price_argument_relations"
        )
    if prices and selected_relation is None and any(
        row.ambiguity is not None for row in argument_groups
    ):
        ambiguities.append("ambiguous_price_to_hardware_argument")
    if selected_relation is not None:
        _, selected_product, selected_price = selected_relation
        roles.extend((selected_product, selected_price))
        groups.extend(
            ("bounded_object", "bundle_boundary", "dell_ai_server")
        )
        groups.append("price_surface")
    else:
        missing.append("bounded_hardware_or_server_object")
        missing.append("currency_price")
    quantities = _quantity_bindings(record)
    if quantities:
        roles.append(quantities[0])
        groups.append("valid_denominator")
    roles.extend(_period_bindings(record))
    return _finalize(
        record=record,
        target_id=ASP_TARGET,
        predicate=predicate,
        roles=roles,
        groups=groups,
        missing=missing,
        ambiguities=ambiguities,
        argument_groups=argument_groups,
    )


def _supplier_frame(record: FrameRecord) -> PredicateFrame | None:
    supplier = _NAMED_SUPPLIER.search(record.text)
    predicate = _SUPPLIER_PREDICATE.search(record.text)
    if not supplier or not predicate:
        return None
    roles: list[RoleBinding] = [
        _binding(record, "predicate", predicate, predicate.group(1)),
        _binding(record, "supplier", supplier, supplier.group(1)),
    ]
    groups = ["named_supplier"]
    missing: list[str] = []
    actor = _first_company_before(record, predicate)
    if re.match(
        r"^\s*dell\b[^.;]{0,48}(?:,\s*|\s+)and\s+"
        r"(?:nvidia|micron|tsmc|broadcom)\b",
        record.text[: predicate.start()],
    ):
        dell_subject = re.search(r"\bdell\b", record.text[: predicate.start()])
        if dell_subject:
            actor = _binding(record, "actor", dell_subject, "Dell")
    dell_component_delivery = bool(
        re.search(
            r"\bdell\b[^.;]{0,64}\bwith\s+"
            r"(?:nvidia|micron|tsmc|taiwan\s+semiconductor|sk\s+hynix|broadcom)\b"
            r"[^.;]{0,64}\b(?:ship(?:s|ped|ping)?|deliver(?:s|ed|ing|y)?)\b",
            record.text,
        )
    )
    if dell_component_delivery:
        dell_subject = re.search(r"\bdell\b", record.text[: predicate.start()])
        if dell_subject:
            actor = _binding(record, "actor", dell_subject, "Dell")
    if actor:
        roles.append(actor)
    relationship = re.search(
        r"partner|collaborat|alliance|team|supplier", predicate.group(1)
    ) is not None
    tail = record.text[predicate.end() :]
    supplier_to_dell = bool(
        actor
        and actor.normalized_value != "Dell"
        and (
            re.search(r"\b(?:to|for|through)\s+dell\b", tail)
            or re.search(r"\bdell\s+(?:ai\s+)?(?:servers?|systems?|infrastructure)\b", tail)
        )
    )
    dell_relationship = bool(
        relationship
        and re.search(r"\bdell\b", record.text)
        and supplier
    )
    if supplier_to_dell or dell_relationship or dell_component_delivery:
        if dell_component_delivery:
            roles.append(
                _binding(
                    record,
                    "counterparty",
                    supplier,
                    supplier.group(1),
                )
            )
            customer = re.search(r"\bcustomers?\b", record.text)
            if customer:
                roles.append(
                    _binding(
                        record,
                        "recipient",
                        customer,
                        "customer_market",
                    )
                )
        elif supplier_to_dell:
            dell = _dell_binding(record, role="recipient")
            if dell:
                roles.append(dell)
        elif actor and actor.normalized_value == "Dell":
            roles.append(
                _binding(
                    record,
                    "counterparty",
                    supplier,
                    supplier.group(1),
                )
            )
        else:
            dell = _dell_binding(record, role="counterparty")
            if dell:
                roles.append(dell)
        groups.extend(("dell_subject", "directional_relationship_delivery"))
    else:
        missing.append("supplier_Dell_relationship_or_delivery_direction")
    products = _product_bindings(record)
    if products:
        roles.append(products[0])
        groups.append("dell_ai_server")
    return _finalize(
        record=record,
        target_id=SUPPLIER_TARGET,
        predicate=predicate,
        roles=roles,
        groups=groups,
        missing=missing,
    )


def _capacity_frame(record: FrameRecord) -> PredicateFrame | None:
    if not _CAPACITY_SURFACE.search(record.text):
        return None
    predicate = _CAPACITY_PREDICATE.search(record.text)
    if not predicate:
        return None
    roles: list[RoleBinding] = [
        _binding(record, "predicate", predicate, predicate.group(1))
    ]
    groups = ["relevant_supply", "capacity_or_availability_event"]
    missing: list[str] = []
    limitations: list[str] = []
    if re.search(
        r"\b(?:zero|0)\b[^.;]{0,40}\b(?:capacity|allocation)\b|"
        r"\b(?:capacity|allocation)\b[^.;]{0,40}\b(?:zero|0)\b",
        record.text,
    ):
        limitations.append("zero_capacity_or_allocation_is_not_positive_release")
    if re.search(r"\ballocated\s+away\s+from\s+dell\b", record.text):
        limitations.append("capacity_allocated_away_from_Dell")
    if actor := _first_company_before(record, predicate):
        roles.append(actor)
    recipient_match = re.search(r"\b(?:to|for)\s+(dell|hp|hpe)\b", record.text)
    if not recipient_match and re.search(
        r"\bdell\b[^.;]{0,48}\b(?:secured?|received?)\b",
        record.text,
    ):
        recipient_match = re.search(r"\bdell\b", record.text)
    if recipient_match and "dell" in recipient_match.group(0):
        roles.append(_binding(record, "recipient", recipient_match, "Dell"))
        groups.append("upstream_Dell_allocation")
    else:
        missing.append("Dell_recipient_or_beneficiary")
    periods = _period_bindings(record)
    if periods:
        roles.extend(periods)
        groups.append("timing_surface")
    else:
        missing.append("allocation_period")
    object_match = _CAPACITY_SURFACE.search(record.text)
    if object_match:
        roles.append(
            _binding(
                record,
                "object",
                object_match,
                "production_capacity_or_supply_allocation",
            )
        )
    return _finalize(
        record=record,
        target_id=CAPACITY_TARGET,
        predicate=predicate,
        roles=roles,
        groups=groups,
        missing=missing,
        limitations=limitations,
    )


def _yield_frame(record: FrameRecord) -> PredicateFrame | None:
    if not re.search(r"\b(?:yield|yielded|yields|utilization)\b", record.text):
        return None
    predicate = _YIELD_PREDICATE.search(record.text)
    measure = r7._PERCENT.search(record.text)  # noqa: SLF001
    if not predicate or not measure:
        return None
    roles: list[RoleBinding] = [
        _binding(record, "predicate", predicate, predicate.group(1)),
        _binding(
            record,
            "yield.percent",
            measure,
            r7._normalized_number(measure.group(1)),  # noqa: SLF001
        ),
    ]
    groups = ["observed_yield_or_utilization", "observed_measure"]
    missing: list[str] = []
    limitations: list[str] = []
    if _WRONG_PROCESS.search(record.text):
        limitations.append("wrong_simulated_or_irrelevant_production_process")
    process_match = re.search(
        r"\b(hbm\s+production|high[- ]bandwidth\s+memory\s+production|"
        r"gpu\s+(?:production|manufacturing)|semiconductor\s+(?:production|manufacturing)|"
        r"dram\s+(?:production|manufacturing)|wafer\s+(?:production|manufacturing)|"
        r"solar(?:-panel)?\s+production|orange\s+juice\s+production)\b",
        record.text,
    )
    if process_match and not re.search(r"solar|orange", process_match.group(1)):
        process_value = (
            "hbm_production"
            if re.search(r"hbm|high-bandwidth", process_match.group(1))
            else "relevant_semiconductor_production"
        )
        roles.append(_binding(record, "process", process_match, process_value))
        groups.append("relevant_supply")
    else:
        missing.append("relevant_production_process")
        if process_match:
            limitations.append("wrong_or_irrelevant_production_process")
    periods = _period_bindings(record)
    if periods:
        roles.extend(periods)
        groups.append("timing_surface")
    else:
        missing.append("observation_period")
    return _finalize(
        record=record,
        target_id=YIELD_TARGET,
        predicate=predicate,
        roles=roles,
        groups=groups,
        missing=missing,
        limitations=limitations,
    )


def _hbm_frame(record: FrameRecord) -> PredicateFrame | None:
    hbm = re.search(r"\b(?:hbm|high[- ]bandwidth\s+memory)\b", record.text)
    predicate = _HBM_PREDICATE.search(record.text)
    if not hbm or not predicate:
        return None
    roles: list[RoleBinding] = [
        _binding(record, "predicate", predicate, predicate.group(1)),
        _binding(record, "object", hbm, "HBM_component_or_supply"),
    ]
    groups = ["hbm_subject", "supply_state"]
    missing: list[str] = []
    dell = _dell_binding(record)
    products = _product_bindings(record)
    if dell:
        roles.append(dell)
        groups.append("directional_Dell_bridge")
    else:
        missing.append("Dell_or_PowerEdge_bridge")
    if products:
        roles.append(products[0])
    periods = _period_bindings(record)
    if periods:
        roles.extend(periods)
        groups.append("timing_surface")
    else:
        missing.append("HBM_bridge_period")
    return _finalize(
        record=record,
        target_id=HBM_TARGET,
        predicate=predicate,
        roles=roles,
        groups=groups,
        missing=missing,
    )


def _units_frame(record: FrameRecord) -> PredicateFrame | None:
    predicate = _UNITS_PREDICATE.search(record.text)
    quantities = _quantity_bindings(record)
    if not predicate and not quantities:
        return None
    if predicate is None:
        predicate = re.search(r"\b(?:servers?|systems?|nodes?)\b", record.text)
    if predicate is None:
        return None
    roles: list[RoleBinding] = [
        _binding(record, "predicate", predicate, predicate.group(0))
    ]
    groups: list[str] = []
    missing: list[str] = []
    limitations: list[str] = []
    actor = _first_company_before(record, predicate)
    if re.search(
        r"\bdell\s+(?:said|reported|confirmed|announced|disclosed)\s+"
        r"(?:that\s+)?(?:the\s+)?customer\s+$",
        record.text[: predicate.start()],
    ):
        actor = None
        limitations.append("asserted_shipper_is_not_Dell")
    if actor and actor.normalized_value == "Dell":
        roles.append(actor)
        groups.extend(("dell_subject", "Dell_seller_or_shipper_role"))
    else:
        missing.append("Dell_actual_shipper")
    if quantities:
        roles.append(quantities[0])
        groups.append("physical_server_quantity")
    else:
        missing.append("physical_server_quantity")
    products = _product_bindings(record)
    physical_ai_server = bool(
        products
        and re.search(r"\b(?:server|system|node|poweredge|xe\s*\d|ai|gpu)\b", record.text)
    )
    if physical_ai_server:
        roles.append(products[0])
        groups.append("dell_ai_server")
    else:
        missing.append("Dell_AI_server_product")
    periods = _period_bindings(record)
    if periods:
        roles.extend(periods)
        groups.append("timing_surface")
    else:
        missing.append("shipment_period")
    return _finalize(
        record=record,
        target_id=UNITS_TARGET,
        predicate=predicate,
        roles=roles,
        groups=groups,
        missing=missing,
        limitations=limitations,
    )


_EXTRACTOR = {
    ASP_TARGET: _asp_frame,
    SUPPLIER_TARGET: _supplier_frame,
    CAPACITY_TARGET: _capacity_frame,
    YIELD_TARGET: _yield_frame,
    HBM_TARGET: _hbm_frame,
    UNITS_TARGET: _units_frame,
}


def extract_predicate_frames(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> list[PredicateFrame]:
    del metadata
    if target_id not in TARGET_IDS:
        raise ValueError(f"unsupported_R10_target:{target_id}")
    extractor = _EXTRACTOR[target_id]
    records = frame_records(text)
    output = [
        frame
        for record in records
        if (frame := extractor(record)) is not None
    ]
    output = _attach_coreferential_state_modifiers(
        frames=output,
        records=records,
    )
    return sorted(
        output,
        key=lambda row: (
            row.sentence_index,
            row.frame_index,
            row.span_start,
            row.frame_id,
        ),
    )


def _best_partial(frames: Sequence[PredicateFrame]) -> PredicateFrame | None:
    if not frames:
        return None
    return min(
        frames,
        key=lambda row: (
            len(row.missing_required_roles)
            + len(row.ambiguities)
            + len(row.limitations),
            len(row.missing_required_roles),
            row.sentence_index,
            row.frame_index,
            row.frame_id,
        ),
    )


def _semantic_signature_body_for_frame(frame: PredicateFrame) -> dict[str, Any]:
    return {
        "target_id": frame.target_id,
        "roles": sorted(
            [
                {
                    "role": row.role,
                    "normalized_value": row.normalized_value,
                }
                for row in frame.role_bindings
            ],
            key=lambda row: (row["role"], row["normalized_value"]),
        ),
        "scope": {
            "polarity": frame.polarity,
            "actuality": frame.actuality,
            "lifecycle_status": frame.lifecycle_status,
            "speech_mode": frame.speech_mode,
            "assertion_owner": (
                frame.assertion_owner.normalized_value
                if frame.assertion_owner is not None
                else None
            ),
        },
        "argument_relations": _semantic_argument_relations_for_frame(frame),
    }


def _redigest_frame(frame: PredicateFrame) -> PredicateFrame:
    semantic_digest = canonical_digest(_semantic_signature_body_for_frame(frame))
    provisional = replace(frame, semantic_signature_digest=semantic_digest)
    body = provisional.as_dict()
    for key in (
        "frame_id",
        "frame_digest",
        "representation_frame_digest",
    ):
        body.pop(key)
    digest = canonical_digest(body)
    return replace(
        provisional,
        frame_id=f"FRAME::R10::{digest[:24].upper()}",
        frame_digest=digest,
        representation_frame_digest=digest,
    )


def _attach_coreferential_state_modifiers(
    *,
    frames: Sequence[PredicateFrame],
    records: Sequence[FrameRecord],
) -> list[PredicateFrame]:
    output = list(frames)
    for modifier in records:
        if not _COREFERENTIAL_RETRACTION.search(modifier.text):
            continue
        lifecycle_match = _REVOKED.search(modifier.text)
        if lifecycle_match is None:
            continue
        candidates = [
            (index, frame)
            for index, frame in enumerate(output)
            if frame.sentence_index == modifier.sentence_index
            and frame.span_end <= modifier.span_start
        ]
        if not candidates:
            continue
        index, target = max(candidates, key=lambda row: row[1].span_end)
        evidence_start = modifier.span_start + lifecycle_match.start()
        evidence_end = modifier.span_start + lifecycle_match.end()
        lifecycle_status = _lifecycle_value(lifecycle_match.group(0))
        edge = _scope_edge(
            source_modifier_frame_id=_modifier_frame_id(
                sentence_index=modifier.sentence_index,
                span_start=modifier.span_start,
                span_end=modifier.span_end,
                raw_text=modifier.text,
            ),
            target_assertion_frame_id=target.assertion_frame_id,
            relation="changes_lifecycle_status",
            evidence_span_start=evidence_start,
            evidence_span_end=evidence_end,
            target_predicate_span_start=target.predicate_span_start,
            target_predicate_span_end=target.predicate_span_end,
            normalized_value=lifecycle_status,
        )
        status_binding = RoleBinding(
            role="scope.lifecycle_status",
            raw_text=lifecycle_match.group(0),
            normalized_value=lifecycle_status,
            span_start=evidence_start,
            span_end=evidence_end,
            source_kind="coreferential_modifier_frame",
        )
        updated = replace(
            target,
            scope_bindings=tuple(
                sorted(
                    (*target.scope_bindings, status_binding),
                    key=lambda row: (row.span_start, row.span_end, row.role),
                )
            ),
            scope_edges=tuple(
                sorted(
                    (*target.scope_edges, edge),
                    key=lambda row: (
                        row.evidence_span_start,
                        row.evidence_span_end,
                        row.relation,
                    ),
                )
            ),
            lifecycle_status=lifecycle_status,
            status=lifecycle_status,
            limitations=tuple(
                sorted(
                    {
                        *target.limitations,
                        "target_frame_revoked_suspended_discontinued_or_withdrawn",
                    }
                )
            ),
            accepted=False,
        )
        output[index] = _redigest_frame(updated)
    return output


def classify_package(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> dict[str, Any]:
    base = r4.classify_dell_report_internal_chain_r4_package(
        target_id=target_id,
        text=text,
        metadata=metadata,
    )
    frames = extract_predicate_frames(
        target_id=target_id,
        text=text,
        metadata=metadata,
    )
    boundary_rows = frame_boundary_decisions(text)
    accepted = next((row for row in frames if row.accepted), None)
    selected = accepted or _best_partial(frames)
    contract = _TARGET_CONTRACT[target_id]
    assessment = dict(base)
    assessment["semantic_guard_revision"] = "R10_RELATIONAL_PREDICATE_FRAME"
    assessment["proposition_completion_mode"] = (
        "one_complete_equals_one_span_bound_predicate_frame_no_sentence_union"
    )
    assessment["required_group_ids"] = list(contract["required"])
    assessment["predicate_frames"] = [row.as_dict() for row in frames]
    assessment["typed_propositions"] = [row.as_dict() for row in frames]
    assessment["frame_boundary_decisions"] = [
        row.as_dict() for row in boundary_rows
    ]
    assessment["selected_frame_id"] = selected.frame_id if selected else None
    assessment["selected_frame_digest"] = (
        selected.frame_digest if selected else None
    )
    assessment["selected_frame_representation_digest"] = (
        selected.representation_frame_digest if selected else None
    )
    assessment["selected_frame_semantic_signature_digest"] = (
        selected.semantic_signature_digest if selected else None
    )
    assessment["accepted_frame_id"] = accepted.frame_id if accepted else None
    assessment["accepted_frame_digest"] = accepted.frame_digest if accepted else None
    assessment["accepted_frame_representation_digest"] = (
        accepted.representation_frame_digest if accepted else None
    )
    assessment["accepted_frame_semantic_signature_digest"] = (
        accepted.semantic_signature_digest if accepted else None
    )
    assessment["accepted_frame_sentence_index"] = (
        accepted.sentence_index if accepted else None
    )
    assessment["accepted_frame_index"] = accepted.frame_index if accepted else None
    assessment["accepted_frame_role_anchors"] = (
        list(accepted.role_anchors) if accepted else []
    )
    # Compatibility fields keep the successor compiler explicit while allowing
    # existing materialization code to consume the stricter authority.
    assessment["accepted_proposition_id"] = accepted.frame_id if accepted else None
    assessment["accepted_proposition_digest"] = (
        accepted.frame_digest if accepted else None
    )
    assessment["accepted_proposition_semantic_signature_digest"] = (
        accepted.semantic_signature_digest if accepted else None
    )
    assessment["accepted_proposition_sentence_index"] = (
        accepted.sentence_index if accepted else None
    )
    assessment["accepted_proposition_clause_index"] = (
        accepted.frame_index if accepted else None
    )
    assessment["accepted_proposition_role_anchors"] = (
        list(accepted.role_anchors) if accepted else []
    )
    if accepted and assessment.get("in_period") is True:
        assessment["classification"] = "complete_bounded_target_package"
        assessment["package_role"] = contract["complete_role"]
        assessment["matched_group_ids"] = list(accepted.matched_group_ids)
        assessment["limitations"] = []
    elif selected:
        assessment["classification"] = "partial_context_only"
        assessment["package_role"] = contract["partial_role"]
        assessment["matched_group_ids"] = list(selected.matched_group_ids)
        limitations = set(selected.limitations)
        limitations.update(
            f"missing_R10_role:{role}" for role in selected.missing_required_roles
        )
        limitations.update(f"R10_ambiguity:{row}" for row in selected.ambiguities)
        if accepted and assessment.get("in_period") is not True:
            limitations.add("accepted_frame_outside_target_period")
        assessment["limitations"] = sorted(limitations)
    else:
        if assessment.get("classification") == "complete_bounded_target_package":
            assessment["classification"] = "partial_context_only"
        assessment["package_role"] = contract["partial_role"]
        assessment["limitations"] = sorted(
            set(assessment.get("limitations") or ())
            | {"no_single_R10_relational_target_frame"}
        )
    return assessment


__all__ = [
    "ArgumentGroupBinding",
    "ASP_TARGET",
    "CAPACITY_TARGET",
    "FrameBoundaryDecision",
    "FrameRecord",
    "HBM_TARGET",
    "PredicateFrame",
    "RoleBinding",
    "ScopeEdge",
    "SUPPLIER_TARGET",
    "TARGET_IDS",
    "UNITS_TARGET",
    "YIELD_TARGET",
    "classify_package",
    "extract_predicate_frames",
    "frame_boundary_decisions",
    "frame_records",
    "normalize_text",
]
