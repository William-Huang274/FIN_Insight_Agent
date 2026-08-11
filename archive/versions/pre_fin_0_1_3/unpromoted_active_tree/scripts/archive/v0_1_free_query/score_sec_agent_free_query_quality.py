from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


CAUSAL_TERMS = (
    "因为",
    "由于",
    "驱动",
    "反映",
    "说明",
    "意味着",
    "导致",
    "支撑",
    "源于",
    "受益于",
    "why",
    "because",
    "driven",
    "reflect",
    "imply",
)
SO_WHAT_TERMS = (
    "增长质量",
    "竞争",
    "优势",
    "可持续",
    "现金流",
    "定价",
    "规模效应",
    "护城河",
    "风险",
    "削弱",
    "边界",
    "so what",
    "sustain",
    "durability",
    "advantage",
)
PEER_ROLE_TERMS = (
    "gpu",
    "加速器",
    "accelerator",
    "asic",
    "网络",
    "networking",
    "semiconductor solutions",
    "半导体解决方案",
    "cpu",
    "foundry",
    "制造",
    "平台",
)
LEDGER_DUMP_TERMS = (
    "INTERACTIVE_",
    "metric_id",
    "total_value::",
    "percentage_rate::",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score free-query SEC agent output for insight quality.")
    parser.add_argument("--run-dir", required=True, help="Interactive run directory containing qwen/agent_outputs.jsonl.")
    parser.add_argument("--output-path", default="", help="Optional JSON report path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_dir = _resolve(args.run_dir)
    rows = _read_jsonl(run_dir / "qwen" / "agent_outputs.jsonl")
    results = [_score_agent_row(row, run_dir) for row in rows]
    summary = _summarize(results)
    report = {
        "schema_version": "sec_agent_free_query_quality_v0.1",
        "run_dir": str(run_dir),
        "case_count": len(results),
        "summary": summary,
        "case_results": results,
    }
    output_path = _resolve(args.output_path) if args.output_path else run_dir / "free_query_quality_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_path": str(output_path), **summary}, ensure_ascii=False, indent=2))


