"""Provider-wire usage projection for a harness transport boundary.

ACP context occupancy is not a bill. Observe *every* provider request, including
compaction, before projecting public ACP events. Raw request/response storage and
reserve/received/unknown transactions remain owned by the existing dispatch store.
No workflow, retries, prices, or compaction policy lives here.
"""
from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class ReportedUsage:
    input_uncached: int
    input_cached: int
    input_cache_write: int
    output: int
    reasoning: int | None

    def cost_micros(self, prices):
        # A write-cache rate is not declared by FIN's current TokenPrices.
        if self.input_cache_write:
            return None
        numerator = (self.input_uncached * prices.input_miss
                     + self.input_cached * prices.input_hit + self.output * prices.output)
        return (numerator + 999_999) // 1_000_000


class WireUsage:
    """Consume decoded SSE objects for one request, retaining missing as unknown.

    Messages input_tokens excludes cache read/write. Chat prompt_tokens includes
    cached tokens. Reasoning is already included in output, never charged twice.
    Terminal/error state is independent of usage completeness and research quality.
    """
    def __init__(self, protocol):
        if protocol not in {"deepseek_messages", "qwen_chat"}:
            raise ValueError("unsupported_usage_protocol")
        self.protocol = protocol
        self.raw = {}
        self.terminal = False
        self.finish_reason = None
        self.response_id = None
        self.error = None

    def observe(self, event):
        if event.get("type") == "error" or event.get("error"):
            self.error = deepcopy(event.get("error", event))
        if self.protocol == "deepseek_messages":
            message = event.get("message", {}) if event.get("type") == "message_start" else {}
            self.response_id = message.get("id", self.response_id)
            usage = message.get("usage") if message else event.get("usage")
            if isinstance(usage, dict):
                self.raw.update(deepcopy(usage))
            if event.get("type") == "message_delta":
                self.finish_reason = event.get("delta", {}).get("stop_reason", self.finish_reason)
            if event.get("type") == "message_stop":
                self.terminal = True
        else:
            self.response_id = event.get("id", self.response_id)
            if isinstance(event.get("usage"), dict):
                self.raw = deepcopy(event["usage"])
            for choice in event.get("choices", []):
                if choice.get("finish_reason") is not None:
                    self.finish_reason = choice["finish_reason"]

    def done(self):
        """Chat [DONE]; socket close alone is not a terminal response."""
        if self.protocol == "qwen_chat":
            self.terminal = True

    def reported(self):
        if not self.terminal or self.finish_reason is None or self.error is not None:
            return None
        r = self.raw
        if self.protocol == "deepseek_messages":
            miss, output = r.get("input_tokens"), r.get("output_tokens")
            hit, write = r.get("cache_read_input_tokens", 0), r.get("cache_creation_input_tokens", 0)
            reasoning = r.get("reasoning_tokens")
        else:
            prompt, output = r.get("prompt_tokens"), r.get("completion_tokens")
            prompt_details = r.get("prompt_tokens_details") or {}
            output_details = r.get("completion_tokens_details") or {}
            if not isinstance(prompt_details, dict) or not isinstance(output_details, dict):
                return None
            hit = prompt_details.get("cached_tokens", 0)
            write = 0
            reasoning = output_details.get("reasoning_tokens")
            if type(prompt) is not int or type(hit) is not int or prompt < hit:
                return None
            miss = prompt - hit
        if any(type(n) is not int or n < 0 for n in (miss, hit, write, output)):
            return None
        if reasoning is not None and (type(reasoning) is not int or reasoning < 0 or reasoning > output):
            return None
        return ReportedUsage(miss, hit, write, output, reasoning)

    def receipt(self):
        usage = self.reported()
        return {"protocol": self.protocol, "response_id": self.response_id,
                "terminal": self.terminal, "finish_reason": self.finish_reason,
                "raw_usage": deepcopy(self.raw), "error": deepcopy(self.error),
                "usage_complete": usage is not None,
                "usage": vars(usage) if usage else None}
