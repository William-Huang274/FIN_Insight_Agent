from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from eval.object_verifier import load_structured_object_map, normalize_text, read_jsonl  # noqa: E402
from evidence.structured_text import structured_object_search_text  # noqa: E402


REVIEWER = "codex_model_assisted_review"
RULESET_VERSION = "codex_object_review_v0.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fill human_label fields with Codex model-assisted object relevance labels."
    )
    parser.add_argument(
        "--input-jsonl",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates.jsonl",
    )
    parser.add_argument(
        "--structured-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument(
        "--output-jsonl",
        default="eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl",
    )
    parser.add_argument(
        "--output-csv",
        default="reports/retrieval_eval/sec_tech_10k_object_review_candidates_codex_labeled.csv",
    )
    parser.add_argument("--reviewed-at", default="2026-05-16")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    object_map = load_structured_object_map(REPO_ROOT / args.structured_dir, args.prefix)
    rows = []
    for row in read_jsonl(REPO_ROOT / args.input_jsonl):
        obj = object_map.get(row["object_id"])
        label, note = label_row(row, obj or {})
        rows.append(
            {
                **row,
                "label_status": "model_assisted_review_by_codex_needs_user_spot_check",
                "reviewer": REVIEWER,
                "reviewed_at": args.reviewed_at,
                "review_ruleset_version": RULESET_VERSION,
                "human_label": label,
                "human_notes": note,
            }
        )

    jsonl_path = REPO_ROOT / args.output_jsonl
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")

    csv_path = REPO_ROOT / args.output_csv
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(rows, csv_path)

    print(json.dumps(_summarize(rows, jsonl_path, csv_path), ensure_ascii=False, indent=2))


def label_row(row: dict[str, Any], obj: dict[str, Any]) -> tuple[str, str]:
    text = normalize_text(structured_object_search_text(obj))
    facet = row.get("facet")
    object_type = obj.get("object_type") or row.get("object_type")
    object_ticker = str(obj.get("ticker") or "").upper()

    if facet == "services_net_sales":
        return _aapl_services_net_sales(text)
    if facet == "services_gross_margin_metrics":
        return _aapl_services_gross_margin_metrics(text, object_type)
    if facet == "services_gross_margin_drivers":
        return _aapl_services_gross_margin_drivers(text, object_type)
    if facet == "consumption_visibility_risk":
        return _snow_consumption_visibility(text)
    if facet == "rpo_visibility" and object_ticker == "SNOW":
        return _snow_rpo_visibility(text, object_type)
    if facet == "customer_metrics" and object_ticker == "SNOW":
        return _snow_customer_metrics(text, object_type)
    if facet == "msft_cloud_growth":
        return _msft_cloud_growth(text, object_ticker, object_type)
    if facet == "msft_ai_capex_margin_pressure":
        return _msft_ai_capex_margin_pressure(text, object_ticker)
    if facet == "googl_cloud_growth_profitability":
        return _googl_cloud_growth_profitability(text, object_ticker, object_type)
    if facet == "googl_capex_pressure":
        return _googl_capex_pressure(text, object_ticker)
    if facet == "aws_segment_metrics":
        return _amzn_aws_segment_metrics(text, object_ticker, object_type)
    if facet == "infrastructure_cost_allocation":
        return _amzn_infra_cost_allocation(text, object_ticker)
    if facet == "fcf_capex_pressure":
        return _amzn_fcf_capex_pressure(text, object_ticker)
    if facet == "aws_cost_offset":
        return _amzn_aws_cost_offset(text, object_ticker)
    if facet == "datacenter_growth":
        return _nvda_datacenter_growth(text, object_ticker, object_type)
    if facet == "customer_concentration":
        return _nvda_customer_concentration(text, object_ticker, object_type)
    if facet == "cloud_customer_demand_context":
        return _nvda_cloud_demand_context(text, object_ticker)
    if facet == "supply_capacity_risk":
        return _nvda_supply_capacity_risk(text, object_ticker)
    if facet == "third_party_manufacturing_risk":
        return _nvda_third_party_manufacturing_risk(text, object_ticker)
    if facet == "arr_growth":
        return _adbe_arr_growth(text, object_ticker)
    if facet == "rpo_visibility" and object_ticker == "ADBE":
        return _adbe_rpo_visibility(text, object_type)
    if facet == "subscription_mix":
        return _adbe_subscription_mix(text, object_ticker, object_type)
    if facet == "contract_caveats":
        return _adbe_contract_caveats(text, object_ticker)

    if row.get("auto_label") == "false":
        return "false", "fallback: auto verifier found no usable facet match"
    return "partial", "fallback: related lexical match but no facet-specific rule"


