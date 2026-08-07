from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.s1_08_candidate_generation_runtime import (
    DiscoveryCandidate,
    DiscoveryQuery,
    S108CandidateGenerationError,
    canonical_digest,
    compile_initial_queries,
    compile_revision,
    evaluator_only_gold_match,
    load_source_catalog,
    run_candidate_generation,
)
from sec_agent.s1_08_official_discovery_adapter import (
    CaptureFirstOfficialDiscoveryAdapter,
)
from sec_agent.official_source_attempt_program import SourceResponse


ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_s1_08_current_source_catalog_and_query_revision_policy_v1_0.json"
VISIBLE_PATH = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/model_visible/shared_benchmark_evidence_pack_v1.json"
HIDDEN_PATH = ROOT / "eval_sets/fin_0_1_3_same_evidence_v1/evaluator_only/hidden_gold_scoring_objects_v1.json"
PROOF_PATH = ROOT / "configs/releases/fin_ia_0_1_3_s1_08_candidate_generation_query_revision_and_gold_match_zero_call_proof_v1_0.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _capture(prefix: str) -> tuple[str, str]:
    return f"capture/{prefix}", canonical_digest({"capture": prefix})


def _entity_key(source: dict) -> str:
    publisher = str(source.get("publisher") or "")
    if "Dell" in publisher:
        return "DELL"
    if "Micron" in publisher:
        return "MU"
    if "NVIDIA" in publisher:
        return "NVDA"
    if "Microsoft" in publisher:
        return "MSFT"
    if "TSMC" in publisher:
        return "TSMC"
    return "DELL"


def _role_id(source: dict) -> str:
    source_id = str(source["source_id"])
    if "MARKET" in source_id:
        return "market_expectation_context"
    if "10K" in source_id or "10Q" in source_id:
        return "regulatory_risk_and_financial_reconciliation"
    if "MSFT" in source_id or "DELL_Q1_FY27_CALL" in source_id:
        return "customer_demand_and_deployment_validation"
    if "TSMC" in source_id or "MU_Q3_FY26_REMARKS" in source_id:
        return "supply_chain_capacity_and_counterevidence"
    return "issuer_results_and_management_commentary"


class _GoldBlindFakeDiscovery:
    def __init__(self, *, case_key: str, visible_pack: dict, delayed_role: str = "") -> None:
        self.case_key = case_key
        self.delayed_role = delayed_role
        source_map = {
            str(row["source_id"]): row for row in visible_pack["source_registry"]
        }
        case = next(row for row in visible_pack["cases"] if row["case_key"] == case_key)
        source_ids = sorted({str(row["source_id"]) for row in case["evidence_items"]})
        self.rows = [source_map[source_id] for source_id in source_ids]

    def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        if query.role_id == self.delayed_role and query.revision == 0:
            return ()
        rows = [row for row in self.rows if _role_id(row) == query.role_id]
        candidates: list[DiscoveryCandidate] = []
        for index, source in enumerate(rows):
            locator = str(source.get("url") or "current_market_snapshot")
            discovery_ref, discovery_digest = _capture(
                f"{self.case_key}/{query.target_key}/{query.revision}/{index}/discovery"
            )
            source_ref, source_digest = _capture(
                f"{self.case_key}/{query.target_key}/{query.revision}/{index}/source"
            )
            parser_ref, parser_digest = _capture(
                f"{self.case_key}/{query.target_key}/{query.revision}/{index}/parser"
            )
            candidates.append(
                DiscoveryCandidate(
                    case_key=self.case_key,
                    target_key=query.target_key,
                    role_id=query.role_id,
                    entity_key=_entity_key(source),
                    title=str(source["title"]),
                    locator=locator,
                    published_on=str(source["published_on"]),
                    authority=str(source["authority"]),
                    discovery_capture_ref=discovery_ref,
                    discovery_capture_digest=discovery_digest,
                    source_capture_ref=source_ref,
                    source_capture_digest=source_digest,
                    parser_capture_ref=parser_ref,
                    parser_capture_digest=parser_digest,
                )
            )
        return tuple(candidates)


