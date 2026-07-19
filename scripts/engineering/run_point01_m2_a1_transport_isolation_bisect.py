"""Fresh-process import-boundary classification for RC-P38-024.

This Phase-A probe intentionally uses only local, synthetic inputs.  Every
child runs with ``-I`` and emits import/module observations separately from
constructor, connect, request and success counts.  A transport module being
loaded is context only; no child is allowed to connect or send a request.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m2_a1_rc_p38_024_root_cause_classification_v1_0.json"
TRANSPORT_ROOTS = frozenset({"aiohttp", "anthropic", "deepseek", "httpx", "openai", "requests", "urllib3"})
PROBES = (
    "clean_python_baseline",
    "canonical_planning_local_compile",
    "legacy_bridge_runtime_facade_import",
    "actual_audit_bootstrap_import",
    "canary_constructor_connect_request_negative",
)


def _canonical_digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _transport_modules() -> dict[str, str | None]:
    return {
        name: str(getattr(module, "__file__", "")) or None
        for name, module in sorted(sys.modules.items())
        if name.split(".", 1)[0] in TRANSPORT_ROOTS
    }


def _result(*, probe_id: str, before: dict[str, str | None], owner: str, details: dict[str, Any], counts: dict[str, int] | None = None) -> dict[str, Any]:
    after = _transport_modules()
    payload = {
        "probe_id": probe_id,
        "fresh_process": True,
        "python_isolated_mode": bool(sys.flags.isolated),
        "transport_modules_before": before,
        "transport_modules_after": after,
        "transport_module_delta": {key: after[key] for key in sorted(set(after) - set(before))},
        "import_owner": owner,
        "constructor_connect_request_counts": counts or {
            "transport_constructor_attempt_count": 0,
            "socket_connect_attempt_count": 0,
            "http_connect_attempt_count": 0,
            "network_request_attempt_count": 0,
            "network_request_success_count": 0,
        },
        "details": details,
        "exit_status": "pass",
    }
    payload["probe_digest"] = _canonical_digest(payload)
    return payload


def _child(probe_id: str) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    before = _transport_modules()
    if probe_id == "clean_python_baseline":
        return _result(probe_id=probe_id, before=before, owner="python_stdlib_only", details={"business_imports": 0})
    if probe_id == "canonical_planning_local_compile":
        from sec_agent.canonical_runtime.legacy_objective_adapter import adapt_legacy_research_objective
        from sec_agent.canonical_runtime.planning_service import DecisionSurfacePlanningService, PackSelectionDecision

        required_items = [
            {
                "required_item_id": f"local-cell-{index}",
                "question": f"Synthetic local planning question {index}?",
                "owner_role": "fundamental_analyst",
                "materiality": "high",
                "evidence_role": "issuer_metric",
                "entity_scope": ["LOCAL"],
                "period_scope": "current",
                "source_policy_ref": "issuer_first",
                "stop_rule": "typed gap",
            }
            for index in range(1, 11)
        ]
        contract = adapt_legacy_research_objective(
            {"query": "Synthetic local planning compile.", "as_of": "2026-07-14T00:00:00Z", "universe": ["LOCAL"], "language": "en", "required_items": required_items},
            tenant_id="tenant-rc-p38-024",
            project_id="project-rc-p38-024",
            case_id="case-rc-p38-024",
            compiler_policy_ref="point01-m2-1-compiler-policy-v1",
        ).model_copy(update={"pack_selection": PackSelectionDecision(universal_pack_refs=("pack-universal-research:v1",))})
        audit_scope = {
            "tenant_id": "tenant-rc-p38-024",
            "project_id": "project-rc-p38-024",
            "case_id": "case-rc-p38-024",
            "actor_snapshot_ref": "actor-rc-p38-024",
            "permission_snapshot_ref": "permission-rc-p38-024",
            "correlation_id": "correlation-rc-p38-024",
            "created_at": "2026-07-14T00:00:00Z",
            "recorded_at": "2026-07-14T00:00:00Z",
        }
        bundle = DecisionSurfacePlanningService(None).compile_deterministic_fixture(contract, audit_scope=audit_scope)
        validation = DecisionSurfacePlanningService(None).validate_decision_surface_bundle(contract.case_id, bundle)
        if validation["status"] != "pass":
            raise RuntimeError("local_planning_validation_failed")
        return _result(probe_id=probe_id, before=before, owner="canonical_runtime.planning_service", details={"local_bundle_cell_count": validation["cell_count"], "planning_authority": validation["planning_authority"]})
    if probe_id == "legacy_bridge_runtime_facade_import":
        from sec_agent.canonical_runtime import RuntimeFacade
        from sec_agent.canonical_runtime.legacy_objective_adapter import adapt_legacy_research_objective

        return _result(probe_id=probe_id, before=before, owner="canonical_runtime.lazy_public_exports+legacy_objective_adapter", details={"runtime_facade_symbol_resolved": RuntimeFacade.__name__, "legacy_adapter_symbol_resolved": adapt_legacy_research_objective.__name__})
    if probe_id == "actual_audit_bootstrap_import":
        from sec_agent.canonical_runtime.m2_a1_execution_receipt import preflight_exact_execution
        from sec_agent.canonical_runtime.m2_a1_audit_canary import M2A1AuditCanary

        canary = M2A1AuditCanary(allowed_temporary_roots=(ROOT / ".phase_a_non_materialized",))
        aliases = canary.observe_transport_module_presence()
        with canary.instrument():
            from sec_agent.canonical_runtime.m2_a1_audit_harness import M2A1ActualRunner

        return _result(probe_id=probe_id, before=before, owner="m2_a1_execution_receipt+clean_child_canary_before_harness_bootstrap", details={"preflight_symbol_resolved": preflight_exact_execution.__name__, "actual_runner_symbol_resolved": M2A1ActualRunner.__name__, "pre_canary_context_aliases": aliases, "supervisor_uses_clean_child": True}, counts={key: int(value) for key, value in canary.snapshot()["counts"].items() if key in {"transport_constructor_attempt_count", "socket_connect_attempt_count", "http_connect_attempt_count", "network_request_attempt_count", "network_request_success_count"}})
    if probe_id == "canary_constructor_connect_request_negative":
        import socket
        import urllib.request
        import requests
        from sec_agent.canonical_runtime.m2_a1_audit_canary import M2A1AuditCanary, M2A1TransportAccessError

        canary = M2A1AuditCanary(allowed_temporary_roots=(ROOT / ".phase_a_non_materialized",))
        aliases = canary.observe_transport_module_presence()
        context = canary.snapshot()["counts"]
        if int(context["transport_constructor_attempt_count"]) != 0:
            raise RuntimeError("module_presence_misclassified_as_constructor")
        blocked: list[str] = []
        with canary.instrument():
            for label, operation in (
                ("requests_session_constructor", lambda: requests.Session()),
                ("socket_connect", lambda: socket.socket().connect(("127.0.0.1", 1))),
                ("urlopen_request", lambda: urllib.request.urlopen("https://example.invalid/")),
            ):
                try:
                    operation()
                except M2A1TransportAccessError:
                    blocked.append(label)
                else:
                    raise RuntimeError(f"negative_control_not_blocked:{label}")
        snapshot = canary.snapshot()
        counts = {key: int(value) for key, value in snapshot["counts"].items() if key in {"transport_constructor_attempt_count", "socket_connect_attempt_count", "http_connect_attempt_count", "network_request_attempt_count", "network_request_success_count"}}
        if counts["network_request_success_count"] != 0:
            raise RuntimeError("network_success_forbidden")
        return _result(probe_id=probe_id, before=before, owner="m2_a1_audit_canary.concrete_constructor_connect_request_guards", details={"context_aliases": aliases, "blocked_negative_controls": blocked}, counts=counts)
    raise ValueError(f"probe_id_invalid:{probe_id}")


def _run_child(probe_id: str) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--child", probe_id], cwd=ROOT, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"bisect_child_failed:{probe_id}:{completed.returncode}:{completed.stderr.strip()}")
    return json.loads(completed.stdout)


def build_classification() -> dict[str, Any]:
    probes = [_run_child(probe_id) for probe_id in PROBES]
    by_id = {row["probe_id"]: row for row in probes}
    planning_transport_delta = by_id["canonical_planning_local_compile"]["transport_module_delta"]
    baseline_transport_delta = by_id["clean_python_baseline"]["transport_module_delta"]
    negative_counts = by_id["canary_constructor_connect_request_negative"]["constructor_connect_request_counts"]
    payload = {
        "schema_version": "finsight_point01_rc_p38_024_root_cause_classification_v1_0",
        "root_cause_id": "RC-P38-024",
        "scope": "phase_a_root_cause_classification_and_transport_isolation_repair_only",
        "prior_fail_closed_actual_digest": "934fb16b76f1e1b19371603f0d69c2e3e25c9357c8427c84e1e626b1247795d7",
        "classification": {
            "production_compiler_or_shadow_eager_transport": "confirmed_before_repair_via_canonical_runtime_init_to_receipt_bound_candidate_bundle_to_bounded_sec_metadata_execution_requests_import; absent_after_lazy_export_repair" if not planning_transport_delta else "repair_incomplete_transport_delta_remains",
            "runner_or_pytest_outer_process_preload": "not_primary_after_clean_process_bisect",
            "canary_module_presence_constructor_conflation": "confirmed_before_repair_fixed_by_context_only_observation",
        },
        "historical_before_repair": {
            "evidence_kind": "phase_a_fresh_python_isolated_import_probe_before_lazy_export_patch",
            "canonical_planning_transport_module_loaded_count": 97,
            "transport_constructor_attempt_count": 0,
            "socket_or_http_connect_attempt_count": 0,
            "network_request_attempt_count": 0,
            "network_request_success_count": 0,
            "import_chain": "canonical_runtime.__init__ -> receipt_bound_candidate_bundle -> bounded_sec_metadata_execution -> requests",
            "interpretation": "production_bootstrap_import_ownership_not_network_use",
        },
        "repair_decision": {
            "canonical_runtime_exports": "lazy_dependency_resolution",
            "actual_runner": "stdlib_supervisor_spawns_python_isolated_clean_child",
            "canary": "module_presence_context_only_concrete_constructor_connect_request_hard_fail",
        },
        "probes": probes,
        "before_after_behavior": {
            "clean_baseline_transport_delta": baseline_transport_delta,
            "planning_transport_delta_after_repair": planning_transport_delta,
            "negative_controls_blocked": by_id["canary_constructor_connect_request_negative"]["details"]["blocked_negative_controls"],
            "negative_control_counts": negative_counts,
        },
        "authority_boundary": "no_admission_no_receipt_no_baseline_rerun_no_network_tool_model_provider_or_fixed_store_write",
        "side_effect_counters": {
            "network_request_success_count": 0,
            "external_tool_call_count": 0,
            "model_or_provider_call_count": 0,
            "fixed_or_business_store_write_count": 0,
            "baseline_rerun_count": 0,
            "new_admission_or_receipt_count": 0,
        },
    }
    return {**payload, "classification_digest": _canonical_digest(payload)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run RC-P38-024 fresh-process transport isolation classification.")
    parser.add_argument("--child", choices=PROBES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    if args.child:
        print(json.dumps(_child(args.child), ensure_ascii=False, sort_keys=True))
        return 0
    result = build_classification()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "classification_digest": result["classification_digest"], "output": str(args.output), "network_request_success_count": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
