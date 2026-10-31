"""Compare context surfaces on real requests, offline and without source prose.

No provider calls or generated summaries. Token counts are LangChain estimates;
serialized SDK messages include reasoning but exclude unavailable tool schemas.
The old provider usage is recorded separately, never treated as new-policy usage.
"""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda
from pydantic import SecretStr
from replay_source_context import messages
from sec_agent.agent_runtime.continuous_context_surface import expand_provenance, prefix_fingerprint, saved_evidence_index
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
from sec_agent.agent_runtime.model_context import project_tool_history, RequestSummaryMiddleware
from sec_agent.agent_runtime.source_result_view import source_message_views


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


async def checkpoint_replay(record, keep):
    """Real native middleware, deterministic stub summary: lifecycle ONLY."""
    original=messages({"messages":record.get("original_messages",record["messages"])})
    system=[m for m in original if m.type=="system"]
    canonical=[m for m in original if m.type!="system"]
    before=prefix_fingerprint(canonical); prompts=[]
    def summarize(value):
        prompts.append(len(value) if isinstance(value,str) else len(encoded([
            m.model_dump(mode='json',exclude={'artifact','response_metadata','usage_metadata'}) for m in value])))
        # Deliberately NOT financial text. No quality/accuracy claim or future
        # model input may be derived from this fixture.
        return AIMessage(content="OFFLINE LIFECYCLE STUB; NOT A RESEARCH SUMMARY. " * 50)
    middleware=RequestSummaryMiddleware(model=FakeListChatModel(responses=["unused"]),
        audited_model=RunnableLambda(summarize), trigger_tokens=32000,keep_tokens=keep,
        context_policy="continuous_surface",navigation_trigger_tokens=12000,max_summaries=2)
    state={"messages":canonical}
    update=await middleware.abefore_model(state,None)
    if update:
        assert "request_summary" in update, update
        state.update(update)
    view=middleware.projected_messages(state)
    assert view==middleware.projected_messages(deepcopy(state))
    assert prefix_fingerprint(canonical)==before
    # Native pair-safe cutoff must not hide first-delivery results.
    last=max(i for i,m in enumerate(canonical) if m.type=="ai")
    assert all(m in view for m in canonical[last:])
    source_ids={r["tool_call_id"] for r in saved_evidence_index(canonical)}
    if update:
        summary=update["request_summary"]
        remaining={m.tool_call_id for m in view if isinstance(m,ToolMessage)}
        assert all(cid in summary["message"]["content"] or cid in remaining for cid in source_ids)
    sdk=ReasoningPreservingChatDeepSeek(model="deepseek-flash",api_key=SecretStr("offline"),max_retries=0,
        tool_context_policy="continuous_surface", tool_context_trigger_tokens=12000)
    payload=sdk._get_request_payload([*system,*view],tools=[{"type":"function","function":{
        "name":"read_saved_result","parameters":{"type":"object"}}}])
    return {"call_id":record["call_id"],"tail_tokens":keep,"fixture_summary_calls":len(prompts),
        "actual_summary_prompt_characters":max(prompts,default=0),
        "fixture_sdk_message_characters":len(encoded(payload["messages"])),
        "canonical_sha256":before,"source_receipt_readers_preserved":len(source_ids)}


