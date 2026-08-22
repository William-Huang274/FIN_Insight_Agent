from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import pytest

from ingestion.official_source_capture import CAPTURE_SCHEMA_VERSION
from retrieval.public_context_source import (
    PublicContextSourceError,
    adjudicate_publication_date_from_capture,
    compile_public_context_candidate,
    compile_public_html_source_object,
    compile_public_pdf_source_object,
)
from retrieval.source_use_policy import SourceUsePolicy


ROOT = Path(__file__).resolve().parents[1]


def _capture(html: str, *, url: str) -> dict:
    body = html.encode("utf-8")
    return {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "capture_kind": "source_response",
        "case_key": "DELL",
        "route_id": "ROUTE::INDUSTRY",
        "request_capture_ref": "sha256://request",
        "request_capture_digest": "a" * 64,
        "status_code": 200,
        "final_url": url,
        "headers": {"content-type": "text/html; charset=utf-8"},
        "redirect_chain": [],
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_bytes": len(body),
        "capture_before_parse": True,
        "credential_cookie_authorization_present": False,
        "preflight_response_refs": [],
    }


def _source_spec(*, publication_date: str = "2026-04-15") -> dict:
    return {
        "source_id": "PUBLIC::TRENDFORCE::20260415",
        "case_key": "DELL",
        "speaker_entity": "TrendForce",
        "speaker_ticker": None,
        "source_class": "official_market_or_industry_primary",
        "source_role": "industry_supply_primary_context",
        "source_type": "INDUSTRY_DATA",
        "relationship_directions": ["industry_to_target_context"],
        "publication_date": publication_date,
        "research_as_of": "2026-08-06",
        "source_url": "https://example.com/research",
        "parser_profile": "article_main_html",
        "segment_character_target": 800,
    }


