from __future__ import annotations

from copy import deepcopy
from typing import Any


def verify_answer_claims(
    *,
    answer: dict[str, Any],
    raw_answer: dict[str, Any] | None,
    ledger_rows: list[dict[str, Any]],
    context_rows: list[dict[str, Any]],
    judgment_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    allowed_metric_ids = {str(row.get("metric_id") or "") for row in ledger_rows if row.get("metric_id")}
    allowed_evidence_ids = _context_evidence_ids(context_rows) | _ledger_evidence_ids(ledger_rows)
    evidence_ids_by_metric_id = _ledger_evidence_ids_by_metric_id(ledger_rows)
    plan_drivers = _plan_drivers(judgment_plan)
    candidates = _claim_candidates(raw_answer or {}, answer)
    verified = []
    for idx, candidate in enumerate(candidates, start=1):
        checked = _verify_candidate(
            candidate,
            idx=idx,
            allowed_metric_ids=allowed_metric_ids,
            allowed_evidence_ids=allowed_evidence_ids,
            evidence_ids_by_metric_id=evidence_ids_by_metric_id,
            plan_drivers=plan_drivers,
        )
        verified.append(checked)
    rendered = _render_verified_answer(answer, verified)
    rejected_count = sum(1 for item in verified if item["status"] == "rejected")
    downgraded_count = sum(1 for item in verified if item["status"] == "downgraded")
    promoted_count = sum(1 for item in verified if item["status"] == "promoted")
    return {
        "schema_version": "claim_first_verification_report_v0.1",
        "answer": rendered,
        "claims": verified,
        "claim_status": "verified" if rejected_count == 0 else "partially_verified",
        "unsupported_claim_count": rejected_count,
        "summary": {
            "candidate_count": len(verified),
            "promoted_count": promoted_count,
            "downgraded_count": downgraded_count,
            "rejected_count": rejected_count,
            "judgment_plan_driver_count": len(plan_drivers),
            "ledger_metric_count": len(allowed_metric_ids),
            "context_evidence_count": len(allowed_evidence_ids),
        },
    }


def _verify_candidate(
    candidate: dict[str, Any],
    *,
    idx: int,
    allowed_metric_ids: set[str],
    allowed_evidence_ids: set[str],
    evidence_ids_by_metric_id: dict[str, list[str]],
    plan_drivers: list[dict[str, Any]],
) -> dict[str, Any]:
    metric_ids = _ordered_allowed(_string_list(candidate.get("metric_ids")), allowed_metric_ids)
    evidence_ids = _ordered_allowed(_string_list(candidate.get("evidence_ids")), allowed_evidence_ids)
    propagated_evidence_ids = _evidence_ids_for_metric_ids(metric_ids, evidence_ids_by_metric_id, allowed_evidence_ids)
    evidence_ids = _ordered_unique([*evidence_ids, *propagated_evidence_ids])
    invalid_metric_ids = [item for item in _string_list(candidate.get("metric_ids")) if item not in allowed_metric_ids]
    invalid_evidence_ids = [item for item in _string_list(candidate.get("evidence_ids")) if item not in allowed_evidence_ids]
    matched_driver = _best_plan_driver(metric_ids, evidence_ids, plan_drivers)
    reasons = []
    status = "promoted"
    if invalid_metric_ids or invalid_evidence_ids:
        status = "rejected"
        reasons.append("contains ids outside current ledger/context")
    if not metric_ids and not evidence_ids:
        status = "rejected"
        reasons.append("no ledger metric_id or evidence_id support")
    if status != "rejected" and plan_drivers and not matched_driver:
        status = "downgraded"
        reasons.append("supported by current ids but not mapped to Judgment Plan driver")
    if status != "rejected" and matched_driver:
        strength = str(matched_driver.get("support_strength") or matched_driver.get("conclusion_strength") or "").lower()
        if strength == "weak" and str(candidate.get("confidence") or "").lower() in {"high", "strong"}:
            status = "downgraded"
            reasons.append("Judgment Plan support strength is weak")
    if not reasons:
        reasons.append("claim has current ledger/context support")
    return {
        "claim_id": str(candidate.get("claim_id") or f"claim_{idx}"),
        "source": candidate.get("source") or {},
        "claim": str(candidate.get("claim") or ""),
        "status": status,
        "reason": "; ".join(reasons),
        "metric_ids": metric_ids,
        "evidence_ids": evidence_ids,
        "invalid_metric_ids": invalid_metric_ids,
        "invalid_evidence_ids": invalid_evidence_ids,
        "matched_driver_id": str((matched_driver or {}).get("driver_id") or (matched_driver or {}).get("id") or ""),
        "confidence": str(candidate.get("confidence") or "medium"),
    }


def _claim_candidates(raw_answer: dict[str, Any], answer: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for idx, item in enumerate(_raw_claim_list(raw_answer), start=1):
        if not isinstance(item, dict):
            continue
        candidates.append(
            {
                "claim_id": str(item.get("claim_id") or item.get("id") or f"raw_claim_{idx}"),
                "source": {"kind": "raw_claim", "index": idx - 1},
                "claim": str(item.get("claim_zh") or item.get("claim") or item.get("point") or ""),
                "metric_ids": _string_list(item.get("metric_ids") or item.get("supporting_metric_ids")),
                "evidence_ids": _string_list(item.get("evidence_ids") or item.get("supporting_evidence_ids")),
                "confidence": str(item.get("confidence") or item.get("conclusion_strength") or "medium"),
            }
        )
    for idx, item in enumerate(answer.get("decision_drivers") or [], start=1):
        if not isinstance(item, dict):
            continue
        claim = "；".join(
            part
            for part in [
                str(item.get("driver_claim") or item.get("claim") or ""),
                str(item.get("why_it_matters") or item.get("rationale") or ""),
            ]
            if part
        )
        candidates.append(
            {
                "claim_id": f"driver_{idx}",
                "source": {"kind": "decision_driver", "index": idx - 1},
                "claim": claim,
                "metric_ids": _string_list(item.get("supporting_metric_ids") or item.get("metric_ids")),
                "evidence_ids": _string_list(item.get("supporting_evidence_ids") or item.get("evidence_ids")),
                "confidence": str(item.get("conclusion_strength") or "medium"),
            }
        )
    for idx, item in enumerate(answer.get("key_points") or [], start=1):
        if not isinstance(item, dict):
            continue
        candidates.append(
            {
                "claim_id": f"key_point_{idx}",
                "source": {"kind": "key_point", "index": idx - 1},
                "claim": str(item.get("point") or ""),
                "metric_ids": _string_list(item.get("metric_ids")),
                "evidence_ids": _string_list(item.get("evidence_ids")),
                "confidence": str(item.get("confidence") or "medium"),
            }
        )
    for field, text_keys in _memo_claim_specs().items():
        for idx, item in enumerate(answer.get(field) or [], start=1):
            if not isinstance(item, dict):
                continue
            claim = "；".join(str(item.get(key) or "") for key in text_keys if str(item.get(key) or ""))
            candidates.append(
                {
                    "claim_id": f"{field}_{idx}",
                    "source": {"kind": field, "index": idx - 1},
                    "claim": claim,
                    "metric_ids": _string_list(item.get("metric_ids") or item.get("supporting_metric_ids")),
                    "evidence_ids": _string_list(item.get("evidence_ids") or item.get("supporting_evidence_ids")),
                    "confidence": str(item.get("confidence") or item.get("conclusion_strength") or "medium"),
                }
            )
    return candidates


def _render_verified_answer(answer: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    rendered = deepcopy(answer)
    by_source = {
        (str(item.get("source", {}).get("kind") or ""), int(item.get("source", {}).get("index") or 0)): item
        for item in claims
    }
    kept_drivers = []
    for idx, driver in enumerate(rendered.get("decision_drivers") or []):
        verdict = by_source.get(("decision_driver", idx))
        if verdict and verdict["status"] == "rejected":
            continue
        if verdict:
            driver["supporting_metric_ids"] = verdict["metric_ids"]
            driver["supporting_evidence_ids"] = verdict["evidence_ids"]
        if verdict and verdict["status"] == "downgraded":
            driver["conclusion_strength"] = "weak" if str(driver.get("conclusion_strength") or "").lower() == "strong" else str(driver.get("conclusion_strength") or "medium")
            driver["caveat"] = _append_caveat(driver.get("caveat"), "该判断已按 claim verifier 降级，只能作为当前证据支持范围内的有限观察。")
        kept_drivers.append(driver)
    kept_points = []
    for idx, point in enumerate(rendered.get("key_points") or []):
        verdict = by_source.get(("key_point", idx))
        if verdict and verdict["status"] == "rejected":
            continue
        if verdict:
            point["metric_ids"] = verdict["metric_ids"]
            point["evidence_ids"] = verdict["evidence_ids"]
        if verdict and verdict["status"] == "downgraded":
            point["confidence"] = "low" if str(point.get("confidence") or "").lower() == "high" else str(point.get("confidence") or "medium")
            point["point"] = _append_sentence(point.get("point"), "该判断已按当前证据范围降级。")
        kept_points.append(point)
    rendered["decision_drivers"] = kept_drivers
    rendered["key_points"] = kept_points
    for field in _memo_claim_specs():
        kept_items = []
        for idx, item in enumerate(rendered.get(field) or []):
            if not isinstance(item, dict):
                continue
            verdict = by_source.get((field, idx))
            if verdict and verdict["status"] == "rejected":
                continue
            if verdict:
                item["metric_ids"] = verdict["metric_ids"]
                item["evidence_ids"] = verdict["evidence_ids"]
            if verdict and verdict["status"] == "downgraded":
                item["confidence"] = "low" if str(item.get("confidence") or "").lower() == "high" else str(item.get("confidence") or "medium")
                item["caveat"] = _append_caveat(item.get("caveat"), "该判断已按 claim verifier 降级。")
            kept_items.append(item)
        rendered[field] = kept_items
    rejected = [item for item in claims if item["status"] == "rejected"]
    downgraded = [item for item in claims if item["status"] == "downgraded"]
    if rejected:
        rendered.setdefault("limitations", []).append(
            f"Claim verifier removed {len(rejected)} unsupported candidate claim(s) before rendering."
        )
    if downgraded:
        rendered.setdefault("limitations", []).append(
            f"Claim verifier downgraded {len(downgraded)} claim(s) to avoid overstating current evidence."
        )
    if not rendered.get("key_points") and not rendered.get("decision_drivers"):
        rendered["summary"] = "当前模型候选判断缺少可验证的 ledger/evidence 支撑，不能渲染为结论。"
        rendered.setdefault("limitations", []).append("No candidate claim survived claim-first verification.")
    return rendered


def _memo_claim_specs() -> dict[str, tuple[str, ...]]:
    return {
        "what_changed": ("claim",),
        "why_it_matters": ("insight", "business_implication"),
        "peer_readthrough": ("peer_or_group", "role", "readthrough", "caveat"),
        "counterarguments": ("claim", "why_it_could_weaken_thesis"),
    }


def _raw_claim_list(raw_answer: dict[str, Any]) -> list[Any]:
    for key in ("claim_candidates", "claims", "verified_claims"):
        value = raw_answer.get(key)
        if isinstance(value, list):
            return value
    return []


def _plan_drivers(judgment_plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(judgment_plan, dict):
        return []
    drivers = judgment_plan.get("drivers")
    if drivers is None:
        drivers = judgment_plan.get("decision_drivers")
    return [item for item in drivers or [] if isinstance(item, dict)]


def _best_plan_driver(metric_ids: list[str], evidence_ids: list[str], plan_drivers: list[dict[str, Any]]) -> dict[str, Any] | None:
    metric_set = set(metric_ids)
    evidence_set = set(evidence_ids)
    best: tuple[int, dict[str, Any] | None] = (0, None)
    for driver in plan_drivers:
        driver_metrics = set(
            _string_list(driver.get("supporting_metric_ids") or driver.get("required_metric_ids") or driver.get("metric_ids"))
        )
        driver_evidence = set(
            _string_list(
                driver.get("supporting_evidence_ids") or driver.get("required_evidence_ids") or driver.get("evidence_ids")
            )
        )
        score = len(metric_set & driver_metrics) * 10 + len(evidence_set & driver_evidence)
        if score > best[0]:
            best = (score, driver)
    return best[1]


def _context_evidence_ids(context_rows: list[dict[str, Any]]) -> set[str]:
    ids = set()
    for row in context_rows:
        for key in ("evidence_id", "object_id", "source_evidence_id"):
            value = str(row.get(key) or "")
            if value:
                ids.add(value)
    return ids


def _ledger_evidence_ids(ledger_rows: list[dict[str, Any]]) -> set[str]:
    ids = set()
    for row in ledger_rows:
        for key in ("source_evidence_id", "evidence_id", "object_id"):
            value = str(row.get(key) or "")
            if value:
                ids.add(value)
    return ids


def _ledger_evidence_ids_by_metric_id(ledger_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = {}
    for row in ledger_rows:
        metric_id = str(row.get("metric_id") or "")
        if not metric_id:
            continue
        evidence_ids = [str(row.get(key) or "") for key in ("source_evidence_id", "evidence_id", "object_id")]
        mapping[metric_id] = _ordered_unique([*mapping.get(metric_id, []), *evidence_ids])
    return mapping


def _evidence_ids_for_metric_ids(
    metric_ids: list[str],
    evidence_ids_by_metric_id: dict[str, list[str]],
    allowed_evidence_ids: set[str],
) -> list[str]:
    out: list[str] = []
    for metric_id in metric_ids:
        for evidence_id in evidence_ids_by_metric_id.get(metric_id, []):
            if evidence_id and evidence_id in allowed_evidence_ids:
                out.append(evidence_id)
    return _ordered_unique(out)


def _ordered_allowed(values: list[str], allowed: set[str]) -> list[str]:
    out = []
    for value in values:
        if value in allowed and value not in out:
            out.append(value)
    return out


def _ordered_unique(values: list[str]) -> list[str]:
    out = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value:
        return [str(value)]
    return []


def _append_caveat(existing: Any, addition: str) -> str:
    text = str(existing or "").strip()
    if not text:
        return addition
    if addition in text:
        return text
    return f"{text} {addition}"


def _append_sentence(existing: Any, addition: str) -> str:
    text = str(existing or "").strip()
    if not text:
        return addition
    if text.endswith(("。", ".", "！", "!")):
        return f"{text}{addition}"
    return f"{text}。{addition}"
