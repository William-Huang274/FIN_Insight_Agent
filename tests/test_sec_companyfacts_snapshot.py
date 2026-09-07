from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError
import pytest
import requests

from scripts.data_retrieval.materialize_sec_snapshot_s2_policy_bridge import (
    parse_args as parse_s2_bridge_args,
)

from financial_facts import (
    CompanyFactMartPolicy,
    CompanySourceBinding,
    SEC_SNAPSHOT_INPUT_SCHEMA_VERSION,
    SecSnapshotCompany,
    SecSnapshotError,
    SecSnapshotInputManifest,
    SecSnapshotRequestPolicy,
    capture_sec_companyfacts_snapshot,
    load_company_fact_mart_policy,
    load_sec_snapshot_input_manifest,
    load_sec_snapshot_result_manifest,
    seal_s2_successor_policy_change_receipt,
    parse_company_source,
)
from financial_facts.sec_snapshot import (
    COMPANYFACTS_URL_TEMPLATE,
    SUBMISSIONS_URL_TEMPLATE,
    build_s2_successor_policy_from_sec_snapshot,
    canonical_digest,
    canonical_sec_payload_digest,
)


CIK = "0001571996"
TICKER = "DELL"
LEGAL_NAME = "Dell Technologies Inc."
# Deliberately assembled so the test suite does not publish a copyable sample
# contact address.  It is used only by fake HTTP and must never reach disk.
TEST_CONTACT = "sec-owner" + chr(64) + "private-research.cn"


@dataclass(frozen=True)
class FakeResponse:
    url: str
    content: bytes
    status_code: int = 200
    content_type: str = "application/json; charset=utf-8"

    @property
    def headers(self) -> dict[str, str]:
        return {"Content-Type": self.content_type}


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


def _companyfacts(*, cik: int = 1571996, name: str = LEGAL_NAME) -> dict[str, Any]:
    return {"cik": cik, "entityName": name, "facts": {}}


def _submissions(*, cik: int = 1571996, name: str = LEGAL_NAME) -> dict[str, Any]:
    return {
        "cik": cik,
        "name": name,
        "filings": {
            "recent": {
                "accessionNumber": [],
                "filingDate": [],
                "acceptanceDateTime": [],
                "reportDate": [],
                "form": [],
                "primaryDocument": [],
            }
        },
    }


def _raw(payload: dict[str, Any]) -> bytes:
    # Non-canonical whitespace proves raw and logical digests are independent.
    return (json.dumps(payload, ensure_ascii=False, indent=1) + "\n").encode()


def _manifest(*, attempt_id: str = "SEC-TEST-001") -> SecSnapshotInputManifest:
    return SecSnapshotInputManifest(
        schema_version=SEC_SNAPSHOT_INPUT_SCHEMA_VERSION,
        attempt_id=attempt_id,
        companies=(
            SecSnapshotCompany(
                ticker=TICKER,
                cik=CIK,
                legal_name=LEGAL_NAME,
            ),
        ),
    )


def _policy(**overrides: Any) -> SecSnapshotRequestPolicy:
    values: dict[str, Any] = {
        "timeout_seconds": 9,
        "requests_per_second": 2.0,
        "maximum_companies": 1,
        "maximum_response_bytes": 4096,
        "per_source_attempts": 1,
    }
    values.update(overrides)
    return SecSnapshotRequestPolicy(**values)


def _urls() -> tuple[str, str]:
    return (
        COMPANYFACTS_URL_TEMPLATE.format(cik=CIK),
        SUBMISSIONS_URL_TEMPLATE.format(cik=CIK),
    )


def _valid_session() -> FakeSession:
    companyfacts_url, submissions_url = _urls()
    return FakeSession(
        [
            FakeResponse(companyfacts_url, _raw(_companyfacts())),
            FakeResponse(submissions_url, _raw(_submissions())),
        ]
    )


def _fixed_now() -> datetime:
    return datetime(2026, 9, 2, 1, 2, 3, tzinfo=timezone.utc)


