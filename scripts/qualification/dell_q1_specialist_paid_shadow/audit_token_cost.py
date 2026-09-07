"""Offline usage/context attribution; never emits prompts, source text, or reasoning.

Prices are a dated scenario, NOT a provider invoice. Message component sizes are
characters, NOT estimated DeepSeek tokens. Original run artifacts are read only.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path


PRICE_SOURCE = "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/"
PRICE_AS_OF = "2026-09-07"
# CNY per million: cache hit, cache miss, output; peak is twice off-peak.
OFF_PEAK = {"deepseek-v4-pro": (0.15, 4.5, 13.5),
            "deepseek-v4-flash": (0.05, 1.5, 4.5),
            "deepseek-v4-flash-vision-exp": (0.05, 1.5, 4.5)}


def encoded(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)


def records(path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def checked_integer(value):
    return value if type(value) is int and value >= 0 else None


def usage_details(raw):
    metadata = raw.get("usage_metadata") or {}
    usage = (raw.get("response_metadata") or {}).get("token_usage") or {}
    hit = checked_integer(usage.get("prompt_cache_hit_tokens"))
    if hit is None:
        hit = checked_integer((metadata.get("input_token_details") or {}).get("cache_read"))
    reason = checked_integer((usage.get("completion_tokens_details") or {}).get("reasoning_tokens"))
    if reason is None:
        reason = checked_integer((metadata.get("output_token_details") or {}).get("reasoning"))
    return hit, reason


def peak_multiplier(timestamp):
    local = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(
        timezone(timedelta(hours=8)))
    return 2 if local.weekday() < 5 and (9 <= local.hour < 12 or 14 <= local.hour < 18) else 1


def cost_parts(model, hit, miss, output, multiplier):
    prices = OFF_PEAK[model]
    return {name: count * rate * multiplier / 1_000_000 for name, count, rate in zip(
        ("cached_input", "uncached_input", "output"), (hit, miss, output), prices)}


def message_components(messages):
    sizes = Counter()
    for message in messages:
        kind, content = message.get("type", "unknown"), message.get("content", "")
        if kind == "tool":
            try:
                payload = json.loads(content)
            except (ValueError, TypeError):
                sizes["tool_non_json"] += len(encoded(content))
                continue
            if not isinstance(payload, dict):
                sizes["tool_non_object"] += len(encoded(payload))
                continue
            for key, value in payload.items():
                if key == "result" and isinstance(value, dict):
                    for child, body in value.items():
                        sizes[f"tool_result.{child}"] += len(encoded(body))
                elif key == "current_context" and isinstance(value, dict):
                    for child, body in value.items():
                        sizes[f"tool_context.{child}"] += len(encoded(body))
                else:
                    sizes[f"tool.{key}"] += len(encoded(value))
        else:
            sizes[f"{kind}_content"] += len(encoded(content))
            if kind == "ai":
                sizes["ai_reasoning"] += len(encoded((message.get("additional_kwargs") or {}).get("reasoning_content", "")))
                sizes["ai_tool_calls"] += len(encoded(message.get("tool_calls") or []))
    return sizes


def summarize(calls):
    result = {"requests": len(calls), "statuses": dict(Counter(c["status"] for c in calls))}
    for key in ("input_tokens", "output_tokens", "total_tokens", "cache_hit_tokens", "cache_miss_tokens", "reasoning_tokens"):
        result[key] = sum(c[key] for c in calls if c[key] is not None)
        result[key + "_known_requests"] = sum(c[key] is not None for c in calls)
    result["modeled_cost_cny"] = sum(c["modeled_cost_cny"] for c in calls if c["modeled_cost_cny"] is not None)
    result["cost_known_requests"] = sum(c["modeled_cost_cny"] is not None for c in calls)
    result["cost_parts_cny"] = dict(sum((Counter(c["cost_parts_cny"] or {}) for c in calls), Counter()))
    result["input_component_characters"] = dict(sum((Counter(c["input_component_characters"]) for c in calls), Counter()))
    result["message_content_characters"] = sum(c["message_content_characters"] for c in calls)
    result["previously_seen_message_characters"] = sum(c["previously_seen_message_characters"] for c in calls)
    return result


def phase_for_actor(actor):
    if actor.startswith("context_summary:"):
        return "context_summary"
    if actor.startswith("lead:"):
        return "planning"
    if actor.startswith("specialist:"):
        return "research"
    if actor.startswith("author_"):
        return "author_revision"
    if actor in {"counter", "verifier", "research_verifier", "report_verifier"}:
        return "review"
    if actor in {"writer", "quick_writer"}:
        return "writing_or_answer"
    return "synthesis" if actor == "synthesis" else "other_disclosed_actor"


def audit(root):
    calls, not_sent = [], []
    for audit_path in sorted(root.glob("*/model-call-events.jsonl")):
        events = [e for e in records(audit_path) if e.get("call_id") and e.get("execution_source") != "saved_response_replay"]
        starts = {e["call_id"]: e for e in events if e.get("event") == "started"}
        outcomes = {e["call_id"]: e for e in events if e.get("event") == "outcome"}
        if len(starts) != sum(e.get("event") == "started" for e in events):
            raise ValueError(f"duplicate_call_id:{audit_path.parent.name}")
        not_sent.extend({"attempt": audit_path.parent.name, "status": e.get("status")}
                        for cid, e in outcomes.items() if cid not in starts)
        private = {}
        for event in records(audit_path.parent / "model-context-reasoning.private.jsonl"):
            # Native middleware writes request and response separately. Merge
            # the two by call ID; legacy combined rows remain supported.
            private.setdefault(event["call_id"], {}).update(event)
        seen = defaultdict(set)
        for cid, start in starts.items():
            outcome = outcomes.get(cid, {})
            context = private.get(cid, {})
            raw = context.get("raw_response") or outcome.get("raw_response") or {}
            inp, out, total = (checked_integer(outcome.get(key)) if outcome.get("usage_reported") else None
                               for key in ("input_tokens", "output_tokens", "total_tokens"))
            hit, reason = usage_details(raw)
            hit = hit if hit is not None else checked_integer(outcome.get("cache_hit_tokens"))
            reason = reason if reason is not None else checked_integer(outcome.get("reasoning_tokens"))
            miss = inp - hit if inp is not None and hit is not None else None
            if miss is not None and miss < 0:
                raise ValueError("cache_hits_exceed_input")
            if reason is not None and out is not None and reason > out:
                raise ValueError("reasoning_exceeds_output")
            model = start.get("model")
            parts = cost_parts(model, hit, miss, out, peak_multiplier(start["recorded_at"])) if (
                model in OFF_PEAK and hit is not None and miss is not None and out is not None) else None
            messages = context.get("messages") or []
            actor = start.get("actor", "unknown")
            component_sizes = message_components(messages)
            repeated, measured = 0, 0
            next_seen = set()
            for message in messages:
                # Drop SDK response/token metadata, which is not sent as content.
                semantic = {key: message.get(key) for key in
                            ("type", "content", "tool_call_id", "tool_calls", "additional_kwargs")}
                digest = hashlib.sha256(encoded(semantic).encode()).hexdigest()
                size = sum(message_components([message]).values())
                measured += size
                if digest in seen[actor]:
                    repeated += size
                next_seen.add(digest)
            seen[actor].update(next_seen)
            calls.append({"attempt": audit_path.parent.name, "call_id": cid, "actor": actor,
                          "phase": phase_for_actor(actor),
                          "message_basis": context.get("messages_basis", "legacy_original_request_history"),
                          "recorded_at": start["recorded_at"], "model": model,
                          "status": outcome.get("status", "pending"),
                          "input_tokens": inp, "output_tokens": out, "total_tokens": total,
                          "cache_hit_tokens": hit, "cache_miss_tokens": miss, "reasoning_tokens": reason,
                          "input_component_characters": dict(component_sizes),
                          "message_content_characters": measured,
                          "previously_seen_message_characters": repeated,
                          "private_context_available": bool(context),
                          "cost_parts_cny": parts, "modeled_cost_cny": sum(parts.values()) if parts else None})
    grouped = {}
    for key in ("attempt", "actor", "phase", "status"):
        groups = defaultdict(list)
        for call in calls:
            groups[call[key]].append(call)
        grouped[key] = {name: summarize(rows) for name, rows in groups.items()}
    return {"price_source": PRICE_SOURCE, "price_as_of": PRICE_AS_OF,
            "cost_is_invoice": False, "missing_usage_is_not_zero": True,
            "component_unit": "archived model-request characters before SDK tool projection; per-call message_basis distinguishes original versus summarized history; excludes tool schemas/serialization; not provider-token attribution",
            "attribution": "post-hoc descriptive; replay/context/failure categories are not independent causal shares",
            "totals": summarize(calls), "not_sent_outcomes": not_sent, "groups": grouped, "calls": calls}


def audit_context_projection(root, *, trigger_tokens=50000, keep=6):
    """Measure already-observed development histories, never replay the model."""
    from langchain_core.messages import messages_from_dict
    from pydantic import SecretStr
    from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
    baseline = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-no-provider"), use_responses_api=False)
    candidate = ReasoningPreservingChatDeepSeek(model="deepseek-v4-pro", api_key=SecretStr("offline-no-provider"),
        use_responses_api=False, tool_context_trigger_tokens=trigger_tokens, tool_context_keep=keep)
    rows = []
    for path in sorted(root.glob("*/model-context-reasoning.private.jsonl")):
        with path.open(encoding="utf-8-sig") as stream:
            for line in stream:
                record = json.loads(line)
                if record.get("event") == "response" or not record.get("messages"):
                    continue
                messages = messages_from_dict([{"type": m["type"], "data": m} for m in record["messages"]])
                original = encoded([m.model_dump(mode="json") for m in messages])
                before = baseline._get_request_payload(messages)["messages"]
                after = candidate._get_request_payload(messages)["messages"]
                if (original != encoded([m.model_dump(mode="json") for m in messages]) or len(before) != len(after)
                        or [m for m in before if m["role"] != "tool"] != [m for m in after if m["role"] != "tool"]
                        or [m["tool_call_id"] for m in before if m["role"] == "tool"] != [m["tool_call_id"] for m in after if m["role"] == "tool"]):
                    raise ValueError("context_projection_mutated_history_reasoning_or_tool_pairing")
                rows.append({"attempt": path.parent.name, "call_id": record["call_id"], "actor": record.get("actor", "unknown"),
                    "wire_message_characters_before": len(encoded(before)), "wire_message_characters_after": len(encoded(after)),
                    "changed_tool_results": sum(a != b for a, b in zip(before, after))})
    totals = {"requests": len(rows), "requests_with_cleared_results": sum(r["changed_tool_results"] > 0 for r in rows)}
    for key in ("wire_message_characters_before", "wire_message_characters_after", "changed_tool_results"):
        totals[key] = sum(r[key] for r in rows)
    return {"mode": "offline_historical_request_projection", "trigger_tokens_approximate": trigger_tokens, "keep": keep,
        "component_unit": "serialized SDK message characters including preserved reasoning; tool schemas excluded and unchanged",
        "quality_or_paid_cost_improvement_proven": False, "new_provider_calls": 0,
        "history_reasoning_tool_pairing_unchanged": True, "totals": totals, "calls": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--context-projection", action="store_true",
                        help="Offline request-only native tool-edit measurement; no provider or quality claims")
    parser.add_argument("--trigger-tokens", type=int, default=50000)
    parser.add_argument("--keep-tool-results", type=int, default=6)
    args = parser.parse_args()
    result = audit_context_projection(args.attempt_root, trigger_tokens=args.trigger_tokens, keep=args.keep_tool_results) if args.context_projection else audit(args.attempt_root)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps(result["totals"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
