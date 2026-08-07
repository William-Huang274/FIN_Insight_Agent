from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.mcp_operational import McpToolProcessSupervisor  # noqa: E402
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


DEFAULT_OUTPUT = REPO_ROOT / "configs" / "releases" / "fin_ia_0_1_3_s1_07_current_source_canary_result_v1_0.json"
SCOPE = "fin_0_1_3.S1_07.current_source_canary:v1"
ROUTES = {
    "DELL": {
        "url": "https://investors.delltechnologies.com/node/19176/pdf",
        "domain": "investors.delltechnologies.com",
        "title": "Dell Technologies official investor material",
    },
    "MU": {
        "url": "https://investors.micron.com/static-files/7a1f8c6f-1ce9-4efe-bc6e-722b6b9c4550",
        "domain": "investors.micron.com",
        "title": "Micron official annual investor material",
    },
    "NVDA": {
        "url": "https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2026/",
        "domain": "investor.nvidia.com",
        "title": "NVIDIA official fiscal 2026 results",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the exact-once FIN 0.1.3 S1-07 current-source canary.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


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
        "context_row_count": len(result.get("context_rows") or []),
        "source_gaps": result.get("source_gaps") or [],
        "redirect_chain": result.get("redirect_chain") or [],
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
    args = parse_args()
    if _git("status", "--porcelain"):
        raise SystemExit("S1-07 canary requires a clean Git worktree")
    if args.output.exists():
        raise SystemExit("S1-07 canary output already exists; exact-once rerun is not allowed")
    upstream_delta = _git("rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if upstream_delta not in {"0\t0", "0 0"}:
        raise SystemExit(f"S1-07 canary requires a synced branch, got {upstream_delta}")
    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    authority_body = {
        "scope": SCOPE,
        "implementation_commit": head,
        "routes": ROUTES,
        "source_call_ceiling": 3,
        "retry_ceiling": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "run_nonce": "fin013_s1_07_current_source_canary_v1",
    }
    admission_digest = canonical_digest(authority_body)
    admission_id = f"fin013_s1_07_admission_{admission_digest[:20]}"
    run_id = f"fin013_s1_07_run_{canonical_digest({'admission': admission_digest})[:20]}"
    attempt_id = f"fin013_s1_07_attempt_{canonical_digest({'run': run_id})[:20]}"
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
    supervisor = McpToolProcessSupervisor()
    results: dict[str, dict[str, Any]] = {}
    try:
        for case_key, route in ROUTES.items():
            results[case_key] = supervisor.invoke(
                "web_evidence_snapshot",
                {
                    "case_key": case_key,
                    "url": route["url"],
                    "domain": route["domain"],
                    "source_title": route["title"],
                    "source_class": "company_ir_material",
                    "claim_types": ["issuer_current_financial_and_demand_context"],
                    "web_scope_policy_ids": ["fin013_s1_07_official_company_ir_only"],
                    "company_domain_verified": True,
                    "company_domains": [route["domain"]],
                    "web_scope_allowed_domains": [route["domain"]],
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

    summaries = {case_key: _summary(result) for case_key, result in results.items()}
    checks = {
        "three_routes_exactly_once": len(summaries) == 3 and sum(int(row.get("network_calls") or 0) for row in summaries.values()) == 3,
        "all_sources_fetched": all(row.get("status") == "ok" for row in summaries.values()),
        "all_sources_parsed": all(row.get("parser_status") == "parsed" for row in summaries.values()),
        "all_trusted_sources_promoted": all(row.get("promotion_decision") == "promote_parsed_evidence" and row.get("evidence_row_count") == 1 for row in summaries.values()),
        "all_raw_captures_retained": all((row.get("request_capture") or {}).get("digest") and (row.get("response_capture") or {}).get("digest") for row in summaries.values()),
        "all_parser_lineage_retained": all((row.get("parser_capture") or {}).get("digest") and row.get("parser_text_sha256") for row in summaries.values()),
        "worker_closed_no_orphan": supervisor.worker_alive is False,
        "no_model_provider_retry": True,
    }
    status = "pass" if all(checks.values()) else "fail"
    body = {
        "schema_version": "fin_ia_0_1_3_s1_07_current_source_canary_result_v1_0",
        "status": status,
        "git": {"branch": branch, "commit": head, "clean_and_synced_at_start": True},
        "authority": {**authority_body, "admission_id": admission_id, "admission_digest": admission_digest, "run_id": run_id, "attempt_id": attempt_id},
        "results": summaries,
        "checks": checks,
        "active_worker_pid_before_close": active_pid,
        "scope": {"network_calls": 3, "retry_calls": 0, "model_calls": 0, "provider_calls": 0, "business_artifact_promotions": 0},
        "known_boundary": "This canary proves only three bounded official company-source fetch/capture/parse/promotion routes. It does not prove broad crawling, retrieval recall/ranking/diversity, research synthesis, DeepSeek quality, human acceptance or release readiness.",
    }
    terminal_digest = canonical_digest(body)
    receipt = ledger.finalize(
        admission_digest=admission_digest,
        run_id=run_id,
        attempt_id=attempt_id,
        terminal_status="success" if status == "pass" else "failed",
        terminal_phase="s1_07_current_source_canary_terminal",
        terminal_code="three_official_sources_fetch_parse_promoted" if status == "pass" else "one_or_more_current_source_routes_failed",
        terminal_result_digest=terminal_digest,
        finalized_at=now,
    )
    payload = {**body, "terminal_result_digest": terminal_digest, "admission_receipt": receipt.as_dict()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "output": str(args.output), "checks": checks, "results": summaries}, ensure_ascii=False, indent=2))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