class _MutationAdapter:
    def __init__(self, candidate: DiscoveryCandidate) -> None:
        self.candidate = candidate

    def discover(self, query: DiscoveryQuery) -> tuple[DiscoveryCandidate, ...]:
        return (self.candidate,) if query.revision == 0 else ()


def _objective(visible: dict, case_key: str) -> str:
    return str(next(row for row in visible["cases"] if row["case_key"] == case_key)["research_objective"])


def _three_case_results(*, delayed_role: str = "") -> tuple[dict, list[dict], dict, dict]:
    catalog = load_source_catalog(CATALOG_PATH)
    visible = _load(VISIBLE_PATH)
    hidden = _load(HIDDEN_PATH)
    results = [
        run_candidate_generation(
            catalog=catalog,
            case_key=case_key,
            research_objective=_objective(visible, case_key),
            adapter=_GoldBlindFakeDiscovery(
                case_key=case_key,
                visible_pack=visible,
                delayed_role=delayed_role,
            ),
        )
        for case_key in ("DELL", "MU", "NVDA")
    ]
    return catalog, results, visible, hidden


def test_catalog_is_gold_blind_and_compiles_provider_neutral_queries() -> None:
    catalog = load_source_catalog(CATALOG_PATH)
    visible = _load(VISIBLE_PATH)
    serialized = json.dumps(catalog, ensure_ascii=False)
    for source in visible["source_registry"]:
        if source.get("url"):
            assert source["url"] not in serialized
    assert "hidden_gold_scoring_objects" not in serialized
    queries = compile_initial_queries(
        catalog=catalog,
        case_key="NVDA",
        research_objective=_objective(visible, "NVDA"),
    )
    assert len(queries) == 5
    assert all(query.revision == 0 for query in queries)
    supply = next(
        row for row in queries if row.role_id == "supply_chain_capacity_and_counterevidence"
    )
    assert set(supply.entity_keys) == {"MU", "TSMC"}
    assert not any(prefix in json.dumps(row.as_dict()) for row in queries for prefix in ("SRC_", "NVDA_E", "NVDA_T"))


def test_three_case_full_fake_reaches_candidate_ceiling_before_ranking() -> None:
    _, results, visible, hidden = _three_case_results()
    evaluation = evaluator_only_gold_match(
        results=results,
        visible_pack=visible,
        hidden_scoring=hidden,
    )
    assert [row["case_key"] for row in results] == ["DELL", "MU", "NVDA"]
    assert all(row["observed_counts"]["model_calls"] == 0 for row in results)
    assert all(len(row["selected_candidates"]) <= 8 for row in results)
    assert evaluation["summary"] == {
        "target_groups": 12,
        "target_in_pool_recall": 1.0,
        "selected_pack_required_slot_coverage": 1.0,
        "ranking_metrics_admitted": True,
    }
    assert evaluation["planner_received_hidden_gold"] is False


