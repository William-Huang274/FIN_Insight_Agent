from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from functools import cached_property
import re
import unicodedata
from typing import Any, Sequence

from .dell_report_r14_common import canonical_digest, require, sha256_bytes
from .dell_report_r14_contracts import PROOF_STATES, RULE_IDS


GRAPH_SCHEMA_VERSION = "fin_ia_dell_03B_R14_event_argument_graph_v1_0"
PRICE_GRAPH_SCHEMA_VERSION = "fin_ia_dell_03B_R14_price_attachment_graph_v1_0"

_PUNCTUATION_CLASS_MAP = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
}

_MONEY_FULL = re.compile(
    r"(?:[$€£¥]\s*[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s*(?:million|billion|mn|bn))?"
    r"|(?:USD|EUR|GBP|JPY|US\$)\s*[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s*(?:million|billion|mn|bn))?"
    r"|[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:US\s+)?dollars?)",
    re.IGNORECASE,
)
_PERCENT_FULL = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)\s*%")
_NUMBER_FULL = re.compile(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_WORD_FULL = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", re.UNICODE)

_EVENT_TARGET_TERMS = {
    "DELL-RSQ-03A-TARGET-ASP": frozenset(
        {"cost", "offer", "price", "quote", "sale", "sell", "sold"}
    ),
    "DELL-RSQ-03A-TARGET-SUPPLIER-READTHROUGH": frozenset(
        {
            "alliance",
            "available",
            "collaborate",
            "deliver",
            "expand",
            "include",
            "partner",
            "provide",
            "ship",
            "supply",
            "team",
        }
    ),
    "DELL-RSQ-03A-TARGET-CAPACITY-RELEASE": frozenset(
        {"allocate", "available", "release", "reserve", "supply"}
    ),
    "DELL-RSQ-03A-TARGET-CAPACITY-UTILIZATION-YIELD": frozenset(
        {"achieve", "operate", "reach", "report", "run", "utilize", "yield"}
    ),
    "DELL-RSQ-03A-TARGET-HBM-SUPPLY": frozenset(
        {"allocate", "available", "deliver", "reserve", "ship", "supply"}
    ),
    "DELL-RSQ-03A-TARGET-UNITS": frozenset(
        {"deliver", "dispatch", "sell", "ship", "sold"}
    ),
}
_EVENT_TYPE_TERMS = {
    "Dell_configuration_or_delivery": frozenset({"configure", "deliver", "ship"}),
    "HBM_supply_state": frozenset(
        {"allocate", "available", "deliver", "reserve", "ship", "supply"}
    ),
    "capacity_allocation": frozenset(
        {"allocate", "available", "release", "reserve", "supply"}
    ),
    "delivery": frozenset({"available", "deliver", "provide", "ship", "supply"}),
    "observed_measurement": frozenset(
        {"achieve", "operate", "reach", "report", "run", "utilize", "yield"}
    ),
    "physical_unit_sale_or_shipment": frozenset(
        {"deliver", "dispatch", "sell", "ship", "sold"}
    ),
    "pricing": frozenset({"cost", "offer", "price", "quote", "sale", "sell", "sold"}),
    "relationship_or_delivery": frozenset(
        {
            "alliance",
            "available",
            "collaborate",
            "deliver",
            "expand",
            "include",
            "partner",
            "provide",
            "ship",
            "supply",
            "team",
        }
    ),
    "supplier_relationship": frozenset(
        {"alliance", "collaborate", "expand", "include", "partner", "team"}
    ),
}
_AUXILIARIES = frozenset(
    {
        "am", "are", "be", "been", "being", "can", "could", "did", "do",
        "does", "had", "has", "have", "is", "may", "might", "must", "shall",
        "should", "was", "were", "will", "would",
    }
)
_FINITE_SUFFIXES = ("ed", "en", "es", "ing", "s")
_IRREGULAR_FINITE = frozenset(
    {
        "became", "began", "bought", "brought", "built", "came", "did", "fell",
        "grew", "had", "made", "ran", "rose", "said", "sold", "took", "was",
        "went", "were", "won", "wrote",
    }
)
_NEGATION = frozenset({"no", "not", "never", "neither", "without"})
_FORWARD = frozenset({"expect", "expects", "expected", "plan", "plans", "will"})
_MODALS = frozenset({"can", "could", "may", "might", "must", "should", "would"})
_REPORTING_LEMMAS = frozenset(
    {
        "announce",
        "claim",
        "report",
        "say",
        "state",
    }
)
_REPORTING_OPERATOR_IDS = frozenset(
    f"OPERATOR::{re.sub(r'[^A-Z0-9]+', '_', row.upper()).strip('_')}"
    for row in _REPORTING_LEMMAS
)
_INACTIVE = frozenset(
    {"discontinue", "discontinued", "suspend", "suspended", "withdraw", "withdrawn"}
)
_STRUCTURAL_FUNCTION_WORDS = frozenset(
    {"a", "an", "as", "at", "by", "for", "from", "in", "of", "on", "the", "to", "with"}
)

ASP_SERVICE_BARRIER_R14 = (
    "service_support_finance_lease_freight_or_maintenance_total_is_not_hardware_price"
)
SUPPLIER_INCLUDE_BARRIER_R14 = (
    "non_relationship_include_context_is_not_supplier_relationship"
)
CAPACITY_GENERIC_SUPPLY_BARRIER_R14 = (
    "generic_supply_or_delivery_is_not_Dell_capacity_release"
)
CAPACITY_INDUSTRY_BARRIER_R14 = "industry_capacity_is_not_Dell_allocation"
YIELD_TARGET_BARRIER_R14 = (
    "plan_goal_capability_or_industry_figure_is_not_observed_issuer_measure"
)
HBM_DOCUMENT_BARRIER_R14 = (
    "document_brochure_guidance_or_announcement_is_not_Dell_supply_state"
)
HBM_GENERIC_BARRIER_R14 = (
    "generic_HBM_market_or_supplier_relationship_is_not_Dell_supply_state"
)
UNITS_PROJECT_BARRIER_R14 = (
    "project_node_install_customer_or_noncompany_count_is_not_Dell_company_units"
)
UNITS_VALUE_BARRIER_R14 = "revenue_or_order_value_is_not_physical_units"


def normalize_structural_text_r14(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(_PUNCTUATION_CLASS_MAP.get(character, character) for character in normalized)


def _identity_fragment(value: str) -> str:
    fragment = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return fragment.upper()


def canonical_semantic_identity_ids_r14(
    mention_type: str, normalized_value: str
) -> tuple[str, ...]:
    normalized = normalize_structural_text_r14(normalized_value).strip()
    if mention_type == "entity":
        base = re.sub(r"(?:'s|s')$", "", normalized).strip()
        fragment = _identity_fragment(base)
        return (f"ENTITY::{fragment}",) if fragment else ()
    if mention_type == "product_or_hardware":
        words = tuple(re.findall(r"[^\W_]+", normalized, re.UNICODE))
        fragments = {_identity_fragment(normalized), *(_identity_fragment(row) for row in words)}
        return tuple(sorted(f"PRODUCT::{row}" for row in fragments if row))
    if mention_type == "price":
        return ("MEASURE::MONEY",)
    if mention_type == "period":
        return ("MEASURE::PERIOD",)
    if mention_type == "quantity":
        return ("MEASURE::NUMBER",)
    if mention_type == "quantity_or_percent":
        return ("MEASURE::PERCENT_OR_NUMBER",)
    if mention_type in {"nominal_head", "bundle"}:
        fragment = _identity_fragment(normalized)
        prefix = "BUNDLE" if mention_type == "bundle" else "NOMINAL_HEAD"
        return (f"{prefix}::{fragment}",) if fragment else ()
    return ()


def canonical_predicate_operator_identity_ids_r14(
    normalized_value: str,
) -> tuple[str, ...]:
    """Return surface-free, mechanically recomputable predicate operators.

    The target compiler consumes these typed identities instead of reading the
    predicate surface.  Keeping the small morphology transform here also lets
    the graph validator independently recompute the identities that the parser
    emitted.
    """
    words = re.findall(
        r"[^\W_]+(?:[-'][^\W_]+)*",
        normalize_structural_text_r14(normalized_value),
        re.UNICODE,
    )
    operators: set[str] = set()
    irregular = {"sold": "sell", "said": "say", "ran": "run"}
    for word in words:
        candidates = {word}
        if word in irregular:
            candidates.add(irregular[word])
        for suffix in ("ied", "ing", "ed", "en", "es", "s"):
            if not word.endswith(suffix) or len(word) <= len(suffix) + 2:
                continue
            stem = word[: -len(suffix)]
            candidates.add(stem)
            if suffix == "ied":
                candidates.add(stem + "y")
            if suffix in {"ing", "ed"} and len(stem) >= 2 and stem[-1] == stem[-2]:
                candidates.add(stem[:-1])
            candidates.add(stem + "e")
        operators.update(
            f"OPERATOR::{_identity_fragment(candidate)}"
            for candidate in candidates
            if _identity_fragment(candidate)
        )
    return tuple(sorted(operators))


def _lemma_candidates_r14(value: str) -> set[str]:
    candidates = {value}
    irregular = {"sold": "sell", "said": "say", "ran": "run"}
    if value in irregular:
        candidates.add(irregular[value])
    for suffix in ("ied", "ing", "ed", "en", "es", "s"):
        if not value.endswith(suffix) or len(value) <= len(suffix) + 2:
            continue
        stem = value[: -len(suffix)]
        candidates.add(stem)
        if suffix == "ied":
            candidates.add(stem + "y")
        if suffix in {"ing", "ed"} and len(stem) >= 2 and stem[-1] == stem[-2]:
            candidates.add(stem[:-1])
        candidates.add(stem + "e")
    return candidates


def canonical_event_semantics_r14(words: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lemmas: set[str] = set()
    for word in words:
        lemmas.update(_lemma_candidates_r14(word))
    labels = tuple(
        sorted(
            target_id
            for target_id, terms in _EVENT_TARGET_TERMS.items()
            if lemmas.intersection(terms)
        )
    )
    event_types = tuple(
        sorted(
            event_type
            for event_type, terms in _EVENT_TYPE_TERMS.items()
            if lemmas.intersection(terms)
        )
    )
    return labels, event_types or ("unknown",)


def canonical_predicate_proof_type_r14(predicate_normalized: str) -> str | None:
    words = tuple(
        re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", predicate_normalized, re.UNICODE)
    )
    if not words:
        return None
    if len(words) >= 2 and words[0] in _AUXILIARIES:
        return "AUXILIARY-PREDICATE-CANDIDATE"
    word = words[-1]
    if any(
        word.endswith(suffix) and len(word) > len(suffix) + 2
        for suffix in _FINITE_SUFFIXES
    ):
        return "MORPHOLOGICAL-PREDICATE-CANDIDATE"
    if word in _IRREGULAR_FINITE:
        return "IRREGULAR-FINITE-PREDICATE-CANDIDATE"
    return None


def classify_token_surface_r14(raw: str) -> str:
    normalized = normalize_structural_text_r14(raw)
    if _MONEY_FULL.fullmatch(normalized):
        return "MONEY"
    if _PERCENT_FULL.fullmatch(normalized):
        return "PERCENT"
    if _NUMBER_FULL.fullmatch(normalized):
        return "NUMBER"
    if _WORD_FULL.fullmatch(normalized):
        return "WORD"
    if normalized.isspace():
        return "WHITESPACE"
    if len(raw) == 1:
        return "PUNCT"
    return "MALFORMED"


@dataclass(frozen=True)
class LocalScopeNodeR14:
    scope_type: str
    document_span: tuple[int, int]
    content_span: tuple[int, int]
    parent_scope_id: str | None
    opener_span: tuple[int, int] | None
    closer_span: tuple[int, int] | None
    depth: int
    proof_state: str

    @cached_property
    def node_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def scope_id(self) -> str:
        return f"LOCAL-SCOPE::R14::{self.node_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "scope_type": self.scope_type,
            "document_span": list(self.document_span),
            "content_span": list(self.content_span),
            "parent_scope_id": self.parent_scope_id,
            "opener_span": list(self.opener_span) if self.opener_span else None,
            "closer_span": list(self.closer_span) if self.closer_span else None,
            "depth": self.depth,
            "proof_state": self.proof_state,
        }

    def as_dict(self) -> dict[str, Any]:
        return {"scope_id": self.scope_id, **self._body(), "node_digest": self.node_digest}


@dataclass(frozen=True)
class TokenR14:
    kind: str
    raw: str
    normalized: str
    start: int
    end: int
    local_scope_id: str

    @cached_property
    def token_digest(self) -> str:
        return canonical_digest(
            {
                "kind": self.kind,
                "raw_sha256": sha256_bytes(self.raw.encode("utf-8")),
                "normalized": self.normalized,
                "span": [self.start, self.end],
                "local_scope_id": self.local_scope_id,
            }
        )

    @cached_property
    def token_id(self) -> str:
        return f"TOKEN::R14::{self.token_digest[:24].upper()}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "token_id": self.token_id,
            "kind": self.kind,
            "raw": self.raw,
            "normalized": self.normalized,
            "span": [self.start, self.end],
            "local_scope_id": self.local_scope_id,
            "raw_bytes_sha256": sha256_bytes(self.raw.encode("utf-8")),
            "token_digest": self.token_digest,
        }


@dataclass(frozen=True)
class ProofRecordR14:
    rule_id: str
    state: str
    conclusion: str
    premise_spans: tuple[tuple[int, int], ...]
    premise_edge_ids: tuple[str, ...] = ()
    premise_node_ids: tuple[str, ...] = ()

    @cached_property
    def proof_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def proof_id(self) -> str:
        return f"PROOF::R14::{self.proof_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "state": self.state,
            "conclusion": self.conclusion,
            "premise_spans": [list(value) for value in self.premise_spans],
            "premise_edge_ids": list(self.premise_edge_ids),
            "premise_node_ids": list(self.premise_node_ids),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"proof_id": self.proof_id, **self._body(), "proof_digest": self.proof_digest}


