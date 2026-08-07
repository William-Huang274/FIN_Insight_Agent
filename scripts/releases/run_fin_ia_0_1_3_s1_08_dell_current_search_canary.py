from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import uuid
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.official_source_attempt_program import (  # noqa: E402
    UrllibOfficialSourceTransport,
)
from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    load_source_catalog,
)
from sec_agent.s1_08_live_canary import (  # noqa: E402
    DellSearchCanaryAdmission,
    execute_dell_search_canary,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


CATALOG_PATH = (
    REPO_ROOT
    / "configs"
    / "runtime"
    / "fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v1_0.json"
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_3_s1_08_dell_current_search_canary_result_v1_0.json"
)
RESEARCH_OBJECTIVE = (
    "Evaluate Dell AI infrastructure demand durability, value and profit capture, "
    "supply-chain constraints, customer deployment evidence, counterevidence and "
    "what would change the investment judgment as of 2026-08-06."
)
EMAIL_RE = re.compile(r"^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$", re.IGNORECASE)


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _synthetic_dns_mode_required(catalog: dict) -> bool:
    synthetic = ipaddress.ip_network("198.18.0.0/15")
    hosts = sorted(
        {
            (urlparse(str(url)).hostname or "").lower()
            for entity in catalog.get("entities") or []
            for url in entity.get("official_landing_pages") or []
        }
        | {"www.sec.gov", "sec.gov"}
    )
    observed_synthetic = False
    for host in hosts:
        addresses = {
            ipaddress.ip_address(row[4][0])
            for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
        for address in addresses:
            forbidden = (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_multicast
                or address.is_reserved
                or address.is_unspecified
            )
            if forbidden and not (address.version == 4 and address in synthetic):
                raise SystemExit("S1-08 canary resolved an allowlisted host to a forbidden non-synthetic address")
            observed_synthetic = observed_synthetic or (
                address.version == 4 and address in synthetic
            )
    return observed_synthetic


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the exact-once FIN 0.1.3 S1-08 DELL current-search canary."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if _git("status", "--porcelain"):
        raise SystemExit("S1-08 canary requires a clean Git worktree")
    if args.output.exists():
        raise SystemExit("S1-08 canary output already exists; exact-once rerun is forbidden")
    upstream_delta = _git("rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if upstream_delta not in {"0\t0", "0 0"}:
        raise SystemExit(f"S1-08 canary requires a synced branch, got {upstream_delta}")
    contact = str(os.environ.get("FINSIGHT_SEC_CONTACT_EMAIL") or "").strip()
    if not EMAIL_RE.fullmatch(contact):
        raise SystemExit("S1-08 canary requires a valid runtime SEC contact identity")

    catalog = load_source_catalog(CATALOG_PATH)
    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    started = _utc_now()
    admission = DellSearchCanaryAdmission.issue(
        catalog=catalog,
        implementation_commit=head,
        run_nonce=f"dell-current-search-{started:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex}",
        issued_at=_iso(started),
        expires_at=_iso(started + timedelta(hours=2)),
        network_call_ceiling=24,
        document_ceiling_per_query=2,
    )
    runtime_root = (
        REPO_ROOT
        / ".codex_runtime"
        / "fin013_s1_08_dell_current_search_canary"
        / admission.admission_id
    )
    ledger = SharedAdmissionConsumptionLedger(
        REPO_ROOT / ".codex_runtime" / "shared" / "fin013_s1_08_admissions.sqlite3"
    )
    synthetic_dns_mode = _synthetic_dns_mode_required(catalog)
    if synthetic_dns_mode:
        os.environ["FINSIGHT_ALLOW_SYNTHETIC_DNS"] = "1"

    result = execute_dell_search_canary(
        admission=admission,
        catalog_path=CATALOG_PATH,
        runtime_root=runtime_root,
        shared_admission_ledger=ledger,
        transport=UrllibOfficialSourceTransport(),
        implementation_commit=head,
        research_objective=RESEARCH_OBJECTIVE,
        observed_at=_iso(started),
        market_snapshot=None,
    )
    payload = {
        "schema_version": "fin_ia_0_1_3_s1_08_dell_current_search_canary_result_v1_0",
        "status": result["status"],
        "git": {
            "branch": branch,
            "commit": head,
            "clean_and_synced_at_start": True,
        },
        "runtime_identity": {
            "SEC_contact_configured": True,
            "SEC_contact_plaintext_persisted": False,
            "synthetic_dns_mode": synthetic_dns_mode,
        },
        "market_snapshot_boundary": {
            "provided": False,
            "reason": "no governed as-of-2026-08-06 DELL market snapshot was bound to this canary",
        },
        "result": result,
        "known_boundary": (
            "This exact-once canary measures DELL live candidate generation and typed gaps. "
            "It does not admit ranking, reranking, MU/NVDA, DeepSeek, S3 research, report "
            "quality, human acceptance or release readiness."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "phase": result["phase"],
                "code": result["code"],
                "network_calls": result["observed_counts"]["network_calls"],
                "accepted_candidates": len(
                    (result.get("candidate_result") or {}).get("accepted_candidates") or []
                ),
                "selected_candidates": len(
                    (result.get("candidate_result") or {}).get("selected_candidates") or []
                ),
                "typed_gaps": len(
                    (result.get("candidate_result") or {}).get("typed_gaps") or []
                ),
                "output": str(args.output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
