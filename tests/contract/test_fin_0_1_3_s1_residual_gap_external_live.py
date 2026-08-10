from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
from typing import Any, Mapping
from urllib.parse import urljoin

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.official_source_attempt_program import SourceResponse  # noqa: E402
from sec_agent.s1_residual_gap_external_live import (  # noqa: E402
    AUTHORITY_SCHEMA,
    LocatorProviderResult,
    ResidualGapExternalLiveError,
    execute_residual_gap_external_live,
    validate_residual_gap_external_live_authority,
)
from sec_agent.s1_residual_gap_external_supplement import (  # noqa: E402
    CASES,
    CONTRACT_REF,
    RUN_SCOPE,
    canonical_digest,
    file_sha256,
    load_residual_gap_external_supplement_policy,
)
from sec_agent.shared_admission_ledger import (  # noqa: E402
    SharedAdmissionConsumptionLedger,
)


POLICY_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_residual_gap_external_supplement_policy_v1_0.json"
)
PLAN_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_3_s1_residual_gap_external_priority_plan_v1_0.json"
)
MODULE_PATH = ROOT / "src/sec_agent/s1_residual_gap_external_live.py"


class FakeTransport:
    live_network = True

    def __init__(self, responses: Mapping[str, SourceResponse]) -> None:
        self.responses = dict(responses)
        self.calls: list[str] = []

    def fetch(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        allowed_hosts: set[str],
        timeout_seconds: int,
        byte_ceiling: int,
    ) -> SourceResponse:
        del headers, timeout_seconds, byte_ceiling
        assert url in self.responses
        assert self.responses[url].final_url.split("/", 3)[2] in allowed_hosts
        self.calls.append(url)
        return self.responses[url]


class FakeLocatorProvider:
    live_network = True

    def __init__(self, *, off_domain: bool = False) -> None:
        self.calls: list[str] = []
        self.off_domain = off_domain

    @property
    def network_calls(self) -> int:
        return len(self.calls)

    def locate(self, *, intent: Mapping[str, Any]) -> LocatorProviderResult:
        self.calls.append(str(intent["intent_id"]))
        if self.off_domain:
            url = "https://example.com/unrelated-navigation.html"
        else:
            url = "https://investors.micron.com/hbm-capacity-results.html"
        return LocatorProviderResult(
            status="completed",
            network_attempted=True,
            capture_refs=(
                {
                    "object_key": f"fake/provider/{canonical_digest(intent['intent_id'])}.json",
                    "digest": canonical_digest({"intent": intent["intent_id"]}),
                },
            ),
            locators=(
                {
                    "canonical_url": url,
                    "title": "HBM advanced packaging capacity ramp yield results",
                    "provider_rank": 1,
                    "passage": "This provider snippet must never enter the result.",
                    "published_at_raw": "2099-01-01",
                },
            ),
        )


@pytest.fixture(scope="module")
def policy_and_plan():
    import json

    policy = load_residual_gap_external_supplement_policy(
        POLICY_PATH,
        repo_root=ROOT,
    )
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    return policy, plan


def _authority(policy: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "schema_version": AUTHORITY_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": RUN_SCOPE,
        "status": "issued_unconsumed",
        "issued_at": "2026-08-10T00:00:00Z",
        "expires_at": "2026-08-11T00:00:00Z",
        "implementation_commit": "test-implementation-commit",
        "admission_id": "fin013-s1-residual-external-test-admission",
        "run_id": "fin013-s1-residual-external-test-run",
        "attempt_id": "fin013-s1-residual-external-test-attempt",
        "maximum_executions": 1,
        "automatic_retry": False,
        "evidence_promotion_allowed": False,
        "model_calls_allowed": 0,
        "priority_plan_digest": plan["plan_digest"],
        "local_evidence_pack_result_digest": plan[
            "local_evidence_pack_result_digest"
        ],
        "budget": deepcopy(policy["budget"]),
        "file_bindings": {
            str(POLICY_PATH.relative_to(ROOT)).replace("\\", "/"): file_sha256(
                POLICY_PATH
            ),
            str(PLAN_PATH.relative_to(ROOT)).replace("\\", "/"): file_sha256(
                PLAN_PATH
            ),
            str(MODULE_PATH.relative_to(ROOT)).replace("\\", "/"): file_sha256(
                MODULE_PATH
            ),
        },
    }
    return {**body, "authority_digest": canonical_digest(body)}


def _html_response(url: str, body: str) -> SourceResponse:
    return SourceResponse(
        status_code=200,
        final_url=url,
        headers={"content-type": "text/html; charset=utf-8"},
        body=body.encode("utf-8"),
    )


def _fixture_responses(
    policy: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    future_case: str = "",
) -> dict[str, SourceResponse]:
    responses: dict[str, SourceResponse] = {}
    for case_key in CASES:
        root_url = str(policy["case_profiles"][case_key]["official_discovery_roots"][0])
        host = str(policy["case_profiles"][case_key]["allowed_subject_hosts"][0])
        document_url = f"https://{host}/financial-results-2026.html"
        case_intents = [
            row for row in plan["selected_intents"] if row["case_key"] == case_key
        ]
        terms = " ".join(
            str(row["semantic_locator_query"]["en"]) for row in case_intents
        )
        responses[root_url] = _html_response(
            root_url,
            (
                "<html><head><title>Investor relations</title></head><body>"
                f"<a href='{document_url}'>{terms}</a>"
                "</body></html>"
            ),
        )
        publication = "2026-08-09" if case_key == future_case else "2026-07-15"
        responses[document_url] = _html_response(
            document_url,
            (
                "<html><head>"
                f"<title>{case_key} financial results</title>"
                f"<meta property='article:published_time' content='{publication}'/>"
                "</head><body>"
                f"{terms} Management explains demand, capacity, margin, cash flow, "
                "counterevidence, mitigation, orders and deployment with company-specific "
                "financial context."
                "</body></html>"
            ),
        )
    supplier_url = "https://investors.micron.com/hbm-capacity-results.html"
    responses[supplier_url] = _html_response(
        supplier_url,
        (
            "<html><head><title>Micron HBM capacity results</title>"
            "<meta property='article:published_time' content='2026-07-20'/></head>"
            "<body>Micron TSMC HBM supply CoWoS advanced packaging capacity ramp "
            "capacity release utilization yield lead time technology symposium results."
            "</body></html>"
        ),
    )
    return responses


