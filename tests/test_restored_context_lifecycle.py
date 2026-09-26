"""Restored/live reads, exact recovery and repeated checkpoints, no provider calls."""
from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sec_agent.agent_runtime.model_context import task_boundary_history
from test_research_context_checkpoint import checkpoint_message, model, request_checkpoint
from test_research_working_state import working_note, source_messages


def observation(key, *, turn=1, **updates):
    return {"kind": "evidence", "status": "success", "failure": None,
        "references": [{"ref_id": key}], "content": [{"text": key + " original USD FY2027 " * 8000}],
        "recovery": {"saved_observation_id": key, "read_tool": "RequestSourceAction",
            "arguments": {"action": "request_source", "selection": {"node_id": key}}, "batch_turn": turn},
        **updates}


def test_restored_checkpoint_has_same_protections_as_live_history_and_no_mutation():
    items = [observation("OLD"), observation("PIN"), observation("CALC", kind="finance"),
        observation("FAIL", status="tool_failure", failure={"code": "timeout"}),
        observation("NO-READER", recovery={}), observation("LATEST-A", turn=2), observation("LATEST-B", turn=2)]
    scope = {"task_context": {"assignment": "Compare quarters, not calendar years"},
        "progress": {"observations": items, "prior_actions": []}}
    rows = [HumanMessage(content=json.dumps(scope)), HumanMessage(content="User correction: keep USD units."),
        *checkpoint_message(working_note(phase_status="working", findings=[], retain_source_ids=["PIN"]))]
    original = deepcopy(rows)
    projected = task_boundary_history(rows)
    saved = json.loads(projected[0].content)
    assert saved["task_context"] == scope["task_context"] and projected[1] == rows[1]
    assert "content" not in saved["progress"]["observations"][0]
    assert saved["progress"]["observations"][0]["recovery"] == items[0]["recovery"]
    assert saved["progress"]["observations"][1:] == items[1:]
    assert rows == original and task_boundary_history(rows) == projected
    rejected = deepcopy(rows); rejected[-1].status = "error"
    assert "content" in json.loads(task_boundary_history(rejected)[0].content)["progress"]["observations"][0]
    # Once a new native read arrives, it becomes the latest protected batch.
    advanced = rows[:-2] + source_messages("NEW-LIVE") + rows[-2:]
    updated = task_boundary_history(advanced)
    assert "content" not in json.loads(updated[0].content)["progress"]["observations"][-1]
    assert updated[3] == advanced[3]


def test_repeated_restored_and_live_checkpoints_release_space_and_supersede_notes():
    old_note = working_note(phase_status="working", findings=[], retain_source_ids=[],
        last_task_detail="OBSOLETE-PROSE " * 1000)
    rows = [HumanMessage(content=json.dumps({"task_context": {"assignment": "Keep original scope",
        "research_working_state": old_note}, "progress": {"observations": [observation("OLD"),
        observation("LAST", turn=2, content=[{"text": "Latest original"}])],
        "prior_actions": [{"action": "update_research_state", "working_state": old_note}]}}))]
    chat = model(research_checkpoint_tokens=30000)
    for cycle in range(4):
        if cycle:
            rows += source_messages(f"BULK-{cycle}")
            rows[-1].content = json.dumps({"ref_id": f"BULK-{cycle}", "text": "old search " * 65000})
            rows += source_messages(f"RECENT-{cycle}")
        assert request_checkpoint(rows, chat)[2] is not None
        note = working_note(phase_status="working", findings=[], retain_source_ids=[],
            last_task_detail=f"Current unfinished comparison {cycle}")
        pair = checkpoint_message(note)
        pair[0].tool_calls[0].update(id=f"cp-{cycle}", args={"working_state": note})
        pair[1].tool_call_id = f"cp-{cycle}"
        rows += pair
        continuation, _, pressure = request_checkpoint(rows, chat)
        assert pressure is None  # No immediate request for another paid note.
        payload = chat._get_request_payload(continuation)
        encoded = json.dumps(payload)
        assert len(encoded) < 90000
        assert "OBSOLETE-PROSE" not in encoded
        assert note["last_task_detail"] in encoded and "Annual composition remains unknown" in encoded
        if cycle:
            assert f"Current unfinished comparison {cycle-1}" not in encoded
        # Fresh read delivered after acceptance must survive the first exposure.
        fresh = source_messages(f"FRESH-{cycle}")
        assert task_boundary_history([*rows, *fresh])[-1] == fresh[-1]


