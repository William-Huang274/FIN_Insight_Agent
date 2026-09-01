from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from financial_facts.sec_snapshot import (  # noqa: E402
    HARD_MAXIMUM_COMPANIES,
    MAXIMUM_RESPONSE_BYTES,
    MAXIMUM_REQUESTS_PER_SECOND,
    SecSnapshotError,
    SecSnapshotRequestPolicy,
    capture_sec_companyfacts_snapshot,
    load_sec_snapshot_input_manifest,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Capture immutable SEC CompanyFacts and Submissions JSON without "
            "normalizing or promoting facts."
        )
    )
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument(
        "--requests-per-second",
        type=float,
        default=MAXIMUM_REQUESTS_PER_SECOND,
    )
    parser.add_argument(
        "--maximum-companies",
        type=int,
        default=HARD_MAXIMUM_COMPANIES,
    )
    parser.add_argument(
        "--maximum-response-bytes",
        type=int,
        default=MAXIMUM_RESPONSE_BYTES,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = load_sec_snapshot_input_manifest(args.input_manifest.resolve())
        policy = SecSnapshotRequestPolicy(
            timeout_seconds=args.timeout_seconds,
            requests_per_second=args.requests_per_second,
            maximum_companies=args.maximum_companies,
            maximum_response_bytes=args.maximum_response_bytes,
            per_source_attempts=1,
        )
        result = capture_sec_companyfacts_snapshot(
            manifest,
            output_root=args.output_root,
            request_policy=policy,
        )
    except SecSnapshotError as exc:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failure_code": exc.code,
                    "failure_receipt": (
                        str(exc.failure_receipt) if exc.failure_receipt else None
                    ),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:
        # Manifest/schema errors are pre-attempt failures.  Never echo the
        # exception text because it may contain an environment value or path.
        print(
            json.dumps(
                {
                    "status": "failed",
                    "failure_code": "sec_snapshot_preflight_invalid",
                    "failure_type": type(exc).__name__,
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {
                "status": result.status,
                "attempt_id": result.attempt_id,
                "company_count": result.company_count,
                "source_count": result.source_count,
                "manifest_digest": result.manifest_digest,
                "output_root": str(args.output_root.resolve()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
