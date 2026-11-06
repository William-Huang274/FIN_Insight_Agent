"""One admitted run of a maintained ACP process, not another agent loop.

The parent owns command admission, money and tool permissions. ACP owns native
history, compression and model/tool scheduling. Persisting the session binding
before prompting permits an interrupted run to resume without forging history.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import os
import re
from hashlib import sha256
from pathlib import Path
from typing import Callable
from uuid import UUID

from acp import PROTOCOL_VERSION, spawn_agent_process, text_block
from acp.schema import ClientCapabilities, Implementation, RequestPermissionResponse


def native_tool_recovery(events, tool_names):
    """Explain an exact case mismatch against today's grants; never execute it."""
    names = ['mcp__financial__' + name for name in tool_names]
    failures = []
    if not events.is_file():
        return failures
    for line in events.read_text(encoding='utf8').splitlines():
        value = json.loads(line).get('update', {})
        if value.get('sessionUpdate') != 'tool_call_update' or value.get('status') != 'failed':
            continue
        for item in value.get('content') or []:
            match = re.fullmatch(r'Error: unknown tool "([^"]+)"', item.get('content', {}).get('text', ''))
            if not match:
                continue
            submitted = match[1]
            candidates = [name for name in names if name.casefold() == submitted.casefold()]
            failures.append({'tool_call_id': value['toolCallId'], 'submitted_tool': submitted,
                'status': 'not_executed', 'available_exact_names': candidates,
                'feedback': 'Tool names are case-sensitive. Use the available tool definition; '
                            'this failed call has not saved or changed any artifact.'})
    return failures


