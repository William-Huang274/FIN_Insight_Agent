from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import json
import re
from time import struct_time
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urljoin, urlsplit

import feedparser
from lxml import etree, html
from trafilatura import extract, extract_metadata


_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|"
    "November|December"
)
_MONTH_DATE_RE = re.compile(
    rf"\b(?P<month>{_MONTHS})\s+(?P<day>[0-3]?\d),\s*(?P<year>20\d{{2}})\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b")
_REPORTING_PERIOD_CONTEXT = (
    "quarter ended",
    "year ended",
    "fiscal year ended",
    "three months ended",
    "six months ended",
    "nine months ended",
    "period ended",
)
_PRESS_MASTHEAD_CONTEXT = (
    "today announced",
    "announced today",
    "news release",
    "press release",
    "immediate release",
)
_EVENT_CONTEXT = (
    "conference call",
    "earnings call",
    "webcast",
    "event",
    "presentation",
)


@dataclass(frozen=True)
class PublicationDateCandidate:
    date_value: str
    date_kind: str
    date_source: str
    date_confidence: str
    context_class: str

    def as_dict(self) -> dict[str, str]:
        return {
            "date_value": self.date_value,
            "date_kind": self.date_kind,
            "date_source": self.date_source,
            "date_confidence": self.date_confidence,
            "context_class": self.context_class,
        }


@dataclass(frozen=True)
class PublicationDateDecision:
    date_value: str
    date_kind: str
    date_source: str
    date_confidence: str
    capture_ref: str
    capture_digest: str
    conflict_status: str
    candidates: tuple[PublicationDateCandidate, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "date_value": self.date_value,
            "date_kind": self.date_kind,
            "date_source": self.date_source,
            "date_confidence": self.date_confidence,
            "capture_ref": self.capture_ref,
            "capture_digest": self.capture_digest,
            "conflict_status": self.conflict_status,
            "candidates": [row.as_dict() for row in self.candidates],
        }


@dataclass(frozen=True)
class OfficialLocatorCandidate:
    url: str
    title: str
    published_on: str
    date_kind: str
    date_source: str
    source_family: str
    endpoint_kind: str = "document"
    form_type: str = ""


@dataclass(frozen=True)
class ParsedOfficialHtml:
    title: str
    main_text: str
    publication_date: PublicationDateDecision
    document_locators: tuple[OfficialLocatorCandidate, ...]
    structured_endpoints: tuple[OfficialLocatorCandidate, ...]
    parser_versions: Mapping[str, str]


def parse_official_html_capture(
    *,
    body: bytes,
    final_url: str,
    headers: Mapping[str, Any],
    as_of: str,
    capture_ref: str,
    capture_digest: str,
) -> ParsedOfficialHtml:
    text = body.decode("utf-8", errors="replace")
    tree = _load_html(text, final_url)
    extracted = extract(
        text,
        url=final_url,
        output_format="txt",
        include_comments=False,
        include_tables=True,
        deduplicate=True,
        favor_precision=True,
    )
    main_text = " ".join((extracted or tree.text_content() or "").split())
    metadata = extract_metadata(
        text,
        default_url=final_url,
        date_config={
            "extensive_search": True,
            "original_date": True,
            "max_date": as_of,
        },
    )
    title = str(getattr(metadata, "title", "") or _tree_title(tree) or final_url)
    decision = extract_publication_date(
        html_text=text,
        final_url=final_url,
        headers=headers,
        as_of=as_of,
        capture_ref=capture_ref,
        capture_digest=capture_digest,
        trafilatura_date=str(getattr(metadata, "date", "") or ""),
    )
    documents, endpoints = _html_locator_candidates(tree, final_url)
    return ParsedOfficialHtml(
        title=title,
        main_text=main_text,
        publication_date=decision,
        document_locators=documents,
        structured_endpoints=endpoints,
        parser_versions={
            "feedparser": feedparser.__version__,
            "trafilatura": _trafilatura_version(),
        },
    )


