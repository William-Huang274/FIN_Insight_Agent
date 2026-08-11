from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

import pytest


pytestmark = pytest.mark.fast_contract

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.fin_0_1_2_s2_paired_model_canary import (
    Fin012S2PairedModelCanaryCompiler,
)
from test_fin_0_1_2_s2_paired_model_canary_compiler import _compiler


WWC_FAMILY = "what_would_change_atoms"


def _wwc_context(
    ticker: str = "MU",
) -> tuple[Fin012S2PairedModelCanaryCompiler, Any, Any]:
    compiler = _compiler(ticker)
    call = next(
        row
        for row in compiler.compile_primary_calls()
        if row.family_id == WWC_FAMILY
        and row.candidate.candidate_id == "pro_preview"
    )
    atom_compiler = compiler._compilers[WWC_FAMILY]
    return compiler, call, atom_compiler


def _response(
    compiler: Fin012S2PairedModelCanaryCompiler,
    call: Any,
    atoms: list[dict[str, Any]],
) -> dict[str, Any]:
    response = compiler.fake_provider_response(call)
    response["content"] = json.dumps(
        {"what_would_change_atoms": atoms},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return response


def _base_atoms(
    compiler: Fin012S2PairedModelCanaryCompiler,
    call: Any,
) -> list[dict[str, Any]]:
    return json.loads(compiler.fake_provider_response(call)["content"])[
        "what_would_change_atoms"
    ]


def test_one_declarative_date_rule_is_visible_to_all_contract_consumers() -> None:
    compiler, call, atom_compiler = _wwc_context()
    visible = atom_compiler.model_visible_contract(call.segment_id)
    rule = atom_compiler.review_date_alias_binding_contract()
    schema = compiler.provider_wire_schema(WWC_FAMILY)
    instruction = atom_compiler.provider_system_instruction(call.segment_id)
    validator = atom_compiler.compiled_surface(call.segment_id)[
        "local_validator"
    ]

    assert visible["review_date_alias_binding_rule"] == rule
    assert validator["cross_field_invariants"] == [rule]
    assert rule["by_review_cadence"]["bound_date"] == (
        "allowed_non_NONE_date_alias"
    )
    assert all(
        mode == "NONE"
        for cadence, mode in rule["by_review_cadence"].items()
        if cadence != "bound_date"
    )
    description = schema["what_would_change_atoms"][0][
        "review_date_alias"
    ]
    assert "bound_date" in description and "otherwise" in description
    assert "review_date_alias_binding_rule" in instruction
    assert "every other review_cadence" in instruction


def test_flash_and_pro_receive_byte_identical_recompiled_wwc_requests() -> None:
    compiler = _compiler("MU")
    pair = [
        row
        for row in compiler.compile_primary_calls()
        if row.family_id == WWC_FAMILY
    ]

    assert len(pair) == 2
    assert pair[0].messages == pair[1].messages
    assert pair[0].model_visible_request_digest == (
        pair[1].model_visible_request_digest
    )
    assert pair[0].request_equivalence_digest == (
        pair[1].request_equivalence_digest
    )
    assert pair[0].model_visible_request_digest != (
        "6f4592534ab20302c966be77b5a665eabfeed2f65f9e0aa0226a512ee4490b46"
    )


def test_date_positive_matrix_covers_every_alias_and_relative_cadence() -> None:
    compiler, call, atom_compiler = _wwc_context()
    base = _base_atoms(compiler, call)[0]
    policy = atom_compiler._wwc_policy()

    for date_alias, iso_date in policy.alias_to_iso_date.items():
        atom = {**base, "review_cadence": "bound_date", "review_date_alias": date_alias}
        outcome = compiler.materialize_response(
            call,
            _response(compiler, call, [atom]),
        )
        assert outcome["status"] == "pass"
        assert outcome["assembled"]["what_would_change"][0]["time_window"][
            "deadline_or_review_date"
        ] == iso_date

    for cadence in atom_compiler.review_cadences:
        if cadence == "bound_date":
            continue
        atom = {**base, "review_cadence": cadence, "review_date_alias": "NONE"}
        outcome = compiler.materialize_response(
            call,
            _response(compiler, call, [atom]),
        )
        assert outcome["status"] == "pass"


@pytest.mark.parametrize(
    ("cadence", "alias_mode", "expected_code"),
    (
        ("bound_date", "NONE", "s4_compiled_wwc_bound_date_alias_required"),
        (
            "next_reporting_event",
            "KNOWN",
            "s4_compiled_wwc_unbound_date_alias_forbidden",
        ),
        (
            "bound_date",
            "D-CROSS-CASE",
            "s4_compiled_wwc_date_alias_unknown_or_cross_case",
        ),
    ),
)
def test_date_negative_matrix_fails_typed_after_capture(
    cadence: str,
    alias_mode: str,
    expected_code: str,
) -> None:
    compiler, call, atom_compiler = _wwc_context()
    base = _base_atoms(compiler, call)[0]
    known_alias = next(iter(atom_compiler._wwc_policy().alias_to_iso_date))
    alias = known_alias if alias_mode == "KNOWN" else alias_mode
    atom = {**base, "review_cadence": cadence, "review_date_alias": alias}

    outcome = compiler.materialize_response(
        call,
        _response(compiler, call, [atom]),
    )

    assert outcome["status"] == "failed"
    assert outcome["terminal_result"]["code"] == expected_code
    assert outcome["terminal_result"]["phase"] == (
        "post_provider_local_semantic_validation"
    )
    assert outcome["capture"]["capture_before_local_validation"] is True
    assert outcome["capture"]["assistant_output_text"]


def _assert_task_claim_bindings(
    atom_compiler: Any,
    atoms: list[dict[str, Any]],
    assembled: dict[str, Any],
) -> None:
    policy = atom_compiler._wwc_policy()
    def source_key(value: Any) -> str:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    expected_by_source = {
        source_key(
            policy.alias_to_authority[
                str(atom["primary_authority_alias"])
            ].source_target()
        ): (
            policy.claim_policy.alias_to_claim_id[str(atom["claim_alias"])]
        )
        for atom in atoms
    }
    for task in assembled["what_would_change"]:
        assert task["claim_id"] == expected_by_source[
            source_key(task["source_target"])
        ]


def test_claim_binding_is_row_local_for_one_claim_multi_claim_and_truncation() -> None:
    compiler, call, atom_compiler = _wwc_context()
    base = _base_atoms(compiler, call)
    policy = atom_compiler._wwc_policy()
    claim_aliases = [row.alias for row in policy.claim_policy.alias_rows]
    authority_aliases = [row.alias for row in policy.authority_aliases]
    assert len(claim_aliases) >= 2 and len(authority_aliases) >= 6

    one = deepcopy(base[0])
    one["claim_alias"] = claim_aliases[1]
    one["primary_authority_alias"] = authority_aliases[0]
    one["authority_aliases"] = [authority_aliases[0]]
    one_result = compiler.materialize_response(
        call,
        _response(compiler, call, [one]),
    )
    assert one_result["status"] == "pass"
    _assert_task_claim_bindings(atom_compiler, [one], one_result["assembled"])

    six = deepcopy(base)
    multi_claim_pattern = [
        claim_aliases[0],
        claim_aliases[1],
        claim_aliases[1],
        claim_aliases[0],
        claim_aliases[1],
        claim_aliases[1],
    ]
    for ordinal, atom in enumerate(six):
        atom["claim_alias"] = multi_claim_pattern[ordinal]
        atom["primary_authority_alias"] = authority_aliases[ordinal]
        atom["authority_aliases"] = [authority_aliases[ordinal]]
    result = compiler.materialize_response(
        call,
        _response(compiler, call, six),
    )
    assert result["status"] == "pass"
    assert len(result["assembled"]["what_would_change"]) == 3
    _assert_task_claim_bindings(atom_compiler, six, result["assembled"])
    assert len({task["claim_id"] for task in result["assembled"]["what_would_change"]}) >= 2


def test_provider_permutation_does_not_change_selection_or_claim_binding() -> None:
    compiler, call, atom_compiler = _wwc_context()
    atoms = _base_atoms(compiler, call)
    policy = atom_compiler._wwc_policy()
    claim_aliases = [row.alias for row in policy.claim_policy.alias_rows]
    authority_aliases = [row.alias for row in policy.authority_aliases]
    for ordinal, atom in enumerate(atoms):
        atom["claim_alias"] = claim_aliases[ordinal % 2]
        atom["primary_authority_alias"] = authority_aliases[ordinal]
        atom["authority_aliases"] = [authority_aliases[ordinal]]

    forward = compiler.materialize_response(
        call,
        _response(compiler, call, atoms),
    )
    reverse = compiler.materialize_response(
        call,
        _response(compiler, call, list(reversed(atoms))),
    )

    assert forward["status"] == reverse["status"] == "pass"
    assert forward["assembled"] == reverse["assembled"]
    _assert_task_claim_bindings(atom_compiler, atoms, forward["assembled"])


def test_sanitized_restricted_pro_shape_replay_no_longer_false_greens() -> None:
    compiler, call, atom_compiler = _wwc_context()
    atoms = [
        {
            "authority_aliases": ["A001", "A002", "A003"],
            "claim_alias": "Q001",
            "direction": "unknown",
            "expected_claim_transition": "no_change",
            "primary_authority_alias": "A001",
            "review_cadence": "next_quarter_end",
            "review_date_alias": "NONE",
            "start_date_alias": "D001",
            "trigger_code": "authority_confirmation",
        },
        {
            "authority_aliases": ["A004", "A005"],
            "claim_alias": "Q002",
            "direction": "challenges",
            "expected_claim_transition": "weaken",
            "primary_authority_alias": "A004",
            "review_cadence": "next_reporting_event",
            "review_date_alias": "NONE",
            "start_date_alias": "D002",
            "trigger_code": "authority_contradiction",
        },
        {
            "authority_aliases": ["A006", "A007", "A008", "A009"],
            "claim_alias": "Q001",
            "direction": "supports",
            "expected_claim_transition": "strengthen",
            "primary_authority_alias": "A006",
            "review_cadence": "bound_date",
            "review_date_alias": "D002",
            "start_date_alias": "D001",
            "trigger_code": "bounded_event_occurs",
        },
    ]

    outcome = compiler.materialize_response(
        call,
        _response(compiler, call, atoms),
    )

    assert outcome["status"] == "pass"
    _assert_task_claim_bindings(atom_compiler, atoms, outcome["assembled"])
    assert {task["claim_id"] for task in outcome["assembled"]["what_would_change"]} == {
        "demand_authenticity_and_sustainability:local_claim:001",
        "demand_authenticity_and_sustainability:local_claim:002",
    }


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_full_fake_preserves_local_truth_and_audit_chain(ticker: str) -> None:
    compiler = _compiler(ticker)
    outcomes = compiler.run_fake_matrix()

    assert [row["status"] for row in outcomes] == ["pass"] * 6
    for outcome in outcomes:
        capture = outcome["capture"]
        raw = json.loads(capture["assistant_output_text"])
        assert not {
            "program_cell_id",
            "case_ticker",
            "case_id",
            "case_version",
            "research_run_id",
            "attempt_id",
            "lineage",
        }.intersection(raw)
        assert outcome["assembled"]["program_cell_id"] == (
            compiler.program_cell_id
        )
        assert capture["runtime_contract_family_binding"]["binding_ref"].endswith(
            ":v1.2"
        )
        terminal = outcome["terminal_result"]
        assert terminal["request_capture_ref"] == capture["request_capture_ref"]
        assert terminal["assistant_output_capture_ref"] == (
            capture["assistant_output_capture_ref"]
        )
        assert terminal["terminal_result_ref"]

    wwc = next(
        row
        for row in outcomes
        if row["capture"]["family_id"] == WWC_FAMILY
    )
    local_dates = set(
        compiler._compilers[WWC_FAMILY]._wwc_policy().alias_to_iso_date.values()
    )
    deadlines = {
        task["time_window"]["deadline_or_review_date"]
        for task in wwc["assembled"]["what_would_change"]
    }
    assert deadlines.intersection(local_dates)
