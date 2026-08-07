from __future__ import annotations

import json
from pathlib import Path

import pytest

from sec_agent.s1_08_candidate_generation_runtime import (
    CandidateGenerationInterrupted,
    DiscoveryCandidate,
    canonical_digest,
    compile_evidence_slots,
    compile_initial_queries,
    load_source_catalog,
    run_candidate_generation,
)
from sec_agent.s1_08_quality_replay import (
    audit_restricted_capture_store,
    load_restricted_manifest,
    run_sanitized_quality_replay,
)
from sec_agent.s1_08_source_quality import canonical_locator_key
from sec_agent.official_source_attempt_program import SourceResponse
from sec_agent.s1_08_official_discovery_adapter import CaptureFirstOfficialDiscoveryAdapter


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v2_0.json"
MANIFEST = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_dell_r1_restricted_capture_manifest_v1_0.json"
FIXTURE = ROOT / "eval_sets/fin_0_1_3_s1_08_sourcehunter_replay/dell_r1_sanitized_quality_replay_fixture_v1_0.json"
RUNTIME_OBJECTS = ROOT / (
    ".codex_runtime/fin013_s1_08_dell_current_search_canary/"
    "fin013_s1_08_dell_search_admission_d1b8c229b7402e195f14/adapter/objects"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _capture(name: str) -> tuple[str, str]:
    return f"capture/{name}", canonical_digest({"capture": name})


def _candidate(query, suffix: str) -> DiscoveryCandidate:
    discovery_ref, discovery_digest = _capture(f"discovery-{suffix}")
    source_ref, source_digest = _capture(f"source-{suffix}")
    parser_ref, parser_digest = _capture(f"parser-{suffix}")
    return DiscoveryCandidate(
        case_key=query.case_key,
        target_key=query.target_key,
        role_id=query.role_id,
        entity_key=query.case_key,
        title="Current official financial results",
        locator=f"https://example.com/{suffix}",
        published_on="2026-07-01",
        authority="issuer_primary",
        discovery_capture_ref=discovery_ref,
        discovery_capture_digest=discovery_digest,
        source_capture_ref=source_ref,
        source_capture_digest=source_digest,
        parser_capture_ref=parser_ref,
        parser_capture_digest=parser_digest,
        evidence_slot_id=query.evidence_slot_id,
        source_family="issuer_ir_document",
        content_quality_score=20,
    )


def test_v2_catalog_compiles_five_executable_evidence_slots_without_gold() -> None:
    catalog = load_source_catalog(CATALOG)
    slots = compile_evidence_slots(catalog=catalog)
    assert len(slots) == 5
    assert all(slot.required for slot in slots)
    assert all(slot.source_families for slot in slots)
    assert all(slot.stop_condition == "candidate_or_typed_gap" for slot in slots)
    queries = compile_initial_queries(
        catalog=catalog,
        case_key="DELL",
        research_objective="Evaluate demand, value capture, counterevidence and market context.",
    )
    assert {query.evidence_slot_id for query in queries} == {
        slot.slot_id for slot in slots
    }
    assert "external_site_search" not in queries[0].route_ids
    serialized = json.dumps([query.as_dict() for query in queries], ensure_ascii=False)
    assert "DELL_E" not in serialized and "DELL_T" not in serialized


def test_restricted_manifest_matches_all_actual_R1_request_objects_without_emitting_raw() -> None:
    manifest = load_restricted_manifest(MANIFEST)
    audit = audit_restricted_capture_store(
        manifest=manifest,
        runtime_root=RUNTIME_OBJECTS,
    )
    assert audit == {
        "restricted_request_objects_verified": 19,
        "raw_content_emitted": False,
        "headers_emitted": False,
    }


def test_sanitized_replay_passes_quality_transport_and_efficiency_together() -> None:
    result = run_sanitized_quality_replay(
        manifest=load_restricted_manifest(MANIFEST),
        fixture=_load(FIXTURE),
    )
    assert result["status"] == "pass"
    assert result["network_model_provider_retry_calls"] == [0, 0, 0, 0]
    assert result["metrics"]["R1_requests_with_terminal_classification"] == 19
    assert result["metrics"]["request_without_terminal_capture"] == 0
    assert result["metrics"]["known_navigation_noise_fetches"] == 0
    assert result["metrics"]["stale_filing_selected_when_newer_eligible_exists"] == 0
    assert result["metrics"]["evidence_roles_with_candidate_or_typed_gap"] == 5
    assert result["metrics"]["qualified_document_yield"] >= 0.5
    assert result["planner_hidden_gold_visibility"] is False


def test_microsoft_case_and_tracking_variants_deduplicate_canonically() -> None:
    first = canonical_locator_key(
        "https://www.microsoft.com/en-us/Investor/earnings/FY-2026-Q4/metrics"
    )
    second = canonical_locator_key(
        "https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/metrics?icid=tracking"
    )
    assert first == second


class _InterruptingAdapter:
    network_calls = 2
    receipts = ({"status": "captured"},)

    def __init__(self) -> None:
        self.calls = 0
        self.checkpoints: list[dict] = []

    @property
    def checkpoint_refs(self):
        return tuple(
            {"object_key": f"checkpoint/{index}", "digest": canonical_digest(row)}
            for index, row in enumerate(self.checkpoints)
        )

    def persist_candidate_checkpoint(self, snapshot):
        self.checkpoints.append(dict(snapshot))

    def discover(self, query):
        self.calls += 1
        if self.calls == 1:
            return (_candidate(query, "first-qualified"),)
        raise RuntimeError("synthetic unexpected adapter failure")


def test_unexpected_adapter_failure_keeps_partial_candidate_and_checkpoint() -> None:
    adapter = _InterruptingAdapter()
    with pytest.raises(CandidateGenerationInterrupted) as exc:
        run_candidate_generation(
            catalog=load_source_catalog(CATALOG),
            case_key="DELL",
            research_objective="Evaluate demand, value capture, counterevidence and market context.",
            adapter=adapter,
        )
    partial = exc.value.partial_result
    assert partial["terminal_status"] == "partial_failed"
    assert len(partial["accepted_candidates"]) == 1
    assert partial["typed_gaps"][0]["code"] == "candidate_generation_interrupted"
    assert partial["observed_counts"]["network_calls"] == 2
    assert adapter.checkpoints


class _QualityRouteTransport:
    live_network = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls.append(url)
        if url == "https://www.microsoft.com/en-us/investor/":
            body = (
                '<html><body><a data-date="2026-07-30" '
                'href="/en-us/surface/devices/surface-laptop-ultra?icid=footer">'
                'Surface laptop</a><a data-date="2026-07-30" '
                'href="/en-us/Investor/earnings/FY-2026-Q4/metrics">'
                'FY2026 Q4 earnings metrics capital expenditure</a></body></html>'
            ).encode()
            content_type = "text/html"
        elif url.endswith("/Investor/earnings/FY-2026-Q4/metrics"):
            body = (
                b"<html><body>Microsoft earnings metrics describe data center capacity, "
                b"capital expenditure, AI infrastructure demand and customer deployment.</body></html>"
            )
            content_type = "text/html"
        elif url == "https://data.sec.gov/submissions/CIK0001571996.json":
            body = json.dumps(
                {
                    "cik": "0001571996",
                    "filings": {
                        "recent": {
                            "accessionNumber": [
                                "0001571996-26-000010",
                                "0001571996-23-000007",
                                "0001571996-22-000044",
                            ],
                            "filingDate": ["2026-05-28", "2023-02-03", "2022-10-28"],
                            "form": ["10-Q", "10-Q", "10-Q"],
                            "primaryDocument": [
                                "dell-20260528.htm",
                                "dell-20230203.htm",
                                "dell-20221028.htm",
                            ],
                        }
                    },
                }
            ).encode()
            content_type = "application/json"
        elif url.endswith("/dell-20260528.htm"):
            body = (
                b"<html><body>Dell Technologies 10-Q filing includes risk factors, cash flow, "
                b"segment revenue, inventory and financial reconciliation.</body></html>"
            )
            content_type = "text/html"
        else:
            raise AssertionError(f"quality gate should have prevented fetch: {url}")
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": content_type},
            body=body,
        )


