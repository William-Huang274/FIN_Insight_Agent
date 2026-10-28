import asyncio
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from sec_agent.agent_runtime.delegated_task_contract import TaskCommand, freeze_input, child_task_context
from sec_agent.agent_runtime.delegated_task_runtime import DelegatedTaskRuntime
from sec_agent.agent_runtime.delegated_task_tools import completion_tool
from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.working_memory import WorkingMemory
from test_conversation_agent import ScriptedTools


def fixture():
    root, run, cp, child = [str(uuid4()) for _ in range(4)]
    command = TaskCommand(command_id=uuid4(), execution_id=root, parent_thread_id=root,
        parent_run_id=run, parent_checkpoint_id=cp, child_thread_id=child, action='create',
        root_budget_id='shared-root-budget', manifest_digest='sha256:'+'a'*64,
        task={'assignment': {'subtask_id': 'compare', 'objective': 'Compare these two original observations with their periods.',
            'success_criteria': ['Explain comparable changes'],
            'relieved_work': 'Read the original disclosures and calculate comparable growth.',
            'retained_parent_work': 'Explain the industry implications and compare competing explanations.'},
            'delivery_intent': 'workpaper', 'method_ids': [], 'materials': [], 'working_notes': []})
    parent = {'checkpoint': {'checkpoint_id': cp}, 'values': {'messages': [
        {'type': 'human', 'content': 'OBSOLETE PHASE REQUIREMENT: complete every report section'},
        {'type': 'ai', 'content': 'OLD CONCLUSION'}]}}
    spec = json.loads((Path(__file__).resolve().parents[1]/'configs/research/runtime/conversation.json').read_text())
    fixed = freeze_input(command, parent, allowed_methods=[], note_reader=lambda *args: None, runtime_configuration=spec)
    return command, parent, fixed


def test_frozen_inputs_do_not_copy_old_obligations_and_do_not_follow_parent_edits():
    command, parent, fixed = fixture()
    before = deepcopy(fixed)
    parent['values']['messages'].append({'type': 'human', 'content': 'NEW PARENT PLAN'})
    context = child_task_context(fixed)
    assert all(s not in str(context) for s in ('OBSOLETE', 'OLD CONCLUSION', 'NEW PARENT PLAN'))
    assert fixed == before and context['assignment'] == command.task.assignment.model_dump(mode='json')
    fixed['task']['assignment']['objective'] = 'A different task and different scope entirely'
    with pytest.raises(ValueError, match='digest_mismatch'):
        child_task_context(fixed)


def test_create_rejects_recursive_parent_and_unobserved_material():
    command, parent, fixed = fixture()
    body = command.model_dump(mode='json')
    body['parent_thread_id'] = str(uuid4())
    with pytest.raises(ValueError, match='only_root'):
        TaskCommand.model_validate(body)
    body = command.model_dump(mode='json')
    body['task']['materials'] = [{'source_id': 'NUMFACT:guessed', 'tool_call_id': 'unknown'}]
    with pytest.raises(ValueError, match='not_observed'):
        freeze_input(body, parent, allowed_methods=[], note_reader=lambda *args: None,
                     runtime_configuration=fixed['runtime_configuration'])


def test_parent_method_selection_does_not_hide_other_host_approved_methods(tmp_path):
    from sec_agent.agent_runtime.delegated_task_graph import child_tools
    command, parent, previous = fixture()
    command.task.method_ids = ['research_loop']
    fixed = freeze_input(command, parent, allowed_methods=['research_loop', 'scenario_sensitivity'],
        note_reader=lambda *args: None, runtime_configuration=previous['runtime_configuration'])
    assert child_task_context(fixed)['method_ids'] == ['research_loop']
    memory = WorkingMemory(tmp_path/'memory.sqlite', owner='alice', workspace='child', actor='child')
    grants = child_tools(fixed_input=fixed, sdk=Native(), owner='alice', child='child', run='run',
                         memory=memory, parent_memory=memory, check=lambda: None)
    reader = next(g.tool for g in grants if g.tool.name == 'get_research_method')
    assert 'scenario_sensitivity' in str(reader.invoke({'method_id': ''}))
    assert 'scenario_sensitivity' in str(reader.invoke({'method_id': 'scenario_sensitivity'}))
    fixed['method_digests']['scenario_sensitivity'] = 'changed'
    rejected = reader.invoke({'type': 'tool_call', 'id': 'changed-method',
                              'name': 'get_research_method', 'args': {'method_id': 'scenario_sensitivity'}})
    assert rejected.status == 'error' and 'version_changed' in rejected.content


