from __future__ import annotations

import ast
import hashlib
import json
import re
from html import unescape
from typing import Any, Mapping


PUBLIC_WEB_CONTEXT_PARSER_SCHEMA_VERSION = "finsight_public_web_context_parser_v0_1"


def parse_public_web_context_rows(
    *,
    ticker: str,
    parent_evidence_ref: str,
    url: str,
    source_class: str,
    repair_type: str,
    analysis_dimension: str,
    title: str,
    body: str,
    content_type: str,
    as_of_datetime: str,
    citation: Mapping[str, Any],
    source_layer_meta: Mapping[str, Any],
    claim_boundary: str,
    authority_boundary: str,
    repair: Mapping[str, Any] | None = None,
    max_rows: int = 12,
) -> list[dict[str, Any]]:
    """Parse allowed public web snapshots into bounded context/proxy rows."""
    text = _visible_text(body, content_type=content_type)
    repair = repair or {}
    facts: list[dict[str, Any]] = []
    facts.extend(_json_context_facts(body, content_type=content_type, repair=repair, source_class=source_class))
    facts.extend(_json_ld_context_facts(body, source_class=source_class, repair_type=repair_type))
    facts.extend(_commerce_microdata_context_facts(body, source_class=source_class))
    facts.extend(_article_context_facts(body, text=text, source_class=source_class, repair_type=repair_type))
    facts.extend(_table_context_facts(body, content_type=content_type, repair_type=repair_type, source_class=source_class))
    if repair_type == "product_surface":
        facts.extend(_product_context_facts(text, repair=repair))
    elif repair_type == "market_proxy":
        facts.extend(_sentence_context_facts(text, repair_type=repair_type, keywords=_MARKET_PROXY_KEYWORDS, fact_type="market_proxy_context"))
    elif repair_type == "supply_chain":
        facts.extend(_sentence_context_facts(text, repair_type=repair_type, keywords=_SUPPLY_CHAIN_KEYWORDS, fact_type="supply_chain_relationship_context"))
    elif repair_type == "capital_ownership":
        facts.extend(_sentence_context_facts(text, repair_type=repair_type, keywords=_CAPITAL_KEYWORDS, fact_type="capital_ownership_context"))
    elif repair_type in {"issuer_official", "local_filing"}:
        facts.extend(_sentence_context_facts(text, repair_type=repair_type, keywords=_ISSUER_DISCLOSURE_KEYWORDS, fact_type="official_disclosure_context"))

    rows: list[dict[str, Any]] = []
    for index, fact in enumerate(_dedupe_facts(facts)[: max(0, int(max_rows or 0))], start=1):
        rows.append(
            _context_row_from_fact(
                fact,
                ticker=ticker,
                parent_evidence_ref=parent_evidence_ref,
                index=index,
                url=url,
                source_class=source_class,
                repair_type=repair_type,
                analysis_dimension=analysis_dimension,
                title=title,
                as_of_datetime=as_of_datetime,
                citation=citation,
                source_layer_meta=source_layer_meta,
                claim_boundary=claim_boundary,
                authority_boundary=authority_boundary,
                repair=repair,
            )
        )
    return rows


def _context_row_from_fact(
    fact: Mapping[str, Any],
    *,
    ticker: str,
    parent_evidence_ref: str,
    index: int,
    url: str,
    source_class: str,
    repair_type: str,
    analysis_dimension: str,
    title: str,
    as_of_datetime: str,
    citation: Mapping[str, Any],
    source_layer_meta: Mapping[str, Any],
    claim_boundary: str,
    authority_boundary: str,
    repair: Mapping[str, Any],
) -> dict[str, Any]:
    fact_type = str(fact.get("fact_type") or "bounded_context_fact")
    label = str(fact.get("fact_label") or fact_type).strip()
    value = str(fact.get("fact_value") or "").strip()
    summary = _compact_text(str(fact.get("structured_context_summary") or f"{label}: {value}").strip(), 520)
    fact_id = hashlib.sha1(
        "|".join([parent_evidence_ref, fact_type, label, value, str(index)]).encode("utf-8", errors="ignore")
    ).hexdigest()[:12]
    evidence_ref = f"{parent_evidence_ref}:parsed:{fact_type}:{fact_id}"
    meta = dict(source_layer_meta or {})
    meta.update(
        {
            "parser_status": "source_specific_context_parser_pass",
            "structured_fact_status": "bounded_context_fact_materialized",
            "evidence_graph_status": "runtime_ready_context",
            "can_support_company_exact_fact": False,
        }
    )
    metric_leads = _unique_strings([*(fact.get("metric_leads") or []), *(repair.get("metric_leads") or []), *(repair.get("official_metric_leads") or [])])[:8]
    entity_binding = _entity_binding_for_fact(
        fact,
        ticker=ticker,
        url=url,
        title=title,
        source_class=source_class,
        repair_type=repair_type,
        repair=repair,
    )
    row = {
        "schema_version": PUBLIC_WEB_CONTEXT_PARSER_SCHEMA_VERSION,
        "evidence_ref": evidence_ref,
        "evidence_id": evidence_ref,
        "parent_evidence_ref": parent_evidence_ref,
        "source_family": "live_public_web_context",
        **meta,
        "source_specific_parser": "public_web_context_parser_v0_1",
        "bounded_structured_context": True,
        "retrieval_route": "live_public_web_context",
        "source_class": source_class,
        "repair_type": repair_type,
        "analysis_dimension": analysis_dimension,
        "claim_types": _claim_types_for_fact(fact, repair_type=repair_type),
        "ticker": ticker,
        "topic": label,
        "fact_type": fact_type,
        "structured_context_type": fact_type,
        "fact_label": label,
        "fact_value": value,
        "structured_context_summary": summary,
        "product_family": str(fact.get("product_family") or "").strip(),
        "product_or_segment": str(fact.get("product_or_segment") or fact.get("product_family") or "").strip(),
        "metric_name": str(fact.get("metric_name") or "").strip(),
        "metric_leads": metric_leads,
        "entity_binding": entity_binding,
        "issuer_binding_status": entity_binding["issuer_binding_status"],
        "product_binding_status": entity_binding["product_binding_status"],
        "counterparty_binding_status": entity_binding["counterparty_binding_status"],
        "entity_binding_claim_boundary": entity_binding["binding_claim_boundary"],
        "table_headers": _unique_strings(fact.get("table_headers") or []),
        "table_row_values": _unique_strings(fact.get("table_row_values") or []),
        "url": url,
        "domain": _domain(url),
        "snapshot_id": evidence_ref,
        "snapshot_url": url,
        "as_of_datetime": as_of_datetime,
        "citation": dict(citation or {"url": url, "title": title}),
        "source_title": title,
        "preview": summary,
        "text": summary,
        "context_only": True,
        "lead_only": False,
        "exact_value_authority": False,
        "promotion_status": "bounded_context_fact_available",
        "source_claim_strength": _source_claim_strength(
            repair_type=repair_type,
            source_layer_id=str(meta.get("source_layer_id") or meta.get("source_layer") or ""),
        ),
        "authority_boundary": authority_boundary,
        "claim_boundary": claim_boundary,
        "parser_claim_boundary": _parser_claim_boundary(repair_type),
        "repair_id": repair.get("repair_id") or "",
    }
    for scalar_key in (
        "stars",
        "forks",
        "pushed_at",
        "latest",
        "modified",
        "downloads",
        "likes",
        "rating",
        "rating_count",
        "review_count",
        "rank",
        "price",
        "availability",
        "job_location",
        "job_department",
        "posted_at",
    ):
        if scalar_key in fact and str(fact.get(scalar_key)) != "":
            row[scalar_key] = fact.get(scalar_key)
    return row


