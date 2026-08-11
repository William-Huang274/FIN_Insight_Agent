from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sec_agent.exact_slot_contracts import build_exact_slot_rows


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_broad_official_careers_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_broad_official_careers_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_amazon_jobs_json_api_rows_enter_hiring_exact_slot(tmp_path: Path) -> None:
    company = {
        "ticker": "AMZN",
        "company_name": "Amazon",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    payload = {
        "jobs": [
            {
                "title": "Data Center Engineering Operations Technician",
                "normalized_location": "Columbus, OH, United States",
                "posted_date": "2026-06-20",
                "job_path": "/en/jobs/123/data-center-engineering-operations-technician",
            }
        ]
    }

    rows = MODULE._parse_amazon_jobs_payload(
        company,
        json.dumps(payload),
        source_url="https://www.amazon.jobs/en/search.json?offset=0&result_limit=10&sort=relevant",
        generated_at="2026-06-20T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "AMZN"
    assert row["underlying_source_id"] == "amazon_jobs_api"
    assert row["requirement_id"] == "hiring_capacity_proxy"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-20T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_atlassian_careers_api_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "TEAM",
        "company_name": "Atlassian Corp",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    payload = [
        {
            "id": 25077,
            "title": "Account Executive - Japanese Speaking",
            "locations": ["Remote - Japan - Remote", "Remote - Remote"],
            "category": "Sales",
            "portalJobPost": {
                "portalUrl": "https://globalcareers-atlassian.icims.com/jobs/25077/account-executive---japanese-speaking/job",
                "updatedDate": "2026-06-22 01:21 AM",
            },
        }
    ]

    rows = MODULE._parse_atlassian_careers_payload(
        company,
        json.dumps(payload),
        source_url="https://www.atlassian.com/endpoint/careers/listings",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "atlassian_careers_api"
    assert rows[0]["job_title"] == "Account Executive - Japanese Speaking"
    assert rows[0]["job_location"] == "Remote - Japan - Remote; Remote - Remote"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_pcsx_careers_api_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "MSFT",
        "company_name": "Microsoft",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    payload = {
        "status": 200,
        "data": {
            "positions": [
                {
                    "id": 1970393556847405,
                    "displayJobId": "200031838",
                    "name": "Software Engineer II - Azure Resource Graph",
                    "locations": ["United States, Multiple Locations, Multiple Locations"],
                    "department": "Software Engineering",
                    "postedTs": 1782218408,
                    "positionUrl": "/careers/job/1970393556847405",
                }
            ]
        },
    }

    rows = MODULE._parse_pcsx_search_payload(
        company,
        json.dumps(payload),
        source_url="https://apply.careers.microsoft.com/api/pcsx/search?domain=microsoft.com&query=&location=&start=0",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "pcsx_careers_api"
    assert rows[0]["job_title"] == "Software Engineer II - Azure Resource Graph"
    assert rows[0]["job_location"] == "United States, Multiple Locations, Multiple Locations"
    assert rows[0]["job_department"] == "Software Engineering"
    assert rows[0]["source_url"] == "https://apply.careers.microsoft.com/careers/job/1970393556847405"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_verizon_next_jobs_browser_payload_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "VZ",
        "company_name": "Verizon Communications",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    payload = {
        "jobs": [
            {
                "Id": "r-1094625",
                "Title": "Retail Sales Associate",
                "Teams": ["Sales"],
                "Locations": [
                    {
                        "Identifier": "5141 O ST, Lincoln, Nebraska",
                        "City": "Lincoln",
                        "Region": "Nebraska",
                        "Country": "United States of America",
                    }
                ],
                "Urls": [{"Url": "/jobs/r-1094625/retail-sales-associate/", "IsDefault": True}],
            }
        ],
        "totalJobs": 1195,
    }

    rows = MODULE._parse_verizon_next_jobs_payload(
        company,
        json.dumps(payload),
        source_url="https://mycareer.verizon.com/api/jobs/search/?page=1&pagesize=2",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "verizon_next_jobs_browser_api"
    assert rows[0]["job_title"] == "Retail Sales Associate"
    assert rows[0]["job_location"] == "5141 O ST, Lincoln, Nebraska"
    assert rows[0]["job_department"] == "Sales"
    assert rows[0]["source_url"] == "https://mycareer.verizon.com/jobs/r-1094625/retail-sales-associate/"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_deltek_findly_widget_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "ROP",
        "company_name": "Roper Technologies",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    html = """
    <ol class="joblist-ol">
      <li class="widget_joblist_row">
        <a href="/job/23409817/principal-costpoint-materials-support-analyst-remote/" lang="en-US">
          Principal Costpoint Materials Support Analyst
        </a>
        <div class="widget_joblist_category" lang="en-US">Customer Support</div>
        <div class="widget_joblist_loc" lang="en-US"><i class="locationtype">Remote</i></div>
      </li>
    </ol>
    """

    rows = MODULE._parse_deltek_findly_widget_jobs(
        company,
        html,
        source_url="https://careers.deltek.com/",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "deltek_findly_widget_jobs"
    assert rows[0]["job_title"] == "Principal Costpoint Materials Support Analyst"
    assert rows[0]["job_location"] == "Remote"
    assert rows[0]["job_department"] == "Customer Support"
    assert rows[0]["source_url"] == "https://careers.deltek.com/job/23409817/principal-costpoint-materials-support-analyst-remote/"
    assert rows[0]["subsidiary_binding"]["subsidiary_name"] == "Deltek"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_ibm_careers_search_api_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "IBM",
        "company_name": "IBM",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    payload = {
        "hits": {
            "hits": [
                {
                    "_source": {
                        "url": "https://careers.ibm.com/careers/JobDetail?jobId=108968",
                        "title": "Application Architect-Adobe Experience Platforms & Analytics",
                        "field_keyword_08": "Infrastructure & Technology",
                        "field_keyword_18": "Professional",
                        "field_keyword_19": "Multiple Cities",
                    }
                }
            ]
        }
    }

    rows = MODULE._parse_ibm_careers_search_payload(
        company,
        json.dumps(payload),
        source_url="https://www-api.ibm.com/search/api/v2",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "ibm_search_api"
    assert rows[0]["job_title"] == "Application Architect-Adobe Experience Platforms & Analytics"
    assert rows[0]["job_location"] == "Multiple Cities"
    assert rows[0]["job_department"] == "Infrastructure & Technology"
    assert rows[0]["source_url"] == "https://careers.ibm.com/careers/JobDetail?jobId=108968"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_shopify_singlefetch_jobs_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "SHOP",
        "company_name": "Shopify Inc.",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    values = [None] * 32
    values[0] = {"_1": 2, "_3": 4}
    values[1] = "jobPostingsWithJobs"
    values[2] = [5]
    values[3] = "atsLocations"
    values[4] = []
    values[5] = {"_6": 7}
    values[6] = "jobPosting"
    values[7] = {"_8": 9, "_10": 11, "_12": 13, "_14": 15, "_16": 17, "_18": 19, "_20": 21, "_22": 23}
    values[8] = "title"
    values[9] = "Applied Machine Learning Engineering Managers"
    values[10] = "locationName"
    values[11] = "Americas"
    values[12] = "workplaceType"
    values[13] = "Remote"
    values[14] = "teamName"
    values[15] = "Engineering"
    values[16] = "publishedDate"
    values[17] = "2026-03-26"
    values[18] = "externalLink"
    values[19] = "https://www.shopify.com/careers?ashby_jid=62d779d3-51c8-4b0a-ab2e-1a440276bb37"
    values[20] = "isListed"
    values[21] = True
    values[22] = "jobId"
    values[23] = "1de454a9-f795-4334-93ff-f4a118dc6629"
    encoded = json.dumps(values, separators=(",", ":"))
    html = f"<script>window.__reactRouterContext.streamController.enqueue({json.dumps(encoded)});</script>"

    rows = MODULE._parse_shopify_singlefetch_jobs(
        company,
        html,
        source_url="https://www.shopify.com/careers",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "shopify_singlefetch_ashby_jobs"
    assert rows[0]["job_title"] == "Applied Machine Learning Engineering Managers"
    assert rows[0]["job_location"] == "Americas (Remote)"
    assert rows[0]["job_department"] == "Engineering"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_cognizant_card_job_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "CTSH",
        "company_name": "Cognizant Technology Solutions",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    html = """
    <div class="card card-job" data-id="00068063111">
      <div class="card-body">
        <h2 class="card-title">
          <a class="stretched-link js-view-job" href="/global-en/jobs/00068063111/hiring-for-ioa-returnship-program/">
            Hiring for IOA Returnship Program
          </a>
        </h2>
        <ul class="list-inline job-meta">
          <li class="list-inline-item">Chennai, Tamil Nadu, India</li>
          <li class="list-inline-item">Technology &amp; Engineering</li>
        </ul>
      </div>
    </div>
    """

    rows = MODULE._parse_cognizant_card_jobs(
        company,
        html,
        source_url="https://careers.cognizant.com/global-en/jobs/?from=0&s=1",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "cognizant_card_job_html"
    assert rows[0]["job_title"] == "Hiring for IOA Returnship Program"
    assert rows[0]["job_location"] == "Chennai, Tamil Nadu, India"
    assert rows[0]["job_department"] == "Technology & Engineering"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_adp_card_job_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "ADP",
        "company_name": "Automatic Data Processing",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    html = """
    <div class="card card-job" data-id="277300">
      <div class="card-body">
        <div class="job-meta"><p><strong>277300</strong></p></div>
        <div class="job-meta">
          <p><time datetime="2026-06-22">06/22/2026</time></p>
          <p>Sales</p>
        </div>
        <h2 class="card-title">
          <a class="stretched-link js-view-job" href="/en/jobs/277300/corporate-sales-manager/">
            Corporate Sales Manager
          </a>
        </h2>
        <div class="job-meta">
          <p><span class="job-meta-location">United States-Home Office, New York, United States</span></p>
        </div>
      </div>
    </div>
    """

    rows = MODULE._parse_card_job_html_jobs(
        company,
        html,
        source_url="https://jobs.adp.com/en/jobs/",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
        provider="adp_card_job_html",
        token="jobs.adp.com",
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "adp_card_job_html"
    assert rows[0]["job_title"] == "Corporate Sales Manager"
    assert rows[0]["job_location"] == "United States-Home Office, New York, United States"
    assert rows[0]["job_department"] == "Sales"
    assert rows[0]["posted_at"] == "2026-06-22"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1


def test_paradox_preload_jobs_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "DRI",
        "company_name": "Darden Restaurants",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    payload = {
        "jobSearch": {
            "jobs": [
                {
                    "title": "AP Research Specialist",
                    "applyURL": "https://darden.paradox.ai/co/DardenRestaurantSupportCenter/Job?job_id=abc",
                    "locations": [
                        {
                            "locationParsedText": "1000 Darden Center Dr, Orlando, FL 32837, United States",
                            "cityStateAbbr": "Orlando, FL",
                        }
                    ],
                    "customFields": [{"cfKey": "cf_functional_area", "value": "Finance & Accounting"}],
                }
            ]
        }
    }
    html = f"<script>window.__PRELOAD_STATE__ = {json.dumps(payload)};</script>"

    rows = MODULE._parse_paradox_preload_jobs(
        company,
        html,
        source_url="https://dardenrscjobs.recruiting.com/",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "paradox_preload_jobs"
    assert rows[0]["job_title"] == "AP Research Specialist"
    assert rows[0]["job_location"] == "1000 Darden Center Dr, Orlando, FL 32837, United States"
    assert rows[0]["job_department"] == "Finance & Accounting"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1


def test_icims_iframe_job_cards_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "PWR",
        "company_name": "Quanta Services",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    html = """
    <ul class="container-fluid iCIMS_JobsTable">
      <li class="iCIMS_JobCardItem">
        <div class="row">
          <div class="col-xs-12 title">
            <a href="https://careers-quanta.icims.com/jobs/16500/craft-recruiter/job?in_iframe=1" class="iCIMS_Anchor" title="16500 - Craft Recruiter">
              <span class="sr-only field-label">Title</span><h3>Craft Recruiter</h3>
            </a>
          </div>
          <dl class="iCIMS_JobHeaderGroup">
            <div class="iCIMS_JobHeaderTag">
              <dt class="iCIMS_JobHeaderField"><span class="sr-only field-label">Location</span></dt>
              <dd class="iCIMS_JobHeaderData"><span>US-LA-Prairieville</span></dd>
            </div>
            <div class="iCIMS_JobHeaderTag">
              <dt class="iCIMS_JobHeaderField">Category</dt>
              <dd class="iCIMS_JobHeaderData"><span>Human Resources/Recruiting</span></dd>
            </div>
          </dl>
        </div>
      </li>
    </ul>
    """

    rows = MODULE._parse_icims_iframe_job_cards(
        company,
        html,
        source_url="https://careers-quanta.icims.com/jobs/search?ss=1&in_iframe=1",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "icims_iframe_job_cards"
    assert rows[0]["job_title"] == "Craft Recruiter"
    assert rows[0]["job_location"] == "US-LA-Prairieville"
    assert rows[0]["job_department"] == "Human Resources/Recruiting"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1


def test_sea_careers_api_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "SE",
        "company_name": "Sea Limited",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    page_html = r'''
    <script>self.__next_f.push([1,"{\"meta\":{\"flatLocations\":[{\"cityId\":2,\"cityName\":\"São Paulo\"}],\"deptList\":[{\"deptId\":9,\"deptName\":\"Operations\"}]}}"])</script>
    '''
    payload = {
        "code": 0,
        "message": "success",
        "data": {
            "job_list": [
                {
                    "job_id": "J02153200",
                    "job_name": "Analista Sênior - FP&A (Fulfillment)",
                    "department_id": 9,
                    "city_id": 2,
                }
            ],
            "total_count": 1,
        },
    }

    rows = MODULE._parse_sea_careers_api_jobs(
        company,
        page_html,
        json.dumps(payload),
        source_url="https://career.sea.com/api/user/job/list?externalEntityId=3&limit=10&offset=0&postType=1",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "sea_careers_api"
    assert rows[0]["job_title"] == "Analista Sênior - FP&A (Fulfillment)"
    assert rows[0]["job_location"] == "São Paulo"
    assert rows[0]["job_department"] == "Operations"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1


def test_direct_ats_candidates_use_verified_token_overrides() -> None:
    bill_urls = MODULE._direct_ats_candidates("BILL", {"company_name": "BILL Holdings, Inc."})
    crwd_urls = MODULE._direct_ats_candidates("CRWD", {"company_name": "CrowdStrike"})
    estc_urls = MODULE._direct_ats_candidates("ESTC", {"company_name": "Elastic N.V."})
    crm_urls = MODULE._direct_ats_candidates("CRM", {"company_name": "Salesforce"})

    assert "https://boards.greenhouse.io/billcom" in bill_urls
    assert crwd_urls[0] == "https://crowdstrike.wd5.myworkdayjobs.com/crowdstrikecareers"
    assert "https://boards.greenhouse.io/elastic" in estc_urls
    assert crm_urls[0] == "https://salesforce.wd12.myworkdayjobs.com/External_Career_Site"


def test_ashby_jobs_api_rows_enter_hiring_exact_slot(tmp_path: Path, monkeypatch) -> None:
    company = {
        "ticker": "TEST",
        "company_name": "Test Issuer",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    payload = {
        "jobs": [
            {
                "title": "AI Infrastructure Engineer",
                "department": "Engineering",
                "location": "New York, NY",
                "publishedAt": "2026-06-20T00:00:00Z",
                "jobUrl": "https://jobs.ashbyhq.com/testissuer/abc",
            }
        ]
    }

    def fake_fetch_text(url, *, timeout_s, accept="application/json"):
        return "ok", json.dumps(payload), ""

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch_text)
    result = MODULE._fetch_ashby_jobs(
        company,
        "https://api.ashbyhq.com/posting-api/job-board/testissuer",
        token="testissuer",
        generated_at="2026-06-20T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=1,
        max_jobs=1,
    )

    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["underlying_source_id"] == "ashby"
    assert row["job_title"] == "AI Infrastructure Engineer"

    exact = build_exact_slot_rows(result["rows"], generated_at="2026-06-20T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_oracle_hcm_ce_rows_enter_hiring_exact_slot(tmp_path: Path, monkeypatch) -> None:
    company = {
        "ticker": "ORCL",
        "company_name": "Oracle",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    payload = {
        "items": [
            {
                "requisitionList": [
                    {
                        "Id": "326565",
                        "Title": "Senior Director- Data Center Readiness",
                        "PrimaryLocation": "Nashville, TN, United States",
                        "PostedDate": "2026-06-23",
                        "JobFunction": "Data Center Operations",
                    }
                ]
            }
        ]
    }

    def fake_fetch_text(url, *, timeout_s, accept="application/json,*/*"):
        assert "recruitingCEJobRequisitions" in url
        assert "siteNumber=CX_1" in url
        return "ok", json.dumps(payload), ""

    monkeypatch.setattr(MODULE, "_fetch_text", fake_fetch_text)
    result = MODULE._fetch_oracle_hcm_jobs(
        company,
        "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/jobs",
        site_number="CX_1",
        generated_at="2026-06-23T00:00:00Z",
        raw_dir=tmp_path,
        timeout_s=1,
        max_jobs=1,
    )

    assert len(result["rows"]) == 1
    row = result["rows"][0]
    assert row["underlying_source_id"] == "oracle_hcm_ce"
    assert row["job_title"] == "Senior Director- Data Center Readiness"
    assert row["job_location"] == "Nashville, TN, United States"
    assert row["provider_token"] == "CX_1"

    exact = build_exact_slot_rows(result["rows"], generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
    assert exact["exact_rows"][0]["requirement_id"] == "hiring_capacity_proxy"


def test_talentbrew_search_list_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "T",
        "company_name": "AT&T",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    html = """
    <section id="search-results-list" class="search-results-list">
      <ul>
        <li>
          <h2 class="headline__small">
            <a href="/job/dallas/sr-director-of-skills-strategy-and-development/117/96801681056" data-job-id="96801681056">
              Sr Director of Skills Strategy &amp; Development
            </a>
          </h2>
          <span class="job-location">Dallas, TX</span>
        </li>
      </ul>
    </section>
    """

    rows = MODULE._parse_talentbrew_search_jobs(
        company,
        html,
        source_url="https://www.att.jobs/search-jobs?from=0&s=1",
        generated_at="2026-06-20T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "talentbrew_html"
    assert rows[0]["job_title"] == "Sr Director of Skills Strategy & Development"
    assert rows[0]["job_location"] == "Dallas, TX"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-20T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1


def test_generic_job_search_table_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "PCOR",
        "company_name": "Procore Technologies",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    html = """
    <table>
      <tr role="link" data-job-url="https://careers.procore.com/jobs/staff-integration-application-developer">
        <td class="job-search-results-title">
          <a href="https://careers.procore.com/jobs/staff-integration-application-developer">
            Staff Integration &amp; Application Developer
          </a>
        </td>
        <td class="job-search-results-location">
          <ul><li aria-label="Location: Austin, Texas">Austin, Texas</li></ul>
        </td>
      </tr>
    </table>
    """

    rows = MODULE._parse_generic_job_search_table_jobs(
        company,
        html,
        source_url="https://careers.procore.com/jobs/search",
        generated_at="2026-06-23T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "generic_job_search_table_html"
    assert rows[0]["job_title"] == "Staff Integration & Application Developer"
    assert rows[0]["job_location"] == "Austin, Texas"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-23T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1


def test_google_careers_html_rows_enter_hiring_exact_slot() -> None:
    company = {
        "ticker": "GOOGL",
        "company_name": "Alphabet Inc.",
        "source_role_matrix": [{"requirement_id": "hiring_capacity_proxy"}],
    }
    html = """
    <li class="lLd3Je">
      <h3 class="QJPWVe">Staff Software Engineer, Vector Search, Vertex AI</h3>
      <span class="RP7SMd"><span>Google</span></span>
      <span class="pwO9Dc vo5qdf"><i>place</i><span class="r0wTof ">Warsaw, Poland</span></span>
    </li>
    """

    rows = MODULE._parse_google_careers_html_jobs(
        company,
        html,
        source_url="https://www.google.com/about/careers/applications/jobs/results/?q=&page=1",
        generated_at="2026-06-20T00:00:00Z",
        max_jobs=1,
    )

    assert len(rows) == 1
    assert rows[0]["underlying_source_id"] == "google_careers_html"
    assert rows[0]["job_title"] == "Staff Software Engineer, Vector Search, Vertex AI"
    assert rows[0]["job_location"] == "Warsaw, Poland"

    exact = build_exact_slot_rows(rows, generated_at="2026-06-20T00:00:00Z")
    assert exact["exact_slot_row_count"] == 1