class Authority:
    def __init__(self):
        self.saved = {}; self.revoked = False
    async def claim(self, command, fixed):
        key = command['command_id']
        if key in self.saved:
            return {**self.saved[key], 'dispatch_allowed': False}
        binding = ({'input_digest': fixed['input_digest'], 'fixed_input': deepcopy(fixed)} if fixed else
                   next(g['binding'] for g in self.saved.values() if g['child_thread_id'] == command['child_thread_id']))
        grant = {'command_id': key, 'execution_id': command['execution_id'],
            'command': deepcopy(command),
            'child_thread_id': command['child_thread_id'], 'owner_id': 'alice', 'action': command['action'],
            'operation_id': str(uuid4()), 'dispatch_allowed': True,
            'binding': binding}
        self.saved[key] = grant
        return grant
    async def check(self, grant, *, read_only=False):
        if self.revoked: raise ValueError('revoked')
        if not read_only and grant['action'] != 'cancel' and any(
                g['action'] == 'cancel' and g['child_thread_id'] == grant['child_thread_id'] for g in self.saved.values()):
            raise ValueError('cancelled')
    async def read(self, child):
        result = next(g for g in self.saved.values() if g['child_thread_id'] == child)
        await self.check(result, read_only=True); return result
    async def catalog(self):
        if self.revoked: raise ValueError('revoked')
        return [{'child_thread_id': g['child_thread_id']} for g in self.saved.values() if g['action'] == 'create']
    async def accept(self, grant, receipt):
        self.saved[grant['command_id']]['receipt'] = deepcopy(receipt)
        return receipt


class Native:
    def __init__(self):
        self.threads_by_id = {}; self.runs_by_id = {}; self.dispatches = 0; self.lose_response = False
        self.state = {'values': {'messages': []}, 'checkpoint': {'checkpoint_id': str(uuid4())}}
        self.threads = SimpleNamespace(create=self.create_thread, get=self.get_thread, get_state=self.get_state)
        self.runs = SimpleNamespace(create=self.create_run, list=self.list_runs, cancel=self.cancel)
    async def create_thread(self, *, thread_id, metadata, **kwargs):
        self.threads_by_id.setdefault(thread_id, {'thread_id': thread_id, 'metadata': metadata})
    async def get_thread(self, tid): return self.threads_by_id[tid]
    async def get_state(self, tid, **kwargs): return deepcopy(self.state)
    async def cancel(self, tid, rid, **kwargs): self.runs_by_id[rid]['status'] = 'interrupted'
    async def list_runs(self, tid, *, offset=0, limit=100):
        return [r for r in self.runs_by_id.values() if r['thread_id'] == tid][offset:offset+limit]
    async def create_run(self, tid, assistant_id, **kwargs):
        assert assistant_id == 'delegated_task'
        self.dispatches += 1
        run = {'thread_id': tid, 'run_id': str(uuid4()), 'metadata': kwargs['metadata'],
               'status': 'pending', 'created_at': str(self.dispatches)}
        self.runs_by_id[run['run_id']] = run
        if self.lose_response: raise TimeoutError('response lost after enqueue')
        return run