def _capture(
    output_root: Path,
    session: FakeSession,
    *,
    manifest: SecSnapshotInputManifest | None = None,
    policy: SecSnapshotRequestPolicy | None = None,
    environment: dict[str, str] | None = None,
    sleeps: list[float] | None = None,
):
    observed_sleeps = sleeps if sleeps is not None else []
    return capture_sec_companyfacts_snapshot(
        manifest or _manifest(),
        output_root=output_root,
        request_policy=policy or _policy(),
        environment=(
            {"FINSIGHT_SEC_CONTACT_EMAIL": TEST_CONTACT}
            if environment is None
            else environment
        ),
        session=session,
        now_utc=_fixed_now,
        monotonic=lambda: 0.0,
        sleep=observed_sleeps.append,
    )


def test_capture_is_raw_only_rate_bounded_and_builder_consumable(tmp_path: Path) -> None:
    output_root = tmp_path / "new-attempt"
    session = _valid_session()
    sleeps: list[float] = []

    result = _capture(output_root, session, sleeps=sleeps)

    assert [call[0] for call in session.calls] == list(_urls())
    for _, kwargs in session.calls:
        assert kwargs["timeout"] == 9
        assert kwargs["allow_redirects"] is False
        assert kwargs["headers"]["Accept"] == "application/json"
        assert kwargs["headers"]["User-Agent"].endswith(f"({TEST_CONTACT})")
    assert sleeps == [0.5]
    assert result.capture_only_no_normalization is True
    assert result.source_capture_authority is False
    assert result.evidence_or_numeric_fact_admission_performed is False
    assert result.source_count == 2

    companyfacts_raw = output_root / "raw/DELL/sec_companyfacts.json"
    expected_raw = _raw(_companyfacts())
    assert companyfacts_raw.read_bytes() == expected_raw
    companyfacts_metadata = json.loads(
        (output_root / "raw/DELL/sec_companyfacts.metadata.json").read_text()
    )
    assert companyfacts_metadata["raw_response_sha256"] == sha256(expected_raw).hexdigest()
    assert companyfacts_metadata["byte_count"] == len(expected_raw)
    assert companyfacts_metadata["canonical_json_sha256"] == canonical_sec_payload_digest(
        _companyfacts()
    )
    assert companyfacts_metadata["source_url"] == _urls()[0]
    assert companyfacts_metadata["content_type"] == "application/json; charset=utf-8"
    assert companyfacts_metadata["ticker"] == TICKER
    assert companyfacts_metadata["cik"] == CIK
    assert companyfacts_metadata["downloaded_at_utc"].endswith("Z")

    loaded = load_sec_snapshot_result_manifest(output_root / "snapshot-manifest.json")
    assert loaded == result
    binding = CompanySourceBinding(
        **result.builder_source_bindings[0].model_dump(mode="python")
    )
    successor_policy = CompanyFactMartPolicy(
        recorded_at="2026-09-02",
        research_as_of="2026-09-02",
        minimum_period_end="2022-01-01",
        allowed_forms=("10-K", "10-Q"),
        sources=(binding,),
        metrics=(),
        acceptance_qrels=(),
        authority={},
    )
    rows, summary = parse_company_source(
        successor_policy,
        binding,
        repository_root=tmp_path,
    )
    assert rows == ()
    assert summary["accepted_observations"] == 0

    persisted = b"\n".join(
        path.read_bytes() for path in output_root.rglob("*") if path.is_file()
    )
    assert TEST_CONTACT.encode() not in persisted
    assert not list(output_root.rglob("*.tmp"))


def test_json_manifest_is_strict_and_requires_explicit_company_identity() -> None:
    valid = {
        "schema_version": SEC_SNAPSHOT_INPUT_SCHEMA_VERSION,
        "attempt_id": "SEC-TEST-JSON",
        "companies": [
            {
                "ticker": TICKER,
                "cik": CIK,
                "legal_name": LEGAL_NAME,
            }
        ],
    }
    assert load_sec_snapshot_input_manifest(json.dumps(valid)).companies[0].cik == CIK

    duplicate = {**valid, "companies": valid["companies"] * 2}
    with pytest.raises(ValidationError, match="sec_snapshot_ticker_duplicate"):
        load_sec_snapshot_input_manifest(json.dumps(duplicate))

    with pytest.raises(ValidationError):
        load_sec_snapshot_input_manifest(json.dumps({**valid, "unknown": True}))


