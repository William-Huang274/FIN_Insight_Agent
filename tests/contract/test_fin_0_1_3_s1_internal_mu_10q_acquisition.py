from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.s1_internal_mu_10q_acquisition import (  # noqa: E402
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


class FakeTransport:
    live_network = False

    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls = 0

    def fetch(self, *, url, headers, allowed_hosts, timeout_seconds, byte_ceiling):
        self.calls += 1
        assert url.endswith("/000072312526000015/mu-20260528.htm")
        assert allowed_hosts == {"www.sec.gov"}
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "text/html"},
            body=self.body,
        )


def _admission(policy: dict) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    import hashlib

    normalized = lambda path: hashlib.sha256(  # noqa: E731
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    return issue_internal_mu_10q_acquisition_admission(
        policy=policy,
        implementation_commit="a" * 40,
        implementation_file_sha256=normalized(MODULE_PATH),
        policy_file_sha256=normalized(POLICY_PATH),
        issued_at=now.isoformat().replace("+00:00", "Z"),
        expires_at=(now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        nonce="fixture-nonce",
    )


def _html(*, valid: bool) -> bytes:
    text = (
        "Micron Technology quarterly report Form 10-Q for the quarter ended "
        "May 28, 2026. Risk Factors. Consolidated Statements of Cash Flows and "
        "cash and cash equivalents."
        if valid
        else "Micron Technology unrelated page"
    )
    return f"<html><body><h1>{text}</h1></body></html>".encode()


def test_single_document_fake_chain_succeeds_and_terminalizes(tmp_path: Path) -> None:
    policy = load_internal_mu_10q_acquisition_policy(POLICY_PATH, repo_root=ROOT)
    admission = _admission(policy)
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "ledger.sqlite3")
    transport = FakeTransport(_html(valid=True))
    result = execute_internal_mu_10q_acquisition_guarded(
        policy=policy,
        admission=admission,
        runtime_root=tmp_path / "runtime",
        ledger=ledger,
        transport=transport,
        observed_at=admission["issued_at"],
    )
    assert result["status"] == "completed_target_acquired"
    assert result["observed_counts"]["network_calls"] == 0
    assert transport.calls == 1
    assert result["source_result"]["source"]["form_type"] == "10-Q"
    assert result["source_result"]["candidate_state"] == "captured_source_not_evidence"
    assert ledger.read(admission["admission_digest"]).state == "terminal"


def test_marker_failure_preserves_capture_and_returns_typed_gap(tmp_path: Path) -> None:
    policy = load_internal_mu_10q_acquisition_policy(POLICY_PATH, repo_root=ROOT)
    admission = _admission(policy)
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "ledger.sqlite3")
    result = execute_internal_mu_10q_acquisition_guarded(
        policy=policy,
        admission=admission,
        runtime_root=tmp_path / "runtime",
        ledger=ledger,
        transport=FakeTransport(_html(valid=False)),
        observed_at=admission["issued_at"],
    )
    assert result["status"] == "completed_with_attempt_backed_gap"
    assert result["source_result"]["failure_code"].startswith(
        "internal_mu_10q_acquisition_markers_absent"
    )
    assert len(result["capture_refs"]) == 2
    assert ledger.read(admission["admission_digest"]).state == "terminal"