def test_unknown_dispatch_reconciles_after_restart_without_new_run():
    command, _, fixed = fixture(); sdk, authority = Native(), Authority()
    async def run():
        sdk.lose_response = True
        with pytest.raises(TimeoutError):
            await DelegatedTaskRuntime(sdk=sdk, authority=authority).execute(command, fixed_input=fixed)
        sdk.lose_response = False
        result = await DelegatedTaskRuntime(sdk=sdk, authority=authority).execute(command, fixed_input=fixed)
        assert result['run_id'] in sdk.runs_by_id and sdk.dispatches == 1
        authority.revoked = True
        with pytest.raises(ValueError, match='revoked'):
            await DelegatedTaskRuntime(sdk=sdk, authority=authority).observe(str(command.child_thread_id))
    asyncio.run(run())


def test_saved_note_is_not_completion_and_submission_reuses_exact_version(tmp_path):
    command, _, fixed = fixture(); child, run = str(command.child_thread_id), str(uuid4())
    memory = WorkingMemory(tmp_path/'memory.sqlite', owner='alice', workspace=child, actor='child')
    saved = memory.save('Comparison', 'The evidence supports a scoped comparison.', 0)
    grant = completion_tool(fixed_input=fixed, child_thread_id=child, run_id=run, memory=memory, access_check=lambda: None)
    model = ScriptedTools(responses=[AIMessage(content='', tool_calls=[{'type': 'tool_call', 'id': 'finish',
        'name': 'complete_delegated_task', 'args': {'note_id': saved['note_id'], 'version': saved['version']}}])])
    agent = build_conversation_agent(model=model, grants=[grant], permission_mode='request_standard',
                                     checkpointer=InMemorySaver(), model_calls=1)
    result = asyncio.run(agent.ainvoke({'messages': [HumanMessage(content='Return the saved work')]},
                                      {'configurable': {'thread_id': child}}))
    messages = [m for m in result['messages'] if isinstance(m, ToolMessage)]
    assert len(messages) == 1
    receipt = messages[0].artifact
    assert receipt['artifact']['id'] == saved['note_id'] and receipt['artifact']['version'] == 1
    assert receipt['outcome']['execution_status'] == 'submitted'
    assert receipt['outcome']['review_status'] == 'not_assessed_in_this_record'
    assert 'The evidence supports' not in json.dumps(receipt)  # No full-body retransmission.


def test_new_run_does_not_inherit_prior_completion():
    command, _, fixed = fixture(); sdk, authority = Native(), Authority()
    async def run():
        controller = DelegatedTaskRuntime(sdk=sdk, authority=authority)
        first = await controller.execute(command, fixed_input=fixed)
        sdk.runs_by_id[first['run_id']]['status'] = 'success'
        sdk.state['values']['messages'] = [{'type': 'tool', 'name': 'complete_delegated_task',
            'artifact': {'run_id': first['run_id'], 'artifact': {'id': 'saved-v1'}}}]
        assert (await controller.observe(str(command.child_thread_id)))['outcome']
        sdk.runs_by_id['next'] = {'run_id': 'next', 'thread_id': str(command.child_thread_id),
                                  'status': 'pending', 'created_at': '2'}
        current = await controller.observe(str(command.child_thread_id))
        assert current['outcome'] is None and current['prior_artifact'] == {'id': 'saved-v1'}
    asyncio.run(run())


def test_continue_preserves_thread_and_cancel_keeps_readback_after_checkpoint_moves():
    command, _, fixed = fixture(); sdk, authority = Native(), Authority()
    async def run():
        controller = DelegatedTaskRuntime(sdk=sdk, authority=authority)
        first = await controller.execute(command, fixed_input=fixed)
        sdk.runs_by_id[first['run_id']]['status'] = 'success'
        body = command.model_dump(mode='json')
        body.update(command_id=str(uuid4()), action='continue', task=None,
                    checkpoint_id=sdk.state['checkpoint']['checkpoint_id'], message='Check the changed period in the same paper.')
        second = await controller.execute(body)
        assert second['run_id'] != first['run_id'] and len(sdk.threads_by_id) == 1
        cancel = {**body, 'command_id': str(uuid4()), 'action': 'cancel', 'message': ''}
        sdk.state['checkpoint']['checkpoint_id'] = str(uuid4())  # Moving run cannot defeat cancellation.
        await controller.execute(cancel)
        assert sdk.runs_by_id[second['run_id']]['status'] == 'interrupted'
        assert (await controller.observe(str(command.child_thread_id)))['checkpoint_id'] == sdk.state['checkpoint']['checkpoint_id']
        with pytest.raises(ValueError, match='cancelled'):
            await controller.execute({**body, 'command_id': str(uuid4()), 'checkpoint_id': sdk.state['checkpoint']['checkpoint_id']})
        assert sdk.dispatches == 2
    asyncio.run(run())


