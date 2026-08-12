from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.ranking_comparison import RANKING_QREL_SCHEMA_VERSION  # noqa: E402


POLICY_SCHEMA = "fin_ia_s1c_ranking_comparison_policy_v1_0"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _records(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("s1c_record_not_object")
                rows.append(value)
    return rows


def materialize(policy: Mapping[str, Any]) -> dict[str, Any]:
    if policy.get("schema_version") != POLICY_SCHEMA:
        raise ValueError("s1c_policy_schema_invalid")
    inputs = policy.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError("s1c_policy_inputs_invalid")
    tier_equivalence = policy.get("source_tier_equivalence")
    if not isinstance(tier_equivalence, Mapping):
        raise ValueError("s1c_source_tier_equivalence_missing")
    official_source_tiers = [
        str(value)
        for value in tier_equivalence.get("official_filing_or_company_disclosure")
        or ()
    ]
    if not official_source_tiers:
        raise ValueError("s1c_source_tier_equivalence_invalid")
    bound: dict[str, dict[str, Any]] = {}
    for key in (
        "current_records",
        "current_object_result",
        "source_qrels",
        "source_owner_acceptance",
        "source_query_contract",
    ):
        path = _resolve(str(inputs[f"{key}_ref"]))
        observed = _sha256(path)
        expected = str(inputs[f"{key}_sha256"]).lower()
        if observed != expected:
            raise ValueError(f"s1c_input_digest_drift:{key}")
        bound[key] = {
            "ref": path.relative_to(ROOT).as_posix(),
            "sha256": observed,
        }

    qrel_packet = _read_json(_resolve(str(inputs["source_qrels_ref"])))
    acceptance = _read_json(_resolve(str(inputs["source_owner_acceptance_ref"])))
    query_contract = _read_json(_resolve(str(inputs["source_query_contract_ref"])))
    if not (
        acceptance.get("status")
        == "owner_accepted_research_qrels_v1_3_ranking_entry_eligible"
        and acceptance.get("owner_decision", {}).get("accepted_qrel_count") == 18
        and acceptance.get("owner_decision", {}).get("ranking_entry_eligible") is True
    ):
        raise ValueError("s1c_owner_qrel_acceptance_missing")
    accepted = set(
        acceptance.get("source_qrels", {}).get("accepted_qrel_digests") or ()
    )
    source_qrels = qrel_packet.get("qrels")
    if not isinstance(source_qrels, list) or len(source_qrels) != 18:
        raise ValueError("s1c_source_qrel_count_invalid")
    if {str(row.get("qrel_digest") or "") for row in source_qrels} != accepted:
        raise ValueError("s1c_owner_accepted_qrel_set_drift")

    requests: dict[tuple[str, str], Mapping[str, Any]] = {}
    for request in query_contract.get("requests") or ():
        if not isinstance(request, Mapping):
            continue
        key = (str(request.get("bundle_id") or ""), str(request.get("route_id") or ""))
        requests[key] = request

    rows = _records(_resolve(str(inputs["current_records_ref"])))
    equivalent: dict[str, list[str]] = {}
    for record in rows:
        current_id = str(record.get("evidence_id") or "")
        identities = {current_id}
        metadata = record.get("metadata")
        if isinstance(metadata, Mapping):
            aliases = metadata.get("legacy_source_record_ids")
            if isinstance(aliases, list):
                identities.update(str(value) for value in aliases)
        for identity in identities:
            if identity:
                equivalent.setdefault(identity, []).append(current_id)

    output_rows: list[dict[str, Any]] = []
    typed_gaps: list[dict[str, Any]] = []
    for index, source in enumerate(source_qrels, start=1):
        bundle_id = str(source["bundle_id"])
        sparse = requests.get((bundle_id, "internal_bm25"))
        dense = requests.get((bundle_id, "internal_milvus_dense"))
        if sparse is None or dense is None:
            raise ValueError(f"s1c_query_route_missing:{bundle_id}")
        selected = source.get("selected_candidate")
        if not isinstance(selected, Mapping):
            raise ValueError("s1c_selected_candidate_invalid")
        legacy_target = str(selected.get("source_key") or "")
        current_targets = sorted(set(equivalent.get(legacy_target) or ()))
        mapping_state = (
            "mapped_current_child" if current_targets else "typed_target_gap"
        )
        if not current_targets:
            typed_gaps.append(
                {
                    "gap_code": "owner_qrel_target_not_in_current_object_store",
                    "source_qrel_digest": str(source["qrel_digest"]),
                    "case_key": str(source["case_key"]),
                    "legacy_target_id": legacy_target,
                    "disposition": (
                        "Retain the qrel in the all-label denominator, exclude it from "
                        "mapped-target MRR, and transfer target requalification to S1-D."
                    ),
                }
            )
        typed_filters = sparse.get("typed_filters")
        if not isinstance(typed_filters, Mapping):
            raise ValueError("s1c_sparse_filter_invalid")
        sparse_texts = [str(value) for value in sparse.get("query_texts") or ()]
        semantic_texts = [str(value) for value in dense.get("query_texts") or ()]
        all_query_text = "\n".join([*sparse_texts, *semantic_texts]).casefold()
        if legacy_target.casefold() in all_query_text or any(
            target.casefold() in all_query_text for target in current_targets
        ):
            raise ValueError("s1c_gold_target_leaked_into_query")
        output_rows.append(
            {
                "qrel_id": f"s1c_qrel_{index:02d}",
                "source_qrel_digest": str(source["qrel_digest"]),
                "case_key": str(source["case_key"]).upper(),
                "subject_ticker": str(typed_filters["subject_ticker"]).upper(),
                "evidence_slot_id": str(source["evidence_slot_id"]),
                "evidence_owner_ticker": str(
                    source["evidence_owner_ticker"]
                ).upper(),
                "relationship_direction": str(
                    typed_filters["relationship_direction"]
                ),
                "sparse_query_texts": sparse_texts,
                "semantic_query_texts": semantic_texts,
                "publication_date_lte": str(
                    typed_filters["publication_date_on_or_before"]
                ),
                "reporting_fiscal_years": [
                    int(value)
                    for value in typed_filters.get("reporting_fiscal_years") or ()
                ],
                "form_types": [
                    str(value).upper()
                    for value in typed_filters.get("form_types") or ()
                ],
                "source_tiers": sorted(
                    set(
                        str(value)
                        for value in typed_filters.get("source_tiers") or ()
                    )
                    | set(official_source_tiers)
                ),
                "legacy_target_id": legacy_target,
                "target_current_source_record_ids": current_targets,
                "target_mapping_state": mapping_state,
                "relevance_grade": int(source["proposed_relevance"]),
                "label_authority": (
                    "Owner-accepted relevance qrel v1.3; current child identity is a "
                    "deterministic lineage requalification and remains evaluation-only."
                ),
            }
        )

    unsigned = {
        "schema_version": RANKING_QREL_SCHEMA_VERSION,
        "status": (
            "owner_qrels_requalified_with_typed_target_gap"
            if typed_gaps
            else "owner_qrels_requalified_to_current_children"
        ),
        "recorded_at": "2026-08-12",
        "scope": "FIN_0_1_3_S1C_SAME_OBJECT_RANKING_LABELS",
        "policy": {
            "labels_joined_after_candidate_generation": True,
            "target_ids_forbidden_from_query_text": True,
            "candidate_is_not_evidence": True,
            "owner_acceptance_not_evidence_promotion": True,
            "current_identity_requalification_not_new_owner_review": True,
        },
        "bound_inputs": bound,
        "summary": {
            "qrel_count": len(output_rows),
            "mapped_current_target_count": sum(
                row["target_mapping_state"] == "mapped_current_child"
                for row in output_rows
            ),
            "typed_target_gap_count": len(typed_gaps),
            "same_current_object_population_records": len(rows),
        },
        "qrels": output_rows,
        "typed_gaps": typed_gaps,
        "known_boundary": (
            "The 18 relevance judgments were previously accepted by the Owner for "
            "ranking entry only. This successor maps their target identities onto the "
            "current S1-B child store without changing relevance grades. One unmapped "
            "target remains a typed gap. No row is Evidence and no ranking route has "
            "been accepted by this artifact."
        ),
    }
    return {**unsigned, "qrel_manifest_digest": canonical_digest(unsigned)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Requalify Owner-accepted S1 labels onto the current S1-B child store."
    )
    parser.add_argument(
        "--policy",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_ranking_comparison_policy_v1_0.json"
        ),
    )
    parser.add_argument(
        "--output",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_requalified_qrels_v1_0.json"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy = _read_json(_resolve(args.policy))
    result = materialize(policy)
    output = _resolve(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(output)
    print(
        json.dumps(
            {
                "status": result["status"],
                **result["summary"],
                "qrel_manifest_digest": result["qrel_manifest_digest"],
                "output": output.relative_to(ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
