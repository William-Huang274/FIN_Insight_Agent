from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from sec_agent.s1_six_case_local_evidence_pack import canonical_digest
from sec_agent.s2_fixed_pack_research import (
    CASES,
    validate_case_model_input,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ADMISSION_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_case_admission_v1_0"
CAPTURE_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_raw_capture_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_3_s2_fixed_pack_terminal_v1_0"
SCOPE = "FIN_0_1_3_S2_FIXED_PACK_RESEARCH_ONE_CASE_EXACT_ONCE"
SPECIALIST_FAMILIES = (
    "demand_authenticity_and_sustainability",
    "product_and_technology_position",
    "supply_capacity_and_competition",
    "financial_transmission_profit_and_cash",
    "capital_allocation_valuation_and_price_in",
    "counter_thesis_risk_and_what_would_change",
)
NODE_ORDER = (
    "direct_baseline",
    "research_lead",
    *tuple(f"specialist::{family}" for family in SPECIALIST_FAMILIES),
    "cross_unit_synthesis",
    "draft_writer",
    "red_team_critic",
    "final_writer",
    "verifier",
)

ProviderCall = Callable[[Mapping[str, Any]], Mapping[str, Any]]
_DIGEST = re.compile(r"[0-9a-f]{64}")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}")
_NUMERIC = re.compile(r"(?<![A-Za-z])\(?[-+]?\d[\d,]*(?:\.\d+)?%?\)?")


class S2FixedPackRuntimeError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S2FixedPackRuntimeError(code)