def _aapl_services_net_sales(text: str) -> tuple[str, str]:
    driver_count = _count_present(text, ["advertising", "app store", "cloud services"])
    if "services net sales increased" in text and driver_count >= 2:
        return "direct", "states Services net sales increase and main Services drivers"
    if _has_any(text, ["services net sales", "higher services net sales"]) or _has_all(text, ["net sales by category", "services"]):
        return "partial", "Services net sales or driver context, but not the full driver statement"
    return "false", "not evidence for Services net sales performance"


def _aapl_services_gross_margin_metrics(text: str, object_type: str) -> tuple[str, str]:
    services_margin = _has_all(text, ["services", "gross margin"])
    has_2025_amount = _has_number(text, "82314")
    has_2025_percent = _has_number(text, "75.4")
    if object_type == "table" and services_margin and has_2025_amount and has_2025_percent:
        return "direct", "table contains both 2025 Services gross margin dollars and percentage"
    if services_margin and (has_2025_amount or has_2025_percent):
        return "partial", "contains one required 2025 Services gross margin metric"
    if services_margin and (_has_number(text, "71050") or _has_number(text, "73.9")):
        return "partial", "contains comparison-year Services gross margin context"
    return "false", "wrong segment, wrong metric, or no Services gross margin value"


def _aapl_services_gross_margin_drivers(text: str, object_type: str) -> tuple[str, str]:
    has_services_margin = _has_all(text, ["services", "gross margin"])
    driver_count = _count_present(
        text,
        ["higher services net sales", "different mix of services", "partially offset by higher costs"],
    )
    if has_services_margin and driver_count >= 1:
        return "direct", "states Services gross margin driver or cost offset"
    if object_type == "table" and driver_count >= 2:
        return "partial", "nearby text carries driver language, but object itself is table context"
    return "false", "not Services gross margin driver evidence"


def _snow_consumption_visibility(text: str) -> tuple[str, str]:
    direct_terms = [
        "recognize revenue on consumption",
        "do not have the visibility",
        "customer consumption fluctuates",
        "unexpected fluctuations in customer consumption",
    ]
    if _count_present(text, direct_terms) >= 1 and ("consumption" in text or "visibility" in text):
        return "direct", "states consumption-based recognition or visibility risk"
    if _has_any(text, ["future financial position", "timing of revenue recognition", "consume our platform"]):
        return "partial", "related visibility or consumption context, but not the core mechanic"
    return "false", "not evidence for consumption-based visibility risk"


def _snow_rpo_visibility(text: str, object_type: str) -> tuple[str, str]:
    has_rpo = _has_any(text, ["remaining performance obligations", "rpo"])
    number_count = _count_numbers(text, ["6.9", "48", "2.4"])
    if has_rpo and object_type != "metric" and number_count >= 2:
        return "direct", "states RPO amount and recognition timing"
    if has_rpo and number_count == 1:
        return "partial", "contains one RPO visibility metric"
    if has_rpo:
        return "partial", "RPO definition or caveat without the target metrics"
    return "false", "not Snowflake RPO visibility evidence"


def _snow_customer_metrics(text: str, object_type: str) -> tuple[str, str]:
    metric_count = _count_numbers(text, ["11159", "745", "126", "580"])
    if metric_count >= 3:
        return "direct", "contains several Snowflake customer expansion metrics"
    if metric_count >= 1 and _has_any(text, ["customers", "net revenue retention", "forbes global 2000"]):
        return "partial", "contains one customer metric needed for the facet"
    if _has_any(text, ["customer count", "net revenue retention rate", "trailing 12-month product revenue"]):
        return "partial", "customer metric definition or adjustment context"
    return "false", "not evidence for Snowflake customer metrics"


def _msft_cloud_growth(text: str, ticker: str, object_type: str) -> tuple[str, str]:
    if ticker != "MSFT":
        return "false", "wrong company for Microsoft cloud growth facet"
    has_msft_cloud = _has_any(text, ["microsoft cloud", "azure and other cloud services", "server products and cloud services"])
    if has_msft_cloud and (_has_number(text, "168.9") or _has_number(text, "34")):
        return "direct", "states Microsoft Cloud or Azure cloud growth metric"
    if has_msft_cloud and _has_number(text, "23"):
        return "partial", "related Microsoft cloud growth metric without the full amount/Azure context"
    return "false", "not Microsoft cloud revenue growth evidence"