def test_reasoned_query_revision_changes_terms_and_routes_without_retry() -> None:
    _, results, _, _ = _three_case_results(
        delayed_role="issuer_results_and_management_commentary"
    )
    for result in results:
        attempts = [
            row
            for row in result["attempts"]
            if row["query"]["role_id"] == "issuer_results_and_management_commentary"
        ]
        assert [row["query"]["revision"] for row in attempts] == [0, 1]
        assert attempts[0]["query"]["query_digest"] != attempts[1]["query"]["query_digest"]
        assert attempts[0]["query"]["query_text"] != attempts[1]["query"]["query_text"]
        assert "sec_submissions_discovery" in attempts[1]["query"]["route_ids"]
        assert attempts[1]["query"]["prior_reason"] == "no_qualified_candidate_for_required_role"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("cross_case", "cross_case_candidate"),
        ("future", "candidate_after_as_of"),
        ("lineage", "capture_first_lineage_invalid"),
        ("unpromoted", "candidate_not_evidence_promoted"),
    ],
)
def test_candidate_mutations_fail_closed(mutation: str, expected_code: str) -> None:
    catalog = load_source_catalog(CATALOG_PATH)
    visible = _load(VISIBLE_PATH)
    query = compile_initial_queries(
        catalog=catalog,
        case_key="DELL",
        research_objective=_objective(visible, "DELL"),
    )[0]
    ref, digest = _capture("mutation")
    base = DiscoveryCandidate(
        case_key="DELL",
        target_key=query.target_key,
        role_id=query.role_id,
        entity_key="DELL",
        title="Official current results",
        locator="https://investors.delltechnologies.com/example",
        published_on="2026-05-28",
        authority="issuer_primary",
        discovery_capture_ref=ref,
        discovery_capture_digest=digest,
        source_capture_ref=ref,
        source_capture_digest=digest,
        parser_capture_ref=ref,
        parser_capture_digest=digest,
    )
    values = base.as_dict()
    if mutation == "cross_case":
        values["case_key"] = "MU"
    elif mutation == "future":
        values["published_on"] = "2026-08-07"
    elif mutation == "lineage":
        values["parser_capture_digest"] = "bad"
    elif mutation == "unpromoted":
        values["promoted"] = False
    candidate = DiscoveryCandidate(**values)
    result = run_candidate_generation(
        catalog=catalog,
        case_key="DELL",
        research_objective=_objective(visible, "DELL"),
        adapter=_MutationAdapter(candidate),
    )
    codes = {
        code
        for row in result["rejected_candidates"]
        for code in row["reason_codes"]
    }
    assert expected_code in codes


def test_evaluator_only_match_detects_missing_source_without_leaking_target_ids() -> None:
    _, results, visible, hidden = _three_case_results()
    mutated = deepcopy(results)
    dell = mutated[0]
    removed = dell["accepted_candidates"].pop(0)
    dell["selected_candidates"] = [
        row for row in dell["selected_candidates"] if row["locator"] != removed["locator"]
    ]
    evaluation = evaluator_only_gold_match(
        results=mutated,
        visible_pack=visible,
        hidden_scoring=hidden,
    )
    assert evaluation["summary"]["target_in_pool_recall"] < 1.0
    serialized_results = json.dumps(results, ensure_ascii=False)
    assert not any(
        str(target["target_id"]) in serialized_results
        for case in hidden["cases"]
        for target in case["required_insights"]
    )


def test_gold_identifier_in_catalog_fails_closed(tmp_path: Path) -> None:
    catalog = _load(CATALOG_PATH)
    catalog["entities"][0]["aliases"].append("DELL_E01")
    path = tmp_path / "leaked.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    with pytest.raises(S108CandidateGenerationError) as exc:
        load_source_catalog(path)
    assert exc.value.code == "s1_08_gold_identifier_leaked_into_catalog"


def test_revision_budget_and_identical_reason_fail_closed() -> None:
    catalog = load_source_catalog(CATALOG_PATH)
    visible = _load(VISIBLE_PATH)
    initial = compile_initial_queries(
        catalog=catalog,
        case_key="DELL",
        research_objective=_objective(visible, "DELL"),
    )[0]
    first = compile_revision(catalog=catalog, prior=initial, reason="missing_role")
    second = compile_revision(catalog=catalog, prior=first, reason="missing_role_after_expansion")
    with pytest.raises(S108CandidateGenerationError) as exc:
        compile_revision(catalog=catalog, prior=second, reason="still_missing")
    assert exc.value.code == "s1_08_query_revision_budget_exceeded"
    with pytest.raises(S108CandidateGenerationError) as exc:
        compile_revision(catalog=catalog, prior=initial, reason="identical_retry")
    assert exc.value.code == "s1_08_query_revision_reason_invalid"


