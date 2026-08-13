from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
)
from apps.workbench.backend.application.research_retrieval_service import (
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
)
from sec_agent.research.current_consumer import (
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    compile_current_research_input,
    compile_current_research_messages,
    parse_current_research_output,
    validate_current_research_output,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths
from sec_agent.runtime_resource_registry import read_registered_runtime_json


POLICY = ROOT / (
    "configs/research/"
    "fin_ia_0_1_3_s3_current_research_consumer_policy_v1_0.json"
)
OBJECTIVE = ROOT / (
    "configs/research/evals/"
    "fin_ia_0_1_3_s3_dell_minimal_planner_canary_objective_v1_0.json"
)
ATOMS = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_planner_r1_atoms_v1_0.json"
)
FAKE_OUTPUT = ROOT / (
    "tests/fixtures/research/"
    "fin_ia_0_1_3_s3_dell_current_research_consumer_fake_output_v1_0.json"
)
READ = frozenset({"current_product:read"})


def _zero_call_runner():
    path = ROOT / "scripts/research/run_s3_current_research_consumer_zero_call.py"
    spec = importlib.util.spec_from_file_location(
        "s3_current_research_consumer_zero_call_runner",
        path,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    paths = resolve_runtime_paths(ROOT)
    evidence_config = read_registered_runtime_json(
        ROOT, "application.config.current_research_evidence_pack_projection"
    )
    evidence_service = ResearchEvidencePackService(
        config=evidence_config,
        result=read_registered_runtime_json(
            ROOT, str(evidence_config["source_result_resource_id"])
        ),
        private_object_root=(
            paths.reviewed_evidence_root
            / str(evidence_config["private_object_root_relative"])
        ),
        private_root_base=paths.reviewed_evidence_root,
    )
    evidence_pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", READ)
    )
    retrieval = ResearchRetrievalService(
        snapshot=read_registered_runtime_json(
            ROOT, "application.result.current_research_retrieval_snapshot"
        ),
        ranking_comparison=read_registered_runtime_json(
            ROOT, "application.result.current_s1c_ranking_comparison_projection"
        ),
        kernel=read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        ),
        route_policy=read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        planning_policy=read_registered_runtime_json(
            ROOT, "application.config.current_research_planning_policy"
        ),
        hybrid_candidate_runtime=None,
        company_financial_fact_mart_path=(
            paths.company_financial_fact_mart_path
        ),
    )
    controlled = retrieval.execute_controlled_plan(
        "DELL",
        _json(OBJECTIVE),
        _json(ATOMS),
        ResearchRetrievalPrincipal("current", READ),
    )
    research_input = compile_current_research_input(
        policy=_json(POLICY),
        evidence_pack=evidence_pack,
        controlled_plan=controlled,
    )
    return evidence_pack, controlled, research_input


@pytest.fixture(scope="module")
def current_inputs() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return _current_inputs()


def test_current_input_consumes_reviewed_pack_and_deduplicated_numeric_facts(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    evidence_pack, controlled, research_input = current_inputs

    assert controlled["summary"]["numeric_fact_count"] == 45
    summary = research_input["input_selection_summary"]
    assert summary["semantic_unique_fact_count_before_period_selection"] == 35
    assert summary["model_visible_numeric_fact_count"] == 25
    assert summary["model_visible_evidence_count"] == 19
    assert summary["model_visible_gap_count"] == 10
    assert len(evidence_pack["evidence_items"]) == 20
    assert [row["cell_id"] for row in research_input["cells"]] == [
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    ]
    transcripts = [
        row
        for row in research_input["evidence_cards"]
        if row["source_type"] == "EARNINGS_CALL_TRANSCRIPT"
    ]
    assert len(transcripts) == 5
    assert all(
        row["source_tier"] == "official_hosted_management_call_transcript"
        for row in transcripts
    )
    assert "EARNINGS_CALL_TRANSCRIPT" not in research_input["objective"][
        "allowed_source_types"
    ]
    assert research_input["authority"]["source_policy_domains_remain_separate"]
    assert "candidates" not in research_input
    assert "rejected_items" not in research_input
    assert all("candidates" not in row for row in research_input["cells"])


def test_model_sees_exact_facts_but_does_not_own_fact_rendering(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    messages = compile_current_research_messages(research_input)
    visible = json.loads(messages[1]["content"])
    serialized = messages[1]["content"]

    assert visible["case_identity"]["subject_ticker"] == "DELL"
    assert "43842000000" in serialized
    assert "24.4 billion" in serialized
    assert "51.3 billion" in serialized
    assert "source_visible_fact_excerpt" in serialized
    assert "Do not repeat or alter identities" in serialized
    assert len(messages[1]["content"]) <= 50000
    for internal_field in (
        "target_id",
        "source_record_id",
        "source_text_digest",
        "source_numeric_fact_ids",
        "source_fact_request_ids",
        "source_observation_ids",
        "source_digests",
        "citation_urls",
    ):
        assert internal_field not in visible
        assert f'"{internal_field}"' not in serialized


def test_fake_judgments_compile_a_reference_safe_workpaper(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
) -> None:
    _, _, research_input = current_inputs
    fake = _json(FAKE_OUTPUT)
    validated = validate_current_research_output(
        fake, research_input=research_input
    )
    deliverable = compile_current_research_deliverable(
        research_input=research_input,
        judgment_output=fake,
    )

    assert len(validated["cells"]) == 5
    assert deliverable["status"] == (
        "structured_workpaper_and_report_preview_compiled"
    )
    assert deliverable["rendering_authority"][
        "harness_generated_research_conclusion"
    ] is False
    demand = deliverable["cells"][0]
    assert demand["thesis_atom"] == fake["cells"][0]["thesis_atom"]
    operating = deliverable["cells"][1]
    assert any(
        row["metric_id"] == "revenue"
        and row["value_decimal"] == "43842000000"
        and row["unit"] == "USD"
        for row in operating["numeric_facts"]
    )
    assert any(
        row["source_type"] == "EARNINGS_CALL_TRANSCRIPT"
        for cell in deliverable["cells"]
        for row in cell["supporting_evidence"]
    )


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda value: value["cells"][0]["supporting_evidence_refs"].append(
                "EV::DOESNOTEXIST"
            ),
            "research_consumer_output_ref_boundary_invalid",
        ),
        (
            lambda value: value["cells"][0].__setitem__(
                "thesis_atom", "戴尔订单增长达到两位数，因此需求已经完全确认。"
            ),
            "research_consumer_thesis_atom_invalid",
        ),
        (
            lambda value: value["cells"].pop(),
            "research_consumer_output_cell_coverage_invalid",
        ),
        (
            lambda value: value["cells"][0]["numeric_refs"].append(
                "NUM::ADC81E7A547FAB94"
            ),
            "research_consumer_output_ref_boundary_invalid",
        ),
        (
            lambda value: value["cells"][1]["what_would_change"].__setitem__(
                "threshold_numeric_ref", "NUM::UNKNOWN"
            ),
            "research_consumer_wwc_threshold_ref_invalid",
        ),
    ],
)
def test_output_mutations_fail_before_materialization(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    mutator,
    code: str,
) -> None:
    _, _, research_input = current_inputs
    value = deepcopy(_json(FAKE_OUTPUT))
    mutator(value)

    with pytest.raises(CurrentResearchConsumerError, match=code):
        compile_current_research_deliverable(
            research_input=research_input,
            judgment_output=value,
        )


