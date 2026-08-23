from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime import canonical_digest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts/research/run_s3_current_dynamic_writer_independent_takeover.py"
)
SPEC = importlib.util.spec_from_file_location("independent_writer_takeover", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

ZERO_SCRIPT = ROOT / "scripts/research/run_s3_current_dynamic_writer_zero_call.py"
ZERO_SPEC = importlib.util.spec_from_file_location(
    "current_dynamic_writer_zero_for_takeover", ZERO_SCRIPT
)
assert ZERO_SPEC is not None and ZERO_SPEC.loader is not None
ZERO = importlib.util.module_from_spec(ZERO_SPEC)
ZERO_SPEC.loader.exec_module(ZERO)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _binding(path: Path, root: Path, *, digest_field: str | None = None) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    result = {
        "ref": path.relative_to(root).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if digest_field:
        result.update(
            {
                "digest_field": digest_field,
                "digest": value[digest_field],
            }
        )
    return result


@pytest.fixture(scope="module")
def zero_bundle():
    return ZERO.build_zero_call_bundle()


def test_takeover_manifest_applies_only_explicit_edits(zero_bundle) -> None:
    source = ZERO._positive_payload(
        zero_bundle["catalog"], zero_bundle["protection"]
    )
    manifest = {
        "model_text_replacements": {
            "confidence.model_text": "Confidence remains bounded by reviewed evidence."
        },
        "reference_replacements": {"confidence.gap_refs": []},
        "remaining_gaps_replacement": deepcopy(source["remaining_gaps"]),
    }

    candidate = RUNNER._apply_manifest(source, manifest)

    assert candidate["confidence"]["model_text"].startswith("Confidence remains")
    assert candidate["confidence"]["gap_refs"] == []
    assert source != candidate
    assert candidate["sections"] == source["sections"]


def test_takeover_output_is_immutable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(RUNNER, "ROOT", tmp_path)
    RUNNER._write_new("result.json", {"status": "first"})
    with pytest.raises(
        RUNNER.IndependentWriterTakeoverError,
        match="independent_writer_output_identity_consumed",
    ):
        RUNNER._write_new("result.json", {"status": "replacement"})


def test_takeover_compiles_zero_provider_locally_valid_candidate(
    zero_bundle, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(RUNNER, "ROOT", tmp_path)
    catalog = deepcopy(zero_bundle["catalog"])
    protection = deepcopy(zero_bundle["protection"])
    source = ZERO._positive_payload(catalog, protection)
    source["executive_thesis"][0]["gap_refs"] = []
    source["what_would_change"][0]["gap_refs"] = []
    nested_text = json.dumps(source, ensure_ascii=False, sort_keys=True)
    nested_sha = hashlib.sha256(nested_text.encode("utf-8")).hexdigest()

    response = {
        "response_digest": "response-digest",
        "response_body": {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "function": {
                                    "arguments": json.dumps(
                                        {"arguments": nested_text},
                                        ensure_ascii=False,
                                    )
                                }
                            }
                        ]
                    }
                }
            ]
        },
    }
    assessment_body = {
        "status": "terminal_test_fixture",
        "inner_nonpromotable_diagnostic": {
            "nested_sha256": nested_sha,
            "nested_characters": len(nested_text),
            "hard_finding_count": 0,
            "quality_finding_count": 0,
            "surface_findings": [],
        },
    }
    assessment = {
        **assessment_body,
        "assessment_digest": canonical_digest(assessment_body),
    }
    authority = {"authority_digest": "authority-digest"}
    public = {"result_digest": "R14-public-digest"}
    manifest_body = {
        "schema_version": RUNNER.MANIFEST_SCHEMA_VERSION,
        "status": RUNNER.MANIFEST_STATUS,
        "run_id": RUNNER.RUN_ID,
        "case_key": "DELL",
        "source_nested_sha256": nested_sha,
        "source_nested_payload_digest": canonical_digest(source),
        "model_text_replacements": {},
        "reference_replacements": {},
        "remaining_gaps_replacement": deepcopy(source["remaining_gaps"]),
    }
    manifest = {
        **manifest_body,
        "manifest_digest": canonical_digest(manifest_body),
    }
    values = {
        "authority.json": authority,
        "public.json": public,
        "assessment.json": assessment,
        "response.json": response,
        "catalog.json": catalog,
        "protection.json": protection,
        "manifest.json": manifest,
    }
    for name, value in values.items():
        _write(tmp_path / name, value)
    source_bindings = {
        "R14_authority": _binding(
            tmp_path / "authority.json", tmp_path, digest_field="authority_digest"
        ),
        "R14_public_result": _binding(
            tmp_path / "public.json", tmp_path, digest_field="result_digest"
        ),
        "R14_failure_assessment": _binding(
            tmp_path / "assessment.json",
            tmp_path,
            digest_field="assessment_digest",
        ),
        "R14_response_capture": _binding(
            tmp_path / "response.json", tmp_path, digest_field="response_digest"
        ),
        "R10_writer_authority_catalog": _binding(
            tmp_path / "catalog.json",
            tmp_path,
            digest_field="authority_catalog_digest",
        ),
        "R10_writer_protection_contract": _binding(
            tmp_path / "protection.json",
            tmp_path,
            digest_field="protection_digest",
        ),
        "private_edit_manifest": _binding(
            tmp_path / "manifest.json", tmp_path, digest_field="manifest_digest"
        ),
    }
    decision_body = {
        "schema_version": RUNNER.DECISION_SCHEMA_VERSION,
        "status": RUNNER.DECISION_STATUS,
        "run_id": RUNNER.RUN_ID,
        "case_key": "DELL",
        "implementation_commit": "a" * 40,
        "implementation_bindings": [
            _binding(tmp_path / "manifest.json", tmp_path)
        ],
        "user_authorization": {
            "independent_writer_takeover_authorized": True,
        },
        "token_budget_basis": {
            "model_node_created": False,
            "paid_call_authority_created": False,
            "provider_token_budget": 0,
        },
        "source_bindings": source_bindings,
        "execution_budget": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "new_evidence_items": 0,
            "candidate_promotions": 0,
        },
        "expected_R14_failure_frontier": {
            "surface_finding_count": 0,
            "hard_finding_count": 0,
            "quality_finding_count": 0,
            "surface_findings": [],
        },
        "change_boundary": {
            "new_evidence_authority_or_gap_ids_allowed": False,
            "remaining_gap_ref_union_must_be_preserved": True,
            "allowed_changed_model_text_paths": [],
            "expected_reference_after": {},
            "allowed_catalog_claim_refs_added": [],
            "target_gap_rows": len(source["remaining_gaps"]),
        },
        "acceptance_boundary": {
            "independent_post_writer_review_pass": False,
            "S3_pass": False,
            "product_publication": False,
            "release_ready": False,
        },
        "output_contract": {
            "private_full_result_ref": "private/full_result.json",
            "public_result_ref": "public_result.json",
        },
    }
    decision = {
        **decision_body,
        "decision_digest": canonical_digest(decision_body),
    }
    _write(tmp_path / "decision.json", decision)

    compiled = RUNNER.compile_takeover("decision.json")

    assert compiled["public"]["execution"]["provider_calls"] == 0
    assert compiled["public"]["local_validation"] == {
        "surface_finding_count": 0,
        "hard_finding_count": 0,
        "quality_finding_count": 0,
        "protected_contract_pass": True,
        "R10_conditional_protection_pass": True,
    }
    assert compiled["public"]["acceptance"]["S3_pass"] is False
    assert compiled["public"]["acceptance"][
        "independent_post_writer_review_pass"
    ] is False