def extract_publication_date(
    *,
    html_text: str,
    final_url: str,
    headers: Mapping[str, Any],
    as_of: str,
    capture_ref: str,
    capture_digest: str,
    trafilatura_date: str = "",
) -> PublicationDateDecision:
    tree = _load_html(html_text, final_url)
    visible_text = " ".join((tree.text_content() or "").split())
    candidates: list[PublicationDateCandidate] = []

    for value in _json_ld_values(tree, "datePublished"):
        _append_candidate(
            candidates,
            value=value,
            kind="published_date",
            source="json_ld_datePublished",
            confidence="high",
            context="explicit_publication_metadata",
        )
    for xpath, source in (
        ("//meta[@property='article:published_time']/@content", "open_graph_article_published_time"),
        ("//meta[@property='og:published_time']/@content", "open_graph_published_time"),
        ("//meta[@name='publishdate']/@content", "html_publishdate_meta"),
        ("//meta[@name='date']/@content", "html_date_meta"),
    ):
        for value in tree.xpath(xpath):
            _append_candidate(
                candidates,
                value=str(value),
                kind="published_date",
                source=source,
                confidence="high",
                context="explicit_publication_metadata",
            )

    event_page = any(token in urlsplit(final_url).path.lower() for token in ("/event", "/earnings/"))
    for element in tree.xpath("//time"):
        value = str(element.get("datetime") or " ".join(element.text_content().split()))
        element_context = " ".join(
            [
                str(element.get("class") or ""),
                str(element.get("itemprop") or ""),
                str(element.get("aria-label") or ""),
            ]
        ).lower()
        if not event_page and not any(token in element_context for token in ("publish", "release", "date")):
            continue
        _append_candidate(
            candidates,
            value=value,
            kind="event_date" if event_page else "published_date",
            source="semantic_html_time",
            confidence="high" if "publish" in element_context else "medium",
            context="explicit_event_or_publication_element",
        )

    for match in _MONTH_DATE_RE.finditer(visible_text):
        value = _month_match_to_iso(match)
        before = visible_text[max(0, match.start() - 90) : match.start()].lower()
        after = visible_text[match.end() : match.end() + 140].lower()
        context = f"{before} {after}"
        if any(token in before[-45:] for token in _REPORTING_PERIOD_CONTEXT):
            context_class = "reporting_period"
            kind = "reporting_period_end"
            source = "body_reporting_period"
            confidence = "rejected"
        elif any(token in context for token in _PRESS_MASTHEAD_CONTEXT) or _masthead_punctuation(before, after):
            context_class = "official_release_masthead"
            kind = "published_date"
            source = "official_release_masthead"
            confidence = "high"
        elif _weekday_near(before) and (event_page or any(token in context for token in _EVENT_CONTEXT)):
            context_class = "official_event_heading"
            kind = "event_date"
            source = "official_event_heading"
            confidence = "high"
        else:
            continue
        _append_candidate(
            candidates,
            value=value,
            kind=kind,
            source=source,
            confidence=confidence,
            context=context_class,
        )

    if trafilatura_date:
        context_class = _context_for_date(visible_text, trafilatura_date)
        _append_candidate(
            candidates,
            value=trafilatura_date,
            kind=("reporting_period_end" if context_class == "reporting_period" else "published_date"),
            source="trafilatura_inferred_date",
            confidence=("rejected" if context_class == "reporting_period" else "low"),
            context=context_class,
        )

    modified = _last_modified_date(headers)
    if modified:
        _append_candidate(
            candidates,
            value=modified,
            kind="modified_date",
            source="http_last_modified",
            confidence="low",
            context="transport_metadata_only",
        )

    unique = _dedupe_candidates(candidates)
    eligible = [
        row
        for row in unique
        if row.date_confidence in {"high", "medium"}
        and row.date_kind in {"published_date", "event_date"}
    ]
    high_values = {
        row.date_value for row in eligible if row.date_confidence == "high"
    }
    if len(high_values) > 1:
        return PublicationDateDecision(
            date_value="",
            date_kind="",
            date_source="",
            date_confidence="",
            capture_ref=capture_ref,
            capture_digest=capture_digest,
            conflict_status="publication_date_conflict",
            candidates=tuple(unique),
        )
    priority = {"high": 0, "medium": 1, "low": 2}
    source_priority = {
        "json_ld_datePublished": 0,
        "open_graph_article_published_time": 1,
        "open_graph_published_time": 2,
        "html_publishdate_meta": 3,
        "html_date_meta": 4,
        "official_release_masthead": 5,
        "semantic_html_time": 6,
        "official_event_heading": 7,
        "trafilatura_inferred_date": 8,
    }
    ordered = sorted(
        eligible,
        key=lambda row: (
            priority[row.date_confidence],
            source_priority.get(row.date_source, 99),
            row.date_value,
        ),
    )
    if not ordered:
        return PublicationDateDecision(
            date_value="",
            date_kind="modified_date" if modified else "",
            date_source="http_last_modified" if modified else "",
            date_confidence="low" if modified else "",
            capture_ref=capture_ref,
            capture_digest=capture_digest,
            conflict_status="publication_date_unproven",
            candidates=tuple(unique),
        )
    selected = ordered[0]
    if date.fromisoformat(selected.date_value) > date.fromisoformat(as_of):
        conflict_status = "publication_date_after_as_of"
    else:
        conflict_status = "none"
    return PublicationDateDecision(
        date_value=selected.date_value,
        date_kind=selected.date_kind,
        date_source=selected.date_source,
        date_confidence=selected.date_confidence,
        capture_ref=capture_ref,
        capture_digest=capture_digest,
        conflict_status=conflict_status,
        candidates=tuple(unique),
    )


