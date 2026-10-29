"""Evaluate reviewed evidence-preservation probes, not financial correctness.

Gold checks live outside Git and bind original SHA256 plus optional table index.
Whole-document presence and same-table preservation are separate measurements.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from hashlib import sha256
import json
import re
from pathlib import Path


def normalize(text):
    return " ".join(str(text).split()).casefold()


def contains(text, expected):
    expected = normalize(expected)
    if not expected:
        raise ValueError("empty_reviewed_anchor")
    left = r"(?<!\w)(?<!\d[.,])" if expected[0].isdigit() else r"(?<!\w)" if expected[0].isalnum() else ""
    right = r"(?!\w|[.,]\d)" if expected[-1].isdigit() else r"(?!\w)" if expected[-1].isalnum() else ""
    return re.search(left + re.escape(expected) + right, normalize(text)) is not None


def content_text(value):
    if isinstance(value, list):
        return " ".join(content_text(v) for v in value)
    return str(value)


def table_texts(output):
    if "tuples" in output:
        grouped = defaultdict(list)
        for row in output["tuples"]:
            # Attached prose may contain unrelated tables or embedded scripts.
            # Footnote linkage needs a separate reviewed check, not core-table credit.
            if row[1] in {"table_title", "table_preamble", "table_data"}:
                grouped[str(row[0])].append(content_text(row[2]))
        return [" ".join(parts) for parts in grouped.values()]
    return [b["text"] for b in output.get("blocks", []) if b["kind"] == "table"]


def evaluate(check, output):
    required = [normalize(v) for v in check["required"]]
    text = normalize(output["text"])
    missing = [r for r in required if not contains(text, r)]
    same_table = None
    if check["scope"] == "table":
        same_table = any(all(contains(t, r) for r in required) for t in table_texts(output))
    return {"whole_text_retained": not missing, "missing": missing,
            "same_table_retained": same_table,
            "passed": not missing and same_table is not False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--checks", type=Path, required=True)
    ap.add_argument("--result-index", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    from lxml import html
    samples = {s["id"]: s for s in json.loads(args.manifest.read_bytes())["samples"]}
    checks = json.loads(args.checks.read_bytes())["checks"]
    if len({c["id"] for c in checks}) != len(checks):
        raise ValueError("duplicate_reviewed_check")
    source_views = {}
    for sid in {c["document_id"] for c in checks}:
        raw = Path(samples[sid]["path"]).read_bytes()
        digest = sha256(raw).hexdigest()
        if digest != samples[sid]["raw_sha256"]:
            raise ValueError("original_digest_mismatch")
        root = html.fromstring(raw)
        for el in root.xpath('//script|//style|//noscript|//*[local-name()="ix:header"]'):
            el.drop_tree()
        source_views[sid] = root
    for check in checks:
        sid = check["document_id"]
        if check["raw_sha256"] != samples[sid]["raw_sha256"]:
            raise ValueError("reviewed_check_original_mismatch")
        root = source_views[sid]
        if check.get("table_index") is not None:
            root = root.xpath("//table")[check["table_index"]]
        text = normalize(" ".join(root.itertext()))
        if not all(contains(text, v) for v in check["required"]):
            raise ValueError("reviewed_check_not_supported_by_original: " + check["id"])
    rows = []
    seen_results = set()
    for path in json.loads(args.result_index.read_bytes())["results"]:
        result = json.loads(Path(path).read_bytes())
        identity = (result["id"], result["parser"])
        if identity in seen_results:
            raise ValueError("duplicate_parser_result")
        seen_results.add(identity)
        if result["raw_sha256"] != samples[result["id"]]["raw_sha256"]:
            raise ValueError("parser_result_original_mismatch")
        if result["manifest_sha256"] != sha256(args.manifest.read_bytes()).hexdigest():
            raise ValueError("parser_result_manifest_mismatch")
        if result["status"] != "parsed":
            raise ValueError("parser_not_successful")
        for check in checks:
            if check["document_id"] == result["id"]:
                rows.append({"check": check["id"], "parser": result["parser"],
                             "document_id": result["id"], **evaluate(check, result["output"])})
    summary = {}
    for parser in sorted({r["parser"] for r in rows}):
        selected = [r for r in rows if r["parser"] == parser]
        summary[parser] = {"checks": len(selected), "passed": sum(r["passed"] for r in selected),
                           "whole_text_retained": sum(r["whole_text_retained"] for r in selected)}
    output = {"scope": "reviewed_development_evidence_retention_not_numeric_fact_or_recall_accuracy",
              "checks_sha256": sha256(args.checks.read_bytes()).hexdigest(),
              "manifest_sha256": sha256(args.manifest.read_bytes()).hexdigest(),
              "summary": summary, "rows": rows}
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
