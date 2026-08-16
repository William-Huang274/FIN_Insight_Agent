from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.providers.chat_completions import (  # noqa: E402
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
)
from sec_agent.providers.deepseek_strict import (  # noqa: E402
    project_deepseek_strict_tool,
    validate_deepseek_strict_submission_profile,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    bind_current_research_model_text_schema_definition,
    compile_current_research_model_text_schema,
    validate_current_research_model_text,
)
from sec_agent.research.reviewed_evidence_pack import canonical_digest  # noqa: E402


AUTHORITY_SCHEMA = "fin_ia_s3_deepseek_strict_pattern_canary_authority_v1_0"
AUTHORITY_STATUS = "signed_exact_once_deepseek_beta_strict_pattern_canary"
RESULT_SCHEMA = "fin_ia_s3_deepseek_strict_pattern_canary_result_v1_0"
FULL_RESULT_SCHEMA = "fin_ia_s3_deepseek_strict_pattern_canary_full_v1_0"
EXPECTED_BUDGET = {
    "maximum_model_calls": 1,
    "maximum_transport_attempts": 1,
    "retries": 0,
    "fallbacks": 0,
    "financial_evidence_calls": 0,
    "product_publication": 0,
}


class StrictPatternCanaryError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise StrictPatternCanaryError("strict_pattern_path_invalid")
    path = ROOT.joinpath(*relative.parts).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise StrictPatternCanaryError("strict_pattern_path_escape") from exc
    return path


def _relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StrictPatternCanaryError("strict_pattern_json_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise StrictPatternCanaryError("strict_pattern_git_unavailable")
    return completed.stdout.strip()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise StrictPatternCanaryError(
            "strict_pattern_exact_once_output_exists"
        ) from exc


def compile_canary_tool() -> tuple[dict[str, Any], dict[str, Any]]:
    parameters = bind_current_research_model_text_schema_definition(
        {
            "type": "object",
            "properties": {
                "safe_atom": compile_current_research_model_text_schema(
                    description=(
                        "Restate the draft as a generic financial conclusion. "
                        "Do not copy filing identifiers, periods, digits, units, "
                        "URLs or internal refs."
                    )
                )
            },
            "required": ["safe_atom"],
            "additionalProperties": False,
        }
    )
    canonical = {
        "type": "function",
        "function": {
            "name": "submit_safe_financial_atom",
            "description": "Submit one model-owned atom without authoritative surfaces.",
            "strict": True,
            "parameters": parameters,
        },
    }
    return project_deepseek_strict_tool(canonical)


def _validate_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> tuple[dict[str, Path], Mapping[str, Any]]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA
        and payload.get("status") == AUTHORITY_STATUS
        and payload.get("execution_budget") == EXPECTED_BUDGET
        and payload.get("product_promotion_authorized") is False
    ):
        raise StrictPatternCanaryError("strict_pattern_authority_invalid")
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise StrictPatternCanaryError("strict_pattern_commit_invalid")
    if _git("rev-parse", "HEAD").lower() != commit:
        raise StrictPatternCanaryError("strict_pattern_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise StrictPatternCanaryError("strict_pattern_upstream_drift")
    status = [
        row
        for row in _git(
            "status", "--porcelain=v1", "--untracked-files=all"
        ).splitlines()
        if row
    ]
    if status != [f"?? {_relative(authority_path)}"]:
        raise StrictPatternCanaryError("strict_pattern_worktree_not_clean")

    bound = payload.get("bound_inputs")
    output = payload.get("output_contract")
    if not isinstance(bound, Mapping) or not isinstance(output, Mapping):
        raise StrictPatternCanaryError("strict_pattern_authority_shape_invalid")
    required_refs = {
        "profile_ref",
        "zero_call_result_ref",
        "scope_decision_ref",
        "runner_ref",
        "projection_implementation_ref",
        "model_text_contract_ref",
    }
    expected_bound = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    }
    if set(bound) != expected_bound:
        raise StrictPatternCanaryError("strict_pattern_bound_inputs_invalid")
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise StrictPatternCanaryError(
                f"strict_pattern_bound_input_drift:{key}"
            )
        paths[key] = path
    proof = _json(paths["zero_call_result_ref"])
    decision = _json(paths["scope_decision_ref"])
    if not (
        proof.get("status") == "engineering_pass_zero_call_deepseek_strict_projection"
        and proof.get("live_authorized") is False
        and decision.get("status")
        == "approved_one_deepseek_beta_strict_pattern_canary_exact_once"
        and decision.get("execution_budget") == EXPECTED_BUDGET
        and decision.get("product_promotion_authorized") is False
    ):
        raise StrictPatternCanaryError("strict_pattern_predecessor_invalid")
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "attempt_id",
        "product_publication",
    }
    if not (
        set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(str(output.get(key) or "") for key in required_output)
    ):
        raise StrictPatternCanaryError("strict_pattern_output_invalid")
    if any(
        path.exists()
        for path in (
            _resolve(str(output["capture_root_ref"])) / str(output["run_id"]),
            _resolve(str(output["private_output_root_ref"])),
            _resolve(str(output["public_result_ref"])),
        )
    ):
        raise StrictPatternCanaryError("strict_pattern_identity_consumed")
    return paths, output


