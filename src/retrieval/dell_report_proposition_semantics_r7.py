from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping, Sequence
import unicodedata

from . import dell_report_internal_chain_ceiling_r4 as r4
from .query_plan import canonical_digest


ASP_TARGET = "DELL-RSQ-03A-TARGET-ASP"
SUPPLIER_TARGET = "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH"
CAPACITY_TARGET = "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE"
YIELD_TARGET = "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD"
HBM_TARGET = "DELL-RSQ-03A-TARGET-HBM-SUPPLY"
UNITS_TARGET = "DELL-RSQ-03A-TARGET-UNITS"

TARGET_IDS = frozenset(
    {
        ASP_TARGET,
        SUPPLIER_TARGET,
        CAPACITY_TARGET,
        YIELD_TARGET,
        HBM_TARGET,
        UNITS_TARGET,
    }
)


@dataclass(frozen=True)
class TypedProposition:
    proposition_id: str
    proposition_digest: str
    target_id: str
    sentence_index: int
    clause_index: int
    span_start: int
    span_end: int
    clause_digest: str
    clause_text: str
    actor: str | None
    predicate: str | None
    object_role: str | None
    recipient: str | None
    counterparty: str | None
    polarity: str
    modality: str
    status: str
    speech_mode: str
    reporter: str | None
    asserted_actor: str | None
    quantity_value: str | None
    measure_value: str | None
    currency_value: str | None
    currency_magnitude: str | None
    unit: str | None
    qualifier: str | None
    product: str | None
    period: str | None
    process: str | None
    matched_group_ids: tuple[str, ...]
    missing_required_roles: tuple[str, ...]
    limitations: tuple[str, ...]
    role_anchors: tuple[str, ...]
    accepted: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "proposition_id": self.proposition_id,
            "proposition_digest": self.proposition_digest,
            "target_id": self.target_id,
            "sentence_index": self.sentence_index,
            "clause_index": self.clause_index,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "clause_digest": self.clause_digest,
            "clause_text": self.clause_text,
            "actor": self.actor,
            "predicate": self.predicate,
            "object_role": self.object_role,
            "recipient": self.recipient,
            "counterparty": self.counterparty,
            "polarity": self.polarity,
            "modality": self.modality,
            "status": self.status,
            "speech_mode": self.speech_mode,
            "reporter": self.reporter,
            "asserted_actor": self.asserted_actor,
            "quantity_value": self.quantity_value,
            "measure_value": self.measure_value,
            "currency_value": self.currency_value,
            "currency_magnitude": self.currency_magnitude,
            "unit": self.unit,
            "qualifier": self.qualifier,
            "product": self.product,
            "period": self.period,
            "process": self.process,
            "matched_group_ids": list(self.matched_group_ids),
            "missing_required_roles": list(self.missing_required_roles),
            "limitations": list(self.limitations),
            "role_anchors": list(self.role_anchors),
            "accepted": self.accepted,
        }


@dataclass(frozen=True)
class ClauseRecord:
    sentence_index: int
    clause_index: int
    span_start: int
    span_end: int
    text: str
    sentence_text: str
    preceding_text: str
    following_text: str


_CLAUSE_BOUNDARY = re.compile(
    r"\s*;\s*|\s+[—–]\s+|"
    r",\s*(?=(?:but|while|whereas|although|though|however)\b)|"
    r"\s+(?=(?:but|while|whereas|although|though|however)\b)|"
    r",\s*(?=(?:dell|nvidia|amd|intel|micron|tsmc|gpu|hbm|"
    r"poweredge|production|manufacturing|yield|utilization|capacity|"
    r"allocation|the\s+(?:company|component|capacity|supplier|customer|"
    r"allocation|quote|figure))\b[^,;]{0,48}\b"
    r"(?:did|does|do|was|were|is|are|has|have|had|will|would|may|"
    r"might|should|could|failed|rejected|refused|denied|disputed|"
    r"revoked|suspended|withdrew|withdrawn|secured|received|allocated|"
    r"earmarked)\b)|"
    r"\s+and\s+(?=(?:dell|nvidia|amd|intel|micron|tsmc|gpu|hbm|"
    r"poweredge|production|manufacturing|yield|utilization|capacity|"
    r"allocation|another|a\s+separate|the\s+(?:company|component|"
    r"capacity|supplier|customer|allocation|quote|figure)|next\s+process)"
    r"\b[^,;]{0,48}\b(?:did|does|do|was|were|is|are|has|have|had|"
    r"will|would|may|might|should|could|failed|rejected|refused|"
    r"denied|disputed|revoked|suspended|withdrew|withdrawn|secured|"
    r"received|allocated|earmarked|target)\b)",
    re.IGNORECASE,
)

_NEGATIVE = re.compile(
    r"\b(?:not|never|no\s+longer|did\s+not|does\s+not|do\s+not|"
    r"has\s+not|have\s+not|had\s+not|was\s+not|were\s+not|"
    r"is\s+not|are\s+not|cannot|can't|didn't|doesn't|isn't|aren't|"
    r"wasn't|weren't|hasn't|haven't|hadn't|failed?\s+to|unable\s+to|"
    r"declin(?:e|es|ed|ing)\s+to|refus(?:e|es|ed|ing)\s+to|"
    r"den(?:y|ies|ied|ying)|disput(?:e|es|ed|ing)|"
    r"reject(?:s|ed|ing)?|refut(?:e|es|ed|ing)|unavailable|"
    r"without|lack(?:s|ed|ing)?)\b"
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
    r"plan(?:s|ned|ning)?\s+(?:to|on|for)|"
    r"propos(?:e|es|ed|ing)|"
    r"intend(?:s|ed|ing)?|aim(?:s|ed|ing)?|target(?:s|ed|ing)?|"
    r"indicative|preliminary|hypothetical|likely|possibly|potentially)\b"
)
_REVOKED = re.compile(
    r"\b(?:revok(?:e|es|ed|ing)|suspend(?:s|ed|ing)?|"
    r"withdraw(?:s|n|ing)?|withdrew|cancel(?:s|l?ed|ling|ing)?|"
    r"terminat(?:e|es|ed|ing)|dissolv(?:e|es|ed|ing)|"
    r"retract(?:s|ed|ing)?|expire(?:s|d|ing)?|ended?)\b"
)
_WRONG_PROCESS = re.compile(
    r"\b(?:prototype(?:-line)?|pilot(?:\s+line)?|trial|test(?:ing)?|"
    r"simulat(?:e|es|ed|ion)|a14|sram|n2|next\s+process|orange\s+juice)\b"
)
_NAMED_SUPPLIER = re.compile(
    r"\b(nvidia|micron|tsmc|taiwan\s+semiconductor|sk\s+hynix|broadcom)\b"
)

