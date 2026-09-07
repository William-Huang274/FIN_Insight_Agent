"""Mechanical readable export; never edit/translate an agent's original content."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, quote
from urllib.request import ProxyHandler, build_opener


def render_workpaper(submission):
    lines = ["# Agent workpaper — unchanged content", "",
             "Mechanical export. Structural acceptance is not financial or human product acceptance.", ""]
    for field in ("thesis", "mechanism", "narrative_markdown", "counterevidence", "what_would_change", "open_gaps"):
        lines.extend([f"## {field}", ""])
        value = submission.get(field, "")
        lines.extend(value if isinstance(value, list) else [value])
        lines.append("")
    lines.extend(["## claims", ""])
    for claim in submission["claims"]:
        lines.extend([f"### {claim['claim_id']} · {claim['kind']} · {claim['materiality']}", "", claim["statement"], ""])
        for key in ("evidence_ids", "fact_ids", "numeric_authority", "authority_note", "reasoning_summary", "citation_quotes"):
            lines.extend([f"{key}: {json.dumps(claim.get(key), ensure_ascii=False)}", ""])
    return "\n".join(lines)


def render_case_report(state):
    """Mechanical footnotes only; never rewrite the model's financial prose."""
    report = state["report"]
    prose = report["narrative_markdown"]
    refs = sorted(report["citations"], key=lambda ref: prose.find("[" + ref + "]"))
    notes = []
    for index, ref in enumerate(refs, 1):
        prose = prose.replace("[" + ref + "]", f"[^s{index}]")
        citation = report["citations"][ref]
        links = []
        for source in citation["sources"]:
            urls = source.get("citation_urls") or [source.get("source_url")]
            for url in urls:
                if not isinstance(url, str) or urlsplit(url).scheme not in {"http", "https"}:
                    continue
                label = str(source.get("title") or " ".join(str(source.get(k) or "") for k in ("ticker", "metric_id", "period_end")).strip() or source["source_id"])
                label = re.sub(r"[\[\]\r\n]", " ", label)
                link = f"[{label}](<{quote(url, safe=':/?#=&%+@,;~-_') }>)"
                if link not in links:
                    links.append(link)
        note = ("结构化数值来源；推断仍需结合期间、口径与正文。" if all(s.get("numeric_fact_authority") for s in citation["sources"])
            else "包含发行人披露或外部材料；请结合正文的来源与不确定性说明，不自动视作权威数值或独立验证。")
        notes.append(f"[^s{index}]: `{ref}` — {'；'.join(links) or '无可公开链接，见原始引用记录'}。{note}")
    return (f"# {report['title']}\n\n> 运行状态：`{state['phase']}`。这是模型原文的机械导出，引用转为可点击脚注；并非自动发布或人工验收通过。\n\n"
        + prose + "\n\n## 引用与来源\n\n" + "\n\n".join(notes) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--snapshot-url", help="Archive a stopped local Agent Server checkpoint before export.")
    args = parser.parse_args()
    root = args.attempt.resolve(strict=True)
    state_path = root / "specialist-final-state.private.json"
    if args.snapshot_url:
        if not re.fullmatch(r"http://127\.0\.0\.1:\d+/threads/[a-f0-9-]{36}/state", args.snapshot_url):
            parser.error("snapshot URL must be an explicit local Agent Server thread state")
        with build_opener(ProxyHandler({})).open(args.snapshot_url, timeout=30) as response:
            data = json.load(response)
        if not any(task.get("error") for task in data.get("tasks", [])):
            parser.error("snapshot recovery is only for an errored checkpoint")
        with state_path.open("x", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
    else:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    state = data.get("values", data)
    if "report" in state:
        outputs = {"report.agent-original.md": render_case_report(state),
            "report-review.agent-original.json": json.dumps(state["report_review"], ensure_ascii=False, indent=2) + "\n"}
    else:
        outputs = {"workpaper.agent-original.md": render_workpaper(state["final_submission"])}
    if "review_results" in state:
        reviews = [{"role": r["role"], "round": r["round"], "target_digest": r["target_digest"],
                    "review": r["review"]} for r in state["review_results"]]
        outputs["reviews.agent-original.json"] = json.dumps({"phase": state["phase"],
            "review_stop_reason": state.get("review_stop_reason"), "reviews": reviews}, ensure_ascii=False, indent=2) + "\n"
    for filename, content in outputs.items():
        path = root / filename
        # Existing evidence is never overwritten by an export invocation.
        with path.open("x", encoding="utf-8") as handle:
            handle.write(content)
        print(str(path))


if __name__ == "__main__":
    main()
