from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.project_os_preflight import run_project_os_preflight  # noqa: E402


DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_post_tencent_provider_portfolio_and_production_search_boundary_decision_v1_0.json"
FIRECRAWL_SCORING_PATH = ROOT / "configs/eval/fin_ia_0_1_3_s1_08_firecrawl_relationship_aware_semantic_control_scoring_v1_0.json"
TENCENT_SCORING_PATH = ROOT / "configs/eval/fin_ia_0_1_3_s1_08_tencent_relationship_aware_semantic_comparator_scoring_v1_0.json"
COMPLETED_SCOPE = (
    "S1_08_POST_TENCENT_SAME_MATRIX_PROVIDER_PORTFOLIO_AND_PRODUCTION_SEARCH_BOUNDARY_DECISION"
)
NEXT_SCOPE = (
    "S1_08_OFFICIAL_FIRST_SOURCEHUNTER_PORTFOLIO_AND_DISCOVERY_SHADOW_ZERO_CALL_IMPLEMENTATION"
)
CLEAN_PROOF_SCOPE = (
    "S1_08_OFFICIAL_FIRST_PORTFOLIO_CLEAN_INDEPENDENT_ZERO_CALL_PROOF"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_decision_is_digest_bound_and_does_not_rewrite_history() -> None:
    decision = _load(DECISION_PATH)
    body = dict(decision)
    supplied = body.pop("decision_digest")
    assert supplied == canonical_digest(body)
    assert decision["status"] == (
        "official_first_portfolio_selected_discovery_only_firecrawl_shadow_implementation_pending"
    )
    assert decision["supersession"][
        "historical_results_and_assessments_remain_immutable"
    ] is True
    assert decision["supersession"][
        "historical_scoring_contracts_remain_valid_for_their_declared_experiments"
    ] is True
    assert _sha256(FIRECRAWL_SCORING_PATH) == (
        "81fe9359f1167c55105972408d7a7b4e1f366f56193253f823cabfe4ceaba1c8"
    )
    assert _sha256(TENCENT_SCORING_PATH) == (
        "dd6b2d279b73379257190dd494e33655d63cfbd47c12ad07a1d5089727e5c7f3"
    )


def test_portfolio_assigns_search_and_financial_authority_to_different_layers() -> None:
    decision = _load(DECISION_PATH)
    portfolio = decision["selected_portfolio"]
    semantic = portfolio["semantic_open_web_lane"]
    assert semantic["selected_provider"] == "firecrawl_keyless"
    assert semantic["provider_status"] == (
        "shadow_integration_candidate_not_production_qualified"
    )
    assert semantic["writer_citable"] is False
    assert semantic["evidence_promotion_allowed"] is False
    assert portfolio["domestic_broad_lane"]["tencent_wsa_searchpro_standard"] == (
        "diagnostic_only_not_selected_zero_of_six_primary_targets"
    )
    assert portfolio["domestic_broad_lane"][
        "additional_provider_purchase_or_live_test_authorized"
    ] is False
    assert portfolio["document_and_parser_lane"][
        "third_party_parser_or_provider_owns_financial_authority"
    ] is False
    assert portfolio["evidence_gate"]["role"] == "sole promotion authority"


def test_provider_date_is_telemetry_but_local_date_is_portfolio_hard_gate() -> None:
    decision = _load(DECISION_PATH)
    qualification = decision["role_specific_qualification"]
    assert "provider-reported publication date" in qualification[
        "locator_route_telemetry_not_authority"
    ]
    assert "local typed publication-date decision" in qualification[
        "portfolio_evidence_hard_checks"
    ]
    assert qualification["ranking_admitted_only_after_candidate_ceiling"] is True


def test_decision_is_zero_call_and_only_authorizes_next_implementation() -> None:
    decision = _load(DECISION_PATH)
    assert list(decision["observed_calls"].values()) == [0, 0, 0, 0, 0]
    assert decision["next_implementation"]["run_scope"] == NEXT_SCOPE
    assert decision["next_implementation"][
        "external_provider_network_model_document_calls"
    ] == [0, 0, 0, 0]
    assert decision["next_implementation"][
        "live_or_integration_authority_granted"
    ] is False


def test_completed_scopes_are_blocked_and_current_clean_proof_scope_is_allowed() -> None:
    completed = run_project_os_preflight(ROOT, run_scope=COMPLETED_SCOPE)
    assert completed["status"] == "blocked"
    assert completed["contract_errors"] == []
    implemented = run_project_os_preflight(ROOT, run_scope=NEXT_SCOPE)
    assert implemented["status"] == "blocked"
    assert implemented["contract_errors"] == []
    successor = run_project_os_preflight(ROOT, run_scope=CLEAN_PROOF_SCOPE)
    assert successor["status"] == "pass"
    assert successor["contract_errors"] == []
