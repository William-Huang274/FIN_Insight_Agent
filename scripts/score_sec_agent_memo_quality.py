from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


SECTION_TERMS = {
    "direct_answer": ("直接回答", "direct answer"),
    "investment_thesis": ("investment thesis", "投资判断", "核心判断", "核心观点"),
    "what_changed": ("what changed", "发生了什么变化", "主要变化"),
    "why_it_matters": ("why it matters", "为什么重要", "投资含义", "业务含义"),
    "peer_readthrough": ("peer readthrough", "同行对比", "竞争格局", "竞争对手"),
    "counterarguments": ("counterarguments", "反证", "反例", "相反证据", "削弱条件"),
    "watch_items": ("watch items", "后续关注", "观察指标", "跟踪指标", "需要关注"),
    "source_limitations": ("source limitations", "证据边界", "来源限制", "资料限制"),
}

THESIS_TERMS = ("我的判断", "核心判断", "结论", "thesis", "增长质量", "可持续", "更稳妥")
CAUSAL_TERMS = ("因为", "由于", "驱动", "反映", "说明", "意味着", "导致", "源于", "受益于", "if", "如果")
SO_WHAT_TERMS = ("重要", "增长质量", "可持续", "盈利能力", "现金流", "竞争", "护城河", "风险", "削弱", "优势")
EVIDENCE_TERMS = ("依据", "SEC", "证据", "10-K", "million", "百万美元", "metric", "evidence", "毛利率", "收入")
AUDIT_ARTIFACT_TERMS = ("INTERACTIVE_", "metric_id", "total_value::", "percentage_rate::", "当前引用未保留", "未在 Exact-Value Ledger")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score SEC agent free-query outputs as investment-memo style answers.")
    parser.add_argument("--run-dir", required=True, help="Interactive run directory containing qwen/agent_outputs.jsonl and case.jsonl.")
    parser.add_argument(
        "--eval-set",
        default="eval_sets/sec_free_query_memo_quality_eval_v1.jsonl",
        help="Memo quality eval JSONL with query-level expectations.",
    )
    parser.add_argument("--output-path", default="", help="Optional JSON report path.")
    parser.add_argument("--pass-threshold", type=float, default=0.78)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    eval_rows = _read_jsonl(_resolve(args.eval_set))
    eval_by_query = {_norm(row.get("query")): row for row in eval_rows}
    agent_rows = _read_jsonl(run_dir / "qwen" / "agent_outputs.jsonl")
    case_rows = {str(row.get("case_id") or ""): row for row in _read_jsonl(run_dir / "case.jsonl")}

    results = []
    for agent in agent_rows:
        case = case_rows.get(str(agent.get("case_id") or ""), {})
        query = str(case.get("prompt") or case.get("query") or "")
        eval_case = eval_by_query.get(_norm(query), {})
        results.append(_score_row(agent, case, eval_case))

    report = {
        "schema_version": "sec_agent_memo_quality_v0.1",
        "run_dir": str(run_dir),
        "eval_set": str(_resolve(args.eval_set)),
        "case_count": len(results),
        "summary": _summarize(results, args.pass_threshold),
        "case_results": results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "memo_quality_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), **report["summary"]}, ensure_ascii=False, indent=2))


def _score_row(agent: dict[str, Any], case: dict[str, Any], eval_case: dict[str, Any]) -> dict[str, Any]:
    answer = agent.get("answer") if isinstance(agent.get("answer"), dict) else {}
    expected = eval_case.get("expected") if isinstance(eval_case.get("expected"), dict) else {}
    full_text = _answer_text(answer)
    summary = str(answer.get("summary") or "")
    drivers = [row for row in answer.get("decision_drivers") or [] if isinstance(row, dict)]
    key_points = [row for row in answer.get("key_points") or [] if isinstance(row, dict)]
    limitations = [str(row) for row in answer.get("limitations") or []]

    scores = {
        "thesis_clarity": _thesis_score(summary, full_text),
        "causal_depth": _causal_depth_score(drivers, full_text),
        "evidence_usefulness": _evidence_usefulness_score(drivers, key_points, full_text),
        "counterargument_coverage": _counterargument_score(full_text, expected, answer),
        "watch_item_coverage": _watch_item_score(full_text, expected, answer),
        "peer_comparability": _peer_comparability_score(full_text, expected),
        "source_boundary": _source_boundary_score(full_text, limitations, expected),
        "memo_structure": _memo_structure_score(full_text, expected, answer),
        "format_polish": _format_polish_score(full_text),
    }
    weighted_total = _weighted_total(scores)
    return {
        "case_id": str(agent.get("case_id") or ""),
        "eval_case_id": str(eval_case.get("case_id") or ""),
        "query": str(case.get("prompt") or case.get("query") or ""),
        "status": agent.get("status"),
        "answer_status": agent.get("answer_status"),
        "score_total": weighted_total,
        "scores": scores,
        "diagnostics": {
            "summary_sentence_count": _sentence_count(summary),
            "driver_count": len(drivers),
            "key_point_count": len(key_points),
            "limitation_count": len(limitations),
            "matched_required_sections": _matched_sections(full_text, expected, answer),
            "missing_required_sections": _missing_sections(full_text, expected, answer),
            "audit_artifact_signal": _contains_any(full_text, AUDIT_ARTIFACT_TERMS),
        },
        "recommendations": _recommendations(scores),
    }


def _thesis_score(summary: str, full_text: str) -> float:
    text = f"{summary} {full_text[:800]}"
    score = 0.0
    if _sentence_count(summary) >= 3:
        score += 0.3
    elif _sentence_count(summary) >= 2:
        score += 0.18
    if _contains_any(text, THESIS_TERMS):
        score += 0.25
    if _contains_any(text, CAUSAL_TERMS):
        score += 0.2
    if _contains_any(text, SO_WHAT_TERMS):
        score += 0.2
    if not _contains_any(summary, AUDIT_ARTIFACT_TERMS):
        score += 0.05
    return round(min(score, 1.0), 4)


def _causal_depth_score(drivers: list[dict[str, Any]], full_text: str) -> float:
    if not drivers:
        return 0.0
    local_scores = []
    for driver in drivers:
        text = " ".join(str(driver.get(key) or "") for key in ("driver_claim", "why_it_matters", "caveat"))
        score = 0.0
        if len(str(driver.get("why_it_matters") or "")) >= 50:
            score += 0.25
        if _contains_any(text, CAUSAL_TERMS):
            score += 0.25
        if _contains_any(text, SO_WHAT_TERMS):
            score += 0.25
        if re.search(r"如果|unless|weaken|削弱|放缓|下滑|无法|不能", text, re.I):
            score += 0.25
        local_scores.append(score)
    count_multiplier = 1.0 if len(drivers) >= 4 else 0.8 if len(drivers) == 3 else 0.6
    text_bonus = 0.05 if re.search(r"二阶|误判|可持续|回报|周期|护城河|竞争格局", full_text) else 0.0
    return round(min((sum(local_scores) / len(local_scores)) * count_multiplier + text_bonus, 1.0), 4)


def _evidence_usefulness_score(drivers: list[dict[str, Any]], key_points: list[dict[str, Any]], full_text: str) -> float:
    units = drivers + key_points
    if not units:
        return 0.0
    bound = 0
    for item in units:
        metric_ids = item.get("supporting_metric_ids") or item.get("metric_ids") or []
        evidence_ids = item.get("supporting_evidence_ids") or item.get("evidence_ids") or []
        if metric_ids or evidence_ids:
            bound += 1
    score = 0.55 * (bound / len(units))
    if _contains_any(full_text, EVIDENCE_TERMS):
        score += 0.2
    if re.search(r"管理层|MD&A|Item 7|risk factors|Item 1A|SEC 文件", full_text, re.I):
        score += 0.15
    if re.search(r"不包含|缺乏|未覆盖|无法", full_text):
        score += 0.1
    return round(min(score, 1.0), 4)


def _counterargument_score(full_text: str, expected: dict[str, Any], answer: dict[str, Any]) -> float:
    counter_rows = [row for row in answer.get("counterarguments") or [] if isinstance(row, dict)]
    if counter_rows:
        with_text = sum(
            bool(str(row.get("claim") or "").strip() and str(row.get("why_it_could_weaken_thesis") or "").strip())
            for row in counter_rows
        )
        evidence_bound = sum(bool(row.get("metric_ids") or row.get("evidence_ids")) for row in counter_rows)
        count_score = min(len(counter_rows) / 2, 1.0) * 0.35
        text_score = (with_text / max(len(counter_rows), 1)) * 0.35
        evidence_score = (evidence_bound / max(len(counter_rows), 1)) * 0.2
        term_score = 0.1 if re.search(r"削弱|推翻|反证|风险|weaken|counter", full_text, re.I) else 0.0
        return round(min(count_score + text_score + evidence_score + term_score, 1.0), 4)
    groups = expected.get("counterargument_terms") or []
    explicit = re.search(r"反证|反例|counter|相反证据|削弱条件|推翻|另一方面", full_text, re.I) is not None
    if not groups:
        if explicit:
            return 0.8
        return 0.45 if re.search(r"但是|风险|如果|无法|不能|口径|可比", full_text) else 0.2
    matched = _matched_term_groups(full_text, groups)
    base = matched / max(len(groups), 1)
    explicit_bonus = 0.35 if explicit else 0.0
    implicit_cap = 0.55 if not explicit else 1.0
    return round(min(0.65 * base + explicit_bonus, implicit_cap), 4)


def _watch_item_score(full_text: str, expected: dict[str, Any], answer: dict[str, Any]) -> float:
    watch_rows = [row for row in answer.get("watch_items") or [] if isinstance(row, dict)]
    if watch_rows:
        with_item = sum(bool(str(row.get("item") or "").strip()) for row in watch_rows)
        with_why = sum(bool(str(row.get("why_it_matters") or "").strip()) for row in watch_rows)
        with_source = sum(bool(str(row.get("source_to_watch") or "").strip()) for row in watch_rows)
        return round(
            min(
                min(len(watch_rows) / 3, 1.0) * 0.3
                + (with_item / max(len(watch_rows), 1)) * 0.25
                + (with_why / max(len(watch_rows), 1)) * 0.25
                + (with_source / max(len(watch_rows), 1)) * 0.2,
                1.0,
            ),
            4,
        )
    groups = expected.get("watch_item_terms") or []
    explicit = re.search(r"后续关注|观察指标|跟踪指标|需要关注|应关注|watch item|should monitor|monitoring", full_text, re.I) is not None
    if not groups:
        return 0.8 if explicit else 0.2
    matched = _matched_term_groups(full_text, groups)
    base = matched / max(len(groups), 1)
    if not explicit:
        return round(min(0.35 * base, 0.35), 4)
    return round(min(0.7 * base + 0.3, 1.0), 4)


def _peer_comparability_score(full_text: str, expected: dict[str, Any]) -> float:
    peers = expected.get("peer_tickers_any_of") or []
    if not peers:
        return 1.0
    peer_hits = sum(1 for peer in peers if str(peer).lower() in full_text.lower())
    score = min(peer_hits / max(min(len(peers), 3), 1), 1.0) * 0.45
    if re.search(r"口径|可比|proxy|代理|segment|直接比较|横向排名", full_text, re.I):
        score += 0.25
    if re.search(r"直接|间接|ASIC|GPU|CPU|cloud|云服务商|网络|foundry|角色|类别", full_text, re.I):
        score += 0.3
    return round(min(score, 1.0), 4)


def _source_boundary_score(full_text: str, limitations: list[str], expected: dict[str, Any]) -> float:
    score = 0.0
    if re.search(r"SEC|10-K|Item|MD&A", full_text, re.I):
        score += 0.35
    if re.search(r"不包含|缺乏|无法|边界|only|source", full_text, re.I):
        score += 0.25
    if limitations:
        score += 0.2
    disallowed = [str(term) for term in expected.get("disallowed_sources") or []]
    violated = [term for term in disallowed if re.search(rf"\b{re.escape(term)}\b", full_text, re.I) and not re.search(rf"不包含|不得|不能|无法使用|without[^。；\n]*{re.escape(term)}", full_text, re.I)]
    if not violated:
        score += 0.2
    return round(min(score, 1.0), 4)


def _memo_structure_score(full_text: str, expected: dict[str, Any], answer: dict[str, Any]) -> float:
    required = expected.get("required_memo_sections") or []
    if not required:
        return 0.6
    matched = len(_matched_sections(full_text, expected, answer))
    return round(matched / max(len(required), 1), 4)


def _format_polish_score(full_text: str) -> float:
    score = 1.0
    if _contains_any(full_text, AUDIT_ARTIFACT_TERMS):
        score -= 0.35
    if len(re.findall(r"metric_ids|evidence_ids|supporting_metric_ids", full_text)) >= 3:
        score -= 0.2
    if re.search(r"当前引用未保留|相关命名标签|未授权", full_text):
        score -= 0.2
    return round(max(score, 0.0), 4)


def _weighted_total(scores: dict[str, float]) -> float:
    weights = {
        "thesis_clarity": 0.15,
        "causal_depth": 0.16,
        "evidence_usefulness": 0.14,
        "counterargument_coverage": 0.14,
        "watch_item_coverage": 0.12,
        "peer_comparability": 0.1,
        "source_boundary": 0.09,
        "memo_structure": 0.06,
        "format_polish": 0.04,
    }
    return round(sum(scores[key] * weight for key, weight in weights.items()), 4)


def _matched_sections(full_text: str, expected: dict[str, Any], answer: dict[str, Any] | None = None) -> list[str]:
    matched = []
    answer = answer or {}
    field_presence = {
        "direct_answer": bool(str(answer.get("direct_answer") or "").strip()),
        "investment_thesis": bool(str(answer.get("investment_thesis") or "").strip()),
        "what_changed": bool(answer.get("what_changed")),
        "why_it_matters": bool(answer.get("why_it_matters")),
        "peer_readthrough": bool(answer.get("peer_readthrough")),
        "counterarguments": bool(answer.get("counterarguments")),
        "watch_items": bool(answer.get("watch_items")),
        "source_limitations": bool(answer.get("source_limitations")),
    }
    for section in expected.get("required_memo_sections") or []:
        if field_presence.get(str(section)):
            matched.append(str(section))
            continue
        terms = SECTION_TERMS.get(str(section), (str(section),))
        if _contains_explicit_section(full_text, tuple(terms)):
            matched.append(str(section))
    return matched


def _missing_sections(full_text: str, expected: dict[str, Any], answer: dict[str, Any] | None = None) -> list[str]:
    matched = set(_matched_sections(full_text, expected, answer))
    return [str(section) for section in expected.get("required_memo_sections") or [] if str(section) not in matched]


def _matched_term_groups(full_text: str, groups: list[Any]) -> int:
    hits = 0
    for group in groups:
        terms = [str(item) for item in group] if isinstance(group, list) else [str(group)]
        if _contains_any(full_text, tuple(terms)):
            hits += 1
    return hits


def _recommendations(scores: dict[str, float]) -> list[str]:
    recs = []
    if scores["counterargument_coverage"] < 0.7:
        recs.append("Add explicit counterarguments: what evidence could weaken or reverse the thesis.")
    if scores["watch_item_coverage"] < 0.7:
        recs.append("Add watch items: the next SEC metrics or disclosures that would confirm/deny the thesis.")
    if scores["memo_structure"] < 0.75:
        recs.append("Render the answer as a memo with direct answer, thesis, what changed, why it matters, counterarguments, watch items, and limitations.")
    if scores["evidence_usefulness"] < 0.75:
        recs.append("Separate evidence roles: core facts, management explanation, peer contrast, risk/counterevidence, and missing evidence.")
    return recs


def _answer_text(answer: dict[str, Any]) -> str:
    parts = [
        str(answer.get("summary") or ""),
        str(answer.get("direct_answer") or ""),
        str(answer.get("investment_thesis") or ""),
    ]
    for driver in answer.get("decision_drivers") or []:
        if isinstance(driver, dict):
            parts.extend(str(driver.get(key) or "") for key in ("driver_claim", "why_it_matters", "caveat"))
    for point in answer.get("key_points") or []:
        if isinstance(point, dict):
            parts.append(str(point.get("point") or ""))
    memo_specs = {
        "what_changed": ("claim",),
        "why_it_matters": ("insight", "business_implication"),
        "peer_readthrough": ("peer_or_group", "role", "readthrough", "caveat"),
        "counterarguments": ("claim", "why_it_could_weaken_thesis"),
    }
    for field, keys in memo_specs.items():
        for item in answer.get(field) or []:
            if isinstance(item, dict):
                parts.extend(str(item.get(key) or "") for key in keys)
    for item in answer.get("watch_items") or []:
        if isinstance(item, dict):
            parts.extend(str(item.get(key) or "") for key in ("item", "why_it_matters", "source_to_watch", "metric_family"))
    parts.extend(str(item) for item in answer.get("source_limitations") or [])
    parts.extend(str(item) for item in answer.get("limitations") or [])
    return " ".join(parts)


def _summarize(results: list[dict[str, Any]], pass_threshold: float) -> dict[str, Any]:
    if not results:
        return {"mean_score_total": 0.0, "pass_threshold": pass_threshold, "pass_count": 0, "fail_count": 0}
    dimensions = {}
    for key in (results[0].get("scores") or {}).keys():
        dimensions[key] = round(sum(float((row.get("scores") or {}).get(key) or 0.0) for row in results) / len(results), 4)
    pass_count = sum(float(row.get("score_total") or 0.0) >= pass_threshold for row in results)
    return {
        "mean_score_total": round(sum(float(row.get("score_total") or 0.0) for row in results) / len(results), 4),
        "pass_threshold": pass_threshold,
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "dimension_means": dimensions,
    }


def _sentence_count(text: str) -> int:
    return len([item for item in re.split(r"[。！？!?]\s*|\n+", str(text or "")) if item.strip()])


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(term.lower() in lowered for term in terms)


def _contains_explicit_section(text: str, terms: tuple[str, ...]) -> bool:
    value = str(text or "")
    for term in terms:
        pattern = rf"(?:^|[\n\r。；;])\s*(?:#{1,6}\s*)?{re.escape(term)}\s*(?:[:：]|$)"
        if re.search(pattern, value, re.I):
            return True
    return False


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


if __name__ == "__main__":
    main()
