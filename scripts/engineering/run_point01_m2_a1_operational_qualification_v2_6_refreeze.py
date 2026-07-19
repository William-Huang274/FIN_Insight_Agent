"""Freeze B0.3's approval-driven JIT entry without issuing authority."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
OLD_PACKAGE_PATH = "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_5.json"
OLD_PACKAGE_DIGEST = "a23dac3931164b4910a6182b97fa37e10d788e893991e4bc1d079e78439ebe6a"
OLD_BLUEPRINT_DIGEST = "9d2ae58f371d57bd4e827eda398933623886f74126a015ee6a7a167a41ea3020"
PACKAGE_REF = "point01-m2-a1-operational-qualification-adversarial-audit-package-v2-6-frozen-jit-entry"
NAMESPACE_ID = "point01_m2_a1_exact_admitted_runs_v2_6"
NAMESPACE_PATH = "D:/temp/FIN_Insight_Agent/point01_m2_a1_exact_admitted_runs_v2_6"
BASELINE = "p01-baseline-separated-input"
FIXED_SHA256 = "ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4"
POLICY = "configs/engineering_handoff/point01_m2_a1_frozen_jit_window_policy_v2_6.json"
OUTPUTS = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_6.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_6.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_3_frozen_jit.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_3_frozen_jit_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_3_frozen_jit.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_3_frozen_jit_gate.json",
}
REPLACED = {
    "scripts/engineering/run_point01_m2_a1_actual_audit_v2_5.py": "scripts/engineering/run_point01_m2_a1_actual_audit_v2_6.py",
    "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_5.py": "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_6.py",
    "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_5.py": "scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_6.py",
    "scripts/engineering/run_point01_m2_a1_v2_5_baseline_jit_window.py": "scripts/engineering/run_point01_m2_a1_v2_6_frozen_jit_window.py",
    "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_5_refreeze.py": "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_6_refreeze.py",
}
NEW_INPUTS = {"src/sec_agent/canonical_runtime/m2_a1_frozen_jit.py", POLICY, "tests/contract/test_point01_m2_a1_v2_6_frozen_jit.py"}


def canonical(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def staged_bytes(path: str) -> bytes:
    result = subprocess.run(["git", "show", f":{path}"], cwd=ROOT, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(f"v2_6_refreeze_index_input_missing:{path}")
    return result.stdout


def staged_json(path: str) -> dict[str, Any]:
    value = json.loads(staged_bytes(path).decode("utf-8"))
    if not isinstance(value, dict): raise RuntimeError("v2_6_refreeze_mapping_required")
    return value


def sha(path: str) -> str:
    return hashlib.sha256(staged_bytes(path)).hexdigest()


def write(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def templates() -> dict[str, Any]:
    unresolved = "unresolved_not_active"
    approval_fields = ("approval_ref", "approval_id", "approval_version", "reviewer_identity", "decision", "issued_at", "expires_at", "package_ref", "package_digest", "package_gate_digest", "plan_digest", "plan_gate_digest", "blueprint_digest", "blueprint_gate_digest", "phase_a_digests", "incident_digest", "expired_terminal_digest", "scenario_id", "input_ref", "mutation", "authority_boundary", "execution_staging_namespace_id", "admission_ttl_minutes", "receipt_ttl_minutes", "single_use", "no_retry_replay_or_renewal", "approval_digest")
    return {"human_jit_window_approval": {"schema_version": "finsight_point01_m2_a1_human_jit_window_approval_v1", "fields": {name: unresolved for name in approval_fields}}, "orchestrator": {"path": "scripts/engineering/run_point01_m2_a1_v2_6_frozen_jit_window.py", "command": "do_not_invoke"}}


def build_package() -> dict[str, Any]:
    old = staged_json(OLD_PACKAGE_PATH)
    if old.get("package_digest") != OLD_PACKAGE_DIGEST: raise RuntimeError("v2_6_refreeze_old_package_mismatch")
    paths = set(old["input_file_sha256"]); paths.difference_update(REPLACED); paths.update(REPLACED.values()); paths.update(NEW_INPUTS)
    hashes = {path: sha(path) for path in sorted(paths)}
    payload = {**{key: value for key, value in old.items() if key not in {"package_digest", "schema_version", "package_ref", "input_file_sha256", "execution_preflight", "transport_isolation", "supersedes", "jit_window_contract"}},
        "schema_version": "finsight_point01_m2_a1_execution_ready_audit_package_manifest_v2_6", "package_ref": PACKAGE_REF, "input_file_sha256": hashes,
        "execution_preflight": {**old["execution_preflight"], "execution_staging_namespace_id": NAMESPACE_ID, "execution_staging_namespace_path": NAMESPACE_PATH},
        "transport_isolation": {**{key:value for key,value in old["transport_isolation"].items() if key != "runtime_hash_bindings"}, "runtime_hash_bindings": {
            "parent_runner":{"relative_path":REPLACED["scripts/engineering/run_point01_m2_a1_actual_audit_v2_5.py"],"sha256":hashes[REPLACED["scripts/engineering/run_point01_m2_a1_actual_audit_v2_5.py"]]}, "clean_child":{"relative_path":REPLACED["scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_5.py"],"sha256":hashes[REPLACED["scripts/engineering/run_point01_m2_a1_actual_audit_clean_child_v2_5.py"]]}, "canary":{"relative_path":"src/sec_agent/canonical_runtime/m2_a1_audit_canary.py","sha256":hashes["src/sec_agent/canonical_runtime/m2_a1_audit_canary.py"]}, "registrar":{"relative_path":REPLACED["scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_5.py"],"sha256":hashes[REPLACED["scripts/engineering/run_point01_m2_a1_receipt_registrar_v2_5.py"]]}, "jit_orchestrator":{"relative_path":REPLACED["scripts/engineering/run_point01_m2_a1_v2_5_baseline_jit_window.py"],"sha256":hashes[REPLACED["scripts/engineering/run_point01_m2_a1_v2_5_baseline_jit_window.py"]]} }},
        "supersedes":{"v2_5_package_digest":OLD_PACKAGE_DIGEST,"v2_5_blueprint_digest":OLD_BLUEPRINT_DIGEST,"v2_4_package_digest":"615a73da64eff69a56a13b42d6c59c892820f15c4de7dc3a2be3c425d2aee68e","authority_disposition":"historical_only_expired_consumed_or_non_replayable"},
        "jit_window_contract":{"approval_schema_version":"finsight_point01_m2_a1_human_jit_window_approval_v1","approval_required_before_issue":True,"orchestrator":{"relative_path":"scripts/engineering/run_point01_m2_a1_v2_6_frozen_jit_window.py","sha256":hashes["scripts/engineering/run_point01_m2_a1_v2_6_frozen_jit_window.py"]},"dry_run":"approval_validate_only_no_admission_receipt_namespace_or_write","execute_sequence":["verify_approval","issue_admission","verify","register","preflight","consume","reverify","grant","materialize","parent_clean_child_execute","immutable_actual","independent_oracle","reviewer","closeout"],"default_command":"do_not_invoke","active_command":"execute_approved_window_only","supersedes_v2_5_package_digest":OLD_PACKAGE_DIGEST}}
    return {**payload,"package_digest":canonical(payload)}


def verify_package(package: Mapping[str, Any]) -> dict[str, Any]:
    failures=[]; payload={key:value for key,value in package.items() if key!="package_digest"}
    if package.get("package_digest") != canonical(payload): failures.append("package_digest_mismatch")
    hashes=package.get("input_file_sha256")
    if not isinstance(hashes,Mapping) or any(sha(path)!=value for path,value in hashes.items()): failures.append("git_index_input_hash_mismatch")
    sys.path.insert(0,str(ROOT/"src")); from sec_agent.canonical_runtime.m2_a1_execution_receipt import M2A1ExecutionPreflightError, preflight_exact_execution
    try: preflight_exact_execution(package,None,repository_root=ROOT,receipt_id="v2-6-schema-only-no-receipt",scenario_id=BASELINE)
    except M2A1ExecutionPreflightError as exc:
        preflight=str(exc)
        if preflight!="package_admission_required": failures.append(f"production_preflight_{preflight}")
    else: preflight="unexpected_pass"; failures.append("production_preflight_missing_admission_did_not_fail_closed")
    dry=subprocess.run([sys.executable,str(ROOT/"scripts/engineering/run_point01_m2_a1_v2_6_frozen_jit_window.py"),"--dry-run-approved-window","--approval",str(ROOT/"DONT_CREATE_APPROVAL.json")],cwd=ROOT,capture_output=True,text=True,check=False)
    try: dry_payload=json.loads(dry.stdout)
    except json.JSONDecodeError: dry_payload={}
    if dry.returncode != 2 or dry_payload.get("status") != "m2_a1_frozen_jit_json_input_unreadable" or any(dry_payload.get(key)!=0 for key in ("new_admission","new_receipt","namespace","runtime","actual")): failures.append("orchestrator_missing_approval_negative_invalid")
    return {"status":"pass" if not failures else "fail_closed","failures":sorted(set(failures)),"calculated_package_digest":canonical(payload),"production_preflight":preflight,"orchestrator_missing_approval":dry_payload,"input_hash_count":len(hashes or {})}


def build_plan(package: Mapping[str,Any], gate:Mapping[str,Any])->dict[str,Any]:
    ids=package["scenario_matrix_summary"]["scenario_ids"]; entries=[{"sequence":i,"group":"P01" if i<=4 else "P02" if i<=10 else "P03","scenario_id":sid,"future_authority":"independent_human_jit_approval_admission_receipt_JIT_only","on_failure":"fail_fast_no_retry_no_replay"} for i,sid in enumerate(ids,1)]
    payload={"schema_version":"finsight_point01_m2_a1_receipt_execution_plan_v1_3_frozen_jit","status":"frozen_jit_entry_refrozen_pending_independent_review_no_authority","exact_package":{"package_ref":package["package_ref"],"package_digest":package["package_digest"],"package_gate_digest":gate["gate_digest"],"scope":package["scope"],"authority_boundary":package["authority_boundary"],"execution_staging_namespace_id":NAMESPACE_ID},"phase_a_digests":package["phase_a_digests"],"incident_binding":package["incident_evidence"],"jit_window_contract":package["jit_window_contract"],"baseline_first":BASELINE,"scenario_execution_order":entries,"group_counts":{"P01":4,"P02":6,"P03":6},"execution_counts":{"approval":0,"admission":0,"receipt":0,"ledger":0,"namespace":0,"actual":0,"external":0,"store_write":0}}
    return {**payload,"plan_digest":canonical(payload)}


def verify_plan(plan:Mapping[str,Any],package:Mapping[str,Any],gate:Mapping[str,Any])->dict[str,Any]:
    payload={key:value for key,value in plan.items() if key!="plan_digest"}; failures=[]
    if plan.get("plan_digest")!=canonical(payload): failures.append("plan_digest_mismatch")
    if plan.get("exact_package",{}).get("package_digest")!=package.get("package_digest") or plan.get("exact_package",{}).get("package_gate_digest")!=gate.get("gate_digest"): failures.append("plan_package_gate_binding_invalid")
    if plan.get("jit_window_contract")!=package.get("jit_window_contract") or plan.get("group_counts")!={"P01":4,"P02":6,"P03":6} or len(plan.get("scenario_execution_order",[]))!=16: failures.append("plan_jit_or_matrix_invalid")
    return {"status":"pass" if not failures else "fail_closed","failures":failures,"calculated_plan_digest":canonical(payload)}


def build_blueprint(package:Mapping[str,Any],pg:Mapping[str,Any],plan:Mapping[str,Any],plg:Mapping[str,Any])->dict[str,Any]:
    payload={"schema_version":"finsight_point01_m2_a1_baseline_authority_blueprint_v1_3_frozen_jit","status":"frozen_jit_blueprint_pending_independent_review_no_authority","exact_binding":{"package_ref":package["package_ref"],"package_digest":package["package_digest"],"package_gate_digest":pg["gate_digest"],"plan_digest":plan["plan_digest"],"plan_gate_digest":plg["gate_digest"],"phase_a_digests":package["phase_a_digests"],"incident_evidence":package["incident_evidence"],"scenario_id":BASELINE,"input_ref":"m2-a1-ai-semis-input","mutation":"none","reviewer_identity":"william/003/total_reviewer","authority_boundary":package["authority_boundary"],"execution_staging_namespace_id":NAMESPACE_ID},"all_other_scenarios":{"count":15,"authority_issue_forbidden":True},"templates":templates(),"command_contracts":{"orchestrator":"do_not_invoke","registrar":"do_not_invoke","executor":"do_not_invoke","baseline_rerun":"do_not_invoke"},"execution_counts":{"approval":0,"admission":0,"receipt":0,"ledger":0,"namespace":0,"actual":0,"external":0,"store_write":0}}
    return {**payload,"blueprint_digest":canonical(payload)}


def verify_blueprint(bp:Mapping[str,Any],package:Mapping[str,Any],pg:Mapping[str,Any],plan:Mapping[str,Any],plg:Mapping[str,Any])->dict[str,Any]:
    payload={key:value for key,value in bp.items() if key!="blueprint_digest"}; b=bp.get("exact_binding",{}); failures=[]
    if bp.get("blueprint_digest")!=canonical(payload): failures.append("blueprint_digest_mismatch")
    if b.get("package_digest")!=package.get("package_digest") or b.get("package_gate_digest")!=pg.get("gate_digest") or b.get("plan_digest")!=plan.get("plan_digest") or b.get("plan_gate_digest")!=plg.get("gate_digest") or b.get("incident_evidence")!=package.get("incident_evidence"): failures.append("blueprint_cross_gate_binding_invalid")
    if bp.get("templates")!=templates() or any(value!="do_not_invoke" for value in bp.get("command_contracts",{}).values()): failures.append("blueprint_template_or_command_invalid")
    return {"status":"pass" if not failures else "fail_closed","failures":failures,"calculated_blueprint_digest":canonical(payload)}


def gate(kind:str,target:Mapping[str,Any],verify:Mapping[str,Any],package:Mapping[str,Any])->dict[str,Any]:
    key={"package":"package_digest","plan":"plan_digest","blueprint":"blueprint_digest"}[kind]; payload={"result_version":f"finsight_point01_m2_a1_v2_6_{kind}_freeze_gate_v1","status":"pass" if verify.get("status")=="pass" else "fail_closed","package_ref":package["package_ref"],"package_digest":package["package_digest"],"target_digest":target[key],"verification":dict(verify),"fixed_store_sha256":FIXED_SHA256,"execution_counts":{"approval":0,"admission":0,"receipt":0,"ledger":0,"namespace":0,"actual":0,"network":0,"tool":0,"model":0,"provider":0,"store_write":0},"next_step":"independent_review_required_no_human_jit_window_approval_issued"}; return {**payload,"gate_digest":canonical(payload)}


def build_artifacts()->dict[str,dict[str,Any]]:
    p=build_package(); pg=gate("package",p,verify_package(p),p); plan=build_plan(p,pg); plg=gate("plan",plan,verify_plan(plan,p,pg),p); bp=build_blueprint(p,pg,plan,plg); bpg=gate("blueprint",bp,verify_blueprint(bp,p,pg,plan,plg),p); return {"package":p,"package_gate":pg,"plan":plan,"plan_gate":plg,"blueprint":bp,"blueprint_gate":bpg}


def main()->int:
    artifacts=build_artifacts()
    for name,path in OUTPUTS.items(): write(path,artifacts[name])
    statuses=[artifacts[key]["status"] for key in ("package_gate","plan_gate","blueprint_gate")]
    print(json.dumps({"status":"phase_b0_3_frozen_jit_entry_refrozen_pending_independent_review" if statuses==["pass"]*3 else "fail_closed",**{f"{name}_digest":artifacts[name]["package_digest" if name=="package" else "gate_digest" if name.endswith("gate") else "plan_digest" if name=="plan" else "blueprint_digest"] for name in artifacts}},sort_keys=True))
    return 0 if statuses==["pass"]*3 else 1


if __name__=="__main__": raise SystemExit(main())
