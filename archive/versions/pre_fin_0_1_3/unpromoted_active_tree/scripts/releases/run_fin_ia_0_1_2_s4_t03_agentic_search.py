from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from typing import Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    Fin012S4T03SearchRunner,
    SearchAdmission,
    SourceResponse,
    UrllibSourceTransport,
    compile_current_nvda_executable_requests,
)


class _ZeroCallSecTransport:
    live_network = False

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
    ) -> SourceResponse:
        rows = (
            ("0001045810-26-000051", "8-K", "2026-05-20", "nvda-20260520.htm"),
            ("0001045810-25-000230", "10-Q", "2025-11-19", "nvda-20251026.htm"),
            ("0001045810-25-000023", "10-K", "2025-02-26", "nvda-20250126.htm"),
            ("0001045810-24-000029", "10-K", "2024-02-21", "nvda-20240128.htm"),
            ("0001045810-23-000017", "10-K", "2023-02-24", "nvda-20230129.htm"),
        )
        payload = {
            "filings": {
                "recent": {
                    "accessionNumber": [row[0] for row in rows],
                    "form": [row[1] for row in rows],
                    "filingDate": [row[2] for row in rows],
                    "primaryDocument": [row[3] for row in rows],
                }
            }
        }
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": "application/json"},
            body=json.dumps(payload).encode("utf-8"),
        )


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_admission(path: Path) -> SearchAdmission:
    return SearchAdmission.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _summary(result: Mapping[str, object]) -> dict[str, object]:
    request_results = list(result.get("request_results") or [])
    return {
        "run_id": result.get("run_id"),
        "attempt_id": result.get("attempt_id"),
        "status": result.get("status"),
        "phase": result.get("phase"),
        "code": result.get("code"),
        "request_results": [
            {
                "program_cell_id": row["request"]["program_cell_id"],
                "status": row["status"],
                "accepted_count": row["accepted_count"],
                "rejected_count": row["rejected_count"],
                "typed_gap_codes": row["typed_gap_codes"],
            }
            for row in request_results
        ],
        "observed_counts": result.get("observed_counts"),
        "terminal_object": result.get("terminal_object"),
        "T04_consumption_authorized": result.get("T04_consumption_authorized"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("zero-call-proof", "live"), required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--admission", type=Path)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    if args.mode == "zero-call-proof":
        requests = compile_current_nvda_executable_requests()
        admission = SearchAdmission.create(
            issued_at=_utc(now - timedelta(minutes=1)),
            expires_at=_utc(now + timedelta(hours=1)),
            request_digests=tuple(row.request_digest for row in requests),
        )
        transport = _ZeroCallSecTransport()
    else:
        if args.admission is None:
            parser.error("--admission is required in live mode")
        admission = _load_admission(args.admission)
        transport = UrllibSourceTransport()

    result = Fin012S4T03SearchRunner(
        repository_root=ROOT,
        runtime_root=args.runtime_root,
        transport=transport,
    ).execute(
        admission=admission,
        now=_utc(now),
        run_nonce=args.run_nonce,
    )
    print(json.dumps(_summary(result), ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
