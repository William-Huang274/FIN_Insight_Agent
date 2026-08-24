from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

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


def _pdf_capture(
    visible_text: str,
    *,
    url: str,
    creation_date: str,
) -> dict:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    escaped = (
        visible_text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
    stream.set_data(
        f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1")
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    writer.add_metadata({"/CreationDate": creation_date})
    output = BytesIO()
    writer.write(output)
    body = output.getvalue()
    assert visible_text in (PdfReader(BytesIO(body)).pages[0].extract_text() or "")
    return {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "capture_kind": "source_response",
        "case_key": "DELL",
        "route_id": "ROUTE::DELL-IR-PDF",
        "request_capture_ref": "sha256://request",
        "request_capture_digest": "a" * 64,
        "status_code": 200,
        "final_url": url,
        "headers": {"content-type": "application/pdf"},
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


def test_pdf_visible_release_date_outranks_later_file_creation_metadata() -> None:
    receipt = adjudicate_publication_date_from_capture(
        response_capture=_pdf_capture(
            "Dell Technologies release March 18, 2025",
            url="https://investors.delltechnologies.com/node/17471/pdf",
            creation_date="D:20260606000000Z",
        ),
        research_as_of="2026-08-06",
        provider_date_telemetry="2025-03-18",
    )

    assert receipt["status"] == "resolved_from_original_source"
    assert receipt["selected_publication_date"] == "2025-03-18"
    assert receipt["provider_date_corroborates_selected"] is True
    assert receipt["original_source_candidates"] == [
        {
            "date": "2025-03-18",
            "source": "original_pdf_visible_header_date",
            "priority": 1,
            "after_research_as_of": False,
        },
        {
            "date": "2026-06-06",
            "source": "original_pdf_creation_date",
            "priority": 2,
            "after_research_as_of": False,
        },
    ]


def test_pdf_context_dates_beyond_header_do_not_override_file_date() -> None:
    receipt = adjudicate_publication_date_from_capture(
        response_capture=_pdf_capture(
            "Technical study without a visible release date in its title. "
            + "Scope and configuration context. " * 12
            + "Research concluded March 27, 2025 and prices changed June 27, 2025.",
            url="https://example.com/technical-study.pdf",
            creation_date="D:20250723000000Z",
        ),
        research_as_of="2026-08-06",
    )

    assert receipt["status"] == "resolved_from_original_source"
    assert receipt["selected_publication_date"] == "2025-07-23"
    assert receipt["original_source_candidates"] == [
        {
            "date": "2025-07-23",
            "source": "original_pdf_creation_date",
            "priority": 2,
            "after_research_as_of": False,
        }
    ]


def test_publication_date_recovers_visible_month_name_date_marker() -> None:
    html = """
    <html><body><article>
      <div class="published-date">June 22, 2026</div>
      <p>Original source body.</p>
    </article></body></html>
    """
    receipt = adjudicate_publication_date_from_capture(
        response_capture=_capture(html, url="https://example.com/research"),
        research_as_of="2026-08-06",
        provider_date_telemetry="2026-06-30",
    )

    assert receipt["status"] == "resolved_from_original_source"
    assert receipt["selected_publication_date"] == "2026-06-22"
    assert receipt["original_source_candidates"] == [
        {
            "date": "2026-06-22",
            "source": "original_html_article_scoped_visible_date",
            "priority": 1,
            "after_research_as_of": False,
        },
        {
            "date": "2026-06-22",
            "source": "original_html_visible_date_marker",
            "priority": 3,
            "after_research_as_of": False,
        }
    ]


def test_article_scoped_date_wins_over_related_story_dates() -> None:
    html = """
    <html><body>
      <div class="article">
        <h1>Dell and NVIDIA product availability</h1>
        <div class="article-date">August 22, 2023</div>
        <div class="article-body">
          <div>Dell PowerEdge systems will support the announced NVIDIA platform.</div>
          <div>Availability is described by the named supplier and system maker.</div>
          <div>Additional bounded article text keeps the body independently useful.</div>
          <div>Relationship context remains speaker bound and does not imply allocation.</div>
          <div>{}</div>
        </div>
      </div>
      <aside class="more-news">
        <span class="index-item-text-info-date">August 17, 2026</span>
        <span class="index-item-text-info-date">August 10, 2026</span>
      </aside>
    </body></html>
    """.format("Supplier relationship context. " * 20)
    receipt = adjudicate_publication_date_from_capture(
        response_capture=_capture(html, url="https://example.com/article"),
        research_as_of="2026-08-06",
    )

    assert receipt["status"] == "resolved_from_original_source"
    assert receipt["selected_publication_date"] == "2023-08-22"
    assert any(
        row["source"] == "original_html_article_scoped_visible_date"
        and row["date"] == "2023-08-22"
        for row in receipt["original_source_candidates"]
    )


def test_publication_date_recovers_publisheddate_meta_variant() -> None:
    html = """
    <html><head><meta name="publishedDate" content="May 26, 2026, 5:35 PM EDT"></head>
    <body><main><p>Captured article body.</p></main></body></html>
    """
    receipt = adjudicate_publication_date_from_capture(
        response_capture=_capture(html, url="https://example.com/article"),
        research_as_of="2026-08-06",
    )

    assert receipt["status"] == "resolved_from_original_source"
    assert receipt["selected_publication_date"] == "2026-05-26"


def test_public_article_compiler_uses_scoped_div_text_without_related_noise() -> None:
    html = """
    <html><body>
      <div class="global-navigation">{}</div>
      <div class="module module-news-details">
        <div class="module-date">April 15, 2026</div>
        <div class="module_body">
          <div>Blackwell product shipments increased sequentially in the reported quarter.</div>
          <div>Supplier commentary described product availability and demand conditions.</div>
          <div>Dell was named as a platform builder, which proves a relationship but not allocation.</div>
          <div>Capacity and shipment timing remain bound to the supplier disclosure.</div>
          <div>{}</div>
        </div>
      </div>
      <div class="related-news">{}</div>
    </body></html>
    """.format(
        "Navigation link " * 100,
        "Captured supplier context remains bounded. " * 30,
        "Unrelated future story " * 100,
    )
    source = compile_public_html_source_object(
        response_capture=_capture(html, url="https://example.com/research"),
        source_spec=_source_spec(),
        capture_ref="capture://div-article",
        capture_sha256="f" * 64,
    )

    rendered = json.dumps(source)
    assert source["parse_quality_receipt"]["text_node_fallback_used"] is True
    assert source["parse_quality_receipt"]["visible_text_characters"] >= 500
    assert "Captured supplier context" in rendered
    assert "Navigation link" not in rendered
    assert "Unrelated future story" not in rendered


def test_public_article_compiler_preserves_article_wrapped_by_page_form() -> None:
    html = """
    <html><body><form id="aspnetForm">
      <header>Investor navigation</header>
      <div class="module module-news-details">
        <div class="module_body">
          <div>Blackwell sales increased while supply timing remained constrained.</div>
          <div>Dell was named as a system platform builder by the supplier.</div>
          <div>{}</div>
        </div>
      </div>
      <footer>Subscription controls</footer>
    </form></body></html>
    """.format("Captured investor relations disclosure. " * 30)
    source = compile_public_html_source_object(
        response_capture=_capture(html, url="https://example.com/research"),
        source_spec=_source_spec(),
        capture_ref="capture://aspnet-article",
        capture_sha256="1" * 64,
    )

    rendered = json.dumps(source)
    assert "Blackwell sales increased" in rendered
    assert "Investor navigation" not in rendered
    assert "Subscription controls" not in rendered


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
