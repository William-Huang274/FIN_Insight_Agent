"""Prepare a fixed local review deployment, never a paid run or new authority engine."""
import argparse
import json
from copy import deepcopy
from pathlib import Path

from sec_agent.agent_runtime.dell_specialist_paid_shadow import file_sha256
from sec_agent.agent_runtime.dell_report_session import load_session_materials
from sec_agent.agent_runtime.deepseek_structured_agents import TokenBudgetBasis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    previous = json.loads((repo / "configs/research/evals/fin_ia_0_1_3_s3_dell_case_report_revision_a3_authority_v1_0.json").read_text(encoding="utf-8"))
    scope = previous["case_convergence_scope"]
    settings = {"owner_scope": "funded_local_dell_report_review_only", "bundle_path": str(args.bundle.resolve()),
        "report_path": str(args.report.resolve()), "bundle_sha256": file_sha256(args.bundle), "report_sha256": file_sha256(args.report),
        "model_config_path": str(repo / "configs/research/fin_ia_0_1_3_dell_case_convergence_native_v1_0.json"),
        "audit_root": str(args.directory.resolve() / "calls"),
        "node_budgets": {k: deepcopy(scope["node_budgets"][k]) for k in ("writer", "verifier")},
        "node_limits": {k: deepcopy(scope["node_limits"][k]) for k in ("writer", "verifier")}}
    for role, budget in settings["node_budgets"].items():
        budget["node_purpose"] = ("Answer a user question about the current Dell case, or revise the existing Chinese report from explicit human feedback using current papers and original sources. Do not restart whole research." if role == "writer"
            else "Independently review the submitted revision in its source context, return material/advisory findings and indispensable evidence needs; never auto-rewrite until PASS.")
        budget["input_scale"] = "Current10738-character Chinese report, compact10-paper catalog, explicit public conversation/feedback(up to16000characters per request), source/claim details read on demand. No duplicated full citation object and no other agent private context."
        budget["comparable_run_evidence"] = "A3Writer4calls189768tokens/.455598CNY;Verifier2calls158494tokens/.5019282CNY;stillneedsrevision. Retain same16model/48tool700kinput32koutput480s ceilings for genuine tool-based checking; ordinary short answers need not exhaust limits."
        budget["required_outputs"] = (["Cited answer for ask, or revised free Chinese report for revise", "Sources/uncertainty and current periods preserved"] if role == "writer"
            else ["Independent report assessment", "Exact report quotes for actionable findings", "No private writer reasoning or human feedback injected as verdict"])
        TokenBudgetBasis.model_validate_json(json.dumps(budget))
    load_session_materials(settings)
    args.directory.mkdir(parents=True, exist_ok=True)
    # Host and container path mappings only; the old report and once authority are unchanged.
    container = deepcopy(settings)
    container.update(bundle_path="/run/fin-insight/session-bundle.json", report_path="/run/fin-insight/session-report.json",
        model_config_path="/deps/FIN_Insight_Agent/configs/research/fin_ia_0_1_3_dell_case_convergence_native_v1_0.json",
        audit_root="/run/fin-insight/session-calls")
    (args.directory / "calls").mkdir(exist_ok=True)
    for name, value in (("host-settings.json", settings), ("container-settings.json", container)):
        with (args.directory / name).open("x", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
    print(json.dumps({"prepared": str(args.directory), "model_calls": 0, "scope": settings["owner_scope"]}))


if __name__ == "__main__":
    main()
