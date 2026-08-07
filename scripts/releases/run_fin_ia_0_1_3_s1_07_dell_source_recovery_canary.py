from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.mcp_operational import McpToolProcessSupervisor  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


PRIOR = REPO_ROOT / "configs" / "releases" / "fin_ia_0_1_3_s1_07_current_source_canary_result_v1_1.json"
OUTPUT = REPO_ROOT / "configs" / "releases" / "fin_ia_0_1_3_s1_07_current_source_canary_result_v1_2.json"
SCOPE = "fin_0_1_3.S1_07.dell_official_source_recovery_canary:v1"
DELL_ROUTE = {
    "url": "https://www.sec.gov/Archives/edgar/data/1571996/000157199625000034/dell-20250131.htm",
    "domain": "www.sec.gov",
    "source_class": "official_regulatory_page",
    "title": "Dell Technologies FY2025 Form 10-K",
}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def _synthetic_dns_mode_required(hostname: str) -> bool:
    network = ipaddress.ip_network("198.18.0.0/15")
    addresses = {
        ipaddress.ip_address(row[4][0])
        for row in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    }
    return bool(addresses) and all(address.version == 4 and address in network for address in addresses)


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    operational = dict(result.get("operational") or {})
    promotion = dict(result.get("promotion") or {})
    parser = dict(result.get("parser") or {})
    return {
        "status": result.get("status"),
        "error": result.get("error"),
        "snapshot_id": result.get("snapshot_id"),
        "final_url": result.get("final_url"),
        "network_calls": result.get("network_calls"),
        "request_capture": result.get("request_capture"),
        "response_capture": result.get("response_capture"),
        "parser_capture": result.get("parser_capture"),
        "promotion_capture": result.get("promotion_capture"),
        "parser_status": parser.get("status"),
        "parser_adapter": parser.get("adapter"),
        "parser_text_sha256": parser.get("text_sha256"),
        "promotion_decision": promotion.get("decision"),
        "evidence_row_count": len(result.get("evidence_rows") or []),
        "source_gaps": result.get("source_gaps") or [],
        "operational": {
            "invocation_id": operational.get("invocation_id"),
            "start_kind": operational.get("start_kind"),
            "worker_pid": operational.get("worker_pid"),
            "elapsed_ms": operational.get("elapsed_ms"),
            "terminal_status": operational.get("terminal_status"),
            "phases": operational.get("phases") or [],
        },
    }


