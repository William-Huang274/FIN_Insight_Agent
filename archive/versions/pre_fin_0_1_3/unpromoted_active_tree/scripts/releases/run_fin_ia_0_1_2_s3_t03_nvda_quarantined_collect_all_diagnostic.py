from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live import (
    _default_completion,
    load_admission,
    load_target,
    prepare_exact_input,
)
from scripts.releases.run_fin_ia_0_1_s4_t06_mu_r6_quarantined_diagnostic_continuation import (
    _repair_json_output as _historical_diagnostic_projection,
)
from sec_agent.canonical_runtime.models import canonical_digest


AUTHORITY = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_quarantined_collect_all_"
    "diagnostic_authority_decision_v1_0.json"
)
SOURCE_FAILURE = ROOT / (
    "configs/releases/fin_ia_0_1_2_s3_t03_nvda_exact_live_execution_"
    "terminal_failure_result_v1_0.json"
)
SOURCE_RUNTIME = ROOT / ".codex_runtime/fin012-s3-t03-nvda-primary-r1"
DEFAULT_OUTPUT_ROOT = ROOT / (
    ".codex_runtime/fin012-s3-t03-nvda-primary-r1-quarantined-"
    "collect-all-diagnostic-r1"
)
EXPECTED_SOURCE_FAILURE_SHA256 = (
    "42f3dd198696dd6d284c9e3bb67b5fbc093b2491b992785ed46d0cc5e1440a56"
)
EXPECTED_EXECUTION_RESULT_SHA256 = (
    "09a0bf6bb643cec69ced0728c98e3b779fcf4825ffb8829924664d2dd245111c"
)
EXPECTED_CAPTURE_INDEX_SHA256 = (
    "b235ff9096d280a61fcecaaa9f3a5347e694288c9fd1506c30215fa5242ec7a2"
)
EXPECTED_CAPTURE_DIGESTS = (
    "47c62e2ff20f6e91b17ad0399b057e2ad5993b97d08ac3582096e2a318dd4e34",
    "a95ee3e699224c4d4675515f790db1b369989c0a1c8eb6a99467197b1b9d4242",
    "ab64faa64f6abff6c600d2b2f13389ce9211c911f2c7fe0534ff733559bdf733",
    "760f008191cf5dd072e766444a9bfcab233b95a6f42ba36615bbe50219b9f614",
    "aece6ebbc361a08e4b8b8b843e64433f982ceabb79350a81a2e0ff2c82d11264",
    "59a83084fda41b94f3b8d48b20d386ec19203568541b8ac4aff14889fb9f324b",
    "f60b5aaa598ecd34a1d81728849fbf5ace5a154c7d6e9313e8d98a1e2b7af792",
)
MAXIMUM_NEW_LIVE_CALLS = 2
MAXIMUM_NEW_LIVE_COST_USD = 0.04
LIVE_STAGES = ("memo_writer", "verifier")
INTERACTION_SCHEMA = (
    "fin_ia_0_1_2_s3_t03_nvda_quarantined_diagnostic_interaction_v1_0"
)
REPAIR_SCHEMA = (
    "fin_ia_0_1_2_s3_t03_nvda_quarantined_diagnostic_repair_v1_0"
)
_CLAIM_ALIAS_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(C002|C003)(?![A-Za-z0-9_])")


