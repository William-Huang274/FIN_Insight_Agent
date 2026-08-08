from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_08_candidate_generation_runtime import DiscoveryQuery
from sec_agent.s1_08_external_combined_live import (
    EXACT_LIVE_SCOPE,
    FacetBoundOfficialAdapter,
    S108ExternalCombinedError,
    compile_external_combined_plan,
    execute_external_combined,
    issue_external_combined_admission,
    load_bound_inputs,
    load_external_combined_policy,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_external_combined_live_policy_v1_0.json"


@pytest.fixture()
def compiled() -> tuple[dict, dict, dict]:
    policy = load_external_combined_policy(POLICY_PATH)
    inputs = load_bound_inputs(repo_root=ROOT, policy=policy)
    plan = compile_external_combined_plan(policy=policy, bound_inputs=inputs)
    return policy, inputs, plan


def test_combined_plan_uses_local_facets_and_covers_all_required_slots(compiled) -> None:
    _, _, plan = compiled
    assert plan["counts"] == {
        "official_query_facet_plans": 18,
        "shadow_query_facet_plans": 24,
        "required_case_slot_opportunities": 12,
        "accepted_model_atoms": 0,
    }
    assert {row["case_key"] for row in plan["official_plan_rows"]} == {
        "DELL",
        "MU",
        "NVDA",
    }
    assert all(row["request_body"]["limit"] == 10 for row in plan["shadow_plan_rows"])
    assert all("http" not in row["request_body"]["query"] for row in plan["shadow_plan_rows"])


@pytest.mark.parametrize(
    ("input_key", "field", "value"),
    [
        ("query_atom_result", "status", "accepted"),
        ("query_facet_proof", "plan_count", 35),
        ("progression_plan", "status", "internal_started_early"),
    ],
)
def test_combined_plan_fails_closed_on_bound_input_mutation(
    compiled, input_key: str, field: str, value
) -> None:
    policy, inputs, _ = compiled
    mutated = deepcopy(inputs)
    mutated[input_key][field] = value
    with pytest.raises(S108ExternalCombinedError):
        compile_external_combined_plan(policy=policy, bound_inputs=mutated)


@dataclass
class _Delegate:
    prepared: list[DiscoveryQuery]
    discovered: list[DiscoveryQuery]
    network_calls: int = 0
    document_fetches: int = 0

    def prepare_attempt(self, *, query, **_) -> None:
        self.prepared.append(query)

    def discover(self, query):
        self.discovered.append(query)
        return ()

    def persist_candidate_checkpoint(self, _snapshot) -> None:
        return None


def test_official_adapter_binds_facet_text_and_digest(compiled) -> None:
    _, _, plan = compiled
    rows = [row for row in plan["official_plan_rows"] if row["case_key"] == "DELL"]
    row = rows[0]
    delegate = _Delegate([], [])
    adapter = FacetBoundOfficialAdapter(delegate=delegate, plan_rows=rows)
    original = DiscoveryQuery(
        case_key="DELL",
        target_key="dell_test",
        role_id="issuer_results",
        revision=0,
        query_text="weak raw query",
        route_ids=("issuer_ir",),
        entity_keys=(row["evidence_owner_entity_key"],),
        prior_reason="initial_role_plan",
        query_digest=canonical_digest("weak raw query"),
        evidence_slot_id=row["evidence_slot_id"],
    )
    adapter.prepare_attempt(
        query=original,
        network_call_allowance=1,
        maximum_document_fetches=1,
        protected_document_fetches=1,
    )
    adapter.discover(original)
    assert delegate.prepared[0] == delegate.discovered[0]
    assert delegate.prepared[0].query_digest != original.query_digest
    assert row["exact_lookup_query"] in delegate.prepared[0].query_text
    assert row["lexical_query"] in delegate.prepared[0].query_text
    assert adapter.bound_query_receipts[0]["query_facet_plan_digests"] == [
        row["plan_digest"]
    ]


def test_official_adapter_preserves_zero_network_market_context(compiled) -> None:
    _, _, plan = compiled
    delegate = _Delegate([], [])
    adapter = FacetBoundOfficialAdapter(
        delegate=delegate,
        plan_rows=[
            row for row in plan["official_plan_rows"] if row["case_key"] == "DELL"
        ],
    )
    query = DiscoveryQuery(
        case_key="DELL",
        target_key="dell_market",
        role_id="market_expectation_context",
        revision=0,
        query_text="local market snapshot",
        route_ids=("current_market_snapshot",),
        entity_keys=("DELL",),
        prior_reason="initial_role_plan",
        query_digest=canonical_digest("local market snapshot"),
        evidence_slot_id="market_expectation_context",
        slot_budget_group="market_context",
    )
    adapter.prepare_attempt(
        query=query,
        network_call_allowance=0,
        maximum_document_fetches=0,
        protected_document_fetches=0,
    )
    assert delegate.prepared == [query]
    assert adapter.bound_query_receipts[0]["binding_state"] == (
        "local_market_context_zero_network_exempt"
    )


class _UnusedTransport:
    live_network = False


def _authority() -> dict:
    body = {
        "schema_version": "test_authority",
        "status": "approved_one_external_combined_exact_live",
        "exact_live_authority": {
            "scope": EXACT_LIVE_SCOPE,
            "maximum_admissions": 1,
            "maximum_executions": 1,
            "network_call_ceiling": 72,
            "retry_ceiling": 0,
            "model_call_ceiling": 0,
        },
    }
    return {**body, "authority_digest": canonical_digest(body)}


def _admission(policy: dict, plan: dict) -> dict:
    return issue_external_combined_admission(
        policy=policy,
        plan=plan,
        authority=_authority(),
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        zero_call_proof_sha256="e" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        run_nonce="test-nonce",
    )


def _fake_official(**values) -> dict:
    case_key = values["case_key"]
    return {
        "case_key": case_key,
        "status": "completed",
        "terminal_code": "fake_official_complete",
        "candidate_result": {
            "case_key": case_key,
            "terminal_status": "complete",
            "selected_candidates": [],
            "typed_gaps": [],
        },
        "network_calls": 2,
        "document_fetches": 1,
        "bound_query_receipts": [
            {"query_facet_plan_digest": row["plan_digest"]}
            for row in values["plan_rows"]
        ],
    }


def _firecrawl_ok(_endpoint: str, request: bytes, _timeout: int) -> tuple[int, bytes]:
    query = json.loads(request.decode("utf-8"))["query"]
    payload = {
        "success": True,
        "id": canonical_digest(query)[:12],
        "creditsUsed": 1,
        "data": {
            "web": [
                {
                    "url": "https://example.com/" + canonical_digest(query)[:12],
                    "title": query[:80],
                    "description": "captured candidate only",
                    "position": 1,
                }
            ]
        },
    }
    return 200, json.dumps(payload).encode("utf-8")


def _execute(tmp_path: Path, compiled, *, firecrawl_call=_firecrawl_ok) -> dict:
    policy, inputs, plan = compiled
    return execute_external_combined(
        admission=_admission(policy, plan),
        policy=policy,
        plan=plan,
        catalog=inputs["source_catalog"],
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        runtime_root=tmp_path / "runtime",
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "ledger.json"),
        official_transport=_UnusedTransport(),
        firecrawl_call=firecrawl_call,
        official_lane_executor=_fake_official,
        observed_at="2026-08-09T01:00:00Z",
    )


