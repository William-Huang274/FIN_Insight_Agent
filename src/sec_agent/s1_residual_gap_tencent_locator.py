from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.s1_08_tencent_wsa_candidate_diagnostic import (
    normalize_search_pro_response,
    redact_runtime_value,
)
from sec_agent.s1_residual_gap_external_live import LocatorProviderResult
from sec_agent.s1_residual_gap_external_supplement import CONTRACT_REF


PROFILE_SCHEMA = "fin_ia_0_1_3_s1_residual_gap_tencent_locator_profile_v1_0"
PROVIDER_ID = "tencent_wsa_searchpro_standard_locator_v1"
PROVIDER_NAMESPACE = "fin-0.1.3/s1/residual-gap-tencent-locator"


class ResidualGapTencentLocatorError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def load_residual_gap_tencent_locator_profile(path: str | Path) -> dict[str, Any]:
    profile = json.loads(Path(path).read_text(encoding="utf-8"))
    api = profile.get("api_contract") or {}
    auth = profile.get("authentication") or {}
    budget = profile.get("budget") or {}
    boundary = profile.get("capability_boundary") or {}
    if (
        profile.get("schema_version") != PROFILE_SCHEMA
        or profile.get("contract_ref") != CONTRACT_REF
        or profile.get("provider_id") != PROVIDER_ID
        or api
        != {
            "endpoint": "wsa.tencentcloudapi.com",
            "protocol": "https",
            "action": "SearchPro",
            "version": "2025-05-08",
            "region": "",
            "request_body_fields": ["Query"],
        }
        or auth.get("mode") != "tencent_cloud_api3_ak_sk_signature"
        or auth.get("credential_persistence_allowed") is not False
        or auth.get("credential_logging_allowed") is not False
        or budget
        != {
            "provider_call_ceiling": 12,
            "result_ceiling_per_call": 10,
            "timeout_seconds_per_call": 30,
            "retry_ceiling": 0,
        }
        or boundary.get("role") != "official_domain_locator_only"
        or boundary.get("provider_snippet_is_evidence") is not False
        or boundary.get("provider_date_is_financial_date_authority") is not False
        or boundary.get("evidence_promotion_allowed") is not False
        or boundary.get("writer_citable") is not False
        or boundary.get("numeric_authority") != "none"
    ):
        raise ResidualGapTencentLocatorError(
            "residual_gap_tencent_locator_profile_invalid"
        )
    return profile