def test_endpoint_specific_official_names_are_versioned_metadata_not_identity(
    tmp_path: Path,
) -> None:
    companyfacts_name = "Micron Technology, Inc."
    submissions_name = "MICRON TECHNOLOGY INC"
    manifest = SecSnapshotInputManifest(
        schema_version=SEC_SNAPSHOT_INPUT_SCHEMA_VERSION,
        attempt_id="SEC-TEST-ENDPOINT-NAMES",
        companies=(
            SecSnapshotCompany(
                ticker="MU",
                cik="0000723125",
                legal_name="Micron Technology",
            ),
        ),
    )
    companyfacts_url = COMPANYFACTS_URL_TEMPLATE.format(cik="0000723125")
    submissions_url = SUBMISSIONS_URL_TEMPLATE.format(cik="0000723125")
    session = FakeSession(
        [
            FakeResponse(
                companyfacts_url,
                _raw(_companyfacts(cik=723125, name=companyfacts_name)),
            ),
            FakeResponse(
                submissions_url,
                _raw(_submissions(cik=723125, name=submissions_name)),
            ),
        ]
    )

    result = _capture(
        tmp_path / "endpoint-specific-names",
        session,
        manifest=manifest,
    )

    assert result.company_count == 1
    assert result.builder_source_bindings[0].legal_name == companyfacts_name
    assert tuple(row.source_entity_name for row in result.artifacts) == (
        companyfacts_name,
        submissions_name,
    )


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"FINSIGHT_SEC_CONTACT_EMAIL": "contact" + chr(64) + "example.com"},
        {"FINSIGHT_SEC_CONTACT_EMAIL": "not-an-email"},
    ],
)
def test_missing_or_placeholder_contact_fails_after_claim_without_http(
    tmp_path: Path,
    environment: dict[str, str],
) -> None:
    root = tmp_path / "attempt"
    session = _valid_session()

    with pytest.raises(SecSnapshotError) as caught:
        _capture(root, session, environment=environment)

    assert caught.value.code == "sec_snapshot_real_contact_email_required"
    assert session.calls == []
    receipt = json.loads((root / "terminal-failure-receipt.json").read_text())
    assert receipt["failure_code"] == caught.value.code
    assert receipt["completed_source_count"] == 0
    assert receipt["contact_value_persisted"] is False
    assert not (root / "snapshot-manifest.json").exists()
    persisted = b"\n".join(path.read_bytes() for path in root.iterdir() if path.is_file())
    for value in environment.values():
        assert value.encode() not in persisted


def test_existing_nonempty_attempt_root_is_never_touched(tmp_path: Path) -> None:
    root = tmp_path / "existing"
    root.mkdir()
    sentinel = root / "old-snapshot.json"
    sentinel.write_bytes(b"immutable-old-snapshot")
    session = _valid_session()

    with pytest.raises(SecSnapshotError, match="sec_snapshot_output_root_not_empty"):
        _capture(root, session)

    assert sentinel.read_bytes() == b"immutable-old-snapshot"
    assert session.calls == []
    assert list(root.iterdir()) == [sentinel]


