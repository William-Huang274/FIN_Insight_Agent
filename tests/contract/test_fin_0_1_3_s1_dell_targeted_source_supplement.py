from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_dell_targeted_source_supplement import (  # noqa: E402
    AUTHORITY_SCHEMA,
    CONTRACT_REF,
    RUN_SCOPE,
    DellTargetedSourceSupplementError,
    execute_dell_targeted_source_supplement,
    load_dell_targeted_source_policy,
    validate_dell_targeted_source_authority,
)
from sec_agent.s1_six_case_local_evidence_pack import (  # noqa: E402
    canonical_digest,
    file_sha256,
    validate_local_evidence_pack,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_dell_targeted_source_supplement_policy_v1_0.json"
)


class FakeTransport:
    def __init__(
        self,
        responses: Mapping[str, SourceResponse],
        *,
        live_network: bool = False,
    ) -> None:
        self.responses = dict(responses)
        self.calls: list[str] = []
        self.live_network = live_network

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SourceResponse:
        del headers, timeout_seconds
        response = self.responses[url]
        assert response.final_url.split("/", 3)[2] in allowed_hosts
        assert len(response.body) <= byte_ceiling
        self.calls.append(url)
        return response


def _response(url: str, text: str, *, content_type: str = "text/html") -> SourceResponse:
    return SourceResponse(
        status_code=200,
        final_url=url,
        headers={"content-type": content_type},
        body=text.encode("utf-8"),
    )


def _responses(
    policy: Mapping[str, Any],
    *,
    omit_dell_margin: bool = False,
) -> dict[str, SourceResponse]:
    by_id = {row["route_id"]: row for row in policy["external_routes"]}
    dell = (
        "Dell booked $24.4 billion in AI orders, recognized $16.1 billion in AI "
        "server revenue and ended with $51.3 billion of backlog. Demand continues "
        "to exceed supply, with memory the primary constraint, across more than "
        "5,000 customers. Memory uncertainty is leading customers to proactively "
        "secure infrastructure across AI and traditional workloads over longer "
        "periods, while Dell maintains pricing and margin discipline. "
    )
    if not omit_dell_margin:
        dell += (
            "AI server profitability remains in line with our mid-single-digit "
            "operating income rate target."
        )
    micron = (
        "DRAM and NAND supply-demand conditions remain tight beyond 2027. "
        "Our Singapore advanced packaging facility will contribute meaningfully "
        "to HBM packaging capacity beginning in the first half of 2027."
    )
    tsmc = (
        "CoWoS remains our main supply for advanced AI packaging, and we are "
        "working hard to provide customers enough capacity."
    )
    market = {
        "data": {
            "tradesTable": {
                "rows": [
                    {
                        "date": "08/06/2026",
                        "close": "$437.65",
                        "volume": "6,094,432",
                        "open": "$450.55",
                        "high": "$455.8699",
                        "low": "$426.00",
                    }
                ]
            }
        }
    }
    return {
        by_id["dell_q1_fy27_earnings_transcript"]["url"]: _response(
            by_id["dell_q1_fy27_earnings_transcript"]["url"], dell
        ),
        by_id["micron_q3_fy26_earnings_slides"]["url"]: _response(
            by_id["micron_q3_fy26_earnings_slides"]["url"], micron
        ),
        by_id["tsmc_q1_2026_earnings_transcript"]["url"]: _response(
            by_id["tsmc_q1_2026_earnings_transcript"]["url"], tsmc
        ),
        by_id["nasdaq_dell_historical_2026_08_06"]["url"]: SourceResponse(
            status_code=200,
            final_url=by_id["nasdaq_dell_historical_2026_08_06"]["url"],
            headers={"content-type": "application/json"},
            body=json.dumps(market).encode("utf-8"),
        ),
    }


def _execute(tmp_path: Path, *, omit_dell_margin: bool = False):
    policy = load_dell_targeted_source_policy(POLICY_PATH, repo_root=ROOT)
    transport = FakeTransport(
        _responses(policy, omit_dell_margin=omit_dell_margin)
    )
    result = execute_dell_targeted_source_supplement(
        policy=policy,
        repo_root=ROOT,
        runtime_root=tmp_path / "runtime",
        transport=transport,
        observed_at="2026-08-10T10:00:00Z",
        execution_commit="fixture",
    )
    return policy, result, transport, tmp_path / "runtime"


def _load_dell_pack(result: Mapping[str, Any], runtime: Path) -> dict[str, Any]:
    reference = result["pack_artifacts"]["DELL"]
    path = runtime / "objects" / reference["object_key"]
    pack = json.loads(path.read_text(encoding="utf-8"))
    validate_local_evidence_pack(pack)
    return pack


def _authority(policy: Mapping[str, Any]) -> dict[str, Any]:
    bindings = {
        str(POLICY_PATH.relative_to(ROOT)).replace("\\", "/"): file_sha256(
            POLICY_PATH
        ),
        "src/sec_agent/s1_dell_targeted_source_supplement.py": file_sha256(
            ROOT / "src/sec_agent/s1_dell_targeted_source_supplement.py"
        ),
    }
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "issued_unconsumed",
        "issued_at": "2026-08-10T00:00:00Z",
        "expires_at": "2026-08-11T00:00:00Z",
        "implementation_commit": "a" * 40,
        "clean_proof_digest": "b" * 64,
        "admission_id": "admission::dell-targeted-source-test",
        "run_id": "dell-targeted-source-test",
        "attempt_id": "dell-targeted-source-test::attempt_1",
        "maximum_executions": 1,
        "automatic_execution": False,
        "automatic_retry": False,
        "business_artifact_promotion": False,
        "evidence_promotion_mode": "local_deterministic_adjudication_only",
        "model_calls_allowed": 0,
        "policy_digest": canonical_digest(policy),
        "budget": deepcopy(policy["budget"]),
        "file_bindings": bindings,
    }
    return {**body, "authority_digest": canonical_digest(body)}


