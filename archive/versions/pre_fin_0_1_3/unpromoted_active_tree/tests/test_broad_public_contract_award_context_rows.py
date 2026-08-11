from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_broad_public_contract_award_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_broad_public_contract_award_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_broad_public_contract_award_queries_aliases_individually(tmp_path: Path, monkeypatch) -> None:
    queried_aliases: list[str] = []

    def fake_post_json(url: str, payload: dict, *, timeout_s: float) -> tuple[int, str, str]:
        assert url == MODULE.USA_SPENDING_URL
        assert timeout_s == 2
        aliases = payload["filters"]["recipient_search_text"]
        assert len(aliases) == 1
        queried_aliases.append(aliases[0])
        if aliases[0] != "ASD Specialty Healthcare":
            return 200, json.dumps({"results": []}), ""
        return (
            200,
            json.dumps(
                {
                    "results": [
                        {
                            "Award ID": "36C24225P1034",
                            "Recipient Name": "ASD SPECIALTY HEALTHCARE, LLC",
                            "Award Amount": 1000,
                            "Start Date": "2026-01-01",
                            "End Date": "2026-12-31",
                            "Awarding Agency": "Department of Veterans Affairs",
                            "Award Description": "medical supply distribution",
                        }
                    ]
                }
            ),
            "",
        )

    monkeypatch.setattr(MODULE, "_post_json", fake_post_json)
    result = MODULE.build_broad_public_contract_award_context_rows(
        matrix_rows=[
            {
                "ticker": "COR",
                "company_name": "Cencora",
                "source_role_matrix": [{"requirement_id": "public_order_proxy"}],
            }
        ],
        generated_at="2026-06-19T00:00:00Z",
        raw_dir=tmp_path,
        tickers=["COR"],
        timeout_s=2,
        sleep_s=0,
        limit=2,
        workers=1,
    )

    assert "ASD Specialty Healthcare" in queried_aliases
    assert len(result["rows"]) == 1
    assert result["rows"][0]["ticker"] == "COR"
    assert result["rows"][0]["requirement_id"] == "public_order_proxy"
    assert result["rows"][0]["matched_recipient_alias"] == "ASD Specialty Healthcare"


def test_broad_public_contract_award_recipient_match_rejects_substring_false_positive() -> None:
    assert MODULE._award_recipient_matches("MCKESSON MEDICAL-SURGICAL GOVERNMENT SOLUTIONS LLC", ["McKesson Medical-Surgical"])
    assert not MODULE._award_recipient_matches("TOKLO TECHNOLOGIES, LLC", ["Oklo"])
    assert not MODULE._award_recipient_matches("P.J. HELICOPTERS, INC.", ["Quanta Services"])


def test_verified_recipient_aliases_are_queried_before_short_company_names() -> None:
    assert MODULE._recipient_aliases("Intuit", "INTU")[0] == "Intuit Inc"


def test_recipient_aliases_preserve_suffix_sensitive_query_strings() -> None:
    aliases = MODULE._recipient_aliases("HONDA MOTOR CO LTD", "HMC")

    assert "Honda Motor" in aliases
    assert "HONDA MOTOR CO LTD" in aliases


def test_strict_alias_only_ticker_does_not_add_broad_simplified_alias() -> None:
    aliases = MODULE._recipient_aliases("TOYOTA MOTOR CORP/", "TM")

    assert aliases == ("Toyota Motor Corporation",)