class _OfficialDiscoveryTransport:
    live_network = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, *, url: str, headers: dict, allowed_hosts: set[str], timeout_seconds: int, byte_ceiling: int) -> SourceResponse:
        self.calls.append(url)
        if url == "https://investors.delltechnologies.com/":
            body = (
                '<html><body><a data-date="2026-05-28" '
                'href="/news/results.html">latest quarterly financial results earnings call</a></body></html>'
            ).encode()
            content_type = "text/html"
        elif url == "https://data.sec.gov/submissions/CIK0001571996.json":
            body = json.dumps(
                {
                    "cik": "0001571996",
                    "filings": {
                        "recent": {
                            "accessionNumber": [],
                            "filingDate": [],
                            "form": [],
                            "primaryDocument": [],
                        }
                    },
                }
            ).encode()
            content_type = "application/json"
        elif url == "https://investors.delltechnologies.com/news/results.html":
            body = b"<html><body>Dell quarterly financial results revenue cash flow earnings.</body></html>"
            content_type = "text/html"
        else:
            raise AssertionError(f"unexpected URL: {url}")
        return SourceResponse(
            status_code=200,
            final_url=url,
            headers={"content-type": content_type},
            body=body,
        )


def test_concrete_official_adapter_captures_discovery_fetch_and_parse(tmp_path: Path) -> None:
    catalog = load_source_catalog(CATALOG_PATH)
    visible = _load(VISIBLE_PATH)
    query = next(
        row
        for row in compile_initial_queries(
            catalog=catalog,
            case_key="DELL",
            research_objective=_objective(visible, "DELL"),
        )
        if row.role_id == "issuer_results_and_management_commentary"
    )
    transport = _OfficialDiscoveryTransport()
    adapter = CaptureFirstOfficialDiscoveryAdapter(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=3,
        document_ceiling_per_query=1,
    )
    candidates = adapter.discover(query)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.locator.endswith("/news/results.html")
    assert candidate.published_on == "2026-05-28"
    assert candidate.authority == "issuer_primary"
    assert len(candidate.discovery_capture_digest) == 64
    assert len(candidate.source_capture_digest) == 64
    assert len(candidate.parser_capture_digest) == 64
    assert adapter.network_calls == 3
    assert len(transport.calls) == 3


def test_concrete_official_adapter_stops_at_network_ceiling(tmp_path: Path) -> None:
    catalog = load_source_catalog(CATALOG_PATH)
    visible = _load(VISIBLE_PATH)
    query = next(
        row
        for row in compile_initial_queries(
            catalog=catalog,
            case_key="DELL",
            research_objective=_objective(visible, "DELL"),
        )
        if row.role_id == "issuer_results_and_management_commentary"
    )
    transport = _OfficialDiscoveryTransport()
    adapter = CaptureFirstOfficialDiscoveryAdapter(
        catalog=catalog,
        case_key="DELL",
        runtime_root=tmp_path,
        transport=transport,
        network_call_ceiling=1,
        document_ceiling_per_query=1,
    )
    assert adapter.discover(query) == ()
    assert adapter.network_calls == 1
    assert any(row.get("code") == "discovery_network_call_ceiling_reached" for row in adapter.receipts)


def test_full_fake_is_deterministic() -> None:
    _, first, visible, hidden = _three_case_results()
    _, second, _, _ = _three_case_results()
    assert canonical_digest(first) == canonical_digest(second)
    first_eval = evaluator_only_gold_match(
        results=first, visible_pack=visible, hidden_scoring=hidden
    )
    second_eval = evaluator_only_gold_match(
        results=second, visible_pack=visible, hidden_scoring=hidden
    )
    assert first_eval == second_eval


def test_materialized_zero_call_proof_is_digest_bound_and_honest() -> None:
    proof = _load(PROOF_PATH)
    body = dict(proof)
    observed = body.pop("proof_digest")
    assert observed == canonical_digest(body)
    assert proof["status"] == "engineering_proof_pass_live_candidate_generation_unproven"
    assert proof["planner_gold_visibility"] is False
    assert proof["evaluator_only_summary"]["target_in_pool_recall"] == 1.0
    assert proof["decision"]["S1_08_live_candidate_ceiling"] == "unproven"
    assert proof["decision"]["S1_08_ranking"] == "not_admitted_on_live_evidence"
    assert proof["verification"]["focused_tests"] == 14
