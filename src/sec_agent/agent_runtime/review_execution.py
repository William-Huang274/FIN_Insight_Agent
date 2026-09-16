"""Expected review failures stop new dispatch, without cancelling paid siblings."""
from threading import Event

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ExtendedModelResponse, ModelResponse, hook_config
from langgraph.types import Command


class ReviewExecutionStopped(ValueError):
    def __init__(self, reason, state, *, call_id=None, raw=None):
        super().__init__(reason)
        self.error = {'reason': reason, 'call_id': call_id,
            'automatic_resume_allowed': False, 'partial_response_accepted': False}


class ReviewExecutionControl:
    """One native review wave; not a queue, retry policy or budget owner."""
    def __init__(self):
        self.stopped = Event()

    def stop(self, reason, state, **details):
        self.stopped.set()
        raise ReviewExecutionStopped(reason, state, **details)

    def before_dispatch(self, state):
        if self.stopped.is_set():
            raise ReviewExecutionStopped('review_wave_stopped_no_new_dispatch', state)
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
            return ExtendedModelResponse(model_response=ModelResponse(result=[]),
                command=Command(update={"execution_error": exc.error, "review": None}))

    @hook_config(can_jump_to=["end"])
    def after_model(self, state, runtime):
        if state.get("execution_error"):
            return {"jump_to": "end"}
        return None