@dataclass(frozen=True)
class MentionNodeR14:
    mention_type: str
    raw_value: str
    normalized_value: str
    start: int
    end: int
    type_proof_rule_id: str
    local_scope_id: str
    proof_state: str = "PROVED"
    semantic_identity_ids: tuple[str, ...] = ()

    @cached_property
    def node_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def mention_id(self) -> str:
        return f"MENTION::R14::{self.node_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "mention_type": self.mention_type,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "span": [self.start, self.end],
            "type_proof_rule_id": self.type_proof_rule_id,
            "local_scope_id": self.local_scope_id,
            "proof_state": self.proof_state,
            "semantic_identity_ids": list(self.semantic_identity_ids),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"mention_id": self.mention_id, **self._body(), "node_digest": self.node_digest}


def _reporting_token_r14(token: TokenR14) -> bool:
    if token.kind != "WORD":
        return False
    return bool(_lemma_candidates_r14(token.normalized).intersection(_REPORTING_LEMMAS))


def assertion_attribution_signal_tokens_r14(
    tokens: Sequence[TokenR14],
) -> tuple[tuple[TokenR14, ...], bool]:
    reporting = tuple(token for token in tokens if _reporting_token_r14(token))
    according_present = any(
        token.kind == "WORD" and token.normalized == "according" for token in tokens
    )
    return reporting, according_present


def _entity_identities_in_span_r14(
    mentions: Sequence[MentionNodeR14],
    *,
    local_scope_id: str,
    span: tuple[int, int],
) -> tuple[str, ...]:
    identities = {
        identity
        for mention in mentions
        if mention.mention_type == "entity"
        and mention.local_scope_id == local_scope_id
        and span[0] <= mention.start
        and mention.end <= span[1]
        for identity in mention.semantic_identity_ids
        if identity.startswith("ENTITY::")
    }
    return tuple(sorted(identities))


def canonical_assertion_speech_mode_r14(
    *,
    predicate_span: tuple[int, int],
    document_span: tuple[int, int],
    sentence_span: tuple[int, int],
    local_scope_id: str,
    assertion_owner_identity_ids: Sequence[str],
    tokens: Sequence[TokenR14],
    mentions: Sequence[MentionNodeR14],
    reporting_tokens: Sequence[TokenR14] | None = None,
    according_present: bool | None = None,
) -> str:
    """Classify the assertion source from structural attribution scope.

    The factual actor and the assertion source are deliberately separate.  A
    third party can attribute a proposition whose actor is Dell; that must not
    become issuer-reported merely because Dell is the embedded event subject.
    The closed forms are a reporting head governing a following complement
    (including a colon), a trailing reporting clause, and ``according to``.
    """

    reporting_tokens = (
        tuple(reporting_tokens)
        if reporting_tokens is not None
        else tuple(token for token in tokens if _reporting_token_r14(token))
    )
    according_present = (
        bool(according_present)
        if according_present is not None
        else any(
            token.kind == "WORD" and token.normalized == "according"
            for token in tokens
        )
    )
    if not reporting_tokens and not according_present:
        return "direct_or_unspecified"

    sentence_tokens = tuple(
        token
        for token in tokens
        if token.local_scope_id == local_scope_id
        and sentence_span[0] <= token.start
        and token.end <= sentence_span[1]
    )
    words = tuple(token for token in sentence_tokens if token.kind == "WORD")
    owner_ids = {
        value for value in assertion_owner_identity_ids if value.startswith("ENTITY::")
    }

    predicate_reporting = any(
        predicate_span[0] <= token.start
        and token.end <= predicate_span[1]
        and _reporting_token_r14(token)
        for token in words
    )
    if predicate_reporting:
        return "issuer_reported" if owner_ids else "reported_speech"

    # ``according to <source>`` is an explicit attribution complement whether
    # it precedes or follows the proposition.  The source is issuer-owned only
    # when a typed entity in that complement matches the factual actor.
    for index, token in enumerate(words[:-1]):
        if token.normalized != "according" or words[index + 1].normalized != "to":
            continue
        complement_start = words[index + 1].end
        complement_end = sentence_span[1]
        if token.start < predicate_span[0]:
            complement_end = predicate_span[0]
        source_ids = set(
            _entity_identities_in_span_r14(
                mentions,
                local_scope_id=local_scope_id,
                span=(complement_start, complement_end),
            )
        )
        return (
            "issuer_reported"
            if owner_ids and owner_ids.intersection(source_ids)
            else "reported_speech"
        )

    reporting_tokens = tuple(
        token
        for token in reporting_tokens
        if sentence_span[0] <= token.start
        and token.end <= sentence_span[1]
        and token.local_scope_id == local_scope_id
    )
    prefix = tuple(token for token in reporting_tokens if token.end <= predicate_span[0])
    for trigger in reversed(prefix):
        between = tuple(
            token
            for token in sentence_tokens
            if trigger.end <= token.start and token.end <= predicate_span[0]
        )
        has_colon = any(token.kind == "PUNCT" and token.normalized == ":" for token in between)
        has_coordinator = any(
            token.kind == "WORD"
            and token.normalized in {"and", "but", "or", "then", "whereas", "while", "yet"}
            for token in between
        )
        # A reporting head governs a following complement until a coordinator;
        # a colon is an explicit scope opener and overrides that barrier.
        if has_coordinator and not has_colon:
            continue
        source_ids = set(
            _entity_identities_in_span_r14(
                mentions,
                local_scope_id=local_scope_id,
                span=(sentence_span[0], trigger.start),
            )
        )
        return (
            "issuer_reported"
            if owner_ids and owner_ids.intersection(source_ids)
            else "reported_speech"
        )

    # A reporting head after the proposition is scoped backward only when a
    # punctuation boundary makes it a trailing attribution clause.
    suffix = tuple(token for token in reporting_tokens if token.start >= document_span[1])
    for trigger in suffix:
        between = tuple(
            token
            for token in sentence_tokens
            if predicate_span[1] <= token.start and token.end <= trigger.start
        )
        if not any(
            token.kind == "PUNCT" and token.normalized in {",", ":", ";"}
            for token in between
        ):
            continue
        source_ids = set(
            _entity_identities_in_span_r14(
                mentions,
                local_scope_id=local_scope_id,
                span=(predicate_span[1], trigger.start),
            )
        )
        return (
            "issuer_reported"
            if owner_ids and owner_ids.intersection(source_ids)
            else "reported_speech"
        )
    return "direct_or_unspecified"


