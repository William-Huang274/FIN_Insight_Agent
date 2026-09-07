from __future__ import annotations

from dataclasses import dataclass
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
class PredicateFrame:
    frame_id: str
    frame_digest: str
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
    polarity: str
    modality: str
    status: str
    speech_mode: str
    matched_group_ids: tuple[str, ...]
    missing_required_roles: tuple[str, ...]
    ambiguities: tuple[str, ...]
    limitations: tuple[str, ...]
    role_anchors: tuple[str, ...]
    accepted: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "frame_digest": self.frame_digest,
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
            "polarity": self.polarity,
            "modality": self.modality,
            "status": self.status,
            "speech_mode": self.speech_mode,
            "matched_group_ids": list(self.matched_group_ids),
            "missing_required_roles": list(self.missing_required_roles),
            "ambiguities": list(self.ambiguities),
            "limitations": list(self.limitations),
            "role_anchors": list(self.role_anchors),
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
    r"\s*;\s*|,\s*(?:and|but|while|whereas)\s+|\s+alongside\s+",
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
    r"indicative|preliminary|hypothetical|likely|possibly|potentially)\b"
)
_REVOKED = re.compile(
    r"\b(?:revok(?:e|es|ed|ing)|suspend(?:s|ed|ing)?|"
    r"withdraw(?:s|n|ing)?|withdrew|cancel(?:s|l?ed|ling|ing)?|"
    r"terminat(?:e|es|ed|ing)|dissolv(?:e|es|ed|ing)|"
    r"retract(?:s|ed|ing)?|expire(?:s|d|ing)?|ended?)\b"
)
_COREFERENTIAL_RETRACTION = re.compile(
    r"^(?:the\s+)?(?:partnership|collaboration|alliance|relationship|"
    r"allocation|capacity|commitment|quote|price|offer|yield|figure|"
    r"measure|rate|configuration|supply|shipment|delivery|report)\b"
    r"[^.;]{0,96}\b(?:revok(?:e|es|ed|ing)|suspend(?:s|ed|ing)?|"
    r"withdraw(?:s|n|ing)?|withdrew|cancel(?:s|l?ed|ling|ing)?|"
    r"terminat(?:e|es|ed|ing)|dissolv(?:e|es|ed|ing)|"
    r"retract(?:s|ed|ing)?|expire(?:s|d|ing)?|ended?)\b",
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
    r"was|were|is|are|has|have|will|rose|grew|target|announced|received)\b"
)
_FRAME_RIGHT_SUBJECT = re.compile(
    r"^(?:dell|nvidia|micron|tsmc|broadcom|hp|hpe|gpu|hbm|"
    r"poweredge|production|manufacturing|yield|utilization|capacity|"
    r"allocation|solar|orange|next\s+process|another|a\s+separate|"
    r"the\s+\w+)\b"
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
    token = boundary.group(0).strip().casefold()
    if token.startswith(";") or "alongside" in token:
        return True
    left = sentence[current_start : boundary.start()]
    right = sentence[boundary.end() :]
    return bool(
        _FRAME_PREDICATE_HINT.search(left)
        and _FRAME_RIGHT_SUBJECT.match(right)
        and _FRAME_PREDICATE_HINT.search(right)
    )


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
            raise ValueError("R8_normalized_sentence_provenance_lost")
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
        merged_pieces: list[tuple[int, int]] = []
        for start, end in pieces:
            candidate = sentence[start:end].strip(" ,")
            if merged_pieces and _COREFERENTIAL_RETRACTION.search(candidate):
                previous_start, _ = merged_pieces.pop()
                merged_pieces.append((previous_start, end))
            else:
                merged_pieces.append((start, end))
        pieces = merged_pieces
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


def _scope_state(
    record: FrameRecord,
    *,
    target_id: str,
    predicate: re.Match[str],
    roles: Sequence[RoleBinding],
) -> tuple[str, str, str, str, tuple[RoleBinding, ...], tuple[str, ...]]:
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
    limitations: list[str] = []
    polarity = "affirmative"
    modality = "actual"
    status = "active"
    speech_mode = "direct_assertion"
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
        modality = "alleged_or_rumor"
        bindings.append(
            _binding(
                record,
                "scope.modality",
                alleged_match,
                "alleged_or_rumor",
            )
        )
        limitations.append("alleged_rumor_or_unconfirmed_target_frame")
    elif match := _MODAL.search(assertion_scope):
        modality = "capability_or_forward_looking"
        bindings.append(
            _binding(
                record,
                "scope.modality",
                match,
                "capability_or_forward_looking",
            )
        )
        limitations.append("capability_or_forward_looking_target_frame")
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
        status = "revoked_suspended_or_withdrawn"
        bindings.append(
            _binding(
                record,
                "scope.status",
                revoked_match,
                "revoked_suspended_or_withdrawn",
            )
        )
        limitations.append("target_frame_revoked_suspended_or_withdrawn")
    reporter_match = _REPORTING.search(record.text[: predicate.start()])
    if reporter_match:
        speech_mode = "attributed_assertion"
        bindings.append(
            _binding(
                record,
                "scope.reporter",
                reporter_match,
                normalize_text(reporter_match.group("reporter")),
            )
        )
        reporter = normalize_text(reporter_match.group("reporter"))
        participants = {
            normalize_text(row.normalized_value)
            for row in roles
            if row.role in {"actor", "counterparty", "recipient"}
        }
        if reporter not in participants:
            limitations.append("third_party_attributed_target_frame")
    return (
        polarity,
        modality,
        status,
        speech_mode,
        tuple(sorted(bindings, key=lambda row: (row.span_start, row.role))),
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
) -> PredicateFrame:
    role_rows = tuple(
        sorted(
            roles,
            key=lambda row: (row.span_start, row.span_end, row.role, row.normalized_value),
        )
    )
    polarity, modality, status, speech_mode, scope, scope_limitations = _scope_state(
        record,
        target_id=target_id,
        predicate=predicate,
        roles=role_rows,
    )
    missing_rows = tuple(sorted(set(missing)))
    ambiguity_rows = tuple(sorted(set(ambiguities)))
    limitation_rows = tuple(sorted(set(limitations) | set(scope_limitations)))
    role_anchors = _anchors(role_rows)
    accepted = (
        not missing_rows
        and not ambiguity_rows
        and not limitation_rows
        and polarity == "affirmative"
        and modality == "actual"
        and status == "active"
    )
    body = {
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
        "polarity": polarity,
        "modality": modality,
        "status": status,
        "speech_mode": speech_mode,
        "matched_group_ids": sorted(set(groups)),
        "missing_required_roles": list(missing_rows),
        "ambiguities": list(ambiguity_rows),
        "limitations": list(limitation_rows),
        "role_anchors": list(role_anchors),
        "accepted": accepted,
    }
    digest = canonical_digest(body)
    return PredicateFrame(
        frame_id=f"FRAME::R8::{digest[:24].upper()}",
        frame_digest=digest,
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
        polarity=polarity,
        modality=modality,
        status=status,
        speech_mode=speech_mode,
        matched_group_ids=tuple(sorted(set(groups))),
        missing_required_roles=missing_rows,
        ambiguities=ambiguity_rows,
        limitations=limitation_rows,
        role_anchors=role_anchors,
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
    if products:
        roles.append(products[0])
        groups.extend(("bounded_object", "bundle_boundary", "dell_ai_server"))
    else:
        missing.append("bounded_hardware_or_server_object")

    selected_prices = prices
    if len(prices) > 1:
        hardware_prices: list[RoleBinding] = []
        for index, price in enumerate(prices):
            local_start = price.span_end - record.span_start
            local_end = (
                prices[index + 1].span_start - record.span_start
                if index + 1 < len(prices)
                else len(record.text)
            )
            tail = record.text[local_start:local_end]
            if re.search(
                r"\b(?:poweredge|xe\s*\d|server|hardware|equipment|bundle)\b",
                tail,
            ) and not re.search(
                r"\b(?:support|freight|financing|service)\b",
                tail,
            ):
                hardware_prices.append(price)
        if len(hardware_prices) == 1:
            selected_prices = hardware_prices
        else:
            selected_prices = []
            ambiguities.append("ambiguous_price_to_hardware_argument")
    if selected_prices:
        roles.append(selected_prices[0])
        groups.append("price_surface")
    else:
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
        raise ValueError(f"unsupported_R8_target:{target_id}")
    extractor = _EXTRACTOR[target_id]
    output = [
        frame
        for record in frame_records(text)
        if (frame := extractor(record)) is not None
    ]
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
    accepted = next((row for row in frames if row.accepted), None)
    selected = accepted or _best_partial(frames)
    contract = _TARGET_CONTRACT[target_id]
    assessment = dict(base)
    assessment["semantic_guard_revision"] = "R8_SPAN_BOUND_PREDICATE_FRAME"
    assessment["proposition_completion_mode"] = (
        "one_complete_equals_one_span_bound_predicate_frame_no_sentence_union"
    )
    assessment["required_group_ids"] = list(contract["required"])
    assessment["predicate_frames"] = [row.as_dict() for row in frames]
    assessment["typed_propositions"] = [row.as_dict() for row in frames]
    assessment["accepted_frame_id"] = accepted.frame_id if accepted else None
    assessment["accepted_frame_digest"] = accepted.frame_digest if accepted else None
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
            f"missing_R8_role:{role}" for role in selected.missing_required_roles
        )
        limitations.update(f"R8_ambiguity:{row}" for row in selected.ambiguities)
        if accepted and assessment.get("in_period") is not True:
            limitations.add("accepted_frame_outside_target_period")
        assessment["limitations"] = sorted(limitations)
    else:
        if assessment.get("classification") == "complete_bounded_target_package":
            assessment["classification"] = "partial_context_only"
        assessment["package_role"] = contract["partial_role"]
        assessment["limitations"] = sorted(
            set(assessment.get("limitations") or ())
            | {"no_single_R8_span_bound_target_frame"}
        )
    return assessment


__all__ = [
    "ASP_TARGET",
    "CAPACITY_TARGET",
    "FrameRecord",
    "HBM_TARGET",
    "PredicateFrame",
    "RoleBinding",
    "SUPPLIER_TARGET",
    "TARGET_IDS",
    "UNITS_TARGET",
    "YIELD_TARGET",
    "classify_package",
    "extract_predicate_frames",
    "frame_records",
    "normalize_text",
]
