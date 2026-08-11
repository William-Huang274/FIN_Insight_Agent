from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
from typing import Any, Mapping


PACKET_ID = "FIN-0.1.2-S2-T04-IDENTITY-SEALED-BLIND-ASSESSMENT-PACKET-R1"
DEFAULT_OUTPUT_ROOT = Path(".codex_runtime/fin012-s2-t04-blind-assessment-r1")
LABELS = ("candidate_A", "candidate_B")

CAPTURES: tuple[dict[str, str], ...] = (
    {
        "family_id": "specialist_fact_atoms",
        "candidate_id": "flash_stable",
        "sha256": "78c8716e726011d85101b846e149479de9753ba35d0efa3a2965fa08af4c6a77",
        "ref": ".codex_runtime/fin012-s2-t03-mu-flash-pro-paired-r1/restricted-audit-objects/fin012/s2/t03/provider-interaction-captures/78/c8/78c8716e726011d85101b846e149479de9753ba35d0efa3a2965fa08af4c6a77.json",
    },
    {
        "family_id": "specialist_fact_atoms",
        "candidate_id": "pro_preview",
        "sha256": "ba2ea774015b87ec1d8e332187ac1e619bb70ba459feb5a29c80efb6f260725e",
        "ref": ".codex_runtime/fin012-s2-t03-mu-flash-pro-paired-r1/restricted-audit-objects/fin012/s2/t03/provider-interaction-captures/ba/2e/ba2ea774015b87ec1d8e332187ac1e619bb70ba459feb5a29c80efb6f260725e.json",
    },
    {
        "family_id": "claim_candidate_atoms",
        "candidate_id": "flash_stable",
        "sha256": "b83f8abf176ce8fd308b6a5b77343588b4d39848fd160964b9f836034a93ec5f",
        "ref": ".codex_runtime/fin012-s2-t03-mu-flash-pro-paired-r1/restricted-audit-objects/fin012/s2/t03/provider-interaction-captures/b8/3f/b83f8abf176ce8fd308b6a5b77343588b4d39848fd160964b9f836034a93ec5f.json",
    },
    {
        "family_id": "claim_candidate_atoms",
        "candidate_id": "pro_preview",
        "sha256": "581b69e31ee9e551b56296dcd02a20e31164594426c6b05594307c2a05c85b36",
        "ref": ".codex_runtime/fin012-s2-t03-mu-flash-pro-paired-r1/restricted-audit-objects/fin012/s2/t03/provider-interaction-captures/58/1b/581b69e31ee9e551b56296dcd02a20e31164594426c6b05594307c2a05c85b36.json",
    },
    {
        "family_id": "what_would_change_atoms",
        "candidate_id": "flash_stable",
        "sha256": "782520cb0279b8bc77fa095bdda77ff1d199a72ac0bcbc30fb4492808877a910",
        "ref": ".codex_runtime/fin012-s2-t03-mu-wwc-v12-replacement-pair-r1/restricted-audit-objects/fin012/s2/t03/wwc-v12-replacement/provider-interaction-captures/78/25/782520cb0279b8bc77fa095bdda77ff1d199a72ac0bcbc30fb4492808877a910.json",
    },
    {
        "family_id": "what_would_change_atoms",
        "candidate_id": "pro_preview",
        "sha256": "cf48a922ad083af2a8676ae07209beb255fafaa221fbc92e6b529970b9acb60d",
        "ref": ".codex_runtime/fin012-s2-t03-mu-wwc-v12-replacement-pair-r1/restricted-audit-objects/fin012/s2/t03/wwc-v12-replacement/provider-interaction-captures/cf/48/cf48a922ad083af2a8676ae07209beb255fafaa221fbc92e6b529970b9acb60d.json",
    },
)

