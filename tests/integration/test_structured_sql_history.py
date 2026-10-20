"""Opt-in historical SQL import/revision/rollback acceptance; no model calls."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading

import pytest

from sec_agent.research_foundation.industry_metrics import import_pack
from sec_agent.research_foundation.metric_workspace import query_metrics

pytestmark = pytest.mark.skipif(not os.getenv("FIN_STRUCTURED_SQL_CASES"), reason="explicit historical SQL manifest required")


def revision_pack(card, *, suffix="one"):
    """Clearly synthetic correction derived from a historical row, never an issuer restatement."""
    row = deepcopy(card)
    for key in ("id", "source_id", "sources", "company_name", "definition", "financial_basis",
                "record_type", "status", "group", "observation_kind", "period_label", "available_at",
                "published_at", "available_at_basis", "formula_version", "comparison_status",
                "comparison_note", "review_ids", "comparison_rules", "unit_correction"):
        row.pop(key, None)
    row.update(source_ref="engineering", evidence_quote="ENGINEERING ONLY: corrected value 17.",
               evidence_locator="Synthetic fault acceptance "+suffix, value="17", value_in_source="17",
               scale="1", comparator="eq", qualifiers=["ENGINEERING ONLY; not an issuer correction"])
    row.pop("source_number_basis", None)
    row.pop("sign", None)
    return {"as_of": "2026-10-20", "companies": [card["entity_id"]],
            "sources": [{"ref": "engineering", "url": "https://qualification.invalid/"+suffix,
                         "title": "ENGINEERING ONLY correction", "published_at": "2026-10-20",
                         "body": row["evidence_quote"]}],
            "definitions": [card["definition"]], "observations": [row],
            "coverage": [{"entity_id": card["entity_id"], "gaps": [],
                          "reviewed_sources": ["engineering"]}]}


def test_historical_sql_revision_idempotency_concurrency_and_rollback(tmp_path):
    manifest = Path(os.environ["FIN_STRUCTURED_SQL_CASES"])
    spec = json.loads(manifest.read_text(encoding="utf8"))
    path = tmp_path/"engineering-build.sqlite"
    shutil.copyfile(manifest.parent/"build.sqlite", path)
    original = spec["cases"][0]["snapshot"]["rows"][0]
    old = query_metrics(path, [original["entity_id"]], section="card", record_id=original["id"])
    pack = revision_pack(original)
    barrier = threading.Barrier(2)
    def write():
        barrier.wait(timeout=10)
        return import_pack(path, pack)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write) for _ in range(2)]
        for f in futures:
            f.result(timeout=20)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT count(*) FROM industry_metric_observations WHERE available_at='2026-10-20'").fetchone()[0] == 1
        new_id = db.execute("SELECT id FROM industry_metric_observations WHERE available_at='2026-10-20'").fetchone()[0]
    assert query_metrics(path, [original["entity_id"]], section="card", record_id=original["id"]) == old
    revised = query_metrics(path, [original["entity_id"]], section="card", record_id=new_id)["items"][0]
    assert revised["value"] == "17" and revised["unit"] == original["unit"]
    assert revised["financial_basis"] == original["financial_basis"]
    with pytest.raises(ValueError, match="cutoff"):
        query_metrics(path, [original["entity_id"]], section="card", record_id=new_id, as_of="2026-10-19")
    # Fail AFTER observations and sources have been written, in the same transaction.
    broken = revision_pack(original, suffix="rollback")
    with closing(sqlite3.connect(path)) as db, db:
        counts = {t: db.execute("SELECT count(*) FROM "+t).fetchone()[0]
                  for t in ("sources", "passages", "industry_metric_observations", "industry_metric_definitions")}
        db.execute("""CREATE TRIGGER reject_coverage BEFORE INSERT ON industry_metric_coverage
                      BEGIN SELECT RAISE(ABORT,'engineering_injected_failure'); END""")
    with pytest.raises(sqlite3.IntegrityError, match="engineering_injected_failure"):
        import_pack(path, broken)
    with closing(sqlite3.connect(path)) as db, db:
        assert {t: db.execute("SELECT count(*) FROM "+t).fetchone()[0] for t in counts} == counts
        db.execute("DROP TRIGGER reject_coverage")
    import_pack(path, broken)
    import_pack(path, broken)
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT count(*) FROM industry_metric_observations WHERE available_at='2026-10-20'").fetchone()[0] == 2
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    evidence = {"status": "passed", "historical_record_id": original["id"], "engineered_revision_id": new_id,
                "concurrent_identical_imports": 2, "new_rows_after_concurrent_import": 1,
                "rollback_tables": counts, "retry_after_explicit_failure_removal": True,
                "old_card_unchanged": True, "provider_calls": 0,
                "revision_policy": "append separate provenance; no inferred supersession"}
    target = Path(os.environ.get("FIN_STRUCTURED_SQL_RESULT", str(tmp_path/"result.json")))
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf8")