def test_adapter_rejects_navigation_before_fetch_and_keeps_current_customer_evidence(tmp_path: Path) -> None:
    catalog = load_source_catalog(CATALOG)
    query = next(
        row
        for row in compile_initial_queries(
            catalog=catalog,
            case_key="DELL",
            research_objective="Evaluate AI infrastructure customer demand and deployment.",
        )
        if row.role_id == "customer_demand_and_deployment_validation"
    )
    transport = _QualityRouteTransport()
    adapter = CaptureFirstOfficialDiscoveryAdapter(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=4,
        document_ceiling_per_query=1,
    )
    candidates = adapter.discover(query)
    assert len(candidates) == 1
    assert candidates[0].source_family == "issuer_ir_document"
    assert not any("surface" in url.lower() for url in transport.calls)
    assert any(
        "navigation_or_commerce_surface" in row.get("reason_codes", [])
        for row in adapter.receipts
    )


def test_adapter_selects_current_SEC_filing_without_fetching_stale_filings(tmp_path: Path) -> None:
    catalog = load_source_catalog(CATALOG)
    query = next(
        row
        for row in compile_initial_queries(
            catalog=catalog,
            case_key="DELL",
            research_objective="Reconcile current filing risk factors and cash flow.",
        )
        if row.role_id == "regulatory_risk_and_financial_reconciliation"
    )
    transport = _QualityRouteTransport()
    adapter = CaptureFirstOfficialDiscoveryAdapter(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=3,
        document_ceiling_per_query=1,
    )
    candidates = adapter.discover(query)
    assert len(candidates) == 1
    assert candidates[0].published_on == "2026-05-28"
    assert not any("20230203" in url or "20221028" in url for url in transport.calls)
    assert sum(
        "stale_for_current_evidence_slot" in row.get("reason_codes", [])
        for row in adapter.receipts
    ) == 2