def _msft_ai_capex_margin_pressure(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "MSFT":
        return "false", "wrong company for Microsoft AI capex/margin facet"
    margin_ai = _has_all(text, ["gross margin", "ai infrastructure"]) and _has_any(text, ["decreased", "scaling"])
    capex_ai = _has_all(text, ["capital expenditures", "cloud offerings"]) and _has_any(text, ["ai infrastructure", "training"])
    if margin_ai or capex_ai:
        return "direct", "states Microsoft AI infrastructure margin pressure or capex plan"
    if _has_all(text, ["gross margin", "decreased"]) or _has_all(text, ["cloud-based", "ai services"]):
        return "partial", "related Microsoft margin or AI infrastructure cost context"
    return "false", "not Microsoft AI capex or margin-pressure evidence"


def _googl_cloud_growth_profitability(text: str, ticker: str, object_type: str) -> tuple[str, str]:
    if ticker != "GOOGL":
        return "false", "wrong company for Google Cloud facet"
    has_google_cloud = "google cloud" in text
    metric_count = _count_numbers(text, ["58.705", "43.229", "13.910", "6.112"])
    driver = _has_all(text, ["increase", "revenues"]) and _has_any(text, ["usage costs", "technical infrastructure", "compensation"])
    if has_google_cloud and ((object_type == "table" and metric_count >= 2) or driver):
        return "direct", "states Google Cloud revenue/profitability metric or driver"
    if has_google_cloud and metric_count >= 1:
        return "partial", "contains one Google Cloud revenue or operating-income value"
    if has_google_cloud:
        return "partial", "Google Cloud business context without the target values"
    return "false", "not Google Cloud growth/profitability evidence"


def _googl_capex_pressure(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "GOOGL":
        return "false", "wrong company for Alphabet capex facet"
    if _has_all(text, ["capital expenditures", "technical infrastructure"]) and _has_number(text, "91.4"):
        return "direct", "states Alphabet capex amount and technical infrastructure use"
    if _has_all(text, ["technical infrastructure", "ai"]) or _has_all(text, ["capital expenditures", "technical infrastructure"]):
        return "partial", "technical infrastructure capex pressure context without the $91.4B anchor"
    return "false", "not Alphabet capex pressure evidence"


def _amzn_aws_segment_metrics(text: str, ticker: str, object_type: str) -> tuple[str, str]:
    if ticker != "AMZN":
        return "false", "wrong company for AWS metrics facet"
    has_aws = "aws" in text
    metric_count = _count_numbers(text, ["128.725", "45.606"])
    income_driver = _has_all(text, ["operating income", "increased", "increased sales"])
    if has_aws and (metric_count >= 1 or income_driver):
        return "direct", "states AWS net sales, operating income, or operating income driver"
    if has_aws and _has_any(text, ["net sales", "operating income"]):
        return "partial", "AWS segment metric context without the target 2025 values"
    return "false", "not AWS segment metric evidence"


def _amzn_infra_cost_allocation(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "AMZN":
        return "false", "wrong company for Amazon infrastructure allocation facet"
    if _has_all(text, ["majority of infrastructure costs", "allocated to the aws segment", "based on usage"]):
        return "direct", "states infrastructure costs allocated to AWS based on usage"
    if _has_all(text, ["technology infrastructure assets", "allocated among the segments based on usage"]):
        return "direct", "states infrastructure cost or asset allocation method"
    if _has_all(text, ["infrastructure", "allocated"]):
        return "partial", "related allocation context but missing AWS/usage detail"
    return "false", "not infrastructure allocation evidence"


def _amzn_fcf_capex_pressure(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "AMZN":
        return "false", "wrong company for Amazon FCF/capex facet"
    fcf_anchor = _has_all(text, ["free cash flow", "cash capital expenditures"])
    tech_ai = (
        _has_any(text, ["spending in technology and infrastructure will increase over time", "spending in technology and infrastructure to increase over time"])
        and _has_any(text, ["artificial intelligence", "machine learning"])
    )
    if fcf_anchor or tech_ai:
        return "direct", "states free-cash-flow capex driver or AI infrastructure spending pressure"
    if _has_any(text, ["capital expenditures", "technology infrastructure", "property and equipment"]):
        return "partial", "capex or infrastructure context without the FCF pressure claim"
    return "false", "not free-cash-flow capex pressure evidence"


def _amzn_aws_cost_offset(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "AMZN":
        return "false", "wrong company for AWS cost-offset facet"
    if _has_all(text, ["partially offset", "technology infrastructure"]) or _has_all(text, ["support aws business growth", "technology infrastructure"]):
        return "direct", "states AWS income growth offset by technology infrastructure investment"
    if _has_any(text, ["aws business growth", "technology infrastructure"]):
        return "partial", "related AWS growth or infrastructure cost context"
    return "false", "not AWS cost-offset evidence"


def _nvda_datacenter_growth(text: str, ticker: str, object_type: str) -> tuple[str, str]:
    if ticker != "NVDA":
        return "false", "wrong company for NVIDIA Data Center facet"
    if _has_all(text, ["data center", "computing"]) and _has_number(text, "162"):
        return "direct", "states Data Center computing growth"
    if _has_all(text, ["hopper", "large language models"]) or _has_any(text, ["recommendation engines", "generative ai"]):
        return "direct", "states Data Center demand driver context"
    if _has_any(text, ["data center", "hopper", "blackwell"]):
        return "partial", "related Data Center demand/growth context"
    return "false", "not Data Center growth evidence"


def _nvda_customer_concentration(text: str, ticker: str, object_type: str) -> tuple[str, str]:
    if ticker != "NVDA":
        return "false", "wrong company for NVIDIA concentration facet"
    if _has_any(text, ["direct customer a", "direct customer b", "direct customer c"]) and _count_numbers(text, ["12", "11"]) >= 1:
        return "direct", "states direct customer concentration percentage"
    if _has_all(text, ["indirect", "csp"]) or _has_all(text, ["direct customers", "sales"]):
        return "direct", "states direct/indirect customer concentration structure"
    if _has_any(text, ["customer concentration", "significant customers", "csp"]):
        return "partial", "customer concentration context without target percentages"
    return "false", "not customer concentration evidence"


def _nvda_cloud_demand_context(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "NVDA":
        return "false", "wrong company for NVIDIA cloud-demand facet"
    if _has_all(text, ["public cloud", "consumer internet companies"]) or _has_all(text, ["major cloud provider", "industry standard servers"]):
        return "direct", "states public cloud and consumer internet demand context"
    if _has_any(text, ["cloud service provider", "cloud provider", "public cloud"]):
        return "partial", "cloud demand context but missing full customer/use-case framing"
    return "false", "not cloud customer demand context"


def _nvda_supply_capacity_risk(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "NVDA":
        return "false", "wrong company for NVIDIA supply risk facet"
    direct_terms = [
        "prepaid manufacturing and capacity agreements",
        "complexity in managing multiple suppliers",
        "inventory provisions or impairments",
        "product transitions",
    ]
    if _count_present(text, direct_terms) >= 1:
        return "direct", "states a target supply/capacity risk factor"
    if _has_any(text, ["capacity", "supplier", "manufacturing", "demand may exceed supply"]):
        return "partial", "related supply/capacity risk context"
    return "false", "not supply/capacity risk evidence"


def _nvda_third_party_manufacturing_risk(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "NVDA":
        return "false", "wrong company for NVIDIA manufacturing-risk facet"
    direct_terms = [
        "third-party suppliers",
        "foundries",
        "contract manufacturers",
        "lack of guaranteed supply",
        "limited number",
        "geographic concentration",
    ]
    if _count_present(text, direct_terms) >= 2 or _has_all(text, ["dependency", "third-party"]):
        return "direct", "states third-party supplier/manufacturing dependency risk"
    if _has_any(text, ["supplier", "manufacturing", "capacity"]):
        return "partial", "related supply risk but not the third-party dependency facet"
    return "false", "not third-party manufacturing risk evidence"


def _adbe_arr_growth(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "ADBE":
        return "false", "wrong company for Adobe ARR facet"
    if _has_all(text, ["total adobe arr", "25.20"]) or _has_all(text, ["annual value", "subscription contracts"]):
        return "direct", "states Total Adobe ARR or ARR definition"
    if _has_any(text, ["digital media arr", "net new arr", "creative arr", "document cloud arr"]) and _has_any(text, ["25.20", "11.5", "arr"]):
        return "partial", "ARR component or growth context, but not complete Total Adobe ARR"
    if "arr" in text:
        return "partial", "related ARR context"
    return "false", "not ARR growth evidence"


def _adbe_rpo_visibility(text: str, object_type: str) -> tuple[str, str]:
    has_rpo = _has_any(text, ["remaining performance obligations", "rpo"])
    metric_count = _count_numbers(text, ["22.52", "13", "65"])
    if has_rpo and object_type != "metric" and metric_count >= 2:
        return "direct", "states Adobe RPO amount, growth, or expected recognition"
    if has_rpo and metric_count >= 1:
        return "partial", "contains one Adobe RPO visibility metric"
    if has_rpo:
        return "partial", "RPO definition or caveat without target values"
    return "false", "not Adobe RPO visibility evidence"


def _adbe_subscription_mix(text: str, ticker: str, object_type: str) -> tuple[str, str]:
    if ticker != "ADBE":
        return "false", "wrong company for Adobe subscription mix facet"
    sub_revenue = _has_all(text, ["subscription", "revenue"])
    if sub_revenue and (_has_number(text, "22.904") or _has_number(text, "96")):
        return "direct", "states subscription revenue amount or percentage of total revenue"
    if _has_all(text, ["recognized", "ratably"]) and "subscription" in text:
        return "direct", "states subscription revenue recognition timing"
    if sub_revenue:
        return "partial", "subscription revenue context without target amount/share"
    return "false", "not subscription mix evidence"


def _adbe_contract_caveats(text: str, ticker: str) -> tuple[str, str]:
    if ticker != "ADBE":
        return "false", "wrong company for Adobe contract caveat facet"
    direct = (
        _has_all(text, ["subscription contracts", "generally non-cancellable"])
        or _has_all(text, ["limited number of customers", "right to cancel"])
        or _has_all(text, ["remaining performance obligations", "usage-based"])
        or _has_all(text, ["remaining performance obligations", "variable consideration"])
    )
    if direct:
        return "direct", "states non-cancellable contract or RPO exclusion caveat"
    if _has_any(text, ["cancellation", "variable consideration", "remaining performance obligations"]):
        return "partial", "related contract/RPO caveat but missing the target caveat"
    return "false", "not contract caveat evidence"


def _has_all(text: str, terms: Iterable[str]) -> bool:
    return all(normalize_text(term) in text for term in terms)


def _has_any(text: str, terms: Iterable[str]) -> bool:
    return any(normalize_text(term) in text for term in terms)


def _count_present(text: str, terms: Iterable[str]) -> int:
    return sum(1 for term in terms if normalize_text(term) in text)


def _has_number(text: str, value: str) -> bool:
    cleaned_text = text.replace(",", "")
    cleaned = normalize_text(value).replace("$", "").replace(",", "")
    candidates = {cleaned}
    if "." in cleaned:
        left, right = cleaned.split(".", 1)
        if len(right) == 3 and left.isdigit() and right.isdigit():
            candidates.add(f"{left}{right}")
    return any(candidate in cleaned_text for candidate in candidates)


def _count_numbers(text: str, values: Iterable[str]) -> int:
    return sum(1 for value in values if _has_number(text, value))


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "query_id",
        "mode",
        "ticker",
        "fiscal_year",
        "facet",
        "candidate_rank",
        "bm25_score",
        "in_gold_target_refs",
        "auto_label",
        "human_label",
        "human_notes",
        "reviewer",
        "reviewed_at",
        "review_ruleset_version",
        "auto_confidence",
        "auto_score",
        "matched_must_find",
        "partial_must_find",
        "missing_must_find",
        "matched_numbers",
        "important_token_coverage",
        "object_type",
        "object_id",
        "source_evidence_id",
        "preview",
        "query",
        "must_find",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})


def _summarize(rows: list[dict[str, Any]], jsonl_path: Path, csv_path: Path) -> dict[str, Any]:
    labels = {"direct": 0, "partial": 0, "false": 0}
    by_facet: dict[str, dict[str, int]] = {}
    for row in rows:
        label = row["human_label"]
        labels[label] += 1
        facet_counts = by_facet.setdefault(row["facet"], {"direct": 0, "partial": 0, "false": 0})
        facet_counts[label] += 1
    return {
        "rows": len(rows),
        "human_label_counts": labels,
        "facet_label_counts": by_facet,
        "jsonl_output": str(jsonl_path),
        "csv_output": str(csv_path),
    }


def _csv_value(value: Any) -> str:
    if isinstance(value, list):
        return " | ".join(str(item) for item in value)
    if value is None:
        return ""
    return str(value)


if __name__ == "__main__":
    main()
