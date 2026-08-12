from pathlib import Path

from sec_agent.runtime_bridge.paths import resolve_runtime_paths


def test_reviewed_evidence_and_mutable_workbench_state_can_be_separate(
    tmp_path: Path, monkeypatch
) -> None:
    data_root = tmp_path / "data"
    reviewed_root = tmp_path / "reviewed-evidence"
    state_root = tmp_path / "state" / "workbench-private"
    monkeypatch.setenv("FINSIGHT_DATA_ROOT", str(data_root))
    monkeypatch.setenv("FINSIGHT_REVIEWED_EVIDENCE_ROOT", str(reviewed_root))
    monkeypatch.setenv("FINSIGHT_WORKBENCH_PRIVATE_ROOT", str(state_root))

    paths = resolve_runtime_paths(tmp_path / "repo")

    assert paths.primary_data_root == data_root.resolve()
    assert paths.reviewed_evidence_root == reviewed_root.resolve()
    assert paths.workbench_private_root == state_root.resolve()
    assert paths.company_financial_fact_mart_path == (
        state_root
        / "fin_0_1_3_s2_company_financial_fact_mart"
        / "v1"
        / "company_financial_facts.sqlite"
    ).resolve()
    assert len({
        paths.primary_data_root,
        paths.reviewed_evidence_root,
        paths.workbench_private_root,
    }) == 3