def canonical_event_inference_barrier_ids_r14(
    *,
    tokens: Sequence[TokenR14],
    mentions: Sequence[MentionNodeR14],
    predicate_operator_ids: Sequence[str],
    event_types: Sequence[str],
) -> tuple[str, ...]:
    """Return typed, compiler-consumable negative inference witnesses.

    These are structural context classes, not a target-word denylist.  Each
    class requires an event type/operator plus the corresponding nominal or
    measure topology.  The target topology decides which classes are material
    for a target by listing the same identifier in ``forbidden_inference``.
    """

    words = {token.normalized for token in tokens if token.kind == "WORD"}
    operators = set(predicate_operator_ids)
    types = set(event_types)
    has_product = any(
        mention.mention_type == "product_or_hardware" for mention in mentions
    )
    has_quantity = any(
        mention.mention_type in {"quantity", "quantity_or_percent"}
        for mention in mentions
    )
    barriers: set[str] = set()

    if "pricing" in types and words.intersection(
        {"finance", "freight", "lease", "maintenance", "service", "support"}
    ):
        barriers.add(ASP_SERVICE_BARRIER_R14)

    include_operator = bool(
        operators.intersection({"OPERATOR::INCLUDE", "OPERATOR::INCLUDED"})
    )
    relationship_context = bool(
        words.intersection(
            {
                "alliance",
                "collaboration",
                "component",
                "ecosystem",
                "partner",
                "partnership",
                "supplier",
            }
        )
    )
    if include_operator and not relationship_context:
        barriers.add(SUPPLIER_INCLUDE_BARRIER_R14)

    if "capacity_allocation" in types:
        if "OPERATOR::SUPPLY" in operators and not operators.intersection(
            {
                "OPERATOR::ALLOCATE",
                "OPERATOR::AVAILABLE",
                "OPERATOR::RELEASE",
                "OPERATOR::RESERVE",
            }
        ):
            barriers.add(CAPACITY_GENERIC_SUPPLY_BARRIER_R14)
        if words.intersection({"global", "industry", "market", "sector"}):
            barriers.add(CAPACITY_INDUSTRY_BARRIER_R14)

    if "observed_measurement" in types and has_quantity and words.intersection(
        {
            "capability",
            "forecast",
            "goal",
            "plan",
            "planned",
            "target",
        }
    ):
        barriers.add(YIELD_TARGET_BARRIER_R14)

    hbm_context = any(
        any(identity.startswith("PRODUCT::HBM") for identity in mention.semantic_identity_ids)
        for mention in mentions
    )
    if hbm_context and words.intersection(
        {"announcement", "brochure", "document", "guidance", "presentation", "release"}
    ):
        barriers.add(HBM_DOCUMENT_BARRIER_R14)
    if hbm_context and words.intersection({"global", "industry", "market"}):
        barriers.add(HBM_GENERIC_BARRIER_R14)

    if (
        "physical_unit_sale_or_shipment" in types
        and has_product
        and has_quantity
        and words.intersection(
            {"customer", "deployment", "install", "installation", "project"}
        )
    ):
        barriers.add(UNITS_PROJECT_BARRIER_R14)
    if "physical_unit_sale_or_shipment" in types and words.intersection(
        {"order", "revenue", "value"}
    ):
        barriers.add(UNITS_VALUE_BARRIER_R14)
    return tuple(sorted(barriers))


@dataclass(frozen=True)
class EventNodeR14:
    event_scope_id: str
    local_scope_id: str
    document_span: tuple[int, int]
    sentence_span: tuple[int, int]
    clause_span: tuple[int, int]
    predicate_span: tuple[int, int]
    predicate_surface: str
    predicate_normalized: str
    predicate_proof_type: str
    semantic_labels: tuple[str, ...]
    event_types: tuple[str, ...]
    subject_state: str
    assertion_owner_mention_id: str | None
    candidate_subject_mention_ids: tuple[str, ...]
    polarity: str
    modality: str
    actuality: str
    lifecycle: str
    speech_mode: str
    assertion_owner: str | None
    ambiguities: tuple[str, ...]
    limitations: tuple[str, ...]
    semantic_operator_ids: tuple[str, ...] = ()
    inference_barrier_ids: tuple[str, ...] = ()

    @cached_property
    def node_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def event_id(self) -> str:
        return f"EVENT::R14::{self.node_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "event_scope_id": self.event_scope_id,
            "local_scope_id": self.local_scope_id,
            "document_span": list(self.document_span),
            "sentence_span": list(self.sentence_span),
            "clause_span": list(self.clause_span),
            "predicate_head_span": list(self.predicate_span),
            "predicate_surface": self.predicate_surface,
            "predicate_normalized": self.predicate_normalized,
            "predicate_proof_type": self.predicate_proof_type,
            "semantic_labels": list(self.semantic_labels),
            "event_types": list(self.event_types),
            "subject_state": self.subject_state,
            "assertion_owner_mention_id": self.assertion_owner_mention_id,
            "candidate_subject_mention_ids": list(self.candidate_subject_mention_ids),
            "polarity": self.polarity,
            "modality": self.modality,
            "actuality": self.actuality,
            "lifecycle": self.lifecycle,
            "speech_mode": self.speech_mode,
            "assertion_owner": self.assertion_owner,
            "ambiguities": list(self.ambiguities),
            "limitations": list(self.limitations),
            "semantic_operator_ids": list(self.semantic_operator_ids),
            "inference_barrier_ids": list(self.inference_barrier_ids),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"event_id": self.event_id, **self._body(), "node_digest": self.node_digest}


@dataclass(frozen=True)
class RoleEdgeR14:
    event_scope_id: str
    event_id: str
    role: str
    mention_id: str
    proof_rule_id: str
    proof_state: str
    evidence_spans: tuple[tuple[int, int], ...]
    premise_proof_ids: tuple[str, ...] = ()

    @cached_property
    def edge_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def edge_id(self) -> str:
        return f"ROLE-EDGE::R14::{self.edge_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "event_scope_id": self.event_scope_id,
            "event_id": self.event_id,
            "role": self.role,
            "mention_id": self.mention_id,
            "proof_rule_id": self.proof_rule_id,
            "proof_state": self.proof_state,
            "evidence_spans": [list(value) for value in self.evidence_spans],
            "premise_proof_ids": list(self.premise_proof_ids),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, **self._body(), "edge_digest": self.edge_digest}


@dataclass(frozen=True)
class SubjectShareEdgeR14:
    source_subject_mention_id: str
    left_event_id: str
    right_event_id: str
    coordinator_span: tuple[int, int]
    proof_rule_id: str = "G23-SUBJECT-INHERIT"
    destination_role: str = "actor"
    cardinality: str = "one_subject_one_left_event_one_right_event_one_actor"

    @cached_property
    def edge_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def edge_id(self) -> str:
        return f"SUBJECT-SHARE::R14::{self.edge_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "source_subject_mention_id": self.source_subject_mention_id,
            "left_event_id": self.left_event_id,
            "right_event_id": self.right_event_id,
            "destination_role": self.destination_role,
            "coordinator_span": list(self.coordinator_span),
            "proof_rule_id": self.proof_rule_id,
            "cardinality": self.cardinality,
        }

    def as_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, **self._body(), "edge_digest": self.edge_digest}


@dataclass(frozen=True)
class TypedTargetBridgeEdgeR14:
    source_event_id: str
    destination_event_id: str
    bridge_type: str
    shared_semantic_identity_ids: tuple[str, ...]
    direction: str
    proof_rule_id: str
    proof_state: str
    premise_edge_ids: tuple[str, ...]

    @cached_property
    def edge_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def edge_id(self) -> str:
        return f"TARGET-BRIDGE::R14::{self.edge_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "source_event_id": self.source_event_id,
            "destination_event_id": self.destination_event_id,
            "bridge_type": self.bridge_type,
            "shared_semantic_identity_ids": list(
                self.shared_semantic_identity_ids
            ),
            "direction": self.direction,
            "proof_rule_id": self.proof_rule_id,
            "proof_state": self.proof_state,
            "premise_edge_ids": list(self.premise_edge_ids),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, **self._body(), "edge_digest": self.edge_digest}


@dataclass(frozen=True)
class TemporalScopeEdgeR14:
    period_mention_id: str
    event_id: str
    scope_type: str
    proof_rule_id: str
    proof_state: str
    evidence_spans: tuple[tuple[int, int], ...]
    premise_proof_ids: tuple[str, ...] = ()

    @cached_property
    def edge_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def edge_id(self) -> str:
        return f"TEMPORAL-EDGE::R14::{self.edge_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "period_mention_id": self.period_mention_id,
            "event_id": self.event_id,
            "scope_type": self.scope_type,
            "proof_rule_id": self.proof_rule_id,
            "proof_state": self.proof_state,
            "evidence_spans": [list(value) for value in self.evidence_spans],
            "premise_proof_ids": list(self.premise_proof_ids),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, **self._body(), "edge_digest": self.edge_digest}


@dataclass(frozen=True)
class NominalEdgeR14:
    source_node_id: str
    source_node_type: str
    destination_node_id: str
    destination_node_type: str
    direction: str
    relation: str
    rule_id: str
    proof_state: str
    spans: tuple[tuple[int, int], ...]
    precedence: int

    @cached_property
    def edge_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def edge_id(self) -> str:
        return f"NOMINAL-EDGE::R14::{self.edge_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "source_node_type": self.source_node_type,
            "destination_node_id": self.destination_node_id,
            "destination_node_type": self.destination_node_type,
            "direction": self.direction,
            "relation": self.relation,
            "rule_id": self.rule_id,
            "proof_state": self.proof_state,
            "spans": [list(value) for value in self.spans],
            "precedence": self.precedence,
        }

    def as_dict(self) -> dict[str, Any]:
        return {"edge_id": self.edge_id, **self._body(), "edge_digest": self.edge_digest}


@dataclass(frozen=True)
class PricePathProofR14:
    event_id: str
    product_mention_ids: tuple[str, ...]
    price_mention_ids: tuple[str, ...]
    governing_head_mention_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    rule_id: str
    state: str
    family: str | None
    competing_head_ids: tuple[str, ...]
    competing_price_ids: tuple[str, ...]
    connector_surface_provenance: tuple[str, ...]
    limitations: tuple[str, ...]

    @cached_property
    def proof_digest(self) -> str:
        return canonical_digest(self._body())

    @cached_property
    def proof_id(self) -> str:
        return f"PRICE-PROOF::R14::{self.proof_digest[:24].upper()}"

    def _body(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "product_mention_ids": list(self.product_mention_ids),
            "price_mention_ids": list(self.price_mention_ids),
            "governing_head_mention_ids": list(self.governing_head_mention_ids),
            "edge_ids": list(self.edge_ids),
            "rule_id": self.rule_id,
            "state": self.state,
            "family": self.family,
            "competing_head_ids": list(self.competing_head_ids),
            "competing_price_ids": list(self.competing_price_ids),
            "connector_surface_provenance": list(self.connector_surface_provenance),
            "limitations": list(self.limitations),
        }

    def as_dict(self) -> dict[str, Any]:
        return {"proof_id": self.proof_id, **self._body(), "proof_digest": self.proof_digest}


