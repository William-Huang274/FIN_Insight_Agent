"""Expected review failures stop new dispatch, without cancelling paid siblings."""
from threading import Event

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ExtendedModelResponse, ModelResponse, hook_config
from langgraph.types import Command
from langchain_core.messages import AIMessage, ToolMessage


def latest_tool_batch_errors(state):
    """Inspect every result of the latest action batch, never archived errors."""
    messages = state.get('messages', [])
    boundary = next((i for i in range(len(messages)-1, -1, -1)
                     if isinstance(messages[i], AIMessage)), None)
    if boundary is None:
        return []
    return [m for m in messages[boundary+1:]
            if isinstance(m, ToolMessage) and m.status == 'error']


class ReviewExecutionStopped(ValueError):
    def __init__(self, reason, state, *, call_id=None, raw=None, provider_call_attempted=False):
        super().__init__(reason)
        self.error = {'reason': reason, 'call_id': call_id,
            'provider_call_attempted': provider_call_attempted,
            'automatic_resume_allowed': False, 'partial_response_accepted': False}


class ReviewExecutionControl:
    """One native review wave; not a queue, retry policy or budget owner."""
    def __init__(self, *, stop_on_tool_error=False):
        self.stopped = Event()
        self.stop_on_tool_error = stop_on_tool_error

    def stop(self, reason, state, **details):
        self.stopped.set()
        raise ReviewExecutionStopped(reason, state, **details)

    def before_dispatch(self, state):
        if self.stopped.is_set():
            raise ReviewExecutionStopped('review_wave_stopped_no_new_dispatch', state)
        if self.stop_on_tool_error and latest_tool_batch_errors(state):
            self.stop('review_tool_batch_error_before_dispatch', state)
class ReviewExecutionState(AgentState):
    execution_error: dict | None


class ReviewExecutionBoundary(AgentMiddleware):
    """Convert only expected failures to a native terminal state, without retry."""
    state_schema = ReviewExecutionState

    async def awrap_model_call(self, request, handler):
        try:
            return await handler(request)
        except ReviewExecutionStopped as exc:
            # The raw response is already in the private audit/dispatch receipt.
            # Do not insert truncated tool calls or invent an assistant answer.
            update = {"execution_error": exc.error, "review": None}
            if exc.error['provider_call_attempted']:
                # Terminal routing skips the native counter's after_model hook.
                # Count the actual failed attempt, never a blocked next request.
                for key in ('thread_model_call_count', 'run_model_call_count'):
                    update[key] = request.state.get(key, 0) + 1
            return ExtendedModelResponse(model_response=ModelResponse(result=[]),
                command=Command(update=update))

    @hook_config(can_jump_to=["end"])
    def after_model(self, state, runtime):
        if state.get("execution_error"):
            return {"jump_to": "end"}
        return None
