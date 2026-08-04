from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s4_t03_executable_agentic_search import (
    CASE_SEARCH_PROFILES,
    Fin012S4T03SearchError,
    Fin012S4T03SearchRunner,
    OfficialFilingIdentity,
    SearchAdmission,
    SourceResponse,
    UrllibSourceTransport,
    compile_current_case_executable_requests,
    parse_sec_submissions,
)


_FIXTURE_FILINGS = {
    "DELL": (
        ("0001571996-26-000021", "8-K", "2026-05-28", "dell-20260528.htm"),
        ("0001571996-25-000127", "10-Q", "2025-12-09", "dell-20251031.htm"),
        ("0001571996-25-000034", "10-K", "2025-03-25", "dell-20250131.htm"),
        ("0001571996-24-000036", "10-K", "2024-03-25", "dell-20240202.htm"),
        ("0001571996-23-000007", "10-K", "2023-03-30", "dell-20230203.htm"),
    ),
    "MU": (
        ("0000723125-26-000006", "10-Q", "2026-03-19", "mu-20260226.htm"),
        ("0000723125-25-000028", "10-K", "2025-10-03", "mu-20250828.htm"),
        ("0000723125-24-000027", "10-K", "2024-10-04", "mu-20240829.htm"),
        ("0000723125-23-000054", "10-K", "2023-10-06", "mu-20230831.htm"),
    ),
    "NVDA": (
        ("0001045810-26-000051", "8-K", "2026-05-20", "nvda-20260520.htm"),
        ("0001045810-25-000230", "10-Q", "2025-11-19", "nvda-20251026.htm"),
        ("0001045810-25-000023", "10-K", "2025-02-26", "nvda-20250126.htm"),
        ("0001045810-24-000029", "10-K", "2024-02-21", "nvda-20240128.htm"),
        ("0001045810-23-000017", "10-K", "2023-02-24", "nvda-20230129.htm"),
    ),
}


class ZeroCallIssuerTransport:
    """Case-bound SEC identity fixture; never performs a network call."""

    live_network = False

    def __init__(self, case_key: str) -> None:
        if case_key not in _FIXTURE_FILINGS:
            raise ValueError("t05_current_search_fixture_case_unsupported")
        self.case_key = case_key

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
    ) -> SourceResponse:
        profile = CASE_SEARCH_PROFILES[self.case_key]
        if (
            url != profile["sec_submissions_url"]
            or set(allowed_hosts) != set(profile["allowed_source_hosts"])
            or "Authorization" in headers
            or "Cookie" in headers
            or timeout_seconds <= 0
        ):
            raise ValueError("t05_current_search_fixture_request_mismatch")
        rows = _FIXTURE_FILINGS[self.case_key]
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
            body=json.dumps(payload, sort_keys=True).encode("utf-8"),
        )


def parse_dell_direct_ir_pdf_identity(
    response: SourceResponse,
    *,
    as_of: str,
    response_capture: Mapping[str, object],
) -> tuple[OfficialFilingIdentity, ...]:
    """Bind a direct official DELL PDF without inventing a publication date."""

    content_type = str(response.headers.get("content-type") or "").lower()
    if "application/pdf" not in content_type or not response.body.startswith(b"%PDF"):
        raise Fin012S4T03SearchError("t05_dell_ir_fallback_not_pdf")
    last_modified = str(response.headers.get("last-modified") or "").strip()
    try:
        published_at = parsedate_to_datetime(last_modified)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        published_at = published_at.astimezone(timezone.utc)
        cutoff = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        cutoff = cutoff.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError) as exc:
        raise Fin012S4T03SearchError(
            "t05_dell_ir_fallback_last_modified_invalid"
        ) from exc
    if published_at > cutoff:
        raise Fin012S4T03SearchError("t05_dell_ir_fallback_future_dated")
    url = str(response.final_url)
    profile = CASE_SEARCH_PROFILES["DELL"]
    if (
        urlparse(url).scheme != "https"
        or (urlparse(url).hostname or "").lower()
        not in set(profile["allowed_source_hosts"])
    ):
        raise Fin012S4T03SearchError("t05_dell_ir_fallback_locator_invalid")
    synthetic = hashlib.sha256(url.encode("utf-8")).hexdigest()[:18]
    return (
        OfficialFilingIdentity(
            accession=synthetic,
            filed_at=published_at.date().isoformat(),
            form_type="issuer_IR_pdf",
            primary_document=Path(urlparse(url).path).name or "DELL official IR PDF",
            source_url=url,
            source_capture_ref=str(response_capture["object_key"]),
            source_capture_digest=str(response_capture["digest"]),
            parser_adapter="dell_ir_direct_pdf_last_modified_identity_v1",
        ),
    )