RUBRIC = {
    "score_range_each_dimension": [0, 2],
    "dimensions": {
        "evidence_selection_relevance": {
            "0": "irrelevant, redundant, or too broad to discriminate",
            "1": "partly relevant but mixed, generic, or incomplete",
            "2": "precise, discriminative evidence for the case and family",
        },
        "epistemic_discipline": {
            "0": "overclaims, conflicts with evidence, or hides uncertainty",
            "1": "generally bounded but generic or incompletely calibrated",
            "2": "calibrated to support, counterevidence, and known limits",
        },
        "decision_usefulness": {
            "0": "no actionable distinction, trigger, transition, or watch condition",
            "1": "usable but incomplete, ambiguous, or weakly timed",
            "2": "specific discriminative trigger, transition, or watch condition",
        },
        "concise_information_density": {
            "0": "repetitive or low-yield atoms",
            "1": "adequate signal-to-redundancy",
            "2": "compact high-yield atoms without material duplication",
        },
    },
    "density_note": "Score signal and redundancy per atom, not prose elegance.",
    "date_note": (
        "A bound review date at or before as_of_date is a decision-usefulness "
        "finding, not a hard-integrity failure."
    ),
}


class BlindPacketError(RuntimeError):
    pass


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_capture(root: Path, spec: Mapping[str, str]) -> dict[str, Any]:
    path = root / spec["ref"]
    if not path.is_file():
        raise BlindPacketError(f"missing_capture:{spec['sha256']}")
    raw = path.read_bytes()
    if _sha256_bytes(raw) != spec["sha256"]:
        raise BlindPacketError(f"capture_digest_mismatch:{spec['sha256']}")
    capture = json.loads(raw.decode("utf-8"))
    if capture.get("family_id") != spec["family_id"]:
        raise BlindPacketError(f"capture_family_mismatch:{spec['sha256']}")
    if capture.get("candidate_id") != spec["candidate_id"]:
        raise BlindPacketError(f"capture_candidate_mismatch:{spec['sha256']}")
    if capture.get("capture_before_local_validation") is not True:
        raise BlindPacketError(f"capture_not_prevalidation:{spec['sha256']}")
    if capture.get("credentials_included") is not False:
        raise BlindPacketError(f"capture_contains_credentials:{spec['sha256']}")
    if capture.get("private_reasoning_included") is not False:
        raise BlindPacketError(f"capture_contains_private_reasoning:{spec['sha256']}")
    return capture


def _user_payload(capture: Mapping[str, Any]) -> dict[str, Any]:
    messages = capture.get("model_visible_request")
    if not isinstance(messages, list):
        raise BlindPacketError("model_visible_request_missing")
    users = [row for row in messages if row.get("role") == "user"]
    if len(users) != 1:
        raise BlindPacketError("exactly_one_user_message_required")
    return json.loads(users[0]["content"])


