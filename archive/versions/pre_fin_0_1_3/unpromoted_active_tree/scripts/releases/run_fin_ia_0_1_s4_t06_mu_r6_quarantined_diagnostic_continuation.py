from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    CaseNumericAuthorityPolicy,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    resolve_s4_case_runtime_binding_for_admission,
)
from apps.workbench.backend.application.research_runtime import (
    prepare_s4_source_grounded_exact_input,
)
from scripts.releases.run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution import (
    _principal,
    _services,
    load_execution_target,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import load_s4_source_grounded_input_pack


DECISION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_"
    "continuation_and_aggregate_defect_surface_decision_v1_0.json"
)
ADMISSION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6.json"
)
ISSUANCE = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_action_planning_temporal_"
    "authority_and_capture_v2_terminal_result_materialization_fresh_"
    "exact_admission_r6_issuance_v1_0.json"
)
R6_FAILURE_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_temporal_authority_terminal_"
    "result_r6_exact_live_execution_failure_result_v1_0.json"
)
SOURCE_RUNTIME_ROOT = ROOT / (
    ".codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-"
    "validation-r1"
)
R6_RUNTIME_RESULT = SOURCE_RUNTIME_ROOT / (
    "s4_t06_mu_temporal_authority_terminal_result_r6_live_execution_"
    "result.json"
)
DEFAULT_OUTPUT_ROOT = ROOT / (
    ".codex_runtime/fin01-s4-t06-mu-r6-quarantined-diagnostic-"
    "continuation-r1"
)
EXPECTED_ADMISSION_SHA256 = (
    "f5f031b5a470c6df2ee0aad6496f1277132b175da7ff4ce5c2fcb938ec607e17"
)
EXPECTED_ADMISSION_DIGEST = (
    "a30d6977df984f1002ec95992c3e6d3bf8e7a7271dd54a626bb5271315bb2ac3"
)
EXPECTED_FAILURE_RESULT_SHA256 = (
    "9be9a675d02814c528cbac8cdbe289b43fdf9618e44975d070726decc985c991"
)
DIAGNOSTIC_RESEARCH_RUN_ID = (
    "diagnostic_research_run_fin01_s4_t06_mu_r6_collect_all_r1"
)
MAXIMUM_NEW_LIVE_CALLS = 8
MAXIMUM_UNIQUE_INTERACTIONS = 12
MAXIMUM_NEW_LIVE_COST_USD = 0.1
NUMERIC_PLACEHOLDER = (
    "Selected numeric aliases are rendered locally; this Provider text is "
    "non-authoritative."
)
DIAGNOSTIC_PLACEHOLDER = (
    "This narrative item is quarantined; material values remain locally owned."
)
NONLOCAL_CASE_MARKER = "registered nonlocal case"
MAXIMUM_REPAIR_FINDINGS = 96
_ALIAS_PATTERN = re.compile(r"^N[0-9]{3}$")
_PATH_TOKEN = re.compile(r"\.([A-Za-z0-9_]+)|\[([0-9]+)\]")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"diagnostic_json_object_required:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json_digest(value: Any) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _path_ref(path: Path) -> str:
    try:
        value = path.relative_to(ROOT)
    except ValueError:
        value = path
    return str(value).replace("\\", "/")