def test_reconciliation_rejects_modified_dispatch_digest():
    command, _, fixed = fixture(); sdk, authority = Native(), Authority()
    async def run():
        first = await DelegatedTaskRuntime(sdk=sdk, authority=authority).execute(command, fixed_input=fixed)
        sdk.runs_by_id[first['run_id']]['metadata']['dispatch_digest'] = 'not-the-request'
        with pytest.raises(ValueError, match='reconciliation_identity'):
            await DelegatedTaskRuntime(sdk=sdk, authority=authority).execute(command, fixed_input=fixed)
        assert sdk.dispatches == 1
    asyncio.run(run())


def test_child_reads_only_selected_originals_and_frozen_parent_note(tmp_path):
    from sec_agent.agent_runtime.delegated_task_graph import child_tools, current_work_catalog
    command, parent, fixed = fixture(); sdk = Native(); sdk.state = parent
    receipt = {'authority_state':'s2_numeric_fact_query_result', 'results':[{'status':'resolved', 'facts':[
        {'numeric_fact_id':'chosen', 'numeric_fact_authority':True, 'value_decimal':'125', 'unit':'USD', 'period_end':'2025-12-31'},
        {'numeric_fact_id':'excluded', 'numeric_fact_authority':True, 'value_decimal':'99', 'unit':'USD', 'period_end':'2024-12-31'}]}]}
    parent['values']['messages'].append({'type':'tool', 'name':'query_financial_data',
                                       'tool_call_id':'original-read', 'status':'success', 'artifact':receipt})
    parent_memory = WorkingMemory(tmp_path/'notes.db', owner='alice', workspace=str(command.execution_id), actor='parent')
    original = parent_memory.save('Working explanation', 'Version one, not a verified fact.', 0)
    task = command.task.model_dump(mode='json')
    task['materials'] = [{'source_id':'chosen', 'tool_call_id':'original-read'}]
    task['working_notes'] = [{'id':original['note_id'], 'version':1}]
    body = command.model_dump(mode='json'); body['task'] = task
    fixed = freeze_input(body, parent, allowed_methods=[], note_reader=lambda n,v: parent_memory.read(n,version=v),
                         runtime_configuration=fixed['runtime_configuration'])
    parent_memory.save('Working explanation', 'Changed later parent explanation.', 1)
    child = str(command.child_thread_id)
    memory = WorkingMemory(tmp_path/'notes.db', owner='alice', workspace=child, actor='delegated_task')
    sdk.threads_by_id[str(command.execution_id)] = {'metadata': {'owner_id':'alice'}}
    access = {'revoked':False}
    def check():
        if access['revoked']: raise ValueError('revoked')
    grants = child_tools(fixed_input=fixed, sdk=sdk, owner='alice', child=child, run=str(uuid4()),
        memory=memory, parent_memory=parent_memory, check=check)
    tools = {g.tool.name:g.tool for g in grants}
    assert 'delegate_research_task' not in tools and 'read_handoff_context' not in tools
    async def run():
        catalog = await tools['list_handoff_evidence'].ainvoke({})
        assert [r['source_id'] for r in catalog['items']] == ['chosen']
        assert '不存在' in await tools['read_handoff_evidence'].ainvoke({'source_id':'excluded'})
        note = await tools['read_handoff_working_note'].ainvoke({'note_id':original['note_id']})
        assert note['version'] == 1 and 'Version one' in note['body']
        access['revoked'] = True
        with pytest.raises(ValueError, match='revoked'):
            await tools['read_handoff_evidence'].ainvoke({'source_id':'chosen'})
    asyncio.run(run())
    saved = memory.save('Child analysis', 'First view.', 0)
    memory.save('Child analysis', 'Revised view.', 1)
    catalog = json.loads(current_work_catalog(memory))
    assert catalog['current_workpapers'][0]['version'] == 2 and 'First view' not in str(catalog)


