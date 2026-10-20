"""Recompute the October qualification tables from retained local raw samples.

No services or providers are called. This deliberately names the accepted batch
directories so diagnostic runs cannot silently replace the comparison baseline.
"""
import argparse
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path

from scripts.engineering.qualification_load import distribution
from scripts.engineering.qualify_retrieval_recall import ranking_metrics, rrf


def summarize(root):
    inputs = {}
    def read(name):
        raw = (root / name).read_bytes()
        inputs[name] = sha256(raw).hexdigest()
        return json.loads(raw)

    result = {"meaning": "Local closed-loop engineering qualification, not production capacity",
              "research": [], "organization_reads": {}, "public_reads": []}
    for level in (1, 4, 8):
        run = read(f"multiuser-r3/load-{level}.json")
        result["research"].append({
            "concurrency": level,
            **{k: run[k] for k in ("requested", "completed", "correct", "failed", "not_started",
                                   "elapsed_seconds", "correct_per_second", "all_terminal_latency")},
            "accepted_latency": distribution([s["result"]["accepted_ms"] for s in run["samples"]
                                               if s["result"]["ok"]]),
        })
        public = read(f"public-reads-r1/load-{level}.json")
        result["public_reads"].append({k: public[k] for k in (
            "concurrency", "requested", "correct", "failed", "not_started", "stage_latency")})
    for batch in ("r1", "r2"):
        result["organization_reads"][batch] = []
        for level in (1, 4, 8):
            run = read(f"organization-retrieval-load-{batch}/retrieval-load-{level}.json")
            result["organization_reads"][batch].append({k: run[k] for k in (
                "concurrency", "requested", "correct", "failed", "not_started",
                "correct_per_second", "all_terminal_latency", "stage_latency")})
    before = result["organization_reads"]["r1"][-1]["all_terminal_latency"]["p95_ms"]
    after = result["organization_reads"]["r2"][-1]["all_terminal_latency"]["p95_ms"]
    result["organization_eight_concurrent_p95_reduction"] = 1 - after / before

    dataset = read("recall-design/questions-v2.json")
    by_id = {q["id"]: q for q in dataset["questions"]}
    result["recall"] = {}
    for label in ("development", "heldout", "development-selected_document", "heldout-selected_document"):
        rows = read(f"recall-r1/{label}.samples.json")
        strata = defaultdict(list)
        failed = []
        for sample in rows:
            if sample["status"] != "completed":
                raise ValueError("incomplete_recall_batch")
            gold = [e["chunk_id"] for e in by_id[sample["id"]]["evidence"]]
            # Use the shared runtime quotas, not the exploratory 40+40 run.
            ranks = sample["rankings"]
            metrics = {
                "lexical": ranking_metrics(ranks["lexical"], gold),
                "dense": ranking_metrics(ranks["dense"], gold),
                "rrf": ranking_metrics(rrf([ranks["dense"][:24], ranks["lexical"][:12]]), gold)}
            strata["all"].append(metrics)
            strata[sample["language"]].append(metrics)
            if not metrics["rrf"]["known_hit@10"]:
                failed.append(sample["id"])
        result["recall"][label] = {
            "questions": len(rows), "families": len({s["family"] for s in rows}),
            "metrics_by_language": {name: {
                channel: {metric: sum(s[channel][metric] for s in samples)/len(samples)
                          for metric in samples[0][channel]}
                for channel in ("lexical", "dense", "rrf")}
                for name, samples in strata.items()},
            "rrf_missing_known_evidence_at_10": failed}
    supplemental = read("multi-evidence-r1/heldout-selected_document.summary.json")
    questions = read("recall-design/multi-evidence-v1.json")["questions"]
    supplemental["sources"] = len({e["source_id"] for q in questions for e in q["evidence"]})
    supplemental["split_meaning"] = "Supplemental diagnostic; shares evidence with main set, not independent heldout"
    result["multi_evidence"] = supplemental
    result["input_sha256"] = inputs
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    result = summarize(args.root)
    target = args.root / "final-measurements.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
    print(json.dumps({"output": str(target), "sha256": sha256(target.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
