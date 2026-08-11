from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_official_product_surface_context_rows import build_official_product_surface_context_rows
from materialize_official_product_surface_pages import (  # noqa: E402
    DEFAULT_CLEAN_DIR,
    DEFAULT_OUTPUT,
    DEFAULT_RAW_DIR,
    HttpThenBrowserFetcher,
    PlaywrightBrowserFetcher,
    materialize_official_product_surface_pages,
    row_usable,
)
from sec_agent.product_family_source_routes import load_jsonl_rows


SCHEMA_VERSION = "finsight_family_official_product_surface_materialization_v0_1"
DEFAULT_SLOTS = REPO_ROOT / "data/manifests/company_product_slots_v0_1.jsonl"
DEFAULT_EXISTING_CONTEXT_ROWS = REPO_ROOT / "data/manifests/official_product_surface_context_rows_v0_1.jsonl"
DEFAULT_CONTEXT_SUMMARY = REPO_ROOT / "data/manifests/official_product_surface_context_rows_summary_v0_1.json"
DEFAULT_DOMAIN_CACHE = REPO_ROOT / "data/manifests/company_domain_locator_cache_v0_1.json"
DEFAULT_SUMMARY = REPO_ROOT / "data/manifests/family_official_product_surface_materialization_summary_v0_1.json"

DOMAIN_OVERRIDES: dict[str, list[str]] = {
    "000660.KS": ["skhynix.com"],
    "005930.KS": ["samsung.com"],
    "1211.HK": ["bydglobal.com", "byd.com", "en.byd.com", "bydbatterybox.com"],
    "2308.TW": ["deltaww.com"],
    "2317.TW": ["foxconn.com", "honhai.com"],
    "2382.TW": ["quantatw.com"],
    "300750.SZ": ["catl.com"],
    "3231.TW": ["wistron.com"],
    "373220.KS": ["lgensol.com"],
    "6146.T": ["disco.co.jp"],
    "6723.T": ["renesas.com"],
    "6752.T": ["na.industrial.panasonic.com", "panasonic.com"],
    "6758.T": ["sony.com"],
    "6857.T": ["advantest.com"],
    "8035.T": ["tel.com"],
    "ACLS": ["axcelis.com"],
    "ABNB": ["airbnb.com"],
    "AEP": ["aep.com"],
    "ANET": ["arista.com"],
    "BAC": ["bankofamerica.com"],
    "DELL": ["dell.com"],
    "FITB": ["53.com"],
    "ICE": ["ice.com"],
    "JPM": ["jpmorganchase.com"],
    "PCG": ["pge.com"],
    "QCOM": ["qualcomm.com"],
    "XOM": ["exxonmobil.com"],
    "XYL": ["xylem.com"],
    "ADM": ["adm.com"],
    "AJG": ["ajg.com"],
    "ALNY": ["alnylam.com"],
    "AEE": ["ameren.com", "amereninvestors.com"],
    "APD": ["airproducts.com"],
    "AVB": ["avalonbay.com"],
    "BALL": ["ball.com"],
    "BHP": ["bhp.com"],
    "BXP": ["bxp.com"],
    "BG": ["bunge.com"],
    "BMY": ["bms.com"],
    "C": ["citigroup.com"],
    "CAH": ["cardinalhealth.com"],
    "CPT": ["camdenliving.com"],
    "CSGP": ["costargroup.com"],
    "CVX": ["chevron.com"],
    "DAL": ["delta.com"],
    "DIOD": ["diodes.com"],
    "ENLT": ["enlightenergy.co.il"],
    "ESS": ["essexapartmenthomes.com", "essexpropertytrust.com"],
    "FANG": ["diamondbackenergy.com"],
    "FDXF": ["fedex.com"],
    "FRT": ["federalrealty.com"],
    "GFS": ["gf.com"],
    "GEHC": ["gehealthcare.com"],
    "GEV": ["gevernova.com"],
    "GE": ["geaerospace.com", "ge.com"],
    "HII": ["hii.com"],
    "HOOD": ["robinhood.com"],
    "HST": ["hosthotels.com"],
    "INTU": ["intuit.com"],
    "INVH": ["invitationhomes.com", "invh.com"],
    "IRM": ["ironmountain.com"],
    "LI": ["lixiang.com"],
    "LLY": ["lillyoncologypipeline.com", "medical.lilly.com", "lilly.com", "trials.lilly.com"],
    "LULU": ["lululemon.com", "shop.lululemon.com"],
    "LVS": ["sands.com"],
    "MELI": ["mercadolibre.com"],
    "MP": ["mpmaterials.com"],
    "MPWR": ["monolithicpower.com"],
    "MSFT": ["microsoft.com"],
    "NIO": ["nio.com"],
    "NWSA": ["newscorp.com"],
    "ODFL": ["odfl.com"],
    "ORLY": ["oreillyauto.com"],
    "OTIS": ["otis.com"],
    "OXY": ["oxy.com"],
    "PLUG": ["plugpower.com"],
    "PLTR": ["palantir.com"],
    "PPL": ["pplweb.com"],
    "PSKY": ["paramount.com"],
    "RIO": ["riotinto.com"],
    "SBAC": ["sbasite.com"],
    "SHOP": ["shopify.com"],
    "SO": ["southerncompany.com"],
    "SPG": ["simon.com"],
    "SQM": ["sqm.com"],
    "SWKS": ["skyworksinc.com"],
    "TDY": ["teledyne.com"],
    "TECH": ["bio-techne.com"],
    "TEL": ["te.com"],
    "TM": ["global.toyota"],
    "TMUS": ["t-mobile.com"],
    "TSM": ["tsmc.com"],
    "TSCO": ["corporate.tractorsupply.com", "tractorsupply.com"],
    "TTWO": ["take2games.com"],
    "UHS": ["uhs.com", "ir.uhs.com"],
    "UNP": ["up.com"],
    "UROY": ["uraniumroyalty.com"],
    "WMB": ["williams.com"],
    "WST": ["westpharma.com"],
    "WTW": ["wtwco.com"],
    "XEL": ["xcelenergy.com"],
    "XYZ": ["block.xyz"],
}
DOMAIN_OVERRIDES.update(
    {
        "BDX": ["bd.com"],
        "CASY": ["caseys.com"],
        "CHTR": ["spectrum.com", "corporate.charter.com", "charter.com"],
        "CL": ["colgatepalmolive.com", "colgate.com"],
        "CRL": ["criver.com"],
        "CVNA": ["carvana.com"],
        "DHI": ["drhorton.com"],
        "EL": ["elcompanies.com", "esteelauder.com"],
        "F": ["ford.com"],
        "HLT": ["hilton.com"],
        "IT": ["gartner.com"],
        "KEYS": ["keysight.com"],
        "KR": ["kroger.com", "thekrogerco.com"],
        "NVR": ["nvrinc.com", "ryanhomes.com"],
        "ON": ["onsemi.com"],
        "SJM": ["jmsmucker.com"],
        "SNY": ["sanofi.com"],
        "SYY": ["sysco.com"],
        "T": ["att.com"],
        "VRTX": ["vrtx.com"],
        "WAT": ["waters.com"],
        "ACN": ["accenture.com"],
        "ARGX": ["argenx.com", "argenx.jp"],
        "CRDO": ["credosemi.com"],
        "DASH": ["doordash.com", "about.doordash.com"],
        "EW": ["edwards.com"],
        "GDDY": ["godaddy.com"],
        "HAS": ["hasbro.com", "shop.hasbro.com"],
        "LCID": ["lucidmotors.com"],
        "LRCX": ["lamresearch.com"],
        "MAR": ["marriott.com"],
        "MKC": ["mccormickcorporation.com", "mccormick.com"],
        "MPC": ["marathonpetroleum.com"],
        "MTD": ["mt.com"],
        "NVO": ["novonordisk.com"],
        "ORCL": ["oracle.com"],
        "PG": ["pg.com"],
        "ROP": ["ropertech.com"],
        "SE": ["sea.com"],
        "SEDG": ["solaredge.com"],
        "SONY": ["sony.com"],
        "TENB": ["tenable.com"],
    }
)

