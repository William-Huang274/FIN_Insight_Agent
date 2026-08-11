from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.official_source_attempt_program import (
    SourceResponse,
    SourceTransport,
    parse_source_document,
)
from sec_agent.s1_08_candidate_generation_runtime import DiscoveryQuery
from sec_agent.s1_08_candidate_generation_runtime_v4 import (
    CACHE_LINEAGE_SCHEMA,
    CATALOG_SCHEMA_V4,
)
from sec_agent.s1_08_official_content_tools import (
    ParsedOfficialHtml,
    parse_official_html_capture,
)
from sec_agent.s1_08_official_discovery_adapter import (
    CaptureFirstOfficialDiscoveryAdapter,
    DISCOVERY_NAMESPACE,
)


class _AttemptSafeDiscoveryCache(dict[Any, tuple[Any, ...]]):
    """Keep an incomplete discovery traversal out of cross-attempt state."""

    def __init__(
        self,
        *,
        adapter: "ProtectedFetchOfficialDiscoveryAdapterV4",
        cache_kind: str,
    ) -> None:
        super().__init__()
        self._adapter = adapter
        self._cache_kind = cache_kind

    def __setitem__(self, key: Any, value: tuple[Any, ...]) -> None:
        if self._adapter._attempt_had_pre_request_local_stop:
            locator = key[0] if isinstance(key, tuple) else key
            self._adapter.cache_lineage.append(
                {
                    "schema_version": CACHE_LINEAGE_SCHEMA,
                    "event": "not_cached",
                    "cache_scope": "attempt_local_noncacheable",
                    "cache_kind": self._cache_kind,
                    "locator_digest": canonical_digest(str(locator)),
                    "remote_outcome_kind": "incomplete_after_pre_request_local_stop",
                    "parser_outcome_kind": "not_applicable",
                    "origin_query_digest": self._adapter._current_query_digest,
                    "failure_code": (
                        self._adapter._last_pre_request_local_stop_code
                    ),
                    "request_started": False,
                }
            )
            return
        super().__setitem__(key, value)


@dataclass(frozen=True)
class _DocumentCacheEntryV4:
    response: SourceResponse | None
    attempt: dict[str, Any]
    parser_ref: dict[str, Any] | None
    parsed_html: ParsedOfficialHtml | None
    remote_outcome_kind: str
    parser_outcome_kind: str
    origin_query_digest: str
    origin_evidence_slot_id: str

    def result(
        self,
    ) -> tuple[
        SourceResponse | None,
        dict[str, Any],
        dict[str, Any] | None,
        ParsedOfficialHtml | None,
    ]:
        return (
            self.response,
            dict(self.attempt),
            self.parser_ref
            if self.parser_outcome_kind == "parser_succeeded"
            else None,
            self.parsed_html,
        )

    def lineage(self, *, locator_digest: str, event: str) -> dict[str, Any]:
        request_capture = self.attempt.get("request_capture") or {}
        response_capture = self.attempt.get("response_capture") or {}
        return {
            "schema_version": CACHE_LINEAGE_SCHEMA,
            "event": event,
            "cache_scope": "cross_attempt_document_cache",
            "locator_digest": locator_digest,
            "remote_outcome_kind": self.remote_outcome_kind,
            "parser_outcome_kind": self.parser_outcome_kind,
            "origin_query_digest": self.origin_query_digest,
            "origin_evidence_slot_id": self.origin_evidence_slot_id,
            "request_capture_ref": request_capture.get("object_key"),
            "request_capture_digest": request_capture.get("digest"),
            "response_capture_ref": response_capture.get("object_key"),
            "response_capture_digest": response_capture.get("digest"),
            "parser_capture_ref": (
                self.parser_ref.get("object_key") if self.parser_ref else None
            ),
            "parser_capture_digest": (
                self.parser_ref.get("digest") if self.parser_ref else None
            ),
        }