def _arguments(result: ChatCompletionToolStepResult) -> dict[str, Any]:
    if result.finish_reason != "tool_calls" or len(result.tool_calls) != 1:
        raise StrictPatternCanaryError("strict_pattern_tool_call_invalid")
    function = result.tool_calls[0].get("function")
    if not (
        isinstance(function, Mapping)
        and function.get("name") == "submit_safe_financial_atom"
    ):
        raise StrictPatternCanaryError("strict_pattern_tool_call_invalid")
    try:
        value = json.loads(str(function.get("arguments") or ""))
    except json.JSONDecodeError as exc:
        raise StrictPatternCanaryError("strict_pattern_arguments_invalid") from exc
    if not isinstance(value, dict) or set(value) != {"safe_atom"}:
        raise StrictPatternCanaryError("strict_pattern_arguments_invalid")
    return value


def run(
    authority_path: Path,
    *,
    executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths, output = _validate_authority(authority, authority_path=authority_path)
    profile = load_chat_completion_profile(_json(paths["profile_ref"]))
    validate_deepseek_strict_submission_profile(profile)
    tool, projection = compile_canary_tool()
    messages = (
        {
            "role": "system",
            "content": (
                "You are testing strict financial Tool submission. The final "
                "Tool arguments must follow the supplied schema exactly."
            ),
        },
        {
            "role": "assistant",
            "content": (
                "Working draft: the 10-Q and FY27 Q1 period appear supportive, "
                "but those authoritative surfaces belong in structured metadata."
            ),
        },
        {
            "role": "user",
            "content": (
                "Call submit_safe_financial_atom exactly once. Preserve only the "
                "generic conclusion and omit every filing identifier, period, "
                "digit, unit, URL and internal ref from safe_atom."
            ),
        },
    )
    provider_step: dict[str, Any] = {}
    validated: dict[str, Any] = {}
    failure = {"phase": "", "code": "", "capture_ref": ""}
    try:
        result = executor(
            profile=profile,
            messages=messages,
            tools=[tool],
            capture_root=_resolve(str(output["capture_root_ref"])),
            run_id=str(output["run_id"]),
            attempt_id=str(output["attempt_id"]),
            tool_choice=None,
        )
        provider_step = result.as_dict()
        arguments = _arguments(result)
        atom = validate_current_research_model_text(
            arguments["safe_atom"],
            maximum=400,
            code="strict_pattern_safe_atom_invalid",
        )
        validated = {
            "safe_atom": atom,
            "safe_atom_digest": canonical_digest({"safe_atom": atom}),
        }
    except ModelGatewayError as exc:
        failure = {
            "phase": "provider_transport_or_strict_schema",
            "code": exc.code,
            "capture_ref": (
                _relative(exc.capture_ref) if exc.capture_ref else ""
            ),
        }
    except StrictPatternCanaryError as exc:
        failure = {"phase": "tool_submission", "code": exc.code, "capture_ref": ""}
    except Exception as exc:
        code = getattr(exc, "code", "strict_pattern_local_validation_failed")
        failure = {"phase": "local_validation", "code": str(code), "capture_ref": ""}

    passed = bool(validated)
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    full_body = {
        "schema_version": FULL_RESULT_SCHEMA,
        "status": (
            "completed_deepseek_beta_strict_pattern_qualified"
            if passed
            else "terminal_failed_no_retry"
        ),
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "messages_digest": canonical_digest(list(messages)),
        "wire_tool": tool,
        "projection_receipt": projection,
        "provider_step": provider_step,
        "validated_output": validated,
        "failure": failure,
        "execution": {
            "model_calls_attempted": 1,
            "transport_attempts": 1,
            "retries": 0,
            "fallbacks": 0,
            "financial_evidence_calls": 0,
            "product_publication": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    private_root = _resolve(str(output["private_output_root_ref"]))
    _write_new(private_root / "full_result.json", full)
    public_body = {
        "schema_version": RESULT_SCHEMA,
        "status": full["status"],
        "recorded_at": recorded_at,
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "messages_digest": full["messages_digest"],
        "projection_receipt": projection,
        "provider_step": (
            {
                "finish_reason": provider_step.get("finish_reason", ""),
                "usage": provider_step.get("usage", {}),
                "request_digest": provider_step.get("request_digest", ""),
                "response_digest": provider_step.get("response_digest", ""),
                "request_capture_ref": (
                    _relative(provider_step["request_capture_ref"])
                    if provider_step.get("request_capture_ref")
                    else ""
                ),
                "response_capture_ref": (
                    _relative(provider_step["response_capture_ref"])
                    if provider_step.get("response_capture_ref")
                    else ""
                ),
            }
            if provider_step
            else {}
        ),
        "safe_atom_digest": validated.get("safe_atom_digest", ""),
        "failure": failure,
        "execution": full["execution"],
        "acceptance": {
            "deepseek_beta_endpoint_accepted_schema": passed,
            "strict_pattern_output_locally_valid": passed,
            "canonical_finance_contract_promoted": False,
            "product_publication": False,
        },
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha(private_root / "full_result.json"),
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), public)
    return public


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args(argv)
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("completed_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
