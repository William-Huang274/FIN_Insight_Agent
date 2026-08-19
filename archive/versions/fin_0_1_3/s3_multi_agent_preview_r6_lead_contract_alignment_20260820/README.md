# R6 Lead contract alignment zero-call proof

This directory preserves the one-time, capture-bound R6 replay used on 2026-08-20.

- `run_zero_call.py` binds the immutable R6 authority, public failure and two local provider captures.
- It generated the tracked Lead plan checkpoint and zero-call result referenced by worklog 090.
- It is not an active product entrypoint and must not be registered in the current Runtime.
- Reusable behavior lives in `src/sec_agent/research/multi_agent_preview.py` and `multi_agent_preview_runtime.py`; regression coverage lives in the active test suite.