def test_parent_can_calculate_from_exact_child_receipt_after_runtime_restart():
    from sec_agent.agent_runtime.delegated_task_tools import delegation_tools
    from sec_agent.agent_runtime.conversation_tools import conversation_tools
    command, _, fixed = fixture(); sdk, authority = Native(), Authority()
    async def check(): pass
    async def run():
        await DelegatedTaskRuntime(sdk=sdk, authority=authority).execute(command, fixed_input=fixed)
        sdk.state['values']['messages'] = [{'type':'tool', 'tool_call_id':'sql', 'name':'query_financial_data',
            'artifact': {'authority_state':'s2_numeric_fact_query_result', 'results':[{'status':'resolved', 'facts':[
                {'numeric_fact_id':'a', 'numeric_fact_authority':True, 'value_decimal':'100', 'unit':'USD', 'period_end':'2024-12-31'},
                {'numeric_fact_id':'b', 'numeric_fact_authority':True, 'value_decimal':'125', 'unit':'USD', 'period_end':'2025-12-31'}]}]}}]
        # Reconstructed adapter; no in-memory transcript needed.
        grants = delegation_tools(controller=DelegatedTaskRuntime(sdk=sdk,authority=authority),
            parent_thread_id=str(command.execution_id), parent_run_id=str(command.parent_run_id),
            root_budget_id=command.root_budget_id, manifest_digest=command.manifest_digest,
            allowed_methods=[], note_reader=lambda *args: None, child_note_reader=lambda *args: None,
            access_check=check, runtime_configuration=fixed['runtime_configuration'])
        args={'child_thread_id':str(command.child_thread_id), 'checkpoint_id':sdk.state['checkpoint']['checkpoint_id'], 'tool_call_id':'sql'}
        model=ScriptedTools(responses=[AIMessage(content='',tool_calls=[
            {'name':'read_delegated_evidence','id':'r1','type':'tool_call','args':{**args,'source_id':'a'}},
            {'name':'read_delegated_evidence','id':'r2','type':'tool_call','args':{**args,'source_id':'b'}}]),
            AIMessage(content='',tool_calls=[{'name':'calculate_research_metric','id':'calc','type':'tool_call','args':{
                'request':{'expression':'(new / old - 1) * 100','operands':{'new':{'source_id':'b'},'old':{'source_id':'a'}},
                           'result_unit':'percent','rationale':'Synthetic same-unit annual comparison'}}}]), AIMessage(content='25%')])
        agent=build_conversation_agent(model=model,grants=grants+conversation_tools(thread_id=str(command.execution_id)),
            permission_mode='approve_for_me',checkpointer=InMemorySaver())
        result=await agent.ainvoke({'messages':[HumanMessage(content='Read child originals and calculate')]},
                                  {'configurable':{'thread_id':str(command.execution_id)}})
        receipt=next(m.artifact for m in result['messages'] if isinstance(m,ToolMessage) and m.name=='calculate_research_metric')
        assert receipt['value_decimal']=='25.00'
        assert receipt['operands']['old']['period_end']=='2024-12-31'
        assert sdk.dispatches==1
    asyncio.run(run())