def _utc(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError as exc:
        raise S2FixedPackRuntimeError("fixed_pack_runtime_timestamp_invalid") from exc


def _digest(value: str, code: str) -> str:
    candidate = str(value or "").lower()
    _require(bool(_DIGEST.fullmatch(candidate)), code)
    return candidate


def issue_case_admission(
    *,
    case_input: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    contract_sha256: str,
    profile_sha256: str,
    issued_at: str,
    expires_at: str,
    run_nonce: str,
    credential_present: bool,
    execution_mode: str = "live",
) -> dict[str, Any]:
    validate_case_model_input(case_input, profile=profile)
    _require(
        bool(_GIT_COMMIT.fullmatch(str(execution_git_commit or ""))),
        "fixed_pack_admission_git_commit_invalid",
    )
    for value in (runner_sha256, contract_sha256, profile_sha256):
        _digest(value, "fixed_pack_admission_runtime_digest_invalid")
    _require(
        execution_mode in {"live", "fixture"},
        "fixed_pack_admission_execution_mode_invalid",
    )
    if execution_mode == "live":
        _require(credential_present is True, "fixed_pack_admission_credential_missing")
    else:
        _require(
            credential_present is False,
            "fixed_pack_fixture_admission_must_not_claim_credential",
        )
    _require(
        _utc(expires_at) > _utc(issued_at),
        "fixed_pack_admission_expiry_invalid",
    )
    case_key = str(case_input.get("case_key") or "")
    _require(case_key in CASES, "fixed_pack_admission_case_invalid")
    run_id = "fin013_s2_fixed_pack_" + case_key.lower() + "_" + canonical_digest(
        {
            "case_key": case_key,
            "git": execution_git_commit,
            "nonce": run_nonce,
            "input": case_input["model_visible_digest"],
        }
    )[:20]
    capacity = deepcopy(dict(profile.get("capacity") or {}))
    body = {
        "schema_version": ADMISSION_SCHEMA,
        "scope": SCOPE,
        "admission_id": "admission::" + run_id,
        "run_id": run_id,
        "attempt_id": run_id + "::attempt_1",
        "runtime_identity": run_id + "::runtime_1",
        "case_key": case_key,
        "case_input_digest": str(case_input["model_visible_digest"]),
        "source_pack_digest": str(case_input["source_pack_digest"]),
        "execution_git_commit": execution_git_commit,
        "runner_sha256": runner_sha256,
        "contract_sha256": contract_sha256,
        "profile_sha256": profile_sha256,
        "provider": {
            "name": str(profile.get("provider") or ""),
            "model": str(profile.get("model") or ""),
            "model_tier": str(profile.get("model_tier") or ""),
            "base_url": str(profile.get("base_url") or ""),
            "chat_completions_path": str(
                profile.get("chat_completions_path") or ""
            ),
        },
        "capacity": capacity,
        "node_order": list(NODE_ORDER),
        "issued_at": issued_at,
        "expires_at": expires_at,
        "run_nonce_digest": canonical_digest(run_nonce),
        "credential_present": credential_present,
        "execution_mode": execution_mode,
        "state": "issued_unconsumed",
        "promotion_authority": False,
    }
    return {**body, "admission_digest": canonical_digest(body)}


def validate_case_admission(
    admission: Mapping[str, Any],
    *,
    case_input: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    contract_sha256: str,
    profile_sha256: str,
    observed_at: str,
) -> None:
    body = deepcopy(dict(admission))
    digest = str(body.pop("admission_digest", ""))
    expected_runtime = (
        execution_git_commit,
        runner_sha256,
        contract_sha256,
        profile_sha256,
    )
    actual_runtime = tuple(
        admission.get(key)
        for key in (
            "execution_git_commit",
            "runner_sha256",
            "contract_sha256",
            "profile_sha256",
        )
    )
    _require(
        admission.get("schema_version") == ADMISSION_SCHEMA
        and admission.get("scope") == SCOPE
        and admission.get("state") == "issued_unconsumed"
        and admission.get("promotion_authority") is False
        and digest == canonical_digest(body),
        "fixed_pack_admission_digest_or_state_invalid",
    )
    _require(
        admission.get("case_key") == case_input.get("case_key")
        and admission.get("case_input_digest")
        == case_input.get("model_visible_digest")
        and admission.get("source_pack_digest") == case_input.get("source_pack_digest")
        and actual_runtime == expected_runtime
        and admission.get("node_order") == list(NODE_ORDER),
        "fixed_pack_admission_execution_binding_invalid",
    )
    _require(
        admission.get("provider", {}).get("name") == profile.get("provider")
        and admission.get("provider", {}).get("model") == profile.get("model")
        and admission.get("capacity") == profile.get("capacity"),
        "fixed_pack_admission_provider_or_capacity_invalid",
    )
    mode = str(admission.get("execution_mode") or "")
    _require(
        mode in {"live", "fixture"},
        "fixed_pack_admission_execution_mode_invalid",
    )
    if mode == "live":
        _require(
            admission.get("credential_present") is True,
            "fixed_pack_admission_credential_missing",
        )
    else:
        _require(
            admission.get("credential_present") is False,
            "fixed_pack_fixture_admission_must_not_claim_credential",
        )
    _require(
        _utc(observed_at) <= _utc(str(admission.get("expires_at") or "")),
        "fixed_pack_admission_expired",
    )


def _compact_case_input(case_input: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_key": case_input["case_key"],
        "issuer": deepcopy(case_input["issuer"]),
        "research_as_of": case_input["research_as_of"],
        "research_objective_zh": case_input["research_objective_zh"],
        "research_questions_zh": deepcopy(case_input["research_questions_zh"]),
        "report_section_order": deepcopy(case_input["report_section_order"]),
        "input_density": deepcopy(case_input["input_density"]),
        "evidence_items": deepcopy(case_input["evidence_items"]),
        "residual_gaps": deepcopy(case_input["residual_gaps"]),
        "model_rules": deepcopy(case_input["model_rules"]),
        "model_visible_digest": case_input["model_visible_digest"],
    }


def _common_system(case_input: Mapping[str, Any]) -> str:
    return (
        "你是受证据边界约束的机构级金融研究员。只能使用用户消息中的冻结 Evidence Pack，"
        "不得调用工具、联网或补入外部知识。精确数字可以读取、分析和引用，但必须绑定同一条"
        "Evidence alias；不得改变主体、期间、币种、单位或关系方向。明确区分事实、有限推断、"
        "假设与证据缺口。输出有效 JSON 对象，不要 Markdown 代码围栏。研究主体为 "
        + str(case_input["case_key"])
        + "。"
    )


def _report_schema_instruction() -> str:
    return (
        "返回 {\"sections\":[{\"section_id\":字符串,\"points\":[{\"text\":中文分析,"
        "\"epistemic_status\":\"fact|bounded_inference|hypothesis|gap\","
        "\"evidence_aliases\":[\"E001\"],\"gap_aliases\":[\"G001\"]}]}],"
        "\"overall_confidence\":\"high|medium|low\",\"limitations\":[字符串]}。"
        "每个实质判断都必须列 evidence_aliases；缺证据时写 gap，不得补造。"
    )


def build_node_request(
    *,
    node_key: str,
    case_input: Mapping[str, Any],
    prior_outputs: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    compact = _compact_case_input(case_input)
    if node_key == "direct_baseline":
        task = (
            "直接完成一份可供投研讨论的完整报告。这是与多节点链路的同输入基线。"
            + _report_schema_instruction()
        )
        context: Any = deepcopy(dict(case_input))
        node_type = node_key
    elif node_key == "research_lead":
        task = (
            "制定研究组织方案。六个 mandatory_research_families 都必须覆盖。返回 "
            "{\"thesis_hypotheses\":[字符串],\"research_units\":[{\"family\":字符串,"
            "\"question\":字符串,\"evidence_aliases\":[字符串],\"gap_aliases\":[字符串],"
            "\"counter_thesis\":字符串}]}。研究单元只作分析规划，不能改写证据。"
        )
        context = deepcopy(dict(case_input))
        node_type = node_key
    elif node_key.startswith("specialist::"):
        family = node_key.split("::", 1)[1]
        task = (
            f"你只负责研究家族 {family}。返回 "
            "{\"family\":字符串,\"findings\":[{\"text\":中文机制分析,"
            "\"epistemic_status\":\"fact|bounded_inference|hypothesis|gap\","
            "\"evidence_aliases\":[字符串],\"gap_aliases\":[字符串],"
            "\"counterevidence\":字符串,\"confidence\":\"high|medium|low\"}],"
            "\"unresolved\":[字符串]}。不要写通用模板话。"
        )
        context = {
            "case_input": deepcopy(dict(case_input)),
            "lead_output": deepcopy(prior_outputs.get("research_lead")),
            "assigned_family": family,
        }
        node_type = "specialist"
    elif node_key == "cross_unit_synthesis":
        task = (
            "综合六个研究家族，解释需求、产品、供给、竞争、利润、现金、估值和反证之间"
            "的经济机制，不要简单拼接。返回 {\"cross_mechanism_findings\":[{\"text\":字符串,"
            "\"epistemic_status\":字符串,\"evidence_aliases\":[字符串],"
            "\"gap_aliases\":[字符串]}],\"thesis\":字符串,\"antithesis\":字符串,"
            "\"unresolved_conflicts\":[字符串]}。"
        )
        context = {
            "case_input": compact,
            "specialist_outputs": [
                deepcopy(prior_outputs.get(key))
                for key in NODE_ORDER
                if key.startswith("specialist::")
            ],
        }
        node_type = node_key
    elif node_key == "draft_writer":
        task = "根据综合结果写成完整研究初稿。" + _report_schema_instruction()
        context = {
            "case_input": compact,
            "synthesis": deepcopy(prior_outputs.get("cross_unit_synthesis")),
            "specialist_outputs": [
                deepcopy(prior_outputs.get(key))
                for key in NODE_ORDER
                if key.startswith("specialist::")
            ],
        }
        node_type = node_key
    elif node_key == "red_team_critic":
        task = (
            "以反方和事实审计员身份批评初稿。返回 {\"issues\":[{\"severity\":"
            "\"L1|L2|L3|L4\",\"text\":字符串,\"affected_section\":字符串,"
            "\"evidence_aliases\":[字符串]}],\"missing_counter_thesis\":[字符串],"
            "\"rewrite_instructions\":[字符串]}。不得声称自己拥有最终验证权。"
        )
        context = {
            "case_input": compact,
            "draft": deepcopy(prior_outputs.get("draft_writer")),
        }
        node_type = node_key
    elif node_key == "final_writer":
        task = (
            "根据初稿和红队意见完成最终报告；保留证据不足，不得为了流畅而删掉关键缺口。"
            + _report_schema_instruction()
        )
        context = {
            "case_input": compact,
            "draft": deepcopy(prior_outputs.get("draft_writer")),
            "critic": deepcopy(prior_outputs.get("red_team_critic")),
        }
        node_type = node_key
    elif node_key == "verifier":
        task = (
            "只审查最终报告与冻结输入是否一致。返回 {\"claim_checks\":[{\"text\":"
            "字符串,\"status\":\"supported|bounded|unsupported|contradicted\","
            "\"evidence_aliases\":[字符串],\"reason\":字符串}],"
            "\"identity_period_unit_findings\":[字符串],\"unknown_aliases\":[字符串],"
            "\"verdict\":\"pass|pass_with_findings|fail\"}。这是建议，不是晋升权威。"
        )
        context = {
            "case_input": compact,
            "final_report": deepcopy(prior_outputs.get("final_writer")),
        }
        node_type = node_key
    else:
        raise S2FixedPackRuntimeError("fixed_pack_runtime_node_unknown")

    messages = [
        {"role": "system", "content": _common_system(case_input)},
        {
            "role": "user",
            "content": task
            + "\n冻结上下文 JSON：\n"
            + json.dumps(context, ensure_ascii=False, separators=(",", ":")),
        },
    ]
    request = {
        "node_key": node_key,
        "node_type": node_type,
        "case_key": case_input["case_key"],
        "case_input_digest": case_input["model_visible_digest"],
        "model": profile["model"],
        "messages": messages,
        "temperature": profile["temperature"],
        "stream": profile["stream"],
        "enable_thinking": profile["enable_thinking"],
        "max_tokens": profile["maximum_output_tokens"][node_type],
        "response_format": {"type": "json_object"},
    }
    size = len(json.dumps(request, ensure_ascii=False, separators=(",", ":")))
    _require(
        size <= int(profile["maximum_input_characters_per_call"]),
        f"fixed_pack_runtime_node_capacity_exceeded:{node_key}",
    )
    return request


def _parse_json_object(content: str) -> tuple[dict[str, Any] | None, str | None]:
    candidate = str(content or "").strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            return None, "model_output_json_object_missing"
        try:
            value = json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return None, "model_output_json_parse_failed"
    if not isinstance(value, dict):
        return None, "model_output_json_not_object"
    return value, None


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _perform_call(
    *,
    call_index: int,
    node_key: str,
    request: Mapping[str, Any],
    provider_call: ProviderCall,
    captures_root: Path,
    observed_at: str,
) -> tuple[
    dict[str, Any],
    dict[str, Any] | str,
    list[dict[str, Any]],
    str | None,
]:
    call_id = f"call_{call_index:02d}_{node_key.replace('::', '__')}"
    call_root = captures_root / call_id
    _atomic_json(
        call_root / "request.json",
        {
            "call_id": call_id,
            "observed_at": observed_at,
            "request": deepcopy(dict(request)),
            "request_digest": canonical_digest(request),
        },
    )
    try:
        response = dict(provider_call(request))
    except Exception as exc:  # terminalized below; no provider retry is allowed.
        response = {
            "status": "provider_error",
            "failure_reason": f"{type(exc).__name__}: {str(exc)[:1000]}",
            "content": "",
        }
    capture_body = {
        "schema_version": CAPTURE_SCHEMA,
        "call_id": call_id,
        "call_index": call_index,
        "node_key": node_key,
        "request_digest": canonical_digest(request),
        "request": deepcopy(dict(request)),
        "provider_response": deepcopy(response),
        "observed_at": observed_at,
    }
    capture = {**capture_body, "capture_digest": canonical_digest(capture_body)}
    _atomic_json(call_root / "capture.json", capture)
    status = str(response.get("status") or "")
    content = str(response.get("content") or "")
    findings: list[dict[str, Any]] = []
    fatal_code: str | None = None
    parsed: dict[str, Any] | None = None
    if status != "ok":
        fatal_code = f"fixed_pack_runtime_provider_failure:{node_key}:{status}"
    elif not content.strip():
        fatal_code = f"fixed_pack_runtime_empty_output:{node_key}"
    else:
        parsed, parse_finding = _parse_json_object(content)
        if parse_finding:
            findings.append(
                {
                    "level": "L2",
                    "code": parse_finding,
                    "node_key": node_key,
                    "disposition": "raw_text_preserved_chain_continues_no_promotion",
                }
            )
    output: dict[str, Any] | str = parsed if parsed is not None else content
    receipt = {
        "call_id": call_id,
        "node_key": node_key,
        "capture_ref": (
            Path("raw_model_only") / "calls" / call_id / "capture.json"
        ).as_posix(),
        "capture_digest": capture["capture_digest"],
        "request_digest": capture["request_digest"],
        "status": status,
        "finish_reason": response.get("finish_reason"),
        "input_tokens": int(response.get("input_tokens") or 0),
        "output_tokens": int(response.get("output_tokens") or 0),
        "total_tokens": int(response.get("total_tokens") or 0),
    }
    return receipt, output, findings, fatal_code


def _collect_point_rows(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            rows.append(dict(value))
        for child in value.values():
            rows.extend(_collect_point_rows(child))
    elif isinstance(value, list):
        for child in value:
            rows.extend(_collect_point_rows(child))
    return rows


def _normalize_numeric(token: str) -> str:
    return token.strip().strip("()").replace(",", "").lstrip("+")


def evaluate_final_output(
    *,
    final_output: Any,
    case_input: Mapping[str, Any],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    evidence = {
        str(row["evidence_alias"]): dict(row)
        for row in case_input.get("evidence_items") or ()
    }
    materials = {
        str(row["source_material_alias"]): dict(row)
        for row in case_input.get("source_materials") or ()
    }
    if not isinstance(final_output, dict):
        return [
            {
                "level": "L2",
                "code": "final_report_not_structured_json",
                "disposition": "raw_candidate_retained_not_promoted",
            }
        ]
    sections = final_output.get("sections")
    if not isinstance(sections, list) or not sections:
        findings.append(
            {
                "level": "L2",
                "code": "final_report_sections_missing",
                "disposition": "raw_candidate_retained_not_promoted",
            }
        )
    known_aliases = set(evidence)
    known_gaps = {str(row["gap_alias"]) for row in case_input.get("residual_gaps") or ()}
    cited_gaps: set[str] = set()
    for point in _collect_point_rows(final_output):
        text = str(point.get("text") or "")
        aliases = [str(value) for value in point.get("evidence_aliases") or ()]
        gap_aliases = [str(value) for value in point.get("gap_aliases") or ()]
        cited_gaps.update(gap_aliases)
        unknown = (set(aliases) - known_aliases) | (set(gap_aliases) - known_gaps)
        if unknown:
            findings.append(
                {
                    "level": "L2",
                    "code": "final_report_unknown_alias",
                    "aliases": sorted(unknown),
                    "text": text[:240],
                }
            )
        if text and point.get("epistemic_status") != "gap" and not aliases:
            findings.append(
                {
                    "level": "L2",
                    "code": "final_report_substantive_point_uncited",
                    "text": text[:240],
                }
            )
        allowed_surface = ""
        for alias in aliases:
            item = evidence.get(alias) or {}
            allowed_surface += json.dumps(item, ensure_ascii=False)
            material_alias = str(item.get("source_material_alias") or "")
            if material_alias in materials:
                allowed_surface += str(materials[material_alias].get("source_text") or "")
        allowed_numeric = {
            _normalize_numeric(token) for token in _NUMERIC.findall(allowed_surface)
        }
        unsupported = sorted(
            {
                token
                for token in (_normalize_numeric(raw) for raw in _NUMERIC.findall(text))
                if token and token not in allowed_numeric
            }
        )
        if unsupported:
            findings.append(
                {
                    "level": "L1",
                    "code": "final_report_numeric_surface_not_in_cited_evidence",
                    "numeric_tokens": unsupported,
                    "text": text[:240],
                }
            )
    if known_gaps and not cited_gaps:
        findings.append(
            {
                "level": "L2",
                "code": "final_report_residual_gaps_not_cited",
                "disposition": "content_quality_finding",
            }
        )
    return findings


def execute_case(
    *,
    admission: Mapping[str, Any],
    case_input: Mapping[str, Any],
    profile: Mapping[str, Any],
    execution_git_commit: str,
    runner_sha256: str,
    contract_sha256: str,
    profile_sha256: str,
    runtime_root: str | Path,
    shared_ledger: SharedAdmissionConsumptionLedger,
    provider_call: ProviderCall,
    observed_at: str,
) -> dict[str, Any]:
    validate_case_admission(
        admission,
        case_input=case_input,
        profile=profile,
        execution_git_commit=execution_git_commit,
        runner_sha256=runner_sha256,
        contract_sha256=contract_sha256,
        profile_sha256=profile_sha256,
        observed_at=observed_at,
    )
    root = Path(runtime_root).resolve()
    _require(not root.exists(), "fixed_pack_runtime_root_already_exists")
    ledger_path = shared_ledger.path.resolve()
    _require(
        ledger_path != root and root not in ledger_path.parents,
        "fixed_pack_runtime_ledger_inside_attempt_root",
    )
    root.mkdir(parents=True)
    captures_root = root / "raw_model_only" / "calls"
    shared_ledger.reserve(
        admission_digest=str(admission["admission_digest"]),
        admission_id=str(admission["admission_id"]),
        scope=str(admission["scope"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        runtime_identity=str(admission["runtime_identity"]),
        reserved_at=observed_at,
    )
    calls: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    outputs: dict[str, Any] = {}
    terminal_status = "completed"
    terminal_phase = "verifier"
    terminal_code = "fixed_pack_chain_completed"
    active_node = "initialization"
    try:
        for call_index, node_key in enumerate(NODE_ORDER, start=1):
            active_node = node_key
            request = build_node_request(
                node_key=node_key,
                case_input=case_input,
                prior_outputs=outputs,
                profile=profile,
            )
            receipt, output, node_findings, fatal_code = _perform_call(
                call_index=call_index,
                node_key=node_key,
                request=request,
                provider_call=provider_call,
                captures_root=captures_root,
                observed_at=observed_at,
            )
            calls.append(receipt)
            outputs[node_key] = output
            findings.extend(node_findings)
            if fatal_code:
                raise S2FixedPackRuntimeError(fatal_code)
        findings.extend(
            evaluate_final_output(
                final_output=outputs.get("final_writer"),
                case_input=case_input,
            )
        )
        if findings:
            terminal_status = "completed_with_findings"
            terminal_code = "fixed_pack_chain_completed_raw_candidate_not_promoted"
    except S2FixedPackRuntimeError as exc:
        terminal_status = "failed"
        terminal_phase = active_node
        terminal_code = exc.code
        findings.append(
            {
                "level": "L1",
                "code": exc.code,
                "disposition": "terminal_failure_no_retry_no_promotion",
            }
        )

    terminal_body = {
        "schema_version": TERMINAL_SCHEMA,
        "scope": SCOPE,
        "run_id": admission["run_id"],
        "attempt_id": admission["attempt_id"],
        "case_key": case_input["case_key"],
        "case_input_digest": case_input["model_visible_digest"],
        "source_pack_digest": case_input["source_pack_digest"],
        "status": terminal_status,
        "terminal_phase": terminal_phase,
        "terminal_code": terminal_code,
        "call_receipts": calls,
        "observed_counts": {
            "provider_calls": len(calls),
            "model_calls": len(calls),
            "network_tool_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "findings": len(findings),
        },
        "findings": findings,
        "raw_outputs": outputs,
        "direct_baseline_input_digest": case_input["model_visible_digest"],
        "agent_chain_input_digest": case_input["model_visible_digest"],
        "same_input_pair_proven": True,
        "business_artifact_promoted": False,
        "qualified_human_acceptance_required": True,
        "observed_at": observed_at,
        "known_boundary": (
            "This terminal preserves a raw fixed-pack research candidate. It does not "
            "prove dynamic tool research or authorize product delivery."
        ),
    }
    terminal = {**terminal_body, "terminal_digest": canonical_digest(terminal_body)}
    _atomic_json(root / "terminal.json", terminal)
    receipt = shared_ledger.finalize(
        admission_digest=str(admission["admission_digest"]),
        run_id=str(admission["run_id"]),
        attempt_id=str(admission["attempt_id"]),
        terminal_status=terminal_status,
        terminal_phase=terminal_phase,
        terminal_code=terminal_code,
        terminal_result_digest=terminal["terminal_digest"],
        finalized_at=observed_at,
    )
    terminal["shared_admission_receipt"] = receipt.as_dict()
    _atomic_json(root / "terminal_with_receipt.json", terminal)
    return terminal


__all__ = [
    "NODE_ORDER",
    "S2FixedPackRuntimeError",
    "SPECIALIST_FAMILIES",
    "build_node_request",
    "evaluate_final_output",
    "execute_case",
    "issue_case_admission",
    "validate_case_admission",
]
