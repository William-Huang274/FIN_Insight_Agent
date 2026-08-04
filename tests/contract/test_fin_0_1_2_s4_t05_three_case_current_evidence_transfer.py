from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [
    str(ROOT),
    str(ROOT / "src"),
    str(ROOT / "tests" / "contract"),
]

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.bounded_agent_contract_policies import (
    FIN_0_1_2_S4_T05_DELL_CURRENT_EVIDENCE_PROFILE_REF,
    FIN_0_1_2_S4_T05_MU_CURRENT_EVIDENCE_PROFILE_REF,
    FIN_0_1_2_S4_T05_NVDA_CURRENT_EVIDENCE_PROFILE_REF,
    estimate_provider_input_tokens,
)
from apps.workbench.backend.application.fin_0_1_2_s4_natural_case_entry import (
    load_current_fin_0_1_2_s4_t01_case_entry,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    CASE_SEARCH_PROFILES,
    Fin012S4T03SearchError,
    Fin012S4T03SearchRunner,
    SearchAdmission,
    SourceResponse,
    compile_current_case_executable_requests,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t04_current_evidence_research import (
    compile_current_case_evidence_pack,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t05_three_case_transfer import (
    Fin012S4T05TransferError,
    compile_case_transfer_surface,
    compile_current_case_agent_input,
    compile_legacy_oracle_agent_input,
    load_transfer_profile_contract,
    validate_transfer_evidence_pack,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_2_s1_bounded_production_consumer_migration import (
    _fin012_runtime,
)
from test_fin_0_1_2_s3_t02_production_runtime_integration import (
    _CurrentS3ProductionFake,
)


FILINGS = {
    "DELL": (
        ("0001571996-26-000021", "8-K", "2026-05-28", "dell-20260528.htm"),
        ("0001571996-25-000127", "10-Q", "2025-12-09", "dell-20251031.htm"),
        ("0001571996-25-000034", "10-K", "2025-03-25", "dell-20250131.htm"),
        ("0001571996-24-000036", "10-K", "2024-03-25", "dell-20240202.htm"),
        ("0001571996-23-000007", "10-K", "2023-03-30", "dell-20230203.htm"),
    ),
    "MU": (
        ("0000723125-26-000006", "10-Q", "2026-03-19", "mu-20260226.htm"),
        ("0000723125-25-000028", "10-K", "2025-10-03", "mu-20250828.htm"),
        ("0000723125-24-000027", "10-K", "2024-10-04", "mu-20240829.htm"),
        ("0000723125-23-000054", "10-K", "2023-10-06", "mu-20230831.htm"),
    ),
    "NVDA": (
        ("0001045810-26-000051", "8-K", "2026-05-20", "nvda-20260520.htm"),
        ("0001045810-25-000230", "10-Q", "2025-11-19", "nvda-20251026.htm"),
        ("0001045810-25-000023", "10-K", "2025-02-26", "nvda-20250126.htm"),
        ("0001045810-24-000029", "10-K", "2024-02-21", "nvda-20240128.htm"),
        ("0001045810-23-000017", "10-K", "2023-02-24", "nvda-20230129.htm"),
    ),
}

IMPLEMENTATION_REF = (
    "configs/releases/"
    "fin_ia_0_1_2_s4_t05_three_case_current_evidence_transfer_package_"
    "zero_call_implementation_v1_0.json"
)
PROJECTION_REF = (
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_51.json"
)


class _CaseSecTransport:
    live_network = False

    def __init__(self, case_key: str) -> None:
        rows = FILINGS[case_key]
        self.body = json.dumps(
            {
                "filings": {
                    "recent": {
                        "accessionNumber": [row[0] for row in rows],
                        "form": [row[1] for row in rows],
                        "filingDate": [row[2] for row in rows],
                        "primaryDocument": [row[3] for row in rows],
                    }
                }
            }
        ).encode("utf-8")

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
    ) -> SourceResponse:
        assert "Authorization" not in headers
        assert "Cookie" not in headers
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "application/json"},
            body=self.body,
        )