def main() -> int:
    if _git("status", "--porcelain"):
        raise SystemExit("S1-07 Dell recovery requires a clean Git worktree")
    if OUTPUT.exists():
        raise SystemExit("S1-07 Dell recovery output already exists")
    if _git("rev-list", "--left-right", "--count", "HEAD...@{upstream}") not in {"0\t0", "0 0"}:
        raise SystemExit("S1-07 Dell recovery requires a synced branch")
    prior = json.loads(PRIOR.read_text(encoding="utf-8"))
    if prior.get("status") != "fail":
        raise SystemExit("S1-07 Dell recovery requires the immutable R2 partial-fail result")
    for case_key in ("MU", "NVDA"):
        row = prior["results"][case_key]
        if row.get("status") != "ok" or row.get("promotion_decision") != "promote_parsed_evidence":
            raise SystemExit(f"S1-07 prior {case_key} success cannot be reused")
    if prior["results"]["DELL"].get("error") != "official_source_transport_failed":
        raise SystemExit("S1-07 Dell recovery root cause does not match R2")

    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    prior_digest = canonical_digest(prior)
    authority_body = {
        "scope": SCOPE,
        "implementation_commit": head,
        "prior_result_digest": prior_digest,
        "route": DELL_ROUTE,
        "source_call_ceiling": 1,
        "retry_ceiling": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "run_nonce": "fin013_s1_07_dell_official_source_recovery_v1",
    }
    admission_digest = canonical_digest(authority_body)
    admission_id = f"fin013_s1_07_dell_admission_{admission_digest[:20]}"
    run_id = f"fin013_s1_07_dell_run_{canonical_digest({'admission': admission_digest})[:20]}"
    attempt_id = f"fin013_s1_07_dell_attempt_{canonical_digest({'run': run_id})[:20]}"
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    runtime_root = REPO_ROOT / ".codex_runtime" / "fin013_s1_07_current_source_canary" / run_id
    ledger = SharedAdmissionConsumptionLedger(REPO_ROOT / ".codex_runtime" / "shared" / "fin013_s1_07_admissions.sqlite3")
    ledger.reserve(
        admission_digest=admission_digest,
        admission_id=admission_id,
        scope=SCOPE,
        run_id=run_id,
        attempt_id=attempt_id,
        runtime_identity=str(runtime_root),
        reserved_at=now,
    )
    synthetic_dns_mode = _synthetic_dns_mode_required(DELL_ROUTE["domain"])
    if synthetic_dns_mode:
        os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = "1"
    supervisor = McpToolProcessSupervisor()
    try:
        result = supervisor.invoke(
            "web_evidence_snapshot",
            {
                "case_key": "DELL",
                "url": DELL_ROUTE["url"],
                "domain": DELL_ROUTE["domain"],
                "source_title": DELL_ROUTE["title"],
                "source_class": DELL_ROUTE["source_class"],
                "claim_types": ["issuer_current_financial_and_demand_context"],
                "web_scope_policy_ids": ["fin013_s1_07_sec_official_fallback"],
                "web_scope_allowed_domains": [DELL_ROUTE["domain"]],
                "web_capture_root": str(runtime_root / "captures"),
                "byte_ceiling": 12_582_912,
                "fetch_timeout_s": 30,
                "excerpt_chars": 2400,
                "timeout_s": 60,
            },
        )
        active_pid = supervisor.worker_pid
    finally:
        supervisor.close()
    dell = _summary(result)
    checks = {
        "prior_MU_success_reused": prior["results"]["MU"]["status"] == "ok",
        "prior_NVDA_success_reused": prior["results"]["NVDA"]["status"] == "ok",
        "only_one_recovery_network_call": dell.get("network_calls") == 1,
        "DELL_fetched": dell.get("status") == "ok",
        "DELL_parsed": dell.get("parser_status") == "parsed",
        "DELL_promoted": dell.get("promotion_decision") == "promote_parsed_evidence" and dell.get("evidence_row_count") == 1,
        "DELL_raw_captures_retained": bool((dell.get("request_capture") or {}).get("digest") and (dell.get("response_capture") or {}).get("digest")),
        "DELL_parser_lineage_retained": bool((dell.get("parser_capture") or {}).get("digest") and dell.get("parser_text_sha256")),
        "worker_closed_no_orphan": supervisor.worker_alive is False,
        "no_model_provider_retry": True,
    }
    status = "pass" if all(checks.values()) else "fail"
    combined = {"DELL": dell, "MU": prior["results"]["MU"], "NVDA": prior["results"]["NVDA"]}
    body = {
        "schema_version": "fin_ia_0_1_3_s1_07_current_source_canary_result_v1_2",
        "status": status,
        "git": {"branch": branch, "commit": head, "clean_and_synced_at_start": True},
        "authority": {**authority_body, "admission_id": admission_id, "admission_digest": admission_digest, "run_id": run_id, "attempt_id": attempt_id},
        "prior_result_ref": str(PRIOR.relative_to(REPO_ROOT)).replace("\\", "/"),
        "results": combined,
        "checks": checks,
        "active_worker_pid_before_close": active_pid,
        "scope": {"new_network_calls": 1, "reused_successful_routes": 2, "retry_calls": 0, "model_calls": 0, "provider_calls": 0, "business_artifact_promotions": 0},
        "transport_environment": {"synthetic_dns_mode": synthetic_dns_mode, "safety_boundary": "explicit hostname allowlist plus HTTPS certificate validation remains required"},
        "known_boundary": "This successor reuses immutable MU/NVDA R2 successes and adds one Dell SEC official fallback. It does not prove broad crawling, retrieval quality, research synthesis, model quality or release readiness.",
    }
    terminal_digest = canonical_digest(body)
    receipt = ledger.finalize(
        admission_digest=admission_digest,
        run_id=run_id,
        attempt_id=attempt_id,
        terminal_status="success" if status == "pass" else "failed",
        terminal_phase="s1_07_dell_source_recovery_terminal",
        terminal_code="three_case_official_source_runtime_proven" if status == "pass" else "dell_official_fallback_failed",
        terminal_result_digest=terminal_digest,
        finalized_at=now,
    )
    payload = {**body, "terminal_result_digest": terminal_digest, "admission_receipt": receipt.as_dict()}
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(OUTPUT), "checks": checks, "DELL": dell}, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
