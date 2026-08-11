from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from sec_agent.s2_same_evidence_collect_all_diagnostic import (
    execute_quarantined_collect_all,
    issue_diagnostic_admission,
)
from sec_agent.s2_same_evidence_experiment_runtime import (
    POLICY_REF,
    SECTION_IDS,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "src/sec_agent/s2_same_evidence_collect_all_diagnostic.py"
POLICY = ROOT / POLICY_REF


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lead(case: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    units = [
        {
            "unit_id": f"DELL_RU0{index + 1}",
            "family": family,
            "question": "What does the assigned evidence support?",
            "why_material": "The answer can change the bounded judgment.",
            "evidence_ids": [],
            "gap_ids": [],
            "stop_condition": "Stop after assessing the assigned evidence and gaps.",
        }
        for index, family in enumerate(policy["mandatory_research_families"])
    ]
    for index, row in enumerate(case["evidence_items"]):
        units[index % len(units)]["evidence_ids"].append(row["evidence_id"])
    for index, row in enumerate(case["explicit_gaps"]):
        units[index % len(units)]["gap_ids"].append(row["gap_id"])
    return {"case_key": case["case_key"], "as_of": case["as_of"], "research_units": units}


class DownstreamFake:
    def __init__(self, *, invented_numeric: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.invented_numeric = invented_numeric

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        node = request["node_type"]
        context = request["context"]
        if node == "specialist_judgment":
            unit = context["research_unit"]
            identity = context["case_identity"]
            output = {
                "case_key": identity["case_key"], "as_of": identity["as_of"],
                "unit_id": unit["unit_id"], "epistemic_state": "mixed",
                "judgment": self._text("The evidence supports a bounded judgment."),
                "mechanism": "The evidence affects the operating interpretation.",
                "financial_or_valuation_link": "The valuation link remains bounded.",
                "evidence_ids": list(unit["evidence_ids"]), "counterevidence_ids": [],
                "gap_ids": list(unit["gap_ids"]),
                "what_would_change": "New case-local evidence could change the judgment.",
            }
        elif node == "cross_cell_synthesis":
            identity = context["case_identity"]
            units = [row["unit_id"] for row in context["specialist_outputs"]]
            output = {
                "case_key": identity["case_key"], "as_of": identity["as_of"],
                "thesis": self._text("The combined evidence supports a bounded thesis."),
                "confidence": "Moderate because material gaps remain.", "unit_ids": units,
                "dependencies": [], "conflicts": [],
                "material_gap_ids": [row["gap_id"] for row in context["explicit_gaps"]],
                "counter_thesis": "The same evidence permits a weaker interpretation.",
                "what_would_change": "New case-local evidence could resolve uncertainty.",
            }
        elif node == "writer":
            identity = context["case_identity"]
            evidence = [row["evidence_id"] for row in context["evidence_index"]]
            gaps = [row["gap_id"] for row in context["explicit_gaps"]]
            units = [row["unit_id"] for row in context["specialist_outputs"]]
            sections = [
                {"section_id": section, "heading": section.replace("_", " "),
                 "narrative": self._text("Evidence supports a bounded conclusion."),
                 "evidence_ids": [evidence[0]], "unit_ids": units, "gap_ids": [gaps[0]]}
                for section in SECTION_IDS
            ]
            sections[0]["evidence_ids"] = evidence
            sections[0]["gap_ids"] = gaps
            output = {
                "case_key": identity["case_key"], "as_of": identity["as_of"],
                "title": "DELL same-evidence diagnostic", "sections": sections,
                "overall_boundary": "This remains a bounded raw diagnostic.",
            }
        else:
            identity = context["case_identity"]
            output = {
                "case_key": identity["case_key"], "as_of": identity["as_of"],
                "decision": "accept_raw_candidate", "material_failure": False, "findings": [],
                "checked_unit_ids": [row["unit_id"] for row in context["specialist_outputs"]],
                "checked_section_ids": [row["section_id"] for row in context["writer"]["sections"]],
            }
        return {
            "status": "ok", "content": json.dumps(output), "finish_reason": "stop",
            "input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
            "transport_attempt_count": 1, "raw_response": {"fixture": True},
        }

    def _text(self, value: str) -> str:
        return value + (" Scenario 987654321 percent." if self.invented_numeric else "")


def _run(tmp_path: Path, *, invented_numeric: bool) -> tuple[dict[str, Any], DownstreamFake]:
    policy = load_runtime_policy(ROOT)
    case = load_frozen_blind_inputs(ROOT, policy)["cases"][0]
    lead_capture = tmp_path / "lead.json"
    lead_capture.write_text(
        json.dumps({"gateway_result": {"content": json.dumps(_lead(case, policy))}}),
        encoding="utf-8",
    )
    admission = issue_diagnostic_admission(
        execution_git_commit="a" * 40,
        runtime_sha256=_sha(RUNTIME),
        policy_sha256=_sha(POLICY),
        original_admission_digest="b" * 64,
        original_lead_capture_sha256=_sha(lead_capture),
        original_lead_capture_digest="c" * 64,
        issued_at="2026-08-07T00:00:00Z",
        expires_at="2026-08-08T00:00:00Z",
        nonce="fixture",
    )
    fake = DownstreamFake(invented_numeric=invented_numeric)
    result = execute_quarantined_collect_all(
        admission=admission, original_lead_capture=lead_capture,
        case_input=case, policy=policy, execution_git_commit="a" * 40,
        runtime_sha256=_sha(RUNTIME), policy_sha256=_sha(POLICY),
        runtime_root=tmp_path / "runtime",
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite3"),
        provider_call=fake, observed_at="2026-08-07T01:00:00Z",
    )
    return result, fake


def test_collect_all_reuses_lead_and_runs_all_nine_downstream_calls(tmp_path: Path) -> None:
    result, fake = _run(tmp_path, invented_numeric=False)
    assert result["status"] == "quarantined_collect_all_complete"
    assert result["new_provider_calls"] == 9
    assert result["full_logical_chain_calls_including_reused_lead"] == 10
    assert len(fake.calls) == 9
    assert result["business_promotable"] is False
    assert result["formal_raw_candidate"] is False
    assert result["business_artifact_promotions"] == 0


def test_collect_all_records_numeric_failures_and_still_reaches_verifier(tmp_path: Path) -> None:
    result, fake = _run(tmp_path, invented_numeric=True)
    assert len(fake.calls) == 9
    assert fake.calls[-1]["role"].endswith("verifier")
    phases = {row["phase"] for row in result["findings"]}
    assert {"specialist_judgment", "cross_cell_synthesis", "writer"} <= phases
    assert any(row["numeric_findings"] for row in result["findings"])