def parse_feed_capture(
    *, body: bytes, base_url: str, allowed_hosts: Sequence[str]
) -> tuple[OfficialLocatorCandidate, ...]:
    parsed = feedparser.parse(body)
    if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", None):
        return ()
    allowed = {str(value).lower() for value in allowed_hosts}
    rows: list[OfficialLocatorCandidate] = []
    for entry in parsed.entries:
        link = urljoin(base_url, str(entry.get("link") or ""))
        if not _allowed_https(link, allowed):
            continue
        published = _feed_date(entry.get("published_parsed"))
        source = "feed_published"
        if not published:
            published = _feed_date(entry.get("updated_parsed"))
            source = "feed_updated"
        rows.append(
            OfficialLocatorCandidate(
                url=link,
                title=" ".join(str(entry.get("title") or link).split()),
                published_on=published,
                date_kind="published_date" if published else "",
                date_source=source if published else "",
                source_family=_infer_structured_source_family(link),
            )
        )
    return _dedupe_locators(rows)


def parse_sitemap_capture(
    *, body: bytes, base_url: str, allowed_hosts: Sequence[str]
) -> tuple[OfficialLocatorCandidate, ...]:
    allowed = {str(value).lower() for value in allowed_hosts}
    try:
        root = etree.fromstring(
            body,
            parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=False),
        )
    except (etree.XMLSyntaxError, ValueError):
        return ()
    local_name = etree.QName(root).localname.lower()
    rows: list[OfficialLocatorCandidate] = []
    for node in root.xpath("//*[local-name()='url' or local-name()='sitemap']"):
        locations = node.xpath("./*[local-name()='loc']/text()")
        if not locations:
            continue
        locator = urljoin(base_url, str(locations[0]).strip())
        if not _allowed_https(locator, allowed):
            continue
        lastmods = node.xpath("./*[local-name()='lastmod']/text()")
        is_endpoint = etree.QName(node).localname.lower() == "sitemap" or local_name == "sitemapindex"
        rows.append(
            OfficialLocatorCandidate(
                url=locator,
                title=locator,
                published_on="",
                date_kind="modified_date" if lastmods else "",
                date_source="sitemap_lastmod" if lastmods else "",
                source_family=("issuer_structured_discovery" if is_endpoint else _infer_structured_source_family(locator)),
                endpoint_kind="sitemap" if is_endpoint else "document",
            )
        )
    return _dedupe_locators(rows)


