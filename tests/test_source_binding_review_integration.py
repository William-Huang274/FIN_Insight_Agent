import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts/engineering"))
spec = importlib.util.spec_from_file_location("finalize_lineage", Path(__file__).parents[1] / "scripts/engineering/finalize_source_binding_review.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_replacing_missing_status_keeps_existing_quality_findings():
    previous = [{"kind":"missing_verified_original","document_id":"a"},
                {"kind":"table_read_order_uncertain","original_id":"other"}]
    reviewed = [{"document_id":"a","availability":"historical_original_recovered", "gap_class":"historical_original_recovered",
                 "processing":{"stage":"parse_recovered_original"}, "next_action":"parse"}]
    result = module.integrate_issues(previous,reviewed)
    assert previous[1] in result
    assert len(result) == 2
    assert not any(r["kind"]=="missing_verified_original" for r in result)
    assert result[-1]["quality_pass"] is False


def test_mismatched_cohort_cannot_silently_drop_missing_records():
    import pytest
    with pytest.raises(ValueError,match="match"):
        module.integrate_issues([{"kind":"missing_verified_original","document_id":"a"}], [])


def test_all_evidence_states_have_real_pipeline_ownership():
    statuses = ["archived_original_existing","historical_original_recovered","readme_api_content_recovered",
        "structured_payload_preserved","derivative_parent_recovered","candidate_version_unverified",
        "recorded_archive_version_unverified","derivative_preserved_original_unlocated"]
    stages = set()
    for status in statuses:
        row = {"availability":status,"document_id":"a","source_id":"s","family":"web", "next_action":"review"}
        record = module.queue_record(row)
        assert record["source_id"] == "s" and record["state"] == "pending"
        assert record["route"]
        stages.add(record["stage"])
    assert len(stages) == 7