BAD_SOURCE_DOMAINS = {
    "sec.gov",
    "www.sec.gov",
    "api.stlouisfed.org",
    "api.usaspending.gov",
    "api.openalex.org",
    "vpic.nhtsa.dot.gov",
    "apps.apple.com",
    "itunes.apple.com",
    "www.itunes.apple.com",
    "github.com",
    "www.github.com",
    "npmjs.com",
    "www.npmjs.com",
    "pypi.org",
    "huggingface.co",
    "cdw.com",
    "www.cdw.com",
    "api.eia.gov",
    "www.api.eia.gov",
}

FAMILY_PATH_HINTS: dict[str, list[str]] = {
    "gpu_accelerator": ["/en-us/data-center/", "/products", "/solutions", "/products-and-solutions"],
    "networking": ["/products", "/solutions", "/networking", "/data-center"],
    "semicap_equipment": ["/products", "/en/products", "/products-and-services"],
    "foundry": ["/technology", "/products", "/services", "/solutions"],
    "memory": ["/products", "/products/memory", "/solutions"],
    "server_oem": ["/products/servers", "/products", "/solutions", "/server"],
    "power_cooling": ["/products", "/solutions", "/data-centers", "/datacenter"],
    "power_grid_cooling": ["/products", "/solutions", "/data-centers", "/datacenter"],
    "cloud_infrastructure": ["/products", "/cloud", "/solutions", "/services"],
    "ai_platform": ["/products", "/ai", "/artificial-intelligence", "/solutions/ai"],
    "saas_crm_workflow": ["/products", "/solutions", "/software"],
    "data_observability_security": ["/products", "/solutions", "/security"],
    "smartphones_tablets": ["/products", "/smartphones", "/mobile", "/phones"],
    "pcs_peripherals": ["/products", "/laptops", "/computers"],
    "wearables_devices": ["/products", "/wearables", "/watch"],
    "glp1_metabolic": ["/products", "/our-medicines", "/medicines", "/therapeutic-areas"],
    "oncology_immunology": ["/products", "/our-medicines", "/medicines", "/pipeline"],
    "vaccines_infectious": ["/products", "/vaccines", "/our-medicines", "/medicines"],
    "medtech_devices": ["/products", "/solutions", "/medical-devices"],
    "ev_vehicle_platform": ["/vehicles", "/models", "/products", "/cars"],
    "battery_charging_autonomy": ["/products", "/charging", "/battery", "/technology"],
    "mass_retail_grocery": ["/products", "/services", "/grocery"],
    "home_improvement": ["/products", "/c", "/departments"],
    "consumer_brands_cpg": ["/brands", "/products", "/our-brands"],
    "agriculture_commodities_ingredients": ["/products-services", "/en-us/products-services", "/products", "/services", "/nutrition", "/ingredients"],
    "restaurants_menu": ["/menu", "/products", "/food"],
    "travel_marketplace": ["/products", "/services", "/travel"],
    "renewable_power_solar_hydrogen": ["/projects/", "/products", "/solutions", "/energy/"],
    "digital_media_content": ["/games/", "/brands", "/products", "/news", "/sitemap.xml"],
    "logistics_transportation": ["/us/en/skymiles/overview", "/shipping/freight.html", "/products", "/services"],
    "real_estate_infrastructure_reit": ["/communities", "/", "/properties", "/products", "/services"],
    "real_estate_data_marketplace": ["/products", "/about-us/our-brands", "/", "/services"],
}