def test_outdated_note_submission_fails_without_erasing_saved_work(tmp_path):
    command, _, fixed = fixture()
    memory=WorkingMemory(tmp_path/'notes.db',owner='alice',workspace=str(command.child_thread_id),actor='child')
    saved=memory.save('Analysis','First version',0)
    memory.save('Analysis','Human correction',1,user_edit=True)
    tool=completion_tool(fixed_input=fixed,child_thread_id=str(command.child_thread_id),run_id=str(uuid4()),
        memory=memory,access_check=lambda:None).tool
    failed=tool.invoke({'note_id':saved['note_id'],'version':1})
    assert '不是当前保存版本' in failed
    assert memory.read(saved['note_id'])['body']=='Human correction'


def test_native_parent_dispatches_once_and_sees_only_receipt():
    from sec_agent.agent_runtime.delegated_task_tools import delegation_tools
    command, parent, fixed=fixture(); sdk, authority=Native(), Authority();sdk.state=parent
    async def check(): pass
    grants=delegation_tools(controller=DelegatedTaskRuntime(sdk=sdk,authority=authority),
        parent_thread_id=str(command.execution_id),parent_run_id=str(command.parent_run_id),
        root_budget_id=command.root_budget_id,manifest_digest=command.manifest_digest,allowed_methods=[],
        note_reader=lambda *a:None,child_note_reader=lambda *a:None,access_check=check,
        runtime_configuration=fixed['runtime_configuration'])
    model=ScriptedTools(responses=[AIMessage(content='',tool_calls=[{'name':'delegate_research_task','id':'create-child',
        'type':'tool_call','args':{'request':command.task.model_dump(mode='json')}}]),AIMessage(content='Delegated; continue integration.')])
    agent=build_conversation_agent(model=model,grants=grants,permission_mode='request_standard',checkpointer=InMemorySaver())
    result=asyncio.run(agent.ainvoke({'messages':[HumanMessage(content='Investigate the comparison with independent help if useful.')]},
        {'configurable':{'thread_id':str(command.execution_id)}}))
    receipt=next(m.content for m in result['messages'] if isinstance(m,ToolMessage))
    assert sdk.dispatches==1 and 'run_id' in receipt
    assert all(s not in receipt for s in ('runtime_configuration','root_budget_id','OLD CONCLUSION'))
    saved=next(iter(authority.saved.values()))
    assert saved['binding']['fixed_input']['runtime_configuration']==fixed['runtime_configuration']


def test_disabled_parent_capability_opens_no_host_resources():
    from sec_agent.agent_runtime.delegated_task_host import admitted_delegation_tools
    def forbidden(): raise AssertionError('Admission must not be called while disabled')
    assert asyncio.run(admitted_delegation_tools(sdk=None,resources=None,run_authority=forbidden,
        root_thread_id='not-even-a-uuid',root_run_id='',specification={},settings={},environment={}))==[]


def test_host_assembly_requires_admitted_parent_and_existing_shared_budget(tmp_path, monkeypatch):
    from sec_agent.agent_runtime.delegated_task_host import admitted_delegation_tools
    command, _, fixed=fixture(); sdk=Native(); root,run=str(command.execution_id),str(command.parent_run_id)
    group=str(uuid4());owner='organization:'+group
    sdk.threads_by_id[root]={'metadata':{'owner_id':owner}}
    resources=SimpleNamespace(execution_id=root,manifest_digest=command.manifest_digest)
    grant={'execution_id':root,'authorized_run_id':run,'organization_id':group}
    budget={'value':None}
    monkeypatch.setattr('sec_agent.agent_runtime.research_budget.budget_from_host',lambda *a,**k:budget['value'])
    args=dict(sdk=sdk,resources=resources,run_authority=lambda:deepcopy(grant),root_thread_id=root,root_run_id=run,
        specification=fixed['runtime_configuration'],settings={},environment={
            'FINSIGHT_ORGANIZATION_TASK_ACTIONS_ENABLED':'1','FINSIGHT_WORKING_MEMORY_PATH':str(tmp_path/'notes.db')})
    async def check():
        with pytest.raises(ValueError,match='shared_root_budget'):
            await admitted_delegation_tools(**args)
        budget['value']=SimpleNamespace(budget='one-existing-root-budget')
        tools=await admitted_delegation_tools(**args)
        assert 'delegate_research_task' in {g.tool.name for g in tools}
        assert sdk.dispatches==0
        grant['authorized_run_id']=str(uuid4())
        with pytest.raises(ValueError,match='not_independently_admitted'):
            await admitted_delegation_tools(**args)
    asyncio.run(check())


