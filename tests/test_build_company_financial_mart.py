"""A user's new dataset can be built without historical case acceptance records."""
import json
from pathlib import Path
import subprocess
import sys

from financial_facts import SecSnapshotCompany
from test_sec_companyfacts_snapshot import (
    FakeResponse, FakeSession, _capture, _manifest, _raw, _submissions,
)


def test_generic_builder_accepts_an_independent_captured_company(tmp_path):
    root = Path(__file__).resolve().parents[1]
    cik, name = 1234567, "Synthetic Example Company"
    company = SecSnapshotCompany(ticker="TEST", cik=f"{cik:010d}", legal_name=name)
    manifest = _manifest().model_copy(update={"companies": (company,)})
    facts = {"cik": cik, "entityName": name, "facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [{"start": "2025-01-01", "end": "2025-12-31",
            "val": 1200, "accn": "0001234567-26-000001", "fy": 2025, "fp": "FY",
            "form": "10-K", "filed": "2026-02-01"}]}}}}}
    submissions = _submissions(cik=cik, name=name)
    submissions["filings"]["recent"].update(
        accessionNumber=["0001234567-26-000001"], filingDate=["2026-02-01"],
        acceptanceDateTime=["2026-02-01T12:00:00Z"], reportDate=["2025-12-31"],
        form=["10-K"], primaryDocument=["annual.htm"],
    )
    source = tmp_path / "capture"
    _capture(source, FakeSession([
        FakeResponse(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", _raw(facts)),
        FakeResponse(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", _raw(submissions)),
    ]), manifest=manifest)
    prepared = tmp_path / "prepared"
    for args in (
        ["scripts.data_retrieval.materialize_companyfacts_snapshot", "--snapshot",
         str(source / "snapshot-manifest.json"), "--output", str(prepared), "--as-of", "2026-09-02"],
        ["scripts.data_retrieval.build_company_financial_mart", "--policy", str(prepared / "policy.json"),
         "--sqlite", str(tmp_path / "rebuilt.sqlite"), "--output", str(tmp_path / "result.json")],
    ):
        run = subprocess.run([sys.executable, "-m", *args], cwd=root, capture_output=True, text=True)
        assert run.returncode == 0, run.stderr
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert result["counts"]["by_ticker"] == {"TEST": 1}
    assert result["status"] == "company_financial_fact_mart_materialized_acceptance_pending"
    assert result["acceptance"]["checks_status"] == "not_requested"
    assert result["acceptance"]["all_qrels_exact"] is None