def _policy() -> SourceUsePolicy:
    payload = json.loads(
        (
            ROOT
            / "configs"
            / "retrieval"
            / "fin_ia_0_1_3_s1_source_strength_and_claim_use_policy_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    return SourceUsePolicy.from_mapping(payload)


def test_public_article_compiler_removes_navigation_and_binds_utf8_capture() -> None:
    excerpt = (
        "Strong AI server demand is causing suppliers to prioritize constrained "
        "components, which extends lead times for general-purpose servers."
    )
    html = f"""
    <html><head><title>Server supply outlook</title>
    <script type="application/ld+json">{{"datePublished":"2026-04-15"}}</script>
    </head><body>
      <nav>{'Navigation link ' * 80}</nav>
      <article><h1>Server supply outlook</h1>
      <p>{excerpt}</p>
      <p>Component allocation remains uneven and shipment growth can lag demand.</p>
      <p>Independent industry tracking provides a market-level view, not a Dell allocation.</p>
      <p>Additional detail keeps this synthetic fixture above the minimum useful article size.</p>
      <p>{'Supply context and market evidence remain speaker bound. ' * 8}</p>
      </article>
    </body></html>
    """
    source = compile_public_html_source_object(
        response_capture=_capture(html, url="https://example.com/research"),
        source_spec=_source_spec(),
        capture_ref="capture://trendforce",
        capture_sha256="b" * 64,
    )

    assert source["status"] == "captured_public_source_compiled_not_evidence"
    assert source["parse_quality_receipt"][
        "bound_publication_date_present_in_json_ld"
    ] is True
    assert "Navigation link" not in json.dumps(source)
    assert source["authority"]["candidate_not_evidence"] is True

    candidate = compile_public_context_candidate(
        source_object=source,
        candidate_spec={
            "proposition_id": "PROP::SERVER_SUPPLY_CONSTRAINT",
            "excerpt": excerpt,
            "claim_use": "industry_exact_fact",
            "speaker_bound": True,
            "subject_bound": True,
            "independent_source_count": 1,
            "license_entitled": False,
        },
        source_use_policy=_policy(),
    )
    assert candidate["source_use_decision"]["evidence_promotion_allowed"] is True
    assert candidate["candidate_not_evidence"] is True
    assert candidate["evidence_admission_required"] is True


def test_public_context_cannot_create_target_numeric_authority() -> None:
    excerpt = "Industry server spending grew while unit growth remained modest."
    html = (
        "<html><body><article>"
        f"<p>{excerpt}</p>"
        f"<p>{'Market context remains distinct from issuer facts. ' * 15}</p>"
        "</article></body></html>"
    )
    source = compile_public_html_source_object(
        response_capture=_capture(html, url="https://example.com/research"),
        source_spec=_source_spec(),
        capture_ref="capture://industry",
        capture_sha256="c" * 64,
    )
    candidate = compile_public_context_candidate(
        source_object=source,
        candidate_spec={
            "proposition_id": "PROP::DELL_EXACT_REVENUE",
            "excerpt": excerpt,
            "claim_use": "target_company_exact_numeric_fact",
            "speaker_bound": True,
            "subject_bound": True,
            "independent_source_count": 1,
        },
        source_use_policy=_policy(),
    )

    assert candidate["source_use_decision"]["evidence_promotion_allowed"] is False
    assert "claim_use_not_allowed_for_source_class" in candidate[
        "source_use_decision"
    ]["blockers"]
    assert candidate["target_company_exact_numeric_authority"] is False


def test_public_context_rejects_post_as_of_source() -> None:
    html = (
        "<html><body><article>"
        f"<p>{'Post-as-of context must not enter a point-in-time case. ' * 15}</p>"
        "</article></body></html>"
    )
    with pytest.raises(
        PublicContextSourceError,
        match="public_context_source_spec_invalid",
    ):
        compile_public_html_source_object(
            response_capture=_capture(html, url="https://example.com/research"),
            source_spec=_source_spec(publication_date="2026-08-18"),
            capture_ref="capture://late",
            capture_sha256="d" * 64,
        )


def test_publication_date_uses_original_page_not_provider_telemetry() -> None:
    html = """
    <html><head>
      <meta property="article:published_time" content="2026-04-15T09:00:00Z">
    </head><body><article><p>Original source body.</p></article></body></html>
    """
    receipt = adjudicate_publication_date_from_capture(
        response_capture=_capture(html, url="https://example.com/research"),
        research_as_of="2026-08-06",
        provider_date_telemetry="2026-06-30",
    )

    assert receipt["status"] == "resolved_from_original_source"
    assert receipt["selected_publication_date"] == "2026-04-15"
    assert receipt["provider_date_is_authority"] is False
    assert receipt["provider_date_corroborates_selected"] is False


def test_publication_date_does_not_promote_provider_date_without_original() -> None:
    receipt = adjudicate_publication_date_from_capture(
        response_capture=_capture(
            "<html><body><article><p>No original date.</p></article></body></html>",
            url="https://example.com/research",
        ),
        research_as_of="2026-08-06",
        provider_date_telemetry="2026-04-15",
    )

    assert receipt["status"] == "unresolved_original_publication_date"
    assert receipt["selected_publication_date"] is None


def test_public_pdf_compiler_emits_candidate_only_segments(monkeypatch) -> None:
    class _FakePage:
        def extract_text(self) -> str:
            return (
                "Dell AI server configuration and supply context remain speaker bound. "
                * 16
            )

    class _FakeReader:
        def __init__(self, _stream) -> None:
            self.pages = [_FakePage(), _FakePage()]
            self.metadata = {"/Title": "Captured public PDF"}

    monkeypatch.setattr(
        "retrieval.public_context_source.PdfReader",
        _FakeReader,
    )
    body = b"%PDF-1.7\nsynthetic bounded fixture"
    response_capture = {
        **_capture("unused", url="https://example.com/research.pdf"),
        "headers": {"content-type": "application/pdf"},
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "body_bytes": len(body),
    }
    source_spec = {
        **_source_spec(),
        "source_url": "https://example.com/research.pdf",
        "source_type": "PUBLIC_ANALYST_PDF",
        "segment_character_target": 800,
    }

    source = compile_public_pdf_source_object(
        response_capture=response_capture,
        source_spec=source_spec,
        capture_ref="capture://pdf",
        capture_sha256="e" * 64,
    )

    assert source["status"] == "captured_public_source_compiled_not_evidence"
    assert source["parse_quality_receipt"]["ocr_executed"] is False
    assert source["segments"]
    assert all(row["candidate_not_evidence"] for row in source["segments"])
