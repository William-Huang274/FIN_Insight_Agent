from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping
import uuid


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.llm_gateway import chat_completion  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402
from sec_agent.s1_08_candidate_generation_runtime import (  # noqa: E402
    load_source_catalog,
)
from sec_agent.s1_08_query_atom_canary_runtime import (  # noqa: E402
    RUN_SCOPE,
    S108QueryAtomCanaryError,
    compile_query_atom_request,
    execute_query_atom_canary,
    issue_query_atom_canary_admission,
    load_query_atom_canary_policy,
)
from sec_agent.s1_08_query_facet_plan import (  # noqa: E402
    compile_query_facet_plans,
    load_query_facet_policy,
)
from sec_agent.s1_08_search_intent_compiler import (  # noqa: E402
    compile_search_intents,
    load_search_intent_policy,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger  # noqa: E402


POLICY_REF = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_08_deepseek_query_atom_canary_policy_v1_0.json"
)
AUTHORITY_REF = ROOT / (
    "configs/releases/fin_ia_0_1_3_s1_08_deepseek_query_atom_canary_authority_decision_v1_0.json"
)
RUNTIME_MODULE_REF = ROOT / "src/sec_agent/s1_08_query_atom_canary_runtime.py"
RUNTIME_BASE = ROOT / ".codex_runtime/fin013_s1_08/query_atom_canary_v1"
AUTHORITY_ROOT = RUNTIME_BASE / "authorities"
RUN_ROOT = RUNTIME_BASE / "runs"
LEDGER_REF = RUNTIME_BASE / "shared/admission_ledger.sqlite"


class QueryAtomRunnerError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise QueryAtomRunnerError("s1_08_query_atom_runner_json_object_required")
    return value


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise QueryAtomRunnerError(
            "s1_08_query_atom_runner_git_failed:" + ":".join(args)
        )
    return result.stdout.strip()


def validate_repository() -> str:
    if _git("status", "--porcelain"):
        raise QueryAtomRunnerError("s1_08_query_atom_runner_repository_not_clean")
    head = _git("rev-parse", "HEAD")
    if head != _git("rev-parse", "@{upstream}"):
        raise QueryAtomRunnerError("s1_08_query_atom_runner_repository_not_synced")
    return head


def _verify_bound_inputs(policy: Mapping[str, Any]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    bindings = policy["immutable_inputs"]
    for key, ref in bindings.items():
        if not key.endswith("_ref"):
            continue
        stem = key.removesuffix("_ref")
        path = ROOT / str(ref)
        if (
            not path.is_file()
            or _normalized_sha256(path) != bindings[f"{stem}_sha256"]
        ):
            raise QueryAtomRunnerError(
                "s1_08_query_atom_runner_bound_input_drift:" + stem
            )
        paths[stem] = path
    return paths


def build_material() -> dict[str, Any]:
    policy = load_query_atom_canary_policy(POLICY_REF)
    paths = _verify_bound_inputs(policy)
    three_way = _load(paths["three_way_zero_call_proof"])
    three_way_body = dict(three_way)
    three_way_digest = three_way_body.pop("evaluation_digest", "")
    if (
        three_way_digest != canonical_digest(three_way_body)
        or three_way.get("status")
        != "zero_call_A_B_pass_model_atom_observation_pending"
        or three_way.get("decision", {}).get("next")
        != "bounded_deepseek_query_atom_canary_authority_decision"
        or three_way.get("quality_gates", {}).get(
            "deterministic_local_structure_pass"
        )
        is not True
    ):
        raise QueryAtomRunnerError(
            "s1_08_query_atom_runner_three_way_basis_invalid"
        )
    proof = _load(paths["query_facet_proof"])
    facet_policy = load_query_facet_policy(paths["query_facet_policy"])
    visible = _load(paths["model_visible_case_pack"])
    objectives = {
        str(row["case_key"]): str(row["research_objective"])
        for row in visible["cases"]
    }
    intents = compile_search_intents(
        catalog=load_source_catalog(paths["source_catalog"]),
        policy=load_search_intent_policy(paths["search_intent_policy"]),
        research_objectives=objectives,
    )
    plans = compile_query_facet_plans(intents=intents, policy=facet_policy)
    plan_rows = [row.as_dict() for row in plans]
    if plan_rows != proof.get("plans"):
        raise QueryAtomRunnerError(
            "s1_08_query_atom_runner_query_facet_projection_drift"
        )
    request = compile_query_atom_request(
        policy=policy,
        query_facet_plans=plan_rows,
        research_objectives=objectives,
    )
    return {
        "policy": policy,
        "paths": paths,
        "query_facet_policy": facet_policy,
        "intents": intents,
        "request": request,
        "three_way_evaluation_digest": three_way_digest,
        "query_facet_plan_set_digest": canonical_digest(plan_rows),
    }


def _validate_authority(*, head: str, material: Mapping[str, Any]) -> dict[str, Any]:
    if not AUTHORITY_REF.is_file():
        raise QueryAtomRunnerError("s1_08_query_atom_runner_authority_missing")
    authority = _load(AUTHORITY_REF)
    body = {
        key: value
        for key, value in authority.items()
        if key != "decision_digest"
    }
    if (
        authority.get("decision_digest") != canonical_digest(body)
        or authority.get("status")
        != "one_bounded_deepseek_query_atom_canary_authorized"
        or authority.get("run_scope") != RUN_SCOPE
        or authority.get("authority", {}).get("provider_call_ceiling") != 1
        or authority.get("authority", {}).get("retry_count") != 0
        or authority.get("authority", {}).get("automatic_runtime_activation")
        is not False
    ):
        raise QueryAtomRunnerError("s1_08_query_atom_runner_authority_invalid")
    implementation = authority.get("implementation_binding") or {}
    expected = {
        "runner_ref": Path(__file__).resolve().relative_to(ROOT).as_posix(),
        "runner_sha256_normalized": _normalized_sha256(Path(__file__).resolve()),
        "runtime_module_ref": RUNTIME_MODULE_REF.relative_to(ROOT).as_posix(),
        "runtime_module_sha256_normalized": _normalized_sha256(
            RUNTIME_MODULE_REF
        ),
        "policy_ref": POLICY_REF.relative_to(ROOT).as_posix(),
        "policy_sha256_normalized": _normalized_sha256(POLICY_REF),
        "request_digest": material["request"]["request_digest"],
        "three_way_evaluation_digest": material[
            "three_way_evaluation_digest"
        ],
        "query_facet_plan_set_digest": material["query_facet_plan_set_digest"],
    }
    if any(implementation.get(key) != value for key, value in expected.items()):
        raise QueryAtomRunnerError(
            "s1_08_query_atom_runner_implementation_binding_drift"
        )
    source_commit = str(authority.get("implementation_commit") or "")
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, head],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if ancestor.returncode != 0:
        raise QueryAtomRunnerError(
            "s1_08_query_atom_runner_implementation_commit_not_ancestor"
        )
    return authority