def _assistant_digest(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for item in value.values():
            found.extend(_walk_mappings(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            found.extend(_walk_mappings(item))
    return found


def _numeric_classifier(
    request: Mapping[str, Any],
) -> CaseNumericAuthorityPolicy | None:
    policies: list[CaseNumericAuthorityPolicy] = []
    seen: set[str] = set()
    for candidate in _walk_mappings(request):
        contract_ref = str(candidate.get("contract_ref") or "")
        if not contract_ref.startswith(
            "fin01.s4.case_numeric_authority_projection_and_"
            "deterministic_rendering:"
        ):
            continue
        digest = _json_digest(candidate)
        if digest in seen:
            continue
        seen.add(digest)
        try:
            policies.append(
                CaseNumericAuthorityPolicy.from_prompt_contract(candidate)
            )
        except (TypeError, ValueError):
            continue
    if not policies:
        return None
    if len(policies) == 1:
        return policies[0]
    return CaseNumericAuthorityPolicy.combined_narrative_classifier(policies)


def _path_tokens(path: str) -> list[str | int]:
    if not path.startswith("$"):
        raise ValueError("diagnostic_json_path_invalid")
    tokens: list[str | int] = []
    for match in _PATH_TOKEN.finditer(path[1:]):
        if match.group(1) is not None:
            tokens.append(match.group(1))
        else:
            tokens.append(int(match.group(2)))
    return tokens


def _get_path(value: Any, path: str) -> Any:
    current = value
    for token in _path_tokens(path):
        if isinstance(token, int):
            if not isinstance(current, list):
                raise ValueError("diagnostic_json_path_list_expected")
            current = current[token]
        else:
            if not isinstance(current, Mapping):
                raise ValueError("diagnostic_json_path_mapping_expected")
            current = current[token]
    return current


def _set_path(value: Any, path: str, replacement: Any) -> None:
    tokens = _path_tokens(path)
    if not tokens:
        raise ValueError("diagnostic_root_replacement_forbidden")
    current = value
    for token in tokens[:-1]:
        current = current[token]
    current[tokens[-1]] = replacement


def _parent_numeric_fact(value: Any, path: str) -> Mapping[str, Any] | None:
    match = re.fullmatch(r"\$\.fact_layer\[([0-9]+)\]\.statement", path)
    if match is None:
        return None
    facts = value.get("fact_layer") if isinstance(value, Mapping) else None
    index = int(match.group(1))
    if not isinstance(facts, list) or index >= len(facts):
        return None
    fact = facts[index]
    if not isinstance(fact, Mapping) or fact.get("support_type") != "Numeric":
        return None
    refs = fact.get("support_refs")
    if (
        not isinstance(refs, list)
        or not refs
        or any(
            not isinstance(ref, str) or _ALIAS_PATTERN.fullmatch(ref) is None
            for ref in refs
        )
    ):
        return None
    return fact


def _identity_projection(
    request: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    for candidate in _walk_mappings(request):
        contract_ref = str(candidate.get("contract_ref") or "")
        if (
            contract_ref.startswith(
                "fin01.s4.case_delivery_identity_current_case_aware_"
                "provider_boundary:"
            )
            and isinstance(candidate.get("registered_case_tickers"), list)
            and isinstance(candidate.get("case_ticker"), str)
        ):
            return candidate
    return None


def _walk_strings(
    value: Any,
    *,
    path: str = "$",
) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            found.extend(_walk_strings(item, path=f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_strings(item, path=f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append((path, value))
    return found


def _repair_json_output(
    *,
    stage: str,
    request: Mapping[str, Any],
    assistant_output_text: str,
) -> tuple[str, list[dict[str, Any]]]:
    duplicate_keys: list[str] = []

    def reject_or_project_duplicates(
        pairs: Sequence[tuple[str, Any]],
    ) -> dict[str, Any]:
        projected: dict[str, Any] = {}
        for key, item in pairs:
            if key in projected:
                duplicate_keys.append(str(key))
                continue
            projected[str(key)] = item
        return projected

    try:
        output = json.loads(
            assistant_output_text,
            object_pairs_hook=reject_or_project_duplicates,
        )
    except json.JSONDecodeError:
        return assistant_output_text, []
    if not isinstance(output, dict):
        return assistant_output_text, []

    findings: list[dict[str, Any]] = []
    for key in sorted(set(duplicate_keys)):
        findings.append(
            {
                "stage": stage,
                "repair_code": "duplicate_key_first_value_projection",
                "field_path": "$",
                "detail": key,
                "acceptance_eligible": False,
            }
        )

    required_keys = request.get("required_top_level_keys")
    if isinstance(required_keys, list) and all(
        isinstance(key, str) for key in required_keys
    ):
        allowed = set(required_keys)
        for key in sorted(set(output).difference(allowed)):
            del output[key]
            findings.append(
                {
                    "stage": stage,
                    "repair_code": "unrequested_top_level_key_pruned",
                    "field_path": f"$.{key}",
                    "acceptance_eligible": False,
                }
            )

    constraints = request.get("output_constraints")
    if isinstance(constraints, Mapping):
        for key, raw in constraints.items():
            if not str(key).endswith("_cardinality") or not isinstance(
                raw, str
            ):
                continue
            match = re.fullmatch(r"([0-9]+)\.\.([0-9]+)", raw.strip())
            field = str(key)[: -len("_cardinality")]
            items = output.get(field)
            if (
                match is not None
                and isinstance(items, list)
                and len(items) > int(match.group(2))
            ):
                before = len(items)
                maximum = int(match.group(2))
                selection_policy = "stable_input_order"
                if field == "judgment_layer":
                    prior = request.get("validated_prior_segments")
                    facts_segment = (
                        prior.get("facts_explanation_and_terminal")
                        if isinstance(prior, Mapping)
                        else None
                    )
                    facts = (
                        facts_segment.get("fact_layer")
                        if isinstance(facts_segment, Mapping)
                        else None
                    )
                    locally_assemblable_aliases = {
                        str(fact.get("fact_alias") or "")
                        for fact in facts or ()
                        if (
                            isinstance(fact, Mapping)
                            and isinstance(
                                fact.get(
                                    "locally_assembled_scope_summary"
                                ),
                                Mapping,
                            )
                            and fact[
                                "locally_assembled_scope_summary"
                            ].get("business_scope")
                            != "mixed"
                        )
                    }

                    def local_scope_rank(
                        indexed: tuple[int, Any],
                    ) -> tuple[int, int]:
                        index, item = indexed
                        if not isinstance(item, Mapping):
                            return (3, index)
                        aliases = item.get("support_fact_aliases")
                        if (
                            isinstance(aliases, list)
                            and bool(aliases)
                            and all(
                                isinstance(alias, str)
                                and alias in locally_assemblable_aliases
                                for alias in aliases
                            )
                        ):
                            return (0, index)
                        if (
                            item.get("epistemic_status")
                            == "cannot_infer"
                            and aliases == []
                        ):
                            return (1, index)
                        return (2, index)

                    output[field] = [
                        item
                        for _, item in sorted(
                            enumerate(items),
                            key=local_scope_rank,
                        )[:maximum]
                    ]
                    selection_policy = (
                        "existing_candidate_local_scope_assemblability_"
                        "then_stable_input_order"
                    )
                else:
                    output[field] = items[:maximum]
                findings.append(
                    {
                        "stage": stage,
                        "repair_code": "explicit_array_max_projection",
                        "field_path": f"$.{field}",
                        "observed_count": before,
                        "projected_count": len(output[field]),
                        "selection_policy": selection_policy,
                        "acceptance_eligible": False,
                    }
                )

    classifier = _numeric_classifier(request)
    if classifier is not None:
        matches = classifier.provider_narrative_matches(output)
        terminal_paths = sorted(
            {match.field_path for match in matches if match.terminal}
        )
        for path in terminal_paths:
            fact = _parent_numeric_fact(output, path)
            replacement = (
                NUMERIC_PLACEHOLDER
                if fact is not None
                else DIAGNOSTIC_PLACEHOLDER
            )
            _set_path(output, path, replacement)
            semantic_classes = sorted(
                {
                    match.semantic_class
                    for match in matches
                    if match.field_path == path and match.terminal
                }
            )
            findings.append(
                {
                    "stage": stage,
                    "repair_code": (
                        "numeric_fact_alias_preserving_local_projection"
                        if fact is not None
                        else "material_numeric_narrative_quarantined"
                    ),
                    "field_path": path,
                    "semantic_classes": semantic_classes,
                    "selected_numeric_aliases": (
                        list(fact.get("support_refs") or ())
                        if fact is not None
                        else []
                    ),
                    "acceptance_eligible": False,
                }
            )

    projection = _identity_projection(request)
    if projection is not None:
        current = str(projection["case_ticker"])
        registered = {
            str(item)
            for item in projection["registered_case_tickers"]
            if isinstance(item, str) and str(item) != current
        }
        for path, text in _walk_strings(output):
            replacement = text
            matched: list[str] = []
            for ticker in sorted(registered):
                pattern = re.compile(
                    rf"(?<![A-Za-z0-9_]){re.escape(ticker)}"
                    rf"(?![A-Za-z0-9_])",
                    re.IGNORECASE,
                )
                if pattern.search(replacement):
                    matched.append(ticker)
                    replacement = pattern.sub(NONLOCAL_CASE_MARKER, replacement)
            if matched:
                _set_path(output, path, replacement)
                findings.append(
                    {
                        "stage": stage,
                        "repair_code": "registered_nonlocal_case_quarantined",
                        "field_path": path,
                        "registered_nonlocal_case_tickers": matched,
                        "acceptance_eligible": False,
                    }
                )

    max_chars = (
        constraints.get("maximum_narrative_item_unicode_characters")
        if isinstance(constraints, Mapping)
        else None
    )
    if isinstance(max_chars, int) and max_chars >= 64:
        narrative_fields = CaseNumericAuthorityPolicy._NARRATIVE_FIELDS
        for path, text in _walk_strings(output):
            field = (
                _path_tokens(path)[-1]
                if _path_tokens(path)
                else ""
            )
            if (
                isinstance(field, str)
                and field in narrative_fields
                and len(text) > max_chars
            ):
                suffix = " [diagnostic length projection]"
                _set_path(
                    output,
                    path,
                    text[: max_chars - len(suffix)] + suffix,
                )
                findings.append(
                    {
                        "stage": stage,
                        "repair_code": "narrative_length_projection",
                        "field_path": path,
                        "observed_characters": len(text),
                        "projected_characters": max_chars,
                        "acceptance_eligible": False,
                    }
                )

    if not findings:
        return assistant_output_text, []
    if len(findings) > MAXIMUM_REPAIR_FINDINGS:
        raise RuntimeError("diagnostic_repair_finding_cap_exceeded")
    repaired = json.dumps(
        output,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    original_digest = _assistant_digest(assistant_output_text)
    repaired_digest = _assistant_digest(repaired)
    for finding in findings:
        finding["original_assistant_output_digest"] = original_digest
        finding["repaired_assistant_output_digest"] = repaired_digest
        finding["original_text_persisted_in_manifest"] = False
        finding["repaired_text_persisted_in_manifest"] = False
    return repaired, findings


def _receipt_envelope(
    *,
    receipt: Mapping[str, Any],
    assistant_output_text: str,
) -> dict[str, Any]:
    return {
        "call_id": str(receipt.get("call_id") or ""),
        "provider": str(receipt.get("provider") or "deepseek"),
        "model": str(receipt.get("model") or "deepseek-v4-pro"),
        "status": str(receipt.get("status") or "ok"),
        "finish_reason": receipt.get("finish_reason"),
        "content": assistant_output_text,
        "input_tokens": int(receipt.get("input_tokens") or 0),
        "output_tokens": int(receipt.get("output_tokens") or 0),
        "total_tokens": int(receipt.get("total_tokens") or 0),
        "latency_ms": int(receipt.get("latency_ms") or 0),
        "transport_attempt_count": int(
            receipt.get("transport_attempt_count") or 1
        ),
        "raw_response": {
            "usage": {
                "prompt_cache_hit_tokens": int(
                    receipt.get("input_cache_hit_tokens") or 0
                ),
                "prompt_cache_miss_tokens": int(
                    receipt.get("input_cache_miss_tokens") or 0
                ),
            }
        },
    }


def _capture_path(object_digest: str) -> Path:
    return (
        SOURCE_RUNTIME_ROOT
        / "canonical-runtime/objects/fin01/provider-output-captures"
        / object_digest[:2]
        / object_digest[2:4]
        / f"{object_digest}.json"
    )


def _load_R6_seed_interactions() -> dict[str, dict[str, Any]]:
    result = _load_json(R6_RUNTIME_RESULT)
    captures = (
        result.get("provider_execution", {})
        .get("provider_output_capture", {})
    )
    digests = captures.get("object_digests") or []
    receipts = result.get("provider_execution", {}).get(
        "usage_receipts"
    ) or []
    receipt_by_stage = {
        str(receipt.get("stage") or ""): receipt
        for receipt in receipts
        if isinstance(receipt, Mapping)
    }
    if len(digests) != 4 or len(receipt_by_stage) != 4:
        raise RuntimeError("diagnostic_R6_seed_count_invalid")
    seeded: dict[str, dict[str, Any]] = {}
    for digest in digests:
        capture = _load_json(_capture_path(str(digest)))
        stage = str(capture.get("stage") or "")
        receipt = receipt_by_stage.get(stage)
        if not stage or receipt is None:
            raise RuntimeError("diagnostic_R6_seed_stage_unbound")
        request = capture.get("model_visible_request")
        text = capture.get("assistant_output_text")
        if not isinstance(request, list) or not isinstance(text, str):
            raise RuntimeError("diagnostic_R6_seed_capture_incomplete")
        seeded[stage] = {
            "source": "immutable_R6_capture_v2",
            "model_visible_request": request,
            "model_visible_request_digest": str(
                capture.get("model_visible_request_digest") or ""
            ),
            "assistant_output_text": text,
            "assistant_output_digest": _assistant_digest(text),
            "envelope": _receipt_envelope(
                receipt=receipt,
                assistant_output_text=text,
            ),
            "capture_object_digest": str(digest),
        }
    return seeded


@contextmanager
def _diagnostic_local_numeric_text_capacity_projection(
    findings: list[dict[str, Any]],
) -> Any:
    original = (
        DeepSeekS3ThreeCellNodeExecutor
        ._validate_segment_narrative_text
    )
    original_facts = (
        DeepSeekS3ThreeCellNodeExecutor
        ._validate_facts_explanation_and_terminal_segment
    )
    original_specialist = (
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output
    )
    original_projected_cost = (
        DeepSeekS3ThreeCellNodeExecutor._projected_cost
    )

    def projected(
        cls: type[DeepSeekS3ThreeCellNodeExecutor],
        segment_id: str,
        output: Mapping[str, Any],
        *,
        maximum_characters: int = 320,
    ) -> None:
        if segment_id != "facts_explanation_and_terminal":
            original(
                segment_id,
                output,
                maximum_characters=maximum_characters,
            )
            return
        values: list[Any] = []
        facts = output.get("fact_layer")
        if isinstance(facts, list):
            for fact in facts:
                if isinstance(fact, Mapping):
                    values.extend(
                        fact[key]
                        for key in ("statement", "boundary")
                        if key in fact
                    )
        for field_id in ("explanation_layer", "remaining_gaps"):
            items = output.get(field_id)
            if isinstance(items, list):
                values.extend(items)
        if any(
            not isinstance(value, str) or not value.strip()
            for value in values
        ):
            original(
                segment_id,
                output,
                maximum_characters=maximum_characters,
            )
            return
        over_limit = [
            value for value in values if len(value) > maximum_characters
        ]
        if over_limit:
            projected_maximum = max(len(value) for value in over_limit)
            marker = (
                "local_numeric_rendering_vs_legacy_text_limit_collision",
                segment_id,
                "fact_layer.statement_or_boundary",
            )
            existing = {
                (
                    row.get("repair_code"),
                    row.get("segment_id"),
                    row.get("field_id"),
                )
                for row in findings
            }
            if marker not in existing:
                findings.append(
                    {
                        "repair_code": marker[0],
                        "segment_id": segment_id,
                        "field_id": marker[2],
                        "legacy_maximum_characters": maximum_characters,
                        "diagnostic_projected_maximum_characters": (
                            projected_maximum
                        ),
                        "failing_item_count": len(over_limit),
                        "provider_narrative_limit_relaxed": False,
                        "exact_local_rendering_limit_relaxed": True,
                        "acceptance_eligible": False,
                    }
                )
        return

    (
        DeepSeekS3ThreeCellNodeExecutor
        ._validate_segment_narrative_text
    ) = classmethod(projected)

    def projected_facts(
        output: Mapping[str, Any],
        cell_input: Mapping[str, Any],
    ) -> None:
        validation_view = deepcopy(dict(output))
        facts = validation_view.get("fact_layer")
        if isinstance(facts, list):
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                for key in ("statement", "boundary"):
                    value = fact.get(key)
                    if (
                        isinstance(value, str)
                        and len(value) > 320
                    ):
                        fact[key] = DIAGNOSTIC_PLACEHOLDER
        original_facts(validation_view, cell_input)

    (
        DeepSeekS3ThreeCellNodeExecutor
        ._validate_facts_explanation_and_terminal_segment
    ) = staticmethod(projected_facts)

    def projected_specialist(
        output: Mapping[str, Any],
        cell_input: Mapping[str, Any],
        **kwargs: Any,
    ) -> None:
        validation_view = deepcopy(dict(output))
        facts = validation_view.get("fact_layer")
        if isinstance(facts, list):
            for fact in facts:
                if not isinstance(fact, dict):
                    continue
                for key in ("statement", "boundary"):
                    value = fact.get(key)
                    if isinstance(value, str) and len(value) > 320:
                        fact[key] = DIAGNOSTIC_PLACEHOLDER
        original_specialist(
            validation_view,
            cell_input,
            **kwargs,
        )

    S3ThreeCellBoundedAgentExecutor._validate_specialist_output = (
        staticmethod(projected_specialist)
    )

    def projected_cost(
        input_bytes: int,
        max_output_tokens: int,
        admission: S3ThreeCellBoundedAgentAdmission,
    ) -> float:
        marker = "diagnostic_byte_to_token_projected_cost_correction"
        if not any(
            row.get("repair_code") == marker for row in findings
        ):
            findings.append(
                {
                    "repair_code": marker,
                    "source_estimator_input_unit": "utf8_bytes",
                    "provider_pricing_input_unit": "tokens",
                    "diagnostic_byte_to_token_divisor": 4,
                    "actual_cost_hard_cap_unchanged": True,
                    "acceptance_eligible": False,
                }
            )
        projected_input_tokens = max(1, (input_bytes + 3) // 4)
        return original_projected_cost(
            projected_input_tokens,
            max_output_tokens,
            admission,
        )

    DeepSeekS3ThreeCellNodeExecutor._projected_cost = staticmethod(
        projected_cost
    )
    try:
        yield
    finally:
        (
            DeepSeekS3ThreeCellNodeExecutor
            ._validate_segment_narrative_text
        ) = classmethod(original.__func__)
        (
            DeepSeekS3ThreeCellNodeExecutor
            ._validate_facts_explanation_and_terminal_segment
        ) = staticmethod(original_facts)
        S3ThreeCellBoundedAgentExecutor._validate_specialist_output = (
            staticmethod(original_specialist)
        )
        DeepSeekS3ThreeCellNodeExecutor._projected_cost = staticmethod(
            original_projected_cost
        )


class QuarantinedCompletionCache:
    def __init__(
        self,
        *,
        output_root: Path,
        seeded: Mapping[str, Mapping[str, Any]],
        live_completion: Callable[..., Mapping[str, Any]],
        maximum_new_live_calls: int = MAXIMUM_NEW_LIVE_CALLS,
    ) -> None:
        self.output_root = output_root
        self.seeded = {key: dict(value) for key, value in seeded.items()}
        self.live_completion = live_completion
        self.maximum_new_live_calls = maximum_new_live_calls
        self.live_cache: dict[str, dict[str, Any]] = {}
        self.repair_findings: list[dict[str, Any]] = []
        self.callback_count = 0
        self.seed_replay_count = 0
        self.live_replay_count = 0
        self.new_live_call_count = 0
        self._load_existing_live_cache()

    def _load_existing_live_cache(self) -> None:
        interaction_root = self.output_root / "restricted_interactions"
        if not interaction_root.exists():
            return
        for path in sorted(interaction_root.glob("*/*/*.json")):
            record = _load_json(path)
            if record.get("schema_version") != (
                "fin_ia_0_1_s4_t06_quarantined_diagnostic_interaction_v1_0"
            ):
                raise RuntimeError("diagnostic_live_cache_schema_invalid")
            if record.get("source") != "new_live_provider_call":
                raise RuntimeError("diagnostic_live_cache_source_invalid")
            digest = _json_digest(record)
            if path.stem != digest:
                raise RuntimeError("diagnostic_live_cache_digest_invalid")
            stage = str(record.get("stage") or "")
            request = record.get("model_visible_request")
            request_digest = str(
                record.get("model_visible_request_digest") or ""
            )
            if (
                not stage
                or not isinstance(request, list)
                or request_digest != _json_digest(request)
            ):
                raise RuntimeError("diagnostic_live_cache_request_invalid")
            cached = {
                **record,
                "interaction_object_digest": digest,
                "interaction_object_ref": _path_ref(path),
            }
            existing = self.live_cache.get(stage)
            if (
                existing is not None
                and existing.get("interaction_object_digest") != digest
            ):
                raise RuntimeError(
                    f"diagnostic_live_cache_stage_ambiguous:{stage}"
                )
            self.live_cache[stage] = cached

    def _persist_interaction(
        self,
        *,
        stage: str,
        messages: Sequence[Mapping[str, Any]],
        result: Mapping[str, Any],
    ) -> dict[str, Any]:
        content = result.get("content")
        if not isinstance(content, str):
            raise RuntimeError("diagnostic_live_assistant_output_missing")
        record = {
            "schema_version": (
                "fin_ia_0_1_s4_t06_quarantined_diagnostic_interaction_v1_0"
            ),
            "access_class": "internal_restricted_diagnostic_audit",
            "stage": stage,
            "source": "new_live_provider_call",
            "model_visible_request": [dict(item) for item in messages],
            "model_visible_request_digest": _json_digest(messages),
            "assistant_output_text": content,
            "assistant_output_digest": _assistant_digest(content),
            "safe_envelope": {
                key: result.get(key)
                for key in (
                    "call_id",
                    "provider",
                    "model",
                    "status",
                    "finish_reason",
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "latency_ms",
                    "transport_attempt_count",
                )
            },
            "credential_value_persisted": False,
            "private_reasoning_persisted": False,
            "raw_provider_response_persisted": False,
            "business_artifact_promotion_allowed": False,
        }
        digest = _json_digest(record)
        path = (
            self.output_root
            / "restricted_interactions"
            / digest[:2]
            / digest[2:4]
            / f"{digest}.json"
        )
        _write_json(path, record)
        cached = {
            **record,
            "interaction_object_digest": digest,
            "interaction_object_ref": _path_ref(path),
        }
        self.live_cache[stage] = cached
        return cached

    @staticmethod
    def _replay_envelope(cached: Mapping[str, Any]) -> dict[str, Any]:
        if "envelope" in cached:
            return deepcopy(dict(cached["envelope"]))
        safe = cached.get("safe_envelope")
        if not isinstance(safe, Mapping):
            raise RuntimeError("diagnostic_live_cache_envelope_missing")
        return {
            **dict(safe),
            "content": str(cached.get("assistant_output_text") or ""),
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": int(
                        safe.get("input_tokens") or 0
                    ),
                }
            },
        }

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        self.callback_count += 1
        trace = kwargs.get("trace_tags")
        messages = kwargs.get("messages")
        if not isinstance(trace, Mapping) or not isinstance(messages, list):
            raise RuntimeError("diagnostic_completion_request_invalid")
        stage = str(trace.get("stage") or "")
        if not stage:
            raise RuntimeError("diagnostic_completion_stage_missing")
        request_digest = _json_digest(messages)

        if stage in self.seeded:
            cached = self.seeded[stage]
            expected_messages = cached.get("model_visible_request")
            if expected_messages != messages:
                raise RuntimeError(
                    f"diagnostic_R6_seed_request_drift:{stage}"
                )
            envelope = self._replay_envelope(cached)
            self.seed_replay_count += 1
        elif stage in self.live_cache:
            cached = self.live_cache[stage]
            if cached.get("model_visible_request_digest") != request_digest:
                raise RuntimeError(
                    f"diagnostic_live_cache_request_drift:{stage}"
                )
            envelope = self._replay_envelope(cached)
            self.live_replay_count += 1
        else:
            if self.new_live_call_count >= self.maximum_new_live_calls:
                raise RuntimeError("diagnostic_new_live_call_cap_exceeded")
            result = self.live_completion(**kwargs)
            if not isinstance(result, Mapping):
                raise RuntimeError("diagnostic_live_provider_envelope_invalid")
            self.new_live_call_count += 1
            cached = self._persist_interaction(
                stage=stage,
                messages=messages,
                result=result,
            )
            envelope = deepcopy(dict(result))

        user_content = messages[-1].get("content")
        try:
            request = json.loads(str(user_content))
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "diagnostic_model_visible_user_request_invalid"
            ) from exc
        if not isinstance(request, dict):
            raise RuntimeError(
                "diagnostic_model_visible_user_request_not_object"
            )
        original = envelope.get("content")
        if not isinstance(original, str):
            raise RuntimeError("diagnostic_assistant_output_missing")
        repaired, findings = _repair_json_output(
            stage=stage,
            request=request,
            assistant_output_text=original,
        )
        envelope["content"] = repaired
        existing = {
            (
                row.get("stage"),
                row.get("repair_code"),
                row.get("field_path"),
                row.get("original_assistant_output_digest"),
            )
            for row in self.repair_findings
        }
        for finding in findings:
            key = (
                finding.get("stage"),
                finding.get("repair_code"),
                finding.get("field_path"),
                finding.get("original_assistant_output_digest"),
            )
            if key not in existing:
                self.repair_findings.append(finding)
                existing.add(key)
        if len(self.repair_findings) > MAXIMUM_REPAIR_FINDINGS:
            raise RuntimeError("diagnostic_repair_finding_cap_exceeded")
        return envelope

    def summary(self) -> dict[str, Any]:
        live_interactions = [
            {
                "stage": stage,
                "interaction_object_ref": row["interaction_object_ref"],
                "interaction_object_digest": row[
                    "interaction_object_digest"
                ],
                "assistant_output_digest": row[
                    "assistant_output_digest"
                ],
                "model_visible_request_digest": row[
                    "model_visible_request_digest"
                ],
            }
            for stage, row in sorted(self.live_cache.items())
        ]
        return {
            "callback_count": self.callback_count,
            "seed_replay_count": self.seed_replay_count,
            "live_replay_count": self.live_replay_count,
            "new_live_call_count": self.new_live_call_count,
            "unique_seed_interactions": len(self.seeded),
            "unique_new_live_interactions": len(self.live_cache),
            "unique_interactions_total": len(self.seeded)
            + len(self.live_cache),
            "live_interactions": live_interactions,
            "repair_finding_count": len(self.repair_findings),
            "repair_findings": self.repair_findings,
        }


def _source_database_sha256() -> str:
    return _sha256_file(
        SOURCE_RUNTIME_ROOT / "canonical-runtime/canonical.sqlite"
    )


def _load_admission_and_target() -> tuple[
    S3ThreeCellBoundedAgentAdmission, Any
]:
    target = load_execution_target(ISSUANCE)
    admission = S3ThreeCellBoundedAgentAdmission.model_validate(
        _load_json(ADMISSION)
    )
    admission.assert_profile_admissible()
    if _sha256_file(ADMISSION) != EXPECTED_ADMISSION_SHA256:
        raise RuntimeError("diagnostic_R6_admission_file_drift")
    if canonical_digest(admission.digest_payload()) != EXPECTED_ADMISSION_DIGEST:
        raise RuntimeError("diagnostic_R6_admission_digest_drift")
    if admission.admission_id != target.admission_id:
        raise RuntimeError("diagnostic_R6_target_admission_mismatch")
    return admission, target


def _prepare_input_in_clone(
    *,
    admission: S3ThreeCellBoundedAgentAdmission,
    target: Any,
    temporary_root: Path,
) -> Any:
    clone_runtime_root = temporary_root / SOURCE_RUNTIME_ROOT.name
    shutil.copytree(SOURCE_RUNTIME_ROOT, clone_runtime_root)
    case_service, _local_service, evidence_service = _services(
        clone_runtime_root
    )
    effective_binding, research_profile_overlay = (
        resolve_s4_case_runtime_binding_for_admission(ROOT, admission)
    )
    current = prepare_s4_source_grounded_exact_input(
        case_service,
        evidence_service,
        effective_binding,
        load_s4_source_grounded_input_pack(ROOT, admission.company),
        str(admission.case_id),
        _principal(),
        decision_surface_contract_ref=target.decision_surface_ref,
        execution_identity=DIAGNOSTIC_RESEARCH_RUN_ID,
        research_profile_overlay=research_profile_overlay,
    )
    if current.input_pack.input_digest != admission.input_digest:
        raise RuntimeError("diagnostic_R6_exact_input_digest_mismatch")
    return current


def preflight(output_root: Path) -> dict[str, Any]:
    decision = _load_json(DECISION)
    failure = _load_json(R6_FAILURE_RESULT)
    runtime_result = _load_json(R6_RUNTIME_RESULT)
    admission, target = _load_admission_and_target()
    if _sha256_file(R6_FAILURE_RESULT) != EXPECTED_FAILURE_RESULT_SHA256:
        raise RuntimeError("diagnostic_R6_failure_result_drift")
    if failure.get("status") != (
        "terminal_failed_admission_consumed_exactly_once_no_retry_no_artifact"
    ):
        raise RuntimeError("diagnostic_R6_failure_truth_invalid")
    if runtime_result.get("status") != (
        "terminal_failed_admission_consumed_no_retry"
    ):
        raise RuntimeError("diagnostic_R6_runtime_truth_invalid")
    if decision.get("status") != (
        "authorized_diagnostic_only_non_promotable_collect_all_continuation"
    ):
        raise RuntimeError("diagnostic_authority_missing")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise RuntimeError("LLM_GATEWAY_TRANSPORT_RETRIES_must_be_0")
    if not admission.api_key_env or not os.environ.get(admission.api_key_env):
        raise RuntimeError("diagnostic_provider_credential_missing")
    source_sha_before = _source_database_sha256()
    seeded = _load_R6_seed_interactions()
    with tempfile.TemporaryDirectory(
        prefix="s4-t06-r6-quarantined-diagnostic-preflight-"
    ) as temp_dir:
        prepared = _prepare_input_in_clone(
            admission=admission,
            target=target,
            temporary_root=Path(temp_dir),
        )
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=lambda **_: (_ for _ in ()).throw(
                AssertionError("diagnostic_preflight_provider_call_forbidden")
            ),
        )
    source_sha_after = _source_database_sha256()
    if source_sha_after != source_sha_before:
        raise RuntimeError("diagnostic_preflight_source_runtime_mutated")
    result = {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_"
            "continuation_preflight_v1_0"
        ),
        "status": "pass_diagnostic_only_zero_call_preflight",
        "decision_ref": str(DECISION.relative_to(ROOT)).replace("\\", "/"),
        "source_R6_admission_digest": EXPECTED_ADMISSION_DIGEST,
        "source_R6_input_digest": prepared.input_pack.input_digest,
        "source_R6_terminal_states": [
            runtime_result["canonical_terminal_truth"][
                "work_unit_state"
            ],
            runtime_result["canonical_terminal_truth"][
                "attempt_state"
            ],
            runtime_result["canonical_terminal_truth"][
                "research_run_state"
            ],
        ],
        "seed_interactions": len(seeded),
        "maximum_new_live_calls": MAXIMUM_NEW_LIVE_CALLS,
        "maximum_unique_interactions": MAXIMUM_UNIQUE_INTERACTIONS,
        "maximum_new_live_cost_usd": MAXIMUM_NEW_LIVE_COST_USD,
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
        "transport_retry_count": 0,
        "provider_health_probe_performed": False,
        "source_runtime_database_sha256_before": source_sha_before,
        "source_runtime_database_sha256_after": source_sha_after,
        "source_runtime_unchanged": True,
        "canonical_target_writes": 0,
        "business_artifact_promotions": 0,
        "model_provider_network_calls": [0, 0, 0],
        "acceptance_eligible": False,
    }
    _write_json(output_root / "preflight.json", result)
    return result


def execute(output_root: Path) -> dict[str, Any]:
    preflight_result = preflight(output_root)
    admission, target = _load_admission_and_target()
    seeded = _load_R6_seed_interactions()
    source_sha_before = _source_database_sha256()

    from sec_agent.llm_gateway import chat_completion

    cache = QuarantinedCompletionCache(
        output_root=output_root,
        seeded=seeded,
        live_completion=chat_completion,
    )
    terminal_status = "diagnostic_terminal_failed"
    artifact_rows: list[dict[str, Any]] = []
    execution_error: dict[str, Any] | None = None
    receipts: list[dict[str, Any]] = []
    observed_counts: Mapping[str, Any] = {}
    diagnostic_run_identity: dict[str, str] = {}
    runtime_projection_findings: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(
        prefix="s4-t06-r6-quarantined-diagnostic-execute-"
    ) as temp_dir:
        prepared = _prepare_input_in_clone(
            admission=admission,
            target=target,
            temporary_root=Path(temp_dir),
        )
        input_pack = prepared.input_pack
        diagnostic_run_identity = {
            "work_unit_id": prepared.work_unit_id,
            "attempt_id": prepared.attempt_id,
            "research_run_id": prepared.research_run_id,
        }
        executor = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=cache,
        )
        try:
            with _diagnostic_local_numeric_text_capacity_projection(
                runtime_projection_findings
            ):
                output = executor.execute(
                    input_pack,
                    admission,
                    run_identity=diagnostic_run_identity,
            )
            terminal_status = "diagnostic_terminal_succeeded_quarantined"
            execution_observation = output.execution_observation
            receipts = [
                dict(row)
                for row in execution_observation.get(
                    "usage_receipts", ()
                )
                if isinstance(row, Mapping)
            ]
            observed_counts = dict(
                execution_observation.get("observed_counts") or {}
            )
            for artifact in output.artifacts:
                payload = dict(artifact.payload)
                artifact_rows.append(
                    {
                        "artifact_type": artifact.artifact_type,
                        "payload_digest": canonical_digest(payload),
                        "payload": payload,
                        "quarantined": True,
                        "business_promotion_allowed": False,
                        "owner_acceptance_eligible": False,
                    }
                )
        except BoundedAgentExecutionError as exc:
            failure_observation = deepcopy(exc.failure_observation)
            execution_error = {
                "exception_type": type(exc).__name__,
                "message": str(exc),
                "failure_observation": failure_observation,
                "completed_node_receipts": deepcopy(
                    failure_observation.get(
                        "completed_node_receipts", ()
                    )
                ),
                "usage_receipts": deepcopy(
                    failure_observation.get("usage_receipts", ())
                ),
                "raw_provider_output_persisted_here": False,
            }
            receipts = [
                dict(row)
                for row in failure_observation.get("usage_receipts", ())
                if isinstance(row, Mapping)
            ]
            observed_counts = dict(
                exc.failure_observation.get("observed_counts") or {}
            )

    source_sha_after = _source_database_sha256()
    if source_sha_after != source_sha_before:
        raise RuntimeError("diagnostic_execution_source_runtime_mutated")
    cache_summary = cache.summary()
    if (
        cache_summary["new_live_call_count"] > MAXIMUM_NEW_LIVE_CALLS
        or cache_summary["unique_interactions_total"]
        > MAXIMUM_UNIQUE_INTERACTIONS
    ):
        raise RuntimeError("diagnostic_execution_interaction_cap_exceeded")
    new_live_stages = {
        row["stage"] for row in cache_summary["live_interactions"]
    }
    new_live_receipts = [
        row for row in receipts if str(row.get("stage") or "") in new_live_stages
    ]
    new_live_cost = round(
        sum(float(row.get("estimated_cost_usd") or 0.0) for row in new_live_receipts),
        8,
    )
    if new_live_cost > MAXIMUM_NEW_LIVE_COST_USD:
        raise RuntimeError("diagnostic_execution_cost_cap_exceeded")

    quarantined_artifacts_ref: str | None = None
    if artifact_rows:
        artifact_path = output_root / "restricted_quarantined_artifacts.json"
        _write_json(
            artifact_path,
            {
                "schema_version": (
                    "fin_ia_0_1_s4_t06_mu_r6_quarantined_artifacts_v1_0"
                ),
                "access_class": "internal_restricted_diagnostic_audit",
                "business_promotion_allowed": False,
                "owner_acceptance_eligible": False,
                "artifacts": artifact_rows,
            },
        )
        quarantined_artifacts_ref = str(
            artifact_path.relative_to(ROOT)
        ).replace("\\", "/")

    result = {
        "schema_version": (
            "fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_"
            "continuation_result_v1_0"
        ),
        "status": terminal_status,
        "diagnostic_only": True,
        "acceptance_eligible": False,
        "source_R6_immutable": True,
        "source_R6_admission_consumed_again": False,
        "preflight": preflight_result,
        "execution_identity_seed": DIAGNOSTIC_RESEARCH_RUN_ID,
        "diagnostic_run_identity": diagnostic_run_identity,
        "provider": admission.provider,
        "model": admission.model,
        "cache_and_repairs": cache_summary,
        "runtime_projection_findings": runtime_projection_findings,
        "execution_error": execution_error,
        "observed_counts_from_executor": observed_counts,
        "usage_receipt_count": len(receipts),
        "new_live_usage_receipt_count": len(new_live_receipts),
        "new_live_input_tokens": sum(
            int(row.get("input_tokens") or 0) for row in new_live_receipts
        ),
        "new_live_output_tokens": sum(
            int(row.get("output_tokens") or 0) for row in new_live_receipts
        ),
        "new_live_total_tokens": sum(
            int(row.get("total_tokens") or 0) for row in new_live_receipts
        ),
        "new_live_cost_usd": new_live_cost,
        "quarantined_artifact_count": len(artifact_rows),
        "quarantined_artifact_types": sorted(
            row["artifact_type"] for row in artifact_rows
        ),
        "quarantined_artifacts_ref": quarantined_artifacts_ref,
        "business_artifact_promotions": 0,
        "paired_assessment_performed": False,
        "owner_acceptance_performed": False,
        "T07_entered": False,
        "source_runtime_database_sha256_before": source_sha_before,
        "source_runtime_database_sha256_after": source_sha_after,
        "source_runtime_unchanged": True,
        "credential_value_persisted": False,
        "private_reasoning_persisted": False,
        "raw_provider_response_persisted": False,
        "next_action": (
            "AGGREGATE_DIAGNOSTIC_DEFECTS_AND_CLASSIFY_"
            "DETERMINISTIC_NODE_OR_FINAL_LIVE_PROOF"
        ),
    }
    _write_json(output_root / "result.json", result)
    print(
        json.dumps(
            {
                **result,
                "execution_error": (
                    None
                    if execution_error is None
                    else {
                        "exception_type": execution_error[
                            "exception_type"
                        ],
                        "message": execution_error["message"],
                        "failure_observation": execution_error[
                            "failure_observation"
                        ],
                    }
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a non-promotable R6 continuation using immutable capture "
            "replay, deterministic repair manifests, and at most eight new "
            "DeepSeek calls."
        )
    )
    parser.add_argument("mode", choices=("preflight", "execute"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    if args.mode == "preflight":
        print(
            json.dumps(
                preflight(output_root),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        execute(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
