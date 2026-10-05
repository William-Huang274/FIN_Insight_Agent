"""Restored/live reads, exact recovery and repeated checkpoints, no provider calls."""
from copy import deepcopy
import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from sec_agent.agent_runtime.model_context import task_boundary_history
from test_research_context_checkpoint import checkpoint_message, model, request_checkpoint
from test_research_working_state import working_note, source_messages


def test_legacy_terminal_feedback_uses_live_envelope_without_losing_draft_or_errors():
    from sec_agent.agent_runtime.model_context import coalesce_context_snapshots
    candidate = {'narrative_markdown': 'Current draft with exact financial scope. ' * 500}
    context = {'turn_index': 7, 'task_context': {'assignment': 'Original research question'},
        'progress': {'feedback': [{'code': 'invalid_field', 'path': '/claims/2/statement'}]},
        'execution_budget': {'remaining_model_turns': 3}, 'allowed_actions': ['revise_workpaper'],
        'submission_to_repair': {'candidate': candidate, 'base_submission_digest': 'a' * 64}}
    action = AIMessage(content='', tool_calls=[{'id': 'submit', 'name': 'SubmitWorkpaperAction', 'args': candidate}])
    rows = [HumanMessage(content='Original user question'), action,
        ToolMessage(tool_call_id='submit', content=json.dumps(context))]
    original = deepcopy(rows)
    out = coalesce_context_snapshots(rows)
    current = json.loads(out[-1].content)['current_context']
    assert current['progress'] == context['progress']
    assert current['task_context'] == context['task_context']
    assert current['submission_to_repair']['base_submission_digest'] == 'a' * 64
    assert current['submission_to_repair']['candidate']['identical_snapshot_retained_at']['tool_call_id'] == 'submit'
    assert out[-1].name == 'SubmitWorkpaperAction' and out[-1].tool_call_id == 'submit'
    assert out[1].tool_calls[0]['args'] == candidate and rows == original
    assert len(out[-1].content) < len(rows[-1].content) / 4
    assert coalesce_context_snapshots(out) == out
    # A source tool returning JSON that resembles a runtime object is not host state.
    source = deepcopy(rows)
    source[1].tool_calls[0]['name'] = 'RequestSourceAction'
    assert coalesce_context_snapshots(source)[-1] == source[-1]
    unpaired = [rows[-1]]
    assert coalesce_context_snapshots(unpaired) == unpaired


def test_current_candidate_replaces_historical_snapshots_but_not_sources_or_errors():
    from sec_agent.agent_runtime.model_context import coalesce_context_snapshots
    def repair(version):
        return {'candidate': {'thesis': f'Draft version {version}. ' * 600},
            'current_candidate_digest': str(version) * 64, 'base_submission_digest': 'b' * 64,
            'validation_feedback': [{'code': f'error{version}', 'path': '/claims/1'}]}
    rows = [HumanMessage(content=json.dumps({'submission_to_repair': repair(1)}))]
    for v in (2, 3):
        rows.append(ToolMessage(tool_call_id=f'edit{v}', name='ReviseWorkpaperAction', content=json.dumps({
            'result': {'accepted': False, 'exact_error': f'field error {v}', 'passage': 'Exact original source.'},
            'current_context': {'submission_to_repair': repair(v)}})))
    original = deepcopy(rows)
    out = coalesce_context_snapshots(rows)
    old = json.loads(out[0].content)['submission_to_repair']
    assert old['superseded_candidate'] is True and 'candidate' not in old
    assert old['current_candidate_at'] == {'message_index': 2, 'field': 'current_context.submission_to_repair'}
    assert old['historical_validation_feedback'] == repair(1)['validation_feedback']
    assert json.loads(out[-1].content)['current_context']['submission_to_repair'] == repair(3)
    for i in (1, 2):
        assert json.loads(out[i].content)['result'] == json.loads(rows[i].content)['result']
    assert rows == original and coalesce_context_snapshots(out) == out
    assert sum(len(m.content) for m in out) < sum(len(m.content) for m in rows) * .5