def test_restored_recovery_locators_execute_against_native_saved_results_after_new_run():
    from sec_agent.agent_runtime.specialist_graph import (
        SpecialistAgenticDependencies, build_specialist_agentic_state_graph)
    from sec_agent.agent_runtime.deepseek_structured_agents import _project_agentic_specialist_request
    from test_specialist_graph import _input, _ScriptedModel, _ToolPorts, _evidence_action, _finance_action
    from test_specialist_tool_batch import _handoff, _batch
    ports = _ToolPorts()
    value = {**_input(), "max_model_turns": 5}
    def graph(turn, prior=None):
        return build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
            model_turn=turn, evidence_tool=ports.evidence, finance_tool=ports.finance), recovery_state=prior).compile()
    initial = graph(_ScriptedModel([_evidence_action(), _finance_action(), _handoff])).invoke(value)
    original = deepcopy(initial)
    calls = []
    def resume(request):
        calls.append(request)
        if len(calls) > 1:
            return _handoff(request)
        projected = _project_agentic_specialist_request(request)
        evidence, finance = projected["progress"]["observations"]
        assert "recovery" not in finance  # Numeric operands stay pinned.
        locator = evidence["recovery"]
        assert locator["saved_observation_id"] == initial["notebook"]["observations"][0]["observation_digest"]
        disabled = deepcopy(request)
        disabled["allowed_actions"].remove("request_evidence")
        assert "recovery" not in _project_agentic_specialist_request(disabled)["progress"]["observations"][0]
        return _batch(request, [locator["arguments"]])
    recovered = graph(resume, initial).invoke({**value, "run_invocation_id": "new-recovery-invocation"})
    assert len(ports.calls) == 2  # No third dispatch or paid external lookup.
    reply = json.loads(calls[-1]["tool_results"][0]["content"])
    assert reply["checkpoint_replay"]["new_tool_dispatch"] is False
    assert reply["observations"][0]["content"] == initial["notebook"]["observations"][0]["content"]
    assert recovered["notebook"]["tool_action_count"] == initial["notebook"]["tool_action_count"]
    assert initial == original


def test_pinned_navigation_rows_are_identical_in_live_and_restored_views():
    kept = {"result_state": "retrieval_candidate", "candidate_id": "PIN", "writer_citable": False,
        "numeric_fact_authority": False, "title": "Exact title", "revision": "v2"}
    unused = {**kept, "candidate_id": "UNUSED", "title": "Different title"}
    gap = {"result_state": "typed_gap", "code": "partial_catalog"}
    obs = observation("PIN", content=[kept, unused, gap])
    restored = HumanMessage(content=json.dumps({"progress": {"observations": [obs], "prior_actions": []}}))
    live = source_messages("catalog")
    live[-1].content = json.dumps({"result": {"observations": [obs]}})
    rows = [restored, *live, *source_messages("RECENT"),
        *checkpoint_message(working_note(phase_status="working", findings=[], retain_source_ids=["PIN"]))]
    original = deepcopy(rows)
    projected = task_boundary_history(rows)
    saved = json.loads(projected[0].content)["progress"]["observations"][0]
    current = json.loads(projected[2].content)["result"]["observations"][0]
    assert saved == current
    assert saved["content"] == [kept, gap] and saved["references"] == obs["references"]
    assert "read_tool" in json.loads(projected[2].content)["result"]["context_recovery"]
    assert rows == original
    # Unknown/citable rows cannot be treated as a divisible menu.
    from sec_agent.agent_runtime.model_context import _retain_navigation_rows
    for row in ({**unused, "writer_citable": True}, {"result_state": "source_bound_passage", "text": "original"},
                {"result_state": "numeric_fact", "value": 123}):
        indivisible = {**obs, "content": [kept, row]}
        assert _retain_navigation_rows(indivisible, {"PIN"}) == indivisible
def test_library_candidate_authority_can_be_bound_in_native_references():
    from sec_agent.agent_runtime.model_context import _retain_navigation_rows
    rows=[{'result_state':'retrieval_candidate','node_id':key,'preview':'Literal original preview'} for key in ('PIN','OTHER')]
    refs=[{'ref_id':r['node_id'],'authority_state':'retrieval_candidate',
           'writer_citable':False,'numeric_fact_authority':False} for r in rows]
    obs=observation('library', content=rows, references=refs)
    original=deepcopy(obs)
    projected=_retain_navigation_rows(obs, {'PIN'})
    assert obs==original and projected['content']==[rows[0]] and projected['references']==refs[:1]
    for bad in ({**obs,'references':[]}, {**obs,'references':[{**r,'writer_citable':True} for r in refs]},
                {**obs,'content':[rows[0],{**rows[1],'writer_citable':True}]},
                {**obs,'content':[rows[0],{**rows[1],'node_id':'UNBOUND'}]}):
        assert _retain_navigation_rows(bad, {'PIN'})==bad


