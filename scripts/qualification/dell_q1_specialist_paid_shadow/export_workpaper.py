"""Mechanical readable export; never edit/translate an agent's original content."""
import argparse
import json
from pathlib import Path
import re
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
