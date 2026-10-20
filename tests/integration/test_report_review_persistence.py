"""Real Agent Server/PostgreSQL verifier history; no Java/product revision claim."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.integration.test_java_intake_native import COMPOSE, ROOT, Stack

pytestmark = pytest.mark.skipif(
    os.getenv("FIN_REPORT_REVIEW_PERSISTENCE_QUALIFICATION") != "1",
    reason="explicit isolated PostgreSQL verifier qualification required")


class ReviewStack(Stack):
    graph_fixture = ROOT / "tests/integration/fixtures/report_review_persistence_graph.py"
    compose_files = (COMPOSE, ROOT / "deploy/qualification/report_review_persistence.compose.yaml")
    synthetic_components = ["model replies", "historical report and tool receipt"]
    registered_graph = "/probe/report_review_persistence_graph.py:graph"
    exercised_runtime = ["verifier create_agent", "review history tools", "checkpoint", "queue"]
    unexercised = ["Java", "BFF", "browser", "full research convergence", "financial quality"]

    def __init__(self):
        super().__init__()
        environment = json.loads((self.output / "environment.json").read_text(encoding="utf-8"))
        environment["real_services"] = ["Agent Server", "PostgreSQL", "Redis"]
        environment["real_runtime"] = self.exercised_runtime
        environment["not_exercised"] = self.unexercised
        paths = [*(ROOT / "src").rglob("*.py"), self.graph_fixture, Path(__file__),
                 *self.compose_files]
        self.source_hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in paths}
        environment["qualified_source_hashes"] = self.source_hashes
        self.save("environment", environment)

    def verify_sources(self):
        assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == digest
                   for p, digest in self.source_hashes.items())
        self.save("source-postflight", {"unchanged": True, "hashes": self.source_hashes})

    def audit_container(self):
        ids = subprocess.check_output([self.docker, "ps", "-q", "--filter",
            "label=com.docker.compose.project=" + self.project,
            "--filter", "label=com.docker.compose.service=api"], text=True, timeout=20).split()
        assert len(ids) == 1
        row = json.loads(subprocess.check_output(
            [self.docker, "inspect", ids[0]], text=True, timeout=20))[0]
        env = dict(v.split("=", 1) for v in row["Config"]["Env"])
        presence = {k: bool(v) for k, v in env.items()
                    if any(t in k.upper() for t in ("API_KEY", "TOKEN", "SECRET"))}
        assert not any(v for k, v in presence.items() if k != "LANGSMITH_API_KEY")
        assert env["LANGSMITH_TRACING"] == "false"
        assert json.loads(env["LANGSERVE_GRAPHS"]) == {
            "research_session": self.registered_graph}
        for mount in row["Mounts"]:
            if mount["Destination"] in ("/qualification/src", "/qualification/configs"):
                assert not mount["RW"]
        self.save("review-container-contract", {
            "credential_presence_only": presence, "registered_graph": env["LANGSERVE_GRAPHS"],
            "real_services": ["Agent Server", "PostgreSQL", "Redis"],
            "real_runtime": self.exercised_runtime,
            "not_exercised": self.unexercised,
            "provider_calls": 0})


def task(version):
    return {"type": "human", "id": f"task-{version}", "content": json.dumps({
        "question": "Static history qualification", "review_target": "final_report",
        "report": {"title": "Static report", "narrative_markdown": f"version {version}"},
        "catalog": {"papers": []}})}


HISTORY = [
    task(1),
    {"type": "ai", "id": "original-read", "content": [
        {"type": "text", "text": "Public source inspection"},
        {"type": "reasoning", "reasoning": "PRIVATE_ORIGINAL"}],
     "additional_kwargs": {"reasoning_content": "PRIVATE_EXTRA"},
     "tool_calls": [{"id": "r", "name": "read_current_source",
                     "args": {"source_id": "CALC::a"}, "type": "tool_call"}]},
    {"type": "tool", "id": "original-receipt", "tool_call_id": "r",
     "name": "read_current_source",
     "content": '{"calculation_id":"CALC::a","operands":[1,2],"period":"FY2027"}'},
]


def test_verifier_versions_restart_and_exact_history(monkeypatch):
    monkeypatch.setenv("FIN_NATIVE_ATTEMPT_DIR", str(Path(os.environ["FIN_NATIVE_ATTEMPT_DIR"]) / "reviewer"))
    s = ReviewStack()
    digests = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in (ROOT / "src").rglob("*.py")}

    def run(tid, body, *, status):
        created = s.request(s.native, "POST", f"/threads/{tid}/runs",
                  json={"assistant_id": "research_session",
                        "config": {"recursion_limit": 50}, **body})
        rid = created["run_id"]
        s.terminal(tid, rid, status=status)
        return rid, s.state_of(tid)

    try:
        s.compose("up", "-d", "--pull", "never", "api")
        s.healthy()
        s.audit_container()
        for interrupted in (False, True):
            tid = s.request(s.native, "POST", "/threads", json={})["thread_id"]
            original_checkpoint = None
            for version in (2, 3, 4):
                current = task(version)
                rid, state = run(tid, {
                    "input": {"messages": [*HISTORY, current] if version == 2 else [current],
                              "report": json.loads(current["content"])["report"], "output": None},
                    "config": {"recursion_limit": 50,
                               "configurable": {"pause_after_history": interrupted}},
                }, status="success")
                if interrupted:
                    # Static breakpoint: run success, thread interrupted. The
                    # checkpoint's pending work, not run.status, proves the stop.
                    thread = s.request(s.native, "GET", f"/threads/{tid}")
                    assert thread["status"] == "interrupted"
                    assert state["next"] and not state["values"].get("output")
                    saved = state["values"]["messages"]
                    assert len([m for m in saved if m.get("name") == "read_review_history"
                                and m["type"] == "tool"]) == (version - 1) * 2
                    if version == 3:
                        s.save("before-restart", state)
                        s.compose("stop", "-t", "5", "api", "postgres", "redis")
                        s.compose("up", "-d", "--pull", "never", "api")
                        s.healthy()
                        restored = s.state_of(tid)
                        assert restored["values"] == state["values"]
                        assert restored["checkpoint"] == state["checkpoint"]
                        s.save("after-restart", restored)
                    # Continue native pending work, do not reconstruct a prompt.
                    rid, state = run(tid, {"input": None, "config": {
                        "recursion_limit": 50, "configurable": {"pause_after_history": False}}},
                        status="success")
                values = state["values"]
                assert not state["next"]
                assert f"version {version}" in values["output"]["summary"]
                assert values["report"]["narrative_markdown"] == f"version {version}"
                messages = values["messages"]
                assert messages[2]["content"] == HISTORY[2]["content"]
                assert messages[1]["additional_kwargs"]["reasoning_content"] == "PRIVATE_EXTRA"
                receipts = [m for m in messages if m["type"] == "tool" and m.get("name") == "read_review_history"]
                assert len(receipts) == (version - 1) * 2
                assert all("PRIVATE_" not in m["content"] for m in receipts)
                assert len([m for m in messages if m["type"] == "human"]) == version
                s.save(f"{'interrupted' if interrupted else 'normal'}-version-{version}", state)
                s.record(f"verifier-version-{version}", thread_id=tid, run_id=rid,
                         interrupted=interrupted, history_reads=len(receipts),
                         report_version=version, provider_calls=0)
                if version == 2:
                    original_checkpoint = state["checkpoint"]
            old = s.request(s.native, "POST", f"/threads/{tid}/state/checkpoint",
                            json={"checkpoint": original_checkpoint})
            assert old["values"]["report"]["narrative_markdown"] == "version 2"
            assert "version 2" in old["values"]["output"]["summary"]
        turns = list(map(json.loads, (s.events / "review-model-turns.jsonl").read_text().splitlines()))
        assert len(turns) == 12
        assert sum(r["phase"] == "history_read" for r in turns) == 6
        assert sum(r["phase"] == "submission" for r in turns) == 6
        assert all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == digest
                   for p, digest in digests.items())
        s.verify_sources()
        s.save("review-result", {"passed": True, "versions_reviewed": 6,
            "native_runs": 9, "scripted_model_turns": len(turns), "provider_calls": 0,
            "restart": ["Agent Server", "PostgreSQL", "Redis"], "source_hashes": digests,
            "financial_quality_certified": False, "organization_product_revision_verified": False})
    finally:
        try:
            s.compose("logs", "--no-color")
        finally:
            s.compose("stop", "-t", "5")
            s.native.close()
            s.bff.close()


class ConvergenceStack(ReviewStack):
    graph_fixture = ROOT / "tests/integration/fixtures/report_convergence_persistence_graph.py"
    compose_files = (*ReviewStack.compose_files, ROOT / "deploy/qualification/report_convergence_persistence.compose.yaml")
    registered_graph = "/probe/report_convergence_persistence_graph.py:graph"
    exercised_runtime = ["research convergence integrated parent", "writer/verifier child agents",
                          "source/history tools", "responsibility router", "checkpoint", "queue"]
    unexercised = ["Java", "BFF", "browser", "specialist execution", "user-triggered revision", "financial quality"]


def test_convergence_parent_corrections_and_review_history_after_restart(monkeypatch):
    from test_research_convergence import artifact_fixture
    monkeypatch.setenv("FIN_NATIVE_ATTEMPT_DIR", str(Path(os.environ["FIN_NATIVE_ATTEMPT_DIR"]) / "convergence"))
    monkeypatch.setenv("FIN_PROBE_SUBNET", os.environ["FIN_CONVERGENCE_PROBE_SUBNET"])
    s = ConvergenceStack()
    # Serialize the same deterministic, source-bound workpapers used by the
    # maintained unit tests; no private corpus or live retrieval is involved.
    papers = list(artifact_fixture()._author_states.values())
    (s.events / "convergence-papers.json").write_text(json.dumps(papers), encoding="utf-8")

    def run(tid, input_value):
        created = s.request(s.native, "POST", f"/threads/{tid}/runs", json={
            "assistant_id": "research_session", "input": input_value,
            "config": {"recursion_limit": 180}})
        s.terminal(tid, created["run_id"])
        return s.state_of(tid)

    try:
        s.compose("up", "-d", "--pull", "never", "api")
        s.healthy()
        s.audit_container()
        tid = s.request(s.native, "POST", "/threads", json={})["thread_id"]
        for index in range(3):
            state = run(tid, {} if index == 0 else None)
            assert state["next"] == ["report_verifier"]
            values = state["values"]
            assert values["correction_round"] == index
            assert f"Revision {index}." in values["report"]["narrative_markdown"]
            history = values["artifact_history"]
            assert len([r for r in history if r["actor"] == "writer"]) == index + 1
            assert len([r for r in history if r["actor"] == "report_verifier"]) == index
            s.save(f"convergence-report-{index + 1}", state)
            if index == 1:
                s.compose("stop", "-t", "5", "api", "postgres", "redis")
                s.compose("up", "-d", "--pull", "never", "api")
                s.healthy()
                restored = s.state_of(tid)
                assert restored["checkpoint"] == state["checkpoint"]
                assert restored["values"] == state["values"]
                s.save("convergence-after-restart", restored)
        final = run(tid, None)
        assert not final["next"]
        values = final["values"]
        assert values["phase"] == "case_report_ready_for_human_review"
        assert not values["stop_reason"] and not values["report_review"]["findings"]
        assert values["report"]["citations"]
        assert "PRIVATE_" not in json.dumps(values)
        turns = list(map(json.loads, (s.events / "convergence-turns.jsonl").read_text().splitlines()))
        assert len(turns) == 9
        assert [r["round"] for r in turns if r["actor"] == "writer"] == [0, 1, 2]
        assert [r["phase"] for r in turns if r["actor"] == "report_verifier"] == [
            "read_current_source", "submission", "read_review_history", "submission",
            "read_review_history", "submission"]
        s.verify_sources()
        s.save("convergence-result", {"passed": True, "thread_id": tid, "native_runs": 4,
            "report_versions": 3, "scripted_model_turns": 9, "provider_calls": 0,
            "real_graph": "build_research_convergence_graph integrated writer/report_verifier route",
            "not_exercised": ["specialist execution", "live models", "Java", "browser", "user-triggered revision"],
            "financial_quality_certified": False})
        s.save("convergence-final", final)
    finally:
        try:
            s.compose("logs", "--no-color")
        finally:
            s.compose("stop", "-t", "5")
            s.native.close()
            s.bff.close()
