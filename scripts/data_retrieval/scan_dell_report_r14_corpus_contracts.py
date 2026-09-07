from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from retrieval.dell_report_r14_common import DellReportR14ContractError  # noqa: E402
from retrieval.dell_report_r14_contracts import load_and_validate_r14_contracts  # noqa: E402
from retrieval.dell_report_runner_r14 import compile_input_text_r14  # noqa: E402


SOURCE_PATH = ROOT / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl"
OBJECT_PATH = ROOT / "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v9/objects.jsonl"
_BUNDLE = None


def _initialize() -> None:
    global _BUNDLE
    _BUNDLE = load_and_validate_r14_contracts(root=ROOT)


def _compile_case(case: tuple[str, str, str]) -> dict[str, Any]:
    lane, identity, text = case
    try:
        compile_input_text_r14(text=text, input_digest="0" * 64, bundle=_BUNDLE)
    except DellReportR14ContractError as exc:
        return {
            "lane": lane,
            "identity": identity,
            "text_sha256": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(),
            "text_prefix": text[:500],
            "status": "FAIL",
            "failure_code": str(exc),
        }
    except Exception as exc:
        return {
            "lane": lane,
            "identity": identity,
            "text_sha256": __import__("hashlib").sha256(text.encode("utf-8")).hexdigest(),
            "text_prefix": text[:500],
            "status": "ERROR",
            "failure_code": f"{type(exc).__name__}:{exc}",
        }
    return {"lane": lane, "identity": identity, "status": "PASS"}


def _cases(source_limit: int, object_limit: int) -> list[tuple[str, str, str]]:
    cases: list[tuple[str, str, str]] = []
    with SOURCE_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            cases.append(("source", row["evidence_id"], row["text"]))
            if source_limit and sum(1 for item in cases if item[0] == "source") >= source_limit:
                break
    seen_text: set[str] = set()
    object_count = 0
    with OBJECT_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            text = row["model_text"]
            digest = __import__("hashlib").sha256(text.encode("utf-8")).hexdigest()
            if digest in seen_text:
                continue
            seen_text.add(digest)
            cases.append(("compiled_unique_text", row["compiled_object_id"], text))
            object_count += 1
            if object_limit and object_count >= object_limit:
                break
    return cases


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=max(1, min(8, os.cpu_count() or 1)))
    parser.add_argument("--source-limit", type=int, default=0)
    parser.add_argument("--object-limit", type=int, default=0)
    args = parser.parse_args()
    cases = _cases(args.source_limit, args.object_limit)
    failures: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    passed = 0
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_initialize) as pool:
        for result in pool.map(_compile_case, cases, chunksize=32):
            if result["status"] == "PASS":
                passed += 1
                continue
            counts[result["failure_code"]] += 1
            if sum(1 for row in failures if row["failure_code"] == result["failure_code"]) < 3:
                failures.append(result)
    output = {
        "schema_version": "fin_ia_dell_03B_R14_corpus_contract_scan_v1_0",
        "case_count": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "failure_counts": dict(sorted(counts.items())),
        "minimal_examples": failures,
        "workers": args.workers,
        "model_provider_calls": 0,
        "files_written": 0,
    }
    print(json.dumps(output, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return 1 if counts else 0


if __name__ == "__main__":
    raise SystemExit(main())