@dataclass(frozen=True)
class EventArgumentGraphR14:
    raw_text: str
    grammar_result_digest: str
    graph_type_registry_digest: str
    local_scopes: tuple[LocalScopeNodeR14, ...]
    tokens: tuple[TokenR14, ...]
    events: tuple[EventNodeR14, ...]
    mentions: tuple[MentionNodeR14, ...]
    role_edges: tuple[RoleEdgeR14, ...]
    subject_share_edges: tuple[SubjectShareEdgeR14, ...]
    temporal_edges: tuple[TemporalScopeEdgeR14, ...]
    proofs: tuple[ProofRecordR14, ...]
    target_bridge_edges: tuple[TypedTargetBridgeEdgeR14, ...] = ()

    @cached_property
    def raw_text_sha256(self) -> str:
        return sha256_bytes(self.raw_text.encode("utf-8"))

    @cached_property
    def graph_digest(self) -> str:
        return canonical_digest(self._body())

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": GRAPH_SCHEMA_VERSION,
            "raw_text_sha256": self.raw_text_sha256,
            "grammar_result_digest": self.grammar_result_digest,
            "graph_type_registry_digest": self.graph_type_registry_digest,
            "local_scopes": [row.as_dict() for row in self.local_scopes],
            "tokens": [row.as_dict() for row in self.tokens],
            "events": [row.as_dict() for row in self.events],
            "mentions": [row.as_dict() for row in self.mentions],
            "role_edges": [row.as_dict() for row in self.role_edges],
            "subject_share_edges": [row.as_dict() for row in self.subject_share_edges],
            "temporal_edges": [row.as_dict() for row in self.temporal_edges],
            "proofs": [row.as_dict() for row in self.proofs],
            "target_bridge_edges": [
                row.as_dict() for row in self.target_bridge_edges
            ],
        }

    def as_dict(self, *, include_raw_text: bool = True) -> dict[str, Any]:
        output = self._body()
        if include_raw_text:
            output["raw_text"] = self.raw_text
        output["graph_digest"] = self.graph_digest
        return output


@dataclass(frozen=True)
class PriceAttachmentGraphR14:
    event_graph_digest: str
    nodes: tuple[MentionNodeR14, ...]
    edges: tuple[NominalEdgeR14, ...]
    proofs: tuple[PricePathProofR14, ...]

    @cached_property
    def graph_digest(self) -> str:
        return canonical_digest(self._body())

    def _body(self) -> dict[str, Any]:
        return {
            "schema_version": PRICE_GRAPH_SCHEMA_VERSION,
            "event_graph_digest": self.event_graph_digest,
            "nodes": [row.as_dict() for row in self.nodes],
            "edges": [row.as_dict() for row in self.edges],
            "proofs": [row.as_dict() for row in self.proofs],
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self._body(), "graph_digest": self.graph_digest}


ROLE_MENTION_TYPES = {
    "predicate": {"predicate"},
    "actor": {"entity"},
    "seller": {"entity"},
    "shipper": {"entity"},
    "recipient": {"entity", "product_or_hardware"},
    "beneficiary": {"entity"},
    "counterparty": {"entity"},
    "owner": {"entity"},
    "supplier": {"entity"},
    "product_supplier": {"entity"},
    "object": {"product_or_hardware", "nominal_head", "bundle"},
    "price": {"price"},
    "quantity": {"quantity"},
    "measure": {"quantity", "quantity_or_percent"},
    "period": {"period"},
}


def _span_valid(span: tuple[int, int], length: int) -> bool:
    return 0 <= span[0] < span[1] <= length