class Fin012S4T05CurrentSearchRunner(Fin012S4T03SearchRunner):
    """Case-aware successor that preserves the frozen T03 NVDA runner."""

    def _load_official_filing_identities(
        self,
        *,
        case_key: str,
        as_of: str,
        admission: SearchAdmission,
        budget: object,
    ) -> tuple[OfficialFilingIdentity, ...]:
        if case_key != "DELL":
            return super()._load_official_filing_identities(
                case_key=case_key,
                as_of=as_of,
                admission=admission,
                budget=budget,
            )
        profile = CASE_SEARCH_PROFILES[case_key]
        allowed_hosts = set(profile["allowed_source_hosts"])
        self._consume_source_budget(admission, budget)
        try:
            response = self.source_client.fetch(
                url=str(profile["sec_submissions_url"]),
                allowed_hosts=allowed_hosts,
            )
            capture = self.source_client.capture_objects[-1]
            filings = parse_sec_submissions(
                response,
                as_of=as_of,
                response_capture=capture,
                cik=str(profile["cik"]),
            )
            if filings:
                return filings
        except Fin012S4T03SearchError:
            filings = ()
        if budget.fallbacks >= admission.fallback_ceiling:
            raise Fin012S4T03SearchError("t03_official_source_identity_unavailable")
        budget.fallbacks += 1
        self._consume_source_budget(admission, budget)
        response = self.source_client.fetch(
            url=str(profile["ir_url"]),
            allowed_hosts=allowed_hosts,
        )
        capture = self.source_client.capture_objects[-1]
        return parse_dell_direct_ir_pdf_identity(
            response,
            as_of=as_of,
            response_capture=capture,
        )


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def compile_zero_call_admission(
    case_key: str,
    *,
    now: datetime,
) -> SearchAdmission:
    requests = compile_current_case_executable_requests(case_key)
    return SearchAdmission.create(
        case_key=case_key,
        issued_at=_utc(now - timedelta(minutes=1)),
        expires_at=_utc(now + timedelta(hours=1)),
        request_digests=tuple(row.request_digest for row in requests),
    )


def load_exact_admission(path: Path, *, case_key: str) -> SearchAdmission:
    admission = SearchAdmission.from_dict(
        json.loads(path.read_text(encoding="utf-8"))
    )
    if admission.case_key != case_key:
        raise ValueError("t05_current_search_admission_case_mismatch")
    return admission


def summarize(result: Mapping[str, object]) -> dict[str, object]:
    request_results = list(result.get("request_results") or [])
    return {
        "run_id": result.get("run_id"),
        "attempt_id": result.get("attempt_id"),
        "case_key": result.get("case_key"),
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
    parser.add_argument("--case-key", choices=tuple(CASE_SEARCH_PROFILES), required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--admission", type=Path)
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    if args.mode == "zero-call-proof":
        if args.admission is not None:
            parser.error("--admission is forbidden in zero-call-proof mode")
        admission = compile_zero_call_admission(args.case_key, now=now)
        transport = ZeroCallIssuerTransport(args.case_key)
    else:
        if args.admission is None:
            parser.error("--admission is required in live mode")
        admission = load_exact_admission(args.admission, case_key=args.case_key)
        transport = UrllibSourceTransport()

    result = Fin012S4T05CurrentSearchRunner(
        repository_root=ROOT,
        runtime_root=args.runtime_root,
        transport=transport,
    ).execute(
        admission=admission,
        now=_utc(now),
        run_nonce=args.run_nonce,
    )
    print(json.dumps(summarize(result), ensure_ascii=False, indent=2))
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