class ProtectedFetchOfficialDiscoveryAdapterV4(
    CaptureFirstOfficialDiscoveryAdapter
):
    """v4 successor with protected document capacity and typed cache lineage."""

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
        if catalog.get("schema_version") != CATALOG_SCHEMA_V4:
            raise ValueError("s1_08_v4_source_catalog_required")
        super().__init__(
            catalog=catalog,
            case_key=case_key,
            runtime_root=runtime_root,
            transport=transport,
            network_call_ceiling=network_call_ceiling,
            document_ceiling_per_query=document_ceiling_per_query,
            market_snapshot=market_snapshot,
        )
        self._document_cache_v4: dict[str, _DocumentCacheEntryV4] = {}
        self.cache_lineage: list[dict[str, Any]] = []
        self._attempt_had_pre_request_local_stop = False
        self._last_pre_request_local_stop_code = ""
        self._landing_cache = _AttemptSafeDiscoveryCache(
            adapter=self,
            cache_kind="landing_discovery_cache",
        )
        self._structured_cache = _AttemptSafeDiscoveryCache(
            adapter=self,
            cache_kind="structured_discovery_cache",
        )
        self.qualified_locator_fetch_opportunities = 0
        self.pre_request_local_stop_cross_attempt_cache_entries = 0
        self._attempt_discovery_call_ceiling = self.network_call_ceiling
        self._attempt_discovery_calls_started = 0
        self._attempt_protected_document_fetches = 0

    def prepare_attempt(
        self,
        *,
        query: DiscoveryQuery,
        network_call_allowance: int,
        maximum_document_fetches: int,
        protected_document_fetches: int,
    ) -> None:
        self._current_query_digest = query.query_digest
        self._attempt_had_pre_request_local_stop = False
        self._last_pre_request_local_stop_code = ""
        self._attempt_network_call_allowance = max(0, int(network_call_allowance))
        self._attempt_network_calls_started = 0
        self._attempt_protected_document_fetches = min(
            self._attempt_network_call_allowance,
            max(0, int(protected_document_fetches)),
        )
        self._attempt_discovery_call_ceiling = (
            self._attempt_network_call_allowance
            - self._attempt_protected_document_fetches
        )
        self._attempt_discovery_calls_started = 0
        self._attempt_document_fetch_ceiling = max(0, int(maximum_document_fetches))
        self._attempt_document_fetches_started = 0

    def current_attempt_budget_state(self) -> dict[str, Any]:
        return {
            "query_digest": self._current_query_digest,
            "network_call_allowance": self._attempt_network_call_allowance,
            "network_calls_started": self._attempt_network_calls_started,
            "discovery_call_ceiling": self._attempt_discovery_call_ceiling,
            "discovery_calls_started": self._attempt_discovery_calls_started,
            "protected_document_fetch_allowance": (
                self._attempt_protected_document_fetches
            ),
            "document_fetch_ceiling": self._attempt_document_fetch_ceiling,
            "document_fetches_started": self._attempt_document_fetches_started,
        }

    def _fetch_and_parse(
        self, url: str, *, query: DiscoveryQuery
    ) -> tuple[
        SourceResponse | None,
        dict[str, Any],
        dict[str, Any] | None,
        ParsedOfficialHtml | None,
    ]:
        locator_digest = canonical_digest(url)
        self.qualified_locator_fetch_opportunities += 1
        self._record_receipt(
            {
                "query_digest": query.query_digest,
                "evidence_slot_id": query.evidence_slot_id,
                "status": "document_fetch_opportunity",
                "code": "qualified_locator_received_document_fetch_opportunity",
                "locator_digest": locator_digest,
                "remaining_global_capacity": max(
                    0, self.network_call_ceiling - self.network_calls
                ),
                "attempt_budget_state": self.current_attempt_budget_state(),
            }
        )
        if url in self._document_cache_v4:
            entry = self._document_cache_v4[url]
            lineage = entry.lineage(locator_digest=locator_digest, event="cache_hit")
            lineage.update(
                {
                    "consumer_query_digest": query.query_digest,
                    "consumer_evidence_slot_id": query.evidence_slot_id,
                }
            )
            self.cache_lineage.append(lineage)
            self._record_receipt(
                {
                    "query_digest": query.query_digest,
                    "evidence_slot_id": query.evidence_slot_id,
                    "status": "cache_hit",
                    "code": "typed_document_cache_hit",
                    "locator_digest": locator_digest,
                    "remote_outcome_kind": entry.remote_outcome_kind,
                    "parser_outcome_kind": entry.parser_outcome_kind,
                }
            )
            return entry.result()
        response, attempt = self._fetch(
            url=url,
            route_id=f"document_{canonical_digest(url)[:16]}",
            query=query,
        )
        if response is None or attempt.get("status") != "captured":
            result = (response, attempt, None, None)
            if not _attempt_has_remote_capture(attempt):
                self.cache_lineage.append(
                    {
                        "schema_version": CACHE_LINEAGE_SCHEMA,
                        "event": "not_cached",
                        "cache_scope": "attempt_local_noncacheable",
                        "locator_digest": locator_digest,
                        "remote_outcome_kind": "pre_request_local_stop",
                        "parser_outcome_kind": "not_run",
                        "origin_query_digest": query.query_digest,
                        "origin_evidence_slot_id": query.evidence_slot_id,
                        "failure_code": attempt.get("failure_code"),
                        "request_started": False,
                    }
                )
                return result
            entry = _DocumentCacheEntryV4(
                response=response,
                attempt=dict(attempt),
                parser_ref=None,
                parsed_html=None,
                remote_outcome_kind="captured_remote_failure",
                parser_outcome_kind="not_run",
                origin_query_digest=query.query_digest,
                origin_evidence_slot_id=query.evidence_slot_id,
            )
            self._store_document_cache_entry(url=url, entry=entry)
            return result
        parsed = parse_source_document(response)
        content_type = str(response.headers.get("content-type") or "").lower()
        parsed_html = None
        if "html" in content_type or response.body.lstrip().startswith(
            (b"<html", b"<!DOCTYPE", b"<?xml")
        ):
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
                {
                    "query_digest": query.query_digest,
                    "status": "rejected",
                    "code": "source_parser_failed",
                }
            )
            parser_outcome_kind = "parser_failed"
        else:
            parser_outcome_kind = "parser_succeeded"
        entry = _DocumentCacheEntryV4(
            response=response,
            attempt=dict(attempt),
            parser_ref=dict(parser_ref),
            parsed_html=parsed_html,
            remote_outcome_kind="captured_remote_success",
            parser_outcome_kind=parser_outcome_kind,
            origin_query_digest=query.query_digest,
            origin_evidence_slot_id=query.evidence_slot_id,
        )
        self._store_document_cache_entry(url=url, entry=entry)
        return entry.result()

    def _store_document_cache_entry(
        self, *, url: str, entry: _DocumentCacheEntryV4
    ) -> None:
        if not _attempt_has_remote_capture(entry.attempt):
            self.pre_request_local_stop_cross_attempt_cache_entries += 1
            raise RuntimeError("pre_request_local_stop_cross_attempt_cache_forbidden")
        self._document_cache_v4[url] = entry
        self.cache_lineage.append(
            entry.lineage(
                locator_digest=canonical_digest(url), event="cache_write"
            )
        )

    def _fetch(
        self, *, url: str, route_id: str, query: DiscoveryQuery
    ) -> tuple[SourceResponse | None, dict[str, Any]]:
        is_document = route_id.startswith("document_")
        if self.network_calls >= self.network_call_ceiling:
            return self._pre_request_stop(
                query=query,
                url=url,
                code="discovery_network_call_ceiling_reached",
                stop_scope="global_network_budget",
            )
        if (
            not is_document
            and self._attempt_discovery_calls_started
            >= self._attempt_discovery_call_ceiling
        ):
            return self._pre_request_stop(
                query=query,
                url=url,
                code="protected_document_fetch_capacity_reserved",
                stop_scope="attempt_discovery_phase",
            )
        if self._attempt_network_calls_started >= self._attempt_network_call_allowance:
            return self._pre_request_stop(
                query=query,
                url=url,
                code="slot_attempt_network_reservation_exhausted",
                stop_scope="attempt_network_budget",
            )
        if (
            is_document
            and self._attempt_document_fetches_started
            >= self._attempt_document_fetch_ceiling
        ):
            return self._pre_request_stop(
                query=query,
                url=url,
                code="document_fetch_ceiling_reached",
                stop_scope="attempt_document_ceiling",
            )
        self._attempt_network_calls_started += 1
        if is_document:
            self._attempt_document_fetches_started += 1
            self.document_fetches += 1
        else:
            self._attempt_discovery_calls_started += 1
        response, attempt = self.client.fetch(
            case_key=self.case_key,
            route_id=route_id,
            url=url,
            allowed_hosts=self._allowed_hosts,
            timeout_seconds=30,
            byte_ceiling=16_777_216,
        )
        attempt = dict(attempt)
        attempt.update(
            {
                "request_started": True,
                "cache_scope": "cross_attempt_remote_capture_eligible",
                "remote_outcome_kind": (
                    "captured_remote_success"
                    if attempt.get("status") == "captured"
                    else "captured_remote_failure"
                ),
            }
        )
        return response, attempt

    def _pre_request_stop(
        self,
        *,
        query: DiscoveryQuery,
        url: str,
        code: str,
        stop_scope: str,
    ) -> tuple[None, dict[str, Any]]:
        self._attempt_had_pre_request_local_stop = True
        self._last_pre_request_local_stop_code = code
        receipt = {
            "query_digest": query.query_digest,
            "evidence_slot_id": query.evidence_slot_id,
            "status": "stopped",
            "code": code,
            "locator_digest": canonical_digest(url),
            "outcome_kind": "pre_request_local_stop",
            "stop_scope": stop_scope,
            "request_started": False,
            "cache_scope": "attempt_local_noncacheable",
        }
        self._record_receipt(receipt)
        return None, {
            "status": "local_stop",
            "failure_code": code,
            "request_capture": {},
            "response_capture": {},
            "outcome_kind": "pre_request_local_stop",
            "stop_scope": stop_scope,
            "request_started": False,
            "cache_scope": "attempt_local_noncacheable",
        }


def _attempt_has_remote_capture(attempt: Mapping[str, Any]) -> bool:
    request_capture = attempt.get("request_capture") or {}
    response_capture = attempt.get("response_capture") or {}
    return bool(
        request_capture.get("object_key")
        and request_capture.get("digest")
        and response_capture.get("object_key")
        and response_capture.get("digest")
    )


__all__ = ["ProtectedFetchOfficialDiscoveryAdapterV4"]