def _score_agent_row(agent: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    answer = agent.get("answer") if isinstance(agent.get("answer"), dict) else {}
    case = _load_case(run_dir, str(agent.get("case_id") or ""))
    prompt = str(case.get("prompt") or "")
    summary = str(answer.get("summary") or "")
    drivers = [item for item in answer.get("decision_drivers") or [] if isinstance(item, dict)]
    key_points = [item for item in answer.get("key_points") or [] if isinstance(item, dict)]
    limitations = [str(item) for item in answer.get("limitations") or []]
    full_text = _answer_text(answer)

    scores = {
        "summary_thesis": _summary_thesis_score(summary),
        "driver_depth": _driver_depth_score(drivers),
        "evidence_binding": _evidence_binding_score(drivers, key_points),
        "peer_role_coverage": _peer_role_score(prompt, full_text),
        "caveat_quality": _caveat_score(limitations, drivers),
        "format_polish": _format_polish_score(full_text),
    }
    total = round(sum(scores.values()) / max(len(scores), 1), 4)
    return {
        "case_id": str(agent.get("case_id") or ""),
        "status": agent.get("status"),
        "answer_status": agent.get("answer_status"),
        "score_total": total,
        "scores": scores,
        "diagnostics": {
            "summary_sentence_count": _sentence_count(summary),
            "driver_count": len(drivers),
            "key_point_count": len(key_points),
            "mentions_peer_prompt": _is_peer_prompt(prompt),
            "ledger_dump_signal": _contains_any(full_text, LEDGER_DUMP_TERMS),
            "exact_value_count": len(re.findall(r"\d[\d,]*(?:\.\d+)?\s*(?:（(?:百万美元|十亿美元|千美元)）|%)", full_text)),
        },
        "recommendations": _recommendations(scores, prompt),
    }


def _summary_thesis_score(summary: str) -> float:
    if not summary.strip():
        return 0.0
    sentence_count = _sentence_count(summary)
    has_causal = _contains_any(summary, CAUSAL_TERMS)
    has_so_what = _contains_any(summary, SO_WHAT_TERMS)
    no_exact_values = not re.search(r"\d[\d,]*(?:\.\d+)?\s*(?:（(?:百万美元|十亿美元|千美元)）|%)", summary)
    score = 0.15
    if sentence_count >= 3:
        score += 0.3
    elif sentence_count >= 2:
        score += 0.18
    if has_causal:
        score += 0.2
    if has_so_what:
        score += 0.2
    if no_exact_values:
        score += 0.15
    return min(score, 1.0)


def _driver_depth_score(drivers: list[dict[str, Any]]) -> float:
    if not drivers:
        return 0.0
    scored = []
    for driver in drivers:
        claim = str(driver.get("driver_claim") or "")
        why = str(driver.get("why_it_matters") or "")
        caveat = str(driver.get("caveat") or "")
        local = 0.0
        if len(claim) >= 18:
            local += 0.18
        if len(why) >= 30:
            local += 0.2
        if _contains_any(f"{claim} {why}", CAUSAL_TERMS):
            local += 0.22
        if _contains_any(why, SO_WHAT_TERMS):
            local += 0.22
        if caveat and _contains_any(caveat, ("风险", "口径", "边界", "不足", "weaken", "proxy", "comparable")):
            local += 0.18
        scored.append(min(local, 1.0))
    count_bonus = 1.0 if len(drivers) >= 4 else 0.75 if len(drivers) == 3 else 0.55
    return round((sum(scored) / len(scored)) * count_bonus, 4)


def _evidence_binding_score(drivers: list[dict[str, Any]], key_points: list[dict[str, Any]]) -> float:
    units = drivers + key_points
    if not units:
        return 0.0
    bound = 0
    for item in units:
        metric_ids = item.get("supporting_metric_ids") or item.get("metric_ids") or []
        evidence_ids = item.get("supporting_evidence_ids") or item.get("evidence_ids") or []
        if metric_ids or evidence_ids:
            bound += 1
    return round(bound / len(units), 4)


def _peer_role_score(prompt: str, text: str) -> float:
    if not _is_peer_prompt(prompt):
        return 1.0
    mentioned_companies = sum(1 for term in ("AMD", "AVGO", "INTC", "Intel", "Broadcom", "QCOM", "AMAT", "MU") if term.lower() in text.lower())
    roles = sum(1 for term in PEER_ROLE_TERMS if term.lower() in text.lower())
    score = 0.0
    if mentioned_companies >= 3:
        score += 0.35
    elif mentioned_companies >= 2:
        score += 0.22
    elif mentioned_companies >= 1:
        score += 0.1
    if roles >= 4:
        score += 0.45
    elif roles >= 2:
        score += 0.3
    elif roles >= 1:
        score += 0.15
    if re.search(r"直接|direct|不同|差异|口径|proxy|代理|角色", text, re.I):
        score += 0.2
    return min(round(score, 4), 1.0)


def _caveat_score(limitations: list[str], drivers: list[dict[str, Any]]) -> float:
    text = " ".join([*limitations, *(str(driver.get("caveat") or "") for driver in drivers)])
    if not text.strip():
        return 0.0
    score = 0.0
    if re.search(r"SEC|10-K|10-Q|8-K|source|来源|证据", text, re.I):
        score += 0.3
    if re.search(r"口径|可比|proxy|代理|segment|definition|直接比较", text, re.I):
        score += 0.3
    if re.search(r"风险|不足|未涵盖|不完整|边界|weaken|降级", text, re.I):
        score += 0.25
    if len(limitations) <= 8:
        score += 0.15
    return min(round(score, 4), 1.0)


def _format_polish_score(text: str) -> float:
    score = 1.0
    if _contains_any(text, LEDGER_DUMP_TERMS):
        score -= 0.35
    if "相关命名标签" in text or "未在 Exact-Value Ledger 中授权" in text:
        score -= 0.25
    if re.search(r"\(\([^)]*（(?:百万美元|十亿美元|千美元)）\)（(?:百万美元|十亿美元|千美元)）", text):
        score -= 0.2
    if len(re.findall(r"必要限制：", text)) >= 2:
        score -= 0.15
    return max(round(score, 4), 0.0)


def _recommendations(scores: dict[str, float], prompt: str) -> list[str]:
    recs = []
    if scores["summary_thesis"] < 0.75:
        recs.append("Strengthen summary thesis: add causal interpretation, so-what, and evidence boundary without exact values.")
    if scores["driver_depth"] < 0.75:
        recs.append("Driver text is still too descriptive; require causal read, business implication, and weakening condition.")
    if _is_peer_prompt(prompt) and scores["peer_role_coverage"] < 0.75:
        recs.append("Peer answer should distinguish competitor roles, not only list company names.")
    if scores["format_polish"] < 0.9:
        recs.append("Renderer/prompt should suppress audit artifacts and clean negative proxy value formatting.")
    return recs


def _is_peer_prompt(prompt: str) -> bool:
    return re.search(r"竞争|对手|同行|peer|competitor|compare|comparison|对比|比较", prompt, re.I) is not None


def _answer_text(answer: dict[str, Any]) -> str:
    parts = [str(answer.get("summary") or "")]
    for driver in answer.get("decision_drivers") or []:
        if isinstance(driver, dict):
            parts.extend(str(driver.get(key) or "") for key in ("driver_claim", "why_it_matters", "caveat"))
    for point in answer.get("key_points") or []:
        if isinstance(point, dict):
            parts.append(str(point.get("point") or ""))
    parts.extend(str(item) for item in answer.get("limitations") or [])
    return " ".join(parts)


def _sentence_count(text: str) -> int:
    chunks = [item.strip() for item in re.split(r"[。！？!?]\s*|\n+", str(text or "")) if item.strip()]
    return len(chunks)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = str(text or "").lower()
    return any(term.lower() in lowered for term in terms)


def _load_case(run_dir: Path, case_id: str) -> dict[str, Any]:
    path = run_dir / "case.jsonl"
    for row in _read_jsonl(path):
        if str(row.get("case_id") or "") == case_id:
            return row
    return {}


def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"mean_score_total": 0.0, "pass_count": 0, "fail_count": 0}
    mean = round(sum(float(row.get("score_total") or 0.0) for row in results) / len(results), 4)
    pass_count = sum(float(row.get("score_total") or 0.0) >= 0.75 for row in results)
    dimensions = {}
    for key in (results[0].get("scores") or {}).keys():
        dimensions[key] = round(sum(float((row.get("scores") or {}).get(key) or 0.0) for row in results) / len(results), 4)
    return {
        "mean_score_total": mean,
        "pass_threshold": 0.75,
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "dimension_means": dimensions,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else REPO_ROOT / value


if __name__ == "__main__":
    main()
