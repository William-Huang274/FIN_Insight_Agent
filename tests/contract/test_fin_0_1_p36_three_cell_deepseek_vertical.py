from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "releases" / "run_fin_ia_0_1_p36_three_cell_deepseek_vertical.py"
CONTRACT = ROOT / "configs" / "releases" / "fin_ia_0_1_p36_three_cell_deepseek_vertical_contract_v1_1.json"


def _module():
    spec = importlib.util.spec_from_file_location("fin_ia_0_1_three_cell_vertical", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(map(str, value)) | {
            key
            for item in value.values()
            for key in _all_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def _candidate(role: str, index: int) -> dict:
    return {
        "candidate_id": f"{role}_{index}",
        "retrieval_lane": "gold_fact_sql" if role == "revenue_capture" else "object_bm25",
        "rank": index,
        "ticker": "NVDA",
        "title": f"Candidate {index}",
        "excerpt": "Bounded evidence excerpt.",
        "source_name": "fixture",
        "source_type": "official",
        "published_at": "2026-01-01",
        "citation_url": "https://example.invalid/source",
        "citation_span": "section 1",
        "evidence_ref": f"ev_{role}_{index}",
        "authority_mode": "official_candidate",
        "claim_boundary": "Do not exceed the disclosed scope.",
        "exact_value_authority": role == "revenue_capture",
        "numeric_eligible": role == "revenue_capture",
        "writer_citable": False,
        "promotion_status": "candidate_not_promoted",
    }


def _inputs(contract: dict) -> tuple[dict, dict]:
    binding = contract["case_binding"]
    roles = binding["selected_roles"]
    research = {
        "case_id": binding["case_id"],
        "case_version": 1,
        "query": "P36 question",
        "as_of": "2026-07-19",
        "preview_digest": binding["research_preview_digest"],
        "cells": [
            {
                "cell_key": f"cell_{role}",
                "evidence_role": role,
                "decision_question": f"Question for {role}",
                "retrieval_lane": "gold_fact_sql" if role == "revenue_capture" else "object_bm25",
                "status": "candidate_ready",
                "typed_gap": None,
                "candidates": [_candidate(role, 1)],
            }
            for role in roles
        ],
        "source_inventory": [],
        "execution_counts": {"network_calls": 0, "model_calls": 0, "canonical_store_writes": 0},
    }
    analysis = {
        "case_id": binding["case_id"],
        "analysis_digest": binding["analysis_digest"],
        "source_preview_digest": binding["research_preview_digest"],
        "numeric": {
            "status": "exact_local_facts_computed",
            "facts": [{
                "candidate_id": "revenue_capture_1",
                "metric_family": "revenue",
                "value": "100",
                "citation_url": "https://example.invalid/should-not-reach-writer",
                "citation_span": "table 1",
                "source_url": "https://example.invalid/source",
            }],
            "derived_metrics": [{"metric": "gross_margin", "value": "70.00"}],
        },
        "repairs": [
            {"evidence_role": role, "repair_id": f"repair_{role}", "remaining_gap": f"gap_{role}"}
            for role in roles
        ],
        "execution_counts": {"network_calls": 0, "model_calls": 0, "canonical_store_writes": 0},
        "hard_boundaries": {"canonical_store_writes": 0, "case_mutations": 0},
    }
    return research, analysis


def test_contract_is_one_preflight_plus_three_semantic_calls_bounded_and_not_release_admitted() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["status"] == "frozen_pending_explicit_paid_llm_approval"
    assert contract["model_profile"]["model"] == "deepseek-v4-pro"
    assert contract["version"] == "1.1"
    assert contract["provider_preflight"] == {
        "required": True,
        "max_output_tokens": 24,
        "thinking": "disabled",
        "max_transport_attempts": 1,
        "persist_raw_response": False,
        "stop_before_semantic_stages_on_failure": True,
    }
    assert contract["execution_budget"]["max_provider_preflight_calls"] == 1
    assert contract["execution_budget"]["max_semantic_model_calls"] == 3
    assert contract["execution_budget"]["max_total_paid_calls"] == 4
    assert contract["execution_budget"]["max_transport_attempts_per_call"] == 1
    assert contract["execution_budget"]["max_total_cost_usd"] == 0.05
    assert [row["stage_id"] for row in contract["stages"]] == [
        "domain_judgment",
        "lead_review_and_bounded_repair",
        "writer_no_source",
    ]
    assert contract["hard_boundaries"]["canonical_case_writes"] == 0
    assert contract["hard_boundaries"]["evidence_promotions"] == 0
    assert contract["hard_boundaries"]["release_admission"] is False
    assert contract["hard_boundaries"]["human_senior_review_required"] is True


def test_input_freeze_selects_only_three_roles_and_preserves_zero_write_boundary() -> None:
    module = _module()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    research, analysis = _inputs(contract)
    pack = module.build_frozen_input_pack(contract, research, analysis)
    assert pack["selected_roles"] == contract["case_binding"]["selected_roles"]
    assert len(pack["cells"]) == 3
    assert all(cell["candidates"][0]["promotion_status"] == "candidate_not_promoted" for cell in pack["cells"])
    assert pack["boundaries"] == {
        "candidate_evidence_not_promoted": True,
        "model_must_not_infer_beyond_claim_boundary": True,
        "canonical_case_writes": 0,
        "evidence_promotions": 0,
        "release_admission": False,
    }
    assert pack["input_digest"] == module.canonical_digest({key: value for key, value in pack.items() if key != "input_digest"})


def test_writer_input_excludes_raw_source_surface() -> None:
    module = _module()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    research, analysis = _inputs(contract)
    pack = module.build_frozen_input_pack(contract, research, analysis)
    lead = {
        "lead_synthesis": {"primary_thesis": "bounded"},
        "reviewed_judgments": [
            {
                "evidence_role": role,
                "reviewed_judgment": "bounded judgment",
                "counter_thesis": "counter",
                "what_would_change": "new evidence",
                "remaining_gap": "gap",
            }
            for role in pack["selected_roles"]
        ],
    }
    writer = module.build_writer_no_source_pack(pack, lead)
    assert writer["source_access_calls"] == 0
    assert not {
        "cells",
        "candidates",
        "citation_url",
        "citation_span",
        "source_url",
        "excerpt",
    }.intersection(_all_keys(writer))


def test_nonzero_upstream_execution_count_stops_freeze() -> None:
    module = _module()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    research, analysis = _inputs(contract)
    research["execution_counts"]["model_calls"] = 1
    with pytest.raises(module.VerticalRunError, match="research.execution_counts_nonzero"):
        module.build_frozen_input_pack(contract, research, analysis)


def test_execute_uses_one_preflight_plus_three_semantic_calls(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    research, analysis = _inputs(contract)
    pack = module.build_frozen_input_pack(contract, research, analysis)
    calls: list[str] = []

    def fake_chat_completion(**kwargs):
        role = str(kwargs["role"])
        calls.append(role)
        roles = pack["selected_roles"]
        if role == "provider_preflight":
            payload = {"status": "ok"}
        elif role == "domain_judgment":
            payload = {
                "judgments": [
                    {
                        "evidence_role": item,
                        "confidence": "bounded",
                        "judgment": f"judgment {item}",
                        "evidence_refs": [f"{item}_1"],
                        "numeric_refs": [],
                        "counter_thesis": "counter",
                        "what_would_change": "new evidence",
                        "remaining_gap": "gap",
                    }
                    for item in roles
                ]
            }
        elif role == "lead_review_and_bounded_repair":
            payload = {
                "lead_synthesis": {
                    "primary_thesis": "bounded thesis",
                    "decision_usefulness": "internal review",
                    "material_boundaries": "candidate evidence",
                },
                "reviewed_judgments": [
                    {
                        "evidence_role": item,
                        "confidence": "bounded",
                        "reviewed_judgment": f"reviewed {item}",
                        "evidence_refs": [f"{item}_1"],
                        "numeric_refs": [],
                        "counter_thesis": "counter",
                        "what_would_change": "new evidence",
                        "remaining_gap": "gap",
                    }
                    for item in roles
                ],
            }
        else:
            payload = {
                "title": "P36",
                "executive_summary": "bounded summary",
                "decision_implications": "review required",
                "sections": [
                    {
                        "evidence_role": item,
                        "heading": item,
                        "narrative": f"narrative {item}",
                        "boundary": "candidate evidence",
                        "what_would_change": "new evidence",
                    }
                    for item in roles
                ],
                "unresolved_gaps": ["gap"],
                "review_note": "human review required",
            }
        return {
            "status": "ok",
            "call_id": f"call_{len(calls)}",
            "model": contract["model_profile"]["model"],
            "content": json.dumps(payload),
            "finish_reason": "stop",
            "latency_ms": 1,
            "input_tokens": 10,
            "output_tokens": 10,
            "total_tokens": 20,
            "transport_attempt_count": 1,
            "raw_response": {"usage": {"prompt_cache_miss_tokens": 10}},
        }

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-not-a-secret")
    monkeypatch.setattr(module, "chat_completion", fake_chat_completion)
    result = module.execute_vertical(contract, pack, tmp_path)

    assert calls == [
        "provider_preflight",
        "domain_judgment",
        "lead_review_and_bounded_repair",
        "writer_no_source",
    ]
    assert result["provider_preflight_call_count"] == 1
    assert result["semantic_model_call_count"] == 3
    assert result["total_paid_call_count"] == 4
    progress = json.loads((tmp_path / "execution_progress.json").read_text(encoding="utf-8"))
    assert progress["total_paid_call_count"] == 4
    assert progress["semantic_model_calls_completed"] == 3
    preflight = json.loads((tmp_path / "provider_preflight.json").read_text(encoding="utf-8"))
    assert preflight["raw_response_saved"] is False
    assert "content" not in preflight


def test_provider_failure_is_counted_and_stops_before_semantic_calls(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    research, analysis = _inputs(contract)
    pack = module.build_frozen_input_pack(contract, research, analysis)
    calls: list[str] = []

    def fake_chat_completion(**kwargs):
        calls.append(str(kwargs["role"]))
        return {
            "status": "error",
            "failure_reason": "provider unavailable",
            "transport_attempt_count": 1,
        }

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-not-a-secret")
    monkeypatch.setattr(module, "chat_completion", fake_chat_completion)
    with pytest.raises(module.VerticalRunError, match="provider_preflight_failure"):
        module.execute_vertical(contract, pack, tmp_path)

    assert calls == ["provider_preflight"]
    progress = json.loads((tmp_path / "execution_progress.json").read_text(encoding="utf-8"))
    assert progress["provider_preflight_call_count"] == 1
    assert progress["semantic_model_call_count"] == 0
    assert progress["total_paid_call_count"] == 1
