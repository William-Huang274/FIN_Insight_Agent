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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--accepted-revisions", type=Path, help="Host-revalidated native submissions to reuse without new model calls.")
    args = parser.parse_args()
    result = prepare()
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
