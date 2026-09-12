"""One-call paired final-judgment replay; no retrieval, retries or production writes."""
import argparse
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langsmith import tracing_context
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model
from sec_agent.agent_runtime.dell_report_session import session_audit_sinks
from sec_agent.agent_runtime.model_context import project_tool_history


ARCHIVES = {
    "mu": "context-closeout-paid-a4/mu-indexed",
    "sk": "context-closeout-sk-paid-a4/sk-baseline",
}
TYPES = {"ai": AIMessage, "human": HumanMessage, "system": SystemMessage, "tool": ToolMessage}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def archive_messages(root, case):
    path = root / ARCHIVES[case] / "model-context-reasoning.private.jsonl"
    rows = [json.loads(line) for line in path.open(encoding="utf-8")]
    request = [r for r in rows if r["event"] == "request"][-1]
    assert any(r["event"] == "response" and r["call_id"] == request["call_id"] for r in rows)
    assert request["messages_basis"] == "original_history_before_sdk_request_projection"
    return [TYPES[m["type"]].model_validate(m) for m in request["messages"]], {
        "path": str(path), "sha256": sha256(path.read_bytes()).hexdigest(), "call_id": request["call_id"]}


def select_original(case, message):
    if not isinstance(message, ToolMessage) or message.status == "error":
        return False
    artifact = message.artifact
    if not isinstance(artifact, dict):
        return False
    if case == "mu":
        return message.name == "read_research_source" and artifact.get("source_id") in {"P01:S079", "P01:S080"}
    return (message.name == "read_source_document" and artifact.get("operation") == "read"
            and any(i.get("result_state") == "source_bound_passage" for i in artifact.get("items", [])))


def paired_messages(originals, case):
    control = project_tool_history(originals, trigger_tokens=16000, keep=2, workpaper_navigation=True)
    restored = deepcopy(control)
    changes = []
    for i, m in enumerate(originals):
        if select_original(case, m) and control[i].content != m.content:
            restored[i] = deepcopy(m)
            changes.append({"index": i, "tool_call_id": m.tool_call_id, "characters": len(m.content),
                            "content_sha256": sha256(m.content.encode()).hexdigest()})
    assert changes, "no_removed_original_to_restore"
    for i, (a, b) in enumerate(zip(control, restored, strict=True)):
        if i not in {c["index"] for c in changes}:
            assert a.model_dump() == b.model_dump()
    return control, restored, changes


def budget(purpose):
    return TokenBudgetBasis(node_role="specialist", node_purpose=purpose,
        input_scale="Frozen final request from the archived MU or SK bounded question; 30-41 messages. Only specified original source tool replies differ in position; no new retrieval or answer seed.",
        required_outputs=("Complete source-grounded Chinese judgment with period and units", "Explicit unresolved checks without false unread claims"),
        schema_burden="No tools for final delivery, original system and user instructions retained verbatim.",
        materiality_quality_risk="Cash classification, QoQ/YoY, KRW scaling, financial statement scope and unsupported necessity can reverse conclusions.",
        comparable_run_evidence="Prior69 known calls1.29M tokens did not isolate source retention; original final requests completed within12k output. Four single calls initially, at most one paired replication; posthoc development, not blind acceptance.",
        reasoning_profile="agentic_message_history_thinking_enabled", max_input_characters=450000,
        max_output_tokens=12000, timeout_seconds=360, max_transport_attempts=1, retry_policy="none",
        truncation_stop_behavior="fail_closed_no_partial_promotion", input_ceiling_behavior="fail_before_transport")


async def invoke_once(messages, output, purpose, *, basis=None):
    output.mkdir(parents=True, exist_ok=False)
    basis = basis or budget(purpose)
    save(output / "TokenBudgetBasis.json", basis.model_dump(mode="json"))
    from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv
    key = SecretStr(os.environ.get("DEEPSEEK_API_KEY") or _dotenv()["DEEPSEEK_API_KEY"])
    profile = DeepSeekModelProfile(model="deepseek-v4-pro", thinking="enabled", reasoning_effort="low")
    model = case_chat_model(profile, basis, SimpleNamespace(base_url="https://api.deepseek.com"), key)
    payload = model._get_request_payload(messages)
    save(output / "payload.private.json", payload)
    pub, private = session_audit_sinks(output)
    audit = CaseModelAudit(actor=output.name, profile=profile, basis=basis, public_sink=pub, private_sink=private)
    try:
        with tracing_context(enabled=False):
            raw = await audit.model_runnable(model).ainvoke(messages)
        (output / "answer.md").write_text(raw.text, encoding="utf-8")
    except BaseException as exc:
        save(output / "failure.json", {"error_type": type(exc).__name__, "no_retry": True})
        raise
    outcomes = [e for e in audit.events if e.get("event") == "outcome"]
    assert len(outcomes) == 1 and isinstance(outcomes[0].get("total_tokens"), int)
    result = {**outcomes[0], "payload_sha256": digest(payload), "financial_acceptance": "pending_nonblind_source_review"}
    save(output / "result.json", result)
    print(json.dumps({k: result.get(k) for k in ["actor", "status", "input_tokens", "output_tokens", "total_tokens", "cache_hit_tokens", "elapsed_ms"]}), flush=True)
    return raw


async def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    pairs, archives = {}, {}
    for case in ARCHIVES:
        originals, archives[case] = archive_messages(args.archives, case)
        control, restored, changes = paired_messages(originals, case)
        pairs[case] = {"control": control, "restored": restored}
        archives[case]["changes"] = changes
        archives[case]["arms"] = {arm: digest([m.model_dump(mode="json") for m in ms]) for arm, ms in pairs[case].items()}
    manifest = {"archives": archives, "model": "deepseek-v4-pro", "thinking": "enabled", "reasoning_effort": "low", "temperature": 0,
                "single_calls": 4, "new_retrieval_calls": 0, "retries": 0,
                "scope": "Nonblind final-request source-retention ablation, not fresh research/full-case quality or cache benchmark.",
                "authority": "Owner approved proposed bounded round20260912; reuse established case provider credential.",
                "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    save(args.output / "manifest.json", manifest)
    if not args.execute:
        print(json.dumps({"prepared": True, "model_calls": 0, "changes": {k: len(v["changes"]) for k, v in archives.items()}}))
        return
    assert json.loads((args.preparation / "manifest.json").read_text(encoding="utf-8")) == manifest
    order = [("mu", "control"), ("mu", "restored"), ("sk", "restored"), ("sk", "control")]
    if args.reverse:
        order.reverse()
    save(args.output / "order.json", order)
    for case, arm in order:
        await invoke_once(pairs[case][arm], args.output / (case + "-" + arm), "Fixed final judgment: " + case)
    for record in archives.values():
        assert sha256(Path(record["path"]).read_bytes()).hexdigest() == record["sha256"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives", type=Path, default=Path("D:/temp/fin211"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preparation", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--reverse", action="store_true")
    args = parser.parse_args()
    if args.execute and not args.preparation:
        parser.error("--execute requires --preparation")
    asyncio.run(run(args))