def _family_context(family_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    contract = payload["compiled_judgment_atom_contract"]
    common = {
        "required_output_schema": payload["required_output_schema"],
        "local_selected_maximum": contract["local_selected_maximum"],
    }
    if family_id == "specialist_fact_atoms":
        return {
            **common,
            "allowed_supports": contract["allowed_supports"],
            "causal_relations": contract["causal_relations"],
            "confidences": contract["confidences"],
            "materialities": contract["materialities"],
            "priorities": contract["priorities"],
            "terminal_classes": contract["terminal_classes"],
        }
    if family_id == "claim_candidate_atoms":
        allowed_facts = contract["allowed_facts"]
        if isinstance(allowed_facts, dict):
            allowed_facts = [allowed_facts]
        return {
            **common,
            "allowed_facts": allowed_facts,
            "claim_kind_support_role_rules": contract[
                "claim_kind_support_role_rules"
            ],
            "claim_kinds": contract["claim_kinds"],
            "directions": contract["directions"],
            "confidences": contract["confidences"],
            "materialities": contract["materialities"],
            "priorities": contract["priorities"],
        }
    if family_id == "what_would_change_atoms":
        return {
            **common,
            "allowed_claims": contract["allowed_claims"],
            "allowed_authorities": contract["allowed_authorities"],
            "allowed_date_aliases": contract["allowed_date_aliases"],
            "directions": contract["directions"],
            "expected_transitions": contract["expected_transitions"],
            "review_cadences": contract["review_cadences"],
            "review_date_alias_binding_rule": contract[
                "review_date_alias_binding_rule"
            ],
            "trigger_codes": contract["trigger_codes"],
        }
    raise BlindPacketError(f"unknown_family:{family_id}")


def _assert_pair_request_equivalence(pair: list[dict[str, Any]]) -> None:
    if len(pair) != 2:
        raise BlindPacketError("exactly_two_candidates_per_family_required")
    left = pair[0]["model_visible_request"]
    right = pair[1]["model_visible_request"]
    if _canonical_bytes(left) != _canonical_bytes(right):
        raise BlindPacketError(f"paired_request_drift:{pair[0]['family_id']}")


def _walk(value: Any, *, keys: list[str], strings: list[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            keys.append(str(key))
            _walk(item, keys=keys, strings=strings)
    elif isinstance(value, list):
        for item in value:
            _walk(item, keys=keys, strings=strings)
    elif isinstance(value, str):
        strings.append(value)


def assert_no_identity_leak(packet: Mapping[str, Any]) -> None:
    keys: list[str] = []
    strings: list[str] = []
    _walk(packet, keys=keys, strings=strings)
    forbidden_keys = {
        "candidate_id",
        "model",
        "model_ref",
        "call_id",
        "finish_reason",
        "latency_ms",
        "usage",
        "provider",
        "capture_sha256",
        "terminal_sha256",
        "source_path",
    }
    leaked_keys = sorted(set(keys) & forbidden_keys)
    if leaked_keys:
        raise BlindPacketError(f"identity_leak_keys:{','.join(leaked_keys)}")
    forbidden_fragments = {
        "deepseek",
        "flash_stable",
        "pro_preview",
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        *(spec["sha256"] for spec in CAPTURES),
        *(spec["ref"].replace("\\", "/") for spec in CAPTURES),
    }
    corpus = "\n".join(strings).lower()
    leaked_fragments = sorted(
        fragment for fragment in forbidden_fragments if fragment.lower() in corpus
    )
    if leaked_fragments:
        raise BlindPacketError(
            "identity_leak_fragments:" + ",".join(leaked_fragments)
        )


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def build_packet(
    repository_root: Path,
    output_root: Path,
    *,
    mapping_bit: int | None = None,
    nonce_hex: str | None = None,
) -> dict[str, Any]:
    repository_root = repository_root.resolve()
    output_root = output_root.resolve()
    packet_path = output_root / "assessor-packet.json"
    manifest_path = output_root / "packet-manifest.json"
    if packet_path.exists() or manifest_path.exists():
        raise BlindPacketError("assessment_packet_identity_already_claimed")

    captures = [_load_capture(repository_root, spec) for spec in CAPTURES]
    by_family: dict[str, list[dict[str, Any]]] = {}
    for capture in captures:
        by_family.setdefault(capture["family_id"], []).append(capture)
    if sorted(by_family) != [
        "claim_candidate_atoms",
        "specialist_fact_atoms",
        "what_would_change_atoms",
    ]:
        raise BlindPacketError("exact_three_family_set_required")
    for pair in by_family.values():
        _assert_pair_request_equivalence(pair)

    if mapping_bit is None:
        mapping_bit = secrets.randbits(1)
    if mapping_bit not in (0, 1):
        raise BlindPacketError("mapping_bit_must_be_zero_or_one")
    ordered_candidates = ("flash_stable", "pro_preview")
    if mapping_bit:
        ordered_candidates = tuple(reversed(ordered_candidates))
    label_to_candidate = dict(zip(LABELS, ordered_candidates, strict=True))
    candidate_to_label = {value: key for key, value in label_to_candidate.items()}
    nonce_hex = nonce_hex or secrets.token_hex(32)
    if len(nonce_hex) < 64:
        raise BlindPacketError("mapping_nonce_must_have_at_least_256_bits")

    mapping = {
        "schema_version": "fin_ia_0_1_2_s2_t04_sealed_mapping_v1_0",
        "packet_id": PACKET_ID,
        "nonce_hex": nonce_hex,
        "label_to_candidate": label_to_candidate,
        "candidate_to_label": candidate_to_label,
    }
    mapping_raw = _canonical_bytes(mapping)
    mapping_sha = _sha256_bytes(mapping_raw)
    mapping_path = (
        output_root
        / "restricted-mapping-objects"
        / mapping_sha[:2]
        / mapping_sha[2:4]
        / f"{mapping_sha}.json"
    )

    family_rows: list[dict[str, Any]] = []
    for family_id in (
        "specialist_fact_atoms",
        "claim_candidate_atoms",
        "what_would_change_atoms",
    ):
        pair = by_family[family_id]
        context_payload = _user_payload(pair[0])
        outputs = []
        for capture in pair:
            outputs.append(
                {
                    "label": candidate_to_label[capture["candidate_id"]],
                    "output": json.loads(capture["assistant_output_text"]),
                }
            )
        outputs.sort(key=lambda row: row["label"])
        family_rows.append(
            {
                "family_id": family_id,
                "evaluation_context": _family_context(family_id, context_payload),
                "candidate_outputs": outputs,
            }
        )

    packet = {
        "schema_version": "fin_ia_0_1_2_s2_t04_blind_assessment_packet_v1_0",
        "packet_id": PACKET_ID,
        "mapping_commitment": f"sha256:{mapping_sha}",
        "assessment_context": {
            "case": "Micron Technology (MU)",
            "program_cell": "demand authenticity and sustainability",
            "as_of_date": "2026-07-26",
            "hard_integrity_status": "all six presented outputs already passed",
            "assessment_scope": (
                "Score only comparative analytical quality. Do not rescore syntax, "
                "transport, or hard integrity."
            ),
        },
        "assessor_independence_attestation": {
            "must_not_access_other_repository_or_runtime_files": True,
            "must_not_attempt_to_identify_the_generating_system": True,
            "must_score_only_from_this_packet": True,
        },
        "rubric": RUBRIC,
        "required_score_record": {
            "schema_version": "fin_ia_0_1_2_s2_t04_independent_score_record_v1_0",
            "packet_id": PACKET_ID,
            "mapping_commitment": f"sha256:{mapping_sha}",
            "assessor_attestation": {
                "fresh_context_without_mapping_or_prior_observations": True,
                "read_only_this_packet": True,
                "did_not_guess_or_seek_identity": True,
            },
            "family_scores": [
                {
                    "family_id": "exact family_id from packet",
                    "candidate_scores": [
                        {
                            "label": "candidate_A or candidate_B",
                            "dimension_scores": {
                                "evidence_selection_relevance": "integer 0..2",
                                "epistemic_discipline": "integer 0..2",
                                "decision_usefulness": "integer 0..2",
                                "concise_information_density": "integer 0..2",
                            },
                            "family_total": "integer sum 0..8",
                            "evidence": [
                                "concise family-row or alias-grounded reason"
                            ],
                        }
                    ],
                }
            ],
            "candidate_totals": {
                "candidate_A": "integer sum 0..24",
                "candidate_B": "integer sum 0..24",
            },
            "comparative_summary": "concise identity-free assessment",
        },
        "families": family_rows,
    }
    assert_no_identity_leak(packet)

    packet_raw = _canonical_bytes(packet)
    packet_sha = _sha256_bytes(packet_raw)
    manifest = {
        "schema_version": "fin_ia_0_1_2_s2_t04_blind_packet_manifest_v1_0",
        "packet_id": PACKET_ID,
        "packet_ref": str(packet_path),
        "packet_sha256": packet_sha,
        "mapping_commitment": f"sha256:{mapping_sha}",
        "restricted_mapping_ref": str(mapping_path),
        "selected_capture_count": 6,
        "family_count": 3,
        "identity_leak_preflight": "pass",
        "model_provider_network_calls": [0, 0, 0],
        "business_artifact_writes": 0,
    }
    _atomic_write(mapping_path, mapping_raw)
    _atomic_write(packet_path, packet_raw)
    _atomic_write(manifest_path, _canonical_bytes(manifest))

    if _sha256_bytes(packet_path.read_bytes()) != packet_sha:
        raise BlindPacketError("packet_readback_digest_mismatch")
    if _sha256_bytes(mapping_path.read_bytes()) != mapping_sha:
        raise BlindPacketError("mapping_readback_digest_mismatch")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    output_root = args.output_root
    if not output_root.is_absolute():
        output_root = args.repository_root / output_root
    manifest = build_packet(args.repository_root, output_root)
    print(
        json.dumps(
            {
                "status": "pass_identity_sealed_packet_materialized",
                "packet_id": manifest["packet_id"],
                "packet_ref": manifest["packet_ref"],
                "packet_sha256": manifest["packet_sha256"],
                "mapping_commitment": manifest["mapping_commitment"],
                "identity_leak_preflight": manifest["identity_leak_preflight"],
                "selected_capture_count": manifest["selected_capture_count"],
                "family_count": manifest["family_count"],
                "model_provider_network_calls": manifest[
                    "model_provider_network_calls"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
