from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a readable Chinese trace for expanded synthesis outputs."
    )
    parser.add_argument(
        "--pool-path",
        default="reports/evidence_pool/sec_tech_10k_expanded_v0_2_calibrated_evidence_pool_grouped.json",
    )
    parser.add_argument(
        "--synthesis-path",
        default="reports/demo/qwen9b_expanded_v0_2_synthesis_demo.json",
    )
    parser.add_argument(
        "--quality-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_answer_quality.json",
    )
    parser.add_argument(
        "--citation-validation-path",
        default="reports/quality/sec_tech_10k_expanded_v0_2_citation_validation.json",
    )
    parser.add_argument(
        "--output-path",
        default="reports/demo/qwen9b_expanded_v0_2_trace_zh.md",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pool = _read_json(REPO_ROOT / args.pool_path)
    synthesis = _read_json(REPO_ROOT / args.synthesis_path)
    quality = _read_json(REPO_ROOT / args.quality_path)
    citation_validation = _read_json(REPO_ROOT / args.citation_validation_path)

    pool_by_query = {row["query_id"]: row for row in pool.get("queries", [])}
    quality_by_query = {row["query_id"]: row for row in quality.get("queries", [])}
    validation_by_query = {
        row["query_id"]: row for row in citation_validation.get("queries", [])
    }

    lines = [
        "# Qwen3.5-9B Expanded Evaluation Trace",
        "",
        "本报告由现有 evidence pool、synthesis output、citation validation 和 answer-quality scorer 导出；不包含新的模型推理。",
        "",
        "## 总览",
        "",
        f"- Query 数量: {synthesis.get('summary', {}).get('query_count')}",
        f"- 解析状态: {_json_inline(synthesis.get('summary', {}).get('parse_status_counts', {}))}",
        f"- 模型结论质量: {_json_inline(synthesis.get('summary', {}).get('conclusion_quality_counts', {}))}",
        f"- Citation validation: pass={citation_validation.get('pass_count')}, repair_required={citation_validation.get('repair_required_count')}",
        f"- Answer-quality diagnostic mean: {quality.get('summary', {}).get('mean_overall')}",
        f"- 总耗时: {synthesis.get('timings', {}).get('total_sec')} sec；模型加载: {synthesis.get('timings', {}).get('load_model_sec')} sec",
        "",
    ]

    for result in synthesis.get("results", []):
        query_id = str(result.get("query_id"))
        pool_row = pool_by_query.get(query_id, {})
        quality_row = quality_by_query.get(query_id, {})
        validation_row = validation_by_query.get(query_id, {})
        synthesis_obj = result.get("synthesis") or {}
        lines.extend(
            [
                f"## {query_id}",
                "",
                f"- Query: {pool_row.get('query') or result.get('query')}",
                f"- Profile: {pool_row.get('scoring_profile') or result.get('mode')}",
                f"- Scope: tickers={pool_row.get('tickers') or pool_row.get('ticker')}, fiscal_years={pool_row.get('fiscal_years') or pool_row.get('fiscal_year')}",
                f"- Package: facets={result.get('package_metrics', {}).get('facet_count')}, aspects={result.get('package_metrics', {}).get('aspect_count')}, citation={result.get('package_metrics', {}).get('citation_evidence_count')}, background={result.get('package_metrics', {}).get('background_evidence_count')}, missing={result.get('package_metrics', {}).get('missing_aspect_count')}",
                f"- Output: parse={result.get('parse_status')}, model_quality={synthesis_obj.get('conclusion_quality')}, cited_objects={result.get('output_metrics', {}).get('cited_object_count')}",
                f"- Citation validator: status={validation_row.get('status')}, hard_failures={validation_row.get('hard_failure_count', 0)}, warnings={validation_row.get('warning_count', 0)}",
                f"- Answer-quality overall: {quality_row.get('overall')}",
                "",
                "### 模型拆分任务",
                "",
            ]
        )
        for facet in pool_row.get("facets", []):
            lines.append(
                f"- {facet.get('facet')}: {len(facet.get('aspects', []))} aspects; must_find={facet.get('facet_must_find')}"
            )
            for aspect in facet.get("aspects", []):
                citation_count = len(aspect.get("citation_evidence") or [])
                background_count = len(aspect.get("background_evidence") or [])
                missing = aspect.get("missing_reason")
                status = (
                    f"citation={citation_count}, background={background_count}"
                    if not missing
                    else f"missing={missing}"
                )
                lines.append(
                    f"  - {aspect.get('aspect_id')}: {aspect.get('aspect')} ({status})"
                )
        lines.extend(["", "### Verifier 选择摘要", ""])
        for facet in pool_row.get("facets", []):
            for aspect in facet.get("aspects", []):
                picks = aspect.get("citation_evidence") or []
                if not picks:
                    continue
                evidence = picks[0]
                lines.append(
                    "- "
                    + f"{aspect.get('aspect_id')}: "
                    + f"{evidence.get('object_id')} "
                    + f"({evidence.get('object_type')}, label={evidence.get('verifier_label')}, "
                    + f"conf={evidence.get('verifier_confidence')}, rerank={evidence.get('rerank_score')})"
                )
        lines.extend(["", "### 模型输出总结", ""])
        lines.append(synthesis_obj.get("answer_zh") or "(empty)")
        lines.extend(["", "### Key Findings", ""])
        for index, finding in enumerate(synthesis_obj.get("key_findings") or [], start=1):
            lines.append(
                f"{index}. {finding.get('claim_zh')} citations={finding.get('cited_object_ids')}"
            )
        missing_items = _as_list(synthesis_obj.get("missing_or_uncertain_zh"))
        if missing_items:
            lines.extend(["", "### Missing / Uncertain", ""])
            for item in missing_items:
                lines.append(f"- {item}")
        notes = _as_list(synthesis_obj.get("evidence_use_notes_zh"))
        if notes:
            lines.extend(["", "### Evidence Notes", ""])
            for item in notes:
                lines.append(f"- {item}")
        lines.append("")

    output_path = REPO_ROOT / args.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(str(output_path))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_inline(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


if __name__ == "__main__":
    main()