TICKER_PATH_HINTS: dict[str, list[str]] = {
    "1211.HK": ["/energy/", "/us", "/"],
    "005930.KS": ["/us/business/semiconductor/"],
    "300750.SZ": ["/en/products/", "/en/solution/"],
    "6146.T": ["/eg/products/", "/eg/solution/", "/eg/products/catalog/"],
    "6752.T": ["/products", "/"],
    "8035.T": ["/product/"],
    "DAL": ["/us/en/skymiles/overview", "/us/en"],
    "ENLT": ["/projects/", "/"],
    "ESS": ["/", "/communities"],
    "INTU": ["/products/", "/"],
    "MSFT": ["/en-us/ai", "/en-us/microsoft-copilot", "/en-us/microsoft-365/copilot"],
    "PLTR": ["/sitemap.xml", "/platforms/aip/", "/platforms/foundry/"],
    "SWKS": ["/sitemap.xml", "/en/Products"],
    "TTWO": ["/games/", "/ir", "/"],
    "TSCO": ["/", "/products", "/services"],
    "2382.TW": [
        "/quanta/english/product/qci_all.aspx",
        "/quanta/english/product/qci_es.aspx",
        "/quanta/english/product/qci_nb.aspx",
        "/quanta/english/about/company.aspx",
        "/quanta/english/service/serviceinfo.aspx",
    ],
    "AEE": ["/about-ameren", "/investors/annual-reports/default.aspx", "/"],
    "C": ["/global/about-us", "/global/investor-relations/annual-reports-and-proxy-statements", "/global/consumer-bank", "/global/institutional-clients-group"],
    "DIOD": [
        "/products",
        "/products/discrete-semiconductors",
        "/products/discrete-semiconductors/diodes-and-rectifiers",
        "/products/discrete-semiconductors/mosfets",
        "/products/discrete-semiconductors/protection-devices",
    ],
    "ACLS": ["/products", "/products/puriona", "/products/gsd", "/products/integra"],
    "ACN": ["/us-en/services", "/us-en/services/cloud", "/us-en/services/data-ai", "/us-en/services/technology"],
    "ADI": ["/en/products.html", "/en/solutions.html", "/en/product-category.html", "/en/products/processors-microcontrollers.html"],
    "ARGX": ["/pipeline", "/products", "/en/science/pipeline", "/en/products"],
    "CASY": ["/menu", "/products", "/c/food", "/c/drinks"],
    "CL": ["/en-us/brands", "/en-us/products", "/en-us/oral-health", "/en-us/products/toothpaste"],
    "CRDO": ["/products", "/products/line-cards", "/products/optical-dsps", "/products/serdes-chiplets"],
    "CRL": ["/products-services", "/products-services/discovery-services", "/products-services/research-models-services", "/products-services/safety-assessment"],
    "CVNA": ["/cars", "/sell-my-car", "/auto-loan-calculator", "/vehicle-protection"],
    "DASH": ["/consumer", "/business", "/merchant", "/dashpass"],
    "DELL": ["/en-us/shop", "/en-us/dt/servers", "/en-us/dt/storage", "/en-us/dt/solutions/artificial-intelligence"],
    "DG": ["/c/food-beverage", "/c/health", "/c/cleaning", "/c/household"],
    "EL": ["/en/our-brands", "/en/brands", "/brands"],
    "EW": ["/healthcare-professionals/products-services", "/healthcare-professionals/products-services/transcatheter-aortic-valve-replacement", "/healthcare-professionals/products-services/surgical-structural-heart", "/healthcare-professionals/products-services/critical-care"],
    "GDDY": ["/websites", "/hosting", "/domains", "/websites/website-builder"],
    "HAS": ["/en-us/brands", "/en-us/shop", "/en-us/toys-games", "/en-us/brands/nerf"],
    "HLT": ["/en/brands", "/en/hilton-honors", "/en/locations", "/en/hotels"],
    "HST": ["/properties", "/portfolio", "/about", "/"],
    "IT": ["/en/products", "/en/information-technology/products", "/en/conferences", "/en/consulting"],
    "INVH": ["/home/default.aspx", "/about-us", "/"],
    "KEYS": ["/us/en/products.html", "/us/en/solutions.html", "/us/en/products/software.html", "/us/en/products/network-test.html"],
    "KR": ["/pr/our-brands", "/brands", "/products", "/"],
    "LCID": ["/air", "/gravity", "/technology", "/studio"],
    "LRCX": ["/products", "/products/etch", "/products/deposition", "/products/clean"],
    "LLY": [
        "/",
        "/us/products/medical-information/oncology",
        "/science/research-development/pipeline",
        "/medicines/current",
        "/conditions/cancer",
        "/conditions/dermatology",
        "/science/clinical-trials/cancer",
        "/en-US/research-areas/cancer",
    ],
    "LULU": ["/", "/c/women-clothes/n14uwk", "/c/men-clothes/n1oxc7", "/story/women", "/story/men"],
    "MAR": ["/en-us/brands.mi", "/loyalty.mi", "/en-us/hotels.mi", "/"],
    "MELI": ["/", "/about", "/mercado-libre", "/mercado-pago"],
    "MKC": ["/en-us/products", "/en-us/recipes", "/en/products", "/en/brands"],
    "MPC": ["/What-We-Do/Products", "/Operations/Refining", "/Operations/Marketing", "/"],
    "MTD": ["/us/en/home/products.html", "/us/en/home/applications.html", "/us/en/home/products/Laboratory_Analytics_Browse.html", "/us/en/home/products/Industrial_Weighing_Solutions.html"],
    "NVO": ["/products", "/disease-areas", "/science-and-technology", "/products/our-medicines"],
    "ORCL": ["/products", "/cloud", "/database", "/applications"],
    "ORLY": ["/shop/b", "/shop/AllBrands", "/shop/b/oil--chemicals---fluids/738983331189", "/shop/b/performance/2fa4e31cd340"],
    "PG": ["/brands", "/products", "/brands/beauty", "/brands/health-care"],
    "ROP": ["/businesses", "/companies", "/about", "/"],
    "SE": ["/products", "/businesses", "/garena", "/shopee"],
    "SEDG": ["/us/products-and-solutions", "/us/products-and-solutions/inverters", "/us/products-and-solutions/power-optimizers", "/us/products-and-solutions/storage-and-backup"],
    "SJM": ["/brands", "/products", "/our-brands", "/"],
    "SNY": ["/en/our-products", "/en/science-and-innovation/pipeline", "/en/your-health/our-medicines", "/en/vaccines"],
    "SONY": ["/en/SonyInfo/products/", "/electronics", "/playstation", "/semicon"],
    "SYY": ["/Products", "/products", "/solutions", "/"],
    "TENB": ["/products", "/cloud-security", "/vulnerability-management", "/identity-exposure"],
    "TJX": ["/company/our-businesses", "/stores", "/about-us", "/"],
    "TMUS": ["/cell-phones", "/plans", "/home-internet", "/business"],
    "TSM": ["/english/dedicatedFoundry/technology", "/english/dedicatedFoundry/services", "/english/dedicatedFoundry/manufacturing", "/english/products"],
    "VRTX": ["/our-science/pipeline", "/medicines", "/therapeutic-areas", "/"],
    "WAT": ["/nextgen/us/en/products.html", "/nextgen/us/en/solutions.html", "/nextgen/us/en/products/chromatography.html", "/nextgen/us/en/products/mass-spectrometry.html"],
    "UHS": ["/", "/annual-reports", "/news/universal-health-services-inc-publishes-2025-annual-report/"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover and materialize official product pages for product-family slots.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--existing-materialized", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--clean-dir", type=Path, default=DEFAULT_CLEAN_DIR)
    parser.add_argument("--domain-cache", type=Path, default=DEFAULT_DOMAIN_CACHE)
    parser.add_argument("--output-materialized", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output-context-rows", type=Path, default=DEFAULT_EXISTING_CONTEXT_ROWS)
    parser.add_argument("--output-context-summary", type=Path, default=DEFAULT_CONTEXT_SUMMARY)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--tickers", nargs="*", default=[])
    parser.add_argument("--max-targets", type=int, default=0, help="0 means all target companies.")
    parser.add_argument("--max-urls-per-issuer", type=int, default=3)
    parser.add_argument("--timeout-s", type=float, default=4.0)
    parser.add_argument("--min-clean-text-chars", type=int, default=300)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--browser-fallback", action="store_true", help="Use Playwright browser rendering after blocked/non-content HTTP fetches. Runs serially.")
    parser.add_argument("--stdout-summary-only", action="store_true", help="Print a compact stdout summary while keeping full attempts in the summary artifact.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    slots = load_jsonl_rows(args.slots)
    raw_existing_rows = load_jsonl_rows(args.existing_materialized)
    existing_rows = _filter_existing_materialized_rows_by_domain(existing_rows=raw_existing_rows, slots=slots)
    cache = _load_json(args.domain_cache)
    profiles, resolver_report = build_family_product_surface_profiles(
        slots=slots,
        existing_rows=existing_rows,
        domain_cache=cache,
        ticker_filter={ticker.upper() for ticker in args.tickers if ticker.strip()},
        max_targets=args.max_targets,
        resolver_workers=max(1, int(args.workers or 1)),
    )
    args.domain_cache.parent.mkdir(parents=True, exist_ok=True)
    args.domain_cache.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.browser_fallback:
        with HttpThenBrowserFetcher(
            PlaywrightBrowserFetcher(),
            min_clean_text_chars=int(args.min_clean_text_chars or 300),
        ) as fetcher:
            materialized = materialize_official_product_surface_pages(
                profiles=profiles,
                existing_rows=existing_rows,
                raw_dir=args.raw_dir,
                clean_dir=args.clean_dir,
                generated_at=generated_at,
                max_urls_per_issuer=args.max_urls_per_issuer,
                timeout_s=args.timeout_s,
                min_clean_text_chars=args.min_clean_text_chars,
                skip_existing=args.skip_existing,
                prune_unusable_existing=True,
                fetch=fetcher,
            )
        materialized["summary"]["execution_mode"] = "serial_http_then_browser"
        materialized["summary"]["workers"] = 1
    elif int(args.workers or 1) > 1:
        materialized = _materialize_profiles_parallel(
            profiles=profiles,
            existing_rows=existing_rows,
            raw_dir=args.raw_dir,
            clean_dir=args.clean_dir,
            generated_at=generated_at,
            max_urls_per_issuer=args.max_urls_per_issuer,
            timeout_s=args.timeout_s,
            min_clean_text_chars=args.min_clean_text_chars,
            skip_existing=args.skip_existing,
            workers=int(args.workers or 1),
        )
    else:
        materialized = materialize_official_product_surface_pages(
            profiles=profiles,
            existing_rows=existing_rows,
            raw_dir=args.raw_dir,
            clean_dir=args.clean_dir,
            generated_at=generated_at,
            max_urls_per_issuer=args.max_urls_per_issuer,
            timeout_s=args.timeout_s,
            min_clean_text_chars=args.min_clean_text_chars,
            skip_existing=args.skip_existing,
            prune_unusable_existing=False,
        )
    args.output_materialized.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.output_materialized, materialized["rows"])
    context_rows = build_official_product_surface_context_rows(
        materialized["rows"],
        generated_at=generated_at,
        max_rows_per_page=12,
    )
    _write_jsonl(args.output_context_rows, context_rows)
    context_summary = {
        "schema_version": "finsight_family_official_product_surface_context_summary_v0_1",
        "generated_at": generated_at,
        "context_row_count": len(context_rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in context_rows}),
        "boundary": "Official product pages are bounded taxonomy/spec context only; no sales/share/ASP/inventory/sell-through authority.",
    }
    args.output_context_summary.write_text(json.dumps(context_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": "pass" if materialized["summary"].get("output_row_count", 0) else "gap",
        "profile_count": len(profiles),
        "resolver_report": resolver_report,
        "materialization_summary": materialized["summary"],
        "existing_domain_binding_pruned_count": len(raw_existing_rows) - len(existing_rows),
        "context_summary": context_summary,
        "outputs": {
            "materialized_rows": str(args.output_materialized),
            "context_rows": str(args.output_context_rows),
            "domain_cache": str(args.domain_cache),
        },
        "boundary": "Discovered URLs are official-product-surface candidates and must pass parser/entity binding before Product Specialist can use them.",
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stdout_summary = _compact_stdout_summary(summary) if args.stdout_summary_only else summary
    print(json.dumps(stdout_summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _materialize_profiles_parallel(
    *,
    profiles: Mapping[str, Mapping[str, Any]],
    existing_rows: list[Mapping[str, Any]],
    raw_dir: Path,
    clean_dir: Path,
    generated_at: str,
    max_urls_per_issuer: int,
    timeout_s: float,
    min_clean_text_chars: int,
    skip_existing: bool,
    workers: int,
) -> dict[str, Any]:
    rows_by_key = {_materialized_row_key(row): dict(row) for row in existing_rows if _materialized_row_key(row)}
    existing_by_ticker: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in existing_rows:
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            existing_by_ticker[ticker].append(row)

    attempts: list[dict[str, Any]] = []
    new_materialized = 0
    updated_materialized = 0
    skipped_existing = 0
    blocked = 0
    failed = 0

    def run_one(ticker: str, profile: Mapping[str, Any]) -> dict[str, Any]:
        return materialize_official_product_surface_pages(
            profiles={ticker: profile},
            existing_rows=existing_by_ticker.get(ticker, []),
            raw_dir=raw_dir,
            clean_dir=clean_dir,
            generated_at=generated_at,
            max_urls_per_issuer=max_urls_per_issuer,
            timeout_s=timeout_s,
            min_clean_text_chars=min_clean_text_chars,
            skip_existing=skip_existing,
            prune_unusable_existing=False,
        )

    with ThreadPoolExecutor(max_workers=max(1, int(workers or 1))) as executor:
        future_map = {executor.submit(run_one, ticker, profile): ticker for ticker, profile in sorted(profiles.items())}
        for future in as_completed(future_map):
            result = future.result()
            summary = result.get("summary") or {}
            attempts.extend(summary.get("attempts") or [])
            new_materialized += int(summary.get("new_materialized_count") or 0)
            updated_materialized += int(summary.get("updated_materialized_count") or 0)
            skipped_existing += int(summary.get("skipped_existing_count") or 0)
            blocked += int(summary.get("blocked_count") or 0)
            failed += int(summary.get("failed_count") or 0)
            for row in result.get("rows") or []:
                key = _materialized_row_key(row)
                if key:
                    rows_by_key[key] = dict(row)

    rows = sorted(rows_by_key.values(), key=lambda item: (str(item.get("ticker") or ""), str(item.get("source_url") or item.get("url") or "")))
    summary = {
        "schema_version": "fin_agent_official_product_surface_materialization_summary_v0_1",
        "generated_at": generated_at,
        "status": "pass" if new_materialized or updated_materialized or rows else "gap",
        "existing_input_count": len(existing_rows),
        "output_row_count": len(rows),
        "ticker_count": len({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "tickers": sorted({str(row.get("ticker") or "") for row in rows if str(row.get("ticker") or "")}),
        "attempted_count": len(attempts),
        "new_materialized_count": new_materialized,
        "updated_materialized_count": updated_materialized,
        "skipped_existing_count": skipped_existing,
        "pruned_unusable_existing_count": 0,
        "blocked_count": blocked,
        "failed_count": failed,
        "attempts": sorted(attempts, key=lambda item: (str(item.get("ticker") or ""), str(item.get("url") or ""))),
        "boundary": "Materialized official product pages are bounded product taxonomy/spec context only; no sales/share/ASP/inventory/sell-through authority.",
        "execution_mode": "parallel_by_ticker",
        "workers": max(1, int(workers or 1)),
    }
    return {"rows": rows, "summary": summary}


def _materialized_row_key(row: Mapping[str, Any]) -> str:
    ticker = str(row.get("ticker") or "").strip().upper()
    url = str(row.get("source_url") or row.get("url") or "").strip()
    return f"{ticker}|{url}" if ticker and url else ""


def build_family_product_surface_profiles(
    *,
    slots: list[Mapping[str, Any]],
    existing_rows: list[Mapping[str, Any]],
    domain_cache: dict[str, Any],
    ticker_filter: set[str] | None = None,
    max_targets: int = 0,
    resolver_workers: int = 1,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    existing_tickers = {str(row.get("ticker") or "").upper() for row in existing_rows if row.get("ticker")}
    targets_by_ticker: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for slot in slots:
        ticker = str(slot.get("ticker") or "").upper()
        if not ticker or (ticker_filter and ticker not in ticker_filter):
            continue
        if not _needs_official_product_surface_target(slot=slot, ticker=ticker, existing_tickers=existing_tickers):
            continue
        targets_by_ticker[ticker].append(slot)
    selected_tickers = sorted(targets_by_ticker)
    if max_targets and max_targets > 0:
        selected_tickers = selected_tickers[:max_targets]
    resolver_status = defaultdict(int)
    profile_results: list[tuple[str, dict[str, Any] | None, str]] = []

    def build_one(ticker: str) -> tuple[str, dict[str, Any] | None, str]:
        rows = targets_by_ticker[ticker]
        company_name = str(rows[0].get("company_name") or ticker).strip()
        if ticker in DOMAIN_OVERRIDES:
            domains = _prefer_com_variants(DOMAIN_OVERRIDES[ticker])
            domain_source = "domain_override"
            domain_cache[ticker] = {"ticker": ticker, "company_name": company_name, "domains": domains, "resolver_sources": {"domain_override": domains}}
        else:
            domains = _filter_company_domains(
                ticker=ticker,
                company_name=company_name,
                domains=_domains_from_slot_urls(rows),
            )
            domain_source = "existing_official_url"
        if not domains:
            domains = _resolve_domains_with_cache(ticker=ticker, company_name=company_name, cache=domain_cache)
            domain_source = "clearbit_autocomplete" if domains else "unresolved"
        if not domains:
            return ticker, None, "domain_unresolved"
        urls = _candidate_urls(domains=domains, slots=rows)
        if not urls:
            return ticker, None, "no_candidate_urls"
        return ticker, {
            "ticker": ticker,
            "company_name": company_name,
            "issuer_name": company_name,
            "company_domains": domains,
            "official_product_urls": urls,
            "official_product_surfaces": _unique_strings([row.get("product_slot_name") or row.get("family_name") or row.get("family_id") for row in rows])[:12],
            "official_metric_leads": ["product taxonomy", "product specification", "product availability context"],
            "profile_source": domain_source,
        }, f"domain_{domain_source}"

    if int(resolver_workers or 1) > 1 and len(selected_tickers) > 1:
        with ThreadPoolExecutor(max_workers=max(1, int(resolver_workers or 1))) as executor:
            futures = [executor.submit(build_one, ticker) for ticker in selected_tickers]
            for future in as_completed(futures):
                profile_results.append(future.result())
    else:
        profile_results = [build_one(ticker) for ticker in selected_tickers]

    profiles: dict[str, dict[str, Any]] = {}
    for ticker, profile, status in sorted(profile_results, key=lambda item: item[0]):
        resolver_status[status] += 1
        if profile:
            profiles[ticker] = profile
    return profiles, {"target_ticker_count": len(targets_by_ticker), "selected_ticker_count": len(selected_tickers), "profile_count": len(profiles), "resolver_status": dict(sorted(resolver_status.items()))}


def _needs_official_product_surface_target(*, slot: Mapping[str, Any], ticker: str, existing_tickers: set[str]) -> bool:
    status = str(slot.get("slot_status") or "")
    has_official_surface_url = bool(_domains_from_slot_urls([slot]))
    has_materialized_product_page = "company_product_page" in {str(value) for value in slot.get("slot_source_ids") or []}
    if status == "official_surface_slot" and has_official_surface_url and has_materialized_product_page:
        return ticker not in existing_tickers
    if status in {"seed_needs_locator", "company_route_needs_family_binding", "source_discovery_needed"}:
        return True
    if status in {"product_kpi_exact_slot", "bounded_context_slot"}:
        return not has_materialized_product_page
    if ticker not in existing_tickers and not has_official_surface_url:
        return True
    return False


def _filter_existing_materialized_rows_by_domain(
    *,
    existing_rows: list[Mapping[str, Any]],
    slots: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    company_by_ticker: dict[str, str] = {}
    for slot in slots:
        ticker = str(slot.get("ticker") or "").upper()
        company_name = str(slot.get("company_name") or "").strip()
        if ticker and company_name and ticker not in company_by_ticker:
            company_by_ticker[ticker] = company_name

    filtered: list[Mapping[str, Any]] = []
    for row in existing_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        domain = urlparse(str(row.get("source_url") or "")).netloc.lower().split(":")[0]
        if domain.startswith("www."):
            domain = domain[4:]
        if not domain:
            continue
        has_usability_metadata = bool(row.get("title") or row.get("clean_text_path") or row.get("clean_text_char_count"))
        if has_usability_metadata and not row_usable(row, min_clean_text_chars=250):
            continue
        if _materialized_domain_allowed(ticker=ticker, company_name=company_by_ticker.get(ticker, ticker), domain=domain):
            filtered.append(row)
    return filtered


def _materialized_domain_allowed(*, ticker: str, company_name: str, domain: str) -> bool:
    key = ticker.upper()
    raw_domain = str(domain or "").lower().strip()
    raw_domain = re.sub(r"^https?://", "", raw_domain).split("/")[0].split(":")[0]
    if raw_domain.startswith("www."):
        raw_domain = raw_domain[4:]
    override_domains = DOMAIN_OVERRIDES.get(key)
    if override_domains:
        allowed = {item.lower().removeprefix("www.") for item in override_domains}
        return any(raw_domain == item or raw_domain.endswith("." + item) for item in allowed)
    normalized = _filter_locator_domains([raw_domain])
    if not normalized:
        return False
    domain = normalized[0]
    return domain in _filter_company_domains(ticker=key, company_name=company_name, domains=[domain])


def _resolve_domains_with_cache(*, ticker: str, company_name: str, cache: dict[str, Any]) -> list[str]:
    key = ticker.upper()
    if key in DOMAIN_OVERRIDES:
        domains = _prefer_com_variants(DOMAIN_OVERRIDES[key])
        cache[key] = {"ticker": key, "company_name": company_name, "domains": domains, "resolver_sources": {"domain_override": domains}}
        return domains
    if key in cache and cache[key].get("domains"):
        cached = _filter_company_domains(ticker=key, company_name=company_name, domains=list(cache[key].get("domains") or []))
        if cached:
            return _prefer_com_variants(cached)
    sources: dict[str, list[str]] = {}
    domains = _clearbit_domains(company_name)
    domains = _filter_company_domains(ticker=ticker, company_name=company_name, domains=domains)
    sources["clearbit_autocomplete"] = domains
    if not domains:
        domains = _bing_official_domains(company_name=company_name, ticker=ticker)
        domains = _filter_company_domains(ticker=ticker, company_name=company_name, domains=domains)
        sources["bing_official_website_locator"] = domains
    if not domains:
        domains = _guess_company_domains(company_name)
        sources["company_name_domain_guess"] = domains
    domains = _prefer_com_variants(domains)
    cache[key] = {"ticker": key, "company_name": company_name, "domains": domains, "resolver_sources": sources}
    return domains


def _clearbit_domains(company_name: str) -> list[str]:
    query = quote(company_name)
    url = f"https://autocomplete.clearbit.com/v1/companies/suggest?query={query}"
    try:
        body = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=8).read().decode("utf-8", errors="replace")
        rows = json.loads(body)
    except Exception:
        return []
    domains: list[str] = []
    for row in rows[:3]:
        domain = str(row.get("domain") or "").lower().strip()
        if not domain or not re.search(r"[a-z0-9-]+\.[a-z]{2,}$", domain):
            continue
        domains.append(domain)
        if domain.endswith(".co"):
            domains.insert(max(0, len(domains) - 1), domain[:-3] + ".com")
    return _unique_strings(domains)[:4]


def _bing_official_domains(*, company_name: str, ticker: str) -> list[str]:
    query = quote(f"{company_name} {ticker} official website")
    url = f"https://www.bing.com/search?q={query}"
    try:
        body = urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=10).read().decode("utf-8", errors="replace")
    except Exception:
        return []
    domains: list[str] = []
    domains.extend(re.findall(r'aria-label="([a-z0-9.-]+\.[a-z]{2,})"', body, flags=re.I))
    for encoded in re.findall(r"[?&]u=(a1[a-zA-Z0-9_\-=]+)", html.unescape(body)):
        decoded = _decode_bing_u(encoded)
        if decoded:
            domain = urlparse(decoded).netloc.lower().split(":")[0]
            if domain.startswith("www."):
                domain = domain[4:]
            domains.append(domain)
    return _filter_locator_domains(domains)[:4]


def _decode_bing_u(value: str) -> str:
    if not value.startswith("a1"):
        return ""
    payload = value[2:].replace("-", "+").replace("_", "/")
    payload += "=" * (-len(payload) % 4)
    try:
        return base64.b64decode(payload).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _guess_company_domains(company_name: str) -> list[str]:
    text = re.sub(r"[^A-Za-z0-9& ]+", " ", company_name or "").strip().lower()
    text = text.replace("&", " and ")
    stopwords = {
        "corp",
        "corporation",
        "inc",
        "incorporated",
        "company",
        "co",
        "ltd",
        "limited",
        "plc",
        "holdings",
        "holding",
        "global",
        "group",
        "technologies",
        "technology",
        "networks",
        "systems",
        "laboratories",
        "pharmaceuticals",
        "therapeutics",
        "industries",
        "services",
        "international",
        "class",
        "ordinary",
        "shares",
        "nv",
        "n",
        "v",
        "sa",
        "ag",
        "se",
    }
    words = [word for word in text.split() if word and word not in stopwords]
    candidates: list[str] = []
    if words:
        candidates.append(f"{words[0]}.com")
    if len(words) >= 2:
        candidates.append(f"{''.join(words[:2])}.com")
        candidates.append(f"{'-'.join(words[:2])}.com")
    if len(words) >= 3:
        candidates.append(f"{''.join(words[:3])}.com")
    reachable: list[str] = []
    for domain in _filter_locator_domains(candidates):
        if _domain_reachable(domain):
            reachable.append(domain)
    return reachable[:4]


def _domain_reachable(domain: str) -> bool:
    for url in (f"https://www.{domain}/", f"https://{domain}/"):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=5) as response:
                return int(getattr(response, "status", 200) or 200) < 500
        except Exception:
            continue
    return False


def _filter_locator_domains(domains: list[str]) -> list[str]:
    blocked = {
        "bing.com",
        "microsoft.com",
        "wikipedia.org",
        "linkedin.com",
        "facebook.com",
        "twitter.com",
        "x.com",
        "youtube.com",
        "yahoo.com",
        "finance.yahoo.com",
        "sec.gov",
        "nasdaq.com",
        "nyse.com",
        "marketscreener.com",
        "stockanalysis.com",
        "bloomberg.com",
        "reuters.com",
        "crunchbase.com",
    }
    out: list[str] = []
    for domain in domains:
        normalized = str(domain or "").lower().strip()
        normalized = re.sub(r"^https?://", "", normalized).split("/")[0].split(":")[0]
        if normalized.startswith("www."):
            normalized = normalized[4:]
        if not re.search(r"^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}$", normalized):
            continue
        if normalized in blocked or any(normalized.endswith("." + item) for item in blocked):
            continue
        out.append(normalized)
    return _unique_strings(out)


def _filter_company_domains(*, company_name: str, domains: list[str], ticker: str = "") -> list[str]:
    tokens = _company_core_tokens(company_name)
    compact_all_tokens = _company_compact_tokens(company_name)
    ticker_l = re.sub(r"[^a-z0-9]+", "", str(ticker or "").lower())
    acronym = "".join(token[0] for token in tokens if token)
    if not tokens and not ticker_l:
        return _filter_locator_domains(domains)
    out: list[str] = []
    compact_name = "".join(tokens)
    weak_tokens = {
        "american",
        "bank",
        "capital",
        "electric",
        "energy",
        "enterprise",
        "financial",
        "first",
        "global",
        "group",
        "international",
        "national",
        "power",
        "resources",
        "services",
        "systems",
        "technologies",
        "technology",
        "third",
        "united",
        "arthur",
        "bristol",
        "charles",
        "edwards",
        "martin",
        "simon",
    }
    for domain in _filter_locator_domains(domains):
        domain_root = domain.split(".")[0].replace("-", "")
        if ticker_l and len(ticker_l) >= 3 and domain_root == ticker_l:
            if len(domain.split(".")) > 2:
                continue
            out.append(domain)
            continue
        if acronym and len(acronym) >= 3 and domain_root == acronym:
            if len(domain.split(".")) > 2:
                continue
            out.append(domain)
            continue
        strong_tokens = [token for token in tokens if len(token) >= 4 and token not in weak_tokens]
        comparable_tokens = strong_tokens if len(strong_tokens) == 1 else strong_tokens[1:]
        if any(domain_root == token for token in strong_tokens):
            out.append(domain)
            continue
        # Prefix-only matches are dangerous for short brand words: `xylemonline.com`
        # is not Xylem and `blockin.com.br` is not Block. Only use prefix evidence
        # for later distinctive tokens in multi-token names or compact legal names.
        if comparable_tokens and any(len(token) >= 6 and domain_root.startswith(token) and len(domain_root) <= len(token) + 8 for token in comparable_tokens):
            out.append(domain)
            continue
        if len(tokens) >= 2 and len(compact_name) >= 8 and domain_root.startswith(compact_name[: min(len(compact_name), 14)]):
            out.append(domain)
            continue
        if len(compact_all_tokens) >= 6 and domain_root.startswith(compact_all_tokens[: min(len(compact_all_tokens), 14)]):
            out.append(domain)
            continue
    return _unique_strings(out)


def _company_core_tokens(company_name: str) -> list[str]:
    text = re.sub(r"[^A-Za-z0-9& ]+", " ", company_name or "").lower().replace("&", " and ")
    stopwords = {
        "ag",
        "class",
        "co",
        "company",
        "corp",
        "corporation",
        "inc",
        "incorporated",
        "industry",
        "limited",
        "ltd",
        "nv",
        "ordinary",
        "plc",
        "sa",
        "se",
        "shares",
        "technologies",
        "technology",
    }
    tokens = [token for token in text.split() if len(token) >= 3 and token not in stopwords]
    if not tokens:
        tokens = [token for token in text.split() if len(token) >= 2 and token not in stopwords]
    return tokens[:5]


def _company_compact_tokens(company_name: str) -> str:
    text = re.sub(r"[^A-Za-z0-9& ]+", " ", company_name or "").lower().replace("&", " and ")
    stopwords = {
        "ag",
        "and",
        "class",
        "co",
        "company",
        "corp",
        "corporation",
        "inc",
        "incorporated",
        "limited",
        "ltd",
        "nv",
        "ordinary",
        "plc",
        "sa",
        "se",
        "shares",
    }
    return "".join(token for token in text.split() if len(token) >= 2 and token not in stopwords)


def _prefer_com_variants(domains: list[str]) -> list[str]:
    def rank(domain: str) -> tuple[int, str]:
        text = str(domain).lower()
        return (0 if text.endswith(".com") else 1, text)

    return sorted(_unique_strings(domains), key=rank)[:4]


def _domains_from_slot_urls(slots: list[Mapping[str, Any]]) -> list[str]:
    domains: list[str] = []
    for slot in slots:
        for url in slot.get("sample_urls") or []:
            domain = urlparse(str(url)).netloc.lower().split(":")[0]
            if not domain or domain in BAD_SOURCE_DOMAINS or any(domain.endswith("." + bad) for bad in BAD_SOURCE_DOMAINS):
                continue
            domains.append(domain[4:] if domain.startswith("www.") else domain)
    return _unique_strings(domains)[:4]


def _candidate_urls(*, domains: list[str], slots: list[Mapping[str, Any]]) -> list[str]:
    direct_urls: list[str] = []
    allowed_domains = {domain.lower().removeprefix("www.") for domain in domains}
    for slot in slots:
        for raw_url in slot.get("sample_urls") or []:
            url = str(raw_url or "").strip()
            parsed = urlparse(url)
            domain = parsed.netloc.lower().split(":")[0].removeprefix("www.")
            if not parsed.scheme.startswith("http") or not domain:
                continue
            if domain in BAD_SOURCE_DOMAINS or any(domain.endswith("." + bad) for bad in BAD_SOURCE_DOMAINS):
                continue
            if allowed_domains and not any(domain == item or domain.endswith("." + item) for item in allowed_domains):
                continue
            direct_urls.append(url)
    paths: list[str] = []
    tickers = _unique_strings([slot.get("ticker") for slot in slots])
    for ticker in tickers:
        paths.extend(TICKER_PATH_HINTS.get(str(ticker).upper(), []))
    for slot in slots:
        family_id = str(slot.get("family_id") or "")
        paths.extend(FAMILY_PATH_HINTS.get(family_id, []))
    paths.extend(["/", "/products", "/solutions", "/products-and-services", "/services"])
    paths = _unique_strings(paths)[:8]
    bases: list[str] = []
    for domain in domains[:3]:
        if domain.startswith("www."):
            domain_bases = [f"https://{domain}"]
        elif domain.count(".") >= 2:
            domain_bases = [f"https://{domain}"]
        else:
            domain_bases = [f"https://www.{domain}", f"https://{domain}"]
        bases.extend(domain_bases)
    urls: list[str] = []
    for path in paths:
        for base in bases:
            urls.append(base.rstrip("/") + (path if path.startswith("/") else "/" + path))
    return _unique_strings(direct_urls + urls)[:60]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _unique_strings(values: list[Any] | tuple[Any, ...]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            out.append(text)
            seen.add(text)
    return out


def _compact_stdout_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    materialization = dict(summary.get("materialization_summary") or {})
    attempts = [item for item in materialization.pop("attempts", []) or [] if isinstance(item, Mapping)]
    materialization["attempt_status_counts"] = dict(sorted(Counter(str(item.get("status") or "") for item in attempts).items()))
    materialization["top_failure_reasons"] = dict(
        Counter(
            str(item.get("reason") or "")
            for item in attempts
            if str(item.get("status") or "") != "materialized"
        ).most_common(12)
    )
    materialization["materialized_tickers"] = sorted(
        {
            str(item.get("ticker") or "")
            for item in attempts
            if str(item.get("status") or "") == "materialized" and str(item.get("ticker") or "")
        }
    )
    compact = dict(summary)
    compact["materialization_summary"] = materialization
    return compact


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