def test_child_submission_is_only_one_version_not_full_history(tmp_path):
    command, _, fixed=fixture()
    memory=WorkingMemory(tmp_path/'notes.db',owner='alice',workspace=str(command.child_thread_id),actor='child')
    first=memory.save('Analysis','Old hypothesis',0)
    second=memory.save('Analysis','Updated explanation from new information',1)
    grant=completion_tool(fixed_input=fixed,child_thread_id=str(command.child_thread_id),run_id=str(uuid4()),
        memory=memory,access_check=lambda:None)
    receipt=grant.tool.invoke({'type':'tool_call','id':'submit','name':grant.tool.name,
        'args':{'note_id':first['note_id'],'version':second['version']}})
    assert receipt.artifact['artifact']['version']==2
    assert 'Old hypothesis' not in receipt.content and 'Updated explanation' not in receipt.content
    assert memory.read(first['note_id'],version=1)['body']=='Old hypothesis'


def test_native_child_saves_reads_resumes_updates_and_submits_without_rewriting_history(tmp_path, monkeypatch):
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
    from sec_agent.agent_runtime.delegated_task_graph import child_tools
    from sec_agent.agent_runtime.working_memory_tools import native_memory_scope
    command, _, fixed=fixture(); sdk=Native(); child=str(command.child_thread_id)
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH',str(tmp_path/'notes.db'))
    memory=WorkingMemory(tmp_path/'notes.db',owner='alice',workspace=child,actor='delegated_task')
    class Steps(ScriptedTools):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            receipts=[json.loads(m.content) for m in messages if isinstance(m,ToolMessage)]
            index=len(receipts)
            if index==0:
                name,args='WriteWorkingNote',{'title':'Comparison','body':'Initial explanation from original material.'}
            elif index==1:
                name,args='ReadWorkingNote',{'note_id':receipts[0]['note_id'],'version':1}
            elif index==2:
                name,args='WriteWorkingNote',{'title':'Comparison','body':'Updated explanation after comparing the periods.','base_version':1}
            else:
                name,args='complete_delegated_task',{'note_id':receipts[-1]['note_id'],'version':2}
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content='',tool_calls=[
                {'name':name,'args':args,'id':'step-'+str(index),'type':'tool_call'}]))])
    grants=child_tools(fixed_input=fixed,sdk=sdk,owner='alice',child=child,run=str(uuid4()),memory=memory,
        parent_memory=memory,check=lambda:None)
    model=Steps(responses=[])
    graph=build_conversation_agent(model=model,grants=grants,permission_mode='request_standard',
        checkpointer=InMemorySaver(),model_calls=2,tool_calls=8)
    config={'configurable':{'thread_id':child}}
    async def run():
        with native_memory_scope('alice',child,access_check=lambda:None,allow_remote_search=False):
            with pytest.raises(ModelCallLimitExceededError):
                await graph.ainvoke({'messages':[HumanMessage(content='Continue this comparison.')]},config)
            state=await graph.aget_state(config)
            assert not any(isinstance(m,ToolMessage) and m.name=='complete_delegated_task' for m in state.values['messages'])
            assert memory.manifest()[0]['version']==1
            result=await graph.ainvoke(None,config)
            submitted=next(m.artifact for m in result['messages'] if isinstance(m,ToolMessage) and m.name=='complete_delegated_task')
            assert submitted['artifact']['version']==2
            assert len([m for m in result['messages'] if isinstance(m,ToolMessage) and m.name=='WriteWorkingNote'])==2
            assert memory.read(submitted['artifact']['id'],version=1)['body'].startswith('Initial')
    asyncio.run(run())
