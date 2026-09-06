"""Collect public review feedback for six responsible authors; no model calls.

Copies archived research and submitted review outputs, never provider transcripts.
Human supplementary findings are explicit and not mislabeled independent/blind.
"""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from sec_agent.agent_runtime.dell_case_artifacts import DellCaseArtifacts
from sec_agent.agent_runtime.dell_case_review_agent import CaseReview

BASE = Path("Z:/FIN_Insight_Agent_qualification/dell_reference_vertical")
BUNDLE = BASE / "case-convergence-20260906-a1/research-bundle.private.json"
REVIEW = BASE / "q1_specialist_paid_shadow/attempts/20260906-dell-case-native-review-a1/specialist-final-state.private.json"


def prepare():
    seed = json.loads(BUNDLE.read_text(encoding="utf-8"))
    state = json.loads(REVIEW.read_text(encoding="utf-8"))["values"]
    if state["phase"] != "case_review_ready_for_convergence":
        raise ValueError("case_review_not_submitted")
    artifacts = DellCaseArtifacts(seed["papers"])
    feedback = {}
    for actor in ("counter", "verifier"):
        review = CaseReview.model_validate(state[actor]["review"])
        for finding in review.findings:
            row = finding.model_dump(mode="json")
            row["finding_id"] = actor + ":" + row["finding_id"]
            row["origin"] = "independent_case_review_A1:" + actor
            feedback.setdefault(finding.paper_id, []).append(row)
    feedback.setdefault("P08", []).append({"finding_id": "human:orders_are_not_observed_usage",
        "paper_id": "P08", "origin": "explicit_host_assisted_followup_not_blind_review", "severity": "material",
        "claim_ids": ["C10"], "problematic_quote": artifacts.read_paper("P08")["thesis"],
        "diagnosis": "订单、收入和积压是采购/交付/财务需求代理量，不是已部署设备的实际利用率或算力使用量。前审也混淆了这一点。效率提高同时可能减少每任务所需资源并刺激任务量，现有样本不能证明前者不存在或净增量必然为正。",
        "requested_change": "自行重读来源并改正文、C10及受影响推理：区分采购需求、交付、工作负载与实际利用率；保留有证据的需求增长判断，但不把订单当实际使用、不把未观测到需求下降说成效率绝无负向替代作用。说明净弹性未被识别，可反对本反馈但须以原源说明。", "source_checks": []})
    feedback["P06"].append({"finding_id": "human:aggregate_bound_materiality",
        "paper_id": "P06", "origin": "explicit_host_assisted_followup_not_blind_review", "severity": "material",
        "claim_ids": ["Q7_C7_GREATER_CHINA_INFERENCE"],
        "problematic_quote": next(c["statement"] for c in artifacts.read_paper("P06", "claims") if c["claim_id"] == "Q7_C7_GREATER_CHINA_INFERENCE"),
        "diagnosis": "单一国家披露不构成Greater China多地域合计的10%上限；即使标为推断也不能修复逻辑错误。该值若作为出口管制风险敞口上限，可能实质误导。",
        "requested_change": "处理Verifier的地域聚合意见并同步修改正文，不能以10%作为Greater China风险上限。保留已经核到的规则版本与生效日，但有限网页采集不保证截至研究日规则完整；不得由旧条文自行宣称最新法律状态。", "source_checks": []})
    if set(feedback) != {"P01", "P04", "P05", "P06", "P07", "P08"}:
        raise ValueError("unexpected_responsible_paper_set")
    return {**seed, "feedback": feedback, "review_outputs": {r: state[r]["review"] for r in ("counter", "verifier")},
        "convergence_origins": [{"path": str(p), "sha256": sha256(p.read_bytes()).hexdigest()} for p in (BUNDLE, REVIEW)],
        "host_assisted": True, "financial_or_product_pass": False}


