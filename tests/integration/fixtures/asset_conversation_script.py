"""Zero-provider browser fixture: actual conversation agent/tools, scripted model."""
import os
from uuid import uuid4
from langchain_core.messages import AIMessage
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langgraph.checkpoint.memory import InMemorySaver
from sec_agent.agent_runtime.conversation_agent import build_conversation_agent
from sec_agent.agent_runtime.conversation_tools import conversation_tools
from sec_agent.research_foundation.task_asset_updates import TaskAssetUpdates, TaskAssetView


class ScriptedModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs): return self


class ScriptedRuns:
    def __init__(self, threads):
        self.threads, self.rows, self.states = threads, {}, {}
        self.checkpointer = InMemorySaver()
        threads.get_state = self.get_state

    async def get_state(self, tid, **kwargs):
        return self.states.get(tid, {'values': {}, 'tasks': []})

    async def list(self, tid, **kwargs): return self.rows.get(tid, [])

    async def create(self, tid, graph, *, input, config, metadata, **kwargs):
        if graph != 'conversation_session':
            raise RuntimeError('Research dispatch prohibited by the non-research fixture')
        root = os.path.join(os.environ['FINSIGHT_LOCAL_STATE_ROOT'], 'attachments')
        rid = str(uuid4()); updates = TaskAssetUpdates(root)
        updates.pin(tid, rid, config['configurable']['finsight_asset_revision'])
        view = TaskAssetView(root, tid, rid)
        selected = view.list(tid)[0]
        # The deterministic answer labels itself and exercises exact tool wiring.
        model = ScriptedModel(responses=[AIMessage(content='', tool_calls=[{'id': str(uuid4()),
            'name': 'read_task_material', 'args': {'request': {'source_space': 'uploads', 'operation': 'read',
                'document_id': selected['document_id']}}}]),
            AIMessage(content=f"工程脚本回答：已读取 {selected['name']}。这不是模型的金融判断。")])
        agent = build_conversation_agent(model=model, grants=conversation_tools(thread_id=tid, attachment_store=view),
            permission_mode='request_standard', checkpointer=self.checkpointer)
        result = await agent.ainvoke(input, config={'configurable': {'thread_id': tid}})
        self.states[tid] = {'values': {'messages': [m.model_dump(mode='json') for m in result['messages']]},
            'tasks': [], 'checkpoint': {'checkpoint_id': str(uuid4())}}
        row = {'run_id': rid, 'status': 'success', 'metadata': metadata}
        self.rows.setdefault(tid, []).insert(0, row)
        return row