def test_targeted_supplement_adds_decision_surfaces_without_cross_company_attribution(
    tmp_path: Path,
) -> None:
    _policy, result, transport, runtime = _execute(tmp_path)
    assert result["status"] == "terminal_succeeded_targeted_source_successor_pack_ready"
    assert len(transport.calls) == 4
    assert result["observed_counts"] == {
        "local_source_records_adjudicated": 5,
        "external_source_fragments_expected": 7,
        "external_source_fragments_adjudicated": 7,
        "new_dell_evidence_items": 12,
        "dell_evidence_items_before": 15,
        "dell_evidence_items_after": 27,
        "dell_residual_gaps_before": 16,
        "dell_residual_gaps_after": 14,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "retries": 0,
    }
    pack = _load_dell_pack(result, runtime)
    by_target = {row["target_id"]: row for row in pack["evidence_items"]}
    hpe = by_target[
        "SUPPLEMENT::DELL::COMPETITOR::HPE::PRIOR_ORDER_DIGESTION"
    ]
    assert hpe["disposition"] == "accepted_bounded_context_evidence"
    assert hpe["causal_attribution_authorized"] is False
    assert "不能证明 Dell" in hpe["slot_bindings"][0]["claim_boundary_zh"]
    market = by_target["NASDAQ::DELL::HISTORICAL::2026-08-06"]
    assert market["disposition"] == "accepted_independent_market_evidence"
    assert market["evidence_role"] == "independent_market_point_in_time"
    gaps = {row["gap_id"]: row for row in pack["residual_gaps"]}
    assert "dell-gap-ai-system-margin" not in gaps
    assert "dell-gap-valuation-basis" not in gaps
    assert gaps["dell-gap-hbm-supply"]["facet_id"] == (
        "dell_specific_hbm_supply_allocation"
    )
    body = deepcopy(result)
    supplied = body.pop("result_digest")
    assert supplied == canonical_digest(body)


def test_missing_required_issuer_fragment_retains_gap_and_blocks_model_live_gate(
    tmp_path: Path,
) -> None:
    _policy, result, _transport, runtime = _execute(
        tmp_path, omit_dell_margin=True
    )
    assert result["status"] == (
        "terminal_completed_targeted_source_successor_pack_with_typed_gaps"
    )
    assert result["stage_acceptance"][
        "successor_pack_ready_for_zero_call_input_compilation"
    ] is False
    pack = _load_dell_pack(result, runtime)
    gaps = {row["gap_id"]: row for row in pack["residual_gaps"]}
    assert "dell-gap-ai-system-margin" in gaps
    assert "dell-gap-valuation-basis" not in gaps


def test_local_corpus_binding_mutation_fails_closed() -> None:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    policy["local_corpus"]["sha256"] = "0" * 64
    mutated = POLICY_PATH.with_name("unused-mutated-policy.json")
    # Loader validation is exercised without writing the mutation to the repo.
    from unittest.mock import patch

    with patch(
        "sec_agent.s1_dell_targeted_source_supplement._read_json",
        return_value=policy,
    ):
        try:
            load_dell_targeted_source_policy(mutated, repo_root=ROOT)
        except DellTargetedSourceSupplementError as exc:
            assert exc.code == (
                "dell_targeted_source_policy_binding_invalid:local_corpus"
            )
        else:
            raise AssertionError("local corpus digest mutation must fail closed")


def test_fake_live_consumes_exact_once_admission_and_records_terminal_receipt(
    tmp_path: Path,
) -> None:
    policy = load_dell_targeted_source_policy(POLICY_PATH, repo_root=ROOT)
    authority = _authority(policy)
    transport = FakeTransport(_responses(policy), live_network=True)
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "admissions.sqlite3")
    result = execute_dell_targeted_source_supplement(
        policy=policy,
        repo_root=ROOT,
        runtime_root=tmp_path / "live-runtime",
        transport=transport,
        observed_at="2026-08-10T10:00:00Z",
        execution_commit="a" * 40,
        authority=authority,
        shared_admission_ledger=ledger,
    )
    assert result["status"] == "terminal_succeeded_targeted_source_successor_pack_ready"
    assert result["observed_counts"]["network_calls"] == 4
    assert len(transport.calls) == 4
    receipt = ledger.read(authority["authority_digest"])
    assert receipt.state == "terminal"
    assert receipt.terminal_status == "success"


def test_authority_budget_mutation_fails_closed() -> None:
    policy = load_dell_targeted_source_policy(POLICY_PATH, repo_root=ROOT)
    authority = _authority(policy)
    authority["budget"]["source_network_calls"] = 5
    body = deepcopy(authority)
    body.pop("authority_digest", None)
    authority["authority_digest"] = canonical_digest(body)
    try:
        validate_dell_targeted_source_authority(
            authority,
            policy=policy,
            repo_root=ROOT,
            observed_at="2026-08-10T10:00:00Z",
        )
    except DellTargetedSourceSupplementError as exc:
        assert exc.code == "dell_targeted_source_authority_boundary_invalid"
    else:
        raise AssertionError("authority budget mutation must fail closed")


def test_targeted_source_live_scope_is_registered_and_not_silently_overridden() -> None:
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    assert preflight["scope_resolution"] == {
        "status": "registered",
        "canonical_scope_id": RUN_SCOPE,
        "owner_stage": "S1",
        "operation_class": "live_search_execution",
        "parent_scope_id": "FIN_0_1_3_S1_08",
    }
    assert preflight["status"] == "pass"
    assert preflight["open_full_chain_blocker_count"] == 0
    assert preflight["allow_open_blockers"] is False