def _entity_binding_for_fact(
    fact: Mapping[str, Any],
    *,
    ticker: str,
    url: str,
    title: str,
    source_class: str,
    repair_type: str,
    repair: Mapping[str, Any],
) -> dict[str, Any]:
    fact_text = " ".join(
        str(part or "")
        for part in [
            title,
            fact.get("fact_label"),
            fact.get("fact_value"),
            fact.get("structured_context_summary"),
            fact.get("product_family"),
            fact.get("product_or_segment"),
            " ".join(_unique_strings(fact.get("table_headers") or [])),
            " ".join(_unique_strings(fact.get("table_row_values") or [])),
        ]
    )
    text_lower = fact_text.lower()
    issuer_terms = _unique_strings(
        [
            ticker,
            repair.get("ticker"),
            repair.get("issuer"),
            repair.get("issuer_name"),
            repair.get("company_name"),
            *_repair_values(repair, "issuer_names"),
            *_repair_values(repair, "company_names"),
        ]
    )
    matched_issuer_terms = [term for term in issuer_terms if term and term.lower() in text_lower]
    domain = _domain(url)
    company_domains = {str(item).lower().strip() for item in repair.get("company_domains") or [] if str(item).strip()}
    company_domain_bound = bool(company_domains) and any(domain == item or domain.endswith("." + item) for item in company_domains)
    if matched_issuer_terms:
        issuer_binding_status = "issuer_mentioned_in_snapshot"
    elif source_class.startswith("company") and company_domain_bound:
        issuer_binding_status = "company_domain_bound"
    elif ticker:
        issuer_binding_status = "repair_plan_ticker_bound_unverified_in_snapshot"
    else:
        issuer_binding_status = "unbound"

    product_terms = _unique_strings(
        [
            fact.get("product_family"),
            fact.get("product_or_segment"),
            *_repair_values(repair, "official_product_surfaces"),
            *_repair_values(repair, "product_terms"),
            *_repair_values(repair, "product_names"),
        ]
    )
    matched_product_terms = [term for term in product_terms if term and term.lower() in text_lower]
    product_binding_status = "product_mentioned_in_snapshot" if matched_product_terms else "not_bound"

    counterparty_terms = _unique_strings(
        [
            *_repair_values(repair, "counterparties"),
            *_repair_values(repair, "customers"),
            *_repair_values(repair, "suppliers"),
            *_repair_values(repair, "partners"),
        ]
    )
    matched_counterparty_terms = [term for term in counterparty_terms if term and term.lower() in text_lower]
    relationship_keywords = {"customer", "supplier", "partner", "contract", "order", "deployment", "procurement"}
    if matched_counterparty_terms:
        counterparty_binding_status = "counterparty_mentioned_in_snapshot"
    elif repair_type == "supply_chain" or source_class in {"supplier_customer_official_news", "public_tender_or_contract_portal"}:
        counterparty_binding_status = "relationship_context_candidate"
    elif any(keyword in text_lower for keyword in relationship_keywords):
        counterparty_binding_status = "counterparty_keyword_context_candidate"
    else:
        counterparty_binding_status = "not_bound"

    return {
        "schema_version": "finsight_public_web_entity_binding_v0_1",
        "issuer_ticker": str(ticker or repair.get("ticker") or "").strip().upper(),
        "issuer_binding_status": issuer_binding_status,
        "issuer_matched_terms": matched_issuer_terms[:6],
        "product_binding_status": product_binding_status,
        "product_matched_terms": matched_product_terms[:6],
        "counterparty_binding_status": counterparty_binding_status,
        "counterparty_matched_terms": matched_counterparty_terms[:6],
        "source_entity_role": _source_entity_role(source_class=source_class, repair_type=repair_type),
        "binding_claim_boundary": (
            "Binding metadata routes context to specialists; it does not promote the row to issuer exact facts, "
            "product KPI authority, shipment, order-volume, sales, or market-share authority."
        ),
    }