def test_accepted_submission_archives_completed_reads_for_later_revision():
    old = source_messages('OLD-SOURCE')
    old[-1].content = json.dumps({'ref_id': 'OLD-SOURCE', 'passage': 'Prior source body ' * 600})
    submit = AIMessage(content='', tool_calls=[{'id': 'submit', 'name': 'SubmitWorkpaperAction',
        'args': {'narrative_markdown': 'Current accepted artifact', 'source_ids': ['OLD-SOURCE']}}])
    receipt = ToolMessage(name='SubmitWorkpaperAction', tool_call_id='submit', content=json.dumps({
        'result': {'accepted': True}, 'current_context': {'task_context': {
            'accepted_revision_baseline': {'submission': 'Current accepted artifact'},
            'revision_feedback': [{'diagnosis': 'Check changed period'}]}}}))
    new = source_messages('NEW-SOURCE')
    new[-1].content = json.dumps({'ref_id': 'NEW-SOURCE', 'passage': 'Current revision evidence'})
    rows = [*old, submit, receipt, *new]
    original = deepcopy(rows)
    out = task_boundary_history(rows)
    assert 'Prior source body' not in '\n'.join(str(m.content) for m in out)
    assert 'Current revision evidence' in '\n'.join(str(m.content) for m in out)
    assert 'Current accepted artifact' in '\n'.join(str(m.content) for m in out)
    assert 'Check changed period' in '\n'.join(str(m.content) for m in out)
    assert rows == original
    rejected = deepcopy(rows)
    rejected[len(old)+1].content = json.dumps({'result': {'accepted': False}})
    assert 'Prior source body' in '\n'.join(str(m.content) for m in task_boundary_history(rejected))


def test_accepted_revision_replaces_only_older_authoring_proposals():
    from sec_agent.agent_runtime.deepseek_structured_agents import _prior_research_actions
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    old = {'action': 'submit_workpaper', 'narrative_markdown': 'Old draft ' * 300,
        'claims': [{'evidence_ids': ['OLD'], 'fact_ids': ['CALC::1']}]}
    read = {'action': 'request_source', 'selection': {'node_id': 'ORIGINAL'}}
    calculation = {'action': 'request_calculation', 'source_ids': ['OPERAND']}
    latest = {**old, 'narrative_markdown': 'New unresolved draft'}
    submission = {**old, 'narrative_markdown': 'Accepted baseline'}
    request = {'notebook': {'model_turn_records': [
        {'action': {'action': 'native_tool_batch', 'tool_calls': [
            {'name': 'SubmitWorkpaperAction', 'id': 'old', 'args': old},
            {'name': 'RequestSourceAction', 'id': 'read', 'args': read}]}},
        {'action': calculation}, {'action': latest}]},
        'task_context': {'accepted_revision_baseline': {'submission': submission,
            'submission_digest': canonical_sha256(submission), 'through_model_turn': 2}}}
    original = deepcopy(request)
    actions = _prior_research_actions(request)
    assert actions[0]['tool_calls'][0]['args']['source_ids'] == ['OLD', 'CALC::1']
    assert 'historical_operation' in actions[0]['tool_calls'][0]['args']
    assert actions[0]['tool_calls'][1]['args']['action'] == read['action']
    assert actions[1:] == [calculation, latest]
    assert request == original
    for invalid in ({}, {'through_model_turn': 4}, {'submission_digest': 'stale'}):
        changed = deepcopy(request)
        if invalid: changed['task_context']['accepted_revision_baseline'].update(invalid)
        else: changed['task_context'] = {}
        assert _prior_research_actions(changed) == [r['action'] for r in original['notebook']['model_turn_records']]