def parse_robots_capture(
    *, body: bytes, base_url: str, allowed_hosts: Sequence[str]
) -> tuple[OfficialLocatorCandidate, ...]:
    allowed = {str(value).lower() for value in allowed_hosts}
    rows: list[OfficialLocatorCandidate] = []
    for line in body.decode("utf-8", errors="replace").splitlines():
        if not line.lower().startswith("sitemap:"):
            continue
        locator = urljoin(base_url, line.split(":", 1)[1].strip())
        if _allowed_https(locator, allowed):
            rows.append(
                OfficialLocatorCandidate(
                    url=locator,
                    title="Official sitemap",
                    published_on="",
                    date_kind="",
                    date_source="robots_sitemap_declaration",
                    source_family="issuer_structured_discovery",
                    endpoint_kind="sitemap",
                )
            )
    return _dedupe_locators(rows)


def _html_locator_candidates(
    tree: html.HtmlElement, base_url: str
) -> tuple[tuple[OfficialLocatorCandidate, ...], tuple[OfficialLocatorCandidate, ...]]:
    allowed_host = (urlsplit(base_url).hostname or "").lower()
    documents: list[OfficialLocatorCandidate] = []
    endpoints: list[OfficialLocatorCandidate] = []
    for element in tree.xpath("//a[@href] | //link[@href]"):
        locator = urljoin(base_url, str(element.get("href") or "").strip())
        if not _allowed_https(locator, {allowed_host}):
            continue
        rel = " ".join(str(element.get("rel") or "").lower().split())
        media_type = str(element.get("type") or "").lower()
        title = " ".join(
            str(element.get("title") or element.get("aria-label") or element.text_content() or locator).split()
        )
        endpoint_kind = ""
        if "alternate" in rel and any(token in media_type for token in ("rss", "atom", "feed+json")):
            endpoint_kind = "feed"
        elif "sitemap" in rel or locator.lower().endswith(("sitemap.xml", ".rss", ".atom")):
            endpoint_kind = "sitemap" if "sitemap" in locator.lower() else "feed"
        if endpoint_kind:
            endpoints.append(
                OfficialLocatorCandidate(
                    url=locator,
                    title=title,
                    published_on="",
                    date_kind="",
                    date_source="html_structured_endpoint",
                    source_family="issuer_structured_discovery",
                    endpoint_kind=endpoint_kind,
                )
            )
            continue
        anchor_date = str(
            element.get("data-date")
            or element.get("data-published-on")
            or ""
        )
        documents.append(
            OfficialLocatorCandidate(
                url=locator,
                title=title,
                published_on=anchor_date,
                date_kind="published_date" if anchor_date else "",
                date_source="html_anchor_metadata" if anchor_date else "",
                source_family=_infer_structured_source_family(locator),
            )
        )
    return _dedupe_locators(documents), _dedupe_locators(endpoints)


def _load_html(text: str, base_url: str) -> html.HtmlElement:
    try:
        tree = html.fromstring(text, base_url=base_url)
    except (etree.ParserError, ValueError):
        tree = html.fromstring("<html></html>", base_url=base_url)
    return tree


def _tree_title(tree: html.HtmlElement) -> str:
    values = tree.xpath("//title/text()")
    return " ".join(str(values[0]).split()) if values else ""


def _json_ld_values(tree: html.HtmlElement, key: str) -> tuple[str, ...]:
    values: list[str] = []
    for raw in tree.xpath("//script[@type='application/ld+json']/text()"):
        try:
            payload = json.loads(str(raw))
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        for row in _walk_json(payload):
            value = row.get(key)
            if isinstance(value, str):
                values.append(value)
    return tuple(values)


