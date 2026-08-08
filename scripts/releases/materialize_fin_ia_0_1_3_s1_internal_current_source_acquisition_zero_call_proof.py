from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_current_source_acquisition import (  # noqa: E402
    execute_internal_source_acquisition,
    issue_internal_source_acquisition_admission,
    load_internal_source_acquisition_policy,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "current_source_acquisition_policy_v1_0.json"
)
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "current_source_acquisition_zero_call_proof_v1_0.json"
)


def _submissions(
    *, accession: str, filed: str, report: str, form: str, primary: str, items: str
) -> bytes:
    return json.dumps(
        {
            "filings": {
                "recent": {
                    "accessionNumber": [accession],
                    "filingDate": [filed],
                    "reportDate": [report],
                    "form": [form],
                    "primaryDocument": [primary],
                    "items": [items],
                }
            }
        }
    ).encode()


class FixtureTransport:
    live_network = True

    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses

    def fetch(self, *, url: str, **_: object) -> SourceResponse:
        content_type, body = self.responses[url]
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": content_type},
            body=body,
        )


def _fixture_responses() -> dict[str, tuple[str, bytes]]:
    dell = (
        "https://www.sec.gov/Archives/edgar/data/1571996/"
        "000157199626000008/dell-20260130.htm"
    )
    mu = (
        "https://www.sec.gov/Archives/edgar/data/723125/"
        "000072312526000020/mu-20260624.htm"
    )
    mu_exhibit = mu.rsplit("/", 1)[0] + "/ex99-1.htm"
    tsm = (
        "https://www.sec.gov/Archives/edgar/data/1046179/"
        "000104617926000030/tsm-20260716.htm"
    )
    tsm_exhibit = tsm.rsplit("/", 1)[0] + "/ex99-1.htm"
    return {
        "https://data.sec.gov/submissions/CIK0001571996.json": (
            "application/json",
            _submissions(
                accession="0001571996-26-000008",
                filed="2026-03-16",
                report="2026-01-30",
                form="10-K",
                primary="dell-20260130.htm",
                items="",
            ),
        ),
        "https://data.sec.gov/submissions/CIK0000723125.json": (
            "application/json",
            _submissions(
                accession="0000723125-26-000020",
                filed="2026-06-24",
                report="2026-05-28",
                form="8-K",
                primary="mu-20260624.htm",
                items="2.02,9.01",
            ),
        ),
        "https://data.sec.gov/submissions/CIK0001046179.json": (
            "application/json",
            _submissions(
                accession="0001046179-26-000030",
                filed="2026-07-16",
                report="2026-06-30",
                form="6-K",
                primary="tsm-20260716.htm",
                items="",
            ),
        ),
        dell: (
            "text/html",
            b"<html><body>Dell Technologies fiscal 2026 Infrastructure Solutions Group and AI-optimized servers risk factors.</body></html>",
        ),
        mu: (
            "text/html",
            b'<html><body><a href="ex99-1.htm">Exhibit 99.1 earnings results</a></body></html>',
        ),
        mu_exhibit: (
            "text/html",
            b"<html><body>Micron Technology third quarter fiscal 2026 HBM revenue and gross margin.</body></html>",
        ),
        tsm: (
            "text/html",
            b'<html><body><a href="ex99-1.htm">Exhibit 99.1 financial results</a></body></html>',
        ),
        tsm_exhibit: (
            "text/html",
            b"<html><body>Taiwan Semiconductor TSMC second quarter Q2 2026 revenue and gross margin capacity.</body></html>",
        ),
    }


def main() -> int:
    preflight = run_project_os_preflight(
        ROOT, run_scope="S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH"
    )
    if preflight.get("status") != "pass":
        raise RuntimeError("internal_source_acquisition_zero_call_preflight_blocked")
    policy = load_internal_source_acquisition_policy(POLICY_PATH, repo_root=ROOT)
    admission = issue_internal_source_acquisition_admission(
        policy=policy,
        implementation_commit="0" * 40,
        implementation_file_sha256="1" * 64,
        policy_file_sha256="2" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        nonce="zero-call-fixture",
    )
    with TemporaryDirectory(prefix="fin013-s1-source-zero-call-") as temp:
        temp_root = Path(temp)
        ledger = SharedAdmissionConsumptionLedger(temp_root / "shared.sqlite")
        result = execute_internal_source_acquisition(
            policy=policy,
            admission=admission,
            runtime_root=temp_root / "runtime",
            ledger=ledger,
            transport=FixtureTransport(_fixture_responses()),
            observed_at="2026-08-09T01:00:00Z",
        )
        receipt = ledger.read(admission["admission_digest"]).as_dict()
    if (
        result["status"] != "completed_all_targets_acquired"
        or result["observed_counts"]["acquired"] != 3
        or result["observed_counts"]["network_calls"] != 8
        or receipt["state"] != "terminal"
        or any(
            row["benchmark_exact_url_used_for_discovery"] is not False
            for row in result["source_results"]
        )
    ):
        raise RuntimeError("internal_source_acquisition_zero_call_assertion_failed")
    body = {
        "schema_version": "fin_ia_0_1_3_s1_internal_current_source_acquisition_zero_call_proof_v1_0",
        "contract_ref": "fin_0_1_3.S1.internal_current_official_source_acquisition:v1",
        "run_scope": "S1_INTERNAL_CURRENT_CORPUS_AND_INDEX_REFRESH",
        "status": "zero_call_engineering_pass_live_authority_not_yet_issued",
        "policy_digest": canonical_digest(policy),
        "fixture_result_digest": result["result_digest"],
        "fixture_terminal_receipt_digest": receipt["receipt_digest"],
        "verification": {
            "typed_targets": 3,
            "simulated_source_calls": 8,
            "actual_network_calls": 0,
            "retry_model_provider_embedding_rerank_evidence_calls": [0, 0, 0, 0, 0, 0],
            "capture_first_request_response": True,
            "same_accession_exhibit_fallbacks": 2,
            "exact_once_terminal_receipt": True,
            "benchmark_exact_url_used_for_discovery": False,
            "candidate_state": "captured_source_not_evidence",
        },
        "stage_acceptance": {
            "source_acquisition_engineering": True,
            "live_authority": False,
            "current_sources_acquired": False,
            "candidate_ceiling": False,
            "BGE_fusion_rerank": False,
            "external_product_coverage": False,
            "release": False,
        },
    }
    output = {**body, "proof_digest": canonical_digest(body)}
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if existing.get("proof_digest") != output["proof_digest"]:
            raise RuntimeError("internal_source_acquisition_proof_path_occupied")
        output = existing
    else:
        OUTPUT_PATH.write_text(
            json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
