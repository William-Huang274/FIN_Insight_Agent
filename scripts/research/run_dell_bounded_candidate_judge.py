"""Run one exact-once, candidate-only DeepSeek judge over two local BM25 pools."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, NoReturn, Sequence


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(SRC), str(ROOT)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.agent_runtime.bounded_candidate_judge import (  # noqa: E402
    BoundedCandidateJudgeError,
    INPUT_SCHEMA_VERSION,
    build_candidate_judge_messages,
    find_banned_qrel_input_keys,
    validate_candidate_judge_input,
    validate_candidate_judge_output,
)
from sec_agent.providers.chat_completions import (  # noqa: E402
    ModelGatewayError,
    execute_chat_completion_exact_once,
    load_chat_completion_profile,
)


CONFIG_SCHEMA_VERSION = "fin_ia_dell_bounded_candidate_judge_config_v1_0"
ATTEMPT_SCHEMA_VERSION = "fin_ia_dell_bounded_candidate_judge_attempt_v1_0"
RESULT_SCHEMA_VERSION = "fin_ia_dell_bounded_candidate_judge_result_v1_0"
FAILURE_SCHEMA_VERSION = "fin_ia_dell_bounded_candidate_judge_failure_v1_0"
DEFAULT_CONFIG = (
    ROOT
    / "configs/research/fin_ia_0_1_3_dell_bounded_candidate_judge_v1_0.json"
)
DEFAULT_PROFILE = (
    ROOT
    / "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_"
    "bounded_candidate_judge_non_thinking_profile_v1_0.json"
)
EXPECTED_CONFIG_FIELDS = {
    "schema_version",
    "status",
    "case_id",
    "source_attempt",
    "queries",
    "token_budget_basis",
    "authority",
}


class CandidateJudgeRunError(RuntimeError):
    """Typed composition-root or immutable-attempt failure."""


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path, *, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateJudgeRunError(code) from exc
    if not isinstance(value, dict):
        raise CandidateJudgeRunError(code)
    return value


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                allow_nan=False,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
    except FileExistsError as exc:
        raise CandidateJudgeRunError("candidate_judge_attempt_file_exists") from exc


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CandidateJudgeRunError(code)


def _resolve_artifact(root: Path, spec: Mapping[str, Any], *, label: str) -> Path:
    expected = {"relative_path", "sha256"}
    _require(set(spec) == expected, f"candidate_judge_{label}_spec_invalid")
    path = (root / str(spec["relative_path"])).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise CandidateJudgeRunError(
            f"candidate_judge_{label}_path_escape"
        ) from exc
    _require(path.is_file(), f"candidate_judge_{label}_missing")
    _require(
        _file_sha256(path) == str(spec["sha256"]).casefold(),
        f"candidate_judge_{label}_digest_mismatch",
    )
    return path


def load_candidate_judge_config(path: Path) -> dict[str, Any]:
    config = _read_json(path, code="candidate_judge_config_invalid")
    _require(set(config) == EXPECTED_CONFIG_FIELDS, "candidate_judge_config_fields_invalid")
    _require(
        config.get("schema_version") == CONFIG_SCHEMA_VERSION,
        "candidate_judge_config_schema_invalid",
    )
    _require(
        config.get("status") == "bounded_engineering_candidate_only",
        "candidate_judge_config_status_invalid",
    )
    _require(
        config.get("case_id") == "DELL_AI_INFRA_REFERENCE_VERTICAL",
        "candidate_judge_case_id_invalid",
    )
    queries = config.get("queries")
    _require(isinstance(queries, list) and len(queries) == 2, "candidate_judge_query_count_invalid")
    _require(
        not find_banned_qrel_input_keys(config),
        "candidate_judge_config_qrel_label_leakage",
    )
    authority = config.get("authority")
    expected_authority = {
        "provider_attempt_ceiling": 1,
        "retry_count": 0,
        "fallback_model_allowed": False,
        "external_knowledge_allowed": False,
        "candidate_only": True,
        "evidence_promotion_authorized": False,
        "formal_qualification_claimed": False,
        "source_attempt_mutation_authorized": False,
    }
    _require(
        isinstance(authority, Mapping) and dict(authority) == expected_authority,
        "candidate_judge_authority_invalid",
    )
    budget = config.get("token_budget_basis")
    _require(isinstance(budget, Mapping), "candidate_judge_token_budget_basis_invalid")
    expected_budget_controls = {
        "max_input_characters": 40_000,
        "max_output_tokens": 2_000,
        "timeout_seconds": 120,
        "max_transport_attempts": 1,
        "retry_policy": "none",
        "truncation_stop_behavior": "fail_closed_no_partial_selection",
        "input_ceiling_behavior": "fail_before_transport",
    }
    _require(
        all(budget.get(key) == value for key, value in expected_budget_controls.items()),
        "candidate_judge_token_budget_controls_invalid",
    )
    return config


def _source_artifacts(
    config: Mapping[str, Any],
) -> tuple[Path, dict[str, Path], dict[str, str]]:
    source = config.get("source_attempt")
    _require(isinstance(source, Mapping), "candidate_judge_source_attempt_invalid")
    expected_fields = {
        "root",
        "expected_attempt_mode",
        "expected_formal_eligible",
        "manifest",
        "route_results",
        "retrieval_nodes",
        "retrieval_route",
        "top_k",
    }
    _require(set(source) == expected_fields, "candidate_judge_source_attempt_fields_invalid")
    _require(
        source.get("expected_attempt_mode") == "engineering_preview"
        and source.get("expected_formal_eligible") is False
        and source.get("retrieval_route") == "bm25"
        and source.get("top_k") == 6,
        "candidate_judge_source_attempt_contract_invalid",
    )
    source_root = Path(str(source["root"])).resolve()
    _require(source_root.is_dir(), "candidate_judge_source_attempt_root_missing")
    paths = {
        label: _resolve_artifact(source_root, source[label], label=label)
        for label in ("manifest", "route_results", "retrieval_nodes")
    }
    digests = {label: _file_sha256(path) for label, path in paths.items()}
    manifest = _read_json(paths["manifest"], code="candidate_judge_source_manifest_invalid")
    _require(
        manifest.get("attempt_mode") == source["expected_attempt_mode"]
        and manifest.get("formal_eligible") is source["expected_formal_eligible"],
        "candidate_judge_source_manifest_authority_mismatch",
    )
    return source_root, paths, digests


def _load_bm25_rows(
    route_path: Path,
    *,
    query_config: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    try:
        with route_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                value = json.loads(line)
                if not isinstance(value, dict):
                    continue
                query_id = str(value.get("query_id") or "")
                if query_id not in query_config or value.get("route") != "bm25":
                    continue
                if query_id in found:
                    raise CandidateJudgeRunError(
                        "candidate_judge_duplicate_bm25_query_result"
                    )
                found[query_id] = value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateJudgeRunError("candidate_judge_route_results_invalid") from exc
    _require(set(found) == set(query_config), "candidate_judge_bm25_query_set_invalid")
    return found


def _load_needed_nodes(path: Path, node_ids: set[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                value = json.loads(line)
                if not isinstance(value, dict):
                    continue
                node_id = str(value.get("node_id") or "")
                if node_id not in node_ids:
                    continue
                if node_id in found:
                    raise CandidateJudgeRunError("candidate_judge_node_id_duplicate")
                found[node_id] = value
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateJudgeRunError("candidate_judge_retrieval_nodes_invalid") from exc
    _require(set(found) == node_ids, "candidate_judge_retrieval_node_set_invalid")
    return found


def build_model_input(
    config: Mapping[str, Any],
    *,
    route_path: Path,
    node_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    query_rows = config["queries"]
    query_config = {str(row["query_id"]): row for row in query_rows}
    _require(
        len(query_config) == len(query_rows),
        "candidate_judge_query_identity_duplicate",
    )
    bm25_by_query = _load_bm25_rows(route_path, query_config=query_config)
    top_ids_by_query: dict[str, list[str]] = {}
    scope_receipts: dict[str, Any] = {}
    for query_id, query in query_config.items():
        route_result = bm25_by_query[query_id]
        ranking = route_result.get("ranking")
        _require(
            isinstance(ranking, list) and len(ranking) >= 6,
            "candidate_judge_bm25_ranking_too_short",
        )
        top = ranking[:6]
        _require(
            [row.get("rank") for row in top] == list(range(1, 7)),
            "candidate_judge_bm25_rank_sequence_invalid",
        )
        node_ids = [str(row.get("node_id") or "") for row in top]
        _require(
            all(node_ids) and len(node_ids) == len(set(node_ids)),
            "candidate_judge_bm25_candidate_identity_invalid",
        )
        receipt = route_result.get("retrieval_scope_receipt")
        expected_scope = {
            "issuer_ids": query["issuer_ids"],
            "fiscal_periods": query["fiscal_periods"],
            "source_roles": query["source_roles"],
        }
        _require(
            isinstance(receipt, Mapping)
            and receipt.get("scope_applied") is True
            and receipt.get("answer_free_retrieval_scope") == expected_scope,
            "candidate_judge_bm25_scope_receipt_invalid",
        )
        top_ids_by_query[query_id] = node_ids
        scope_receipts[query_id] = receipt

    all_node_ids = {node_id for rows in top_ids_by_query.values() for node_id in rows}
    _require(len(all_node_ids) == 12, "candidate_judge_cross_query_candidate_overlap")
    nodes = _load_needed_nodes(node_path, all_node_ids)
    cases: list[dict[str, Any]] = []
    for query in query_rows:
        query_id = str(query["query_id"])
        candidates: list[dict[str, Any]] = []
        for rank, node_id in enumerate(top_ids_by_query[query_id], start=1):
            node = nodes[node_id]
            candidate = {
                "node_id": node_id,
                "retrieval_rank": rank,
                "node_kind": node.get("node_kind"),
                "issuer_id": node.get("issuer_id"),
                "fiscal_period": node.get("fiscal_period"),
                "route_id": node.get("route_id"),
                "source_role": node.get("source_role"),
                "publication_date": node.get("publication_date"),
                "period_end": node.get("period_end"),
                "section_path": node.get("section_path") or [],
                "page_start": node.get("page_start"),
                "page_end": node.get("page_end"),
                "stable_url": node.get("stable_url"),
                "content": node.get("content"),
                "candidate_is_not_evidence": node.get("candidate_is_not_evidence"),
                "citation_eligible": node.get("citation_eligible"),
                "numeric_authority": node.get("numeric_authority"),
            }
            candidates.append(candidate)
        cases.append(
            {
                "query_id": query_id,
                "question_zh": query["question_zh"],
                "retrieval_query_en": query["retrieval_query_en"],
                "issuer_ids": query["issuer_ids"],
                "fiscal_periods": query["fiscal_periods"],
                "source_roles": query["source_roles"],
                "route_ids": query["route_ids"],
                "requirements": query["requirements"],
                "candidates": candidates,
            }
        )
    payload = {
        "schema_version": INPUT_SCHEMA_VERSION,
        "task": "select_minimal_sufficient_local_candidates",
        "candidate_authority": "candidate_only_not_evidence",
        "external_knowledge_allowed": False,
        "cases": cases,
    }
    validated = validate_candidate_judge_input(payload)
    return validated.model_dump(mode="json"), scope_receipts


def prepare_attempt(
    *,
    config_path: Path,
    profile_path: Path,
) -> dict[str, Any]:
    config = load_candidate_judge_config(config_path)
    profile_payload = _read_json(profile_path, code="candidate_judge_profile_invalid")
    profile = load_chat_completion_profile(profile_payload)
    _require(
        profile.provider_id == "deepseek"
        and profile.model == "deepseek-v4-pro"
        and profile.base_url == "https://api.deepseek.com"
        and profile.endpoint == "/chat/completions"
        and profile.api_key_env == "DEEPSEEK_API_KEY"
        and profile.timeout_seconds == 120
        and profile.request_defaults
        == {
            "max_tokens": 2000,
            "stream": False,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
        },
        "candidate_judge_profile_contract_invalid",
    )
    source_root, paths, source_digests = _source_artifacts(config)
    model_input_value, scope_receipts = build_model_input(
        config,
        route_path=paths["route_results"],
        node_path=paths["retrieval_nodes"],
    )
    model_input = validate_candidate_judge_input(model_input_value)
    messages = build_candidate_judge_messages(model_input)
    total_input_characters = sum(len(row["content"]) for row in messages)
    max_input_characters = int(config["token_budget_basis"]["max_input_characters"])
    _require(
        total_input_characters <= max_input_characters,
        "candidate_judge_input_character_limit_exceeded",
    )
    _require(
        not find_banned_qrel_input_keys(model_input_value),
        "candidate_judge_qrel_label_leakage",
    )
    return {
        "config": config,
        "profile": profile,
        "source_root": source_root,
        "source_paths": paths,
        "source_digests": source_digests,
        "model_input": model_input,
        "model_input_value": model_input_value,
        "messages": messages,
        "input_characters": total_input_characters,
        "scope_receipts": scope_receipts,
        "config_sha256": _file_sha256(config_path),
        "profile_sha256": _file_sha256(profile_path),
    }


def _git_projection() -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return completed.stdout.strip()

    try:
        status = run("status", "--porcelain")
        return {
            "branch": run("branch", "--show-current"),
            "head": run("rev-parse", "HEAD"),
            "dirty": bool(status),
        }
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CandidateJudgeRunError("candidate_judge_git_projection_failed") from exc


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _failure_code(exc: BaseException) -> str:
    if isinstance(exc, ModelGatewayError):
        return exc.code
    return str(exc) or type(exc).__name__


def _finish_failure(
    *,
    attempt_root: Path,
    run_id: str,
    attempt_id: str,
    prepared: Mapping[str, Any],
    exc: BaseException,
    provider_function_entered: bool,
) -> NoReturn:
    capture_ref = exc.capture_ref if isinstance(exc, ModelGatewayError) else ""
    capture_dir = attempt_root / "provider_capture"
    request_capture_exists = any(capture_dir.rglob("model_visible_request.json"))
    response_capture_exists = any(capture_dir.rglob("provider_response.json"))
    failure = {
        "schema_version": FAILURE_SCHEMA_VERSION,
        "status": "terminal_failed_candidate_only_no_retry",
        "recorded_at": _utc_now(),
        "run_id": run_id,
        "attempt_id": attempt_id,
        "error_type": type(exc).__name__,
        "error_code": _failure_code(exc),
        "capture_ref": capture_ref,
        "provider_function_entered": provider_function_entered,
        "provider_request_capture_exists": request_capture_exists,
        "provider_response_capture_exists": response_capture_exists,
        "retry_count": 0,
        "fallback_model_used": False,
        "candidate_selection_promoted": False,
        "evidence_promotion_authorized": False,
        "formal_qualification_claimed": False,
        "source_attempt_mutated": False,
        "model_input_sha256": _digest(prepared["model_input_value"]),
        "credential_or_authorization_captured": False,
    }
    _write_new_json(attempt_root / "terminal_failure.json", failure)
    print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
    raise SystemExit(1)


def execute_attempt(
    *,
    config_path: Path,
    profile_path: Path,
    attempt_root: Path,
    run_id: str,
    attempt_id: str,
) -> dict[str, Any]:
    prepared = prepare_attempt(config_path=config_path, profile_path=profile_path)
    credential_present = bool(os.environ.get(prepared["profile"].api_key_env, "").strip())
    _require(credential_present, "candidate_judge_provider_credential_missing")
    try:
        attempt_root.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise CandidateJudgeRunError("candidate_judge_attempt_root_exists") from exc

    implementation_paths = {
        "runner": Path(__file__).resolve(),
        "contract": (
            ROOT / "src/sec_agent/agent_runtime/bounded_candidate_judge.py"
        ).resolve(),
        "transport": (
            ROOT / "src/sec_agent/providers/chat_completions.py"
        ).resolve(),
    }
    preflight = {
        "schema_version": ATTEMPT_SCHEMA_VERSION,
        "status": "preflight_passed_provider_not_yet_called",
        "recorded_at": _utc_now(),
        "run_id": run_id,
        "attempt_id": attempt_id,
        "case_id": prepared["config"]["case_id"],
        "git": _git_projection(),
        "config_ref": config_path.resolve().as_posix(),
        "config_sha256": prepared["config_sha256"],
        "profile_ref": profile_path.resolve().as_posix(),
        "profile_sha256": prepared["profile_sha256"],
        "implementation_sha256": {
            label: _file_sha256(path) for label, path in implementation_paths.items()
        },
        "source_attempt_root": prepared["source_root"].as_posix(),
        "source_artifact_sha256": prepared["source_digests"],
        "source_attempt_mutation_authorized": False,
        "source_attempt_mutated": False,
        "query_count": 2,
        "candidate_count": 12,
        "candidate_count_per_query": 6,
        "model_input_sha256": _digest(prepared["model_input_value"]),
        "model_visible_input_characters": prepared["input_characters"],
        "max_input_characters": prepared["config"]["token_budget_basis"][
            "max_input_characters"
        ],
        "qrel_label_keys_in_model_input": list(
            find_banned_qrel_input_keys(prepared["model_input_value"])
        ),
        "credential_presence_checked": True,
        "credential_present": True,
        "credential_or_authorization_captured": False,
        "provider_attempt_ceiling": 1,
        "provider_attempts_completed": 0,
        "retry_count": 0,
        "fallback_model_allowed": False,
        "external_knowledge_allowed": False,
        "candidate_only": True,
        "evidence_promotion_authorized": False,
        "formal_qualification_claimed": False,
        "token_budget_basis": prepared["config"]["token_budget_basis"],
    }
    _write_new_json(attempt_root / "preflight_manifest.json", preflight)
    _write_new_json(attempt_root / "model_input.json", prepared["model_input_value"])

    provider_function_entered = False
    try:
        provider_function_entered = True
        gateway_result = execute_chat_completion_exact_once(
            profile=prepared["profile"],
            messages=prepared["messages"],
            capture_root=attempt_root / "provider_capture",
            run_id=run_id,
            attempt_id=attempt_id,
        )
        _require(
            gateway_result.finish_reason == "stop",
            "candidate_judge_finish_reason_invalid",
        )
        try:
            raw_output = json.loads(
                gateway_result.content,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"non-finite JSON constant: {value}")
                ),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise CandidateJudgeRunError("candidate_judge_response_json_invalid") from exc
        validated_output = validate_candidate_judge_output(
            raw_output,
            model_input=prepared["model_input"],
        )
        for label, path in prepared["source_paths"].items():
            _require(
                _file_sha256(path) == prepared["source_digests"][label],
                "candidate_judge_source_artifact_changed_during_call",
            )
        result = {
            "schema_version": RESULT_SCHEMA_VERSION,
            "status": "completed_exact_once_candidate_only",
            "completed_at": _utc_now(),
            "run_id": run_id,
            "attempt_id": attempt_id,
            "source_attempt_root": prepared["source_root"].as_posix(),
            "source_attempt_mutated": False,
            "source_artifact_sha256": prepared["source_digests"],
            "model_input_sha256": _digest(prepared["model_input_value"]),
            "model_output": validated_output.model_dump(mode="json"),
            "model_output_sha256": _digest(
                validated_output.model_dump(mode="json")
            ),
            "provider": gateway_result.provider_id,
            "model": gateway_result.model,
            "finish_reason": gateway_result.finish_reason,
            "usage": dict(gateway_result.usage),
            "request_capture_ref": gateway_result.request_capture_ref,
            "response_capture_ref": gateway_result.response_capture_ref,
            "request_digest": gateway_result.request_digest,
            "response_digest": gateway_result.response_digest,
            "private_reasoning_fields_redacted": (
                gateway_result.private_reasoning_fields_redacted
            ),
            "provider_attempts_completed": 1,
            "retry_count": 0,
            "fallback_model_used": False,
            "external_knowledge_used": False,
            "candidate_selection_promoted": False,
            "candidate_authority": "candidate_only_not_evidence",
            "evidence_promotion_authorized": False,
            "formal_qualification_claimed": False,
            "credential_or_authorization_captured": False,
        }
        _write_new_json(attempt_root / "result.json", result)
        return result
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        _finish_failure(
            attempt_root=attempt_root,
            run_id=run_id,
            attempt_id=attempt_id,
            prepared=prepared,
            exc=exc,
            provider_function_entered=provider_function_entered,
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--run-id", default="DELL-RAG-BOUNDED-CANDIDATE-JUDGE")
    parser.add_argument("--attempt-id", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = execute_attempt(
        config_path=args.config.resolve(),
        profile_path=args.profile.resolve(),
        attempt_root=args.attempt_root.resolve(),
        run_id=str(args.run_id),
        attempt_id=str(args.attempt_id),
    )
    summary = {
        "status": result["status"],
        "attempt_id": result["attempt_id"],
        "attempt_root": args.attempt_root.resolve().as_posix(),
        "provider_attempts_completed": result["provider_attempts_completed"],
        "retry_count": result["retry_count"],
        "usage": result["usage"],
        "model_output_sha256": result["model_output_sha256"],
        "judgments": [
            {
                "query_id": row["query_id"],
                "decision": row["decision"],
                "selected_node_ids": row["selected_node_ids"],
                "confidence": row["confidence"],
            }
            for row in result["model_output"]["judgments"]
        ],
        "candidate_authority": result["candidate_authority"],
        "formal_qualification_claimed": False,
    }
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
