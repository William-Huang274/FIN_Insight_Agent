"""Public request-size projection, independent of cumulative billing totals."""

CAPACITY_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing"
CAPACITY_AS_OF = "2026-09-09"
MODEL_CAPACITY = {"deepseek-v4-flash": 1_000_000, "deepseek-v4-pro": 1_000_000}


def request_context_usage(events):
    calls = {}
    for event in events:
        if event.get("kind") != "model" or not event.get("call_id"):
            continue
        call = calls.setdefault(event["call_id"], {})
        call.update({k: v for k, v in event.items() if v is not None})
        if event.get("event") == "started":
            call["started_at"] = event.get("recorded_at")
    latest = {}
    for call_id, call in calls.items():
        actor = call.get("actor", "model")
        request_at = call.get("started_at") or call.get("recorded_at") or ""
        if actor in latest and request_at < latest[actor]["request_at"]:
            continue
        measured = call.get("input_tokens")
        measured = measured if type(measured) is int and measured >= 0 else None
        capacity = MODEL_CAPACITY.get(call.get("model"))
        characters, character_limit = call.get("input_characters"), call.get("max_input_characters")
        near_character_limit = type(characters) is int and type(character_limit) is int and character_limit > 0 and characters >= character_limit * .8
        latest[actor] = {"actor": actor, "call_id": call_id, "model": call.get("model"),
            "input_tokens": measured, "input_characters": call.get("input_characters"),
            "max_input_characters": character_limit, "near_character_limit": near_character_limit,
            "capacity_tokens": capacity, "capacity_source": CAPACITY_SOURCE if capacity else None,
            "capacity_as_of": CAPACITY_AS_OF if capacity else None,
            "basis": "provider_reported_input" if measured is not None else "awaiting_provider_usage",
            "recorded_at": call.get("recorded_at"), "status": call.get("status") or "pending",
            "request_at": request_at,
            "near_capacity": measured is not None and capacity is not None and measured >= capacity * .8}
    return {"nodes": list(latest.values()),
        "notice": "每个节点最近一次模型请求的输入量；不是完整会话存档大小，也不是累计计费量。新请求返回前tokens未知。容量来自供应商声明，不代表金融证据可被无损压缩。"}
