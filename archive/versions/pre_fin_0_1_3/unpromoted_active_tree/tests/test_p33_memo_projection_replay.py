from __future__ import annotations

from pathlib import Path

from sec_agent.p33_memo_projection_replay import (
    DEFAULT_MEMO_WRITER_NODE_RESULT,
    build_multicase_goldset_readiness,
    build_single_case_projection_replay,
    write_projection_replay_artifacts,
)


def test_single_case_projection_replay_passes_from_scoped_memo_writer_artifact() -> None:
    assert DEFAULT_MEMO_WRITER_NODE_RESULT.exists()

    replay = build_single_case_projection_replay(DEFAULT_MEMO_WRITER_NODE_RESULT)

    assert replay["status"] == "pass"
    assert replay["checks"] == {
        "renderer_projection_pass": True,
        "final_verifier_projection_pass": True,
        "workbench_projection_pass": True,
        "no_paid_llm_called": True,
    }
    renderer = replay["renderer_projection"]
    verifier = replay["final_verifier_projection"]
    workbench = replay["workbench_projection"]
    assert renderer["status"] == "pass"
    assert renderer["rendered_answer_chars"] >= 3500
    assert not renderer["internal_marker_hits"]
    assert renderer["citation_label_count"] >= 6
    rendered = renderer["rendered_answer"]
    assert "本轮材料没有匹配到可提权" not in rendered
    assert "产品层可以形成有边界的判断" in rendered
    assert "DELL 的 AI server 需求可见度较强" in rendered
    assert "NVIDIA remains the main external accelerator system bottleneck" not in rendered
    assert "Dell has unusually visible AI server revenue demand" not in rendered
    assert verifier["status"] == "pass"
    assert verifier["deterministic_status"] == "pass"
    assert verifier["input_pack_fingerprint"]["known_evidence_ref_count"] >= 10
    assert workbench["status"] == "pass"
    assert workbench["counts"]["section_count"] >= 6
    assert workbench["counts"]["claim_count"] >= 6
    assert workbench["counts"]["evidence_linked_claim_count"] >= 6
    assert "paid_llm" in replay["not_run"]
    assert "full_chain" in replay["not_run"]


def test_multicase_goldset_readiness_keeps_hard_blockers_visible() -> None:
    replay = build_single_case_projection_replay(DEFAULT_MEMO_WRITER_NODE_RESULT)

    readiness = build_multicase_goldset_readiness(single_case_projection=replay)

    assert readiness["status"] == "blocked_until_multicase_artifact_depth_and_fresh_specialists_pass"
    assert readiness["case_count"] == 15
    assert readiness["artifact_ready_count"] == 1
    assert readiness["fresh_specialist_pass_count"] == 0
    assert readiness["runtime_contract_ready_count"] == 15
    assert readiness["blocking_case_count"] == 15

    rows = {row["case_id"]: row for row in readiness["case_results"]}
    ai_semis = rows["ai_semis_dell_nvda_anchor_v0_1"]
    assert ai_semis["artifact_backed_evidence_depth"]["status"] == "pass"
    assert (
        ai_semis["fresh_all_specialist_gold_pass"]["status"]
        == "blocked_targeted_composite_not_fresh_all_specialist"
    )
    assert (
        "fresh_all_specialist_gold_pass:blocked_targeted_composite_not_fresh_all_specialist"
        in ai_semis["blocking_reasons"]
    )

    missing_depth = [
        row
        for row in readiness["case_results"]
        if row["artifact_backed_evidence_depth"]["status"] != "pass"
    ]
    assert len(missing_depth) == 14
    assert "paid_all_specialist_rerun" in readiness["not_run"]
    assert "paid_memo_writer" in readiness["not_run"]


def test_projection_replay_writer_outputs_artifacts(tmp_path: Path) -> None:
    projection_json = tmp_path / "projection.json"
    projection_md = tmp_path / "projection.md"
    multi_json = tmp_path / "multi.json"
    multi_md = tmp_path / "multi.md"

    result = write_projection_replay_artifacts(
        memo_writer_node_result=DEFAULT_MEMO_WRITER_NODE_RESULT,
        projection_json=projection_json,
        projection_md=projection_md,
        multi_case_json=multi_json,
        multi_case_md=multi_md,
    )

    assert result["single_case_projection"]["status"] == "pass"
    assert result["multi_case_readiness"]["status"].startswith("blocked_")
    for path in (projection_json, projection_md, multi_json, multi_md):
        assert path.exists()
        assert path.read_text(encoding="utf-8").strip()
