from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _current_agent_server_preflight(decision_path: Path) -> dict:
    """Delegate current execution checks to its existing runner, not R14's schema.

    This is a compatibility entrypoint, not a second authority or full-product
    verdict. Live data/MCP/identity checks still run before the first model call
    in Agent Server. Historical decisions retain their original preflight.
    """
    from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _preflight_git
    from sec_agent.agent_runtime.dell_specialist_paid_shadow import load_dell_q1_paid_shadow_authority, file_sha256
    from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekStructuredAgentConfig

    authority = load_dell_q1_paid_shadow_authority(decision_path)
    head = _preflight_git(authority, decision_path)
    config_path = ROOT / "configs/research" / authority.deepseek_config_filename
    if file_sha256(config_path) != authority.deepseek_config_sha256:
        raise ValueError("paid_shadow_model_config_binding_invalid")
    config = DeepSeekStructuredAgentConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    if config.model != authority.model:
        raise ValueError("paid_shadow_model_binding_invalid")
    if authority.lead_scope:
        if not config.agentic_message_history or any(
            basis.reasoning_profile != "agentic_message_history_thinking_" + config.profile_for(role).thinking
            for role, basis in authority.lead_scope.node_budgets.items()
        ):
            raise ValueError("lead_budget_thinking_profile_mismatch")
    return {"schema_version": "fin_ia_current_decision_bound_project_os_preflight_v1_0",
            "status": "current_agent_server_execution_contract_pass", "decision_ref": str(decision_path.relative_to(ROOT)),
            "head": head, "workflow": authority.workflow, "network_calls": 0, "model_calls": 0,
            "provider_calls": 0, "credential_value_persisted": False, "full_product_pass": False,
            "known_boundary": "Existing runner owns freshness; Agent Server owns live data/MCP/identity checks before model. Historical R14/full-repository results are not promoted."}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the current-baseline, decision-bound Project OS preflight. "
            "The historical multi-agent preflight implementation remains archived."
        )
    )
    parser.add_argument("--decision", required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        decision_path = (ROOT / args.decision).resolve()
        if not decision_path.is_relative_to(ROOT):
            raise ValueError("preflight_decision_outside_repository")
        schema = json.loads(decision_path.read_text(encoding="utf-8")).get("schema_version")
        if schema == "fin_ia_dell_q1_specialist_paid_shadow_authority_v1_0":
            result = _current_agent_server_preflight(decision_path)
        else:
            from sec_agent.project_os_preflight import build_preflight
            result = build_preflight(root=ROOT, decision_ref=args.decision)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        result = {
            "schema_version": "fin_ia_current_decision_bound_project_os_preflight_v1_0",
            "status": "fail_closed",
            "decision_ref": args.decision,
            "failure_code": str(exc),
            "network_calls": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "credential_value_persisted": False,
        }
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 1
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            sort_keys=True,
            indent=2 if args.pretty else None,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