def test_checkpoint_preserves_error_payload_and_inherits_method_by_exact_pointer():
    from sec_agent.agent_runtime.model_context import task_boundary_history
    task={'assignment':'Original scope ' * 100,'stage_methods':{'text':'Method ' * 200}}
    rows=[HumanMessage(content=json.dumps({'task_context':task})),
          ToolMessage(name='RequestSourceAction',tool_call_id='failed',status='error',content=json.dumps({
              'result':{'error':'Source timeout is not missing disclosure'},
              'current_context':{'task_context':{**task,'runtime_progress':{'n':2}},'progress':{'counter':2}}})),
          *checkpoint_message(working_note(phase_status='working',findings=[],retain_source_ids=[]))]
    original=deepcopy(rows)
    projected=task_boundary_history(rows)
    error=json.loads(projected[1].content)
    assert rows==original and projected[1].status=='error'
    assert error['result']=={'error':'Source timeout is not missing disclosure'}
    assert 'progress' not in error['current_context']
    assert projected[0]==rows[0]
    assert error['current_context']['task_context']['runtime_progress']=={'n':2}


def test_checkpoint_latest_navigation_projection_keeps_latest_original_passage():
    kept={'result_state':'retrieval_candidate','node_id':'PIN','title':'Exact candidate'}
    unused={**kept,'node_id':'OTHER','title':'Other candidate'}
    refs=[{'ref_id':key,'authority_state':'retrieval_candidate','writer_citable':False,
           'numeric_fact_authority':False} for key in ('PIN','OTHER')]
    obs=observation('menu',content=[kept,unused],references=refs)
    rows=source_messages('catalog')
    rows[-1].content=json.dumps({'result':{'observations':[obs]}})
    # One live batch holds both the menu and a genuine source result.
    rows[0].tool_calls.append({'name':'RequestSourceAction','id':'original','args':{},'type':'tool_call'})
    passage=ToolMessage(name='RequestSourceAction',tool_call_id='original',content=json.dumps({
        'result':{'observations':[observation('ORIGINAL', content=[{'result_state':'source_bound_passage',
            'writer_citable':True,'passage':'Exact period, unit and original restriction.'}])]}}))
    rows += [passage,*checkpoint_message(working_note(phase_status='working',findings=[],retain_source_ids=['PIN']))]
    original=deepcopy(rows)
    projected=task_boundary_history(rows)
    menu=json.loads(projected[1].content)['result']['observations'][0]
    assert rows==original and menu['content']==[kept] and menu['references']==refs[:1]
    assert projected[2]==passage


def test_accepted_note_is_not_duplicated_by_real_next_turn_envelope():
    from sec_agent.agent_runtime.model_context import coalesce_context_snapshots
    for cycle in range(3):
        note = working_note(phase_status="working", findings=[], retain_source_ids=[],
            last_task_detail=f"Unfinished comparison {cycle}: " + "Exact public working memory. " * 1500)
        receipt = {"result": {"accepted": True, "checkpoint": True, "working_state": note},
            "current_context": {"allowed_actions": ["request_source"],
                "task_context": {"assignment": "Original five-company task", "research_working_state": deepcopy(note),
                    "runtime_progress": {"turn": cycle}}}}
        message = ToolMessage(name="UpdateResearchStateAction", tool_call_id=f"cp-{cycle}",
            content=json.dumps(receipt))
        original = deepcopy(message)
        projected = coalesce_context_snapshots([message])
        body = json.loads(projected[0].content)
        assert message == original and body["result"] == receipt["result"]
        assert body["current_context"]["allowed_actions"] == ["request_source"]
        task = body["current_context"]["task_context"]
        assert task["assignment"] == "Original five-company task" and task["runtime_progress"] == {"turn": cycle}
        assert task["research_working_state"]["identical_snapshot_retained_at"] == {
            "tool_call_id": f"cp-{cycle}", "field": "result.working_state"}
        assert len(projected[0].content) < len(message.content) * .6
        assert coalesce_context_snapshots(projected) == projected
        for changed in ("different_note", "rejected", "error"):
            value = deepcopy(receipt)
            if changed == "different_note":
                value["current_context"]["task_context"]["research_working_state"]["last_task_detail"] = "Updated instruction"
            elif changed == "rejected":
                value["result"]["accepted"] = False
            other = ToolMessage(name=message.name, tool_call_id=message.tool_call_id,
                content=json.dumps(value), status="error" if changed == "error" else "success")
            assert coalesce_context_snapshots([other]) == [other]