def test_accepted_revision_preserves_malformed_call_receipts_without_interpreting_them():
    from sec_agent.agent_runtime.deepseek_structured_agents import _prior_research_actions
    from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
    failed = [
        {'name': 'SubmitWorkpaperAction', 'type': 'invalid_tool_call', 'args': '{"action":'},
        {'name': 'SubmitWorkpaperAction', 'args': '{"action":"submit_workpaper"}'},
        {'name': 'SubmitWorkpaperAction', 'args': None},
        {'name': 'SubmitWorkpaperAction', 'args': []},
        {'name': 'SubmitWorkpaperAction', 'type': 'invalid_tool_call',
            'args': {'action': 'submit_workpaper', 'narrative_markdown': 'Rejected proposal'}},
        None,
    ]
    accepted = {'action': 'submit_workpaper', 'narrative_markdown': 'Accepted answer'}
    request = {'notebook': {'model_turn_records': [{'action': {
        'action': 'native_tool_batch', 'tool_calls': [*failed, {'name': 'SubmitWorkpaperAction', 'args': accepted}]}}]},
        'task_context': {'accepted_revision_baseline': {'submission': accepted,
            'submission_digest': canonical_sha256(accepted), 'through_model_turn': 1}}}
    original = deepcopy(request)
    projected = _prior_research_actions(request)
    assert projected[0]['tool_calls'][:-1] == failed
    assert projected[0]['tool_calls'][-1]['args']['historical_operation'] is True
    assert request == original


def test_latest_handoff_reuses_identical_accepted_baseline_and_working_state():
    from sec_agent.agent_runtime.model_context import coalesce_context_snapshots
    task = {'accepted_revision_baseline': {'submission': {'narrative_markdown': 'Original answer. ' * 300}},
        'research_working_state': working_note(phase_status='working')}
    rows = [HumanMessage(content=json.dumps({'task_context': task})),
        ToolMessage(tool_call_id='fresh', content=json.dumps({'result': {'passage': 'New source'},
            'current_context': {'task_context': task, 'allowed_actions': ['request_source']}}))]
    original = deepcopy(rows)
    out = coalesce_context_snapshots(rows)
    body = json.loads(out[1].content)
    assert body['result'] == {'passage': 'New source'}
    for key in task:
        assert body['current_context']['task_context'][key]['identical_snapshot_retained_at']['message_index'] == 0
    changed = deepcopy(rows)
    new = json.loads(changed[1].content)
    new['current_context']['task_context']['research_working_state']['next_step'] = 'Different next read'
    changed[1].content = json.dumps(new)
    assert json.loads(coalesce_context_snapshots(changed)[1].content)['current_context']['task_context']['research_working_state'] == new['current_context']['task_context']['research_working_state']
    assert rows == original


def test_dependency_papers_reuse_exact_values_across_changing_task_progress():
    from sec_agent.agent_runtime.model_context import coalesce_context_snapshots
    paper = {'task_id': 'cloud', 'revision': 'r1', 'narrative': 'Source-bound finding. ' * 500,
             'source_ids': ['PASSAGE::original']}
    task = {'assignment': 'Research demand', 'dependency_workpapers': [paper],
            'future_runtime_handoff': {'instructions': 'Preserve original scope. ' * 30}}
    rows = [HumanMessage(content=json.dumps({'task_context': task}))]
    for i in range(3):
        rows.append(ToolMessage(tool_call_id=f'read-{i}', content=json.dumps({
            'result': {'passage': f'Fresh original {i}', 'period': 'FY2027 Q1'},
            'current_context': {'task_context': {**task, 'runtime_progress': {'n': i}}}})))
    original = deepcopy(rows)
    projected = coalesce_context_snapshots(rows)
    for i in (1, 2):
        body = json.loads(projected[i].content)
        for key in ('dependency_workpapers', 'future_runtime_handoff'):
            assert body['current_context']['task_context'][key]['identical_snapshot_retained_at'] == {
                'message_index': 0, 'field': f'task_context.{key}'}
        assert body['result'] == json.loads(rows[i].content)['result']
    assert json.loads(projected[-1].content)['current_context']['task_context']['dependency_workpapers'] == [paper]
    assert coalesce_context_snapshots(projected) == projected
    changed = deepcopy(rows)
    body = json.loads(changed[1].content)
    body['current_context']['task_context']['dependency_workpapers'][0]['revision'] = 'r2'
    changed[1].content = json.dumps(body)
    assert json.loads(coalesce_context_snapshots(changed)[1].content)['current_context']['task_context']['dependency_workpapers'][0]['revision'] == 'r2'
    assert rows == original