def _walk_json(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for nested in value.values():
            yield from _walk_json(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_json(nested)


def _append_candidate(
    rows: list[PublicationDateCandidate],
    *,
    value: str,
    kind: str,
    source: str,
    confidence: str,
    context: str,
) -> None:
    normalized = _normalize_date(value)
    if normalized:
        rows.append(
            PublicationDateCandidate(
                date_value=normalized,
                date_kind=kind,
                date_source=source,
                date_confidence=confidence,
                context_class=context,
            )
        )


def _normalize_date(value: str) -> str:
    text = str(value or "").strip()
    iso = _ISO_DATE_RE.search(text)
    if iso:
        candidate = "-".join(iso.groups())
    else:
        month = _MONTH_DATE_RE.search(text)
        candidate = _month_match_to_iso(month) if month else ""
    if not candidate:
        return ""
    try:
        return date.fromisoformat(candidate).isoformat()
    except ValueError:
        return ""


def _month_match_to_iso(match: re.Match[str]) -> str:
    parsed = datetime.strptime(
        f"{match.group('month')} {match.group('day')}, {match.group('year')}",
        "%B %d, %Y",
    )
    return parsed.date().isoformat()


def _context_for_date(text: str, iso_date: str) -> str:
    parsed = date.fromisoformat(iso_date)
    forms = (
        iso_date,
        f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}",
    )
    lower = text.lower()
    for form in forms:
        index = lower.find(form.lower())
        if index < 0:
            continue
        before = lower[max(0, index - 60) : index]
        if any(token in before for token in _REPORTING_PERIOD_CONTEXT):
            return "reporting_period"
    return "library_inferred_untyped"


def _masthead_punctuation(before: str, after: str) -> bool:
    left = before.rstrip()
    right = after.lstrip()
    dash_chars = ("—", "–", "-", "�")
    return any(left.endswith(token) for token in dash_chars) and any(
        right.startswith(token) for token in dash_chars
    )


def _weekday_near(before: str) -> bool:
    return any(
        before.rstrip().endswith(value)
        for value in (
            "monday,",
            "tuesday,",
            "wednesday,",
            "thursday,",
            "friday,",
            "saturday,",
            "sunday,",
        )
    )


def _last_modified_date(headers: Mapping[str, Any]) -> str:
    value = str(headers.get("last-modified") or headers.get("Last-Modified") or "")
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _feed_date(value: struct_time | None) -> str:
    if value is None:
        return ""
    try:
        return date(value.tm_year, value.tm_mon, value.tm_mday).isoformat()
    except (TypeError, ValueError, AttributeError):
        return ""


def _dedupe_candidates(
    rows: Sequence[PublicationDateCandidate],
) -> list[PublicationDateCandidate]:
    seen: set[tuple[str, str, str, str, str]] = set()
    out: list[PublicationDateCandidate] = []
    for row in rows:
        key = (
            row.date_value,
            row.date_kind,
            row.date_source,
            row.date_confidence,
            row.context_class,
        )
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def _dedupe_locators(
    rows: Sequence[OfficialLocatorCandidate],
) -> tuple[OfficialLocatorCandidate, ...]:
    out: dict[str, OfficialLocatorCandidate] = {}
    for row in rows:
        key = row.url.rstrip("/").lower()
        out.setdefault(key, row)
    return tuple(out[key] for key in sorted(out))


def _allowed_https(url: str, allowed_hosts: set[str]) -> bool:
    split = urlsplit(url)
    return split.scheme.lower() == "https" and (split.hostname or "").lower() in allowed_hosts


def _infer_structured_source_family(url: str) -> str:
    path = urlsplit(url).path.lower()
    if "/customers/" in path or "/customer" in path:
        return "customer_official_disclosure"
    if any(token in path for token in ("/earnings/", "/results", "/news/", "/events/")):
        return "issuer_ir_document"
    return "issuer_official_page"


def _trafilatura_version() -> str:
    try:
        from importlib.metadata import version

        return version("trafilatura")
    except Exception:
        return "unknown"


__all__ = [
    "OfficialLocatorCandidate",
    "ParsedOfficialHtml",
    "PublicationDateCandidate",
    "PublicationDateDecision",
    "extract_publication_date",
    "parse_feed_capture",
    "parse_official_html_capture",
    "parse_robots_capture",
    "parse_sitemap_capture",
]