async def run(audits):
    candidates = {
        "current_keep2": {"policy":"legacy_window", "trigger_tokens":6000, "keep":2},
        "lossless_only": {"policy":"continuous_surface", "trigger_tokens":None},
        "navigation_only": {"policy":"continuous_surface", "trigger_tokens":12000},
    }
    reader = next(g.tool for g in conversation_tools(thread_id="offline-replay") if g.tool.name == "read_saved_result")
    sdk = ReasoningPreservingChatDeepSeek(model="deepseek-flash", api_key=SecretStr("offline"), max_retries=0)
    result, checkpoints = [], []
    for audit in audits:
        for line in audit.open(encoding="utf-8"):
            record = json.loads(line)
            if record.get("event") != "request":
                continue
            original = messages(record); before = prefix_fingerprint(original)
            expected = source_message_views(original)
            original_tools = {m.tool_call_id: m for m in original if m.type == "tool"}
            last_assistant = max(i for i, m in enumerate(original) if m.type == "ai")
            for label, options in candidates.items():
                view = project_tool_history(original, saved_result_reader=True, **options)
                counts = {"full_source_items":0, "indexed_source_items":0, "indexed_navigation_items":0,
                          "readback_checks":0, "cleared_results":0}
                if options["policy"] == "continuous_surface":
                    assert view == project_tool_history(view, saved_result_reader=True, **options), "projection not idempotent"
                    expanded = expand_provenance(view)
                    for i, (old, current) in enumerate(zip(expected, expanded)):
                        if old.type != "tool" or old.status != "success":
                            assert old == current
                            continue
                        try:
                            body, shown = json.loads(old.content), json.loads(current.content)
                        except (ValueError, TypeError):
                            assert old == current
                            continue
                        if not isinstance(shown, dict):
                            assert body == shown
                            continue
                        kind = shown.get("context_surface", {}).get("kind")
                        if kind:
                            assert i < last_assistant, "first delivery was archived"
                            key = "indexed_source_items" if kind == "saved_evidence_index" else "indexed_navigation_items"
                            counts[key] += len(shown["items"])
                            assert len(shown["items"]) == len(body["items"])
                            for item in shown["items"]:
                                read = reader.func(tool_call_id=old.tool_call_id, runtime=SimpleNamespace(state={"messages":original}),
                                    json_pointer=item["original_json_pointer"], max_characters=24000)
                                parts = [read["content"]]
                                while read["next_offset"] is not None:
                                    read = reader.func(tool_call_id=old.tool_call_id, runtime=SimpleNamespace(state={"messages":original}),
                                        json_pointer=item["original_json_pointer"], offset=read["next_offset"], max_characters=24000)
                                    parts.append(read["content"])
                                restored = json.loads("".join(parts))
                                identity = "passage_id" if kind == "saved_evidence_index" else "candidate_id"
                                assert restored[identity] == item[identity]
                                # Compare original stored item including all qualifiers,
                                # dates, units, unknown metadata and source hashes.
                                position = int(item["original_json_pointer"].split("/")[-1])
                                assert restored == json.loads(original_tools[old.tool_call_id].content)["items"][position]
                                counts["readback_checks"] += 1
                        elif "duplicate_of_tool_call_id" in shown:
                            # Existing exact-read dedup retains its target in request.
                            target = next(m for m in expanded if m.type=="tool" and m.tool_call_id==shown["duplicate_of_tool_call_id"])
                            assert json.loads(target.content) == body
                        else:
                            assert shown == body, (label, record["call_id"], i)
                            if isinstance(body, dict):
                                counts["full_source_items"] += sum(x.get("result_state")=="source_bound_passage" for x in body.get("items",[]) if isinstance(x,dict))
                else:
                    counts["cleared_results"] = sum(bool(m.response_metadata.get("context_editing",{}).get("cleared")) for m in view)
                wire = sdk._get_request_payload(view)["messages"]
                assert prefix_fingerprint(original) == before, "canonical history changed"
                result.append({"audit":str(audit), "call_id":record["call_id"], "policy":label,
                    "canonical_sha256":before, "content_characters":sum(len(str(m.content)) for m in view),
                    "message_token_estimate":count_tokens_approximately(view),
                    "sdk_message_characters_including_reasoning":len(encoded(wire)), **counts})
            for keep in (6000, 12000, 24000):
                checkpoints.append(await checkpoint_replay(record,keep))
    return {"paid_calls":0, "summaries_generated":0, "network_disabled":True,
            "measurement_scope":"Recorded summary projection + real canonical suffix; SDK messages only, tool schemas excluded. No quality or cache-hit claim.",
            "checkpoint_measurement_scope":"Native checkpoint replay from full original journal using a conspicuous constant summary stub; output sizes prove execution/retention only, NOT real summary size, quality, provider tokens or cost.",
            "checkpoint_rows":checkpoints, "rows":result}


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--audit",type=Path,action="append",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    async def offline():
        # Windows creates its local event-loop socket pair before this guard.
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Offline replay prohibits network")):
            return await run(args.audit)
    result=asyncio.run(offline())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    for label in dict.fromkeys(r["policy"] for r in result["rows"]):
        rows=[r for r in result["rows"] if r["policy"]==label]
        print(label, "requests",len(rows), "SDK message chars",min(r["sdk_message_characters_including_reasoning"] for r in rows),
              max(r["sdk_message_characters_including_reasoning"] for r in rows),
              "readbacks",sum(r["readback_checks"] for r in rows))
