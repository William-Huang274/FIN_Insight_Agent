from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_mu_10q_locator import (  # noqa: E402
    build_internal_mu_10q_locator_observation,
    load_internal_mu_10q_locator_policy,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_mu_10q_locator_policy_v1_0.json"
)


def test_mu_10q_locator_is_derived_from_retained_capture_without_calls() -> None:
    policy = load_internal_mu_10q_locator_policy(POLICY_PATH, repo_root=ROOT)
    result = build_internal_mu_10q_locator_observation(
        policy=policy, repo_root=ROOT
    )
    assert result["status"] == "retained_capture_locator_proven"
    assert result["target"] == {
        "target_id": "MU_Q3_FY2026_CURRENT_10Q",
        "ticker": "MU",
        "cik": "0000723125",
        "form_type": "10-Q",
        "accession_number": "0000723125-26-000015",
        "filing_date": "2026-06-25",
        "report_date": "2026-05-28",
        "primary_document": "mu-20260528.htm",
        "source_url": (
            "https://www.sec.gov/Archives/edgar/data/723125/"
            "000072312526000015/mu-20260528.htm"
        ),
    }
    assert not any(result["observed_calls"].values())
    assert result["benchmark_exact_url_used_for_discovery"] is False