def test_partial_failure_preserves_completed_source_and_failure_receipt(
    tmp_path: Path,
) -> None:
    root = tmp_path / "attempt"
    old_snapshot = tmp_path / "prior-attempt" / "snapshot-manifest.json"
    old_snapshot.parent.mkdir()
    old_snapshot.write_bytes(b"prior-immutable")
    companyfacts_url, submissions_url = _urls()
    session = FakeSession(
        [
            FakeResponse(companyfacts_url, _raw(_companyfacts())),
            FakeResponse(submissions_url, b"{}", status_code=503),
        ]
    )

    with pytest.raises(SecSnapshotError) as caught:
        _capture(root, session)

    assert caught.value.code == "sec_snapshot_http_status_invalid"
    assert (root / "raw/DELL/sec_companyfacts.json").is_file()
    assert (root / "raw/DELL/sec_companyfacts.metadata.json").is_file()
    assert not (root / "raw/DELL/sec_submissions.json").exists()
    assert not (root / "snapshot-manifest.json").exists()
    receipt = json.loads((root / "terminal-failure-receipt.json").read_text())
    assert receipt["completed_source_count"] == 1
    assert receipt["failed_source"]["source_kind"] == "sec_submissions"
    assert receipt["complete_files_preserved"] is True
    assert old_snapshot.read_bytes() == b"prior-immutable"
    assert not list(root.rglob("*.tmp"))


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (
            FakeResponse(_urls()[0], b"{}", status_code=302),
            "sec_snapshot_http_status_invalid",
        ),
        (
            FakeResponse(_urls()[0], b"<html></html>", content_type="text/html"),
            "sec_snapshot_content_type_invalid",
        ),
        (
            FakeResponse("https://www.sec.gov/redirect", _raw(_companyfacts())),
            "sec_snapshot_response_url_drift",
        ),
        (
            FakeResponse(_urls()[0], _raw(_companyfacts(cik=1045810))),
            "sec_snapshot_payload_cik_mismatch",
        ),
    ],
)
def test_untrusted_or_mismatched_response_fails_closed(
    tmp_path: Path,
    response: FakeResponse,
    expected_code: str,
) -> None:
    root = tmp_path / expected_code
    session = FakeSession([response])

    with pytest.raises(SecSnapshotError) as caught:
        _capture(root, session)

    assert caught.value.code == expected_code
    receipt = json.loads((root / "terminal-failure-receipt.json").read_text())
    assert receipt["failure_code"] == expected_code
    assert receipt["completed_source_count"] == 0
    assert not (root / "raw/DELL/sec_companyfacts.json").exists()


def test_transport_timeout_has_typed_receipt(tmp_path: Path) -> None:
    root = tmp_path / "timeout"
    session = FakeSession([requests.Timeout("do not persist this message")])

    with pytest.raises(SecSnapshotError) as caught:
        _capture(root, session)

    assert caught.value.code == "sec_snapshot_transport_timeout"
    persisted = (root / "terminal-failure-receipt.json").read_text()
    assert "do not persist this message" not in persisted
    assert TEST_CONTACT not in persisted


def test_company_and_resource_hard_bounds_fail_before_http(tmp_path: Path) -> None:
    second = SecSnapshotCompany(
        ticker="NVDA",
        cik="0001045810",
        legal_name="NVIDIA CORP",
    )
    manifest = _manifest().model_copy(
        update={"companies": (_manifest().companies[0], second)}
    )
    session = _valid_session()

    with pytest.raises(
        SecSnapshotError,
        match="sec_snapshot_company_execution_ceiling_exceeded",
    ):
        _capture(tmp_path / "not-claimed", session, manifest=manifest)

    assert session.calls == []
    assert not (tmp_path / "not-claimed").exists()
    with pytest.raises(ValidationError):
        _policy(timeout_seconds=61)
    with pytest.raises(ValidationError):
        _policy(requests_per_second=2.1)
    with pytest.raises(ValidationError):
        _policy(maximum_response_bytes=33 * 1024 * 1024)


def test_response_byte_ceiling_fails_before_any_raw_write(tmp_path: Path) -> None:
    root = tmp_path / "oversized"
    companyfacts_url, _ = _urls()
    oversized = b"{" + (b" " * 2048) + b"}"
    session = FakeSession([FakeResponse(companyfacts_url, oversized)])

    with pytest.raises(SecSnapshotError) as caught:
        _capture(
            root,
            session,
            policy=_policy(maximum_response_bytes=1024),
        )

    assert caught.value.code == "sec_snapshot_response_too_large"
    assert not (root / "raw").exists()