def test_checkpoint_archived_reads_do_not_reintroduce_dependency_papers():
    paper = {'task_id': 'upstream', 'revision': 'r1',
             'narrative': 'Original upstream evidence and interpretation. ' * 800}
    task = {'assignment': 'Original scope', 'dependency_workpapers': [paper]}
    rows = [HumanMessage(content=json.dumps({'task_context': task}))]
    for i in range(4):
        batch = source_messages(f'OLD-{i}')
        body = json.loads(batch[-1].content)
        body['current_context'] = {'task_context': {**deepcopy(task), 'runtime_progress': {'n': i}}}
        if i == 2:
            body['current_context']['task_context']['dependency_workpapers'][0]['revision'] = 'r2'
        batch[-1].content = json.dumps(body)
        rows.extend(batch)
    recent = source_messages('RECENT')
    rows.extend(recent)
    rows.extend(checkpoint_message(working_note(phase_status='working', findings=[], retain_source_ids=[])))
    original = deepcopy(rows)
    projected = task_boundary_history(rows)
    assert rows == original
    assert projected[-3] == recent[-1]  # Latest read still available in full.
    for i in range(4):
        body = json.loads(projected[2 + i * 2].content)
        assert 'archived_result' in body and 'RequestSourceAction' in body['archived_result']
        saved = body['current_context']['task_context']
        if i == 2:
            assert saved['dependency_workpapers'][0]['revision'] == 'r2'
        else:
            assert saved['dependency_workpapers']['identical_snapshot_retained_at'] == {
                'message_index': 0, 'field': 'task_context.dependency_workpapers'}
        assert saved['runtime_progress'] == {'n': i}
    assert sum(m.content.count(paper['narrative']) for m in projected) == 2


def observation(key, *, turn=1, **updates):
    return {"kind": "evidence", "status": "success", "failure": None,
        "references": [{"ref_id": key}], "content": [{"text": key + " original USD FY2027 " * 8000}],
        "recovery": {"saved_observation_id": key, "read_tool": "RequestSourceAction",
            "arguments": {"action": "request_source", "selection": {"node_id": key}}, "batch_turn": turn},
        **updates}


def test_exact_rows_share_one_original_across_restore_live_with_distinct_receipts():
    from sec_agent.agent_runtime.model_context import coalesce_context_snapshots
    item = observation("BODY", content=[{"passage_id": "BODY", "text": "FY2027 USD original " * 100}])
    rows = [HumanMessage(content=json.dumps({"progress": {"observations": [item]}})),
        ToolMessage(name="RequestSourceAction", tool_call_id="new", content=json.dumps({"result": {
            "observations": [{**item, "recovery": {"saved_observation_id": "different-call"}}]}}))]
    original = deepcopy(rows)
    projected = coalesce_context_snapshots(rows)
    second = json.loads(projected[1].content)["result"]["observations"][0]
    assert second["content"][0]["identical_source_row_at"]["message_index"] == 0
    assert second["references"] == item["references"]
    assert second["recovery"]["saved_observation_id"] == "different-call"
    assert rows == original
    assert coalesce_context_snapshots(projected) == projected
    for field, value in (("references", [{"ref_id": "BODY", "authority_state": "retrieval_candidate"}]),
                         ("status", "tool_failure"), ("provenance_kind", "another-source"),
                         ("content", [{"passage_id": "BODY", "text": "Changed revision " * 100}])):
        changed = deepcopy(rows)
        body = json.loads(changed[1].content)
        body["result"]["observations"][0][field] = value
        changed[1].content = json.dumps(body)
        assert coalesce_context_snapshots(changed)[1] == changed[1]


def test_document_pin_does_not_expand_to_all_descendant_candidates():
    from sec_agent.agent_runtime.model_context import _retain_navigation_rows
    rows = [{"node_id": name, "candidate_id": "LOC::" + name, "document_id": "DOC",
        "parent_document_id": "DOC", "result_state": "retrieval_candidate",
        "writer_citable": False, "numeric_fact_authority": False} for name in ("DOC", "A", "B")]
    item = observation("LOC::DOC", content=rows)
    projected = _retain_navigation_rows(item, {"DOC", "LOC::B"})
    assert [r["node_id"] for r in projected["content"]] == ["DOC", "B"]
    assert item["content"] == rows


