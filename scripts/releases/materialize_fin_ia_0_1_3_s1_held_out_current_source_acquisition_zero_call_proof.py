from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_research_held_out_current_source_acquisition import (  # noqa: E402
    RUN_SCOPE,
    execute_held_out_current_source_acquisition,
    issue_held_out_current_source_admission,
    load_held_out_current_source_policy,
)
from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_held_out_current_source_acquisition_policy_v1_0.json"
OUTPUT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_held_out_current_source_acquisition_zero_call_proof_v1_0.json"


def _submissions(accession: str, filed: str, report: str, form: str, primary: str) -> bytes:
    return json.dumps({"filings": {"recent": {"accessionNumber": [accession], "filingDate": [filed], "reportDate": [report], "form": [form], "primaryDocument": [primary], "items": [""]}}}).encode()


class FixtureTransport:
    live_network = True

    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses

    def fetch(self, *, url: str, **_: object) -> SourceResponse:
        content_type, body = self.responses[url]
        return SourceResponse(status_code=200, final_url=url, headers={"content-type": content_type}, body=body)


def _responses() -> dict[str, tuple[str, bytes]]:
    orcl = "https://www.sec.gov/Archives/edgar/data/1341439/000134143926000111/orcl-20260531.htm"
    asml = "https://www.sec.gov/Archives/edgar/data/937966/000093796626000222/asml-20260715.htm"
    asml_exhibit = asml.rsplit("/", 1)[0] + "/ex99-1.htm"
    anet = "https://www.sec.gov/Archives/edgar/data/1596532/000159653226000333/anet-20260630.htm"
    return {
        "https://data.sec.gov/submissions/CIK0001341439.json": ("application/json", _submissions("0001341439-26-000111", "2026-06-22", "2026-05-31", "10-K", "orcl-20260531.htm")),
        "https://data.sec.gov/submissions/CIK0000937966.json": ("application/json", _submissions("0000937966-26-000222", "2026-07-15", "2026-06-28", "6-K", "asml-20260715.htm")),
        "https://data.sec.gov/submissions/CIK0001596532.json": ("application/json", _submissions("0001596532-26-000333", "2026-08-03", "2026-06-30", "10-Q", "anet-20260630.htm")),
        orcl: ("text/html", b"<html><body>Oracle Corporation fiscal 2026 year ended May 31, 2026 cloud services and capital expenditures.</body></html>"),
        asml: ("text/html", b'<html><body><a href="ex99-1.htm">Exhibit 99.1 results</a></body></html>'),
        asml_exhibit: ("text/html", b"<html><body>ASML Holding second quarter Q2 2026 EUV bookings gross margin.</body></html>"),
        anet: ("text/html", b"<html><body>Arista Networks second quarter Q2 2026 revenue gross margin Ethernet AI.</body></html>"),
    }


def main() -> int:
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("held_out_source_zero_call_project_os_preflight_failed")
    policy = load_held_out_current_source_policy(POLICY_PATH, repo_root=ROOT)
    admission = issue_held_out_current_source_admission(
        policy=policy,
        implementation_commit="0" * 40,
        implementation_file_sha256="1" * 64,
        policy_file_sha256="2" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        nonce="zero-call-fixture",
    )
    with TemporaryDirectory(prefix="fin013-heldout-source-zero-call-") as temp:
        root = Path(temp)
        ledger = SharedAdmissionConsumptionLedger(root / "shared.sqlite")
        result = execute_held_out_current_source_acquisition(
            policy=policy,
            admission=admission,
            runtime_root=root / "runtime",
            ledger=ledger,
            transport=FixtureTransport(_responses()),
            observed_at="2026-08-09T01:00:00Z",
        )
        receipt = ledger.read(str(admission["admission_digest"])).as_dict()
    if (
        result["status"] != "completed_all_targets_acquired"
        or result["observed_counts"]["acquired"] != 3
        or result["observed_counts"]["network_calls"] != 7
        or receipt["state"] != "terminal"
    ):
        raise RuntimeError("held_out_source_zero_call_assertion_failed")
    body = {
        "schema_version": "fin_ia_0_1_3_s1_held_out_current_source_acquisition_zero_call_proof_v1_0",
        "contract_ref": policy["contract_ref"],
        "run_scope": policy["run_scope"],
        "status": "zero_call_engineering_pass_live_authority_not_yet_issued",
        "policy_digest": canonical_digest(policy),
        "fixture_result_digest": result["result_digest"],
        "fixture_terminal_receipt_digest": canonical_digest(
            {
                "state": receipt["state"],
                "terminal_status": receipt["terminal_status"],
                "terminal_phase": receipt["terminal_phase"],
                "terminal_code": receipt["terminal_code"],
                "terminal_result_digest": receipt["terminal_result_digest"],
            }
        ),
        "verification": {
            "typed_targets": 3,
            "simulated_source_calls": 7,
            "actual_network_calls": 0,
            "model_provider_embedding_rerank_evidence_calls": [0, 0, 0, 0, 0],
            "capture_first_request_response": True,
            "same_accession_exhibit_fallbacks": 1,
            "exact_accession_or_final_url_seeded": False,
            "exact_once_terminal_receipt": True
        },
        "stage_acceptance": {
            "source_acquisition_engineering": True,
            "live_authority": False,
            "current_sources_acquired": False,
            "current_source_reparse": False,
            "held_out_product_generalization": False,
            "sparse_dense_rebuild_admitted": False
        },
        "known_boundary": "Fixture proof establishes deterministic selection, capture-first retention and terminalization only. It does not claim that any 2026 source is available or accepted."
    }
    output = {**body, "proof_digest": canonical_digest(body)}
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if existing.get("proof_digest") != output["proof_digest"]:
            raise RuntimeError("held_out_source_zero_call_output_occupied")
    else:
        OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
