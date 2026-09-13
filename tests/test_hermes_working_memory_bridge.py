"""Native API transport and scope qualification without provider requests."""
import asyncio
import json

import httpx
import pytest

from sec_agent.agent_runtime.hermes_bridge import build_hermes_graph, bind_session


@pytest.mark.parametrize('success',[True,False])
def test_native_runs_protocol(monkeypatch,tmp_path,success):
    monkeypatch.setenv('FINSIGHT_WORKING_MEMORY_PATH',str(tmp_path/'notes.sqlite'))
    monkeypatch.setenv('FINSIGHT_HERMES_URL','http://hermes.local')
    monkeypatch.setenv('FINSIGHT_HERMES_TOKEN','test-token')
    requests=[]
    def respond(request):
        requests.append(request)
        assert request.headers['authorization']=='Bearer test-token'
        if request.method=='POST' and request.url.path=='/v1/runs':
            body=json.loads(request.content)
            assert body['input']=='用户纠正'
            assert body['session_id']==bind_session('alice','thread','writer')
            assert request.headers['idempotency-key']=='native-run'
            return httpx.Response(200,json={'run_id':'remote-run'})
        if request.url.path.endswith('/events'):
            return httpx.Response(200,text='data: '+json.dumps({'event':'message.delta','delta':'已读底稿'})+'\n\ndata: '+json.dumps({'event':'tool.completed','tool':'ReadWorkingNote'})+'\n\n')
        if request.url.path.endswith('/stop'): return httpx.Response(200,json={})
        return httpx.Response(200,json={'status':'completed' if success else 'failed','output':'修订结果' if success else '', 'usage':{}})
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(respond),**kw))
    events=[]
    graph=build_hermes_graph(owner='alice',workspace='thread',actor='writer',model='deepseek-v4-flash',public_sink=events.append)
    async def run():
        return await graph.ainvoke({'messages':[('human','用户纠正')]},{'configurable':{'run_id':'native-run'}})
    if success:
        result=asyncio.run(run())
        assert result['messages'][-1].content=='修订结果'
    else:
        with pytest.raises(RuntimeError,match='hermes_run_incomplete'): asyncio.run(run())
        assert requests[-1].url.path.endswith('/stop')
    assert not any(e.get('objective')=='已读底稿' for e in events)  # chunks are live, not duplicated in durable audit
    assert any(e.get('tool')=='ReadWorkingNote' for e in events)
    assert bind_session('alice','thread','writer')!=bind_session('bob','thread','writer')
