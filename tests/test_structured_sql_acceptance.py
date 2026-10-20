"""CI-sized deterministic counterpart of the opt-in historical transaction test."""
import json
import shutil

from test_industry_foundation import foundation
from test_industry_metrics import pack
from sec_agent.research_foundation.industry_metrics import import_pack
from sec_agent.research_foundation.metric_workspace import query_metrics
from tests.integration.test_structured_sql_history import (
    test_historical_sql_revision_idempotency_concurrency_and_rollback as run_transaction_scenario,
)


def test_revision_and_transaction_scenario_without_private_data(foundation, tmp_path, monkeypatch):
    path, _, _ = foundation
    import_pack(path, pack())
    row = query_metrics(path, ["NVIDIA"], section="history")["items"][0]
    card = query_metrics(path, ["NVIDIA"], section="card", record_id=row["id"])["items"][0]
    inputs = tmp_path/"inputs"
    inputs.mkdir()
    shutil.copyfile(path, inputs/"build.sqlite")
    manifest = inputs/"cases.json"
    manifest.write_text(json.dumps({"cases": [{"snapshot": {"rows": [card]}}]}), encoding="utf8")
    monkeypatch.setenv("FIN_STRUCTURED_SQL_CASES", str(manifest))
    monkeypatch.setenv("FIN_STRUCTURED_SQL_RESULT", str(tmp_path/"ci-result.json"))
    run_transaction_scenario(tmp_path)
    assert json.loads((tmp_path/"ci-result.json").read_text())["old_card_unchanged"]
