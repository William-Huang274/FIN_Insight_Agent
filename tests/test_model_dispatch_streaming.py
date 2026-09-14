"""Real SDK SSE decoding through the FIN model boundary; no provider network."""
import asyncio
import json
import httpx
import pytest
from langchain.agents.middleware.types import ModelResponse

from test_model_dispatch_guard import boundary


class Stream(httpx.AsyncByteStream):
    def __init__(self, mode): self.mode=mode
    async def __aiter__(self):
        def event(delta, finish=None, usage=None):
            return ('data: '+json.dumps({'id':'synthetic-stream','object':'chat.completion.chunk','created':1,
                'model':'deepseek-v4-pro','choices':[{'index':0,'delta':delta,'finish_reason':finish}],
                'usage':usage})+'\n\n').encode()
        yield event({'role':'assistant','content':'Synthetic answer.'})
        if self.mode=='disconnect':
            raise httpx.ReadError('synthetic_disconnect')
        if self.mode=='early_eof': return
        usage=None
        if self.mode!='no_usage':
            usage={'prompt_tokens':100,'completion_tokens':50,'total_tokens':150,
                   'prompt_cache_hit_tokens':40,'prompt_cache_miss_tokens':60}
            if self.mode=='partial_usage': usage.pop('completion_tokens')
        yield event({},'length' if self.mode=='length' else 'aborted' if self.mode=='aborted' else 'stop',usage=usage)
        yield b'data: [DONE]\n\n'


@pytest.mark.parametrize('mode',['complete','length','no_usage','partial_usage','disconnect','early_eof','aborted'])
def test_sdk_stream_usage_and_incomplete_response(boundary,mode):
    b,calls=boundary,[]
    async def exercise():
        def serve(request):
            payload=json.loads(request.content); calls.append(payload)
            assert payload['stream'] is True and payload['stream_options']['include_usage'] is True
            return httpx.Response(200,headers={'content-type':'text/event-stream'},stream=Stream(mode))
        async with httpx.AsyncClient(transport=httpx.MockTransport(serve)) as client:
            from sec_agent.agent_runtime.deepseek_structured_agents import ReasoningPreservingChatDeepSeek
            from pydantic import SecretStr
            model=ReasoningPreservingChatDeepSeek(model=b.profile.model,api_key=SecretStr('fixture-not-a-secret'),
                http_async_client=client,max_retries=0,streaming=True,stream_usage=True,use_responses_api=False)
            request=b.request.override(model=model)
            async def handler(request):
                return ModelResponse(result=[await request.model.ainvoke(request.messages)])
            return await b.audit.awrap_model_call(request,handler)
    if mode in ('length','disconnect','early_eof','aborted'):
        with pytest.raises(Exception): asyncio.run(exercise())
    else:
        assert asyncio.run(exercise()).result[-1].content=='Synthetic answer.'
    assert len(calls)==1
    if mode in ('disconnect','early_eof'):
        b.store.received.assert_not_called()
        b.store.unknown.assert_called_once()
    else:
        assert b.store.received.call_args.args[-1] == (None if mode in ('no_usage','partial_usage') else 160)