_PRODUCT_TOKEN = re.compile(
    r"(?<![0-9a-z])(?P<prefix>xe|gb|mi|h|b|a)"
    r"(?P<separator>[\s_\-/‐‑‒–—−]*)"
    r"(?P<number>\d{2,4}x?)(?P<plural>s)?(?![0-9a-z])"
)
_PRODUCT_ALLOWED = {
    "xe": {"9680", "9712", "7740", "7745"},
    "gb": {"200", "300"},
    "mi": {"300", "300x", "325x", "355x"},
    "h": {"100", "200"},
    "b": {"100", "200"},
    "a": {"100", "800"},
}

_PRICE_PREFIX = re.compile(
    r"(?P<qualifier>about|approximately|approx\.?|around|at\s+most|"
    r"up\s+to|no\s+more\s+than)?\s*"
    r"(?:(?:usd|us\$)\s*\$?|\$)\s*"
    r"(?P<number>[0-9][0-9,]*(?:\.[0-9]+)?)\s*"
    r"(?P<magnitude>k|m|bn|thousand|million|billion)?\b"
)
_PRICE_SUFFIX = re.compile(
    r"(?P<qualifier>about|approximately|approx\.?|around|at\s+most|"
    r"up\s+to|no\s+more\s+than)?\s*"
    r"(?P<number>[0-9][0-9,]*(?:\.[0-9]+)?)\s*"
    r"(?P<magnitude>k|m|bn|thousand|million|billion)?\s*"
    r"(?:us\s+)?dollars?\b"
)
_PERCENT = re.compile(r"(?<![0-9a-z])([0-9]{1,3}(?:\.[0-9]+)?)\s*%")
_QUANTITY = re.compile(
    r"(?<![$0-9a-z])(?P<number>[0-9][0-9,]*|one|two|three|four|five|"
    r"six|seven|eight|nine|ten)(?:\s*\([0-9]+\))?"
    r"(?:\s+[a-z0-9-]+){0,5}\s+"
    r"(?P<unit>server\s+units|servers|systems|nodes)(?![0-9a-z])"
)
_NUMBER_WORDS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}
_FY = re.compile(r"(?<![0-9a-z])fy\s*['’]?\s*([0-9]{2,4})(?![0-9a-z])")
_FISCAL_YEAR = re.compile(
    r"(?<![0-9a-z])fiscal(?:\s+year)?\s*([0-9]{2,4})(?![0-9a-z])"
)
_QUARTER = re.compile(r"(?<![0-9a-z])q([1-4])(?:\s*(20[0-9]{2}))?(?![0-9a-z])")
_YEAR = re.compile(r"(?<![0-9a-z])(20[0-9]{2})(?![0-9a-z])")

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
        ),
        "complete_role": "observed_relevant_supply_yield_or_utilization",
        "partial_role": "yield_or_utilization_context",
    },
    HBM_TARGET: {
        "required": (
            "hbm_subject",
            "supply_state",
            "directional_Dell_bridge",
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
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.translate(
        str.maketrans(
            {
                "−": "-",
                "‐": "-",
                "‑": "-",
                "‒": "-",
                "–": "-",
                "—": "-",
                "’": "'",
                "‘": "'",
            }
        )
    )
    return re.sub(r"\s+", " ", text).strip().casefold()


def _sentence_units(text: str) -> list[str]:
    return [normalize_text(row) for row in r4._sentence_units(text) if normalize_text(row)]  # noqa: SLF001


def clause_records(text: str) -> list[ClauseRecord]:
    records: list[ClauseRecord] = []
    absolute = 0
    for sentence_index, sentence in enumerate(_sentence_units(text)):
        clauses = [part.strip(" ,") for part in _CLAUSE_BOUNDARY.split(sentence) if part.strip(" ,")]
        merged: list[str] = []
        for clause in clauses:
            if (
                merged
                and _NAMED_SUPPLIER.fullmatch(merged[-1])
                and re.match(
                    r"dell\s+(?:is|are|was|were|has|have)\s+"
                    r"(?:partner|collaborat|team|all)",
                    clause,
                )
            ):
                merged[-1] = f"{merged[-1]} and {clause}"
            else:
                merged.append(clause)
        clauses = merged
        local = 0
        spans: list[tuple[int, int]] = []
        for clause in clauses:
            start = sentence.find(clause, local)
            if start < 0:
                start = local
            end = start + len(clause)
            spans.append((start, end))
            local = end
        for clause_index, (clause, (start, end)) in enumerate(zip(clauses, spans)):
            records.append(
                ClauseRecord(
                    sentence_index=sentence_index,
                    clause_index=clause_index,
                    span_start=absolute + start,
                    span_end=absolute + end,
                    text=clause,
                    sentence_text=sentence,
                    preceding_text=" ".join(clauses[:clause_index]),
                    following_text=" ".join(clauses[clause_index + 1 :]),
                )
            )
        absolute += len(sentence) + 1
    return records


def _normalized_number(value: str) -> str:
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation:
        return value.replace(",", "").casefold()
    rendered = format(number.normalize(), "f")
    return "0" if rendered in {"", "-0"} else rendered


def _canonical_year(value: str) -> str:
    year = int(value)
    return str(year + 2000 if len(value) == 2 else year)


def _canonical_qualifier(value: str | None) -> str | None:
    token = normalize_text(value)
    if not token:
        return None
    if token in {"approximately", "approx.", "approx", "around"}:
        return "about"
    if token in {"up to", "no more than"}:
        return "at_most"
    return token.replace(" ", "_")


def _canonical_magnitude(value: str | None) -> str | None:
    token = normalize_text(value)
    return {
        "k": "thousand",
        "m": "million",
        "bn": "billion",
    }.get(token, token or None)


def _product_matches(text: str) -> list[tuple[str, tuple[int, int]]]:
    output: list[tuple[str, tuple[int, int]]] = []
    normalized = normalize_text(text)
    for match in _PRODUCT_TOKEN.finditer(normalized):
        prefix = match.group("prefix")
        number = match.group("number")
        separator = match.group("separator")
        if prefix == "a" and separator.isspace():
            continue
        canonical = f"{prefix}{number}"
        if number in _PRODUCT_ALLOWED.get(prefix, set()):
            output.append((canonical, match.span()))
        elif separator:
            output.append((f"unknown_{canonical}", match.span()))
    return output


def _product_role(text: str) -> str | None:
    products = _product_matches(text)
    if products:
        return products[0][0]
    normalized = normalize_text(text)
    if re.search(r"\b(?:dell\s+)?poweredge\b", normalized):
        return "dell_poweredge_server"
    if re.search(r"\b(?:ai|gpu|accelerator|high\s+performance)\s+(?:server|system|node)s?\b", normalized):
        return "ai_server_system"
    if re.search(r"\b(?:hardware|equipment|bundle)\b", normalized):
        return "bounded_hardware_configuration"
    return None


def _price_role(text: str) -> tuple[str | None, str | None, str | None, int]:
    candidates: list[re.Match[str]] = list(_PRICE_PREFIX.finditer(text))
    candidates.extend(_PRICE_SUFFIX.finditer(text))
    if not candidates:
        return None, None, None, 0
    match = min(candidates, key=lambda row: row.start())
    return (
        _normalized_number(match.group("number")),
        _canonical_magnitude(match.group("magnitude")),
        _canonical_qualifier(match.group("qualifier")),
        match.end(),
    )


def _quantity_role(text: str) -> tuple[str | None, str | None, int]:
    match = _QUANTITY.search(text)
    if not match:
        return None, None, 0
    raw = match.group("number")
    value = _NUMBER_WORDS.get(raw, _normalized_number(raw))
    unit = "physical_server" if match.group("unit") else None
    return value, unit, match.end()


def _period_role(text: str) -> tuple[str | None, tuple[str, ...]]:
    anchors: set[str] = set()
    for pattern in (_FY, _FISCAL_YEAR):
        for match in pattern.finditer(text):
            anchors.add(f"period.fiscal_year:{_canonical_year(match.group(1))}")
    for match in _QUARTER.finditer(text):
        anchors.add(f"period.quarter:{match.group(1)}")
        if match.group(2):
            anchors.add(f"period.calendar_year:{match.group(2)}")
    for match in _YEAR.finditer(text):
        year_anchor = f"period.calendar_year:{match.group(1)}"
        if not any(match.group(1) in anchor and "fiscal_year" in anchor for anchor in anchors):
            anchors.add(year_anchor)
    return (sorted(anchors)[0] if anchors else None, tuple(sorted(anchors)))


def _yield_process(clause: str, sentence: str) -> str | None:
    scope = f"{clause} {sentence}"
    if "orange juice" in clause:
        return "irrelevant_orange_juice"
    if "hbm" in scope or "high bandwidth memory" in scope:
        return "hbm_production"
    if re.search(r"\b(?:dram|memory|gpu|wafer|semiconductor|fab)\b", scope):
        return "relevant_semiconductor_production"
    return None


def _reporter(text: str, assertion_start: int) -> tuple[str | None, str]:
    prefix = text[:assertion_start]
    matches = list(
        re.finditer(
            r"(?P<reporter>(?:a\s+)?(?:dell\s+customer|customer|acme|"
            r"analyst|source|nvidia|dell|[a-z][a-z0-9-]{1,24}))\s+"
            r"(?P<verb>said|reported|claimed|disclosed|announced|stated|confirmed)\b",
            prefix,
        )
    )
    if not matches:
        return None, "direct_assertion"
    reporter = matches[-1].group("reporter")
    return reporter, "attributed_assertion"


def _semantic_scope(text: str, assertion_end: int) -> str:
    scope = text[:assertion_end]
    return re.sub(
        r"\b(?:not\s+(?:only|alone)|not\s+previously\s+disclosed|"
        r"not\s+constrained|no\s+later\s+than)\b",
        "",
        scope,
    )


def _tail_revokes(record: ClauseRecord, target_id: str, assertion_end: int) -> bool:
    tail = f"{record.text[assertion_end:]} {record.following_text}".strip()
    if not tail or not _REVOKED.search(tail):
        return False
    nouns = {
        ASP_TARGET: r"\b(?:quote|price|offer|it|this|that)\b",
        SUPPLIER_TARGET: r"\b(?:partnership|collaboration|alliance|relationship|it|this|that)\b",
        CAPACITY_TARGET: r"\b(?:allocation|capacity|commitment|it|this|that)\b",
        YIELD_TARGET: r"\b(?:yield|figure|measure|rate|it|this|that)\b",
        HBM_TARGET: r"\b(?:allocation|configuration|supply|bridge|it|this|that)\b",
        UNITS_TARGET: r"\b(?:shipment|delivery|report|it|this|that)\b",
    }
    return re.search(nouns[target_id], tail) is not None


def _state(
    record: ClauseRecord,
    target_id: str,
    assertion_end: int,
    *,
    extra_limitations: Sequence[str] = (),
) -> tuple[str, str, str, tuple[str, ...]]:
    scope = _semantic_scope(record.text, assertion_end)
    limitations = set(extra_limitations)
    polarity = "affirmative"
    modality = "actual"
    status = "active"
    if _NEGATIVE.search(scope):
        polarity = "negative"
        limitations.add("negative_or_denied_target_proposition")
    if _ALLEGED.search(scope):
        modality = "alleged_or_rumor"
        limitations.add("alleged_rumor_or_unconfirmed_target_proposition")
    elif _MODAL.search(scope):
        modality = "capability_or_forward_looking"
        limitations.add("capability_or_forward_looking_target_proposition")
    if _tail_revokes(record, target_id, assertion_end):
        status = "revoked_suspended_or_withdrawn"
        limitations.add("target_proposition_later_revoked_suspended_or_withdrawn")
    return polarity, modality, status, tuple(sorted(limitations))


def _role_anchors(
    *,
    target_id: str,
    actor: str | None,
    predicate: str | None,
    object_role: str | None,
    recipient: str | None,
    counterparty: str | None,
    product: str | None,
    quantity: str | None,
    measure: str | None,
    currency: str | None,
    magnitude: str | None,
    qualifier: str | None,
    period_anchors: Sequence[str],
    process: str | None,
) -> tuple[str, ...]:
    anchors: set[str] = set(period_anchors)

    def role_token(value: str) -> str:
        return re.sub(
            r"[^a-z0-9]+", "_", normalize_text(value)
        ).strip("_")

    def predicate_token(value: str) -> str:
        token = normalize_text(value)
        if target_id == ASP_TARGET:
            return "price_quote_or_sale"
        if target_id == SUPPLIER_TARGET:
            if re.search(
                r"partner|collaborat|alliance|team|supplier", token
            ):
                return "supplier_relationship"
            return "supplier_product_delivery"
        if target_id == CAPACITY_TARGET:
            return "capacity_allocation_or_receipt"
        if target_id == YIELD_TARGET:
            return "observed_yield_or_utilization"
        if target_id == HBM_TARGET:
            return "hbm_integration_or_supply"
        if target_id == UNITS_TARGET:
            return "physical_server_shipment"
        return role_token(token)

    for role, value in (
        ("actor", actor),
        ("recipient", recipient),
        ("counterparty", counterparty),
        ("object", object_role),
    ):
        if value:
            anchors.add(f"{role}:{role_token(value)}")
    if predicate:
        anchors.add(f"predicate:{predicate_token(predicate)}")
    if product:
        prefix = "product_code" if product not in {"dell_poweredge_server", "ai_server_system", "bounded_hardware_configuration"} else "product"
        anchors.add(f"{prefix}:{product}")
    if target_id == ASP_TARGET and currency:
        anchors.add(f"price.currency_usd:{currency}")
        if magnitude:
            anchors.add(f"price.magnitude:{magnitude}")
        if qualifier:
            anchors.add(f"price.qualifier:{qualifier}")
    if target_id in {ASP_TARGET, UNITS_TARGET} and quantity:
        anchors.add(f"quantity.physical_server:{quantity}")
    if target_id == YIELD_TARGET and measure:
        anchors.add(f"yield.percent:{measure}")
    if process:
        anchors.add(f"process:{process}")
    return tuple(sorted(anchors))


def _finalize(
    *,
    record: ClauseRecord,
    target_id: str,
    actor: str | None,
    predicate: str | None,
    object_role: str | None,
    recipient: str | None,
    counterparty: str | None,
    polarity: str,
    modality: str,
    status: str,
    speech_mode: str,
    reporter: str | None,
    asserted_actor: str | None,
    quantity: str | None,
    measure: str | None,
    currency: str | None,
    magnitude: str | None,
    unit: str | None,
    qualifier: str | None,
    product: str | None,
    period: str | None,
    process: str | None,
    groups: Sequence[str],
    missing: Sequence[str],
    limitations: Sequence[str],
    period_anchors: Sequence[str],
) -> TypedProposition:
    role_anchors = _role_anchors(
        target_id=target_id,
        actor=actor,
        predicate=predicate,
        object_role=object_role,
        recipient=recipient,
        counterparty=counterparty,
        product=product,
        quantity=quantity,
        measure=measure,
        currency=currency,
        magnitude=magnitude,
        qualifier=qualifier,
        period_anchors=period_anchors,
        process=process,
    )
    missing_roles = tuple(sorted(set(missing)))
    observed_limitations = tuple(sorted(set(limitations)))
    accepted = (
        not missing_roles
        and polarity == "affirmative"
        and modality == "actual"
        and status == "active"
        and not observed_limitations
    )
    body = {
        "target_id": target_id,
        "sentence_index": record.sentence_index,
        "clause_index": record.clause_index,
        "span_start": record.span_start,
        "span_end": record.span_end,
        "clause_digest": canonical_digest(record.text),
        "actor": actor,
        "predicate": predicate,
        "object_role": object_role,
        "recipient": recipient,
        "counterparty": counterparty,
        "polarity": polarity,
        "modality": modality,
        "status": status,
        "speech_mode": speech_mode,
        "reporter": reporter,
        "asserted_actor": asserted_actor,
        "quantity_value": quantity,
        "measure_value": measure,
        "currency_value": currency,
        "currency_magnitude": magnitude,
        "unit": unit,
        "qualifier": qualifier,
        "product": product,
        "period": period,
        "process": process,
        "matched_group_ids": sorted(set(groups)),
        "missing_required_roles": list(missing_roles),
        "limitations": list(observed_limitations),
        "role_anchors": list(role_anchors),
        "accepted": accepted,
    }
    digest = canonical_digest(body)
    return TypedProposition(
        proposition_id=f"PROP::R7::{digest[:24].upper()}",
        proposition_digest=digest,
        target_id=target_id,
        sentence_index=record.sentence_index,
        clause_index=record.clause_index,
        span_start=record.span_start,
        span_end=record.span_end,
        clause_digest=body["clause_digest"],
        clause_text=record.text,
        actor=actor,
        predicate=predicate,
        object_role=object_role,
        recipient=recipient,
        counterparty=counterparty,
        polarity=polarity,
        modality=modality,
        status=status,
        speech_mode=speech_mode,
        reporter=reporter,
        asserted_actor=asserted_actor,
        quantity_value=quantity,
        measure_value=measure,
        currency_value=currency,
        currency_magnitude=magnitude,
        unit=unit,
        qualifier=qualifier,
        product=product,
        period=period,
        process=process,
        matched_group_ids=tuple(sorted(set(groups))),
        missing_required_roles=missing_roles,
        limitations=observed_limitations,
        role_anchors=role_anchors,
        accepted=accepted,
    )


def _asp_proposition(record: ClauseRecord) -> TypedProposition | None:
    text = record.text
    predicate_match = re.search(
        r"\b(quoted?|pricing|priced?|sold|sale|purchase\s+price|"
        r"configuration\s+price|recommended\s+price|contract\s+amount|"
        r"total\s+contract\s+cost|contract\s+cost)\b",
        text,
    )
    currency, magnitude, qualifier, price_end = _price_role(text)
    if not predicate_match and not currency:
        return None
    quantity, unit, quantity_end = _quantity_role(text)
    product = _product_role(text)
    bounded_object = bool(
        product
        or re.search(r"\b(?:hardware|equipment|bundle|server|system|node)s?\b", text)
    )
    actor = "Dell" if re.search(r"\bdell\b[^.;]{0,56}\b(?:quoted?|priced?|sold)\b", text) else None
    predicate = predicate_match.group(1) if predicate_match else None
    assertion_end = max(
        predicate_match.end() if predicate_match else 0,
        price_end,
        quantity_end,
    )
    reporter, speech_mode = _reporter(text, predicate_match.start() if predicate_match else 0)
    extra: list[str] = []
    if reporter and reporter != "dell":
        extra.append("third_party_price_report_not_Dell_quote")
    polarity, modality, status, limitations = _state(
        record, ASP_TARGET, assertion_end, extra_limitations=extra
    )
    period, period_anchors = _period_role(text)
    groups = []
    if actor:
        groups.append("dell_subject")
    if predicate:
        groups.append("affirmative_price_quote")
    if currency:
        groups.append("price_surface")
    if bounded_object:
        groups.append("bounded_object")
        groups.append("bundle_boundary")
    if product:
        groups.append("dell_ai_server")
    if quantity:
        groups.append("valid_denominator")
    missing = []
    if not actor:
        missing.append("Dell_seller_or_quoter")
    if not predicate:
        missing.append("affirmative_price_predicate")
    if not currency:
        missing.append("currency_price")
    if not bounded_object:
        missing.append("bounded_hardware_or_server_object")
    return _finalize(
        record=record,
        target_id=ASP_TARGET,
        actor=actor,
        predicate=predicate,
        object_role=product or ("bounded_hardware_configuration" if bounded_object else None),
        recipient=None,
        counterparty=None,
        polarity=polarity,
        modality=modality,
        status=status,
        speech_mode=speech_mode,
        reporter=reporter,
        asserted_actor=actor,
        quantity=quantity,
        measure=None,
        currency=currency,
        magnitude=magnitude,
        unit=unit,
        qualifier=qualifier,
        product=product,
        period=period,
        process=None,
        groups=groups,
        missing=missing,
        limitations=limitations,
        period_anchors=period_anchors,
    )


def _supplier_proposition(record: ClauseRecord) -> TypedProposition | None:
    text = record.text
    supplier_match = _NAMED_SUPPLIER.search(text)
    if not supplier_match or "dell" not in text:
        return None
    relationship_match = re.search(
        r"\b(partner(?:s|ed|ing|ship)?|"
        r"collaborat(?:e|es|ed|ing|ion)|alliance|"
        r"team(?:s|ed|ing)?\s+up|supplier)\b",
        text,
    )
    delivery_match = re.search(
        r"\b(suppl(?:y|ies|ied|ying)|deliver(?:s|ed|ing|y)?|"
        r"ship(?:s|ped|ping)?|available)\b",
        text,
    )
    predicate_match = relationship_match or delivery_match
    if not predicate_match:
        return None
    product = _product_role(text)
    prefix = text[: predicate_match.start()]
    tail = text[predicate_match.end() :]
    supplier = supplier_match.group(1)
    explicit_relationship = relationship_match is not None
    supplier_to_dell = bool(
        delivery_match
        and (
            re.search(r"\b(?:to|for|through)\s+dell\b", tail)
            or re.match(r"\s+dell\b", tail)
            or re.search(
                r"\bdell\b[^.;]{0,48}\b(?:received?|secured?)\b",
                text,
            )
        )
    )
    dell_component_subject_delivery = bool(
        delivery_match
        and "dell" in prefix
        and supplier in prefix
        and (
            _product_matches(prefix)
            or re.search(r"\b(?:poweredge|server|system|node)s?\b", prefix)
        )
    )
    relevant_product_after_delivery = bool(
        delivery_match
        and (
            _product_matches(tail)
            or re.search(
                r"\b(?:poweredge|ai\s+infrastructure|gpu|accelerator|"
                r"server|system|node)s?\b",
                tail,
            )
        )
    )
    direction_valid = bool(
        explicit_relationship
        or supplier_to_dell
        or dell_component_subject_delivery
        or relevant_product_after_delivery
    )
    assertion_end = predicate_match.end()
    extra: list[str] = []
    supplier_tail = f"{text[assertion_end:]} {record.following_text}"
    if re.search(
        r"\b(?:partnership|collaboration|alliance|relationship|rumou?r)\b"
        r"[^.;]{0,64}\b(?:denied|disputed|refuted|rejected)\b",
        supplier_tail,
    ):
        extra.append("supplier_relationship_rumor_or_claim_denied")
    if not direction_valid:
        extra.append(
            "delivery_predicate_object_is_not_supplier_Dell_"
            "relationship_or_relevant_product"
        )
    polarity, modality, status, limitations = _state(
        record,
        SUPPLIER_TARGET,
        assertion_end,
        extra_limitations=extra,
    )
    period, period_anchors = _period_role(text)
    groups = ["dell_subject", "named_supplier"]
    if direction_valid:
        groups.append("directional_relationship_delivery")
    if product or "server" in text:
        groups.append("dell_ai_server")
    missing = []
    if not direction_valid:
        missing.append(
            "supplier_Dell_relationship_or_relevant_product_delivery_direction"
        )
    actor = (
        "Dell"
        if dell_component_subject_delivery
        or (
            relevant_product_after_delivery
            and "dell" in prefix
            and supplier not in prefix
        )
        else supplier
    )
    recipient = (
        "customer_market"
        if actor == "Dell" and not explicit_relationship
        else "Dell"
    )
    return _finalize(
        record=record,
        target_id=SUPPLIER_TARGET,
        actor=actor,
        predicate=predicate_match.group(1),
        object_role=product or "ai_infrastructure_delivery",
        recipient=recipient,
        counterparty=(supplier if actor == "Dell" else "Dell"),
        polarity=polarity,
        modality=modality,
        status=status,
        speech_mode="direct_or_participant_attributed_assertion",
        reporter=None,
        asserted_actor=actor,
        quantity=None,
        measure=None,
        currency=None,
        magnitude=None,
        unit=None,
        qualifier=None,
        product=product,
        period=period,
        process="ai_infrastructure_supply",
        groups=groups,
        missing=missing,
        limitations=limitations,
        period_anchors=period_anchors,
    )


def _capacity_proposition(record: ClauseRecord) -> TypedProposition | None:
    text = record.text
    if not re.search(r"\b(?:capacity|allocation|supply)\b", text) or "dell" not in text:
        return None
    predicate_match = re.search(
        r"\b(allocat(?:e|es|ed|ing)|earmark(?:s|ed|ing)?|"
        r"reserv(?:e|es|ed|ing)|commit(?:s|ted|ting)?|"
        r"dedicat(?:e|es|ed|ing)|assign(?:s|ed|ing)?|"
        r"grant(?:s|ed|ing)?|secur(?:e|es|ed|ing)|"
        r"receiv(?:e|es|ed|ing)|available|suppl(?:y|ies|ied|ying))\b",
        text,
    )
    if not predicate_match:
        return None
    recipient = "Dell" if re.search(r"\b(?:to|for)\s+dell\b|\bdell\b[^.;]{0,48}\b(?:secured?|received?)\b", text) else None
    period, period_anchors = _period_role(text)
    assertion_end = max(predicate_match.end(), max((m.end() for m in _QUARTER.finditer(text)), default=0), max((m.end() for m in _YEAR.finditer(text)), default=0))
    extra: list[str] = []
    if re.search(r"\b(?:to|for)\s+(?:hp|hpe)\b[^.;]{0,40}\brather\s+than\b[^.;]{0,24}\bdell\b", text):
        extra.append("allocation_recipient_is_other_company_not_Dell")
    if re.search(r"\b(?:zero|0)\b[^.;]{0,40}\b(?:capacity|allocation)\b|\b(?:capacity|allocation)\b[^.;]{0,40}\b(?:zero|0)\b", text):
        extra.append("zero_capacity_or_allocation_is_not_positive_release")
    if re.search(r"\ballocated\s+away\s+from\s+dell\b", text):
        extra.append("capacity_allocated_away_from_Dell")
    polarity, modality, status, limitations = _state(
        record, CAPACITY_TARGET, assertion_end, extra_limitations=extra
    )
    groups = ["relevant_supply", "capacity_or_availability_event"]
    if recipient:
        groups.append("upstream_Dell_allocation")
    if period:
        groups.append("timing_surface")
    missing = []
    if not recipient:
        missing.append("Dell_recipient_or_beneficiary")
    if not period:
        missing.append("allocation_period")
    return _finalize(
        record=record,
        target_id=CAPACITY_TARGET,
        actor="upstream_capacity_provider",
        predicate=predicate_match.group(1),
        object_role="production_capacity_or_supply_allocation",
        recipient=recipient,
        counterparty=None,
        polarity=polarity,
        modality=modality,
        status=status,
        speech_mode="direct_assertion",
        reporter=None,
        asserted_actor="upstream_capacity_provider",
        quantity=None,
        measure=None,
        currency=None,
        magnitude=None,
        unit=None,
        qualifier=None,
        product=_product_role(text),
        period=period,
        process="gpu_or_component_production_capacity",
        groups=groups,
        missing=missing,
        limitations=limitations,
        period_anchors=period_anchors,
    )


def _yield_proposition(record: ClauseRecord) -> TypedProposition | None:
    text = record.text
    if not re.search(r"\b(?:yield|utilization)\b", text):
        return None
    measure_match = _PERCENT.search(text)
    full_utilization = re.search(r"\b(?:at|near|below)\s+full\s+utilization\b", text)
    if not measure_match and not full_utilization:
        return None
    predicate_match = re.search(
        r"\b(achiev(?:e|es|ed|ing)|reached?|recorded?|reported?|was|is|stood|measured)\b",
        text,
    )
    process = _yield_process(text, record.sentence_text)
    period, period_anchors = _period_role(text)
    assertion_end = max(
        measure_match.end() if measure_match else 0,
        full_utilization.end() if full_utilization else 0,
        predicate_match.end() if predicate_match else 0,
    )
    extra: list[str] = []
    if _WRONG_PROCESS.search(text) or process in {None, "irrelevant_orange_juice"}:
        extra.append("wrong_simulated_or_irrelevant_production_process")
    polarity, modality, status, limitations = _state(
        record, YIELD_TARGET, assertion_end, extra_limitations=extra
    )
    groups = []
    if process and process != "irrelevant_orange_juice":
        groups.append("relevant_supply")
    if predicate_match:
        groups.append("observed_yield_or_utilization")
    if measure_match or full_utilization:
        groups.append("observed_measure")
    missing = []
    if not process or process == "irrelevant_orange_juice":
        missing.append("relevant_production_process")
    if not predicate_match:
        missing.append("observed_measure_predicate")
    return _finalize(
        record=record,
        target_id=YIELD_TARGET,
        actor=process,
        predicate=predicate_match.group(1) if predicate_match else None,
        object_role="yield_or_utilization_measure",
        recipient=None,
        counterparty=None,
        polarity=polarity,
        modality=modality,
        status=status,
        speech_mode="direct_assertion",
        reporter=None,
        asserted_actor=process,
        quantity=None,
        measure=_normalized_number(measure_match.group(1)) if measure_match else "full_utilization",
        currency=None,
        magnitude=None,
        unit="percent" if measure_match else "utilization_state",
        qualifier=None,
        product=_product_role(text),
        period=period,
        process=process,
        groups=groups,
        missing=missing,
        limitations=limitations,
        period_anchors=period_anchors,
    )


def _hbm_proposition(record: ClauseRecord) -> TypedProposition | None:
    text = record.text
    if not re.search(r"\b(?:hbm|high[- ]bandwidth\s+memory)\b", text):
        return None
    predicate_match = re.search(
        r"\b(allocat(?:e|es|ed|ing)|earmark(?:s|ed|ing)?|"
        r"configur(?:e|es|ed|ing)|equip(?:s|ped|ping)?|"
        r"incorporat(?:e|es|ed|ing)|integrat(?:e|es|ed|ing)|"
        r"power(?:s|ed|ing)?|suppl(?:ies|ied|ying)|supply(?!\s+capacity)|"
        r"available)\b",
        text,
    )
    if not predicate_match:
        return None
    recipient = "Dell" if re.search(r"\b(?:dell|poweredge)\b", text) else None
    period, period_anchors = _period_role(text)
    assertion_end = predicate_match.end()
    extra: list[str] = []
    if re.search(r"\bwithout\s+(?:hbm|high[- ]bandwidth\s+memory)\b", text):
        extra.append("configured_without_HBM")
    polarity, modality, status, limitations = _state(
        record, HBM_TARGET, assertion_end, extra_limitations=extra
    )
    groups = ["hbm_subject", "supply_state"]
    if recipient:
        groups.append("directional_Dell_bridge")
    if period:
        groups.append("time_surface")
    missing = []
    if not recipient:
        missing.append("Dell_or_PowerEdge_bridge")
    return _finalize(
        record=record,
        target_id=HBM_TARGET,
        actor=recipient or "HBM_supplier",
        predicate=predicate_match.group(1),
        object_role="HBM_component_or_supply",
        recipient=recipient,
        counterparty=None,
        polarity=polarity,
        modality=modality,
        status=status,
        speech_mode="direct_assertion",
        reporter=None,
        asserted_actor=recipient,
        quantity=None,
        measure=None,
        currency=None,
        magnitude=None,
        unit=None,
        qualifier=None,
        product=_product_role(text),
        period=period,
        process="HBM_supply_or_configuration",
        groups=groups,
        missing=missing,
        limitations=limitations,
        period_anchors=period_anchors,
    )


def _units_proposition(record: ClauseRecord) -> TypedProposition | None:
    text = record.text
    action_match = re.search(r"\b(shipped|delivered|sent)\b", text)
    quantity, unit, quantity_end = _quantity_role(text)
    if not action_match and not quantity:
        return None
    actor = None
    asserted_actor = None
    if action_match:
        prefix = text[: action_match.start()]
        if re.search(
            r"\bdell\s+(?:(?:has|had|already|recently|currently)\s+){0,3}$",
            prefix,
        ):
            actor = "Dell"
            asserted_actor = "Dell"
        elif re.search(
            r"\bdell\s+(?:said|reported|confirmed|announced|disclosed)\s+"
            r"(?:that\s+)?it\s+$",
            prefix,
        ):
            actor = "Dell"
            asserted_actor = "Dell"
        elif re.search(r"\b(?:it|dell)\s*$", prefix) and "dell" in text[: action_match.start()]:
            actor = "Dell"
            asserted_actor = "Dell"
        elif re.search(r"\bby\s+dell\b", text[action_match.end() :]):
            actor = "Dell"
            asserted_actor = "Dell"
    reporter, speech_mode = _reporter(text, action_match.start() if action_match else 0)
    product = _product_role(text)
    ai_physical = bool(
        product
        and (
            product not in {"dell_poweredge_server", "bounded_hardware_configuration"}
            or re.search(r"\b(?:ai|gpu|accelerator|hgx)\b", text)
        )
    )
    period, period_anchors = _period_role(text)
    assertion_end = max(action_match.end() if action_match else 0, quantity_end)
    extra: list[str] = []
    if reporter and reporter != "dell":
        extra.append("third_party_report_not_Dell_company_shipment")
    if action_match and re.search(r"\bdell\s+(?:said|disclosed|reported)\s+(?:that\s+)?(?:nvidia|(?:the\s+)?customer)\s+" + re.escape(action_match.group(1)), text):
        extra.append("asserted_shipper_is_not_Dell")
        actor = None
    if not ai_physical:
        extra.append("generic_or_non_AI_server_quantity")
    polarity, modality, status, limitations = _state(
        record, UNITS_TARGET, assertion_end, extra_limitations=extra
    )
    groups = []
    if actor:
        groups.append("dell_subject")
        groups.append("Dell_seller_or_shipper_role")
    if quantity and unit:
        groups.append("physical_server_quantity")
    if product:
        groups.append("dell_ai_server")
    if period:
        groups.append("timing_surface")
    missing = []
    if not actor:
        missing.append("Dell_actual_shipper")
    if not quantity or not unit:
        missing.append("physical_server_quantity")
    if not ai_physical:
        missing.append("Dell_AI_server_product")
    if not period:
        missing.append("shipment_period")
    return _finalize(
        record=record,
        target_id=UNITS_TARGET,
        actor=actor,
        predicate=action_match.group(1) if action_match else None,
        object_role="physical_AI_server_shipment" if ai_physical else product,
        recipient=None,
        counterparty=None,
        polarity=polarity,
        modality=modality,
        status=status,
        speech_mode=speech_mode,
        reporter=reporter,
        asserted_actor=asserted_actor,
        quantity=quantity,
        measure=None,
        currency=None,
        magnitude=None,
        unit=unit,
        qualifier=None,
        product=product,
        period=period,
        process="Dell_company_server_shipment",
        groups=groups,
        missing=missing,
        limitations=limitations,
        period_anchors=period_anchors,
    )


_EXTRACTOR = {
    ASP_TARGET: _asp_proposition,
    SUPPLIER_TARGET: _supplier_proposition,
    CAPACITY_TARGET: _capacity_proposition,
    YIELD_TARGET: _yield_proposition,
    HBM_TARGET: _hbm_proposition,
    UNITS_TARGET: _units_proposition,
}


def extract_typed_propositions(
    *, target_id: str, text: str, metadata: Mapping[str, Any]
) -> list[TypedProposition]:
    del metadata
    if target_id not in TARGET_IDS:
        raise ValueError(f"unsupported_R7_target:{target_id}")
    extractor = _EXTRACTOR[target_id]
    output = [
        proposition
        for record in clause_records(text)
        if (proposition := extractor(record)) is not None
    ]
    return sorted(
        output,
        key=lambda row: (
            row.sentence_index,
            row.clause_index,
            row.span_start,
            row.proposition_id,
        ),
    )


def _best_partial(propositions: Sequence[TypedProposition]) -> TypedProposition | None:
    if not propositions:
        return None
    return min(
        propositions,
        key=lambda row: (
            len(row.missing_required_roles) + len(row.limitations),
            len(row.missing_required_roles),
            row.sentence_index,
            row.clause_index,
            row.proposition_id,
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
    propositions = extract_typed_propositions(
        target_id=target_id,
        text=text,
        metadata=metadata,
    )
    accepted = next((row for row in propositions if row.accepted), None)
    selected = accepted or _best_partial(propositions)
    contract = _TARGET_CONTRACT[target_id]
    assessment = dict(base)
    assessment["semantic_guard_revision"] = "R7_SINGLE_TYPED_PROPOSITION"
    assessment["proposition_completion_mode"] = (
        "one_complete_equals_one_proposition_no_group_union"
    )
    assessment["required_group_ids"] = list(contract["required"])
    assessment["typed_propositions"] = [row.as_dict() for row in propositions]
    assessment["accepted_proposition_id"] = (
        accepted.proposition_id if accepted else None
    )
    assessment["accepted_proposition_digest"] = (
        accepted.proposition_digest if accepted else None
    )
    assessment["accepted_proposition_sentence_index"] = (
        accepted.sentence_index if accepted else None
    )
    assessment["accepted_proposition_clause_index"] = (
        accepted.clause_index if accepted else None
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
            f"missing_R7_role:{role}"
            for role in selected.missing_required_roles
        )
        if accepted and assessment.get("in_period") is not True:
            limitations.add("accepted_proposition_outside_target_period")
        assessment["limitations"] = sorted(limitations)
    else:
        if assessment.get("classification") == "complete_bounded_target_package":
            assessment["classification"] = "partial_context_only"
        assessment["package_role"] = contract["partial_role"]
        assessment["limitations"] = sorted(
            set(assessment.get("limitations") or ())
            | {"no_single_R7_typed_target_proposition"}
        )
    return assessment


def generic_typed_material_anchors(text: str) -> list[str]:
    normalized = normalize_text(text)
    anchors: set[str] = set()
    occupied: list[tuple[int, int]] = []
    for product, span in _product_matches(normalized):
        anchors.add(f"product_code:{product}")
        occupied.append(span)
    for pattern in (_PRICE_PREFIX, _PRICE_SUFFIX):
        for match in pattern.finditer(normalized):
            anchors.add(f"currency_usd:{_normalized_number(match.group('number'))}")
            magnitude = _canonical_magnitude(match.group("magnitude"))
            qualifier = _canonical_qualifier(match.group("qualifier"))
            if magnitude:
                anchors.add(f"magnitude:{magnitude}")
            if qualifier:
                anchors.add(f"qualifier:{qualifier}")
            occupied.append(match.span())
    for match in _PERCENT.finditer(normalized):
        anchors.add(f"percent:{_normalized_number(match.group(1))}")
        occupied.append(match.span())
    _, period_anchors = _period_role(normalized)
    anchors.update(anchor.replace("period.", "") for anchor in period_anchors)
    for pattern in (_FY, _FISCAL_YEAR, _QUARTER, _YEAR):
        occupied.extend(match.span() for match in pattern.finditer(normalized))
    for match in re.finditer(r"(?<![0-9a-z-])([0-9][0-9,]*(?:\.[0-9]+)?)(?![0-9a-z-])", normalized):
        if any(match.start() < end and match.end() > start for start, end in occupied):
            continue
        anchors.add(f"number:{_normalized_number(match.group(1))}")
    for word, value in _NUMBER_WORDS.items():
        if re.search(rf"(?<![0-9a-z-]){word}(?![0-9a-z-])", normalized):
            anchors.add(f"number_word:{word}")
    return sorted(anchors)


__all__ = [
    "TypedProposition",
    "classify_package",
    "extract_typed_propositions",
    "generic_typed_material_anchors",
    "normalize_text",
]