def validate_event_argument_graph_r14(graph: EventArgumentGraphR14) -> None:
    text_length = len(graph.raw_text)
    require(bool(graph.grammar_result_digest), "R14_graph_grammar_binding_missing")
    require(bool(graph.graph_type_registry_digest), "R14_graph_registry_binding_missing")
    scope_by_id = {row.scope_id: row for row in graph.local_scopes}
    require(len(scope_by_id) == len(graph.local_scopes), "R14_graph_scope_ID_collision")
    roots = [row for row in graph.local_scopes if row.parent_scope_id is None]
    require(len(roots) == 1, "R14_graph_root_scope_invalid")
    require(
        tuple(graph.local_scopes)
        == tuple(
            sorted(
                graph.local_scopes,
                key=lambda row: (
                    row.document_span,
                    row.depth,
                    row.scope_type,
                    row.node_digest,
                ),
            )
        ),
        "R14_graph_scope_canonical_order_invalid",
    )
    for scope in graph.local_scopes:
        require(_span_valid(scope.document_span, max(text_length, 1)) or (text_length == 0 and scope.document_span == (0, 0)), "R14_graph_scope_span_invalid")
        require(0 <= scope.content_span[0] <= scope.content_span[1] <= text_length, "R14_graph_scope_content_span_invalid")
        require(scope.proof_state in PROOF_STATES, "R14_graph_scope_state_invalid")
        if scope.parent_scope_id is not None:
            require(scope.parent_scope_id in scope_by_id, "R14_graph_scope_parent_orphan")
            parent = scope_by_id[scope.parent_scope_id]
            require(
                parent.document_span[0] <= scope.document_span[0]
                and scope.document_span[1] <= parent.document_span[1]
                and scope.depth == parent.depth + 1,
                "R14_graph_scope_parent_containment_invalid",
            )
        seen_scopes: set[str] = set()
        cursor_scope: LocalScopeNodeR14 | None = scope
        while cursor_scope is not None:
            require(
                cursor_scope.scope_id not in seen_scopes,
                "R14_graph_scope_parent_cycle",
            )
            seen_scopes.add(cursor_scope.scope_id)
            cursor_scope = (
                scope_by_id[cursor_scope.parent_scope_id]
                if cursor_scope.parent_scope_id is not None
                else None
            )

    require(
        tuple(graph.tokens) == tuple(sorted(graph.tokens, key=lambda row: (row.start, row.end, row.kind, row.token_digest))),
        "R14_graph_token_canonical_order_invalid",
    )
    cursor = 0
    for token in graph.tokens:
        require(token.start == cursor and token.end > token.start, "R14_graph_token_gap_overlap_or_empty")
        require(token.end <= text_length, "R14_graph_token_span_out_of_bounds")
        require(token.raw == graph.raw_text[token.start : token.end], "R14_graph_token_raw_slice_mismatch")
        require(token.normalized == normalize_structural_text_r14(token.raw), "R14_graph_token_normalization_mismatch")
        require(token.kind == classify_token_surface_r14(token.raw), "R14_graph_token_kind_mismatch")
        require(token.local_scope_id in scope_by_id, "R14_graph_token_scope_orphan")
        cursor = token.end
    require(cursor == text_length, "R14_graph_token_stream_not_lossless")

    mention_by_id = {row.mention_id: row for row in graph.mentions}
    event_by_id = {row.event_id: row for row in graph.events}
    proof_by_id = {row.proof_id: row for row in graph.proofs}
    graph_edge_ids = {
        row.edge_id
        for row in (
            *graph.role_edges,
            *graph.subject_share_edges,
            *graph.temporal_edges,
            *graph.target_bridge_edges,
        )
    }
    require(len(mention_by_id) == len(graph.mentions), "R14_graph_mention_ID_collision")
    require(len(event_by_id) == len(graph.events), "R14_graph_event_ID_collision")
    require(len(proof_by_id) == len(graph.proofs), "R14_graph_proof_ID_collision")
    mention_ids = set(mention_by_id)
    graph_node_ids = mention_ids | set(event_by_id)
    proof_ids = set(proof_by_id)
    require(
        tuple(graph.proofs)
        == tuple(
            sorted(
                graph.proofs,
                key=lambda row: (
                    row.premise_spans,
                    row.rule_id,
                    row.conclusion,
                    row.proof_digest,
                ),
            )
        ),
        "R14_graph_proof_canonical_order_invalid",
    )
    require(tuple(graph.mentions) == tuple(sorted(graph.mentions, key=lambda row: (row.start, row.end, row.mention_type, row.type_proof_rule_id, row.node_digest))), "R14_graph_mention_canonical_order_invalid")
    require(tuple(graph.events) == tuple(sorted(graph.events, key=lambda row: (row.document_span, row.predicate_span, row.event_scope_id, row.node_digest))), "R14_graph_event_canonical_order_invalid")
    for mention in graph.mentions:
        require(_span_valid((mention.start, mention.end), text_length), "R14_graph_mention_span_out_of_bounds")
        require(mention.raw_value == graph.raw_text[mention.start : mention.end], "R14_graph_mention_raw_slice_mismatch")
        require(mention.normalized_value == normalize_structural_text_r14(mention.raw_value), "R14_graph_mention_normalization_mismatch")
        require(mention.local_scope_id in scope_by_id, "R14_graph_mention_scope_orphan")
        require(mention.proof_state in PROOF_STATES, "R14_graph_mention_state_invalid")
        require(
            tuple(sorted(set(mention.semantic_identity_ids)))
            == mention.semantic_identity_ids,
            "R14_graph_mention_semantic_identity_canonical_invalid",
        )
        if mention.mention_type != "predicate":
            require(
                mention.semantic_identity_ids
                == canonical_semantic_identity_ids_r14(
                    mention.mention_type, mention.normalized_value
                ),
                "R14_graph_mention_semantic_identity_recomputation_failed",
            )
    tokens_by_scope: dict[str, list[TokenR14]] = {}
    mentions_by_scope: dict[str, list[MentionNodeR14]] = {}
    for token in graph.tokens:
        tokens_by_scope.setdefault(token.local_scope_id, []).append(token)
    for mention in graph.mentions:
        mentions_by_scope.setdefault(mention.local_scope_id, []).append(mention)
    token_starts_by_scope = {
        key: [row.start for row in rows] for key, rows in tokens_by_scope.items()
    }
    mention_starts_by_scope = {
        key: [row.start for row in rows] for key, rows in mentions_by_scope.items()
    }
    predicate_mentions_by_scope_span: dict[
        tuple[str, tuple[int, int]], tuple[MentionNodeR14, ...]
    ] = {}
    predicate_rows: dict[
        tuple[str, tuple[int, int]], list[MentionNodeR14]
    ] = {}
    for mention in graph.mentions:
        if mention.mention_type == "predicate":
            predicate_rows.setdefault(
                (mention.local_scope_id, (mention.start, mention.end)), []
            ).append(mention)
    predicate_mentions_by_scope_span = {
        key: tuple(rows) for key, rows in predicate_rows.items()
    }
    event_tokens_by_id: dict[str, tuple[TokenR14, ...]] = {}
    event_mentions_by_id: dict[str, tuple[MentionNodeR14, ...]] = {}
    event_words_by_id: dict[str, tuple[str, ...]] = {}
    # Recompute content-derived event identities before traversing any proof
    # references.  Otherwise a forged identity changes the content-addressed
    # event ID and is reported only as a downstream orphan.
    for event in graph.events:
        require(
            event.semantic_operator_ids
            == canonical_predicate_operator_identity_ids_r14(
                event.predicate_normalized
            ),
            "R14_graph_event_operator_identity_recomputation_failed",
        )
        require(
            event.local_scope_id in scope_by_id
            and _span_valid(event.document_span, text_length)
            and _span_valid(event.predicate_span, text_length)
            and event.document_span[0] <= event.predicate_span[0]
            and event.predicate_span[1] <= event.document_span[1]
            and event.predicate_surface
            == graph.raw_text[event.predicate_span[0] : event.predicate_span[1]]
            and event.predicate_normalized
            == normalize_structural_text_r14(event.predicate_surface),
            "R14_graph_event_preproof_surface_recomputation_failed",
        )
        scoped_tokens = tokens_by_scope.get(event.local_scope_id, [])
        token_start_index = bisect_left(
            token_starts_by_scope.get(event.local_scope_id, []),
            event.document_span[0],
        )
        bounded_tokens: list[TokenR14] = []
        for token in scoped_tokens[token_start_index:]:
            if token.start >= event.document_span[1]:
                break
            if token.end <= event.document_span[1]:
                bounded_tokens.append(token)
        scoped_mentions = mentions_by_scope.get(event.local_scope_id, [])
        mention_start_index = bisect_left(
            mention_starts_by_scope.get(event.local_scope_id, []),
            event.document_span[0],
        )
        bounded_mentions: list[MentionNodeR14] = []
        for mention in scoped_mentions[mention_start_index:]:
            if mention.start >= event.document_span[1]:
                break
            if mention.end <= event.document_span[1]:
                bounded_mentions.append(mention)
        preproof_words = tuple(
            sorted(
                {
                    token.normalized
                    for token in bounded_tokens
                    if token.kind == "WORD"
                }
            )
        )
        event_tokens_by_id[event.event_id] = tuple(bounded_tokens)
        event_mentions_by_id[event.event_id] = tuple(bounded_mentions)
        event_words_by_id[event.event_id] = preproof_words
        predicate_words = tuple(
            re.findall(
                r"[^\W_]+(?:[-'][^\W_]+)*",
                event.predicate_normalized,
                re.UNICODE,
            )
        )
        expected_labels, expected_types = canonical_event_semantics_r14(
            predicate_words
        )
        nominal_price_assertion = (
            bool(set(preproof_words).intersection({"cost", "price", "pricing", "quote"}))
            and any(
                row.mention_type == "product_or_hardware"
                and row.proof_state == "PROVED"
                for row in bounded_mentions
            )
        )
        if nominal_price_assertion:
            expected_labels = tuple(
                sorted({*expected_labels, "DELL-RSQ-03A-TARGET-ASP"})
            )
            expected_types = tuple(sorted({*expected_types, "pricing"}))
        require(
            event.semantic_labels == expected_labels
            and event.event_types == expected_types,
            "R14_graph_event_semantics_recomputation_failed",
        )
        preproof_word_set = set(preproof_words)
        require(
            event.polarity
            == ("negative" if preproof_word_set.intersection(_NEGATION) else "affirmative")
            and event.modality
            == ("modal" if preproof_word_set.intersection(_MODALS) else "asserted")
            and event.actuality
            == (
                "forward_looking"
                if preproof_word_set.intersection(_FORWARD)
                else "actual_or_current"
            )
            and event.lifecycle
            == (
                "inactive"
                if preproof_word_set.intersection(_INACTIVE)
                else "active_or_unspecified"
            )
            and event.speech_mode
            in {"direct_or_unspecified", "issuer_reported", "reported_speech"},
            "R14_graph_event_assertion_semantics_recomputation_failed",
        )
        require(
            tuple(sorted(set(event.inference_barrier_ids)))
            == event.inference_barrier_ids,
            "R14_graph_event_inference_barrier_canonical_invalid",
        )
    assertion_signals_by_sentence: dict[
        tuple[str, tuple[int, int]], tuple[tuple[TokenR14, ...], bool]
    ] = {}
    for event in graph.events:
        key = (event.local_scope_id, event.sentence_span)
        if key in assertion_signals_by_sentence:
            continue
        scoped_tokens = tokens_by_scope.get(event.local_scope_id, ())
        start_index = bisect_left(
            token_starts_by_scope.get(event.local_scope_id, ()),
            event.sentence_span[0],
        )
        sentence_tokens: list[TokenR14] = []
        for token in scoped_tokens[start_index:]:
            if token.start >= event.sentence_span[1]:
                break
            if token.end <= event.sentence_span[1]:
                sentence_tokens.append(token)
        assertion_signals_by_sentence[key] = assertion_attribution_signal_tokens_r14(
            sentence_tokens
        )
    for proof in graph.proofs:
        require(proof.rule_id in RULE_IDS and proof.state in PROOF_STATES, "R14_graph_proof_rule_or_state_invalid")
        require(all(_span_valid(span, text_length) for span in proof.premise_spans), "R14_graph_proof_span_invalid")
        require(
            set(proof.premise_edge_ids).issubset(graph_edge_ids),
            "R14_graph_proof_premise_edge_orphan",
        )
        require(
            set(proof.premise_node_ids).issubset(graph_node_ids),
            "R14_graph_proof_premise_node_orphan",
        )
        if proof.rule_id == "G22-OBJECT-LIST" and proof.state == "PROVED":
            require(
                proof.conclusion == "no_new_event_object_list"
                and len(proof.premise_spans) == 3
                and len(proof.premise_node_ids) == 2,
                "R14_graph_proof_G22_semantics_invalid",
            )
            left = mention_by_id[proof.premise_node_ids[0]]
            right = mention_by_id[proof.premise_node_ids[1]]
            coordinator_span = proof.premise_spans[1]
            require(
                left.mention_type == right.mention_type
                and left.mention_type
                in {"product_or_hardware", "quantity", "quantity_or_percent"}
                and left.local_scope_id == right.local_scope_id
                and proof.premise_spans
                == (
                    (left.start, left.end),
                    coordinator_span,
                    (right.start, right.end),
                )
                and left.end <= coordinator_span[0]
                and coordinator_span[1] <= right.start
                and normalize_structural_text_r14(
                    graph.raw_text[coordinator_span[0] : coordinator_span[1]]
                )
                in {"and", "or"},
                "R14_graph_proof_G22_endpoint_or_span_invalid",
            )
            # G22 is a structural no-new-event proof.  It must never derive
            # its validity from role edges that it can itself influence.
            # Endpoint type/scope, exact slices and the closed token barrier
            # are the independent oracle; target roles are downstream only.
            covered = ((right.start, right.end),)
            scoped_tokens = tokens_by_scope.get(right.local_scope_id, ())
            bounded_start = bisect_left(
                token_starts_by_scope.get(right.local_scope_id, ()),
                coordinator_span[1],
            )
            unexplained_between = [
                token
                for token in scoped_tokens[bounded_start:]
                if token.start < right.end
                and token.end <= right.end
                and token.kind == "WORD"
                and token.normalized not in _STRUCTURAL_FUNCTION_WORDS
                and not any(
                    start <= token.start and token.end <= end
                    for start, end in covered
                )
            ]
            require(
                not unexplained_between,
                "R14_graph_proof_G22_unexplained_content_barrier",
            )
    for event in graph.events:
        require(event.local_scope_id in scope_by_id, "R14_graph_event_scope_orphan")
        require(_span_valid(event.document_span, text_length) and _span_valid(event.predicate_span, text_length), "R14_graph_event_span_out_of_bounds")
        require(event.document_span[0] <= event.predicate_span[0] and event.predicate_span[1] <= event.document_span[1], "R14_graph_event_predicate_outside_event")
        require(event.predicate_surface == graph.raw_text[event.predicate_span[0] : event.predicate_span[1]], "R14_graph_event_predicate_slice_mismatch")
        require(event.predicate_normalized == normalize_structural_text_r14(event.predicate_surface), "R14_graph_event_predicate_normalization_mismatch")
        require(
            event.semantic_operator_ids
            == canonical_predicate_operator_identity_ids_r14(
                event.predicate_normalized
            ),
            "R14_graph_event_operator_identity_recomputation_failed",
        )
        require(set(event.candidate_subject_mention_ids).issubset(mention_ids), "R14_graph_event_subject_candidate_orphan")
        if event.assertion_owner_mention_id is not None:
            require(event.assertion_owner_mention_id in mention_by_id, "R14_graph_event_owner_orphan")

        event_words = event_words_by_id[event.event_id]
        predicate_words = tuple(
            re.findall(
                r"[^\W_]+(?:[-'][^\W_]+)*",
                event.predicate_normalized,
                re.UNICODE,
            )
        )
        expected_labels, expected_event_types = canonical_event_semantics_r14(
            predicate_words
        )
        nominal_price_assertion = (
            bool(set(event_words).intersection({"cost", "price", "pricing", "quote"}))
            and any(
                row.mention_type == "product_or_hardware"
                and row.proof_state == "PROVED"
                for row in event_mentions_by_id[event.event_id]
            )
        )
        if nominal_price_assertion:
            expected_labels = tuple(
                sorted({*expected_labels, "DELL-RSQ-03A-TARGET-ASP"})
            )
            expected_event_types = tuple(
                sorted({*expected_event_types, "pricing"})
            )
        require(
            event.semantic_labels == expected_labels
            and event.event_types == expected_event_types,
            "R14_graph_event_semantics_recomputation_failed",
        )
        expected_proof_type = canonical_predicate_proof_type_r14(
            event.predicate_normalized
        )
        require(
            event.predicate_proof_type
            == (
                "AMBIGUOUS-NONCE-EVENT-BARRIER"
                if event.predicate_proof_type == "AMBIGUOUS-NONCE-EVENT-BARRIER"
                else expected_proof_type
            )
            and (
                expected_proof_type is not None
                or event.predicate_proof_type == "AMBIGUOUS-NONCE-EVENT-BARRIER"
            ),
            "R14_graph_event_predicate_proof_recomputation_failed",
        )
        product_spans = [
            (row.start, row.end)
            for row in event_mentions_by_id[event.event_id]
            if row.mention_type == "product_or_hardware"
        ]
        expected_subjects = tuple(
            row.mention_id
            for row in sorted(
                (
                    row
                    for row in event_mentions_by_id[event.event_id]
                    if row.mention_type == "entity"
                    and event.document_span[0] <= row.start
                    and row.end <= event.predicate_span[0]
                    and not any(
                        start <= row.start and row.end <= end
                        for start, end in product_spans
                    )
                ),
                key=lambda row: (row.start, row.end, row.node_digest),
            )
        )
        require(
            event.candidate_subject_mention_ids == expected_subjects,
            "R14_graph_event_subject_candidates_recomputation_failed",
        )
        if len(expected_subjects) == 1:
            expected_subject_state = (
                "explicit"
                if mention_by_id[expected_subjects[0]].proof_state == "PROVED"
                else "explicit_unknown"
            )
            expected_owner_id = expected_subjects[0]
        elif len(expected_subjects) > 1:
            expected_subject_state = "ambiguous"
            expected_owner_id = None
        elif event.assertion_owner_mention_id is not None:
            expected_subject_state = "inherited_actor_only"
            expected_owner_id = event.assertion_owner_mention_id
        else:
            expected_subject_state = "unproved"
            expected_owner_id = None
        require(
            event.subject_state == expected_subject_state
            and event.assertion_owner_mention_id == expected_owner_id
            and event.assertion_owner
            == (
                mention_by_id[expected_owner_id].normalized_value
                if expected_owner_id is not None
                else None
            ),
            "R14_graph_event_subject_state_recomputation_failed",
        )
        word_set = set(event_words)
        expected_speech_mode = canonical_assertion_speech_mode_r14(
            predicate_span=event.predicate_span,
            document_span=event.document_span,
            sentence_span=event.sentence_span,
            local_scope_id=event.local_scope_id,
            assertion_owner_identity_ids=(
                mention_by_id[expected_owner_id].semantic_identity_ids
                if expected_owner_id is not None
                else ()
            ),
            tokens=graph.tokens,
            mentions=graph.mentions,
            reporting_tokens=assertion_signals_by_sentence[
                (event.local_scope_id, event.sentence_span)
            ][0],
            according_present=assertion_signals_by_sentence[
                (event.local_scope_id, event.sentence_span)
            ][1],
        )
        expected_inference_barriers = canonical_event_inference_barrier_ids_r14(
            tokens=event_tokens_by_id[event.event_id],
            mentions=event_mentions_by_id[event.event_id],
            predicate_operator_ids=event.semantic_operator_ids,
            event_types=event.event_types,
        )
        require(
            event.polarity
            == ("negative" if word_set.intersection(_NEGATION) else "affirmative")
            and event.modality
            == ("modal" if word_set.intersection(_MODALS) else "asserted")
            and event.actuality
            == (
                "forward_looking"
                if word_set.intersection(_FORWARD)
                else "actual_or_current"
            )
            and event.lifecycle
            == (
                "inactive"
                if word_set.intersection(_INACTIVE)
                else "active_or_unspecified"
            )
            and event.speech_mode == expected_speech_mode,
            "R14_graph_event_assertion_semantics_recomputation_failed",
        )
        require(
            event.inference_barrier_ids == expected_inference_barriers,
            "R14_graph_event_inference_barrier_recomputation_failed",
        )
        required_ambiguities = set()
        if event.predicate_proof_type == "AMBIGUOUS-NONCE-EVENT-BARRIER":
            required_ambiguities.add("ambiguous_event_barrier")
        if scope_by_id[event.local_scope_id].proof_state != "PROVED":
            required_ambiguities.add("unclosed_or_mismatched_local_scope")
        if len(expected_subjects) > 1:
            required_ambiguities.add("multiple_subject_candidates")
        require(
            set(event.ambiguities).issubset(
                {
                    "ambiguous_event_barrier",
                    "unclosed_or_mismatched_local_scope",
                    "multiple_subject_candidates",
                }
            )
            and required_ambiguities.issubset(event.ambiguities)
            and event.limitations
            == (() if expected_labels else ("predicate_semantic_type_unproved",)),
            "R14_graph_event_ambiguity_or_limitation_recomputation_failed",
        )

    expected_role_contracts: set[
        tuple[str, str, str, str, str, tuple[tuple[int, int], ...]]
    ] = set()
    for event in graph.events:
        predicate_mentions = predicate_mentions_by_scope_span.get(
            (event.local_scope_id, event.predicate_span), ()
        )
        require(
            len(predicate_mentions) == 1,
            "R14_graph_event_predicate_mention_bijection_failed",
        )
        predicate = predicate_mentions[0]
        expected_role_contracts.add(
            (
                event.event_id,
                "predicate",
                predicate.mention_id,
                "G30-ROLE-LOCAL",
                "AMBIGUOUS" if event.ambiguities else "PROVED",
                (event.predicate_span,),
            )
        )
        if event.assertion_owner_mention_id is not None:
            actor = mention_by_id[event.assertion_owner_mention_id]
            inherited = event.subject_state == "inherited_actor_only"
            expected_role_contracts.add(
                (
                    event.event_id,
                    "actor",
                    actor.mention_id,
                    "G23-SUBJECT-INHERIT" if inherited else "G30-ROLE-LOCAL",
                    "PROVED"
                    if inherited or actor.proof_state == "PROVED"
                    else "AMBIGUOUS",
                    ((actor.start, actor.end), event.predicate_span),
                )
            )
        event_mentions = list(event_mentions_by_id[event.event_id])
        products = [
            row for row in event_mentions if row.mention_type == "product_or_hardware"
        ]
        event_tokens = list(event_tokens_by_id[event.event_id])
        for mention in event_mentions:
            if mention.mention_id in {
                predicate.mention_id,
                event.assertion_owner_mention_id or "",
            }:
                continue
            role = None
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
                role = "recipient" if preceding and preceding[-1] in {"to", "for"} else "counterparty"
            if role is None:
                continue
            state = (
                "PROVED"
                if not event.ambiguities and event.semantic_labels
                else "AMBIGUOUS"
                if event.ambiguities
                else "UNSUPPORTED"
            )
            if role in {"quantity", "measure"} and len(products) != 1:
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
            expected_role_contracts.add(
                (
                    event.event_id,
                    role,
                    mention.mention_id,
                    "G31-TEMPORAL-LOCAL" if role == "period" else "G30-ROLE-LOCAL",
                    state,
                    ((mention.start, mention.end), event.predicate_span),
                )
            )

    actual_role_contracts = {
        (
            row.event_id,
            row.role,
            row.mention_id,
            row.proof_rule_id,
            row.proof_state,
            row.evidence_spans,
        )
        for row in graph.role_edges
    }
    require(
        actual_role_contracts == expected_role_contracts
        and len(actual_role_contracts) == len(graph.role_edges),
        "R14_graph_role_population_recomputation_failed",
    )

    role_edges_by_event_role_mention: dict[
        tuple[str, str, str], tuple[RoleEdgeR14, ...]
    ] = {}
    role_edge_rows: dict[tuple[str, str, str], list[RoleEdgeR14]] = {}
    for role_edge in graph.role_edges:
        role_edge_rows.setdefault(
            (role_edge.event_id, role_edge.role, role_edge.mention_id), []
        ).append(role_edge)
    role_edges_by_event_role_mention = {
        key: tuple(rows) for key, rows in role_edge_rows.items()
    }

    require(tuple(graph.role_edges) == tuple(sorted(graph.role_edges, key=lambda row: (row.event_id, row.role, row.mention_id, row.edge_digest))), "R14_graph_role_canonical_order_invalid")
    role_edge_ids = {row.edge_id for row in graph.role_edges}
    require(len(role_edge_ids) == len(graph.role_edges), "R14_graph_role_edge_collision")
    for edge in graph.role_edges:
        require(edge.event_id in event_by_id and edge.mention_id in mention_by_id, "R14_graph_role_endpoint_orphan")
        event = event_by_id[edge.event_id]
        mention = mention_by_id[edge.mention_id]
        require(edge.event_scope_id == event.event_scope_id, "R14_graph_role_event_scope_mismatch")
        require(edge.role in ROLE_MENTION_TYPES and mention.mention_type in ROLE_MENTION_TYPES[edge.role], "R14_graph_role_endpoint_type_invalid")
        require(edge.proof_rule_id in RULE_IDS and edge.proof_state in PROOF_STATES, "R14_graph_role_proof_invalid")
        require(set(edge.premise_proof_ids).issubset(proof_ids), "R14_graph_role_premise_proof_orphan")
        require(len(edge.premise_proof_ids) == 1, "R14_graph_role_premise_cardinality_invalid")
        premise = proof_by_id[edge.premise_proof_ids[0]]
        require(
            premise.rule_id == edge.proof_rule_id
            and premise.state == edge.proof_state
            and premise.conclusion == f"event_role:{edge.role}:{event.event_scope_id}"
            and tuple(premise.premise_spans) == tuple(edge.evidence_spans)
            and len(premise.premise_node_ids) >= 2
            and premise.premise_node_ids[0] == event.event_id
            and premise.premise_node_ids[1] == mention.mention_id,
            "R14_graph_role_premise_recomputation_failed",
        )
        require(all(_span_valid(span, text_length) for span in edge.evidence_spans), "R14_graph_role_evidence_span_invalid")
        require(mention.local_scope_id == event.local_scope_id, "R14_graph_cross_local_scope_material_edge")
        if edge.proof_rule_id != "G23-SUBJECT-INHERIT":
            require(event.document_span[0] <= mention.start and mention.end <= event.document_span[1], "R14_graph_cross_event_material_edge")
        else:
            require(edge.role == "actor" and edge.proof_state == "PROVED", "R14_graph_subject_inherit_non_actor")
        if edge.role == "predicate":
            require(
                mention.start == event.predicate_span[0]
                and mention.end == event.predicate_span[1]
                and mention.semantic_identity_ids
                == tuple(
                    sorted(
                        {
                            *(f"TARGET::{row}" for row in event.semantic_labels),
                            *(f"EVENT_TYPE::{row}" for row in event.event_types),
                            *event.semantic_operator_ids,
                        }
                    )
                ),
                "R14_graph_role_predicate_witness_invalid",
            )
        elif edge.role == "actor" and edge.proof_rule_id == "G30-ROLE-LOCAL":
            require(
                mention.mention_id in event.candidate_subject_mention_ids
                and mention.end <= event.predicate_span[0],
                "R14_graph_role_explicit_actor_witness_invalid",
            )
        elif edge.role not in {"actor", "predicate"} and edge.proof_state == "PROVED":
            require(
                bool(event.semantic_labels),
                "R14_graph_role_target_semantic_event_unproved",
            )
            if mention.start < event.predicate_span[0]:
                between_words = {
                    token.normalized
                    for token in event_tokens_by_id[event.event_id]
                    if token.kind == "WORD"
                    and mention.end <= token.start
                    and token.end <= event.predicate_span[0]
                }
                require(
                    edge.role == "object"
                    and "pricing" in event.event_types
                    and (
                        event.predicate_normalized.split()[0]
                        in {"was", "were", "is", "are"}
                        or bool(
                            between_words.intersection({"was", "were", "is", "are"})
                        )
                    ),
                    "R14_graph_role_pre_predicate_material_witness_invalid",
                )

    ordered_events = sorted(graph.events, key=lambda row: (row.document_span, row.predicate_span))
    event_position = {row.event_id: index for index, row in enumerate(ordered_events)}
    require(
        tuple(graph.subject_share_edges)
        == tuple(sorted(graph.subject_share_edges, key=lambda row: row.edge_digest))
        and len({row.edge_id for row in graph.subject_share_edges})
        == len(graph.subject_share_edges),
        "R14_graph_subject_share_canonical_or_duplicate_invalid",
    )
    subject_shares_by_right_subject: dict[
        tuple[str, str], tuple[SubjectShareEdgeR14, ...]
    ] = {}
    subject_share_rows: dict[tuple[str, str], list[SubjectShareEdgeR14]] = {}
    for share_edge in graph.subject_share_edges:
        subject_share_rows.setdefault(
            (share_edge.right_event_id, share_edge.source_subject_mention_id), []
        ).append(share_edge)
    subject_shares_by_right_subject = {
        key: tuple(rows) for key, rows in subject_share_rows.items()
    }
    for edge in graph.subject_share_edges:
        require(
            edge.proof_rule_id == "G23-SUBJECT-INHERIT"
            and edge.destination_role == "actor"
            and edge.cardinality
            == "one_subject_one_left_event_one_right_event_one_actor",
            "R14_graph_subject_share_contract_invalid",
        )
        require(edge.left_event_id in event_by_id and edge.right_event_id in event_by_id and edge.source_subject_mention_id in mention_by_id, "R14_graph_subject_share_endpoint_invalid")
        left = event_by_id[edge.left_event_id]
        right = event_by_id[edge.right_event_id]
        source = mention_by_id[edge.source_subject_mention_id]
        require(source.mention_type == "entity" and left.local_scope_id == right.local_scope_id == source.local_scope_id, "R14_graph_subject_share_scope_or_type_invalid")
        require(left.clause_span == right.clause_span and event_position[right.event_id] == event_position[left.event_id] + 1, "R14_graph_subject_share_nonadjacent")
        require(0 <= edge.coordinator_span[0] < edge.coordinator_span[1] <= text_length and normalize_structural_text_r14(graph.raw_text[edge.coordinator_span[0] : edge.coordinator_span[1]]) in {"and", "but", "or", "while", "whereas", "then", "yet"}, "R14_graph_subject_share_coordinator_invalid")
        require(
            left.document_span[1] <= edge.coordinator_span[0]
            and edge.coordinator_span[1] <= right.document_span[0],
            "R14_graph_subject_share_coordinator_not_between_adjacent_events",
        )
        left_actor = [
            row
            for row in role_edges_by_event_role_mention.get(
                (left.event_id, "actor", source.mention_id), ()
            )
            if row.proof_rule_id in {"G30-ROLE-LOCAL", "G23-SUBJECT-INHERIT"}
            and row.proof_state == "PROVED"
        ]
        right_actor = [
            row
            for row in role_edges_by_event_role_mention.get(
                (right.event_id, "actor", source.mention_id), ()
            )
            if row.proof_rule_id == "G23-SUBJECT-INHERIT"
            and row.proof_state == "PROVED"
        ]
        require(len(left_actor) == len(right_actor) == 1, "R14_graph_subject_share_actor_bijection_invalid")
        if left_actor[0].proof_rule_id == "G23-SUBJECT-INHERIT":
            require(
                any(
                    prior.right_event_id == left.event_id
                    and prior.source_subject_mention_id == source.mention_id
                    for prior in subject_shares_by_right_subject.get(
                        (left.event_id, source.mention_id), ()
                    )
                ),
                "R14_graph_subject_share_transitive_source_unproved",
            )

    require(
        tuple(graph.temporal_edges)
        == tuple(sorted(graph.temporal_edges, key=lambda row: row.edge_digest))
        and len({row.edge_id for row in graph.temporal_edges})
        == len(graph.temporal_edges),
        "R14_graph_temporal_canonical_or_duplicate_invalid",
    )
    for edge in graph.temporal_edges:
        require(edge.event_id in event_by_id and edge.period_mention_id in mention_by_id, "R14_graph_temporal_endpoint_invalid")
        event = event_by_id[edge.event_id]
        period = mention_by_id[edge.period_mention_id]
        require(period.mention_type == "period" and period.local_scope_id == event.local_scope_id, "R14_graph_temporal_scope_or_type_invalid")
        require(edge.proof_rule_id == "G31-TEMPORAL-LOCAL" and edge.proof_state in {"PROVED", "AMBIGUOUS", "UNSUPPORTED"}, "R14_graph_temporal_proof_invalid")
        require(
            edge.scope_type == "event_local_single_event"
            and all(_span_valid(span, text_length) for span in edge.evidence_spans)
            and len(edge.premise_proof_ids) == 1
            and edge.premise_proof_ids[0] in proof_by_id,
            "R14_graph_temporal_contract_invalid",
        )
        premise = proof_by_id[edge.premise_proof_ids[0]]
        require(
            premise.rule_id == edge.proof_rule_id
            and premise.state == edge.proof_state
            and premise.conclusion == f"event_role:period:{event.event_scope_id}"
            and tuple(premise.premise_spans) == tuple(edge.evidence_spans)
            and premise.premise_node_ids[:2]
            == (event.event_id, period.mention_id),
            "R14_graph_temporal_premise_recomputation_failed",
        )
        matching = [
            row
            for row in role_edges_by_event_role_mention.get(
                (event.event_id, "period", period.mention_id), ()
            )
            if row.proof_state == edge.proof_state
        ]
        require(len(matching) == 1, "R14_graph_temporal_role_bijection_invalid")

    require(
        tuple(graph.target_bridge_edges)
        == tuple(sorted(graph.target_bridge_edges, key=lambda row: row.edge_digest))
        and len({row.edge_id for row in graph.target_bridge_edges})
        == len(graph.target_bridge_edges),
        "R14_graph_target_bridge_canonical_or_duplicate_invalid",
    )
    role_by_id = {row.edge_id: row for row in graph.role_edges}
    role_ids = set(role_by_id)
    adjacent_event_pairs: set[tuple[str, str]] = set()
    events_by_sentence: dict[tuple[int, int], list[EventNodeR14]] = {}
    for event in graph.events:
        events_by_sentence.setdefault(event.sentence_span, []).append(event)
    for sentence_events in events_by_sentence.values():
        ordered = sorted(
            sentence_events,
            key=lambda row: (row.document_span, row.predicate_span, row.event_id),
        )
        adjacent_event_pairs.update(
            (left.event_id, right.event_id)
            for left, right in zip(ordered, ordered[1:])
        )
    for edge in graph.target_bridge_edges:
        require(
            edge.source_event_id in event_by_id
            and edge.destination_event_id in event_by_id
            and edge.source_event_id != edge.destination_event_id,
            "R14_graph_target_bridge_endpoint_invalid",
        )
        source_event = event_by_id[edge.source_event_id]
        destination_event = event_by_id[edge.destination_event_id]
        require(
            source_event.local_scope_id == destination_event.local_scope_id
            and source_event.sentence_span == destination_event.sentence_span,
            "R14_graph_target_bridge_scope_invalid",
        )
        require(
            (edge.source_event_id, edge.destination_event_id)
            in adjacent_event_pairs,
            "R14_graph_target_bridge_non_adjacent_events",
        )
        bridge_contract = {
            "SUPPLIER_RELATIONSHIP_TO_DELIVERY": (
                "supplier_relationship",
                "delivery",
                "relationship_to_delivery",
            ),
            "HBM_STATE_TO_DELL": (
                "HBM_supply_state",
                "Dell_configuration_or_delivery",
                "upstream_state_to_Dell",
            ),
        }
        require(
            edge.bridge_type in bridge_contract
            and edge.direction == bridge_contract[edge.bridge_type][2]
            and bridge_contract[edge.bridge_type][0] in source_event.event_types
            and bridge_contract[edge.bridge_type][1]
            in destination_event.event_types
            and edge.proof_rule_id == "G30-ROLE-LOCAL"
            and edge.proof_state == "PROVED"
            and bool(edge.shared_semantic_identity_ids)
            and tuple(sorted(set(edge.shared_semantic_identity_ids)))
            == edge.shared_semantic_identity_ids,
            "R14_graph_target_bridge_contract_invalid",
        )
        require(
            bool(edge.premise_edge_ids)
            and set(edge.premise_edge_ids).issubset(role_ids)
            and all(
                role_by_id[edge_id].event_id
                in {edge.source_event_id, edge.destination_event_id}
                and role_by_id[edge_id].proof_state == "PROVED"
                for edge_id in edge.premise_edge_ids
            ),
            "R14_graph_target_bridge_premise_invalid",
        )
        identities_by_event: dict[str, set[str]] = {
            edge.source_event_id: set(),
            edge.destination_event_id: set(),
        }
        for edge_id in edge.premise_edge_ids:
            role = role_by_id[edge_id]
            identities_by_event[role.event_id].update(
                value
                for value in mention_by_id[role.mention_id].semantic_identity_ids
                if value.startswith("ENTITY::") or value.startswith("PRODUCT::")
            )
        require(
            set(edge.shared_semantic_identity_ids)
            == identities_by_event[edge.source_event_id].intersection(
                identities_by_event[edge.destination_event_id]
            ),
            "R14_graph_target_bridge_identity_recomputation_failed",
        )
        if edge.bridge_type == "HBM_STATE_TO_DELL":
            require(
                any(
                    value.startswith("PRODUCT::HBM")
                    for value in edge.shared_semantic_identity_ids
                ),
                "R14_graph_HBM_bridge_identity_invalid",
            )
        else:
            require(
                "ENTITY::DELL" in edge.shared_semantic_identity_ids
                and any(
                    value.startswith("ENTITY::") and value != "ENTITY::DELL"
                    for value in edge.shared_semantic_identity_ids
                ),
                "R14_graph_supplier_bridge_identity_invalid",
            )


