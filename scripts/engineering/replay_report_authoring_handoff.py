"""Offline projection replay of saved writer requests; no model or tool execution."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from langchain_core.messages import messages_from_dict
from langgraph.graph.message import add_messages

from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.report_authoring import (
    report_authoring_input, report_authoring_message_update,
)
from sec_agent.agent_runtime.report_synthesis_agent import report_model_view


def replay(run_dir, output):
    run_dir, output = Path(run_dir).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Use a new output directory; original records must not be overwritten")
    output.mkdir(parents=True)
    inputs = {}

    def load(path):
        raw = path.read_bytes()
        inputs[str(path)] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    def save(name, value):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    parent = load(run_dir / "failure-state.private.json")
    convergence = load(run_dir / "convergence-state.private.json")
    artifacts = CaseArtifacts(parent["case_papers"]).with_revisions(convergence["revisions"])
    basis_digest = convergence["authoring_context"]["basis_digest"]

    def refresh(state):
        messages = messages_from_dict([{"type": m["type"], "data": m} for m in state["messages"]])
        old_message = next(m for m in messages if m.type == "human"
                           and "authoring_basis_digest" in m.content)
        old_body = json.loads(old_message.content)
        assert old_body["authoring_basis_digest"] == basis_digest
        body = report_authoring_input(
            old_body["question"], artifacts, human_feedback=old_body.get("human_feedback"),
            report=convergence.get("report"), review=convergence.get("report_review"),
            synthesis=convergence.get("synthesis"), synthesis_review=convergence.get("synthesis_review"),
            material_conditions=old_body.get("material_conditions", ()))
        body["authoring_basis_digest"] = basis_digest
        assert body["catalog"] == old_body["catalog"]
        assert body["research_synthesis"] == report_model_view(convergence["synthesis"])
        assert body["synthesis_review"] == convergence["synthesis_review"]
        updates, same = report_authoring_message_update(body, messages)
        assert same
        refreshed = add_messages(messages, updates)
        assert len(refreshed) == len(messages)
        for before, after in zip(messages, refreshed):
            if before.id != old_message.id:
                assert before == after
        assert add_messages(refreshed, report_authoring_message_update(body, refreshed)[0]) == refreshed
        result = deepcopy(state)
        result["messages"] = [m.model_dump(mode="json") for m in refreshed]
        assert {k: v for k, v in result.items() if k != "messages"} == {
            k: v for k, v in state.items() if k != "messages"}
        return result, old_body, body

    rows = []
    for path in sorted((run_dir / "request-states").glob("*.private.json")):
        request_state = load(path)
        if request_state["actor"] != "writer":
            continue
        restored, old_body, body = refresh(request_state["state"])
        request = load(run_dir / "requests" / path.name)
        projected = deepcopy(request)
        matches = 0
        for message in projected["messages"]:
            if message["role"] != "user" or not isinstance(message.get("content"), str):
                continue
            try:
                parsed = json.loads(message["content"])
            except ValueError:
                continue
            if parsed == old_body:
                message["content"] = json.dumps(body, ensure_ascii=False)
                matches += 1
        assert matches == 1
        assert {k: v for k, v in request.items() if k != "messages"} == {
            k: v for k, v in projected.items() if k != "messages"}
        for old_msg, new_msg in zip(request["messages"], projected["messages"]):
            if old_msg != new_msg:
                assert old_msg["role"] == new_msg["role"] == "user"
        save("requests/" + path.name, projected)
        save("request-states/" + path.name, {**request_state, "state": restored})
        rows.append({"request": path.name,
            "before_characters": len(json.dumps(request, ensure_ascii=False)),
            "after_characters": len(json.dumps(projected, ensure_ascii=False)),
            "successful_reads_preserved": sum(m.get("type") == "tool" and m.get("status") == "success"
                and m.get("name", "").startswith("read_") for m in request_state["state"]["messages"])})
    if not rows:
        raise ValueError("No real writer requests found")
    original = load(run_dir / "actor-states/writer.private.json")
    restored, _, _ = refresh(original)
    save("recovered-writer-state.private.json", restored)
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in inputs.items())
    result = {"provider_calls": 0, "tool_calls": 0, "requests": rows,
        "all_original_files_unchanged": True, "proposals_receipts_and_reasoning_unchanged": True,
        "papers_synthesis_review_unchanged": True, "same_basis_refresh_idempotent": True,
        "recovered_message_count": len(restored["messages"]),
        "recovered_successful_reads": sum(m.get("type") == "tool" and m.get("status") == "success"
            and m.get("name", "").startswith("read_") for m in restored["messages"]),
        "current_synthesis_matches_bound_basis": convergence["authoring_context"]["basis"]["synthesis"] == convergence["synthesis"],
        "review_finding_ids": [f["finding_id"] for f in convergence["synthesis_review"]["findings"]],
        "automatic_publication": False, "financial_quality_pass": False}
    save("input-hashes.json", inputs)
    save("result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    def offline(*args, **kwargs):
        raise RuntimeError("Network is disabled for this offline replay")

    socket.socket.connect = offline
    socket.create_connection = offline
    print(json.dumps(replay(args.run_dir, args.output), ensure_ascii=False, indent=2))