def prepare_report_revision(state_path, human_review_path):
    """Reuse completed native outputs; feedback is public, not private history."""
    from langchain_core.messages import ToolMessage
    from sec_agent.agent_runtime.dell_case_convergence_agent import (
        CaseReport, ReportReview, PaperRevision, validated_revision, validate_reused_revisions,
    )
    seed = prepare()
    envelope = json.loads(state_path.read_text(encoding="utf-8"))
    state = envelope["values"]
    if state["phase"] not in {"case_report_needs_revision", "case_report_ready_for_human_review"}:
        raise ValueError("report_revision_requires_finished_report_handoff")
    report = CaseReport.model_validate({k: state["report"][k] for k in ("title", "narrative_markdown")})
    review = ReportReview.model_validate(state["report_review"])
    audit_path = state_path.parent / "model-context-reasoning.private.jsonl"
    events = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    receipt_path = state_path.parent / "terminal-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    artifacts = DellCaseArtifacts(seed["papers"])
    saved = {}
    for pid, output in state["revisions"].items():
        actor = "author_" + pid
        origin = state["actor_metrics"][actor].get("reused_from")
        if not origin:
            request = next(r for r in reversed(events) if r.get("actor") == actor and r.get("event") == "request")
            response = next(r for r in reversed(events) if r.get("actor") == actor and r.get("event") == "response")
            call = next(c for c in response["raw_response"]["tool_calls"] if c["name"] == "submit_paper_revision")
            observed = [ToolMessage.model_validate(m) for m in request["messages"] if m.get("type") == "tool"]
            check = validated_revision(PaperRevision.model_validate(call["args"]["revision"]), paper_id=pid,
                feedback=seed["feedback"][pid], artifacts=artifacts, messages=observed)
            if check != output:
                raise ValueError("saved_report_author_submission_mismatch")
            origin = {"execution_id": state_path.parent.name, "server_thread_id": receipt["identity"]["server_thread_id"],
                "server_run_id": receipt["identity"]["server_run_id"], "checkpoint_ns": envelope["checkpoint"]["checkpoint_ns"],
                "checkpoint_id": envelope["checkpoint"]["checkpoint_id"], "state_key": "revisions." + pid,
                "native_submission_revalidated": True}
        saved[pid] = {"output": output, "origin": origin}
    seed["accepted_revisions"] = validate_reused_revisions(saved, artifacts, seed["feedback"])
    seed["report_revision_request"] = {"prior_report": report.model_dump(mode="json"),
        "independent_review": review.model_dump(mode="json"),
        "human_review": json.loads(human_review_path.read_text(encoding="utf-8")),
        "notice": "Public review feedback is not source truth or blind gold. Recheck sources; preserve original report and failures."}
    seed["convergence_origins"].extend({"path": str(p), "sha256": sha256(p.read_bytes()).hexdigest()}
        for p in (state_path, human_review_path))
    return seed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--accepted-revisions", type=Path, help="Host-revalidated native submissions to reuse without new model calls.")
    parser.add_argument("--report-state", type=Path, help="Finished report handoff to revise; reuses every author output.")
    parser.add_argument("--human-review", type=Path, help="Explicitly labeled public human feedback, not blind gold.")
    args = parser.parse_args()
    if bool(args.report_state) != bool(args.human_review) or (args.report_state and args.accepted_revisions):
        parser.error("report-state and human-review must be paired; do not also supply accepted-revisions")
    result = prepare_report_revision(args.report_state, args.human_review) if args.report_state else prepare()
    if args.accepted_revisions:
        from sec_agent.agent_runtime.dell_case_convergence_agent import validate_reused_revisions
        result["accepted_revisions"] = validate_reused_revisions(
            json.loads(args.accepted_revisions.read_text(encoding="utf-8")), DellCaseArtifacts(result["papers"]), result["feedback"])
        result["convergence_origins"].append({"path": str(args.accepted_revisions),
            "sha256": sha256(args.accepted_revisions.read_bytes()).hexdigest()})
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"output": str(args.output), "papers": len(result["papers"]),
        "responsible_revisions": sorted(result["feedback"]), "host_assisted": True,
        "sha256": sha256(args.output.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