def validate_price_attachment_graph_r14(value: PriceAttachmentGraphR14, *, graph: EventArgumentGraphR14) -> None:
    require(value.event_graph_digest == graph.graph_digest, "R14_price_graph_event_graph_digest_mismatch")
    event_by_id = {row.event_id: row for row in graph.events}
    node_by_id = {row.mention_id: row for row in (*graph.mentions, *value.nodes)}
    require(len(node_by_id) == len(graph.mentions) + len(value.nodes), "R14_price_graph_node_collision")
    edge_by_id = {row.edge_id: row for row in value.edges}
    require(len(edge_by_id) == len(value.edges), "R14_price_graph_edge_collision")
    price_node_ids = set(node_by_id)
    price_edge_ids = set(edge_by_id)
    require(tuple(value.nodes) == tuple(sorted(value.nodes, key=lambda row: (row.start, row.end, row.mention_type, row.type_proof_rule_id, row.node_digest))), "R14_price_graph_node_canonical_order_invalid")
    require(tuple(value.edges) == tuple(sorted(value.edges, key=lambda row: (row.spans, row.source_node_type, row.relation, row.destination_node_type, row.edge_digest))), "R14_price_graph_edge_canonical_order_invalid")
    require(
        tuple(value.proofs)
        == tuple(sorted(value.proofs, key=lambda row: (row.event_id, row.proof_digest)))
        and len({row.proof_id for row in value.proofs}) == len(value.proofs),
        "R14_price_proof_canonical_or_duplicate_invalid",
    )
    allowed_pairs = {
        ("event", "product_or_hardware"),
        ("event", "bundle"),
        ("event", "nominal_head"),
        ("price", "product_or_hardware"),
        ("price", "bundle"),
        ("price", "nominal_head"),
        ("nominal_head", "nominal_head"),
        ("nominal_head", "product_or_hardware"),
        ("product_or_hardware", "bundle"),
    }
    edge_shape = {
        ("event", "product_or_hardware", "event_object_head"): "event_to_nominal",
        ("event", "bundle", "event_object_head"): "event_to_nominal",
        ("event", "nominal_head", "event_object_head"): "event_to_nominal",
        ("price", "product_or_hardware", "price_attachment"): "price_to_nominal",
        ("price", "bundle", "price_attachment"): "price_to_nominal",
        ("price", "nominal_head", "price_attachment"): "price_to_nominal",
        ("product_or_hardware", "bundle", "bundle_member"): "member_to_bundle",
        ("nominal_head", "nominal_head", "complement"): "head_to_complement",
        ("nominal_head", "nominal_head", "relative"): "head_to_complement",
        ("nominal_head", "nominal_head", "participial"): "head_to_complement",
        ("nominal_head", "nominal_head", "apposition"): "head_to_complement",
        ("nominal_head", "nominal_head", "coordination"): "head_to_complement",
        ("nominal_head", "product_or_hardware", "complement"): "head_to_complement",
        ("nominal_head", "product_or_hardware", "relative"): "head_to_complement",
        ("nominal_head", "product_or_hardware", "participial"): "head_to_complement",
        ("nominal_head", "product_or_hardware", "apposition"): "head_to_complement",
        ("nominal_head", "product_or_hardware", "coordination"): "head_to_complement",
    }
    for node in value.nodes:
        require(node.mention_type in {"nominal_head", "bundle"}, "R14_price_graph_private_node_type_invalid")
        require(
            _span_valid((node.start, node.end), len(graph.raw_text))
            and node.raw_value == graph.raw_text[node.start : node.end]
            and node.normalized_value
            == normalize_structural_text_r14(node.raw_value)
            and node.local_scope_id in {row.scope_id for row in graph.local_scopes}
            and node.type_proof_rule_id == "G40-NOMINAL-HEAD"
            and node.proof_state in {"PROVED", "AMBIGUOUS", "UNSUPPORTED"},
            "R14_price_graph_private_node_invalid",
        )
    for edge in value.edges:
        require((edge.source_node_type, edge.destination_node_type) in allowed_pairs, "R14_price_graph_endpoint_type_invalid")
        require(
            edge_shape.get(
                (edge.source_node_type, edge.destination_node_type, edge.relation)
            )
            == edge.direction,
            "R14_price_graph_edge_direction_or_relation_invalid",
        )
        if edge.source_node_type == "event":
            require(edge.source_node_id in event_by_id, "R14_price_graph_event_orphan")
        else:
            require(edge.source_node_id in node_by_id and node_by_id[edge.source_node_id].mention_type == edge.source_node_type, "R14_price_graph_source_orphan_or_type_mismatch")
        require(edge.destination_node_id in node_by_id and node_by_id[edge.destination_node_id].mention_type == edge.destination_node_type, "R14_price_graph_destination_orphan_or_type_mismatch")
        require(edge.rule_id in {"G40-NOMINAL-HEAD", "G50-PRICE-DIRECT", "G51-PRICE-NOMINAL", "G52-HARDWARE-BUNDLE"}, "R14_price_graph_edge_rule_invalid")
        require(edge.proof_state in {"PROVED", "AMBIGUOUS", "UNSUPPORTED"}, "R14_price_graph_edge_state_invalid")
        require(
            bool(edge.spans)
            and all(_span_valid(span, len(graph.raw_text)) for span in edge.spans),
            "R14_price_graph_edge_span_invalid",
        )
        source_span = (
            event_by_id[edge.source_node_id].predicate_span
            if edge.source_node_type == "event"
            else (
                node_by_id[edge.source_node_id].start,
                node_by_id[edge.source_node_id].end,
            )
        )
        destination_span = (
            node_by_id[edge.destination_node_id].start,
            node_by_id[edge.destination_node_id].end,
        )
        require(
            edge.spans == (source_span, destination_span),
            "R14_price_graph_edge_endpoint_span_recomputation_failed",
        )
    family_by_rule = {
        "G50-PRICE-DIRECT": "pricing_event_product_and_price_complement",
        "G51-PRICE-NOMINAL": {
            "product_priced_at_price",
            "explicit_price_or_cost_of_for_product_copular_amount",
        },
        "G52-HARDWARE-BUNDLE": "all_hardware_bounded_bundle_total",
    }
    proved_roles_by_event: dict[str, dict[str, set[str]]] = {}
    for role_edge in graph.role_edges:
        if role_edge.proof_state != "PROVED":
            continue
        proved_roles_by_event.setdefault(role_edge.event_id, {}).setdefault(
            role_edge.role, set()
        ).add(role_edge.mention_id)
    product_node_ids = {
        node_id
        for node_id, node in node_by_id.items()
        if node.mention_type == "product_or_hardware"
    }
    for proof in value.proofs:
        require(proof.event_id in event_by_id, "R14_price_proof_event_orphan")
        require(set(proof.product_mention_ids).issubset(price_node_ids) and all(node_by_id[node_id].mention_type == "product_or_hardware" for node_id in proof.product_mention_ids), "R14_price_proof_product_orphan")
        require(set(proof.price_mention_ids).issubset(price_node_ids) and all(node_by_id[node_id].mention_type == "price" for node_id in proof.price_mention_ids), "R14_price_proof_price_orphan")
        require(set(proof.governing_head_mention_ids).issubset(price_node_ids), "R14_price_proof_governing_head_orphan")
        require(set(proof.competing_head_ids).issubset(price_node_ids) and set(proof.competing_price_ids).issubset(price_node_ids), "R14_price_proof_competing_endpoint_orphan")
        require(set(proof.edge_ids).issubset(price_edge_ids), "R14_price_proof_edge_orphan")
        if proof.state == "PROVED":
            event = event_by_id[proof.event_id]
            event_roles = proved_roles_by_event.get(proof.event_id, {})
            require(not event.ambiguities and event.subject_state not in {"ambiguous", "unproved"}, "R14_price_positive_ambiguous_event")
            require(proof.rule_id in family_by_rule and len(proof.price_mention_ids) == 1 and len(proof.governing_head_mention_ids) == 1 and bool(proof.product_mention_ids) and bool(proof.edge_ids), "R14_price_positive_topology_invalid")
            expected_family = family_by_rule[proof.rule_id]
            require(proof.family == expected_family or isinstance(expected_family, set) and proof.family in expected_family, "R14_price_positive_family_rule_mismatch")
            require(not proof.competing_head_ids and not proof.competing_price_ids and not proof.limitations, "R14_price_positive_conflict_or_limitation")
            require(
                set(proof.product_mention_ids)
                == event_roles.get("object", set()).intersection(
                    product_node_ids
                )
                and set(proof.price_mention_ids) == event_roles.get("price", set())
                and all(
                    node_by_id[node_id].local_scope_id == event.local_scope_id
                    and event.document_span[0]
                    <= node_by_id[node_id].start
                    < node_by_id[node_id].end
                    <= event.document_span[1]
                    for node_id in (*proof.product_mention_ids, *proof.price_mention_ids)
                ),
                "R14_price_positive_event_role_rebind",
            )
            path_edges = [edge_by_id[edge_id] for edge_id in proof.edge_ids]
            require(
                all(
                    row.proof_state == "PROVED"
                    and (
                        row.rule_id == proof.rule_id
                        or row.rule_id == "G40-NOMINAL-HEAD"
                        and row.relation
                        in {"complement", "relative", "participial", "apposition", "coordination"}
                    )
                    for row in path_edges
                ),
                "R14_price_positive_path_rule_or_state_mismatch",
            )
            adjacency: dict[str, set[str]] = {}
            for path_edge in path_edges:
                adjacency.setdefault(path_edge.source_node_id, set()).add(
                    path_edge.destination_node_id
                )

            def reaches_governing_head(start: str) -> bool:
                pending = [start]
                visited: set[str] = set()
                while pending:
                    current = pending.pop()
                    if current in visited:
                        continue
                    visited.add(current)
                    if current in proof.governing_head_mention_ids:
                        return True
                    pending.extend(adjacency.get(current, ()))
                return False

            require(
                reaches_governing_head(proof.event_id),
                "R14_price_positive_event_head_path_missing",
            )
            require(
                all(reaches_governing_head(price_id) for price_id in proof.price_mention_ids),
                "R14_price_positive_price_head_path_missing",
            )
            if proof.rule_id in {"G50-PRICE-DIRECT", "G51-PRICE-NOMINAL"}:
                expected_direct = proof.family != (
                    "explicit_price_or_cost_of_for_product_copular_amount"
                )
                require(
                    len(proof.product_mention_ids) == 1
                    and proof.governing_head_mention_ids
                    == proof.product_mention_ids
                    and (
                        expected_direct
                        and len(path_edges) == 2
                        and {row.relation for row in path_edges}
                        == {"event_object_head", "price_attachment"}
                        or not expected_direct
                        and len(path_edges) == 3
                        and {row.relation for row in path_edges}
                        == {"event_object_head", "price_attachment", "complement"}
                        and len(
                            {
                                row.destination_node_id
                                for row in path_edges
                                if row.relation
                                in {"event_object_head", "price_attachment"}
                            }
                        )
                        == 1
                        and any(
                            row.relation == "complement"
                            and row.destination_node_id
                            == proof.product_mention_ids[0]
                            for row in path_edges
                        )
                    ),
                    "R14_price_positive_single_product_head_mismatch",
                )
            if proof.rule_id == "G52-HARDWARE-BUNDLE":
                bundle_id = proof.governing_head_mention_ids[0]
                members = {
                    row.source_node_id
                    for row in path_edges
                    if row.relation == "bundle_member"
                    and row.destination_node_id == bundle_id
                }
                require(
                    members == set(proof.product_mention_ids)
                    and len(path_edges) == 2 + len(proof.product_mention_ids)
                    and {row.relation for row in path_edges}
                    == {"event_object_head", "price_attachment", "bundle_member"},
                    "R14_price_positive_bundle_member_bijection_invalid",
                )
        else:
            require(proof.state in {"AMBIGUOUS", "UNSUPPORTED"} and proof.rule_id == "G90-CONFLICT", "R14_price_nonproved_rule_invalid")


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
    "TypedTargetBridgeEdgeR14",
    "TemporalScopeEdgeR14",
    "TokenR14",
    "assertion_attribution_signal_tokens_r14",
    "canonical_assertion_speech_mode_r14",
    "canonical_event_inference_barrier_ids_r14",
    "canonical_predicate_operator_identity_ids_r14",
    "canonical_semantic_identity_ids_r14",
    "classify_token_surface_r14",
    "normalize_structural_text_r14",
    "validate_event_argument_graph_r14",
    "validate_price_attachment_graph_r14",
]
