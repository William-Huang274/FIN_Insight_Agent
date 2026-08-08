from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_internal_mu_10q_acquisition import (  # noqa: E402
    RUN_SCOPE,
    execute_internal_mu_10q_acquisition_guarded,
    issue_internal_mu_10q_acquisition_admission,
    load_internal_mu_10q_acquisition_policy,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "mu_10q_acquisition_policy_v1_0.json"
)
MODULE_PATH = ROOT / "src/sec_agent/s1_internal_mu_10q_acquisition.py"
OUTPUT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_internal_"
    "mu_10q_acquisition_zero_call_proof_v1_1.json"
)


def _normalized(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


class FakeTransport:
    live_network = False

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "text/html"},
            body=(
                b"<html><body>Micron Technology quarterly report Form 10-Q "
                b"for the quarter ended May 28, 2026. Risk Factors. "
                b"Consolidated Statements of Cash Flows and cash and cash "
                b"equivalents.</body></html>"
            ),
        )


def main() -> int:
    if OUTPUT_PATH.exists():
        raise RuntimeError("internal_mu_10q_zero_call_proof_already_exists")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise RuntimeError("internal_mu_10q_zero_call_project_os_blocked")
    policy = load_internal_mu_10q_acquisition_policy(POLICY_PATH, repo_root=ROOT)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    admission = issue_internal_mu_10q_acquisition_admission(
        policy=policy,
        implementation_commit="f" * 40,
        implementation_file_sha256=_normalized(MODULE_PATH),
        policy_file_sha256=_normalized(POLICY_PATH),
        issued_at=now.isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        nonce="zero-call-fixture",
    )
    with TemporaryDirectory(prefix="fin013_mu10q_proof_") as temp:
        temp_root = Path(temp)
        ledger = SharedAdmissionConsumptionLedger(temp_root / "ledger.sqlite3")
        result = execute_internal_mu_10q_acquisition_guarded(
            policy=policy,
            admission=admission,
            runtime_root=temp_root / "runtime",
            ledger=ledger,
            transport=FakeTransport(),
            observed_at=admission["issued_at"],
        )
        receipt = ledger.read(admission["admission_digest"]).as_dict()
    valid = (
        result.get("status") == "completed_target_acquired"
        and result.get("observed_counts", {}).get("network_calls") == 0
        and result.get("source_result", {}).get("source", {}).get("form_type")
        == "10-Q"
        and receipt.get("state") == "terminal"
        and result.get("stage_boundary", {}).get(
            "mu_10q_source_acquisition_proven"
        )
        is True
        and result.get("stage_boundary", {}).get("BGE_fusion_rerank_admitted")
        is False
    )
    body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_internal_mu_10q_"
            "acquisition_zero_call_proof_v1_1"
        ),
        "contract_ref": str(policy["contract_ref"]),
        "run_scope": RUN_SCOPE,
        "status": (
            "zero_call_engineering_pass_live_authority_not_yet_issued"
            if valid
            else "zero_call_engineering_failed"
        ),
        "policy_digest": canonical_digest(policy),
        "fixture_terminal_result_digest": str(result["result_digest"]),
        "fixture_shared_ledger_state": str(receipt["state"]),
        "authorized_live_shape": {
            "targets": 1,
            "network_call_ceiling": 1,
            "retry_ceiling": 0,
            "model_provider_embedding_rerank_evidence_calls": [0, 0, 0, 0, 0],
        },
        "project_os_preflight": {
            "status": str(preflight["status"]),
            "run_scope": str(preflight["run_scope"]),
        },
        "implementation": {
            "module_ref": MODULE_PATH.relative_to(ROOT).as_posix(),
            "module_sha256": _normalized(MODULE_PATH),
            "policy_ref": POLICY_PATH.relative_to(ROOT).as_posix(),
            "policy_sha256": _normalized(POLICY_PATH),
        },
        "live_calls_observed": 0,
        "known_boundary": (
            "The proof uses a fake transport. It authorizes no live call by itself "
            "and does not prove candidate recall, ranking, Evidence or release."
        ),
    }
    output = {**body, "proof_digest": canonical_digest(body)}
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": output["status"],
                "proof_digest": output["proof_digest"],
                "authorized_live_shape": output["authorized_live_shape"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