class TencentSearchProLocatorProvider:
    live_network = True

    def __init__(
        self,
        *,
        profile: Mapping[str, Any],
        runtime_root: str | Path,
        models: Any,
        client: Any,
        secrets: Sequence[str],
    ) -> None:
        self.profile = dict(profile)
        self.runtime_root = Path(runtime_root).resolve()
        self.models = models
        self.client = client
        self.secrets = tuple(str(value) for value in secrets if value)
        self._network_calls = 0
        self._systemic_stop = ""
        self._store: FileCanonicalObjectStore | None = None

    @property
    def network_calls(self) -> int:
        return self._network_calls

    def locate(self, *, intent: Mapping[str, Any]) -> LocatorProviderResult:
        if self._systemic_stop:
            return LocatorProviderResult(
                status="typed_gap",
                locators=(),
                failure_code="not_attempted_after_systemic_provider_rejection",
                network_attempted=False,
            )
        ceiling = int(self.profile["budget"]["provider_call_ceiling"])
        if self._network_calls >= ceiling:
            return LocatorProviderResult(
                status="typed_gap",
                locators=(),
                failure_code="locator_provider_call_ceiling_reached",
                network_attempted=False,
            )
        query = str(intent["official_domain_query"]["en"])
        safe_request = {
            "schema_version": "fin_ia_0_1_3_s1_residual_gap_tencent_safe_request_v1_0",
            "provider_id": PROVIDER_ID,
            "endpoint": self.profile["api_contract"]["endpoint"],
            "action": "SearchPro",
            "api_version": self.profile["api_contract"]["version"],
            "request_body": {"Query": query},
            "intent_id": intent["intent_id"],
            "intent_digest": intent["intent_digest"],
            "credential_values_included": False,
            "authorization_headers_included": False,
            "provider_role": "locator_only",
        }
        request_ref = self._put(safe_request, "tencent_locator_safe_request")
        request = self.models.SearchProRequest()
        request.from_json_string(json.dumps({"Query": query}, ensure_ascii=False))
        self._network_calls += 1
        try:
            response = self.client.SearchPro(request)
            raw = json.loads(response.to_json_string())
            safe_raw = redact_runtime_value(raw, self.secrets)
            raw_ref = self._put(safe_raw, "tencent_locator_raw_response")
            projection = normalize_search_pro_response(
                safe_raw,
                result_ceiling=int(
                    self.profile["budget"]["result_ceiling_per_call"]
                ),
            )
            projection_ref = self._put(
                projection,
                "tencent_locator_private_normalized_projection",
            )
            public_locators = tuple(
                {
                    "canonical_url": str(row["canonical_url"]),
                    "title": str(row["title"]),
                    "provider_rank": int(row["provider_rank"]),
                    "source_domain": str(row["source_domain"]),
                    "provider_snippet_included": False,
                    "provider_date_included": False,
                }
                for row in projection["locators"]
            )
            return LocatorProviderResult(
                status="completed",
                locators=public_locators,
                capture_refs=(request_ref, raw_ref, projection_ref),
                network_attempted=True,
            )
        except Exception as exc:
            projected = redact_runtime_value(_safe_error(exc), self.secrets)
            failure_ref = self._put(
                {
                    "schema_version": "fin_ia_0_1_3_s1_residual_gap_tencent_failure_v1_0",
                    "intent_id": intent["intent_id"],
                    "request_capture_ref": request_ref["object_key"],
                    "request_capture_digest": request_ref["digest"],
                    "failure": projected,
                    "retry_allowed": False,
                    "credential_values_included": False,
                },
                "tencent_locator_typed_failure",
            )
            error_code = str(projected.get("error_code") or "")
            if _is_systemic_stop(error_code):
                self._systemic_stop = error_code
            return LocatorProviderResult(
                status="typed_gap",
                locators=(),
                capture_refs=(request_ref, failure_ref),
                failure_code=(
                    f"locator_provider_{error_code}"
                    if error_code
                    else "locator_provider_sdk_or_transport_error"
                ),
                network_attempted=True,
            )

    def _put(self, value: Mapping[str, Any], artifact_type: str) -> dict[str, Any]:
        if self._store is None:
            self._store = FileCanonicalObjectStore(
                self.runtime_root / "provider-objects"
            )
        ref = self._store.put_json(
            value,
            namespace=PROVIDER_NAMESPACE,
            artifact_type=artifact_type,
        )
        observed = self._store.get_json(
            ref["object_key"],
            expected_digest=ref["digest"],
        )
        serialized = json.dumps(observed, ensure_ascii=False)
        if any(secret and secret in serialized for secret in self.secrets):
            raise ResidualGapTencentLocatorError(
                "residual_gap_tencent_locator_secret_redaction_failed"
            )
        return ref


def _safe_error(exc: Exception) -> dict[str, Any]:
    code = getattr(exc, "get_code", lambda: exc.__class__.__name__)()
    message = getattr(exc, "get_message", lambda: str(exc))()
    request_id = getattr(exc, "get_request_id", lambda: "")()
    return {
        "error_code": str(code or exc.__class__.__name__),
        "message": str(message or "")[:500],
        "request_id": str(request_id or "") or None,
    }


def _is_systemic_stop(error_code: str) -> bool:
    normalized = str(error_code).casefold()
    return normalized.startswith("authfailure") or normalized in {
        "unauthorizedoperation",
        "resourcenotfound",
        "resourceunavailable",
        "requestlimitexceeded",
    }


__all__ = [
    "PROFILE_SCHEMA",
    "PROVIDER_ID",
    "ResidualGapTencentLocatorError",
    "TencentSearchProLocatorProvider",
    "load_residual_gap_tencent_locator_profile",
]
