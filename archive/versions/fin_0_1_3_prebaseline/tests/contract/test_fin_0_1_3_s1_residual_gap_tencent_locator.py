from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_residual_gap_tencent_locator import (  # noqa: E402
    ResidualGapTencentLocatorError,
    TencentSearchProLocatorProvider,
    load_residual_gap_tencent_locator_profile,
)


PROFILE_PATH = ROOT / (
    "configs/runtime/"
    "fin_ia_0_1_3_s1_residual_gap_tencent_locator_profile_v1_0.json"
)


class FakeRequest:
    def __init__(self) -> None:
        self.body = {}

    def from_json_string(self, value: str) -> None:
        self.body = json.loads(value)


class FakeModels:
    SearchProRequest = FakeRequest


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def to_json_string(self) -> str:
        return json.dumps(self.payload, ensure_ascii=False)


class FakeSDKError(Exception):
    def get_code(self):
        return "AuthFailure.SignatureFailure"

    def get_message(self):
        return str(self)

    def get_request_id(self):
        return "request-test"


class FakeClient:
    def __init__(self, *, secret: str = "", fail: bool = False) -> None:
        self.secret = secret
        self.fail = fail
        self.calls = 0

    def SearchPro(self, request: FakeRequest):
        self.calls += 1
        assert set(request.body) == {"Query"}
        if self.fail:
            raise FakeSDKError(f"credential {self.secret} rejected")
        return FakeResponse(
            {
                "Response": {
                    "Query": request.body["Query"],
                    "Pages": [
                        {
                            "url": "https://investors.micron.com/hbm-results?utm_source=x",
                            "title": "Micron HBM capacity results",
                            "passage": f"private snippet {self.secret}",
                            "date": "2099-01-01",
                            "score": 0.9,
                        }
                    ],
                    "RequestId": "request-test",
                }
            }
        )


def _intent() -> dict:
    return {
        "intent_id": "residual_search_intent::DELL::supplier::1234",
        "intent_digest": "1" * 64,
        "official_domain_query": {
            "en": "Micron HBM capacity site:investors.micron.com"
        },
    }


def test_profile_is_locator_only() -> None:
    profile = load_residual_gap_tencent_locator_profile(PROFILE_PATH)
    assert profile["budget"]["provider_call_ceiling"] == 12
    assert profile["capability_boundary"]["role"] == "official_domain_locator_only"
    assert profile["capability_boundary"]["provider_snippet_is_evidence"] is False


def test_provider_keeps_snippet_and_date_private_and_redacts_secret(tmp_path) -> None:
    profile = load_residual_gap_tencent_locator_profile(PROFILE_PATH)
    secret = "super-secret-value"
    client = FakeClient(secret=secret)
    provider = TencentSearchProLocatorProvider(
        profile=profile,
        runtime_root=tmp_path,
        models=FakeModels,
        client=client,
        secrets=(secret,),
    )
    result = provider.locate(intent=_intent())
    assert result.status == "completed"
    assert result.network_attempted is True
    assert provider.network_calls == 1
    assert len(result.capture_refs) == 3
    assert result.locators == (
        {
            "canonical_url": "https://investors.micron.com/hbm-results",
            "title": "Micron HBM capacity results",
            "provider_rank": 1,
            "source_domain": "investors.micron.com",
            "provider_snippet_included": False,
            "provider_date_included": False,
        },
    )
    assert secret not in json.dumps(result.locators)
    assert all(secret not in path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.json"))


def test_systemic_failure_stops_later_provider_calls(tmp_path) -> None:
    profile = load_residual_gap_tencent_locator_profile(PROFILE_PATH)
    secret = "secret-rejected"
    client = FakeClient(secret=secret, fail=True)
    provider = TencentSearchProLocatorProvider(
        profile=profile,
        runtime_root=tmp_path,
        models=FakeModels,
        client=client,
        secrets=(secret,),
    )
    first = provider.locate(intent=_intent())
    second = provider.locate(intent=_intent())
    assert first.failure_code == "locator_provider_AuthFailure.SignatureFailure"
    assert first.network_attempted is True
    assert second.failure_code == "not_attempted_after_systemic_provider_rejection"
    assert second.network_attempted is False
    assert provider.network_calls == client.calls == 1
    assert all(secret not in path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.json"))


def test_profile_mutation_fails_closed(tmp_path) -> None:
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    changed = deepcopy(profile)
    changed["capability_boundary"]["provider_snippet_is_evidence"] = True
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ResidualGapTencentLocatorError) as exc:
        load_residual_gap_tencent_locator_profile(path)
    assert exc.value.code == "residual_gap_tencent_locator_profile_invalid"