class _CurrentVerifierCompiledAtomFake:
    """Keep the T05 12/9 transport while honoring the compact verifier view."""

    def __init__(self, base: Any) -> None:
        self.base = base

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.base.calls

    @property
    def compiled_calls(self) -> int:
        return self.base.compiled_calls

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        analysis = request.get("analysis_input")
        if (
            request.get("node_id") == "verifier"
            and isinstance(analysis, Mapping)
            and analysis.get("model_view_contract_ref")
            == "fin01.s4.t04.current_evidence.verifier_model_view:v1"
        ):
            self.base.calls.append({"kwargs": dict(kwargs), "request": request})
            return _CurrentS3ProductionFake._response(
                {
                    "findings": [
                        {
                            "layer": layer,
                            "status": "pass",
                            "issue_codes": [],
                            "artifact_or_claim_refs": [],
                            "repair_owner": None,
                        }
                        for layer in analysis["required_layers"]
                    ],
                    "bound_lead_digest": analysis["cross_cell_lead_digest"],
                    "bound_writer_digest": analysis["writer_digest"],
                    "decision": "accept_for_internal_review",
                },
                len(self.base.calls),
            )
        return self.base(**kwargs)


def _search_and_pack(case_key: str, tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    requests = compile_current_case_executable_requests(case_key)
    admission = SearchAdmission.create(
        case_key=case_key,
        issued_at="2026-08-04T00:00:00Z",
        expires_at="2026-08-05T00:00:00Z",
        request_digests=tuple(row.request_digest for row in requests),
    )
    terminal = Fin012S4T03SearchRunner(
        repository_root=ROOT,
        runtime_root=tmp_path / case_key.lower(),
        transport=_CaseSecTransport(case_key),
    ).execute(
        admission=admission,
        now="2026-08-04T12:00:00Z",
        run_nonce=f"t05-transfer-{case_key.lower()}-full-fake",
    )
    pack = compile_current_case_evidence_pack(
        terminal,
        terminal_digest=terminal["terminal_object"]["digest"],
        t01_entry=load_current_fin_0_1_2_s4_t01_case_entry(case_key),
        case_key=case_key,
    )
    return terminal, validate_transfer_evidence_pack(pack, case_key=case_key)


@pytest.fixture(scope="module")
def three_case_search_packs(
    tmp_path_factory: pytest.TempPathFactory,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    root = tmp_path_factory.mktemp("fin012-s4-t05-three-case-search")
    return {
        case_key: _search_and_pack(case_key, root)
        for case_key in ("DELL", "MU", "NVDA")
    }


def test_profile_contract_is_single_content_addressed_source_for_three_cases() -> None:
    contract = load_transfer_profile_contract(ROOT)
    assert [row["case_key"] for row in contract["cases"]] == ["DELL", "MU", "NVDA"]
    assert contract["profiles_digest"] == canonical_digest(
        {key: value for key, value in contract.items() if key != "profiles_digest"}
    )
    for case_key in ("DELL", "MU", "NVDA"):
        surface = compile_case_transfer_surface(case_key, repository_root=ROOT)
        assert surface["case_key"] == case_key
        assert len(surface["executable_requests"]) == 3
        assert len(set(surface["executable_request_digests"])) == 3
        assert surface["regression_oracle"]["current_product_proof"] is False
        assert surface["nonpromotion_boundary"] == {
            "live_source_calls_authorized": False,
            "model_calls_authorized": False,
            "provider_calls_authorized": False,
            "regression_oracle_promoted": False,
            "product_acceptance_changed": False,
        }
        assert set(surface["official_source_profile"]["allowed_source_hosts"]) == set(
            CASE_SEARCH_PROFILES[case_key]["allowed_source_hosts"]
        )
        if case_key in {"DELL", "MU"}:
            oracle_input = compile_legacy_oracle_agent_input(
                case_key, repository_root=ROOT
            )
            assert oracle_input.company == case_key
            assert oracle_input.s4_case_runtime["paid_execution_authorized"] is False


def test_T05_A_result_and_projection_are_content_addressed_and_nonpromotable() -> None:
    result = json.loads((ROOT / IMPLEMENTATION_REF).read_text(encoding="utf-8"))
    assert result["implementation_digest"] == canonical_digest(
        {
            key: value
            for key, value in result.items()
            if key != "implementation_digest"
        }
    )
    for binding in result["immutable_bindings"]:
        assert hashlib.sha256((ROOT / binding["ref"]).read_bytes()).hexdigest() == (
            binding["sha256"]
        )
    assert result["observed_external_counts"] == {
        "model_calls": 0,
        "provider_calls": 0,
        "execution_network_calls": 0,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "admissions": 0,
        "research_runs": 0,
        "business_artifacts": 0,
        "paired_assessments": 0,
        "owner_acceptances": 0,
    }
    projection = json.loads((ROOT / PROJECTION_REF).read_text(encoding="utf-8"))
    truth = projection["current_truth"]
    assert truth["S4_T05_A"] == "engineering_pass_zero_call"
    assert truth["DELL_current_R2"] is False
    assert truth["MU_current_R2"] is False
    assert truth["post_transfer_NVDA_R2"] is False
    assert projection["authority_boundary"]["T05_B_DELL_live_authorized"] is False


def test_profile_or_request_cross_case_mutation_fails_closed() -> None:
    request = compile_current_case_executable_requests("DELL")[0]
    with pytest.raises(Fin012S4T03SearchError, match="t03_executable_request_digest_mismatch"):
        replace(request, target_entity_ref="MU").require_valid()
    contract = deepcopy(load_transfer_profile_contract(ROOT))
    contract["cases"][0]["issuer_cik"] = "0000723125"
    path = ROOT / contract["cases"][0]["regression_oracle_ref"]
    assert path.is_file()
    with pytest.raises(Fin012S4T05TransferError, match="s4_t05_case_unsupported"):
        compile_case_transfer_surface("AMD", repository_root=ROOT)


@pytest.mark.parametrize("case_key", ("DELL", "MU", "NVDA"))
def test_three_case_search_gate_full_fake_reaches_uniform_18_15_3_contract(
    case_key: str,
    three_case_search_packs: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    terminal, pack = three_case_search_packs[case_key]
    assert terminal["status"] == "success"
    assert terminal["observed_counts"]["source_calls"] == 1
    assert terminal["observed_counts"]["local_retrieval_or_tool_invocations"] == 6
    assert terminal["observed_counts"]["accepted_candidates"] == 18
    assert [len(pack["evidence_rows"]), len(pack["numeric_rows"])] == [15, 3]
    assert len(pack["typed_gaps"]) == 3
    assert all(row["entity_ref"] == case_key for row in pack["evidence_rows"])
    assert all(row["entity_ref"] == case_key for row in pack["numeric_rows"])
    assert terminal["observed_counts"]["model_calls"] == 0
    assert terminal["observed_counts"]["provider_calls"] == 0


def test_cross_case_date_numeric_and_lineage_mutations_fail_closed(
    three_case_search_packs: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    _, pack = three_case_search_packs["MU"]
    mutations = []
    cross_case = deepcopy(pack)
    cross_case["evidence_rows"][0]["entity_ref"] = "DELL"
    mutations.append(cross_case)
    future = deepcopy(pack)
    future["evidence_rows"][0]["published_at"] = "2027-01-01"
    mutations.append(future)
    numeric = deepcopy(pack)
    numeric["numeric_rows"][0]["value"] = "999999999999"
    mutations.append(numeric)
    lineage = deepcopy(pack)
    lineage["evidence_rows"][0]["parser_lineage"]["parser_digest"] = "0" * 64
    mutations.append(lineage)
    for changed in mutations:
        changed["evidence_pack_digest"] = canonical_digest(
            {key: value for key, value in changed.items() if key != "evidence_pack_digest"}
        )
        with pytest.raises(Exception):
            validate_transfer_evidence_pack(changed, case_key="MU")


@pytest.mark.parametrize("case_key", ("DELL", "MU", "NVDA"))
def test_current_shared_runtime_full_fake_reaches_nine_artifacts_for_each_case(
    monkeypatch: pytest.MonkeyPatch,
    case_key: str,
    three_case_search_packs: dict[str, tuple[dict[str, Any], dict[str, Any]]],
) -> None:
    baseline, admission, legacy_fake = _fin012_runtime(case_key)
    fake = _CurrentVerifierCompiledAtomFake(legacy_fake)
    input_pack = compile_current_case_agent_input(
        baseline,
        three_case_search_packs[case_key][1],
        case_key=case_key,
    )
    admission = admission.model_copy(
        update={
            "admission_id": f"fin012-s4-t05-{case_key.lower()}-current-full-fake",
            "case_id": input_pack.case_id,
            "case_version": input_pack.case_version,
            "as_of": input_pack.as_of,
            "input_digest": input_pack.input_digest,
            "execution_mode": "zero_call_t05_current_evidence_transfer_full_fake",
            "research_profile_ref": {
                "DELL": FIN_0_1_2_S4_T05_DELL_CURRENT_EVIDENCE_PROFILE_REF,
                "MU": FIN_0_1_2_S4_T05_MU_CURRENT_EVIDENCE_PROFILE_REF,
                "NVDA": FIN_0_1_2_S4_T05_NVDA_CURRENT_EVIDENCE_PROFILE_REF,
            }[case_key],
        }
    )
    admission.assert_profile_admissible()
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": f"fin012-s4-t05-{case_key.lower()}-shared-full-fake",
            "attempt_id": f"fin012-s4-t05-{case_key.lower()}-shared-full-fake",
        },
    )
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    assert len(result.provider_output_captures) == 12
    artifact_text = json.dumps(
        [row.model_dump(mode="json") for row in result.artifacts],
        ensure_ascii=False,
        sort_keys=True,
    )
    assert three_case_search_packs[case_key][1]["evidence_pack_digest"] in (
        artifact_text
    )
    assert f'"entity_label": "{case_key}"' in artifact_text
    assert all(
        f'"entity_label": "{other_case}"' not in artifact_text
        for other_case in {"DELL", "MU", "NVDA"} - {case_key}
    )
    assert len(fake.calls) == 12
    assert fake.compiled_calls == 9
    assert input_pack.company == case_key
    if case_key in {"DELL", "MU"}:
        assert tuple(input_pack.lineage) == (
            "S4_T02_case_pack",
            "S4_T02_method_contract",
            "S4_T03_runtime_binding",
            "S4_T04_source_grounded_input",
            "S4_research_profile_overlay",
        )
        assert input_pack.s4_case_runtime is not None
        assert input_pack.lineage["S4_T04_source_grounded_input"]["digest"] == (
            three_case_search_packs[case_key][1]["evidence_pack_digest"]
        )
        assert input_pack.s4_case_runtime["source_grounded_input"][
            "source_pack_digest"
        ] == three_case_search_packs[case_key][1]["evidence_pack_digest"]
    else:
        assert tuple(input_pack.lineage) == (
            "T02_runtime_plan",
            "T03_evidence_route_plan",
            "T04_financial_pack",
            "T05_graph_pack",
            "T06_judgment_contract",
            "T07_presentation_contract",
        )
        assert input_pack.s4_case_runtime is None
        assert input_pack.lineage["T04_financial_pack"]["digest"] == (
            three_case_search_packs[case_key][1]["evidence_pack_digest"]
        )
    projected_tokens = [
        estimate_provider_input_tokens(
            str(row["kwargs"]["messages"][0]["content"])
            + str(row["kwargs"]["messages"][1]["content"])
        )
        for row in fake.calls
    ]
    assert max(projected_tokens) < 108000
    assert (
        admission.max_semantic_model_calls,
        admission.max_provider_calls,
        admission.max_network_calls,
        admission.max_transport_attempts_per_call,
        admission.retry_budget,
    ) == (12, 12, 12, 1, 0)