def _execute(
    tmp_path: Path,
    policy: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    provider: FakeLocatorProvider | None = None,
    future_case: str = "",
):
    provider = provider or FakeLocatorProvider()
    transport = FakeTransport(_fixture_responses(policy, plan, future_case=future_case))
    result = execute_residual_gap_external_live(
        policy=policy,
        plan=plan,
        authority=_authority(policy, plan),
        repo_root=ROOT,
        runtime_root=tmp_path / "runtime",
        observed_at="2026-08-10T12:00:00Z",
        execution_commit="test-execution-commit",
        official_transport=transport,
        locator_provider=provider,
        shared_admission_ledger=SharedAdmissionConsumptionLedger(
            tmp_path / "shared-admissions.sqlite3"
        ),
    )
    return result, transport, provider


def test_six_case_fake_live_terminalizes_all_intents_without_promoting_evidence(
    policy_and_plan, tmp_path
) -> None:
    policy, plan = policy_and_plan
    result, transport, provider = _execute(tmp_path, policy, plan)
    assert result["status"] == "terminal_completed_with_candidates_and_typed_gaps"
    assert result["observed_counts"]["intents"] == 12
    assert result["observed_counts"]["candidate_ready_for_local_readjudication"] == 12
    assert result["observed_counts"]["typed_gap"] == 0
    assert result["observed_counts"]["official_discovery_network_calls"] == 6
    assert result["observed_counts"]["official_document_network_calls"] == 8
    assert result["observed_counts"]["locator_provider_network_calls"] == 2
    assert result["observed_counts"]["total_network_calls"] == 16
    assert len(transport.calls) == 14
    assert len(provider.calls) == 2
    assert result["observed_counts"]["evidence_promotions"] == 0
    assert all(row["writer_citable"] is False for row in result["intent_results"])
    assert "_private_text" not in str(result)
    assert "This provider snippet" not in str(result)
    assert "2099-01-01" not in str(result)
    body = deepcopy(result)
    supplied = body.pop("result_digest")
    assert supplied == canonical_digest(body)


def test_off_domain_provider_locator_becomes_typed_gap(policy_and_plan, tmp_path) -> None:
    policy, plan = policy_and_plan
    result, _transport, provider = _execute(
        tmp_path,
        policy,
        plan,
        provider=FakeLocatorProvider(off_domain=True),
    )
    supplier_rows = [
        row
        for row in result["intent_results"]
        if row["intent_key"] in {
            "supplier_hbm_packaging_capacity",
            "supplier_packaging_hbm_capacity",
        }
    ]
    assert len(provider.calls) == 2
    assert all(row["status"] == "typed_gap" for row in supplier_rows)
    assert all(row["terminal_code"] == "no_qualified_official_locator" for row in supplier_rows)


def test_future_publication_is_captured_but_not_ready(policy_and_plan, tmp_path) -> None:
    policy, plan = policy_and_plan
    result, _transport, _provider = _execute(
        tmp_path,
        policy,
        plan,
        future_case="ORCL",
    )
    orcl = [row for row in result["intent_results"] if row["case_key"] == "ORCL"]
    assert len(orcl) == 2
    assert all(
        row["status"] == "captured_candidate_with_typed_date_or_content_gap"
        for row in orcl
    )
    assert all(row["terminal_code"] == "publication_date_after_as_of" for row in orcl)


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("budget", "residual_external_live_authority_plan_binding_invalid"),
        ("promotion", "residual_external_live_authority_boundary_invalid"),
        ("binding", "residual_external_live_authority_file_binding_invalid"),
        ("expired", "residual_external_live_authority_not_active"),
    ],
)
def test_authority_mutations_fail_closed(
    policy_and_plan, mutation, expected_code
) -> None:
    policy, plan = policy_and_plan
    authority = _authority(policy, plan)
    observed_at = "2026-08-10T12:00:00Z"
    if mutation == "budget":
        authority["budget"]["total_network_call_ceiling"] = 31
    elif mutation == "promotion":
        authority["evidence_promotion_allowed"] = True
    elif mutation == "binding":
        first = next(iter(authority["file_bindings"]))
        authority["file_bindings"][first] = "0" * 64
    else:
        observed_at = "2026-08-12T00:00:00Z"
    body = deepcopy(authority)
    body.pop("authority_digest", None)
    authority["authority_digest"] = canonical_digest(body)
    with pytest.raises(ResidualGapExternalLiveError) as exc:
        validate_residual_gap_external_live_authority(
            authority,
            policy=policy,
            plan=plan,
            repo_root=ROOT,
            observed_at=observed_at,
        )
    assert exc.value.code == expected_code


def test_same_runtime_cannot_execute_twice(policy_and_plan, tmp_path) -> None:
    policy, plan = policy_and_plan
    _execute(tmp_path, policy, plan)
    with pytest.raises(ResidualGapExternalLiveError) as exc:
        _execute(tmp_path, policy, plan)
    assert exc.value.code == "residual_external_live_runtime_already_exists"