class DiagnosticError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DiagnosticError(f"diagnostic_json_object_required:{path}")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _path_ref(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _tree_digest(root: Path) -> str:
    rows = [
        {
            "path": str(path.relative_to(root)).replace("\\", "/"),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]
    return _digest(rows)


def _capture_path(object_key: str) -> Path:
    return SOURCE_RUNTIME / "restricted-audit-objects" / object_key


def _source_interactions() -> dict[str, dict[str, Any]]:
    if _sha256(SOURCE_FAILURE) != EXPECTED_SOURCE_FAILURE_SHA256:
        raise DiagnosticError("diagnostic_source_failure_file_drift")
    if _sha256(SOURCE_RUNTIME / "execution-result.json") != (
        EXPECTED_EXECUTION_RESULT_SHA256
    ):
        raise DiagnosticError("diagnostic_source_execution_result_drift")
    if _sha256(SOURCE_RUNTIME / "capture-index.json") != (
        EXPECTED_CAPTURE_INDEX_SHA256
    ):
        raise DiagnosticError("diagnostic_source_capture_index_drift")
    index = _load_json(SOURCE_RUNTIME / "capture-index.json")
    objects = index.get("capture_objects")
    if not isinstance(objects, list) or len(objects) != 7:
        raise DiagnosticError("diagnostic_source_capture_topology_invalid")
    if tuple(str(row.get("digest")) for row in objects) != EXPECTED_CAPTURE_DIGESTS:
        raise DiagnosticError("diagnostic_source_capture_digest_sequence_drift")

    interactions: dict[str, dict[str, Any]] = {}
    for sequence, row in enumerate(objects, start=1):
        path = _capture_path(str(row["object_key"]))
        capture = _load_json(path)
        if (
            canonical_digest(capture) != row["digest"]
            or int(capture.get("capture_sequence") or 0) != sequence
            or not isinstance(capture.get("model_visible_request"), list)
            or not isinstance(capture.get("assistant_output_text"), str)
        ):
            raise DiagnosticError("diagnostic_source_capture_readback_invalid")
        stage = str(capture.get("stage") or "")
        if not stage or stage in interactions:
            raise DiagnosticError("diagnostic_source_capture_stage_invalid")
        interactions[stage] = {
            "source": "immutable_formal_capture_replay",
            "capture_digest": str(row["digest"]),
            "capture_ref": _path_ref(path),
            "capture_sequence": sequence,
            "messages": capture["model_visible_request"],
            "assistant_output_text": capture["assistant_output_text"],
            "safe_envelope": {
                "status": "ok",
                "finish_reason": capture.get("finish_reason"),
                "input_tokens": int(capture["usage"]["input_tokens"]),
                "output_tokens": int(capture["usage"]["output_tokens"]),
                "total_tokens": int(capture["usage"]["total_tokens"]),
                "latency_ms": capture.get("latency_ms"),
                "transport_attempt_count": int(
                    capture.get("transport_attempt_count") or 1
                ),
                "provider": "deepseek",
                "model": "deepseek-v4-pro",
                "call_id": f"diagnostic-formal-capture-replay-{sequence}",
            },
        }
    if len(interactions) != 7 or "research_lead" not in interactions:
        raise DiagnosticError("diagnostic_source_interaction_set_invalid")
    return interactions


def _swap_claim_aliases(text: str) -> str:
    return _CLAIM_ALIAS_PATTERN.sub(
        lambda match: "C003" if match.group(1) == "C002" else "C002",
        text,
    )


def _walk_and_swap(value: Any, *, path: str = "$") -> tuple[Any, list[dict[str, Any]]]:
    findings: list[dict[str, Any]] = []
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in value.items():
            changed, nested = _walk_and_swap(item, path=f"{path}.{key}")
            output[key] = changed
            findings.extend(nested)
        return output, findings
    if isinstance(value, list):
        output_list: list[Any] = []
        for index, item in enumerate(value):
            changed, nested = _walk_and_swap(item, path=f"{path}[{index}]")
            output_list.append(changed)
            findings.extend(nested)
        return output_list, findings
    if isinstance(value, str):
        changed = _swap_claim_aliases(value)
        if changed != value:
            findings.append(
                {
                    "stage": "research_lead",
                    "repair_code": "adjacent_same_cell_claim_alias_semantic_swap",
                    "field_path": path,
                    "before_value_digest": _digest(value),
                    "after_value_digest": _digest(changed),
                    "acceptance_eligible": False,
                }
            )
        return changed, findings
    return value, findings


def _claim_support_counts(request: Mapping[str, Any]) -> dict[str, int]:
    analysis = request.get("analysis_input")
    if not isinstance(analysis, Mapping):
        raise DiagnosticError("diagnostic_lead_analysis_input_missing")
    table = analysis.get("compact_scoped_reference_alias_table")
    specialists = analysis.get("specialist_outputs")
    if not isinstance(table, Mapping) or not isinstance(specialists, list):
        raise DiagnosticError("diagnostic_lead_alias_or_specialist_input_missing")
    support_by_local: dict[tuple[str, str], int] = {}
    for specialist in specialists:
        if not isinstance(specialist, Mapping):
            continue
        cell_id = str(specialist.get("program_cell_id") or "")
        for claim in specialist.get("judgment_layer") or ():
            if isinstance(claim, Mapping):
                support_by_local[(cell_id, str(claim.get("claim_id") or ""))] = len(
                    claim.get("support_fact_ids") or ()
                )
    support_by_alias: dict[str, int] = {}
    for row in table.get("rows") or ():
        if not isinstance(row, Mapping) or row.get("identity_kind") != "claim":
            continue
        alias = str(row.get("alias") or "")
        key = (
            str(row.get("program_cell_id") or ""),
            str(row.get("local_id") or ""),
        )
        if alias:
            support_by_alias[alias] = support_by_local.get(key, 0)
    if support_by_alias != {"C001": 0, "C002": 0, "C003": 3, "C004": 0}:
        raise DiagnosticError("diagnostic_lead_support_truth_drift")
    return support_by_alias


def repair_research_lead(
    *,
    request: Mapping[str, Any],
    assistant_output_text: str,
) -> tuple[str, list[dict[str, Any]]]:
    try:
        original = json.loads(assistant_output_text)
    except json.JSONDecodeError as exc:
        raise DiagnosticError("diagnostic_lead_output_not_json") from exc
    if not isinstance(original, dict):
        raise DiagnosticError("diagnostic_lead_output_not_object")
    repaired, findings = _walk_and_swap(original)
    support = _claim_support_counts(request)
    conflicts = repaired.get("conflict_adjudications")
    if not isinstance(conflicts, list):
        raise DiagnosticError("diagnostic_lead_conflicts_missing")
    for index, conflict in enumerate(conflicts):
        if not isinstance(conflict, dict):
            raise DiagnosticError("diagnostic_lead_conflict_not_object")
        aliases = conflict.get("involved_claim_ids")
        if not isinstance(aliases, list) or not aliases:
            raise DiagnosticError("diagnostic_lead_conflict_aliases_missing")
        supported = sum(1 for alias in aliases if support.get(str(alias), 0) > 0)
        expected = (
            "no_facts_present"
            if supported == 0
            else "facts_present"
            if supported == len(aliases)
            else "mixed_fact_presence"
        )
        observed = conflict.get("fact_presence_summary")
        if observed != expected:
            conflict["fact_presence_summary"] = expected
            findings.append(
                {
                    "stage": "research_lead",
                    "repair_code": "deterministic_fact_presence_materialization",
                    "field_path": (
                        f"$.conflict_adjudications[{index}].fact_presence_summary"
                    ),
                    "before_value_digest": _digest(observed),
                    "after_value_digest": _digest(expected),
                    "acceptance_eligible": False,
                }
            )
    repaired_text = json.dumps(
        repaired,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if not findings:
        raise DiagnosticError("diagnostic_lead_expected_repair_not_observed")
    original_digest = _text_digest(assistant_output_text)
    repaired_digest = _text_digest(repaired_text)
    for finding in findings:
        finding["original_assistant_output_digest"] = original_digest
        finding["repaired_assistant_output_digest"] = repaired_digest
        finding["business_promotion_allowed"] = False
    return repaired_text, findings


def _request_from_messages(messages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(messages) < 2:
        raise DiagnosticError("diagnostic_model_visible_request_incomplete")
    try:
        request = json.loads(str(messages[-1]["content"]))
    except (KeyError, json.JSONDecodeError) as exc:
        raise DiagnosticError("diagnostic_model_visible_user_request_invalid") from exc
    if not isinstance(request, dict):
        raise DiagnosticError("diagnostic_model_visible_user_request_not_object")
    return request


def _safe_usage(result: Mapping[str, Any]) -> dict[str, int]:
    raw = result.get("raw_response")
    usage = raw.get("usage") if isinstance(raw, Mapping) else None
    cache_hit = int(usage.get("prompt_cache_hit_tokens") or 0) if isinstance(usage, Mapping) else 0
    cache_miss = int(usage.get("prompt_cache_miss_tokens") or 0) if isinstance(usage, Mapping) else 0
    input_tokens = int(result.get("input_tokens") or cache_hit + cache_miss)
    if cache_hit + cache_miss == 0:
        cache_miss = input_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": int(result.get("output_tokens") or 0),
        "total_tokens": int(result.get("total_tokens") or 0),
        "input_cache_hit_tokens": cache_hit,
        "input_cache_miss_tokens": cache_miss,
    }


class DiagnosticCompletion:
    def __init__(
        self,
        *,
        output_root: Path,
        admission: S3ThreeCellBoundedAgentAdmission,
        live_completion: Callable[..., Mapping[str, Any]],
        maximum_new_live_calls: int = MAXIMUM_NEW_LIVE_CALLS,
    ) -> None:
        self.output_root = output_root
        self.admission = admission
        self.source = _source_interactions()
        self.live_completion = live_completion
        self.maximum_new_live_calls = maximum_new_live_calls
        self.live_cache: dict[str, dict[str, Any]] = {}
        self.repair_objects: list[dict[str, Any]] = []
        self.seen_stages: list[str] = []
        self.seed_replay_count = 0
        self.live_replay_count = 0
        self.new_live_call_count = 0
        self.next_live_stage: str | None = None
        self._load_live_cache()

    def _load_live_cache(self) -> None:
        root = self.output_root / "restricted_interactions"
        if not root.exists():
            return
        for path in sorted(root.rglob("*.json")):
            record = _load_json(path)
            digest = _digest(record)
            if (
                record.get("schema_version") != INTERACTION_SCHEMA
                or record.get("source") != "new_live_provider_call"
                or path.stem != digest
            ):
                raise DiagnosticError("diagnostic_live_cache_invalid")
            stage = str(record.get("stage") or "")
            if stage not in LIVE_STAGES:
                raise DiagnosticError("diagnostic_live_cache_stage_invalid")
            if stage in self.live_cache and self.live_cache[stage]["digest"] != digest:
                raise DiagnosticError("diagnostic_live_cache_stage_ambiguous")
            self.live_cache[stage] = {
                **record,
                "digest": digest,
                "ref": _path_ref(path),
            }

    def _persist_live(
        self,
        *,
        stage: str,
        messages: Sequence[Mapping[str, Any]],
        response: Mapping[str, Any],
    ) -> dict[str, Any]:
        content = response.get("content")
        if not isinstance(content, str):
            raise DiagnosticError("diagnostic_live_assistant_output_missing")
        usage = _safe_usage(response)
        record = {
            "schema_version": INTERACTION_SCHEMA,
            "access_class": "internal_restricted_diagnostic_audit",
            "stage": stage,
            "source": "new_live_provider_call",
            "model_visible_request": [dict(row) for row in messages],
            "model_visible_request_digest": _digest(messages),
            "assistant_output_text": content,
            "assistant_output_digest": _text_digest(content),
            "safe_envelope": {
                "status": response.get("status"),
                "finish_reason": response.get("finish_reason"),
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "total_tokens": usage["total_tokens"],
                "input_cache_hit_tokens": usage["input_cache_hit_tokens"],
                "input_cache_miss_tokens": usage["input_cache_miss_tokens"],
                "latency_ms": response.get("latency_ms"),
                "transport_attempt_count": response.get("transport_attempt_count"),
                "call_id": response.get("call_id"),
                "provider": response.get("provider"),
                "model": response.get("model"),
            },
            "capture_before_local_parse_or_validation": True,
            "credentials_included": False,
            "authorization_headers_included": False,
            "cookies_included": False,
            "private_reasoning_included": False,
            "raw_provider_response_included": False,
            "business_promotable": False,
        }
        digest = _digest(record)
        path = (
            self.output_root
            / "restricted_interactions"
            / digest[:2]
            / digest[2:4]
            / f"{digest}.json"
        )
        _write_json(path, record)
        cached = {**record, "digest": digest, "ref": _path_ref(path)}
        self.live_cache[stage] = cached
        return cached

    @staticmethod
    def _envelope(cached: Mapping[str, Any]) -> dict[str, Any]:
        safe = cached.get("safe_envelope")
        if not isinstance(safe, Mapping):
            raise DiagnosticError("diagnostic_replay_safe_envelope_missing")
        cache_hit = int(safe.get("input_cache_hit_tokens") or 0)
        cache_miss = int(safe.get("input_cache_miss_tokens") or safe.get("input_tokens") or 0)
        return {
            **dict(safe),
            "content": str(cached.get("assistant_output_text") or ""),
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": cache_hit,
                    "prompt_cache_miss_tokens": cache_miss,
                }
            },
        }

    def _persist_repair(
        self,
        *,
        stage: str,
        original: str,
        repaired: str,
        findings: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not findings:
            return None
        record = {
            "schema_version": REPAIR_SCHEMA,
            "access_class": "internal_restricted_diagnostic_audit",
            "stage": stage,
            "original_assistant_output_digest": _text_digest(original),
            "repaired_assistant_output_digest": _text_digest(repaired),
            "repaired_assistant_output_text": repaired,
            "findings": findings,
            "diagnostic_only": True,
            "business_promotion_allowed": False,
            "owner_acceptance_eligible": False,
        }
        digest = _digest(record)
        path = (
            self.output_root
            / "restricted_repairs"
            / digest[:2]
            / digest[2:4]
            / f"{digest}.json"
        )
        _write_json(path, record)
        row = {
            "stage": stage,
            "digest": digest,
            "ref": _path_ref(path),
            "finding_count": len(findings),
            "repair_codes": sorted({str(item["repair_code"]) for item in findings}),
        }
        if row not in self.repair_objects:
            self.repair_objects.append(row)
        return row

    def _repair(
        self,
        *,
        stage: str,
        messages: Sequence[Mapping[str, Any]],
        envelope: dict[str, Any],
    ) -> dict[str, Any]:
        original = envelope.get("content")
        if not isinstance(original, str):
            raise DiagnosticError("diagnostic_assistant_output_missing")
        request = _request_from_messages(messages)
        if stage == "research_lead":
            repaired, findings = repair_research_lead(
                request=request,
                assistant_output_text=original,
            )
        elif stage in LIVE_STAGES:
            repaired, findings = _historical_diagnostic_projection(
                stage=stage,
                request=request,
                assistant_output_text=original,
            )
        else:
            repaired, findings = original, []
        self._persist_repair(
            stage=stage,
            original=original,
            repaired=repaired,
            findings=findings,
        )
        envelope["content"] = repaired
        return envelope

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        messages = kwargs.get("messages")
        stage = str(kwargs.get("role") or "")
        if not isinstance(messages, list) or not stage:
            raise DiagnosticError("diagnostic_completion_request_invalid")
        self.seen_stages.append(stage)
        if stage in self.source:
            cached = self.source[stage]
            if cached["messages"] != messages:
                raise DiagnosticError(f"diagnostic_source_request_drift:{stage}")
            envelope = self._envelope(cached)
            self.seed_replay_count += 1
        elif stage in self.live_cache:
            cached = self.live_cache[stage]
            if cached["model_visible_request_digest"] != _digest(messages):
                raise DiagnosticError(f"diagnostic_live_request_drift:{stage}")
            envelope = self._envelope(cached)
            self.live_replay_count += 1
        else:
            self.next_live_stage = stage
            if stage not in LIVE_STAGES:
                raise DiagnosticError(f"diagnostic_unexpected_live_stage:{stage}")
            if self.new_live_call_count >= self.maximum_new_live_calls:
                raise DiagnosticError("diagnostic_new_live_call_cap_exceeded")
            response = self.live_completion(**kwargs)
            if not isinstance(response, Mapping):
                raise DiagnosticError("diagnostic_live_provider_envelope_invalid")
            self.new_live_call_count += 1
            cached = self._persist_live(
                stage=stage,
                messages=messages,
                response=response,
            )
            envelope = deepcopy(dict(response))
            if int(response.get("transport_attempt_count") or 0) != 1:
                raise DiagnosticError("diagnostic_transport_attempt_count_invalid")
        return self._repair(stage=stage, messages=messages, envelope=envelope)

    def live_cost_usd(self) -> float:
        total = 0.0
        for row in self.live_cache.values():
            safe = row["safe_envelope"]
            total += (
                int(safe.get("input_cache_hit_tokens") or 0)
                * self.admission.input_cache_hit_usd_per_million
                / 1_000_000
                + int(safe.get("input_cache_miss_tokens") or 0)
                * self.admission.input_cache_miss_usd_per_million
                / 1_000_000
                + int(safe.get("output_tokens") or 0)
                * self.admission.output_usd_per_million
                / 1_000_000
            )
        return round(total, 8)

    def summary(self) -> dict[str, Any]:
        live_rows = [
            {
                "stage": stage,
                "interaction_ref": row["ref"],
                "interaction_digest": row["digest"],
                "model_visible_request_digest": row["model_visible_request_digest"],
                "assistant_output_digest": row["assistant_output_digest"],
                "safe_envelope": row["safe_envelope"],
            }
            for stage, row in sorted(self.live_cache.items())
        ]
        return {
            "seen_stages": self.seen_stages,
            "seed_replay_count": self.seed_replay_count,
            "live_replay_count": self.live_replay_count,
            "new_live_call_count": self.new_live_call_count,
            "unique_new_live_interactions": len(self.live_cache),
            "live_interactions": live_rows,
            "repair_objects": self.repair_objects,
            "new_live_cost_usd": self.live_cost_usd(),
        }


def _authority_preflight() -> tuple[S3ThreeCellBoundedAgentAdmission, Any]:
    authority = _load_json(AUTHORITY)
    if authority.get("status") != (
        "authorized_diagnostic_only_non_promotable_downstream_continuation"
    ):
        raise DiagnosticError("diagnostic_authority_missing")
    limits = authority.get("hard_limits") or {}
    if (
        limits.get("maximum_new_live_calls") != MAXIMUM_NEW_LIVE_CALLS
        or limits.get("maximum_new_live_cost_usd") != MAXIMUM_NEW_LIVE_COST_USD
        or limits.get("retry_budget") != 0
        or limits.get("fallback_budget") != 0
    ):
        raise DiagnosticError("diagnostic_authority_limit_drift")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise DiagnosticError("LLM_GATEWAY_TRANSPORT_RETRIES_must_be_0")
    target = load_target()
    admission = load_admission(target)
    if (
        admission.provider != "deepseek"
        or admission.model != "deepseek-v4-pro"
        or not admission.api_key_env
        or not os.environ.get(admission.api_key_env)
    ):
        raise DiagnosticError("diagnostic_deepseek_pro_credential_or_binding_missing")
    return admission, target


def preflight(output_root: Path) -> dict[str, Any]:
    admission, target = _authority_preflight()
    source_tree_before = _tree_digest(SOURCE_RUNTIME)
    source = _source_interactions()
    callback = DiagnosticCompletion(
        output_root=output_root,
        admission=admission,
        live_completion=lambda **_: (_ for _ in ()).throw(
            AssertionError("diagnostic_preflight_provider_call_forbidden")
        ),
        maximum_new_live_calls=0,
    )
    with tempfile.TemporaryDirectory(
        prefix="fin012-s3-t03-nvda-collect-all-preflight-",
        dir=output_root.parent,
    ) as temporary:
        prepared = prepare_exact_input(Path(temporary), target, admission)
        executor = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=callback,
        )
        try:
            executor.execute(
                prepared.input_pack,
                admission,
                run_identity={
                    "research_run_id": prepared.research_run_id,
                    "attempt_id": prepared.attempt_id,
                },
            )
        except Exception:
            pass
    if callback.seed_replay_count != 7 or callback.next_live_stage != "memo_writer":
        raise DiagnosticError("diagnostic_zero_call_continuation_preflight_failed")
    source_tree_after = _tree_digest(SOURCE_RUNTIME)
    if source_tree_after != source_tree_before:
        raise DiagnosticError("diagnostic_source_runtime_mutated_during_preflight")
    result = {
        "schema_version": (
            "fin_ia_0_1_2_s3_t03_nvda_quarantined_collect_all_"
            "diagnostic_preflight_v1_0"
        ),
        "status": "pass_zero_call_replay_lead_repair_reaches_memo_writer",
        "authority_ref": _path_ref(AUTHORITY),
        "source_capture_count": len(source),
        "source_replay_count": callback.seed_replay_count,
        "next_live_stage": callback.next_live_stage,
        "research_lead_repair_objects": callback.repair_objects,
        "source_runtime_tree_digest_before": source_tree_before,
        "source_runtime_tree_digest_after": source_tree_after,
        "source_runtime_unchanged": True,
        "credential_present": True,
        "credential_value_read_output_or_persisted": False,
        "provider_health_probe_performed": False,
        "maximum_new_live_calls": MAXIMUM_NEW_LIVE_CALLS,
        "maximum_new_live_cost_usd": MAXIMUM_NEW_LIVE_COST_USD,
        "model_provider_network_calls": [0, 0, 0],
        "business_artifact_promotions": 0,
        "acceptance_eligible": False,
    }
    _write_json(output_root / "preflight.json", result)
    return result


def execute(
    output_root: Path,
    *,
    live_completion: Callable[..., Mapping[str, Any]] = _default_completion,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    preflight_result = preflight(output_root)
    admission, target = _authority_preflight()
    source_tree_before = _tree_digest(SOURCE_RUNTIME)
    callback = DiagnosticCompletion(
        output_root=output_root,
        admission=admission,
        live_completion=live_completion,
    )
    terminal_status = "diagnostic_terminal_failed_quarantined"
    execution_error: dict[str, Any] | None = None
    artifact_rows: list[dict[str, Any]] = []
    observation: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(
        prefix="fin012-s3-t03-nvda-collect-all-execute-",
        dir=output_root.parent,
    ) as temporary:
        prepared = prepare_exact_input(Path(temporary), target, admission)
        executor = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=callback,
        )
        try:
            output = executor.execute(
                prepared.input_pack,
                admission,
                run_identity={
                    "research_run_id": prepared.research_run_id,
                    "attempt_id": prepared.attempt_id,
                },
            )
            terminal_status = "diagnostic_terminal_succeeded_quarantined"
            observation = deepcopy(dict(output.execution_observation))
            artifact_rows = [
                {
                    "artifact_type": artifact.artifact_type,
                    "payload_digest": canonical_digest(artifact.payload),
                    "payload": deepcopy(dict(artifact.payload)),
                    "quarantined": True,
                    "business_promotion_allowed": False,
                    "owner_acceptance_eligible": False,
                }
                for artifact in output.artifacts
            ]
        except BoundedAgentExecutionError as exc:
            execution_error = {
                "exception_type": type(exc).__name__,
                "stage": exc.stage,
                "failure_codes": list(
                    exc.failure_observation.get("failure_codes") or ()
                ),
                "failure_observation": deepcopy(exc.failure_observation),
            }
        except Exception as exc:
            execution_error = {
                "exception_type": type(exc).__name__,
                "stage": callback.next_live_stage or "diagnostic_runtime",
                "failure_codes": [str(exc)],
            }

    source_tree_after = _tree_digest(SOURCE_RUNTIME)
    if source_tree_after != source_tree_before:
        raise DiagnosticError("diagnostic_source_runtime_mutated")
    summary = callback.summary()
    if (
        summary["new_live_call_count"] > MAXIMUM_NEW_LIVE_CALLS
        or len(summary["live_interactions"]) > MAXIMUM_NEW_LIVE_CALLS
        or summary["new_live_cost_usd"] > MAXIMUM_NEW_LIVE_COST_USD
    ):
        raise DiagnosticError("diagnostic_live_budget_exceeded")
    artifact_ref: str | None = None
    if artifact_rows:
        artifact_path = output_root / "restricted_quarantined_artifacts.json"
        _write_json(
            artifact_path,
            {
                "schema_version": (
                    "fin_ia_0_1_2_s3_t03_nvda_quarantined_artifacts_v1_0"
                ),
                "access_class": "internal_restricted_diagnostic_audit",
                "business_promotion_allowed": False,
                "owner_acceptance_eligible": False,
                "artifacts": artifact_rows,
            },
        )
        artifact_ref = _path_ref(artifact_path)
    result = {
        "schema_version": (
            "fin_ia_0_1_2_s3_t03_nvda_quarantined_collect_all_"
            "diagnostic_result_v1_0"
        ),
        "status": terminal_status,
        "diagnostic_only": True,
        "acceptance_eligible": False,
        "authority_ref": _path_ref(AUTHORITY),
        "formal_source_failure_ref": _path_ref(SOURCE_FAILURE),
        "formal_source_failure_immutable": True,
        "formal_admission_consumed_again": False,
        "preflight": preflight_result,
        "provider": admission.provider,
        "model": admission.model,
        "cache_and_repairs": summary,
        "execution_error": execution_error,
        "execution_observation": observation,
        "quarantined_artifact_count": len(artifact_rows),
        "quarantined_artifact_types": sorted(
            row["artifact_type"] for row in artifact_rows
        ),
        "quarantined_artifacts_ref": artifact_ref,
        "business_artifact_promotions": 0,
        "paired_assessment_performed": False,
        "owner_acceptance_performed": False,
        "S3_T04_entered": False,
        "source_runtime_tree_digest_before": source_tree_before,
        "source_runtime_tree_digest_after": source_tree_after,
        "source_runtime_unchanged": True,
        "credential_value_persisted": False,
        "private_reasoning_persisted": False,
        "raw_provider_response_persisted": False,
        "next_action": (
            "AGGREGATE_DOWNSTREAM_DEFECTS_BY_SHARED_OWNERSHIP_AND_"
            "DESIGN_ONE_MAINLINE_STRUCTURAL_REPAIR_BUNDLE"
        ),
    }
    _write_json(output_root / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Replay the immutable NVDA S3-T03 captures, repair only the "
            "known Lead alias blocker, and run at most Writer plus Verifier "
            "with DeepSeek Pro in a non-promotable diagnostic runtime."
        )
    )
    parser.add_argument("mode", choices=("preflight", "execute"))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    if args.mode == "preflight":
        print(json.dumps(preflight(output_root), ensure_ascii=False, indent=2))
    else:
        execute(output_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