@pytest.mark.parametrize(
    ("mutator", "code"),
    [
        (
            lambda pack, _: pack["evidence_items"][0].__setitem__(
                "case_key", "MU"
            ),
            "research_consumer_evidence_boundary_invalid",
        ),
        (
            lambda pack, _: pack["evidence_items"][-1]["source"].__setitem__(
                "source_tier", "unknown_transcript_tier"
            ),
            "research_consumer_reviewed_source_not_allowed",
        ),
        (
            lambda pack, _: pack["evidence_items"][0].__setitem__(
                "publication_date", "2027-01-01"
            ),
            "research_consumer_evidence_temporal_boundary_invalid",
        ),
        (
            lambda pack, _: pack["rejected_items"].append(
                {"writer_citable": True}
            ),
            "research_consumer_rejected_item_boundary_invalid",
        ),
        (
            lambda _, controlled: controlled["request_results"][2][
                "typed_fact_results"
            ][0]["facts"][0].__setitem__("numeric_fact_authority", False),
            "research_consumer_numeric_fact_boundary_invalid",
        ),
    ],
)
def test_input_mutations_fail_closed(
    current_inputs: tuple[dict[str, object], dict[str, object], dict[str, object]],
    mutator,
    code: str,
) -> None:
    evidence_pack, controlled, _ = current_inputs
    changed_pack = deepcopy(evidence_pack)
    changed_controlled = deepcopy(controlled)
    mutator(changed_pack, changed_controlled)

    with pytest.raises(CurrentResearchConsumerError, match=code):
        compile_current_research_input(
            policy=_json(POLICY),
            evidence_pack=changed_pack,
            controlled_plan=changed_controlled,
        )


def test_parser_requires_exact_json() -> None:
    fake = _json(FAKE_OUTPUT)
    assert parse_current_research_output(json.dumps(fake))["cells"]
    with pytest.raises(CurrentResearchConsumerError, match="not_exact_json"):
        parse_current_research_output("```json\n{}\n```")
    with pytest.raises(CurrentResearchConsumerError, match="json_invalid"):
        parse_current_research_output("not-json")


def test_clean_reproof_authority_binds_head_upstream_and_only_itself_untracked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _zero_call_runner()
    commit = "a" * 40
    authority_path = ROOT / (
        "configs/research/evals/"
        "fin_ia_0_1_3_s3_dell_current_research_consumer_"
        "zero_call_authority_v1_1.json"
    )
    binding = {
        "implementation_commit": commit,
        "head_must_equal_implementation_commit": True,
        "upstream_must_equal_implementation_commit": True,
        "tracked_worktree_must_be_clean": True,
        "only_authority_may_be_untracked": True,
    }

    def clean_git(*args: str) -> str:
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return f"?? {authority_path.relative_to(ROOT).as_posix()}"
        return commit

    monkeypatch.setattr(runner, "_git", clean_git)
    runner._validate_clean_implementation(
        {"clean_implementation": binding},
        authority_path=authority_path,
    )

    monkeypatch.setattr(
        runner,
        "_git",
        lambda *args: (
            f"?? {authority_path.relative_to(ROOT).as_posix()}\n"
            " M src/sec_agent/research/current_consumer.py"
            if args == ("status", "--porcelain=v1", "--untracked-files=all")
            else commit
        ),
    )
    with pytest.raises(
        runner.CurrentResearchConsumerRunnerError,
        match="current_consumer_implementation_worktree_not_clean",
    ):
        runner._validate_clean_implementation(
            {"clean_implementation": binding},
            authority_path=authority_path,
        )