def _credential_present(policy: Mapping[str, Any]) -> bool:
    env_name = str(policy["provider"]["api_key_env"])
    return bool(os.environ.get(env_name, "").strip())


def admission_storage_path(
    admission: Mapping[str, Any], *, authority_root: Path = AUTHORITY_ROOT
) -> Path:
    run_id = str(admission.get("run_id") or "")
    if re.fullmatch(
        r"fin013_s1_08_query_atom_canary_[0-9a-f]{20}",
        run_id,
    ) is None:
        raise QueryAtomRunnerError(
            "s1_08_query_atom_runner_admission_storage_identity_invalid"
        )
    return authority_root / f"{run_id}.json"


def compile_admission(
    *, head: str, material: Mapping[str, Any], issued_at: str, expires_at: str
) -> dict[str, Any]:
    authority = _validate_authority(head=head, material=material)
    return issue_query_atom_canary_admission(
        execution_git_commit=head,
        runner_sha256=_normalized_sha256(Path(__file__).resolve()),
        runtime_module_sha256=_normalized_sha256(RUNTIME_MODULE_REF),
        policy_sha256=_normalized_sha256(POLICY_REF),
        authority_decision_digest=authority["decision_digest"],
        request=material["request"],
        issued_at=issued_at,
        expires_at=expires_at,
        run_nonce=uuid.uuid4().hex,
        credential_present=_credential_present(material["policy"]),
        policy=material["policy"],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--issue", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--admission", type=Path)
    args = parser.parse_args()
    head = validate_repository()
    material = build_material()
    authority = _validate_authority(head=head, material=material)
    if not _credential_present(material["policy"]):
        raise QueryAtomRunnerError("s1_08_query_atom_runner_credential_absent")
    preflight = run_project_os_preflight(ROOT, run_scope=RUN_SCOPE)
    if preflight.get("status") != "pass":
        raise QueryAtomRunnerError("s1_08_query_atom_runner_project_os_blocked")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if args.preflight:
        print(
            json.dumps(
                {
                    "status": "preflight_pass",
                    "execution_git_commit": head,
                    "run_scope": RUN_SCOPE,
                    "request_digest": material["request"]["request_digest"],
                    "visible_plan_count": len(material["request"]["plans"]),
                    "provider": material["policy"]["provider"]["model"],
                    "provider_call_ceiling": 1,
                    "retry_count": 0,
                    "credential_present": True,
                    "credential_value_read_or_persisted": False,
                    "authority_decision_digest": authority["decision_digest"],
                    "automatic_runtime_activation": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.issue:
        admission = compile_admission(
            head=head,
            material=material,
            issued_at=now.isoformat().replace("+00:00", "Z"),
            expires_at=(now + timedelta(hours=2))
            .isoformat()
            .replace("+00:00", "Z"),
        )
        AUTHORITY_ROOT.mkdir(parents=True, exist_ok=True)
        path = admission_storage_path(admission)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    admission,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        print(
            json.dumps(
                {
                    "status": "admission_issued",
                    "admission_path": str(path),
                    "admission_id": admission["admission_id"],
                    "admission_digest": admission["admission_digest"],
                    "run_id": admission["run_id"],
                    "attempt_id": admission["attempt_id"],
                    "expires_at": admission["expires_at"],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.admission is None:
        parser.error("--execute requires --admission")
    admission = _load(args.admission.resolve())
    terminal = execute_query_atom_canary(
        admission=admission,
        request=material["request"],
        policy=material["policy"],
        intents=material["intents"],
        query_facet_policy=material["query_facet_policy"],
        execution_git_commit=head,
        runner_sha256=_normalized_sha256(Path(__file__).resolve()),
        runtime_module_sha256=_normalized_sha256(RUNTIME_MODULE_REF),
        policy_sha256=_normalized_sha256(POLICY_REF),
        runtime_root=RUN_ROOT / str(admission["run_id"]),
        shared_ledger=SharedAdmissionConsumptionLedger(LEDGER_REF),
        provider_call=chat_completion,
        observed_at=now.isoformat().replace("+00:00", "Z"),
    )
    print(json.dumps(terminal, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if terminal["status"] == "terminal_succeeded_exact_once" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (QueryAtomRunnerError, S108QueryAtomCanaryError) as exc:
        print(
            json.dumps(
                {
                    "status": "blocked_or_failed_before_execution",
                    "code": str(getattr(exc, "code", str(exc))),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