def test_s2_policy_bridge_replaces_only_sources_and_binds_relative_refs(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "snapshot"
    captured = _capture(snapshot_root, _valid_session())
    payload = captured.model_dump(mode="json", exclude={"manifest_digest"})
    binding = dict(payload["builder_source_bindings"][0])
    for key in (
        "companyfacts_ref",
        "companyfacts_metadata_ref",
        "submissions_ref",
        "submissions_metadata_ref",
    ):
        binding[key] = Path(binding[key]).resolve().relative_to(snapshot_root).as_posix()
    payload["builder_source_bindings"] = [binding]
    relative_snapshot = load_sec_snapshot_result_manifest(
        json.dumps({**payload, "manifest_digest": canonical_digest(payload)})
    )
    baseline = _minimal_s2_policy()

    successor = build_s2_successor_policy_from_sec_snapshot(
        baseline,
        relative_snapshot,
        snapshot_root=snapshot_root,
        research_as_of="2026-09-02",
    )

    mutable_fields = {"research_as_of", "source_bindings"}
    assert {key: value for key, value in successor.items() if key not in mutable_fields} == {
        key: value for key, value in baseline.items() if key not in mutable_fields
    }
    assert successor["research_as_of"] == "2026-09-02"
    assert successor["acceptance_qrels"] == baseline["acceptance_qrels"]
    assert successor["source_bindings"][0]["legal_name"] == LEGAL_NAME
    for key in (
        "companyfacts_ref",
        "companyfacts_metadata_ref",
        "submissions_ref",
        "submissions_metadata_ref",
    ):
        resolved = Path(successor["source_bindings"][0][key]).resolve()
        assert resolved.is_file()
        assert resolved.is_relative_to(snapshot_root.resolve())
    assert load_company_fact_mart_policy(successor).sources[0].ticker == TICKER


def test_s2_policy_bridge_rejects_binding_outside_exact_snapshot_root(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "snapshot"
    captured = _capture(snapshot_root, _valid_session())
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    payload = captured.model_dump(mode="json", exclude={"manifest_digest"})
    binding = dict(payload["builder_source_bindings"][0])
    binding["companyfacts_ref"] = str(outside.resolve())
    payload["builder_source_bindings"] = [binding]
    escaped_snapshot = load_sec_snapshot_result_manifest(
        json.dumps({**payload, "manifest_digest": canonical_digest(payload)})
    )

    with pytest.raises(
        ValueError,
        match="sec_snapshot_s2_bridge_ref_outside_snapshot",
    ):
        build_s2_successor_policy_from_sec_snapshot(
            _minimal_s2_policy(),
            escaped_snapshot,
            snapshot_root=snapshot_root,
            research_as_of="2026-09-02",
        )


def test_s2_policy_bridge_rejects_research_as_of_regression(tmp_path: Path) -> None:
    snapshot_root = tmp_path / "snapshot"
    captured = _capture(snapshot_root, _valid_session())

    with pytest.raises(
        ValueError,
        match="sec_snapshot_s2_bridge_research_as_of_regressed",
    ):
        build_s2_successor_policy_from_sec_snapshot(
            _minimal_s2_policy(),
            captured,
            snapshot_root=snapshot_root,
            research_as_of="2026-08-05",
        )


def test_s2_policy_bridge_cli_requires_explicit_research_as_of() -> None:
    common = [
        "--baseline-policy",
        "baseline.json",
        "--snapshot-manifest",
        "snapshot-manifest.json",
        "--output-policy",
        "successor.json",
    ]
    with pytest.raises(SystemExit) as caught:
        parse_s2_bridge_args(common)
    assert caught.value.code == 2

    parsed = parse_s2_bridge_args([*common, "--research-as-of", "2026-09-02"])
    assert parsed.research_as_of == "2026-09-02"


def test_s2_policy_bridge_rejects_as_of_before_snapshot_fact_accepted_at(
    tmp_path: Path,
) -> None:
    accession = "0001571996-26-000030"
    companyfacts = _companyfacts()
    companyfacts["facts"] = {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            "start": "2026-01-31",
                            "end": "2026-05-01",
                            "val": 100,
                            "accn": accession,
                            "fp": "Q1",
                            "fy": 2027,
                        }
                    ]
                }
            }
        }
    }
    submissions = _submissions()
    submissions["filings"]["recent"] = {
        "accessionNumber": [accession],
        "filingDate": ["2026-08-28"],
        "acceptanceDateTime": ["2026-08-28T16:30:00Z"],
        "reportDate": ["2026-05-01"],
        "form": ["10-Q"],
        "primaryDocument": ["dell-20260501.htm"],
    }
    companyfacts_url, submissions_url = _urls()
    snapshot_root = tmp_path / "snapshot-with-fact"
    captured = _capture(
        snapshot_root,
        FakeSession(
            [
                FakeResponse(companyfacts_url, _raw(companyfacts)),
                FakeResponse(submissions_url, _raw(submissions)),
            ]
        ),
    )

    with pytest.raises(
        ValueError,
        match="sec_snapshot_s2_bridge_research_as_of_before_snapshot_fact",
    ):
        build_s2_successor_policy_from_sec_snapshot(
            _minimal_s2_policy(),
            captured,
            snapshot_root=snapshot_root,
            research_as_of="2026-08-07",
        )

    successor = build_s2_successor_policy_from_sec_snapshot(
        _minimal_s2_policy(),
        captured,
        snapshot_root=snapshot_root,
        research_as_of="2026-09-02",
    )
    receipt = seal_s2_successor_policy_change_receipt(
        _minimal_s2_policy(),
        successor,
        snapshot_root=snapshot_root,
    )
    assert receipt["changed_fields"] == ["research_as_of", "source_bindings"]
    assert receipt["latest_snapshot_fact_accepted_at"] == (
        "2026-08-28T16:30:00+00:00"
    )
    assert receipt["metric_qrel_temporal_finance_rules_preserved"] is True
    unsigned = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    assert receipt["receipt_digest"] == canonical_digest(unsigned)


