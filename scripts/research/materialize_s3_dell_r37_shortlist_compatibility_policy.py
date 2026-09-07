from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.research.dynamic_single_unit_loop import (  # noqa: E402
    load_dynamic_single_unit_policy,
)


PREDECESSOR = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_5.json"
)
OUTPUT = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_s3_dell_dynamic_single_unit_loop_policy_v1_6.json"
)


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"r37_shortlist_policy_output_exists:{OUTPUT}")
    predecessor = json.loads(PREDECESSOR.read_text(encoding="utf-8"))
    if not isinstance(predecessor, dict):
        raise ValueError("r37_shortlist_policy_predecessor_invalid")
    value = deepcopy(predecessor)
    value["objective"]["objective_id"] = (
        "OBJ::DELL::DYNAMIC-VALUE-CAPTURE-R37-REVIEWED-PUBLIC-PDF-SHORTLIST"
    )
    value["authority"][
        "legacy_shortlist_alias_changes_candidate_features_only"
    ] = True
    value["authority"]["successor_facet_identity_preserved"] = True
    request_basis = value["token_budget_bases"]["request_planning"]
    request_basis["comparable_run_evidence"] = (
        "R37 R6 passed source-route, retrieval-need and material-policy "
        "compilation but failed when the legacy advisory shortlist role layer "
        "did not recognize bounded_price_configuration_context. The successor "
        "maps three bounded facets only to semantically equivalent predecessor "
        "facets for candidate feature scoring; source lineage, Evidence, "
        "NumericFact and public-gap authority are unchanged."
    )
    validated = load_dynamic_single_unit_policy(value)
    rendered = (
        json.dumps(validated, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    OUTPUT.write_bytes(rendered)
    print(OUTPUT.relative_to(ROOT).as_posix())
    print(hashlib.sha256(rendered).hexdigest())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
