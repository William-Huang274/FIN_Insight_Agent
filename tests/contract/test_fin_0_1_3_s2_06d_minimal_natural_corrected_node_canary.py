from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = ROOT / "scripts" / "releases"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_fin_ia_0_1_3_s2_06d_minimal_natural_corrected_node_canary as canary  # noqa: E402


class ValidNaturalShapeFake:
    def __call__(self, **kwargs: object) -> dict[str, object]:
        request = json.loads(str(kwargs["messages"][1]["content"]))  # type: ignore[index]
        context = request["context"]
        unit = context["research_unit"]
        directive = context["visible_correction_directive"]
        gap_id = unit["gap_ids"][0]
        payload = {
            "schema_version": canary.CORRECTED_NODE_ENVELOPE_SCHEMA,
            "node_output": {
                "case_key": request["case_key"],
                "as_of": request["as_of"],
                "unit_id": unit["unit_id"],
                "epistemic_state": "mixed",
                "judgment": "Supply pressure is supported, while the margin effect remains unresolved.",
                "mechanism": "Constrained components can delay conversion and raise cost pressure.",
                "financial_or_valuation_link": "The unresolved pass-through gap limits a durable margin conclusion.",
                "evidence_ids": unit["evidence_ids"],
                "counterevidence_ids": [],
                "gap_ids": unit["gap_ids"],
                "what_would_change": "Issuer evidence on pass-through and fulfillment would change the judgment.",
            },
            "correction_resolutions": [
                {
                    "correction_id": directive["correction_ids"][0],
                    "status": "typed_unresolved",
                    "evidence_ids": directive["evidence_ids"],
                    "gap_ids": [gap_id],
                    "resolution_summary": "No valid counterevidence is available; the limitation remains typed.",
                }
            ],
        }
        content = json.dumps(payload)
        return {
            "status": "ok",
            "content": content,
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 100,
            "total_tokens": 200,
            "transport_attempt_count": 1,
        }


def test_one_call_canary_is_capture_first_exact_once_and_never_promotes(
    tmp_path: Path,
) -> None:
    material = canary.build_material()
    admission = canary.compile_admission(head="a" * 40, material=material)
    terminal = canary.execute_canary(
        admission=admission,
        material=material,
        provider_call=ValidNaturalShapeFake(),
        runtime_root=tmp_path / "run",
        ledger_path=tmp_path / "ledger.sqlite",
        observed_at="2026-08-07T10:00:00Z",
    )
    assert terminal["status"] == "terminal_completed", terminal
    assert terminal["provider_calls"] == 1
    assert terminal["retry_count"] == terminal["fallback_count"] == 0
    assert terminal["corrected_candidate_frozen"] is False
    assert terminal["formal_DELL_proof_executed"] is False
    assert terminal["correction_closure_receipts"][0]["status"] == "typed_unresolved"
    assert len(list((tmp_path / "run/canary/captures").glob("*.json"))) == 1