def _repair_values(repair: Mapping[str, Any], key: str) -> list[str]:
    value = repair.get(key)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [str(item) for item in value.values() if str(item).strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _source_entity_role(*, source_class: str, repair_type: str) -> str:
    if source_class in {"supplier_customer_official_news", "company_customer_page", "company_supplier_page", "official_partner_directory"}:
        return "supplier_customer_or_partner_context"
    if source_class in {"company_product_page", "company_product_documentation", "company_support_documentation", "official_app_store_or_marketplace"}:
        return "product_or_platform_context"
    if source_class in {"mainstream_financial_news_article", "official_statistics_dataset", "industry_association_dataset"}:
        return "trusted_event_or_industry_context"
    if source_class in {"ecommerce_major_platform", "channel_pricing_snapshot"}:
        return "channel_offer_proxy_context"
    if source_class in {"developer_ecosystem_snapshot", "job_posting_snapshot", "platform_review_or_ranking_snapshot"}:
        return "public_proxy_signal_context"
    if source_class in {"public_tender_or_contract_portal"}:
        return "public_order_or_procurement_lead"
    return f"{repair_type}_context"


def _json_context_facts(body: str, *, content_type: str, repair: Mapping[str, Any], source_class: str) -> list[dict[str, Any]]:
    stripped = body.strip()
    if "json" not in content_type.lower() and not stripped.startswith(("{", "[")):
        return []
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return []
    facts: list[dict[str, Any]] = []
    if not isinstance(payload, Mapping):
        return facts
    facts.extend(_developer_or_marketplace_json_facts(payload, source_class=source_class))
    filings = payload.get("filings") if isinstance(payload.get("filings"), Mapping) else {}
    name = str(payload.get("name") or payload.get("companyName") or "").strip()
    if name and (filings or payload.get("cik") or payload.get("cik_str")):
        facts.append(
            {
                "fact_type": "official_issuer_identity_context",
                "fact_label": "official issuer identity",
                "fact_value": name,
                "structured_context_summary": f"Official source identifies issuer as {name}.",
                "metric_leads": ["issuer identity", "filing coverage"],
                "claim_types": ["official_issuer_context", "issuer_filing_presence", "verification_lead"],
            }
        )
    recent = filings.get("recent") if isinstance(filings.get("recent"), Mapping) else {}
    forms = _list_values(recent.get("form"))
    dates = _list_values(recent.get("filingDate"))
    accessions = _list_values(recent.get("accessionNumber"))
    targets = {str(item).upper() for item in repair.get("target_forms") or [] if str(item).strip()}
    if not targets:
        targets = {"10-K", "10-Q", "20-F", "40-F", "6-K", "8-K", "S-1", "S-3", "424B", "13F-HR", "3", "4", "5", "SC 13D", "SC 13G"}
    for idx, form in enumerate(forms[:40]):
        form_text = str(form).upper().strip()
        if not form_text or form_text not in targets:
            continue
        date = str(dates[idx] if idx < len(dates) else "").strip()
        accession = str(accessions[idx] if idx < len(accessions) else "").strip()
        facts.append(
            {
                "fact_type": "official_filing_presence_context",
                "fact_label": f"{form_text} filing presence",
                "fact_value": " ".join(part for part in [form_text, date, accession] if part),
                "structured_context_summary": _compact_text(
                    f"Official submissions source lists {form_text}"
                    f"{' filed on ' + date if date else ''}"
                    f"{' accession ' + accession if accession else ''}.",
                    420,
                ),
                "metric_leads": ["filing presence", "filing date", "accession number"],
                "claim_types": ["issuer_filing_presence", "official_disclosure_context", "verification_lead"],
            }
        )
        if len(facts) >= 8:
            break
    return facts


def _developer_or_marketplace_json_facts(payload: Mapping[str, Any], *, source_class: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    if "stargazers_count" in payload and "full_name" in payload:
        repo = str(payload.get("full_name") or "").strip()
        stars = _scalar_text(payload.get("stargazers_count"))
        forks = _scalar_text(payload.get("forks_count"))
        pushed_at = str(payload.get("pushed_at") or "").strip()
        facts.append(
            {
                "fact_type": "developer_ecosystem_context",
                "fact_label": repo or "GitHub repository",
                "fact_value": _compact_text(f"stars={stars}; forks={forks}; pushed_at={pushed_at}", 220),
                "structured_context_summary": _compact_text(
                    f"Public GitHub API context for {repo}: stars={stars}, forks={forks}, pushed_at={pushed_at}. "
                    "This is developer adoption/activity proxy only.",
                    420,
                ),
                "stars": stars,
                "forks": forks,
                "pushed_at": pushed_at,
                "metric_leads": ["stars", "forks", "pushed_at", "developer activity"],
                "claim_types": ["market_proxy_context", "developer_ecosystem_context", "verification_lead"],
            }
        )
    if ("dist-tags" in payload or "versions" in payload) and payload.get("name"):
        package = str(payload.get("name") or "").strip()
        dist_tags = payload.get("dist-tags") if isinstance(payload.get("dist-tags"), Mapping) else {}
        latest = str(dist_tags.get("latest") or "").strip()
        modified = ""
        times = payload.get("time") if isinstance(payload.get("time"), Mapping) else {}
        if times:
            modified = str(times.get("modified") or "").strip()
        facts.append(
            {
                "fact_type": "developer_package_context",
                "fact_label": package,
                "fact_value": _compact_text(f"latest={latest}; modified={modified}", 220),
                "structured_context_summary": _compact_text(
                    f"Public npm registry context for {package}: latest={latest}, modified={modified}. "
                    "This is package activity proxy only.",
                    420,
                ),
                "metric_leads": ["latest version", "modified date", "package activity"],
                "claim_types": ["market_proxy_context", "developer_ecosystem_context", "verification_lead"],
            }
        )
    info = payload.get("info") if isinstance(payload.get("info"), Mapping) else {}
    if info and (info.get("name") or info.get("version")):
        package = str(info.get("name") or "").strip()
        version = str(info.get("version") or "").strip()
        summary = str(info.get("summary") or "").strip()
        facts.append(
            {
                "fact_type": "developer_package_context",
                "fact_label": package or "PyPI package",
                "fact_value": _compact_text(f"version={version}; summary={summary}", 260),
                "structured_context_summary": _compact_text(
                    f"Public PyPI context for {package}: version={version}; {summary}. This is developer/package proxy only.",
                    420,
                ),
                "metric_leads": ["version", "package summary", "developer activity"],
                "claim_types": ["market_proxy_context", "developer_ecosystem_context", "verification_lead"],
            }
        )
    model_id = str(payload.get("modelId") or payload.get("id") or "").strip()
    if source_class == "developer_ecosystem_snapshot" and model_id and any(key in payload for key in ("downloads", "likes", "pipeline_tag")):
        downloads = str(payload.get("downloads") or "").strip()
        likes = str(payload.get("likes") or "").strip()
        pipeline = str(payload.get("pipeline_tag") or "").strip()
        facts.append(
            {
                "fact_type": "developer_ecosystem_context",
                "fact_label": model_id,
                "fact_value": _compact_text(f"downloads={downloads}; likes={likes}; pipeline={pipeline}", 220),
                "structured_context_summary": _compact_text(
                    f"Public HuggingFace API context for {model_id}: downloads={downloads}, likes={likes}, pipeline={pipeline}. "
                    "This is model/developer attention proxy only.",
                    420,
                ),
                "metric_leads": ["downloads", "likes", "pipeline tag", "developer activity"],
                "claim_types": ["market_proxy_context", "developer_ecosystem_context", "verification_lead"],
            }
        )
    results = payload.get("results") if isinstance(payload.get("results"), list) else []
    for result in results[:3]:
        if not isinstance(result, Mapping):
            continue
        app_name = str(result.get("trackName") or result.get("trackCensoredName") or "").strip()
        if not app_name:
            continue
        rating = str(result.get("averageUserRating") or "").strip()
        rating_count = str(result.get("userRatingCount") or "").strip()
        version = str(result.get("version") or "").strip()
        release_date = str(result.get("currentVersionReleaseDate") or result.get("releaseDate") or "").strip()
        facts.append(
            {
                "fact_type": "app_store_marketplace_context",
                "fact_label": app_name,
                "fact_value": _compact_text(f"rating={rating}; rating_count={rating_count}; version={version}; release_date={release_date}", 260),
                "structured_context_summary": _compact_text(
                    f"Public App Store lookup context for {app_name}: rating={rating}, rating_count={rating_count}, "
                    f"version={version}, release_date={release_date}. This is app marketplace proxy only.",
                    420,
                ),
                "metric_leads": ["rating", "rating count", "version", "release date", "app marketplace proxy"],
                "claim_types": ["market_proxy_context", "app_store_marketplace_context", "verification_lead"],
            }
        )
    return facts


def _json_ld_context_facts(body: str, *, source_class: str, repair_type: str) -> list[dict[str, Any]]:
    if "ld+json" not in body.lower():
        return []
    facts: list[dict[str, Any]] = []
    for raw_payload in re.findall(r"(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>", body)[:12]:
        try:
            payload = json.loads(unescape(raw_payload).strip())
        except json.JSONDecodeError:
            continue
        for item in _json_ld_items(payload):
            facts.extend(_json_ld_item_facts(item, source_class=source_class, repair_type=repair_type))
            if len(facts) >= 12:
                return facts
    return facts


def _commerce_microdata_context_facts(body: str, *, source_class: str) -> list[dict[str, Any]]:
    if source_class not in {"ecommerce_major_platform", "channel_pricing_snapshot", "platform_review_or_ranking_snapshot"}:
        return []
    tag_data = _cdw_tag_management_data(body)
    name = str(tag_data.get("product_name") or _itemprop_text(body, "name") or _meta_content(body, "og:title")).strip()
    sku = str(tag_data.get("product_id") or _itemprop_text(body, "sku") or "").strip()
    mpn = str(_itemprop_text(body, "mpn") or "").strip()
    brand = str(tag_data.get("product_root_brand_name") or tag_data.get("product_brand_name") or _itemprop_text(body, "brand") or "").strip()
    price = str(tag_data.get("product_price") or _itemprop_content(body, "price") or "").strip()
    currency = str(_itemprop_content(body, "priceCurrency") or "").strip()
    availability = str(tag_data.get("product_stock_status") or _itemprop_content(body, "availability") or "").strip()
    if availability.startswith("http"):
        availability = availability.rsplit("/", 1)[-1]
    facts: list[dict[str, Any]] = []
    if source_class in {"ecommerce_major_platform", "channel_pricing_snapshot"} and (
        name or sku or mpn or price or availability
    ):
        facts.append(
            {
                "fact_type": "channel_offer_context",
                "fact_label": name or sku or mpn or "channel offer",
                "fact_value": _compact_text(
                    f"brand={brand}; sku={sku}; mpn={mpn}; price={price} {currency}; availability={availability}",
                    320,
                ),
                "structured_context_summary": _compact_text(
                    f"Public channel/ecommerce offer context for {name or sku or mpn or 'product'}: "
                    f"brand={brand}, sku={sku or mpn}, price={price} {currency}, availability={availability}. "
                    "This is price/configuration/availability proxy only, not ASP, inventory, sell-through, sales, or share authority.",
                    520,
                ),
                "product_family": name,
                "product_or_segment": name,
                "metric_leads": ["channel price", "availability", "sku", "configuration", "offer snapshot"],
                "claim_types": ["market_proxy_context", "channel_offer_context", "verification_lead"],
            }
        )
    rating_value = str(tag_data.get("average_overall_rating") or _itemprop_content(body, "ratingValue") or "").strip()
    review_count = str(tag_data.get("total_review_count") or _itemprop_content(body, "reviewCount") or _itemprop_content(body, "ratingCount") or "").strip()
    if _positive_number(rating_value) or _positive_number(review_count):
        facts.append(
            {
                "fact_type": "platform_review_ranking_context",
                "fact_label": name or "platform review",
                "fact_value": _compact_text(f"rating={rating_value}; review_count={review_count}", 220),
                "structured_context_summary": _compact_text(
                    f"Public platform review/rating context for {name or 'product'}: rating={rating_value}, review_count={review_count}. "
                    "This is review/attention proxy only, not sales, revenue, retention, or market-share authority.",
                    460,
                ),
                "product_family": name,
                "product_or_segment": name,
                "metric_leads": ["rating", "review count", "platform review proxy"],
                "claim_types": ["market_proxy_context", "platform_review_ranking_context", "verification_lead"],
            }
        )
    return facts


def _cdw_tag_management_data(body: str) -> dict[str, Any]:
    match = re.search(r"(?is)window\.cdwTagManagementData\s*=\s*(\{.*?\});\s*</script>", body)
    if not match:
        return {}
    raw = match.group(1)
    try:
        value = ast.literal_eval(raw)
    except (SyntaxError, ValueError):
        return _simple_js_object_fields(raw)
    return dict(value) if isinstance(value, Mapping) else {}


def _simple_js_object_fields(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in re.findall(r"['\"]([A-Za-z0-9_]+)['\"]\s*:\s*['\"]([^'\"]*)['\"]", raw):
        out[key] = unescape(value)
    return out


def _itemprop_content(body: str, prop: str) -> str:
    escaped = re.escape(prop)
    patterns = [
        rf"(?is)<[^>]+\bitemprop=['\"]{escaped}['\"][^>]+\bcontent=['\"]([^'\"]*)['\"][^>]*>",
        rf"(?is)<[^>]+\bcontent=['\"]([^'\"]*)['\"][^>]+\bitemprop=['\"]{escaped}['\"][^>]*>",
    ]
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return _compact_text(unescape(match.group(1)), 220)
    return ""


def _itemprop_text(body: str, prop: str) -> str:
    content = _itemprop_content(body, prop)
    if content:
        return content
    escaped = re.escape(prop)
    patterns = [
        rf"(?is)<(?P<tag>[a-z0-9]+)[^>]+\bitemprop=['\"]{escaped}['\"][^>]*>(?P<text>.*?)</(?P=tag)>",
    ]
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return _compact_text(unescape(re.sub(r"(?is)<[^>]+>", " ", match.group("text"))), 220)
    return ""


def _positive_number(value: str) -> bool:
    try:
        return float(str(value or "").strip()) > 0
    except ValueError:
        return False


def _article_context_facts(body: str, *, text: str, source_class: str, repair_type: str) -> list[dict[str, Any]]:
    if source_class not in {"mainstream_financial_news_article", "supplier_customer_official_news", "industry_association_dataset"}:
        return []
    title = _html_title(body)
    description = _meta_content(body, "description") or _meta_content(body, "og:description")
    published = _meta_content(body, "article:published_time") or _meta_content(body, "date") or _meta_content(body, "datePublished")
    keywords = _SUPPLY_CHAIN_KEYWORDS if source_class == "supplier_customer_official_news" else _NEWS_EVENT_KEYWORDS
    snippets = [
        sentence
        for sentence in _sentences(text, max_sentences=80)
        if any(keyword in sentence.lower() for keyword in keywords)
    ][:3]
    if not (title or description or snippets):
        return []
    if source_class == "supplier_customer_official_news":
        fact_type = "official_supply_chain_news_context"
        label = title or "supplier/customer official news"
        boundary = "official supplier/customer news context only; no shipment, revenue, allocation, or order-volume authority"
        claim_types = ["supply_chain_context", "customer_supplier_relationship_context", "verification_lead"]
        metric_leads = ["customer", "supplier", "partner", "contract", "order context"]
    elif source_class == "industry_association_dataset":
        fact_type = "trusted_industry_association_context"
        label = title or "industry association context"
        boundary = "trusted industry association context only; no issuer exact financial, sales, shipment, or market-share authority"
        claim_types = ["market_proxy_context", "trusted_industry_association_context", "industry_cycle_context", "verification_lead"]
        metric_leads = ["industry context", "cycle context", "market context", "association report"]
    else:
        fact_type = "trusted_news_event_context"
        label = title or "trusted news event context"
        boundary = "trusted mainstream news context only; no issuer exact financial or product KPI authority"
        claim_types = ["market_proxy_context", "trusted_news_event_context", "verification_lead"]
        metric_leads = ["event context", "industry context", "competitive context"]
    summary_parts = [
        f"title={title}" if title else "",
        f"published={published}" if published else "",
        f"description={description}" if description else "",
        f"snippets={' / '.join(snippets)}" if snippets else "",
    ]
    summary = "; ".join(part for part in summary_parts if part)
    return [
        {
            "fact_type": fact_type,
            "fact_label": _compact_text(label, 160),
            "fact_value": _compact_text(summary, 420),
            "structured_context_summary": _compact_text(f"Parsed L2 article/news context ({boundary}): {summary}.", 560),
            "metric_leads": metric_leads,
            "claim_types": claim_types,
        }
    ]


def _html_title(body: str) -> str:
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", body)
    if not match:
        return ""
    return _compact_text(unescape(re.sub(r"(?is)<[^>]+>", " ", match.group(1))), 220)


def _meta_content(body: str, key: str) -> str:
    escaped_key = re.escape(key)
    patterns = [
        rf"(?is)<meta[^>]+(?:name|property)=['\"]{escaped_key}['\"][^>]+content=['\"]([^'\"]+)['\"][^>]*>",
        rf"(?is)<meta[^>]+content=['\"]([^'\"]+)['\"][^>]+(?:name|property)=['\"]{escaped_key}['\"][^>]*>",
    ]
    for pattern in patterns:
        match = re.search(pattern, body)
        if match:
            return _compact_text(unescape(match.group(1)), 320)
    return ""


def _json_ld_items(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        out: list[Mapping[str, Any]] = []
        for item in payload:
            out.extend(_json_ld_items(item))
        return out
    if not isinstance(payload, Mapping):
        return []
    rows: list[Mapping[str, Any]] = [payload]
    graph = payload.get("@graph")
    if isinstance(graph, list):
        rows.extend(item for item in graph if isinstance(item, Mapping))
    return rows


def _json_ld_item_facts(item: Mapping[str, Any], *, source_class: str, repair_type: str) -> list[dict[str, Any]]:
    type_text = " ".join(_unique_strings(item.get("@type") or item.get("type"))).lower()
    facts: list[dict[str, Any]] = []
    if "jobposting" in type_text or source_class == "job_posting_snapshot":
        title = str(item.get("title") or item.get("name") or "").strip()
        location = _json_ld_location(item.get("jobLocation"))
        date_posted = str(item.get("datePosted") or item.get("validThrough") or "").strip()
        if title or location or date_posted:
            facts.append(
                {
                    "fact_type": "hiring_signal_context",
                    "fact_label": title or "job posting",
                    "fact_value": _compact_text(f"location={location}; date={date_posted}", 260),
                    "structured_context_summary": _compact_text(
                        f"Public job posting context: {title or 'role'}"
                        f"{' in ' + location if location else ''}"
                        f"{' dated ' + date_posted if date_posted else ''}. "
                        "This is hiring/capacity proxy only.",
                        420,
                    ),
                    "metric_leads": ["job title", "location", "date posted", "hiring proxy"],
                    "claim_types": ["market_proxy_context", "hiring_signal_context", "verification_lead"],
                }
            )
    if "product" in type_text or source_class in {"ecommerce_major_platform", "channel_pricing_snapshot"}:
        name = str(item.get("name") or "").strip()
        sku = str(item.get("sku") or item.get("mpn") or "").strip()
        offer = _first_mapping(item.get("offers"))
        price = str(offer.get("price") or offer.get("lowPrice") or offer.get("highPrice") or "").strip()
        currency = str(offer.get("priceCurrency") or "").strip()
        availability = str(offer.get("availability") or "").rsplit("/", 1)[-1].strip()
        if name or sku or price or availability:
            facts.append(
                {
                    "fact_type": "channel_offer_context",
                    "fact_label": name or sku or "channel offer",
                    "fact_value": _compact_text(f"sku={sku}; price={price} {currency}; availability={availability}", 260),
                    "structured_context_summary": _compact_text(
                        f"Public channel/ecommerce offer context for {name or sku or 'product'}: "
                        f"price={price} {currency}, availability={availability}. "
                        "This is price/availability proxy only, not ASP, inventory, or sell-through authority.",
                        460,
                    ),
                    "metric_leads": ["channel price", "availability", "sku", "offer snapshot"],
                    "claim_types": ["market_proxy_context", "channel_offer_context", "verification_lead"],
                }
            )
        rating = _first_mapping(item.get("aggregateRating"))
        rating_value = str(rating.get("ratingValue") or "").strip()
        review_count = str(rating.get("reviewCount") or rating.get("ratingCount") or "").strip()
        if rating_value or review_count:
            facts.append(
                {
                    "fact_type": "platform_review_ranking_context",
                    "fact_label": name or "platform rating",
                    "fact_value": _compact_text(f"rating={rating_value}; review_count={review_count}", 220),
                    "structured_context_summary": _compact_text(
                        f"Public platform review/rating context for {name or 'product'}: rating={rating_value}, review_count={review_count}. "
                        "This is attention/sentiment proxy only.",
                        420,
                    ),
                    "metric_leads": ["rating", "review count", "platform review proxy"],
                    "claim_types": ["market_proxy_context", "platform_review_ranking_context", "verification_lead"],
                }
            )
    description_text = " ".join(
        _unique_strings([item.get("name"), item.get("description"), item.get("award"), item.get("identifier")])
    ).lower()
    if source_class == "public_tender_or_contract_portal" or any(token in description_text for token in ("tender", "award", "procurement", "contract")):
        name = str(item.get("name") or item.get("description") or "public tender or contract").strip()
        identifier = str(item.get("identifier") or item.get("sku") or "").strip()
        date_value = str(item.get("datePublished") or item.get("startDate") or item.get("endDate") or "").strip()
        facts.append(
            {
                "fact_type": "public_tender_contract_context",
                "fact_label": _compact_text(name, 140),
                "fact_value": _compact_text(f"identifier={identifier}; date={date_value}", 240),
                "structured_context_summary": _compact_text(
                    f"Public tender/contract context: {name}"
                    f"{' identifier ' + identifier if identifier else ''}"
                    f"{' date ' + date_value if date_value else ''}. "
                    "This is public order/tender lead only, not total company order or revenue authority.",
                    460,
                ),
                "metric_leads": ["tender", "contract", "award", "public order lead"],
                "claim_types": ["market_proxy_context", "public_tender_contract_context", "verification_lead"],
            }
        )
    return facts


def _json_ld_location(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(_json_ld_location(item) for item in value if _json_ld_location(item))[:220]
    if not isinstance(value, Mapping):
        return str(value or "").strip()
    address = value.get("address")
    if isinstance(address, Mapping):
        return ", ".join(
            _unique_strings(
                [
                    address.get("addressLocality"),
                    address.get("addressRegion"),
                    address.get("addressCountry"),
                ]
            )
        )
    return str(value.get("name") or "").strip()


def _first_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, Mapping):
                return item
    return {}


def _table_context_facts(body: str, *, content_type: str, repair_type: str, source_class: str) -> list[dict[str, Any]]:
    if "html" not in content_type.lower() and "<table" not in body.lower():
        return []
    facts: list[dict[str, Any]] = []
    keywords = _keywords_for_repair_type(repair_type)
    for table_index, table in enumerate(re.findall(r"(?is)<table\b.*?</table>", body)[:6], start=1):
        row_cells = _html_table_rows(table)
        if len(row_cells) < 2:
            continue
        headers = row_cells[0]
        for row_index, cells in enumerate(row_cells[1:12], start=1):
            if not cells:
                continue
            row_text = " | ".join(cells)
            if keywords and not any(keyword in row_text.lower() for keyword in keywords) and repair_type not in {"product_surface", "market_proxy"}:
                continue
            facts.append(
                {
                    "fact_type": _table_fact_type(repair_type=repair_type, source_class=source_class),
                    "fact_label": _compact_text(cells[0] or f"table {table_index} row {row_index}", 120),
                    "fact_value": _compact_text(row_text, 360),
                    "structured_context_summary": _compact_text(f"Parsed allowed-source table row for {repair_type}: {row_text}", 520),
                    "table_headers": headers,
                    "table_row_values": cells,
                    "metric_leads": _table_metric_leads(headers, cells),
                    "claim_types": _default_claim_types(repair_type),
                }
            )
            if len(facts) >= 10:
                return facts
    return facts


def _table_fact_type(*, repair_type: str, source_class: str) -> str:
    return {
        "ecommerce_major_platform": "channel_offer_context",
        "channel_pricing_snapshot": "channel_offer_context",
        "public_tender_or_contract_portal": "public_tender_contract_context",
        "job_posting_snapshot": "hiring_signal_context",
        "platform_review_or_ranking_snapshot": "platform_review_ranking_context",
        "official_app_store_or_marketplace": "app_store_marketplace_context",
        "developer_ecosystem_snapshot": "developer_ecosystem_context",
    }.get(source_class, f"{repair_type}_table_context")


def _product_context_facts(text: str, *, repair: Mapping[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    product_terms = _unique_strings([*(repair.get("official_product_surfaces") or []), *(repair.get("product_surfaces") or []), *(repair.get("target_products") or [])])
    lowered = text.lower()
    for product in product_terms[:8]:
        present = product.lower() in lowered
        facts.append(
            {
                "fact_type": "official_product_taxonomy_context",
                "fact_label": product,
                "fact_value": "mentioned_on_allowed_official_surface" if present else "repair_plan_product_surface_lead",
                "structured_context_summary": (
                    f"Official product surface {'mentions' if present else 'targets'} {product}; "
                    "this is taxonomy/spec context, not sales or market share authority."
                ),
                "product_family": product,
                "product_or_segment": product,
                "metric_leads": _unique_strings(repair.get("official_metric_leads") or repair.get("metric_leads") or []),
                "claim_types": ["official_product_surface", "product_taxonomy_context", "product_spec_context", "verification_lead"],
            }
        )
    for sentence in _sentences(text, max_sentences=80):
        sentence_lower = sentence.lower()
        if not any(keyword in sentence_lower for keyword in _PRODUCT_SPEC_KEYWORDS):
            continue
        product = _matched_product(sentence, product_terms)
        model = _extract_model_code(sentence)
        facts.append(
            {
                "fact_type": "product_spec_context",
                "fact_label": product or model or "product specification context",
                "fact_value": _compact_text(sentence, 360),
                "structured_context_summary": _compact_text(f"Parsed official product/spec context: {sentence}", 520),
                "product_family": product,
                "product_or_segment": product,
                "metric_leads": ["specification", "configuration", "capacity", "throughput"],
                "claim_types": ["product_spec_context", "product_taxonomy_context", "verification_lead"],
            }
        )
        if len(facts) >= 12:
            break
    return facts


def _sentence_context_facts(text: str, *, repair_type: str, keywords: tuple[str, ...], fact_type: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for sentence in _sentences(text, max_sentences=80):
        sentence_lower = sentence.lower()
        if not any(keyword in sentence_lower for keyword in keywords):
            continue
        label = _topic_label_from_sentence(sentence, keywords)
        facts.append(
            {
                "fact_type": fact_type,
                "fact_label": label,
                "fact_value": _compact_text(sentence, 360),
                "structured_context_summary": _compact_text(f"Parsed bounded {repair_type} context: {sentence}", 520),
                "metric_leads": _metric_leads_from_sentence(sentence, repair_type=repair_type),
                "claim_types": _default_claim_types(repair_type),
            }
        )
        if len(facts) >= 8:
            break
    return facts


def _visible_text(body: str, *, content_type: str) -> str:
    if "json" in content_type.lower():
        try:
            return json.dumps(json.loads(body), ensure_ascii=False)
        except json.JSONDecodeError:
            return body
    text = re.sub(r"(?is)<script\b.*?</script>", " ", body)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?is)<(br|p|div|li|tr|h[1-6])\b[^>]*>", ". ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    return _compact_text(text, 12000)


def _html_table_rows(table_html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row_html in re.findall(r"(?is)<tr\b.*?</tr>", table_html):
        cells = [
            _compact_text(unescape(re.sub(r"(?is)<[^>]+>", " ", cell)), 160)
            for cell in re.findall(r"(?is)<t[dh]\b.*?</t[dh]>", row_html)
        ]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(cells)
    return rows


def _sentences(text: str, *, max_sentences: int) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    pieces = re.split(r"(?<=[.!?。！？])\s+|[;\n\r]+", normalized)
    out: list[str] = []
    for piece in pieces:
        sentence = _compact_text(piece, 420)
        if len(sentence) < 24:
            continue
        out.append(sentence)
        if len(out) >= max_sentences:
            break
    return out


def _dedupe_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for fact in facts:
        key = "|".join(
            [
                str(fact.get("fact_type") or ""),
                str(fact.get("fact_label") or "").lower(),
                str(fact.get("fact_value") or "").lower()[:180],
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(fact))
    return out


def _claim_types_for_fact(fact: Mapping[str, Any], *, repair_type: str) -> list[str]:
    explicit = _unique_strings(fact.get("claim_types") or [])
    return explicit or _default_claim_types(repair_type)


def _default_claim_types(repair_type: str) -> list[str]:
    return {
        "product_surface": ["official_product_surface", "product_taxonomy_context", "product_spec_context", "verification_lead"],
        "market_proxy": ["market_proxy_context", "industry_cycle_context", "verification_lead"],
        "supply_chain": ["supply_chain_context", "customer_supplier_relationship_context", "verification_lead"],
        "capital_ownership": ["capital_ownership_context", "offering_or_ownership_parser_lead", "verification_lead"],
        "local_filing": ["local_filing_context", "issuer_filing_presence", "verification_lead"],
        "issuer_official": ["official_issuer_context", "issuer_filing_presence", "verification_lead"],
    }.get(repair_type, ["public_context", "verification_lead"])


def _parser_claim_boundary(repair_type: str) -> str:
    return {
        "product_surface": "bounded product taxonomy/spec context only; exact product KPI facts remain gated",
        "market_proxy": "bounded directional proxy only; no issuer-specific sales/share/order inference",
        "supply_chain": "bounded relationship context only; no shipment/revenue/allocation inference",
        "capital_ownership": "bounded capital/ownership parser lead only; exact amount/security/holder facts remain gated",
        "local_filing": "official filing context only; exact values require period/unit/citation parser gates",
        "issuer_official": "official issuer context only; exact values require period/unit/citation parser gates",
    }.get(repair_type, "bounded public context only")


def _source_claim_strength(*, repair_type: str, source_layer_id: str) -> str:
    if source_layer_id == "L1":
        return "official_context_parser_backed_not_exact_metric"
    if source_layer_id == "L2":
        return "trusted_context_parser_backed"
    if source_layer_id == "L3":
        return "directional_market_proxy_parser_backed"
    return f"{repair_type}_bounded_context"


def _keywords_for_repair_type(repair_type: str) -> tuple[str, ...]:
    return {
        "product_surface": _PRODUCT_SPEC_KEYWORDS,
        "market_proxy": _MARKET_PROXY_KEYWORDS,
        "supply_chain": _SUPPLY_CHAIN_KEYWORDS,
        "capital_ownership": _CAPITAL_KEYWORDS,
        "local_filing": _ISSUER_DISCLOSURE_KEYWORDS,
        "issuer_official": _ISSUER_DISCLOSURE_KEYWORDS,
    }.get(repair_type, ())


def _table_metric_leads(headers: list[str], cells: list[str]) -> list[str]:
    terms = _unique_strings([*headers, *cells])
    return [
        term
        for term in terms[:8]
        if any(keyword in term.lower() for keyword in ("revenue", "sales", "share", "rank", "price", "capacity", "volume", "date", "form", "model", "throughput"))
    ][:6]


def _metric_leads_from_sentence(sentence: str, *, repair_type: str) -> list[str]:
    lower = sentence.lower()
    keyword_map = {
        "market_proxy": ("market", "share", "rank", "shipment", "registration", "download", "price", "review"),
        "supply_chain": ("supplier", "customer", "partner", "contract", "order", "tender", "award", "channel"),
        "capital_ownership": ("debt", "note", "maturity", "coupon", "interest", "offering", "ownership", "holder"),
        "issuer_official": ("filing", "annual report", "20-f", "10-k", "6-k", "8-k", "presentation"),
        "local_filing": ("filing", "annual report", "regulator", "exchange", "disclosure"),
    }
    return [keyword for keyword in keyword_map.get(repair_type, ()) if keyword in lower][:6]


def _topic_label_from_sentence(sentence: str, keywords: tuple[str, ...]) -> str:
    lower = sentence.lower()
    for keyword in keywords:
        if keyword in lower:
            return keyword.replace("_", " ")
    return _compact_text(sentence, 80)


def _matched_product(sentence: str, product_terms: list[str]) -> str:
    lower = sentence.lower()
    for product in product_terms:
        if product.lower() in lower:
            return product
    return ""


def _extract_model_code(sentence: str) -> str:
    match = re.search(r"\b[A-Z]{2,6}[: -]?\d{2,5}[A-Z]?\b", sentence)
    return match.group(0) if match else ""


def _domain(url: str) -> str:
    match = re.match(r"^[a-z]+://([^/]+)", str(url).strip().lower())
    return match.group(1).split("@")[-1].split(":")[0] if match else ""


def _list_values(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _unique_strings(values: Any) -> list[str]:
    if values is None:
        return []
    iterable = values if isinstance(values, (list, tuple, set)) else [values]
    out: list[str] = []
    seen: set[str] = set()
    for value in iterable:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _scalar_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _compact_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


_PRODUCT_SPEC_KEYWORDS = (
    "model",
    "platform",
    "generation",
    "configuration",
    "specification",
    "capacity",
    "throughput",
    "wafers per hour",
    "wph",
    "high-na",
    "numerical aperture",
    "resolution",
    " nm",
    "node",
    "euv",
    "duv",
)
_MARKET_PROXY_KEYWORDS = (
    "market",
    "share",
    "rank",
    "ranking",
    "download",
    "review",
    "shipment",
    "registration",
    "install base",
    "price",
    "availability",
    "channel",
    "vendor",
)
_SUPPLY_CHAIN_KEYWORDS = (
    "supplier",
    "customer",
    "partner",
    "channel",
    "distributor",
    "contract",
    "order",
    "tender",
    "award",
    "supply",
)
_CAPITAL_KEYWORDS = (
    "debt",
    "note",
    "notes",
    "maturity",
    "coupon",
    "interest rate",
    "offering",
    "13f",
    "13d",
    "13g",
    "form 3",
    "form 4",
    "form 5",
    "holder",
    "ownership",
)
_ISSUER_DISCLOSURE_KEYWORDS = (
    "annual report",
    "filing",
    "form 20-f",
    "20-f",
    "6-k",
    "10-k",
    "10-q",
    "8-k",
    "regulator",
    "exchange",
    "investor",
    "presentation",
)
_NEWS_EVENT_KEYWORDS = (
    "announced",
    "reported",
    "said",
    "deal",
    "contract",
    "order",
    "partnership",
    "supplier",
    "customer",
    "demand",
    "market",
    "industry",
    "regulator",
    "approval",
    "launch",
)
