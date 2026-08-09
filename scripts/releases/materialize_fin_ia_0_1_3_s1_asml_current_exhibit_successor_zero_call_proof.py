from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.financial_research_asml_exhibit_successor import (  # noqa: E402
    execute_asml_exhibit_successor,
    issue_asml_exhibit_admission,
    load_asml_exhibit_successor_policy,
)
from sec_agent.financial_research_held_out_current_source_acquisition import RUN_SCOPE  # noqa: E402
from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_asml_current_exhibit_successor_policy_v1_0.json"
OUTPUT_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_asml_current_exhibit_successor_zero_call_proof_v1_0.json"


class FixtureTransport:
    live_network = True

    def __init__(self, responses: dict[str, tuple[str, bytes]]) -> None:
        self.responses = responses

    def fetch(self, *, url: str, **_: object) -> SourceResponse:
        content_type, body = self.responses[url]
        return SourceResponse(status_code=200, final_url=url, headers={"content-type": content_type}, body=body)


def main() -> int:
    project_os = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if project_os.get("status") != "pass":
        raise RuntimeError("asml_exhibit_zero_call_project_os_preflight_failed")
    policy = load_asml_exhibit_successor_policy(POLICY_PATH, repo_root=ROOT)
    from sec_agent.financial_research_asml_exhibit_successor import derive_asml_accession_index

    lineage = derive_asml_accession_index(policy=policy, repo_root=ROOT)
    first = lineage["accession_base_url"] + "exhibit991pressrelease.htm"
    second = lineage["accession_base_url"] + "exhibit992financialresults.htm"
    index_body = json.dumps(
        {
            "directory": {
                "item": [
                    {"name": lineage["primary_document"], "size": 12000, "type": "text/html"},
                    {"name": "asml-20260628_lab.xml", "size": 500, "type": "text/xml"},
                    {"name": "exhibit991pressrelease.htm", "size": 10000, "type": "text/html"},
                    {"name": "exhibit992financialresults.htm", "size": 20000, "type": "text/html"},
                ]
            }
        }
    ).encode()
    responses = {
        lineage["index_url"]: ("application/json", index_body),
        first: ("text/html", b"<html><body>ASML Q2 2026 gross margin outlook.</body></html>"),
        second: (
            "text/html",
            b"<html><body>ASML Q2 2026 net bookings EUV High-NA systems sold installed base gross margin cash flows outlook.</body></html>",
        ),
    }
    admission = issue_asml_exhibit_admission(
        policy=policy,
        implementation_commit="0" * 40,
        implementation_file_sha256="1" * 64,
        policy_file_sha256="2" * 64,
        issued_at="2026-08-09T00:00:00Z",
        expires_at="2026-08-10T00:00:00Z",
        nonce="zero-call-fixture",
    )
    with TemporaryDirectory(prefix="fin013-asml-exhibit-zero-call-") as temp:
        temp_root = Path(temp)
        ledger = SharedAdmissionConsumptionLedger(temp_root / "shared.sqlite")
        result = execute_asml_exhibit_successor(
            policy=policy,
            admission=admission,
            repo_root=ROOT,
            runtime_root=temp_root / "runtime",
            ledger=ledger,
            transport=FixtureTransport(responses),
            observed_at="2026-08-09T01:00:00Z",
        )
        receipt = ledger.read(str(admission["admission_digest"])).as_dict()
    if (
        result["status"] != "completed_detailed_exhibit_acquired"
        or result["observed_counts"]["network_calls"] != 3
        or receipt["state"] != "terminal"
        or result["selected_detailed_source"]["candidate"]["name"] != "exhibit992financialresults.htm"
    ):
        raise RuntimeError("asml_exhibit_zero_call_assertion_failed")
    semantic_receipt = {
        key: receipt[key]
        for key in ("state", "terminal_status", "terminal_phase", "terminal_code", "terminal_result_digest")
    }
    body = {
        "schema_version": "fin_ia_0_1_3_s1_asml_current_exhibit_successor_zero_call_proof_v1_0",
        "contract_ref": policy["contract_ref"],
        "run_scope": RUN_SCOPE,
        "status": "zero_call_engineering_pass_live_authority_not_yet_issued",
        "policy_digest": canonical_digest(policy),
        "fixture_result_digest": result["result_digest"],
        "fixture_terminal_receipt_digest": canonical_digest(semantic_receipt),
        "verification": {
            "index_from_bound_accession": True,
            "primary_and_xbrl_excluded": True,
            "candidate_document_ceiling": 2,
            "simulated_calls": 3,
            "actual_network_calls": 0,
            "headline_only_first_candidate_rejected": True,
            "detailed_second_candidate_accepted": True,
            "capture_first": True,
            "exact_once_terminal": True,
            "retry_model_provider_embedding_rerank_evidence_calls": [0, 0, 0, 0, 0, 0],
        },
        "stage_acceptance": {
            "asml_exhibit_successor_engineering": True,
            "live_authority": False,
            "asml_detailed_current_source_capture": False,
            "three_case_reparse": False,
            "sparse_dense_rebuild_admitted": False,
        },
        "known_boundary": "Fixture proof does not establish that the live accession index contains a qualifying detailed exhibit.",
    }
    output = {**body, "proof_digest": canonical_digest(body)}
    if OUTPUT_PATH.exists():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        if existing.get("proof_digest") != output["proof_digest"]:
            raise RuntimeError("asml_exhibit_zero_call_output_occupied")
    else:
        OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