def _persist(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class TurnTextProjection:
    """Separate pre-tool assistant text from terminal delivery, without rewriting it.

    ACP text chunks are not necessarily a final answer. Tool completion updates
    may arrive late; only a new tool call starts a new delivery segment.
    """
    version = 'acp_terminal_text.v1'

    def __init__(self):
        self.text, self.progress = [], []
        self.tool_ids = set()

    def accept(self, value):
        kind = value.get('sessionUpdate')
        if kind == 'tool_call' and value['toolCallId'] not in self.tool_ids:
            self.tool_ids.add(value['toolCallId'])
            self.progress.extend(self.text)
            self.text.clear()
        elif kind == 'agent_message_chunk' and value.get('content', {}).get('type') == 'text':
            self.text.append(value['content']['text'])

    def fields(self):
        return {'text': ''.join(self.text), 'progress_text': ''.join(self.progress),
                'text_projection': self.version}


def completed_text_projection(prior, events):
    """Adapt an old completed receipt using its exact events; never overwrite it."""
    if prior.get('text_projection') == TurnTextProjection.version:
        return prior
    if not events.is_file():
        raise ValueError('harness_completed_text_events_missing')
    projection = TurnTextProjection()
    with events.open(encoding='utf8') as stream:
        for line in stream:
            record = json.loads(line)
            if record['session_id'] != prior['session_id']:
                raise ValueError('harness_completed_text_session_mismatch')
            projection.accept(record['update'])
    fields = projection.fields()
    if fields['progress_text'] + fields['text'] != prior['text']:
        raise ValueError('harness_completed_text_events_mismatch')
    return {**prior, **fields}


def completed_recovery(directory, *, previous_run_id, binding):
    """Read a completed predecessor only after Java admitted its recovery.

    An incomplete/unknown provider response is deliberately not promoted. The
    caller supplies the signed predecessor, never a model-selected file path.
    """
    directory = Path(directory)
    session_path = directory / 'session-binding.json'
    turn_path = directory / str(UUID(previous_run_id)) / 'turn.private.json'
    if not turn_path.exists():
        return None  # e.g. a genuine legacy FIN checkpoint handoff
    prior = json.loads(turn_path.read_text(encoding='utf8'))
    if prior.get('status') != 'completed':
        return None
    session = json.loads(session_path.read_text(encoding='utf8'))
    if session['binding'] != binding or prior['session_id'] != session['session_id']:
        raise ValueError('harness_recovery_response_binding_mismatch')
    return completed_text_projection(prior, turn_path.with_name('events.private.jsonl'))


class HarnessSessionClient:
    """Private event storage and public text are separate; no implicit grants."""
    def __init__(self, events: Path, public: Callable | None = None, stop_on_failure=None):
        self.events, self.public = events, public
        self.projection = TurnTextProjection()
        self.active_turn = False
        self.stop_on_failure = stop_on_failure

    async def session_update(self, session_id, update, **kwargs):
        value = update.model_dump(mode='json', by_alias=True, exclude_none=True)
        with self.events.open('a', encoding='utf8') as stream:
            stream.write(json.dumps({'session_id': session_id, 'update': value}, ensure_ascii=False) + '\n')
            stream.flush()
        self.projection.accept(value)
        # Native tool lookup can fail before it reaches FIN's MCP bridge. Stop
        # financial admission for a live failure too, but not replayed history
        # emitted while loading a saved ACP session.
        if (self.active_turn and self.stop_on_failure
                and value.get('sessionUpdate') == 'tool_call_update' and value.get('status') == 'failed'):
            self.stop_on_failure()
        if value.get('sessionUpdate') == 'agent_message_chunk':
            content = value.get('content', {})
            if content.get('type') == 'text':
                if self.public:
                    self.public({'type': 'assistant_text', 'text': content['text']})

    async def request_permission(self, session_id, tool_call, options, **kwargs):
        # Business tools have already been admitted by the host. Shell/file
        # access and additional permissions are not granted by this adapter.
        return RequestPermissionResponse(outcome={'outcome': 'cancelled'})


class HarnessSession:
    def __init__(self, connection, client, session_id, *, authority, stop, turn_path):
        self.connection, self.client, self.session_id = connection, client, session_id
        self.authority, self.stop, self.turn_path = authority, stop, turn_path

    async def prompt(self, text: str):
        await asyncio.to_thread(self.authority)
        digest = sha256(text.encode('utf8')).hexdigest()
        if self.turn_path.exists():
            prior = json.loads(self.turn_path.read_text(encoding='utf8'))
            if prior.get('prompt_digest') != digest:
                raise ValueError('harness_run_prompt_identity_changed')
            if prior['status'] == 'completed':
                return completed_text_projection(prior, self.client.events)
            # A new Java recovery run is required; never resend an uncertain
            # prompt implicitly inside the same run.
            raise RuntimeError('harness_turn_already_started_requires_recovery_command')
        _persist(self.turn_path, {'status': 'started', 'session_id': self.session_id, 'prompt': text, 'prompt_digest': digest})
        self.client.projection = TurnTextProjection()
        self.client.active_turn = True
        try:
            response = await self.connection.prompt(session_id=self.session_id, prompt=[text_block(text)])
            result = {'status': 'completed', 'session_id': self.session_id,
                      'stop_reason': response.stop_reason, **self.client.projection.fields(), 'prompt_digest': digest}
            if response.stop_reason != 'end_turn':
                result['status'] = 'interrupted'
            _persist(self.turn_path, result)
            return result
        except BaseException:
            # Revocation closes tool/provider admission before protocol cancel.
            self.stop()
            try:
                await asyncio.wait_for(asyncio.shield(self.connection.cancel(session_id=self.session_id)), timeout=5)
            except (Exception, asyncio.CancelledError):
                pass
            # Keep started receipt: interruption does not mean zero cost or
            # that no tool effect occurred. SDK tears down the process.
            raise
        finally:
            self.client.active_turn = False


@asynccontextmanager
async def admitted_acp_session(*, binary, arguments, environment, directory,
                               binding, run_id, authority, stop, mcp_servers,
                               public=None, spawn=spawn_agent_process, workspace=None):
    """Bind an execution workspace to one ACP session across admitted runs.

    `binding` comes from validated Java authority and host release selection,
    never from model arguments. Run ID changes on recovery, task binding does
    not. Old FIN checkpoints must be passed as explicit handoff content.
    """
    await asyncio.to_thread(authority)
    directory = Path(directory).resolve()
    workspace = Path(workspace or directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    saved_path = directory / 'session-binding.json'
    prior = json.loads(saved_path.read_text(encoding='utf8')) if saved_path.exists() else None
    if prior and prior['binding'] != binding:
        raise ValueError('harness_session_binding_mismatch')
    run_directory = directory / str(UUID(run_id))
    run_directory.mkdir(exist_ok=True)
    client = HarnessSessionClient(run_directory / 'events.private.jsonl', public, stop_on_failure=stop)
    with (run_directory / 'process.private.log').open('ab') as stderr:
        async with spawn(client, binary, *arguments, env=environment, cwd=workspace,
                         transport_kwargs={'stderr': stderr, 'limit': 16 * 1024 * 1024}) as (connection, process):
            initialized = await connection.initialize(protocol_version=PROTOCOL_VERSION,
                client_capabilities=ClientCapabilities(), client_info=Implementation(name='finsight', version='1'))
            if prior:
                capabilities = initialized.agent_capabilities
                if capabilities.session_capabilities and capabilities.session_capabilities.resume is not None:
                    await connection.resume_session(session_id=prior['session_id'], cwd=str(workspace), mcp_servers=mcp_servers)
                elif capabilities.load_session:
                    await connection.load_session(session_id=prior['session_id'], cwd=str(workspace), mcp_servers=mcp_servers)
                else:
                    raise ValueError('harness_native_session_restore_unsupported')
                session_id = prior['session_id']
            else:
                response = await connection.new_session(cwd=str(workspace), mcp_servers=mcp_servers)
                session_id = response.session_id
                _persist(saved_path, {'binding': binding, 'session_id': session_id})
            await asyncio.to_thread(authority)
            try:
                yield HarnessSession(connection, client, session_id, authority=authority, stop=stop,
                                     turn_path=run_directory / 'turn.private.json')
            finally:
                stop()