def test_latest_accepted_state_releases_old_pins_and_completed_operand_reads():
    old = working_note(phase_status="working", findings=[{"finding": "Old candidate", "source_ids": ["OLD"],
        "limitation": "Preview only"}], retain_source_ids=["OLD"])
    # Use the actual note schema's fixture fields for the source binding.
    old["findings"] = [{**working_note()["findings"][0], "source_ids": ["OLD"]}]
    initial = HumanMessage(content=json.dumps({"task_context": {"research_working_state": old},
        "progress": {"observations": [observation("OLD"), observation("CALC-SOURCE")],
        "prior_actions": [{"action": "native_tool_batch", "tool_calls": [
            {"name": "UpdateResearchStateAction", "args": {"action": "update_research_state", "working_state": old}},
            {"name": "RequestCalculationAction", "args": {"action": "request_calculation", "source_ids": ["CALC-SOURCE"]}}]}]}}))
    rows = [initial, *source_messages("LATEST"), *checkpoint_message(working_note(
        phase_status="working", findings=[], retain_source_ids=[]))]
    projected = task_boundary_history(rows)
    observations = json.loads(projected[0].content)["progress"]["observations"]
    assert "content" not in observations[0]
    assert "content" not in observations[1]
    assert observations[1]['recovery']['saved_observation_id'] == 'CALC-SOURCE'
    assert "OLD" in json.loads(initial.content)["task_context"]["research_working_state"]["findings"][0]["source_ids"]


def test_first_restored_request_consumes_host_accepted_checkpoint_without_new_note():
    note = working_note(phase_status="working", findings=[], retain_source_ids=["PIN"])
    body = {"task_context": {"accepted_restored_checkpoint": True, "research_working_state": note},
        "progress": {"observations": [observation("OLD"), observation("PIN"), observation("NEW", turn=2)],
        "prior_actions": [{"action": "native_tool_batch", "tool_calls": [{"name": "UpdateResearchStateAction",
            "args": {"action": "update_research_state", "working_state": note}}]}]}}
    initial = HumanMessage(content=json.dumps(body))
    view = json.loads(task_boundary_history([initial])[0].content)
    assert "content" not in view["progress"]["observations"][0]
    assert view["progress"]["observations"][1:] == body["progress"]["observations"][1:]
    assert view["task_context"]["research_working_state"] == note
    assert view["progress"]["prior_actions"] == []
    assert view["progress"]["archived_action_count"] == 1
    body["task_context"].pop("accepted_restored_checkpoint")
    assert "content" not in json.loads(task_boundary_history([HumanMessage(content=json.dumps(body))])[0].content)["progress"]["observations"][0]


def test_legacy_restored_checkpoint_marker_requires_exact_accepted_receipt():
    from sec_agent.agent_runtime.specialist_graph import _model_request, SpecialistNotebook
    from test_specialist_graph import _input, _ScriptedModel, _ToolPorts, _evidence_action
    from test_specialist_tool_batch import _handoff
    from sec_agent.agent_runtime.specialist_graph import SpecialistAgenticDependencies, build_specialist_agentic_state_graph
    ports = _ToolPorts()
    state = build_specialist_agentic_state_graph(dependencies=SpecialistAgenticDependencies(
        model_turn=_ScriptedModel([_evidence_action(), _handoff]), evidence_tool=ports.evidence,
        finance_tool=ports.finance)).compile().invoke(_input())
    note = working_note(phase_status="working")
    state["research_working_state"] = note
    for accepted, checkpoint, changed in [(True, True, False), (False, True, False), (True, False, False), (True, True, True)]:
        receipt = {"accepted": accepted, "checkpoint": checkpoint, "working_state": {**note, **({"next_action": "changed"} if changed else {})}}
        state["tool_results"] = [{"name": "UpdateResearchStateAction", "content": json.dumps(receipt)}]
        req = _model_request(state=state, notebook=SpecialistNotebook.model_validate_json(json.dumps(state["notebook"])), working_state_enabled=True)
        assert bool(req["task_context"].get("accepted_restored_checkpoint")) == (accepted and checkpoint and not changed)


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
        if cycle:
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
        assert finance['recovery']['read_tool'] == 'RequestFinanceAction'
        assert finance['content']  # Numeric operands stay visible until explicit dismissal.
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
