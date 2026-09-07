"""Read-only adapters from frozen Dell artifacts to the S3 compiler.

The adapter verifies existing artifacts and keeps only answer-free selector
metadata. It does not search, rank, admit Evidence, copy source text, or turn
the current owner-review candidate catalog into execution authority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlparse

from sec_agent.agent_runtime.dell_agentic_contracts import (
    MinimumRouteObligation,
    canonical_digest,
)
from sec_agent.agent_runtime.dell_owner_data_gate import (
    DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST,
    DellOwnerDataGateDecision,
    DellOwnerDataGateError,
    validate_trusted_dell_owner_data_gate_decision,
)
from sec_agent.agent_runtime.dell_source_family_compiler import (
    CapabilityArtifactBinding,
    CapabilityInventorySnapshot,
    DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE,
    ExternalInventoryBucket,
    LocalInventoryBucket,
    LocalInventoryRecord,
    ReviewedEvidenceIndexV1_2,
    S2CapabilityBucket,
    SourceFamilyCatalog,
    SourceFamilyCatalogEntry,
    HostOwnedBaselineSourcePlan,
    build_host_owned_baseline_source_plan,
    build_local_inventory_buckets,
)
from sec_agent.agent_runtime.planner_tool_capabilities import (
    PlannerToolCapabilityProjection,
)


EXPECTED_PHYSICAL_ROUTE_CATALOG_SHA256 = (
    "5e5c57ec952e44da4e319a19ccd128ed58b6fd1442696b203c2f39c30cf0c74b"
)
EXPECTED_PHYSICAL_ROUTE_CATALOG_DIGEST = (
    "5aa9d723bbfd86aa7eacec9e9c64f03378aaea43e79d62e6ee8e2f9d4d985cfa"
)
EXPECTED_LOCAL_NODES_SHA256 = (
    "f7fbf9f43a68933bad52146c3a8aa3c9a1b52bba81e4e804c2b05a0aff9d0817"
)
EXPECTED_EXTERNAL_MANIFEST_SHA256 = (
    "db7eae9aaa8108faadbe7ff07404dd25414e0191b7f62af0c7a42b85a0938b94"
)
EXPECTED_EXTERNAL_MANIFEST_DIGEST = (
    "c12d47a7a6dc9c6b5a4134c70e9916753e25d00ca494ee117e8147511f7a79df"
)
EXPECTED_S2_RESULT_SHA256 = (
    "dd2c92400de777867545de2c41b975d1f07ca6060f4ed431075b7081ab16ed82"
)
EXPECTED_S2_RESULT_DIGEST = (
    "f5a3ef877214766409a981d02349a2fd7ea010ed4a2548314531b7554a899ea6"
)

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_CATALOG_STATUS = "owner_review_candidate_answer_free_not_execution_authority"
_CATALOG_SCHEMA = "fin_ia_dell_source_family_physical_route_catalog_v1_0"
_NODE_SCHEMA = "fin_ia_dell_structured_rag_node_v1_0"
_MANIFEST_SCHEMA = "fin_ia_dell_external_exact_url_qualification_manifest_v1_0"
_S2_SCHEMA = "fin_ia_s2_company_financial_fact_mart_build_result_v1_0"
_POLICY_ROUTE_KINDS = (
    "external_source",
    "local_candidate",
    "reviewed_evidence",
)
_FORBIDDEN_CATALOG_KEYS = {
    "answer", "content", "document_text", "excerpt", "gold", "model_text",
    "numeric_value", "raw_text", "value",
}
_TOP_KEYS = {
    "schema_version", "status", "recorded_at", "case_id", "case_key",
    "research_as_of", "purpose", "authority", "digest_contract",
    "input_bindings", "catalog_contract", "catalog_counts", "local_routes",
    "external_routes", "reviewed_topic_branch_mapping", "entity_aliases",
    "owner_review_items", "catalog_digest",
}
_LOCAL_ROUTE_KEYS = {
    "route_id", "canonical_issuer_id", "canonical_domain", "source_role",
    "source_family_refs", "branch_ids", "document_kind", "fiscal_periods",
    "physical_node_count", "searchable_leaf_count",
}
_EXTERNAL_ROUTE_KEYS = {
    "route_id", "canonical_issuer_id", "canonical_domain", "source_role",
    "source_family_refs", "branch_ids", "official_url",
    "foundation_required_family_match",
}
_NODE_BASE_KEYS = {
    "candidate_is_not_evidence", "citation_eligible", "content",
    "content_sha256", "document_kind", "fiscal_period", "issuer_id", "lane",
    "model_text", "node_id", "node_kind", "numeric_authority",
    "parent_section_id", "publication_date", "period_end", "raw_body_sha256",
    "route_id", "schema_version", "source_role", "stable_url",
}
_NODE_ALLOWED_KEYS = _NODE_BASE_KEYS | {
    "company", "mixed_span_index", "page_end", "page_start",
    "parent_document_id", "section_chunk_index", "section_path",
    "source_block_ids", "source_chunk_id", "source_chunk_ids",
    "source_chunk_text_sha256", "source_spans", "table_column_count",
    "table_id", "table_row_count", "ticker", "title",
}


class CurrentCapabilityInventoryError(ValueError):
    """A frozen artifact cannot be truthfully projected into the inventory."""


@dataclass(frozen=True)
class PhysicalLocalRoute:
    route_id: str
    canonical_issuer_id: str
    canonical_domain: str
    source_role: str
    source_family_refs: tuple[str, ...]
    branch_ids: tuple[str, ...]
    document_kind: str
    fiscal_periods: tuple[str, ...]
    physical_node_count: int
    searchable_leaf_count: int


@dataclass(frozen=True)
class PhysicalExternalRoute:
    route_id: str
    canonical_issuer_id: str
    canonical_domain: str
    source_role: str
    source_family_refs: tuple[str, ...]
    branch_ids: tuple[str, ...]
    official_url: str
    foundation_required_family_match: bool


@dataclass(frozen=True)
class ValidatedPhysicalRouteCatalog:
    catalog_path: Path
    file_sha256: str
    catalog_digest: str
    status: str
    owner_review_required: bool
    execution_authority: bool
    case_id: str
    case_key: str
    research_as_of: str
    foundation_digest: str
    local_nodes_ref: str
    local_nodes_sha256: str
    expected_physical_node_count: int
    expected_searchable_leaf_count: int
    expected_parent_section_count: int
    external_manifest_ref: str
    external_manifest_sha256: str
    external_manifest_digest: str
    local_routes: tuple[PhysicalLocalRoute, ...]
    external_routes: tuple[PhysicalExternalRoute, ...]
    entity_aliases: tuple[tuple[str, tuple[str, ...]], ...]
    blocking_owner_review_ids: tuple[str, ...]

    def aliases_for(self, canonical_entity_id: str) -> tuple[str, ...]:
        aliases = dict(self.entity_aliases).get(canonical_entity_id)
        if aliases is None:
            raise CurrentCapabilityInventoryError(
                f"physical_catalog_entity_alias_missing:{canonical_entity_id}"
            )
        return aliases


def _file_sha(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha(value: Any, code: str) -> str:
    if not isinstance(value, str) or not _SHA_RE.fullmatch(value.strip().lower()):
        raise CurrentCapabilityInventoryError(code)
    return value.strip().lower()


def _duplicate_safe_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CurrentCapabilityInventoryError(f"json_duplicate_key:{key}")
        result[key] = value
    return result


def _non_finite(value: str) -> None:
    raise CurrentCapabilityInventoryError(f"json_non_finite_number:{value}")


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_duplicate_safe_object,
            parse_constant=_non_finite,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CurrentCapabilityInventoryError(f"json_read_failed:{path}") from exc
    if not isinstance(value, dict):
        raise CurrentCapabilityInventoryError("json_root_not_object")
    return value


def _keys(value: Mapping[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        raise CurrentCapabilityInventoryError(code)


def _required(value: Mapping[str, Any], names: Iterable[str], code: str) -> None:
    if not set(names).issubset(value):
        raise CurrentCapabilityInventoryError(code)


def _text(value: Any, code: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CurrentCapabilityInventoryError(code)
    return value.strip()


def _count(value: Any, code: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise CurrentCapabilityInventoryError(code)
    return value


def _strings(value: Any, code: str, *, empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not empty):
        raise CurrentCapabilityInventoryError(code)
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise CurrentCapabilityInventoryError(code)
    items = tuple(sorted(item.strip() for item in value))
    if len(items) != len(set(items)):
        raise CurrentCapabilityInventoryError(f"{code}_duplicate")
    return items


def _canonical_self_digest(value: Mapping[str, Any], field: str) -> str:
    return canonical_digest({key: item for key, item in value.items() if key != field})


def _iso_datetime(value: Any, code: str) -> str:
    text = _text(value, code)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CurrentCapabilityInventoryError(code) from exc
    if parsed.tzinfo is None:
        raise CurrentCapabilityInventoryError(f"{code}_timezone")
    return text


def _optional_date(value: Any, code: str) -> None:
    if value in {None, ""}:
        return
    try:
        date.fromisoformat(_text(value, code))
    except ValueError as exc:
        raise CurrentCapabilityInventoryError(code) from exc


def _host(url: Any, code: str) -> str:
    parsed = urlparse(_text(url, code))
    if parsed.scheme not in {"http", "https"} or parsed.hostname is None:
        raise CurrentCapabilityInventoryError(code)
    return parsed.hostname.casefold()


def _forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in _FORBIDDEN_CATALOG_KEYS:
                raise CurrentCapabilityInventoryError(
                    f"physical_catalog_forbidden_field:{path}.{key}"
                )
            _forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _forbidden_keys(child, f"{path}[{index}]")


def load_physical_route_catalog(
    path: str | Path,
    *,
    expected_file_sha256: str,
    expected_catalog_digest: str | None = None,
) -> ValidatedPhysicalRouteCatalog:
    """Validate the physical catalog, while preserving its non-executable state."""

    catalog_path = Path(path).expanduser().resolve(strict=True)
    actual_sha = _file_sha(catalog_path)
    if actual_sha != _sha(expected_file_sha256, "catalog_expected_sha_invalid"):
        raise CurrentCapabilityInventoryError("physical_catalog_file_sha256_mismatch")
    raw = _json(catalog_path)
    _keys(raw, _TOP_KEYS, "physical_catalog_top_schema_mismatch")
    _forbidden_keys(raw)
    if raw["schema_version"] != _CATALOG_SCHEMA or raw["status"] != _CATALOG_STATUS:
        raise CurrentCapabilityInventoryError("physical_catalog_schema_or_status_mismatch")
    _iso_datetime(raw["recorded_at"], "physical_catalog_recorded_at_invalid")
    research_as_of = _iso_datetime(
        raw["research_as_of"], "physical_catalog_research_as_of_invalid"
    )[:10]
    digest = _sha(raw["catalog_digest"], "physical_catalog_digest_invalid")
    if _canonical_self_digest(raw, "catalog_digest") != digest:
        raise CurrentCapabilityInventoryError("physical_catalog_self_digest_mismatch")
    if expected_catalog_digest is not None and digest != _sha(
        expected_catalog_digest, "catalog_expected_digest_invalid"
    ):
        raise CurrentCapabilityInventoryError("physical_catalog_expected_digest_mismatch")

    authority = raw["authority"]
    _required(
        authority,
        {"answer_free", "owner_review_required", "execution_authority",
         "candidate_is_not_evidence", "numeric_fact_authority",
         "evidence_admission_authority"},
        "physical_catalog_authority_schema_mismatch",
    )
    if any(authority.get(key) is not True for key in (
        "answer_free", "owner_review_required", "candidate_is_not_evidence",
    )) or any(authority.get(key) is not False for key in (
        "execution_authority", "numeric_fact_authority", "evidence_admission_authority",
    )):
        raise CurrentCapabilityInventoryError("physical_catalog_authority_mismatch")
    if raw["digest_contract"] != {
        "algorithm": "sha256",
        "canonicalization": "utf8_json_ensure_ascii_false_sort_keys_true_separators_comma_colon",
        "self_digest_field": "catalog_digest",
        "self_digest_field_excluded_from_digest": True,
    }:
        raise CurrentCapabilityInventoryError("physical_catalog_digest_contract_mismatch")

    bindings = raw["input_bindings"]
    _required(bindings, {"foundation", "structured_local_nodes",
                         "external_candidate_manifest", "reviewed_evidence_topic_inventory"},
              "physical_catalog_bindings_incomplete")
    foundation = bindings["foundation"]
    local_binding = bindings["structured_local_nodes"]
    external_binding = bindings["external_candidate_manifest"]
    reviewed_binding = bindings["reviewed_evidence_topic_inventory"]
    if (
        foundation.get("expected_question_branch_count") != 9
        or foundation.get("expected_source_family_count") != 11
        or local_binding.get("schema_version") != _NODE_SCHEMA
        or external_binding.get("schema_version") != _MANIFEST_SCHEMA
        or reviewed_binding.get("base_item_count") != 55
        or reviewed_binding.get("overlay_item_count") != 6
        or reviewed_binding.get("composite_item_count") != 61
    ):
        raise CurrentCapabilityInventoryError("physical_catalog_binding_contract_mismatch")

    aliases: dict[str, tuple[str, ...]] = {}
    alias_owner: dict[str, str] = {}
    alias_rows = raw["entity_aliases"]
    if not isinstance(alias_rows, list):
        raise CurrentCapabilityInventoryError("physical_catalog_aliases_invalid")
    for row in alias_rows:
        if not isinstance(row, dict):
            raise CurrentCapabilityInventoryError("physical_catalog_alias_row_invalid")
        _keys(row, {"canonical_entity_id", "entity_kind", "aliases", "canonical_domains"},
              "physical_catalog_alias_row_schema_mismatch")
        canonical = _text(row["canonical_entity_id"], "catalog_alias_id_invalid")
        if canonical in aliases:
            raise CurrentCapabilityInventoryError("catalog_alias_id_duplicate")
        values = tuple(sorted({canonical, *_strings(row["aliases"], "catalog_aliases_invalid")}))
        _strings(row["canonical_domains"], "catalog_alias_domains_invalid")
        for alias in values:
            key = alias.casefold()
            if key in alias_owner and alias_owner[key] != canonical:
                raise CurrentCapabilityInventoryError(f"catalog_alias_ambiguous:{alias}")
            alias_owner[key] = canonical
        aliases[canonical] = values

    local_routes: list[PhysicalLocalRoute] = []
    for row in raw["local_routes"]:
        if not isinstance(row, dict):
            raise CurrentCapabilityInventoryError("catalog_local_route_invalid")
        _keys(row, _LOCAL_ROUTE_KEYS, "catalog_local_route_schema_mismatch")
        route = PhysicalLocalRoute(
            route_id=_text(row["route_id"], "catalog_local_route_id_invalid"),
            canonical_issuer_id=_text(row["canonical_issuer_id"], "catalog_local_issuer_invalid"),
            canonical_domain=_text(row["canonical_domain"], "catalog_local_domain_invalid").casefold(),
            source_role=_text(row["source_role"], "catalog_local_role_invalid"),
            source_family_refs=_strings(row["source_family_refs"], "catalog_local_family_invalid"),
            branch_ids=_strings(row["branch_ids"], "catalog_local_branch_invalid"),
            document_kind=_text(row["document_kind"], "catalog_local_kind_invalid"),
            fiscal_periods=_strings(row["fiscal_periods"], "catalog_local_period_invalid", empty=True),
            physical_node_count=_count(row["physical_node_count"], "catalog_local_physical_count_invalid"),
            searchable_leaf_count=_count(row["searchable_leaf_count"], "catalog_local_leaf_count_invalid"),
        )
        if len(route.source_family_refs) != 1 or route.canonical_issuer_id not in aliases:
            raise CurrentCapabilityInventoryError(f"catalog_local_route_unbound:{route.route_id}")
        local_routes.append(route)

    external_routes: list[PhysicalExternalRoute] = []
    for row in raw["external_routes"]:
        if not isinstance(row, dict):
            raise CurrentCapabilityInventoryError("catalog_external_route_invalid")
        _keys(row, _EXTERNAL_ROUTE_KEYS, "catalog_external_route_schema_mismatch")
        if not isinstance(row["foundation_required_family_match"], bool):
            raise CurrentCapabilityInventoryError("catalog_external_family_flag_invalid")
        route = PhysicalExternalRoute(
            route_id=_text(row["route_id"], "catalog_external_route_id_invalid"),
            canonical_issuer_id=_text(row["canonical_issuer_id"], "catalog_external_issuer_invalid"),
            canonical_domain=_text(row["canonical_domain"], "catalog_external_domain_invalid").casefold(),
            source_role=_text(row["source_role"], "catalog_external_role_invalid"),
            source_family_refs=_strings(row["source_family_refs"], "catalog_external_family_invalid"),
            branch_ids=_strings(row["branch_ids"], "catalog_external_branch_invalid"),
            official_url=_text(row["official_url"], "catalog_external_url_invalid"),
            foundation_required_family_match=row["foundation_required_family_match"],
        )
        if (len(route.source_family_refs) != 1
                or route.canonical_issuer_id not in aliases
                or _host(route.official_url, "catalog_external_url_invalid") != route.canonical_domain):
            raise CurrentCapabilityInventoryError(f"catalog_external_route_unbound:{route.route_id}")
        external_routes.append(route)

    local_routes.sort(key=lambda row: row.route_id)
    external_routes.sort(key=lambda row: row.route_id)
    route_ids = [row.route_id for row in (*local_routes, *external_routes)]
    counts = raw["catalog_counts"]
    if (
        len(route_ids) != len(set(route_ids))
        or counts.get("local_route_count") != len(local_routes)
        or counts.get("external_route_count") != len(external_routes)
        or counts.get("total_route_count") != len(route_ids)
        or counts.get("local_physical_node_count") != sum(row.physical_node_count for row in local_routes)
        or counts.get("local_searchable_leaf_count") != sum(row.searchable_leaf_count for row in local_routes)
        or counts.get("entity_alias_record_count") != len(aliases)
        or counts.get("reviewed_topic_count") != len(raw["reviewed_topic_branch_mapping"])
        or local_binding.get("expected_route_count") != len(local_routes)
        or local_binding.get("expected_physical_node_count") != counts.get("local_physical_node_count")
        or local_binding.get("expected_searchable_leaf_count") != counts.get("local_searchable_leaf_count")
        or external_binding.get("expected_route_count") != len(external_routes)
    ):
        raise CurrentCapabilityInventoryError("physical_catalog_count_or_uniqueness_mismatch")
    parent_count = _count(local_binding.get("expected_parent_section_count"),
                          "catalog_parent_count_invalid")
    if parent_count + counts["local_searchable_leaf_count"] != counts["local_physical_node_count"]:
        raise CurrentCapabilityInventoryError("physical_catalog_parent_count_mismatch")

    blockers = []
    for item in raw["owner_review_items"]:
        if not isinstance(item, dict):
            raise CurrentCapabilityInventoryError("catalog_owner_review_item_invalid")
        _required(item, {"review_id", "state"}, "catalog_owner_review_item_incomplete")
        if item["state"] in {"open", "owner_review_candidate"}:
            blockers.append(_text(item["review_id"], "catalog_review_id_invalid"))
    return ValidatedPhysicalRouteCatalog(
        catalog_path=catalog_path, file_sha256=actual_sha, catalog_digest=digest,
        status=raw["status"], owner_review_required=authority["owner_review_required"],
        execution_authority=authority["execution_authority"],
        case_id=_text(raw["case_id"], "catalog_case_id_invalid"),
        case_key=_text(raw["case_key"], "catalog_case_key_invalid"),
        research_as_of=research_as_of,
        foundation_digest=_sha(foundation.get("sha256"), "catalog_foundation_sha_invalid"),
        local_nodes_ref=_text(local_binding.get("ref"), "catalog_nodes_ref_invalid"),
        local_nodes_sha256=_sha(local_binding.get("sha256"), "catalog_nodes_sha_invalid"),
        expected_physical_node_count=counts["local_physical_node_count"],
        expected_searchable_leaf_count=counts["local_searchable_leaf_count"],
        expected_parent_section_count=parent_count,
        external_manifest_ref=_text(external_binding.get("ref"), "catalog_manifest_ref_invalid"),
        external_manifest_sha256=_sha(external_binding.get("sha256"), "catalog_manifest_sha_invalid"),
        external_manifest_digest=_sha(external_binding.get("manifest_digest"),
                                      "catalog_manifest_digest_invalid"),
        local_routes=tuple(local_routes), external_routes=tuple(external_routes),
        entity_aliases=tuple(sorted(aliases.items())),
        blocking_owner_review_ids=tuple(sorted(blockers)),
    )


def _foundation_maps(
    source_families: Sequence[Mapping[str, Any]],
    question_branches: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    authorities = {
        _text(row.get("source_family_id"), "foundation_family_id_invalid"):
        _text(row.get("authority"), "foundation_family_authority_invalid")
        for row in source_families
    }
    requirements = {
        _text(row.get("branch_id"), "foundation_branch_id_invalid"):
        _strings(row.get("required_source_families"), "foundation_required_families_invalid")
        for row in question_branches
    }
    if len(authorities) != len(source_families) or len(requirements) != len(question_branches):
        raise CurrentCapabilityInventoryError("foundation_mapping_duplicate")
    expected = {branch: tuple(sorted(families))
                for branch, families in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE}
    families = {family for values in expected.values() for family in values}
    if requirements != expected or set(authorities) != families:
        raise CurrentCapabilityInventoryError("foundation_mapping_mismatch")
    return authorities, requirements


def build_source_family_catalog(
    catalog: ValidatedPhysicalRouteCatalog,
    *,
    foundation_source_families: Sequence[Mapping[str, Any]],
    foundation_question_branches: Sequence[Mapping[str, Any]],
    case_version: str = "FIN-0.1.3",
    local_cardinality_ceiling: int = 100_000,
) -> SourceFamilyCatalog:
    """Build all 11 policy families; never infer support from route availability."""

    if local_cardinality_ceiling < 1:
        raise CurrentCapabilityInventoryError("local_cardinality_ceiling_invalid")
    authorities, requirements = _foundation_maps(
        foundation_source_families, foundation_question_branches
    )
    memberships = {family: set() for family in authorities}
    for branch, families in requirements.items():
        for family in families:
            memberships[family].add(branch)
    for route in (*catalog.local_routes, *catalog.external_routes):
        family = route.source_family_refs[0]
        if family not in memberships:
            raise CurrentCapabilityInventoryError(f"catalog_route_family_unknown:{route.route_id}")
        if (isinstance(route, PhysicalLocalRoute) or route.foundation_required_family_match) \
                and not set(route.branch_ids).issubset(memberships[family]):
            raise CurrentCapabilityInventoryError(f"catalog_route_branch_mismatch:{route.route_id}")

    entries = []
    for family in sorted(authorities):
        body = {
            "source_family_ref": family,
            "coverage_obligation_ids": tuple(sorted(memberships[family])),
            "supported_route_kinds": _POLICY_ROUTE_KINDS,
            "semantic_role_refs": (authorities[family],),
            "authority_refs": ("authority:primary-read", "authority:reviewed-read"),
            "local_cardinality_ceiling": local_cardinality_ceiling,
        }
        entries.append(SourceFamilyCatalogEntry(**body, entry_digest=canonical_digest(body)))
    body = {
        "contract_version": "1.2",
        "catalog_id": f"catalog:dell:physical:{catalog.catalog_digest[:24]}",
        "case_id": catalog.case_id, "case_version": case_version,
        "research_as_of": catalog.research_as_of,
        "foundation_digest": catalog.foundation_digest,
        "entries": tuple(entries), "answer_free": True,
    }
    return SourceFamilyCatalog(**body, catalog_digest=canonical_digest(body))


def build_local_inventory_buckets_from_nodes(
    *,
    nodes_path: str | Path,
    catalog: ValidatedPhysicalRouteCatalog,
    source_family_catalog: SourceFamilyCatalog,
    semantic_role_by_source_family: Mapping[str, str],
) -> tuple[LocalInventoryBucket, ...]:
    """Validate every node but retain only searchable leaf identities."""

    path = Path(nodes_path).expanduser().resolve(strict=True)
    artifact_sha = _file_sha(path)
    if artifact_sha != catalog.local_nodes_sha256:
        raise CurrentCapabilityInventoryError("local_nodes_file_sha256_mismatch")
    routes = {row.route_id: row for row in catalog.local_routes}
    families = {row.source_family_ref: row for row in source_family_catalog.entries}
    records: list[LocalInventoryRecord] = []
    route_physical: Counter[str] = Counter()
    route_leaves: Counter[str] = Counter()
    parent_route: dict[str, str] = {}
    leaf_parents: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                node = json.loads(line, object_pairs_hook=_duplicate_safe_object,
                                  parse_constant=_non_finite)
            except (json.JSONDecodeError, CurrentCapabilityInventoryError) as exc:
                raise CurrentCapabilityInventoryError(f"local_node_json_invalid:{line_no}") from exc
            if not isinstance(node, dict) or not _NODE_BASE_KEYS.issubset(node) \
                    or not set(node).issubset(_NODE_ALLOWED_KEYS):
                raise CurrentCapabilityInventoryError(f"local_node_schema_mismatch:{line_no}")
            if node["schema_version"] != _NODE_SCHEMA:
                raise CurrentCapabilityInventoryError(f"local_node_version_mismatch:{line_no}")
            route_id = _text(node["route_id"], f"local_node_route_invalid:{line_no}")
            route = routes.get(route_id)
            if route is None:
                raise CurrentCapabilityInventoryError(f"local_node_route_unknown:{route_id}")
            node_id = _text(node["node_id"], f"local_node_id_invalid:{line_no}")
            if node_id in seen:
                raise CurrentCapabilityInventoryError(f"local_node_duplicate:{node_id}")
            seen.add(node_id)
            route_physical[route_id] += 1
            period = None if node["fiscal_period"] in {None, ""} else _text(
                node["fiscal_period"], f"local_node_period_invalid:{line_no}"
            )
            if (node["issuer_id"] != route.canonical_issuer_id
                    or node["source_role"] != route.source_role
                    or node["document_kind"] != route.document_kind
                    or ({period} if period else set()) != set(route.fiscal_periods)
                    or _host(node["stable_url"], "local_node_url_invalid") != route.canonical_domain):
                raise CurrentCapabilityInventoryError(f"local_node_route_metadata_mismatch:{node_id}")
            _optional_date(node["publication_date"], "local_node_publication_date_invalid")
            _optional_date(node["period_end"], "local_node_period_end_invalid")
            if (node["candidate_is_not_evidence"] is not True
                    or node["citation_eligible"] is not False
                    or node["numeric_authority"] is not False):
                raise CurrentCapabilityInventoryError(f"local_node_authority_mismatch:{node_id}")
            if not isinstance(node["content"], str) or not isinstance(node["model_text"], str):
                raise CurrentCapabilityInventoryError(f"local_node_text_invalid:{node_id}")
            content_sha = _sha(node["content_sha256"], "local_node_content_sha_invalid")
            if sha256(node["content"].encode("utf-8")).hexdigest() != content_sha:
                raise CurrentCapabilityInventoryError(f"local_node_content_sha_mismatch:{node_id}")
            _sha(node["raw_body_sha256"], "local_node_raw_body_sha_invalid")
            parent_id = _text(node["parent_section_id"], "local_node_parent_invalid")
            lane = node["lane"]
            if lane == "parent":
                if node["node_kind"] != "section" or parent_id != node_id:
                    raise CurrentCapabilityInventoryError(f"local_parent_shape_invalid:{node_id}")
                parent_route[node_id] = route_id
                continue
            if lane == "prose_leaf" and node["node_kind"] in {"chunk", "mixed_prose_span"}:
                surfaces = ("prose",)
            elif lane == "table_leaf" and node["node_kind"] == "table":
                surfaces = ("table",)
            else:
                raise CurrentCapabilityInventoryError(f"local_leaf_shape_invalid:{node_id}")
            leaf_parents.append((node_id, parent_id, route_id))
            route_leaves[route_id] += 1
            family = route.source_family_refs[0]
            semantic_role = semantic_role_by_source_family.get(family)
            entry = families.get(family)
            if (entry is None or not isinstance(semantic_role, str)
                    or (semantic_role.strip(),) != entry.semantic_role_refs):
                raise CurrentCapabilityInventoryError(f"local_semantic_role_unbound:{family}")
            body = {
                "object_ref": node_id, "source_family_ref": family,
                "branch_refs": route.branch_ids,
                "entity_refs": catalog.aliases_for(route.canonical_issuer_id),
                "canonical_issuer_id": route.canonical_issuer_id,
                "period_refs": (() if period is None else (period,)),
                "fiscal_period": period, "semantic_role_refs": (semantic_role.strip(),),
                "source_role": route.source_role, "route_id": route_id, "lane": lane,
                "content_surface_refs": surfaces,
                "authority_refs": ("authority:primary-read",),
                "source_artifact_digest": artifact_sha,
                "source_object_digest": content_sha,
            }
            records.append(LocalInventoryRecord(**body, metadata_digest=canonical_digest(body)))

    if any(parent_route.get(parent) != route for _, parent, route in leaf_parents):
        raise CurrentCapabilityInventoryError("local_leaf_parent_binding_mismatch")
    if (len(seen) != catalog.expected_physical_node_count
            or len(records) != catalog.expected_searchable_leaf_count
            or len(parent_route) != catalog.expected_parent_section_count
            or set(route_physical) != set(routes)):
        raise CurrentCapabilityInventoryError("local_node_global_count_mismatch")
    for route_id, route in routes.items():
        if (route_physical[route_id] != route.physical_node_count
                or route_leaves[route_id] != route.searchable_leaf_count):
            raise CurrentCapabilityInventoryError(f"local_node_route_count_mismatch:{route_id}")
    return build_local_inventory_buckets(
        records, catalog=source_family_catalog,
        expected_source_artifact_digest=artifact_sha,
    )


def _external_periods(result: Mapping[str, Any]) -> tuple[str, ...]:
    identity = result.get("source_identity")
    if not isinstance(identity, dict):
        raise CurrentCapabilityInventoryError("external_source_identity_invalid")
    value = identity.get("source_period")
    if isinstance(value, str) and re.search(
        r"(?i)(?:\bFY\s*\d|\b\dQ\d{2}\b|\bQ[1-4]\b)", value
    ):
        return (value.strip(),)
    return ()


def build_external_inventory_buckets_from_manifest(
    *, manifest_path: str | Path, catalog: ValidatedPhysicalRouteCatalog,
    source_family_catalog: SourceFamilyCatalog,
) -> tuple[ExternalInventoryBucket, ...]:
    """Validate r12 and expose exact-URL selector buckets, never its text."""

    path = Path(manifest_path).expanduser().resolve(strict=True)
    artifact_sha = _file_sha(path)
    if artifact_sha != catalog.external_manifest_sha256:
        raise CurrentCapabilityInventoryError("external_manifest_file_sha256_mismatch")
    manifest = _json(path)
    digest = _sha(manifest.get("manifest_digest"), "external_manifest_digest_invalid")
    if (manifest.get("schema_version") != _MANIFEST_SCHEMA
            or _canonical_self_digest(manifest, "manifest_digest") != digest
            or digest != catalog.external_manifest_digest
            or manifest.get("status") != "PASS"
            or manifest.get("candidate_is_not_evidence") is not True
            or manifest.get("evidence_admission_authorized") is not False
            or manifest.get("mcp_promotion_authorized") is not False
            or manifest.get("model_calls") != 0 or manifest.get("paid_calls") != 0):
        raise CurrentCapabilityInventoryError("external_manifest_contract_mismatch")
    routes = {row.route_id: row for row in catalog.external_routes}
    results = manifest.get("route_results")
    if not isinstance(results, list) or any(
        manifest.get(key) != len(routes)
        for key in ("declared_route_count", "attempted_route_count", "passed_route_count")
    ):
        raise CurrentCapabilityInventoryError("external_manifest_count_mismatch")
    by_id: dict[str, Mapping[str, Any]] = {}
    for result in results:
        if not isinstance(result, dict):
            raise CurrentCapabilityInventoryError("external_route_result_invalid")
        route_id = _text(result.get("route_id"), "external_route_id_invalid")
        result_digest = _sha(result.get("route_result_digest"),
                             "external_route_result_digest_invalid")
        if route_id in by_id or _canonical_self_digest(result, "route_result_digest") != result_digest:
            raise CurrentCapabilityInventoryError(f"external_route_result_invalid:{route_id}")
        by_id[route_id] = result
    if set(by_id) != set(routes):
        raise CurrentCapabilityInventoryError("external_route_coverage_mismatch")

    family_refs = {entry.source_family_ref for entry in source_family_catalog.entries}
    buckets = []
    for route_id in sorted(routes):
        route, result = routes[route_id], by_id[route_id]
        identity = result.get("source_identity")
        if not isinstance(identity, dict) or (
            result.get("status") != "PASS" or result.get("failure_code") is not None
            or result.get("exact_url_bound") is not True
            or result.get("candidate_is_not_evidence") is not True
            or result.get("source_capture_authority") is not False
            or result.get("admission_required_before_citation") is not True
            or result.get("model_calls") != 0
            or result.get("branch_id") not in route.branch_ids
            or result.get("official_url") != route.official_url
            or str(identity.get("official_domain", "")).casefold() != route.canonical_domain
        ):
            raise CurrentCapabilityInventoryError(f"external_route_contract_mismatch:{route_id}")
        if route.source_family_refs[0] not in family_refs:
            raise CurrentCapabilityInventoryError(f"external_route_family_unbound:{route_id}")
        body = {
            "bucket_id": f"external:{route_id}",
            "source_family_ref": route.source_family_refs[0],
            "coverage_obligation_ids": route.branch_ids,
            "external_route_ref": route_id,
            "canonical_entity_id": route.canonical_issuer_id,
            "entity_refs": catalog.aliases_for(route.canonical_issuer_id),
            "period_refs": _external_periods(result),
            "domain_allowlist": (route.canonical_domain,),
            "authority_refs": ("authority:primary-read",),
            "available_not_before": None, "available_not_after": None,
            "source_artifact_digest": artifact_sha, "eligible_object_count": 1,
            "foundation_required_family_match": route.foundation_required_family_match,
        }
        buckets.append(ExternalInventoryBucket(**body, bucket_digest=canonical_digest(body)))
    return tuple(buckets)


def build_s2_capability_bucket_from_verified_result(
    *, result_path: str | Path, expected_result_sha256: str,
    expected_result_digest: str = EXPECTED_S2_RESULT_DIGEST,
    expected_mart_sha256: str | None = None,
    expected_observation_count: int | None = None,
    expected_entity_count: int | None = None,
    expected_metric_count: int | None = None,
    planner_capabilities: PlannerToolCapabilityProjection,
    catalog: ValidatedPhysicalRouteCatalog,
) -> S2CapabilityBucket:
    """Bind the existing S2 capability projection; never duplicate fact rows."""

    path = Path(result_path).expanduser().resolve(strict=True)
    artifact_sha = _file_sha(path)
    if artifact_sha != _sha(expected_result_sha256, "s2_expected_result_sha_invalid"):
        raise CurrentCapabilityInventoryError("s2_result_file_sha256_mismatch")
    result = _json(path)
    result_digest = _sha(result.get("result_digest"), "s2_result_digest_invalid")
    counts, storage, acceptance = result.get("counts"), result.get("storage"), result.get("acceptance")
    if not all(isinstance(value, dict) for value in (counts, storage, acceptance)):
        raise CurrentCapabilityInventoryError("s2_result_shape_invalid")
    assert isinstance(counts, dict) and isinstance(storage, dict) and isinstance(acceptance, dict)
    observations = _count(counts.get("observations"), "s2_observation_count_invalid")
    by_ticker = counts.get("by_ticker")
    observed_metrics = tuple(sorted(
        metric.metric_id for metric in planner_capabilities.finance.metrics
        if metric.observed_tickers
    ))
    mart_sha = _sha(storage.get("sqlite_sha256"), "s2_mart_sha_invalid")
    if (result.get("schema_version") != _S2_SCHEMA
            or _canonical_self_digest(result, "result_digest") != result_digest
            or result_digest
            != _sha(expected_result_digest, "s2_expected_result_digest_invalid")
            or result.get("status") != "s2_company_financial_fact_mart_engineering_pass"
            or not isinstance(by_ticker, dict)
            or observations != sum(_count(value, "s2_ticker_count_invalid") for value in by_ticker.values())
            or counts.get("tickers") != len(planner_capabilities.finance.supported_tickers)
            or counts.get("metrics") != len(observed_metrics)
            or mart_sha != planner_capabilities.mart_sha256
            or (
                expected_mart_sha256 is not None
                and mart_sha
                != _sha(expected_mart_sha256, "s2_expected_mart_sha_invalid")
            )
            or (
                expected_observation_count is not None
                and observations != expected_observation_count
            )
            or (
                expected_entity_count is not None
                and counts.get("tickers") != expected_entity_count
            )
            or (
                expected_metric_count is not None
                and counts.get("metrics") != expected_metric_count
            )
            or acceptance.get("all_qrels_exact") is not True
            or acceptance.get("mutations_pass") is not True
            or acceptance.get("network_calls") != 0 or acceptance.get("model_calls") != 0
            or acceptance.get("candidate_or_metric_row_grants_numeric_authority") is not False):
        raise CurrentCapabilityInventoryError("s2_result_capability_binding_mismatch")
    alias_lookup = {alias.casefold(): canonical
                    for canonical, aliases in catalog.entity_aliases for alias in aliases}
    entities = []
    for ticker in planner_capabilities.finance.supported_tickers:
        canonical = alias_lookup.get(ticker.casefold())
        if canonical is None:
            raise CurrentCapabilityInventoryError(f"s2_entity_alias_missing:{ticker}")
        entities.append(canonical)
    body = {
        "bucket_id": f"s2:planner-capability:{planner_capabilities.projection_digest[:24]}",
        "entity_refs": tuple(sorted(set(entities))), "metric_refs": observed_metrics,
        "period_refs": tuple(sorted(
            f"period_role:{role}" for role in planner_capabilities.finance.canonical_granularities
        )),
        "authority_refs": ("s2_companyfacts_exact_period_lookup",),
        "source_artifact_digest": artifact_sha,
        "eligible_observation_count": observations,
    }
    return S2CapabilityBucket(**body, bucket_digest=canonical_digest(body))


def _binding(kind: str, ref: str, digest: str, count: int,
             catalog_digest: str, owner_decision_digest: str) -> CapabilityArtifactBinding:
    receipt = canonical_digest({
        "adapter": "dell_current_capability_inventory", "capability_kind": kind,
        "artifact_digest": digest, "validated_object_count": count,
        "physical_catalog_digest": catalog_digest,
        "owner_data_gate_decision_digest": owner_decision_digest,
    })
    body = {
        "capability_kind": kind, "artifact_ref": ref, "artifact_digest": digest,
        "validated_object_count": count,
        "validation_receipt_ref": f"receipt:current-capability:{kind}:{receipt[:24]}",
        "validation_receipt_digest": receipt,
    }
    return CapabilityArtifactBinding(**body, binding_digest=canonical_digest(body))


def build_current_capability_inventory(
    *, physical_catalog_path: str | Path, expected_physical_catalog_sha256: str,
    foundation_source_families: Sequence[Mapping[str, Any]],
    foundation_question_branches: Sequence[Mapping[str, Any]],
    local_nodes_path: str | Path, external_manifest_path: str | Path,
    s2_result_path: str | Path, expected_s2_result_sha256: str,
    planner_capabilities: PlannerToolCapabilityProjection,
    reviewed_index: ReviewedEvidenceIndexV1_2, snapshot_id: str,
    owner_data_gate_decision: DellOwnerDataGateDecision | None = None,
    case_version: str = "FIN-0.1.3",
) -> CapabilityInventorySnapshot:
    """Compose the exact inventory only under the separate Owner decision."""

    catalog = load_physical_route_catalog(
        physical_catalog_path, expected_file_sha256=expected_physical_catalog_sha256
    )
    if owner_data_gate_decision is None:
        blockers = ",".join(catalog.blocking_owner_review_ids) or "catalog_authority"
        raise CurrentCapabilityInventoryError(f"physical_catalog_not_execution_authority:{blockers}")
    try:
        decision = validate_trusted_dell_owner_data_gate_decision(
            owner_data_gate_decision
        )
    except DellOwnerDataGateError as exc:
        raise CurrentCapabilityInventoryError(str(exc)) from exc
    _validate_owner_data_gate_for_physical_catalog(catalog, decision)
    bound = decision.bound_inputs
    if (
        _sha(expected_s2_result_sha256, "s2_expected_result_sha_invalid")
        != bound.s2_result_sha256
        or planner_capabilities.mart_sha256 != bound.s2_mart_sha256
    ):
        raise CurrentCapabilityInventoryError(
            "owner_data_gate_s2_runtime_binding_mismatch"
        )
    family_catalog = build_source_family_catalog(
        catalog, foundation_source_families=foundation_source_families,
        foundation_question_branches=foundation_question_branches,
        case_version=case_version,
    )
    semantic_roles, _ = _foundation_maps(
        foundation_source_families, foundation_question_branches
    )
    local = build_local_inventory_buckets_from_nodes(
        nodes_path=local_nodes_path, catalog=catalog,
        source_family_catalog=family_catalog,
        semantic_role_by_source_family=semantic_roles,
    )
    external = build_external_inventory_buckets_from_manifest(
        manifest_path=external_manifest_path, catalog=catalog,
        source_family_catalog=family_catalog,
    )
    s2 = build_s2_capability_bucket_from_verified_result(
        result_path=s2_result_path, expected_result_sha256=expected_s2_result_sha256,
        expected_result_digest=bound.s2_result_digest,
        expected_mart_sha256=bound.s2_mart_sha256,
        expected_observation_count=bound.s2_observation_count,
        expected_entity_count=bound.s2_entity_count,
        expected_metric_count=bound.s2_metric_count,
        planner_capabilities=planner_capabilities, catalog=catalog,
    )
    reviewed = ReviewedEvidenceIndexV1_2.model_validate(reviewed_index.model_dump(mode="python"))
    reviewed_count = decision.reviewed_evidence_decision.executable_item_count
    if reviewed.indexed_item_count != reviewed_count:
        raise CurrentCapabilityInventoryError("current_reviewed_index_count_mismatch")
    bindings = tuple(sorted((
        _binding("local_candidate", catalog.local_nodes_ref, catalog.local_nodes_sha256, 890, catalog.catalog_digest, decision.decision_digest),
        _binding("reviewed_evidence", reviewed.index_id, reviewed.source_pack_digest, reviewed_count, catalog.catalog_digest, decision.decision_digest),
        _binding("s2_numeric_fact", bound.s2_result_ref, s2.source_artifact_digest, bound.s2_observation_count, catalog.catalog_digest, decision.decision_digest),
        _binding("external_source", catalog.external_manifest_ref, catalog.external_manifest_sha256, 12, catalog.catalog_digest, decision.decision_digest),
    ), key=lambda row: row.capability_kind))
    body = {
        "contract_version": "1.2", "snapshot_id": snapshot_id,
        "case_id": family_catalog.case_id, "case_version": family_catalog.case_version,
        "research_as_of": family_catalog.research_as_of,
        "foundation_digest": family_catalog.foundation_digest,
        "source_family_catalog": family_catalog, "component_bindings": bindings,
        "local_buckets": tuple(sorted(local, key=lambda row: row.bucket_id)),
        "reviewed_evidence_index": reviewed, "s2_buckets": (s2,),
        "external_buckets": tuple(sorted(external, key=lambda row: row.bucket_id)),
        "local_candidate_count": sum(row.eligible_object_count for row in local),
        "reviewed_evidence_count": reviewed.indexed_item_count,
        "s2_observation_count": s2.eligible_observation_count,
        "external_object_count": sum(row.eligible_object_count for row in external),
        "owner_data_gate_decision_digest": decision.decision_digest,
        "answer_free": True,
    }
    return CapabilityInventorySnapshot(**body, inventory_snapshot_digest=canonical_digest(body))


def _validate_owner_data_gate_for_physical_catalog(
    catalog: ValidatedPhysicalRouteCatalog,
    decision: DellOwnerDataGateDecision,
) -> None:
    bound = decision.bound_inputs
    route_decision = decision.route_catalog_decision
    route_ids = tuple(
        sorted(
            row.route_id
            for row in (*catalog.local_routes, *catalog.external_routes)
        )
    )
    if not (
        decision.authority.physical_catalog_runtime_consumption_authorized
        and decision.authority.capability_inventory_composition_authorized
        and catalog.file_sha256 == bound.physical_catalog_sha256
        and catalog.catalog_digest == bound.physical_catalog_digest
        and catalog.case_id == decision.case_id
        and catalog.case_key == decision.case_key
        and route_ids == route_decision.accepted_route_ids
        and len(catalog.local_routes) == route_decision.accepted_local_route_count
        and len(catalog.external_routes)
        == route_decision.accepted_external_route_count
        and len(route_ids) == route_decision.accepted_total_route_count
    ):
        raise CurrentCapabilityInventoryError(
            "owner_data_gate_physical_catalog_binding_mismatch"
        )

    smci = next(
        (
            row
            for row in catalog.external_routes
            if row.route_id
            == route_decision.smci_q9_supplemental_decision.route_id
        ),
        None,
    )
    smci_decision = route_decision.smci_q9_supplemental_decision
    if smci is None or not (
        smci.canonical_issuer_id == smci_decision.canonical_issuer_id
        and smci.branch_ids == (smci_decision.branch_id,)
        and smci.source_family_refs == (smci_decision.source_family_ref,)
        and smci.foundation_required_family_match is False
        and smci_decision.may_satisfy_f12_minimum_route is False
    ):
        raise CurrentCapabilityInventoryError(
            "owner_data_gate_smci_supplemental_binding_mismatch"
        )

    for boundary in route_decision.local_zero_boundaries:
        eligible = tuple(
            row
            for row in catalog.local_routes
            if boundary.branch_id in row.branch_ids
            and boundary.source_family_ref in row.source_family_refs
        )
        if (
            len(eligible) != boundary.eligible_local_route_count
            or sum(row.searchable_leaf_count for row in eligible)
            != boundary.eligible_local_searchable_leaf_count
        ):
            raise CurrentCapabilityInventoryError(
                f"owner_data_gate_local_zero_boundary_mismatch:{boundary.branch_id}"
            )

    raw = _json(catalog.catalog_path)
    review_ids = tuple(
        sorted(
            _text(row.get("review_id"), "catalog_review_id_invalid")
            for row in raw.get("owner_review_items", ())
            if isinstance(row, Mapping)
        )
    )
    mapping = raw.get("reviewed_topic_branch_mapping")
    mapping_digest = canonical_digest({"reviewed_topic_branch_mapping": mapping})
    topic = route_decision.topic_mapping_decision
    if not (
        review_ids == route_decision.accepted_owner_review_ids
        and isinstance(mapping, list)
        and len(mapping) == topic.accepted_topic_mapping_count
        and mapping_digest == topic.topic_mapping_digest
        and topic.mapping_semantics == "selector_only"
        and topic.proves_claim_relevance is False
        and topic.proves_branch_coverage is False
        and topic.may_suppress_reviewed_lane is False
    ):
        raise CurrentCapabilityInventoryError(
            "owner_data_gate_topic_or_review_binding_mismatch"
        )


def build_current_host_owned_baseline_source_plan(
    *,
    inventory: CapabilityInventorySnapshot,
    owner_data_gate_decision: DellOwnerDataGateDecision,
) -> HostOwnedBaselineSourcePlan:
    """Build the semantic route catalog exposed to the planner/compiler.

    Required Reviewed routes preserve the foundation's exact family floor.
    Local and external routes are optional alternatives created only where the
    approved current inventory has a matching physical bucket.  No issuer,
    domain, local route ID, lane, or other physical selector is returned to the
    provider-facing plan.
    """

    current = CapabilityInventorySnapshot.model_validate(
        inventory.model_dump(mode="python")
    )
    try:
        decision = validate_trusted_dell_owner_data_gate_decision(
            owner_data_gate_decision
        )
    except DellOwnerDataGateError as exc:
        raise CurrentCapabilityInventoryError(str(exc)) from exc
    if not (
        decision.authority.capability_inventory_composition_authorized
        and decision.decision_digest
        == DEFAULT_EXPECTED_OWNER_DATA_GATE_DECISION_DIGEST
        and current.owner_data_gate_decision_digest == decision.decision_digest
    ):
        raise CurrentCapabilityInventoryError(
            "owner_data_gate_baseline_composition_binding_mismatch"
        )

    def route(
        *,
        route_id: str,
        branch_id: str,
        route_kind: str,
        family_refs: tuple[str, ...],
        authority_ref: str,
        requirement: str,
    ) -> MinimumRouteObligation:
        body = {
            "route_obligation_id": route_id,
            "coverage_obligation_id": branch_id,
            "requirement": requirement,
            "route_kind": route_kind,
            "semantic_source_family_refs": family_refs,
            "entity_refs": (),
            "period_intents": (),
            "metric_refs": (),
            "required_authority_refs": (authority_ref,),
            "substitution_policy": "none",
            "acceptable_replacement_route_kinds": (),
            "replacement_conditions": (),
            "answer_free": True,
        }
        return MinimumRouteObligation(
            **body,
            route_digest=canonical_digest(body),
        )

    routes: list[MinimumRouteObligation] = []
    for branch_id, family_refs in DELL_REQUIRED_SOURCE_FAMILIES_BY_COVERAGE:
        routes.append(
            route(
                route_id=f"route:{branch_id}:required-reviewed",
                branch_id=branch_id,
                route_kind="reviewed_evidence",
                family_refs=family_refs,
                authority_ref="authority:reviewed-read",
                requirement="required",
            )
        )
        for family_ref in family_refs:
            if any(
                row.source_family_ref == family_ref
                and branch_id in row.branch_refs
                for row in current.local_buckets
            ):
                routes.append(
                    route(
                        route_id=f"route:{branch_id}:{family_ref}:local",
                        branch_id=branch_id,
                        route_kind="local_candidate",
                        family_refs=(family_ref,),
                        authority_ref="authority:primary-read",
                        requirement="optional",
                    )
                )
            if any(
                row.source_family_ref == family_ref
                and branch_id in row.coverage_obligation_ids
                and row.foundation_required_family_match
                for row in current.external_buckets
            ):
                routes.append(
                    route(
                        route_id=f"route:{branch_id}:{family_ref}:external",
                        branch_id=branch_id,
                        route_kind="external_source",
                        family_refs=(family_ref,),
                        authority_ref="authority:primary-read",
                        requirement="optional",
                    )
                )
    routes.sort(key=lambda row: row.route_obligation_id)
    policy_digest = canonical_digest(
        {
            "policy": "owner_approved_current_inventory_semantic_route_projection_v1",
            "owner_data_gate_decision_digest": decision.decision_digest,
            "inventory_snapshot_digest": current.inventory_snapshot_digest,
        }
    )
    return build_host_owned_baseline_source_plan(
        authority_ref=(
            "authority:owner-data-gate:"
            f"{decision.decision_digest[:24]}"
        ),
        source_plan_id=(
            "source-plan:dell:owner-data-gate:"
            f"{decision.decision_digest[:24]}"
        ),
        inventory=current,
        route_obligations=tuple(routes),
        policy_digest=policy_digest,
    )


__all__ = [
    "CurrentCapabilityInventoryError",
    "EXPECTED_EXTERNAL_MANIFEST_DIGEST", "EXPECTED_EXTERNAL_MANIFEST_SHA256",
    "EXPECTED_LOCAL_NODES_SHA256", "EXPECTED_PHYSICAL_ROUTE_CATALOG_DIGEST",
    "EXPECTED_PHYSICAL_ROUTE_CATALOG_SHA256", "EXPECTED_S2_RESULT_DIGEST",
    "EXPECTED_S2_RESULT_SHA256", "PhysicalExternalRoute", "PhysicalLocalRoute",
    "ValidatedPhysicalRouteCatalog", "build_current_capability_inventory",
    "build_current_host_owned_baseline_source_plan",
    "build_external_inventory_buckets_from_manifest",
    "build_local_inventory_buckets_from_nodes",
    "build_s2_capability_bucket_from_verified_result",
    "build_source_family_catalog", "load_physical_route_catalog",
]