def test_s2_policy_change_receipt_rejects_qrel_or_other_rule_drift(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "snapshot"
    captured = _capture(snapshot_root, _valid_session())
    baseline = _minimal_s2_policy()
    successor = build_s2_successor_policy_from_sec_snapshot(
        baseline,
        captured,
        snapshot_root=snapshot_root,
        research_as_of="2026-09-02",
    )
    drifted = json.loads(json.dumps(successor))
    drifted["acceptance_qrels"][0]["qrel_id"] = "drifted-qrel"

    with pytest.raises(
        ValueError,
        match="sec_snapshot_s2_bridge_policy_rule_drift",
    ):
        seal_s2_successor_policy_change_receipt(
            baseline,
            drifted,
            snapshot_root=snapshot_root,
        )


def _minimal_s2_policy() -> dict[str, Any]:
    return {
        "schema_version": "fin_ia_s2_company_financial_fact_mart_policy_v1_0",
        "status": "zero_network_source_bound_company_fact_mart_policy",
        "recorded_at": "2026-08-13",
        "research_as_of": "2026-08-06",
        "minimum_period_end": "2022-01-01",
        "allowed_forms": ["10-K", "10-Q"],
        "source_bindings": [
            {
                "ticker": "OLD",
                "cik": "0000000001",
                "legal_name": "Old source",
                "companyfacts_ref": "old-companyfacts.json",
                "companyfacts_metadata_ref": "old-companyfacts.metadata.json",
                "companyfacts_sha256": "0" * 64,
                "submissions_ref": "old-submissions.json",
                "submissions_metadata_ref": "old-submissions.metadata.json",
                "submissions_sha256": "1" * 64,
            }
        ],
        "metric_definitions": [
            {
                "metric_id": "revenue",
                "unit_family": "currency",
                "allowed_units": ["USD"],
                "concepts": [{"taxonomy": "us-gaap", "concept": "Revenues"}],
            }
        ],
        "acceptance_qrels": [
            {"qrel_id": "fixture-only", "research_as_of": "2026-08-06"}
        ],
        "authority": {
            "raw_capture_digest_required": True,
            "accepted_at_required": True,
            "network_calls": 0,
            "model_calls": 0,
            "preserve_all_vintages": True,
            "fact_signal_context_mixed_table_forbidden": True,
            "typed_conflict_fails_closed": True,
        },
    }