def test_full_fake_terminalizes_both_lanes_and_preserves_boundaries(
    tmp_path: Path, compiled
) -> None:
    result = _execute(tmp_path, compiled)
    assert result["status"] == "completed"
    assert len(result["official_case_results"]) == 3
    assert len(result["firecrawl_shadow_results"]) == 24
    assert result["observed_counts"] == {
        "official_cases_terminalized": 3,
        "shadow_queries_terminalized": 24,
        "official_network_calls": 6,
        "shadow_provider_calls": 24,
        "shadow_network_calls": 24,
        "network_calls": 30,
        "document_fetches": 3,
        "model_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
        "evidence_promotions": 0,
        "retry_calls": 0,
        "fallback_calls": 0,
    }
    assert all(
        row["provider_projection"]["locators"][0]["writer_citable"] is False
        for row in result["firecrawl_shadow_results"]
    )
    assert (tmp_path / "runtime/terminal-result.json").is_file()


def test_systemic_shadow_rejection_stops_network_but_terminalizes_all(
    tmp_path: Path, compiled
) -> None:
    calls = 0

    def rejected(*_args) -> tuple[int, bytes]:
        nonlocal calls
        calls += 1
        return 403, b'{"message":"forbidden"}'

    result = _execute(tmp_path, compiled, firecrawl_call=rejected)
    assert calls == 1
    assert result["status"] == "completed_with_typed_failures"
    assert len(result["firecrawl_shadow_results"]) == 24
    assert result["observed_counts"]["shadow_network_calls"] == 1
    assert sum(row["network_call_attempted"] for row in result["firecrawl_shadow_results"]) == 1


def test_raw_response_is_saved_before_parse_failure(tmp_path: Path, compiled) -> None:
    def invalid_json(*_args) -> tuple[int, bytes]:
        return 200, b"not-json"

    result = _execute(tmp_path, compiled, firecrawl_call=invalid_json)
    first = result["firecrawl_shadow_results"][0]
    assert first["terminal_code"] == "firecrawl_shadow_transport_or_parse_error"
    assert (tmp_path / "runtime/firecrawl-shadow" / first["capture_refs"]["raw_response"]).is_file()


def test_shared_ledger_rejects_duplicate_consumption(tmp_path: Path, compiled) -> None:
    policy, inputs, plan = compiled
    admission = _admission(policy, plan)
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "ledger.json")
    common = dict(
        admission=admission,
        policy=policy,
        plan=plan,
        catalog=inputs["source_catalog"],
        execution_git_commit="a" * 40,
        runner_sha256="b" * 64,
        runtime_module_sha256="c" * 64,
        policy_sha256="d" * 64,
        shared_ledger=ledger,
        official_transport=_UnusedTransport(),
        firecrawl_call=_firecrawl_ok,
        official_lane_executor=_fake_official,
        observed_at="2026-08-09T01:00:00Z",
    )
    execute_external_combined(runtime_root=tmp_path / "runtime-a", **common)
    with pytest.raises(SharedAdmissionLedgerError):
        execute_external_combined(runtime_root=tmp_path / "runtime-b", **common)
