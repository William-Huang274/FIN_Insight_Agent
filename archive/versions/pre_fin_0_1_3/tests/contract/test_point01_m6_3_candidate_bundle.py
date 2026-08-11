from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.candidate_bundle import CandidateBundleCompiler, CandidateBundleError, CandidateMetadata, CandidateMetadataSnapshot


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_3_candidate_bundle_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_metadata_bundle_is_replayable_and_retains_expansion_kinds() -> None:
    request, plan = RUNNER.issuer_request_and_plan()
    compiler = CandidateBundleCompiler(policy=RUNNER.policy())
    first = compiler.compile(request=request, plan=plan, snapshot=RUNNER.metadata_snapshot())
    second = compiler.compile(request=request, plan=plan, snapshot=RUNNER.metadata_snapshot())
    assert first.bundle.bundle_digest == second.bundle.bundle_digest
    assert first.bundle.status == "metadata_fixture_compiled"
    assert first.bundle.top_k_candidate_ids == ("candidate-filing-seed",)
    assert first.bundle.neighbor_candidate_ids == ("candidate-filing-neighbor",)
    assert first.bundle.table_context_candidate_ids == ("candidate-filing-table",)
    assert first.retrieval_call_count == first.external_call_count == first.store_write_count == 0


def test_missing_context_and_absent_metadata_are_typed_exhaustion() -> None:
    request, plan = RUNNER.issuer_request_and_plan()
    compiler = CandidateBundleCompiler(policy=RUNNER.policy())
    missing_table = compiler.compile(request=request, plan=plan, snapshot=RUNNER.metadata_snapshot(include_table=False)).bundle
    empty = compiler.compile(request=request, plan=plan, snapshot=CandidateMetadataSnapshot.create(snapshot_id="empty", candidates=())).bundle
    assert missing_table.status == "retrieval_exhausted"
    assert missing_table.typed_gap_codes == ("required_context_kind_missing:table_context",)
    assert empty.exhaustion_status == "metadata_candidate_absent"


def test_rejects_request_plan_route_and_snapshot_execution_bypasses() -> None:
    request, plan = RUNNER.issuer_request_and_plan()
    compiler = CandidateBundleCompiler(policy=RUNNER.policy())
    with pytest.raises(CandidateBundleError, match="tool_selection_plan_request_lineage_mismatch"):
        compiler.compile(request=request, plan=plan.model_copy(update={"request_digest": "wrong"}), snapshot=RUNNER.metadata_snapshot())
    with pytest.raises(CandidateBundleError, match="candidate_metadata_snapshot_must_be_fixture_only"):
        CandidateMetadataSnapshot.create(snapshot_id="live", candidates=(), fixture_only=False)
    wrong_route = CandidateMetadataSnapshot.create(
        snapshot_id="wrong-route",
        candidates=(CandidateMetadata(candidate_id="wrong-route", document_id="doc", document_version="v1", source_snapshot_ref="source", source_policy_ref="issuer_first", route_id="unselected-route", source_role="issuer_disclosure", source_authority_rank=5, entity_ref="AAA", period_ref="latest_fiscal_period", candidate_kind="top_k_seed", section_or_table_ref="section", metadata_rank=1, content_ref="object://fixture/wrong"),),
    )
    bundle = compiler.compile(request=request, plan=plan, snapshot=wrong_route).bundle
    assert bundle.status == "retrieval_exhausted"
    assert bundle.typed_gap_codes == ("candidate_route_not_selected",)


def test_review_is_user_scoped_and_does_not_claim_independent_human_signoff() -> None:
    review = json.loads((ROOT / "configs/engineering_handoff/point01_m6_3_cross_owner_design_review_v1_0.json").read_text(encoding="utf-8"))
    assert review["status"] == "user_confirmed_structured_cross_owner_review_accepted_for_m6_3"
    assert review["independent_human_or_multi_person_signoff"] is False
    assert review["user_confirmation"]["decision"] == "approve_m6_3_deterministic_metadata_candidate_bundle_only"


def test_m6_3_fixture_runner_is_metadata_only_and_execution_free(tmp_path: Path) -> None:
    output = tmp_path / "m6_3_fixture.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["issuer_topk_neighbor_table_metadata_bundle"] is True
    assert result["checks"]["missing_table_is_typed_exhaustion"] is True
    assert result["authority_boundary"]["rag_sql_graph_retrieval"] is False
