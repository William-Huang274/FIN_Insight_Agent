from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping
from urllib.parse import urlparse

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.official_source_attempt_program import (
    CaptureFirstOfficialSourceClient,
    SourceResponse,
    SourceTransport,
    parse_source_document,
)
from sec_agent.s1_08_candidate_generation_runtime import (
    DiscoveryCandidate,
    DiscoveryQuery,
)
from sec_agent.s1_08_source_quality import (
    infer_source_family,
    qualify_locator,
    qualify_parsed_content,
    qualify_relationship_direction,
)
from sec_agent.s1_08_official_content_tools import (
    OfficialLocatorCandidate,
    ParsedOfficialHtml,
    PublicationDateDecision,
    parse_feed_capture,
    parse_official_html_capture,
    parse_robots_capture,
    parse_sitemap_capture,
)


DISCOVERY_NAMESPACE = "fin-0.1.3/s1-08/current-source-discovery"


@dataclass(frozen=True)
class _Locator:
    url: str
    title: str
    published_on: str
    discovery_capture_ref: str
    discovery_capture_digest: str
    source_family: str = "issuer_official_page"
    form_type: str = ""
    date_kind: str = ""
    date_source: str = ""
    endpoint_kind: str = "document"


class CaptureFirstOfficialDiscoveryAdapter:
    """Discovers official documents, captures them, parses them, then emits candidates."""

    def __init__(
        self,
        *,
        catalog: Mapping[str, Any],
        case_key: str,
        runtime_root: str | Path,
        transport: SourceTransport,
        network_call_ceiling: int,
        document_ceiling_per_query: int = 2,
        market_snapshot: Mapping[str, Any] | None = None,
    ) -> None:
        self.catalog = dict(catalog)
        self.case_key = case_key
        self.store = FileCanonicalObjectStore(Path(runtime_root).resolve() / "objects")
        self.client = CaptureFirstOfficialSourceClient(
            store=self.store,
            transport=transport,
            namespace=DISCOVERY_NAMESPACE,
        )
        self.network_call_ceiling = int(network_call_ceiling)
        self.document_ceiling_per_query = int(document_ceiling_per_query)
        self.market_snapshot = dict(market_snapshot or {})
        self.receipts: list[dict[str, Any]] = []
        self.checkpoint_refs: list[dict[str, Any]] = []
        self.known_navigation_noise_fetches = 0
        self.document_fetches = 0
        self._landing_cache: dict[tuple[str, bool], tuple[_Locator, ...]] = {}
        self._structured_cache: dict[str, tuple[_Locator, ...]] = {}
        self._document_cache: dict[
            str,
            tuple[
                SourceResponse | None,
                dict[str, Any],
                dict[str, Any] | None,
                ParsedOfficialHtml | None,
            ],
        ] = {}
        self._attempt_network_call_allowance = self.network_call_ceiling
        self._attempt_network_calls_started = 0
        self._attempt_document_fetch_ceiling = self.document_ceiling_per_query
        self._attempt_document_fetches_started = 0
        self._current_query_digest = ""
        self._entity_by_key = {
            str(row["entity_key"]): row for row in self.catalog.get("entities") or []
        }
        self._allowed_hosts = {
            (urlparse(str(url)).hostname or "").lower()
            for row in self._entity_by_key.values()
            for url in row.get("official_landing_pages") or []
        } | {"www.sec.gov", "sec.gov"}
        self._provider_capabilities = {
            str(row.get("route_id") or ""): dict(row)
            for row in self.catalog.get("source_provider_capabilities") or []
        }

    @property
    def network_calls(self) -> int:
        return self.client.network_calls

    def prepare_attempt(
        self,
        *,
        query: DiscoveryQuery,
        network_call_allowance: int,
        maximum_document_fetches: int,
    ) -> None:
        self._current_query_digest = query.query_digest
        self._attempt_network_call_allowance = max(0, int(network_call_allowance))
        self._attempt_network_calls_started = 0
        self._attempt_document_fetch_ceiling = max(0, int(maximum_document_fetches))
        self._attempt_document_fetches_started = 0

    def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        if self._current_query_digest != query.query_digest:
            self.prepare_attempt(
                query=query,
                network_call_allowance=max(0, self.network_call_ceiling - self.network_calls),
                maximum_document_fetches=self.document_ceiling_per_query,
            )
        if query.case_key != self.case_key:
            self._record_receipt(
                {"query_digest": query.query_digest, "status": "rejected", "code": "cross_case_query"}
            )
            return ()
        if "local_market_snapshot" in query.route_ids:
            return self._market_candidate(query)
        operational_route_ids: list[str] = []
        for route_id in query.route_ids:
            capability = self._provider_capabilities.get(route_id)
            if capability is not None and capability.get("operational") is not True:
                self._record_receipt(
                    {
                        "query_digest": query.query_digest,
                        "evidence_slot_id": query.evidence_slot_id,
                        "route_id": route_id,
                        "status": "typed_gap",
                        "code": "source_provider_route_unavailable",
                    }
                )
            else:
                operational_route_ids.append(route_id)
        locators: list[_Locator] = []
        for entity_key in query.entity_keys:
            entity = self._entity_by_key.get(entity_key)
            if entity is None:
                continue
            for landing_url in self._route_landing_pages(
                entity, tuple(operational_route_ids)
            ):
                locators.extend(self._discover_landing(landing_url, query=query))
        qualified: list[tuple[_Locator, Any]] = []
        for locator in locators:
            owner_key = _entity_key_for_url(self._entity_by_key, locator.url)
            owner = self._entity_by_key.get(owner_key, {})
            relationship_reasons = (
                qualify_relationship_direction(
                    role_id=query.role_id,
                    url=locator.url,
                    subject_entity=query.subject_entity,
                    evidence_owner_entity=owner_key,
                    evidence_owner_roles=tuple(owner.get("ecosystem_roles") or ()),
                    claim_direction=query.claim_direction,
                    allowed_source_owner_roles=query.allowed_source_owner_roles,
                    forbidden_nested_relationships=query.forbidden_nested_relationships,
                )
                if query.subject_entity
                else ()
            )
            decision = qualify_locator(
                role_id=query.role_id,
                allowed_source_families=query.source_families,
                url=locator.url,
                title=locator.title,
                published_on=locator.published_on,
                as_of=str(self.catalog["as_of"]),
                currentness_window_days=query.currentness_window_days,
                form_type=locator.form_type,
            )
            combined_reasons = tuple(
                sorted(set((*decision.reason_codes, *relationship_reasons)))
            )
            self._record_receipt(
                {
                    "query_digest": query.query_digest,
                    "evidence_slot_id": query.evidence_slot_id,
                    "status": (
                        "qualified_before_fetch"
                        if decision.decision == "fetch" and not relationship_reasons
                        else "rejected_before_fetch"
                    ),
                    "code": (
                        "locator_quality_pass"
                        if not combined_reasons
                        else combined_reasons[0]
                    ),
                    "reason_codes": list(combined_reasons),
                    "locator_digest": canonical_digest(decision.canonical_locator),
                    "quality_score": decision.quality_score,
                    "source_family": locator.source_family,
                }
            )
            if decision.decision == "fetch" and not relationship_reasons:
                qualified.append((locator, decision))
        ranked = sorted(
            qualified,
            key=lambda pair: (
                -pair[1].quality_score,
                pair[1].canonical_locator,
            ),
        )
        candidates: list[DiscoveryCandidate] = []
        seen: set[str] = set()
        for locator, decision in ranked:
            canonical = decision.canonical_locator
            if canonical in seen or len(candidates) >= self.document_ceiling_per_query:
                continue
            seen.add(canonical)
            response, attempt, parser_ref, parsed_html = self._fetch_and_parse(
                locator.url, query=query
            )
            if response is None or attempt.get("status") != "captured" or parser_ref is None:
                continue
            date_decision = (
                PublicationDateDecision(
                    date_value=locator.published_on,
                    date_kind=locator.date_kind or "published_date",
                    date_source=locator.date_source or "locator_metadata",
                    date_confidence="high",
                    capture_ref=str(attempt["response_capture"]["object_key"]),
                    capture_digest=str(attempt["response_capture"]["digest"]),
                    conflict_status="none",
                    candidates=(),
                )
                if locator.published_on
                else parsed_html.publication_date
                if parsed_html is not None
                else PublicationDateDecision(
                    date_value="",
                    date_kind="",
                    date_source="",
                    date_confidence="",
                    capture_ref=str(attempt["response_capture"]["object_key"]),
                    capture_digest=str(attempt["response_capture"]["digest"]),
                    conflict_status="publication_date_unproven",
                    candidates=(),
                )
            )
            published_on = locator.published_on or date_decision.date_value
            if not published_on or date_decision.conflict_status != "none":
                self._record_receipt(
                    {
                        "query_digest": query.query_digest,
                        "status": "rejected",
                        "code": (
                            date_decision.conflict_status
                            if date_decision.conflict_status != "none"
                            else "discovered_source_published_date_unproven"
                        ),
                        "locator_digest": canonical_digest(locator.url),
                        "publication_date": date_decision.as_dict(),
                    }
                )
                continue
            entity_key = _entity_key_for_url(self._entity_by_key, response.final_url)
            parsed = parse_source_document(response)
            parsed_text = (
                parsed_html.main_text if parsed_html is not None else str(parsed.get("text") or "")
            )
            aliases = list(self._entity_by_key.get(entity_key, {}).get("aliases") or [])
            content_reasons = qualify_parsed_content(
                role_id=query.role_id,
                title=locator.title,
                text=parsed_text,
                entity_aliases=aliases,
            )
            if content_reasons:
                self._record_receipt(
                    {
                        "query_digest": query.query_digest,
                        "evidence_slot_id": query.evidence_slot_id,
                        "status": "rejected_after_fetch",
                        "code": content_reasons[0],
                        "reason_codes": list(content_reasons),
                        "locator_digest": canonical_digest(canonical),
                    }
                )
                continue
            candidates.append(
                DiscoveryCandidate(
                    case_key=query.case_key,
                    target_key=query.target_key,
                    role_id=query.role_id,
                    entity_key=entity_key,
                    title=locator.title or response.final_url,
                    locator=response.final_url,
                    published_on=published_on,
                    authority=_authority(
                        entity_key=entity_key,
                        case_key=query.case_key,
                        host=(urlparse(response.final_url).hostname or "").lower(),
                    ),
                    discovery_capture_ref=locator.discovery_capture_ref,
                    discovery_capture_digest=locator.discovery_capture_digest,
                    source_capture_ref=str(attempt["response_capture"]["object_key"]),
                    source_capture_digest=str(attempt["response_capture"]["digest"]),
                    parser_capture_ref=str(parser_ref["object_key"]),
                    parser_capture_digest=str(parser_ref["digest"]),
                    evidence_slot_id=query.evidence_slot_id,
                    source_family=locator.source_family,
                    content_quality_score=decision.quality_score,
                    promotion_decision="accepted_candidate",
                    subject_entity=query.subject_entity,
                    evidence_owner_entity=(entity_key if query.subject_entity else ""),
                    ecosystem_role=(
                        _evidence_owner_role(
                            self._entity_by_key.get(entity_key, {}),
                            query.allowed_source_owner_roles,
                        )
                        if query.subject_entity
                        else ""
                    ),
                    claim_direction=(query.claim_direction if query.subject_entity else ""),
                    publication_date_kind=(
                        locator.date_kind or date_decision.date_kind or "published_date"
                        if query.subject_entity
                        else ""
                    ),
                    publication_date_source=(
                        locator.date_source or date_decision.date_source
                        if query.subject_entity
                        else ""
                    ),
                    publication_date_confidence=(
                        date_decision.date_confidence if query.subject_entity else ""
                    ),
                    publication_date_conflict_status=(
                        date_decision.conflict_status if query.subject_entity else ""
                    ),
                )
            )
        self._record_receipt(
            {
                "query_digest": query.query_digest,
                "status": "terminal",
                "code": "qualified_candidates_discovered" if candidates else "no_qualified_candidate",
                "candidate_count": len(candidates),
            }
        )
        return tuple(candidates)

    def persist_candidate_checkpoint(self, snapshot: Mapping[str, Any]) -> None:
        body = dict(snapshot)
        body.pop("checkpoint_refs", None)
        ref = self.store.put_json(
            body,
            namespace=DISCOVERY_NAMESPACE,
            artifact_type="sourcehunter_candidate_checkpoint",
        )
        self.checkpoint_refs.append(ref)

    def _record_receipt(self, receipt: Mapping[str, Any]) -> None:
        self.receipts.append(dict(receipt))

    def _route_landing_pages(
        self, entity: Mapping[str, Any], route_ids: tuple[str, ...]
    ) -> tuple[str, ...]:
        pages = [str(value) for value in entity.get("official_landing_pages") or []]
        out: list[str] = []
        if any(
            route_id in route_ids
            for route_id in (
                "issuer_ir_discovery",
                "issuer_ir_structured_discovery",
                "official_ir_feed_discovery",
                "official_domain_bounded_search",
            )
        ):
            out.extend(url for url in pages if "data.sec.gov/submissions" not in url)
        if "sec_submissions_discovery" in route_ids:
            out.extend(url for url in pages if "data.sec.gov/submissions" in url)
        return tuple(dict.fromkeys(out))

    def _discover_landing(
        self, landing_url: str, *, query: DiscoveryQuery
    ) -> tuple[_Locator, ...]:
        structured = any(
            route_id in query.route_ids
            for route_id in (
                "official_ir_feed_discovery",
                "official_domain_bounded_search",
            )
        )
        cache_key = (landing_url, structured)
        if cache_key in self._landing_cache:
            return self._landing_cache[cache_key]
        response, attempt = self._fetch(
            url=landing_url,
            route_id=f"discovery_{canonical_digest(landing_url)[:16]}",
            query=query,
        )
        if response is None or attempt.get("status") != "captured":
            self._landing_cache[cache_key] = ()
            return ()
        capture = attempt["response_capture"]
        content_type = str(response.headers.get("content-type") or "").lower()
        if "json" in content_type or landing_url.startswith("https://data.sec.gov/submissions/"):
            rows = _sec_submission_locators(response, capture)
        else:
            parsed = parse_official_html_capture(
                body=response.body,
                final_url=response.final_url,
                headers=response.headers,
                as_of=str(self.catalog["as_of"]),
                capture_ref=str(capture["object_key"]),
                capture_digest=str(capture["digest"]),
            )
            rows = _official_candidates_to_locators(
                parsed.document_locators, capture=capture
            )
            if structured:
                endpoints = list(parsed.structured_endpoints)
                if not endpoints:
                    split = urlparse(response.final_url)
                    endpoints.append(
                        OfficialLocatorCandidate(
                            url=f"{split.scheme}://{split.netloc}/robots.txt",
                            title="Official robots discovery",
                            published_on="",
                            date_kind="",
                            date_source="derived_same_host_robots",
                            source_family="issuer_structured_discovery",
                            endpoint_kind="robots",
                        )
                    )
                structured_rows: list[_Locator] = []
                for endpoint in endpoints:
                    structured_rows.extend(
                        self._discover_structured_endpoint(
                            endpoint, query=query, depth=0
                        )
                    )
                rows = tuple((*rows, *structured_rows))
        self._landing_cache[cache_key] = rows
        return rows

    def _discover_structured_endpoint(
        self,
        endpoint: OfficialLocatorCandidate,
        *,
        query: DiscoveryQuery,
        depth: int,
    ) -> tuple[_Locator, ...]:
        if endpoint.url in self._structured_cache:
            return self._structured_cache[endpoint.url]
        response, attempt = self._fetch(
            url=endpoint.url,
            route_id=f"structured_{canonical_digest(endpoint.url)[:16]}",
            query=query,
        )
        if response is None or attempt.get("status") != "captured":
            self._structured_cache[endpoint.url] = ()
            return ()
        capture = attempt["response_capture"]
        content_type = str(response.headers.get("content-type") or "").lower()
        path = urlparse(response.final_url).path.lower()
        allowed_hosts = tuple(self._allowed_hosts)
        if endpoint.endpoint_kind == "robots" or path.endswith("robots.txt"):
            discovered = parse_robots_capture(
                body=response.body,
                base_url=response.final_url,
                allowed_hosts=allowed_hosts,
            )
        elif endpoint.endpoint_kind == "sitemap" or "sitemap" in path:
            discovered = parse_sitemap_capture(
                body=response.body,
                base_url=response.final_url,
                allowed_hosts=allowed_hosts,
            )
        elif endpoint.endpoint_kind == "feed" or any(
            token in content_type for token in ("rss", "atom", "feed+json")
        ):
            discovered = parse_feed_capture(
                body=response.body,
                base_url=response.final_url,
                allowed_hosts=allowed_hosts,
            )
        elif "xml" in content_type:
            discovered = parse_sitemap_capture(
                body=response.body,
                base_url=response.final_url,
                allowed_hosts=allowed_hosts,
            )
            if not discovered:
                discovered = parse_feed_capture(
                    body=response.body,
                    base_url=response.final_url,
                    allowed_hosts=allowed_hosts,
                )
        else:
            discovered = ()
        documents = [row for row in discovered if row.endpoint_kind == "document"]
        nested = [row for row in discovered if row.endpoint_kind != "document"]
        rows = list(_official_candidates_to_locators(documents, capture=capture))
        if depth < 1:
            for child in nested:
                rows.extend(
                    self._discover_structured_endpoint(
                        child, query=query, depth=depth + 1
                    )
                )
        result = tuple(rows)
        self._structured_cache[endpoint.url] = result
        return result

    def _fetch_and_parse(
        self, url: str, *, query: DiscoveryQuery
    ) -> tuple[
        SourceResponse | None,
        dict[str, Any],
        dict[str, Any] | None,
        ParsedOfficialHtml | None,
    ]:
        if url in self._document_cache:
            return self._document_cache[url]
        response, attempt = self._fetch(
            url=url,
            route_id=f"document_{canonical_digest(url)[:16]}",
            query=query,
        )
        if response is None or attempt.get("status") != "captured":
            result = (response, attempt, None, None)
            self._document_cache[url] = result
            return result
        parsed = parse_source_document(response)
        content_type = str(response.headers.get("content-type") or "").lower()
        parsed_html = None
        if "html" in content_type or response.body.lstrip().startswith((b"<html", b"<!DOCTYPE", b"<?xml")):
            parsed_html = parse_official_html_capture(
                body=response.body,
                final_url=response.final_url,
                headers=response.headers,
                as_of=str(self.catalog["as_of"]),
                capture_ref=str(attempt["response_capture"]["object_key"]),
                capture_digest=str(attempt["response_capture"]["digest"]),
            )
        parser_ref = self.store.put_json(
            {
                "schema_version": "fin_ia_0_1_3_s1_08_parser_capture_v1_0",
                "response_capture_ref": attempt["response_capture"]["object_key"],
                "response_capture_digest": attempt["response_capture"]["digest"],
                "parser": {key: value for key, value in parsed.items() if key != "text"},
                "mature_component_parse": (
                    {
                        "title": parsed_html.title,
                        "publication_date": parsed_html.publication_date.as_dict(),
                        "main_text_sha256": canonical_digest(parsed_html.main_text),
                        "parser_versions": dict(parsed_html.parser_versions),
                    }
                    if parsed_html is not None
                    else None
                ),
            },
            namespace=DISCOVERY_NAMESPACE,
            artifact_type="official_discovery_parser_result",
        )
        if parsed.get("status") != "parsed":
            self._record_receipt(
                {"query_digest": query.query_digest, "status": "rejected", "code": "source_parser_failed"}
            )
            result = (response, attempt, None, parsed_html)
        else:
            result = (response, attempt, parser_ref, parsed_html)
        self._document_cache[url] = result
        return result

    def _fetch(
        self, *, url: str, route_id: str, query: DiscoveryQuery
    ) -> tuple[SourceResponse | None, dict[str, Any]]:
        is_document = route_id.startswith("document_")
        if self.network_calls >= self.network_call_ceiling:
            receipt = {
                "query_digest": query.query_digest,
                "status": "stopped",
                "code": "discovery_network_call_ceiling_reached",
                "locator_digest": canonical_digest(url),
            }
            self._record_receipt(receipt)
            return None, {
                "status": "transport_failure",
                "failure_code": receipt["code"],
                "request_capture": {},
                "response_capture": {},
            }
        if self._attempt_network_calls_started >= self._attempt_network_call_allowance:
            receipt = {
                "query_digest": query.query_digest,
                "evidence_slot_id": query.evidence_slot_id,
                "status": "stopped",
                "code": "slot_attempt_network_reservation_exhausted",
                "locator_digest": canonical_digest(url),
            }
            self._record_receipt(receipt)
            return None, {
                "status": "transport_failure",
                "failure_code": receipt["code"],
                "request_capture": {},
                "response_capture": {},
            }
        if is_document and self._attempt_document_fetches_started >= self._attempt_document_fetch_ceiling:
            receipt = {
                "query_digest": query.query_digest,
                "evidence_slot_id": query.evidence_slot_id,
                "status": "stopped",
                "code": "document_fetch_ceiling_reached",
                "locator_digest": canonical_digest(url),
            }
            self._record_receipt(receipt)
            return None, {
                "status": "transport_failure",
                "failure_code": receipt["code"],
                "request_capture": {},
                "response_capture": {},
            }
        self._attempt_network_calls_started += 1
        if is_document:
            self._attempt_document_fetches_started += 1
            self.document_fetches += 1
        return self.client.fetch(
            case_key=self.case_key,
            route_id=route_id,
            url=url,
            allowed_hosts=self._allowed_hosts,
            timeout_seconds=30,
            byte_ceiling=16_777_216,
        )

    def _market_candidate(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        if not self.market_snapshot:
            self._record_receipt(
                {"query_digest": query.query_digest, "status": "typed_gap", "code": "current_market_snapshot_unavailable"}
            )
            return ()
        snapshot_ref = self.store.put_json(
            {
                "schema_version": "fin_ia_0_1_3_s1_08_local_market_snapshot_capture_v1_0",
                "case_key": query.case_key,
                "as_of": self.catalog["as_of"],
                "snapshot": self.market_snapshot,
            },
            namespace=DISCOVERY_NAMESPACE,
            artifact_type="local_market_snapshot",
        )
        parser_ref = self.store.put_json(
            {
                "schema_version": "fin_ia_0_1_3_s1_08_local_market_parser_capture_v1_0",
                "snapshot_digest": snapshot_ref["digest"],
                "status": "parsed",
            },
            namespace=DISCOVERY_NAMESPACE,
            artifact_type="local_market_snapshot_parser",
        )
        entity_ref = self.store.put_json(
            {
                "schema_version": "fin_ia_0_1_3_s1_08_local_market_discovery_capture_v1_0",
                "query_digest": query.query_digest,
                "route_id": "local_market_snapshot",
            },
            namespace=DISCOVERY_NAMESPACE,
            artifact_type="local_market_snapshot_discovery",
        )
        return (
            DiscoveryCandidate(
                case_key=query.case_key,
                target_key=query.target_key,
                role_id=query.role_id,
                entity_key=query.case_key,
                title="Current governed market snapshot",
                locator="current_market_snapshot",
                published_on=str(self.catalog["as_of"]),
                authority="non_authoritative_market_context",
                discovery_capture_ref=entity_ref["object_key"],
                discovery_capture_digest=entity_ref["digest"],
                source_capture_ref=snapshot_ref["object_key"],
                source_capture_digest=snapshot_ref["digest"],
                parser_capture_ref=parser_ref["object_key"],
                parser_capture_digest=parser_ref["digest"],
                evidence_slot_id=query.evidence_slot_id,
                source_family="market_context",
                content_quality_score=100,
                subject_entity=query.subject_entity,
                evidence_owner_entity=(query.case_key if query.subject_entity else ""),
                ecosystem_role=("subject" if query.subject_entity else ""),
                claim_direction=(query.claim_direction if query.subject_entity else ""),
                publication_date_kind=("as_of_date" if query.subject_entity else ""),
                publication_date_source=(
                    "governed_local_snapshot_as_of" if query.subject_entity else ""
                ),
                publication_date_confidence=("high" if query.subject_entity else ""),
                publication_date_conflict_status=("none" if query.subject_entity else ""),
            ),
        )


def _official_candidates_to_locators(
    rows: tuple[OfficialLocatorCandidate, ...] | list[OfficialLocatorCandidate],
    *,
    capture: Mapping[str, Any],
) -> tuple[_Locator, ...]:
    return tuple(
        _Locator(
            url=row.url,
            title=row.title,
            published_on=row.published_on,
            discovery_capture_ref=str(capture["object_key"]),
            discovery_capture_digest=str(capture["digest"]),
            source_family=row.source_family or infer_source_family(row.url),
            form_type=row.form_type,
            date_kind=row.date_kind,
            date_source=row.date_source,
            endpoint_kind=row.endpoint_kind,
        )
        for row in rows
    )


def _sec_submission_locators(
    response: SourceResponse, capture: Mapping[str, Any]
) -> tuple[_Locator, ...]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
        recent = payload["filings"]["recent"]
        ciks = re.sub(r"\D", "", str(payload["cik"])).lstrip("0")
        rows = zip(
            recent["accessionNumber"],
            recent["filingDate"],
            recent["form"],
            recent["primaryDocument"],
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return ()
    out: list[_Locator] = []
    for accession, filing_date, form, document in rows:
        if str(form) not in {"10-K", "10-Q", "8-K", "20-F", "6-K"}:
            continue
        compact = re.sub(r"\D", "", str(accession))
        url = f"https://www.sec.gov/Archives/edgar/data/{ciks}/{compact}/{document}"
        out.append(
            _Locator(
                url=url,
                title=f"{form} filed {filing_date}",
                published_on=str(filing_date),
                discovery_capture_ref=str(capture["object_key"]),
                discovery_capture_digest=str(capture["digest"]),
                source_family="regulatory_filing",
                form_type=str(form),
                date_kind="filing_date",
                date_source="SEC_submissions_filingDate",
            )
        )
    return tuple(out)


def _query_score(query: str, title: str, url: str) -> int:
    haystack = f"{title} {url}".lower()
    terms = {
        token
        for token in re.findall(r"[a-zA-Z0-9-]{3,}", query.lower())
        if token not in {"latest", "official", "current", "available", "quarter"}
    }
    score = sum(token in haystack for token in terms)
    if any(term in haystack for term in ("earnings", "results", "10-q", "10-k", "financial")):
        score += 2
    return score


def _entity_key_for_url(
    entities: Mapping[str, Mapping[str, Any]], url: str
) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host in {"www.sec.gov", "sec.gov"}:
        match = re.search(r"/data/(?P<cik>\d+)/", url)
        if match:
            cik = match.group("cik").lstrip("0")
            for key, entity in entities.items():
                if str(entity.get("cik") or "").lstrip("0") == cik:
                    return key
    for key, entity in entities.items():
        if any((urlparse(str(page)).hostname or "").lower() == host for page in entity.get("official_landing_pages") or []):
            return key
    return ""


def _authority(*, entity_key: str, case_key: str, host: str) -> str:
    if host in {"www.sec.gov", "sec.gov"}:
        return "regulatory_primary"
    return "issuer_primary" if entity_key == case_key else "industry_primary"


def _evidence_owner_role(
    entity: Mapping[str, Any], allowed_roles: tuple[str, ...]
) -> str:
    roles = tuple(str(value) for value in entity.get("ecosystem_roles") or ())
    return next((role for role in roles if role in set(allowed_roles)), roles[0] if roles else "")


__all__ = ["CaptureFirstOfficialDiscoveryAdapter", "DISCOVERY_NAMESPACE"]
