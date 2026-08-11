from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from scripts.cloud.sec_agent_graph_runner import _native_resume_requires_synthesis
from sec_agent.langgraph_orchestrator import NATIVE_NODE_ORDER


def test_native_resume_synthesis_gate_only_blocks_pre_synthesis_nodes() -> None:
    assert _native_resume_requires_synthesis("build_judgment_plan", NATIVE_NODE_ORDER) is True
    assert _native_resume_requires_synthesis("synthesize_answer", NATIVE_NODE_ORDER) is True
    assert _native_resume_requires_synthesis("execute_second_pass_retrieval", NATIVE_NODE_ORDER) is True

    assert _native_resume_requires_synthesis("verify_claims", NATIVE_NODE_ORDER) is False
    assert _native_resume_requires_synthesis("run_deterministic_gates", NATIVE_NODE_ORDER) is False
    assert _native_resume_requires_synthesis("render_answer", NATIVE_NODE_ORDER) is False
