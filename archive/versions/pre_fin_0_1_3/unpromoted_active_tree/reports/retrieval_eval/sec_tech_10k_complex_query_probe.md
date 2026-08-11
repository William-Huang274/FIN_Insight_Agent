# SEC Tech 10-K Complex Query Probe

Date: 2026-05-15

Retriever: Qwen3-Embedding-0.6B seq8192 batch16 dense, plus equal-weight BM25+dense RRF for filtered mode.

Scope: 12 manually designed common and deep finance questions over the 10-company, 2023-2025 SEC 10-K corpus. This is manual retrieval inspection, not a scored benchmark.

Elapsed seconds: 19.209

## Manual Inspection Summary

The seed metrics have diagnostic value, but they are not sufficient to claim that the current retriever is ready for deep finance questions. The complex-query probe shows a clear split:

- Common, single-company financial questions usually retrieve useful top5 evidence when ticker/year filters are applied.
- Multi-facet questions often retrieve one strong facet and miss another. Typical missing facets are capex, leases, RPO, or the bridge between operating narrative and financial statement notes.
- Equal-weight RRF is mixed. It helps some exact-term risk queries, such as NVIDIA supply-chain/customer concentration, but can move generic or table-of-contents-like chunks above better dense hits.
- Unfiltered dense retrieval is not reliable enough for company/year-sensitive questions. Across 12 queries, only 41 of 60 unfiltered top5 hits matched the target ticker/year. The worst cases drifted to adjacent fiscal years or similar companies such as NVIDIA/AMD.
- Current `precision@k` and `nDCG@k` are useful as a first ranking diagnostic over seed qrels, but the qrels are too narrow. They do not measure whether all required financial facets are present in top5.

| Query | Dense Filtered Judgment | Hybrid Filtered Judgment | Main Finding |
| --- | --- | --- | --- |
| MSFT cloud / AI margin | Good | Good | Top5 covers cloud revenue, segment table, and capital/infrastructure discussion. |
| AAPL iPhone / Services margin | Good | Good | Top5 covers Services, iPhone, and Services gross margin. |
| NVDA data center / customer concentration | Good | Partial | Dense gets data center revenue and concentration; hybrid moves broad context above the best dense hit. |
| AMZN AWS margin / capex | Partial | Partial | Segment note appears, but capex/infrastructure pressure is noisy and not cleanly ranked. |
| META ads / AI capex | Partial | Partial | Ads and AI/product investment appear; capex is not cleanly surfaced in top5. |
| GOOGL ads / cloud / capex | Partial | Partial | Cloud and infrastructure appear, but advertising growth and capex bridge are weak. |
| ADBE ARR / RPO durability | Partial | Partial | ARR is retrieved; RPO is not cleanly retrieved in top5. |
| SNOW consumption / RPO / customers | Good | Good | Top5 includes consumption visibility risk, customer acquisition, revenue table, and RPO seasonality. |
| PANW platformization / billings / RPO | Weak | Weak | Retrieval drifts to financial-statement index/cash-flow/business chunks and misses the platformization-to-RPO thesis. |
| AMD segment mix / margin / inventory | Good | Good | Segment and gross margin are strong; supply/inventory appears better in hybrid. |
| NVDA supply-chain / customer risk | Partial | Good | Hybrid improves this exact-term risk query by surfacing supplier dependency and concentration together. |
| AMZN liquidity / leases / commitments | Partial | Partial | Commitments and cash flow are retrieved, but leases/free-cash-flow framing is mixed with tax/noisy chunks. |

Decision: current metrics are valuable for measuring whether known evidence IDs are ranked early, but the evaluation set should be expanded with complex multi-facet qrels before using the metrics as a project-quality claim. The next retrieval design should add query decomposition or facet-aware retrieval before reranking.

## common_msft_2025_cloud_ai_margin

- Category: `common_financial`
- Filter: `MSFT 2025`
- Query: For Microsoft fiscal 2025, what explains cloud revenue growth and what do margins or costs suggest about AI infrastructure investment?
- Expected signal: cloud revenue growth, Azure/cloud services, AI infrastructure or capital/cost pressure
- Unfiltered dense top5 metadata matches target: 5/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `MSFT_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Highlights from fiscal year 2025 compared with fiscal year 2024 included | management_discussion | False | Highlights from fiscal year 2025 compared with fiscal year 2024 included: • Microsoft Cloud revenue increased 23% to $168.9 billion. • Microsoft 365 Commercial products and cloud services revenue increased 14% driven by Microsoft 365 Commercial cloud revenue growth of 15%. • Micr... |
| 2 | `MSFT_2025_10K_ITEM8_BLOCK_0022_PART_02_OF_04` | Item 8. Financial Statements and Supplementary Data | NOTE 18 | financial_statement_or_note | True | [TABLE_START id=72 rows=22] (In millions) Year Ended June 30, \| 2025 \| 2024 \| 2023 Productivity and Business Processes Revenue \| $ \| 120,810 \| $ \| 106,820 \| $ \| 94,151 Cost of revenue \| 22,422 \| 19,611 \| 17,202 Operating expenses \| 28,615 \| 27,548 \| 26,875 Operating Income \| $ \| ... |
| 3 | `MSFT_2025_10K_ITEM7_BLOCK_0005_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Productivity and Business Processes and Intelligent Cloud | management_discussion | True | Productivity and Business Processes and Intelligent Cloud Metrics related to our Productivity and Business Processes and Intelligent Cloud segments assess the health of our core businesses within these segments. The metrics primarily reflect growth across our cloud services. [TAB... |
| 4 | `MSFT_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Productivity and Business Processes and Intelligent Cloud | management_discussion | False | Reportable Segments Fiscal Year 2025 Compared with Fiscal Year 2024 Productivity and Business Processes Revenue increased $14.0 billion or 13%. • Microsoft 365 Commercial products and cloud services revenue increased $10.8 billion or 14%. Microsoft 365 Commercial cloud revenue gr... |
| 5 | `MSFT_2025_10K_ITEM7_BLOCK_0010_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Other Planned Uses of Capital | management_discussion | False | Other Planned Uses of Capital We will continue to invest in sales, marketing, product support infrastructure, and existing and advanced areas of technology, as well as acquisitions that align with our business strategy. Additions to property and equipment will continue, including... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `MSFT_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Highlights from fiscal year 2025 compared with fiscal year 2024 included | management_discussion | False | Highlights from fiscal year 2025 compared with fiscal year 2024 included: • Microsoft Cloud revenue increased 23% to $168.9 billion. • Microsoft 365 Commercial products and cloud services revenue increased 14% driven by Microsoft 365 Commercial cloud revenue growth of 15%. • Micr... |
| 2 | `MSFT_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Productivity and Business Processes and Intelligent Cloud | management_discussion | False | Reportable Segments Fiscal Year 2025 Compared with Fiscal Year 2024 Productivity and Business Processes Revenue increased $14.0 billion or 13%. • Microsoft 365 Commercial products and cloud services revenue increased $10.8 billion or 14%. Microsoft 365 Commercial cloud revenue gr... |
| 3 | `MSFT_2025_10K_ITEM7_BLOCK_0005_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Productivity and Business Processes and Intelligent Cloud | management_discussion | True | Productivity and Business Processes and Intelligent Cloud Metrics related to our Productivity and Business Processes and Intelligent Cloud segments assess the health of our core businesses within these segments. The metrics primarily reflect growth across our cloud services. [TAB... |
| 4 | `MSFT_2025_10K_ITEM8_BLOCK_0022_PART_02_OF_04` | Item 8. Financial Statements and Supplementary Data | NOTE 18 | financial_statement_or_note | True | [TABLE_START id=72 rows=22] (In millions) Year Ended June 30, \| 2025 \| 2024 \| 2023 Productivity and Business Processes Revenue \| $ \| 120,810 \| $ \| 106,820 \| $ \| 94,151 Cost of revenue \| 22,422 \| 19,611 \| 17,202 Operating expenses \| 28,615 \| 27,548 \| 26,875 Operating Income \| $ \| ... |
| 5 | `MSFT_2025_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | GENERAL | business_description | False | ITEM 1. B USINESS GENERAL Microsoft is a technology company committed to making digital technology and artificial intelligence (“AI”) available broadly and doing so responsibly. Our mission is to empower every person and every organization on the planet to achieve more. We develo... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `MSFT_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Highlights from fiscal year 2025 compared with fiscal year 2024 included | management_discussion | False | Highlights from fiscal year 2025 compared with fiscal year 2024 included: • Microsoft Cloud revenue increased 23% to $168.9 billion. • Microsoft 365 Commercial products and cloud services revenue increased 14% driven by Microsoft 365 Commercial cloud revenue growth of 15%. • Micr... |
| 2 | `MSFT_2025_10K_ITEM8_BLOCK_0022_PART_02_OF_04` | Item 8. Financial Statements and Supplementary Data | NOTE 18 | financial_statement_or_note | True | [TABLE_START id=72 rows=22] (In millions) Year Ended June 30, \| 2025 \| 2024 \| 2023 Productivity and Business Processes Revenue \| $ \| 120,810 \| $ \| 106,820 \| $ \| 94,151 Cost of revenue \| 22,422 \| 19,611 \| 17,202 Operating expenses \| 28,615 \| 27,548 \| 26,875 Operating Income \| $ \| ... |
| 3 | `MSFT_2025_10K_ITEM7_BLOCK_0005_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Productivity and Business Processes and Intelligent Cloud | management_discussion | True | Productivity and Business Processes and Intelligent Cloud Metrics related to our Productivity and Business Processes and Intelligent Cloud segments assess the health of our core businesses within these segments. The metrics primarily reflect growth across our cloud services. [TAB... |
| 4 | `MSFT_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Productivity and Business Processes and Intelligent Cloud | management_discussion | False | Reportable Segments Fiscal Year 2025 Compared with Fiscal Year 2024 Productivity and Business Processes Revenue increased $14.0 billion or 13%. • Microsoft 365 Commercial products and cloud services revenue increased $10.8 billion or 14%. Microsoft 365 Commercial cloud revenue gr... |
| 5 | `MSFT_2025_10K_ITEM7_BLOCK_0010_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Other Planned Uses of Capital | management_discussion | False | Other Planned Uses of Capital We will continue to invest in sales, marketing, product support infrastructure, and existing and advanced areas of technology, as well as acquisitions that align with our business strategy. Additions to property and equipment will continue, including... |

## common_aapl_2025_iphone_services_margin

- Category: `common_financial`
- Filter: `AAPL 2025`
- Query: For Apple fiscal 2025, compare iPhone and Services net sales performance and explain the gross margin drivers.
- Expected signal: iPhone sales, Services sales, product/services gross margin discussion
- Unfiltered dense top5 metadata matches target: 5/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AAPL_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Services | management_discussion | True | Services Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services. Apple Inc. \| 2025 Form 10-K \| 23 Gross Margin Products and Services gross margin and gross margin percentage for 2025, 2024 and... |
| 2 | `AAPL_2025_10K_ITEM7_BLOCK_0002_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Fourth Quarter 2025 | management_discussion | False | (1) Services net sales include amortization of the deferred value of services bundled in the sales price of certain products. iPhone iPhone net sales increased during 2025 compared to 2024 due to higher net sales of Pro models. Mac Mac net sales increased during 2025 compared to ... |
| 3 | `AAPL_2025_10K_ITEM7_BLOCK_0002_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Fourth Quarter 2025 | management_discussion | True | Fourth Quarter 2025: • iPhone 17, iPhone Air, iPhone 17 Pro and iPhone 17 Pro Max • Apple Watch Series 11, Apple Watch SE 3 and Apple Watch Ultra 3 • AirPods Pro 3 Fiscal Period The Company’s fiscal year is the 52- or 53-week period that ends on the last Saturday of September. An... |
| 4 | `AAPL_2025_10K_ITEM7_BLOCK_0005_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Services Gross Margin | management_discussion | True | Services Gross Margin Services gross margin increased during 2025 compared to 2024 primarily due to higher Services net sales and a different mix of services. Services gross margin percentage increased during 2025 compared to 2024 primarily due to a different mix of services, par... |
| 5 | `AAPL_2025_10K_ITEM7_BLOCK_0001_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations The following discussion should be read in conjunction with the consolidated financial statements and accompanying notes included in Part II, Item 8 of this Form 10-K. This Item generall... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AAPL_2025_10K_ITEM7_BLOCK_0002_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Fourth Quarter 2025 | management_discussion | True | Fourth Quarter 2025: • iPhone 17, iPhone Air, iPhone 17 Pro and iPhone 17 Pro Max • Apple Watch Series 11, Apple Watch SE 3 and Apple Watch Ultra 3 • AirPods Pro 3 Fiscal Period The Company’s fiscal year is the 52- or 53-week period that ends on the last Saturday of September. An... |
| 2 | `AAPL_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Services | management_discussion | True | Services Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services. Apple Inc. \| 2025 Form 10-K \| 23 Gross Margin Products and Services gross margin and gross margin percentage for 2025, 2024 and... |
| 3 | `AAPL_2025_10K_ITEM7_BLOCK_0005_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Services Gross Margin | management_discussion | True | Services Gross Margin Services gross margin increased during 2025 compared to 2024 primarily due to higher Services net sales and a different mix of services. Services gross margin percentage increased during 2025 compared to 2024 primarily due to a different mix of services, par... |
| 4 | `AAPL_2025_10K_ITEM7_BLOCK_0002_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Fourth Quarter 2025 | management_discussion | False | (1) Services net sales include amortization of the deferred value of services bundled in the sales price of certain products. iPhone iPhone net sales increased during 2025 compared to 2024 due to higher net sales of Pro models. Mac Mac net sales increased during 2025 compared to ... |
| 5 | `AAPL_2025_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | Item 1. Business | business_description | False | Item 1. Business Company Background The Company designs, manufactures and markets smartphones, personal computers, tablets, wearables and accessories, and sells a variety of related services. The Company’s fiscal year is the 52- or 53-week period that ends on the last Saturday of... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AAPL_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Services | management_discussion | True | Services Services net sales increased during 2025 compared to 2024 primarily due to higher net sales from advertising, the App Store and cloud services. Apple Inc. \| 2025 Form 10-K \| 23 Gross Margin Products and Services gross margin and gross margin percentage for 2025, 2024 and... |
| 2 | `AAPL_2025_10K_ITEM7_BLOCK_0002_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Fourth Quarter 2025 | management_discussion | False | (1) Services net sales include amortization of the deferred value of services bundled in the sales price of certain products. iPhone iPhone net sales increased during 2025 compared to 2024 due to higher net sales of Pro models. Mac Mac net sales increased during 2025 compared to ... |
| 3 | `AAPL_2025_10K_ITEM7_BLOCK_0002_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Fourth Quarter 2025 | management_discussion | True | Fourth Quarter 2025: • iPhone 17, iPhone Air, iPhone 17 Pro and iPhone 17 Pro Max • Apple Watch Series 11, Apple Watch SE 3 and Apple Watch Ultra 3 • AirPods Pro 3 Fiscal Period The Company’s fiscal year is the 52- or 53-week period that ends on the last Saturday of September. An... |
| 4 | `AAPL_2025_10K_ITEM7_BLOCK_0005_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Services Gross Margin | management_discussion | True | Services Gross Margin Services gross margin increased during 2025 compared to 2024 primarily due to higher Services net sales and a different mix of services. Services gross margin percentage increased during 2025 compared to 2024 primarily due to a different mix of services, par... |
| 5 | `AAPL_2025_10K_ITEM7_BLOCK_0001_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Item 7. Management’s Discussion and Analysis of Financial Condition and Results of Operations The following discussion should be read in conjunction with the consolidated financial statements and accompanying notes included in Part II, Item 8 of this Form 10-K. This Item generall... |

## common_nvda_2025_datacenter_customer_concentration

- Category: `common_financial`
- Filter: `NVDA 2025`
- Query: For NVIDIA fiscal 2025, how does data center revenue growth relate to customer concentration and demand from large cloud or service providers?
- Expected signal: data center revenue, customer concentration, large cloud/service providers
- Unfiltered dense top5 metadata matches target: 1/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `NVDA_2025_10K_ITEM7_BLOCK_0005_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Compute & Networking revenue | management_discussion | False | Compute & Networking revenue – The year over year increase was due to strong demand for our accelerated computing and AI solutions. Revenue from Data Center computing grew 162% driven primarily by demand for our Hopper computing platform used for large language models, recommenda... |
| 2 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_03_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | True | Macroeconomic Factors Macroeconomic factors, including inflation, interest rate changes, capital market volatility, global supply chain constraints, tariffs, and global economic and geopolitical developments, may have direct and indirect impacts on our results of operations, part... |
| 3 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_01_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations The following discussion and analysis of our financial condition and results of operations should be read in conjunction with “Item 1A. Risk Factors,” our Consolidated Financial Statemen... |
| 4 | `NVDA_2025_10K_ITEM1_BLOCK_0001_PART_02_OF_03` | Item 1. Business | Item 1. Business | business_description | False | 4 Table of Contents Researchers and developers use our computing solutions to accelerate a wide range of important applications, from simulating molecular dynamics to climate forecasting. With support for more than 4,400 applications, NVIDIA computing enables some of the most pro... |
| 5 | `NVDA_2025_10K_ITEM7_BLOCK_0007_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Concentration of Revenue | management_discussion | False | Concentration of Revenue We refer to customers who purchase products directly from NVIDIA as direct customers, such as AIBs, distributors, ODMs, OEMs, and system integrators. We have certain customers that may purchase products directly from NVIDIA and may use either internal res... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_03_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | True | Macroeconomic Factors Macroeconomic factors, including inflation, interest rate changes, capital market volatility, global supply chain constraints, tariffs, and global economic and geopolitical developments, may have direct and indirect impacts on our results of operations, part... |
| 2 | `NVDA_2025_10K_ITEM1_BLOCK_0001_PART_02_OF_03` | Item 1. Business | Item 1. Business | business_description | False | 4 Table of Contents Researchers and developers use our computing solutions to accelerate a wide range of important applications, from simulating molecular dynamics to climate forecasting. With support for more than 4,400 applications, NVIDIA computing enables some of the most pro... |
| 3 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_01_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations The following discussion and analysis of our financial condition and results of operations should be read in conjunction with “Item 1A. Risk Factors,” our Consolidated Financial Statemen... |
| 4 | `NVDA_2025_10K_ITEM7_BLOCK_0007_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Concentration of Revenue | management_discussion | False | Concentration of Revenue We refer to customers who purchase products directly from NVIDIA as direct customers, such as AIBs, distributors, ODMs, OEMs, and system integrators. We have certain customers that may purchase products directly from NVIDIA and may use either internal res... |
| 5 | `NVDA_2025_10K_ITEM7_BLOCK_0005_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Compute & Networking revenue | management_discussion | False | Compute & Networking revenue – The year over year increase was due to strong demand for our accelerated computing and AI solutions. Revenue from Data Center computing grew 162% driven primarily by demand for our Hopper computing platform used for large language models, recommenda... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `NVDA_2024_10K_ITEM7_BLOCK_0002_PART_03_OF_04` | Item 7. Management's Discussion and Analysis | Recent Developments, Future Objectives and Challenges | management_discussion | False | Revenue for fiscal year 2024 was $60.9 billion, up 126% from a year ago. Data Center revenue for fiscal year 2024 was up 217%. Strong demand was driven by enterprise software and consumer internet applications, and multiple industry verticals including automotive, financial servi... |
| 2 | `AMD_2025_10K_ITEM7_BLOCK_0004_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Results of Operations | management_discussion | True | Results of Operations Additional information on our reportable segments is contained in Note 4 – Segment Reporting of the Notes to Financial Statements (Part II, Item 8 of this Form 10-K). Our operating results tend to vary seasonally. Historically, our net revenue has been gener... |
| 3 | `AMD_2025_10K_ITEM7_BLOCK_0001_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS The following discussion should be read in conjunction with the Consolidated Financial Statements as of December 27, 2025 and December 28, 2024 and for each of the three years in the per... |
| 4 | `NVDA_2025_10K_ITEM7_BLOCK_0005_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Compute & Networking revenue | management_discussion | False | Compute & Networking revenue – The year over year increase was due to strong demand for our accelerated computing and AI solutions. Revenue from Data Center computing grew 162% driven primarily by demand for our Hopper computing platform used for large language models, recommenda... |
| 5 | `NVDA_2023_10K_ITEM7_BLOCK_0007_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | True | 41 Table of Contents Revenue Revenue by Reportable Segments [TABLE_START id=12 rows=6] Year Ended January 29, 2023 \| January 30, 2022 \| $ Change \| % Change ($ in millions) Compute & Networking \| $ \| 15,068 \| $ \| 11,046 \| $ \| 4,022 \| 36 \| % Graphics \| 11,906 \| 15,868 \| (3,962) \| (... |

## common_amzn_2025_aws_margin_capex

- Category: `common_financial`
- Filter: `AMZN 2025`
- Query: For Amazon fiscal 2025, what does the filing say about AWS revenue, operating income or margin, and infrastructure capital spending pressure?
- Expected signal: AWS revenue and operating income, capital expenditures or infrastructure investment
- Unfiltered dense top5 metadata matches target: 4/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMZN_2025_10K_ITEM7_BLOCK_0006_CHUNK_0001` | Item 7. Management's Discussion and Analysis | General and Administrative | management_discussion | True | General and Administrative General and administrative costs in 2025 did not significantly change compared to the prior year. Other Operating Expense (Income), Net Other operating expense (income), net was $763 million and $4.6 billion during 2024 and 2025. The increase in 2025 wa... |
| 2 | `AMZN_2025_10K_ITEM8_BLOCK_0011_PART_02_OF_02` | Item 8. Financial Statements and Supplementary Data | Note 10 — | financial_statement_or_note | True | (3) Includes commissions and any related fulfillment and shipping fees, and other third-party seller services. (4) Includes sales of advertising services to sellers, vendors, publishers, authors, and others, through programs such as sponsored ads, display, and video advertising. ... |
| 3 | `AMZN_2025_10K_ITEM8_BLOCK_0011_PART_01_OF_02` | Item 8. Financial Statements and Supplementary Data | Note 10 — | financial_statement_or_note | True | Note 10 — SEGMENT INFORMATION We have organized our operations into three segments: North America, International, and AWS. We allocate to segment results the operating expenses “Fulfillment,” “Technology and infrastructure,” “Sales and marketing,” and “General and administrative”... |
| 4 | `AMZN_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_10` | Item 8. Financial Statements and Supplementary Data | Note 1 — | financial_statement_or_note | True | Note 1 — DESCRIPTION OF BUSINESS, ACCOUNTING POLICIES, AND SUPPLEMENTAL DISCLOSURES Description of Business We seek to be Earth’s most customer-centric company. In each of our segments, we serve our primary customer sets, consisting of consumers, sellers, developers, enterprises,... |
| 5 | `AMZN_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Overview | management_discussion | False | Shipping costs were $95.8 billion and $102.7 billion in 2024 and 2025. Shipping costs to receive products from our suppliers are included in our inventory and recognized as cost of sales upon sale of products to our customers. We expect our cost of shipping to continue to increas... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMZN_2025_10K_ITEM8_BLOCK_0011_PART_01_OF_02` | Item 8. Financial Statements and Supplementary Data | Note 10 — | financial_statement_or_note | True | Note 10 — SEGMENT INFORMATION We have organized our operations into three segments: North America, International, and AWS. We allocate to segment results the operating expenses “Fulfillment,” “Technology and infrastructure,” “Sales and marketing,” and “General and administrative”... |
| 2 | `AMZN_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Overview | management_discussion | False | Shipping costs were $95.8 billion and $102.7 billion in 2024 and 2025. Shipping costs to receive products from our suppliers are included in our inventory and recognized as cost of sales upon sale of products to our customers. We expect our cost of shipping to continue to increas... |
| 3 | `AMZN_2025_10K_ITEM7_BLOCK_0006_CHUNK_0001` | Item 7. Management's Discussion and Analysis | General and Administrative | management_discussion | True | General and Administrative General and administrative costs in 2025 did not significantly change compared to the prior year. Other Operating Expense (Income), Net Other operating expense (income), net was $763 million and $4.6 billion during 2024 and 2025. The increase in 2025 wa... |
| 4 | `AMZN_2025_10K_ITEM8_BLOCK_0011_PART_02_OF_02` | Item 8. Financial Statements and Supplementary Data | Note 10 — | financial_statement_or_note | True | (3) Includes commissions and any related fulfillment and shipping fees, and other third-party seller services. (4) Includes sales of advertising services to sellers, vendors, publishers, authors, and others, through programs such as sponsored ads, display, and video advertising. ... |
| 5 | `AMZN_2025_10K_ITEM7_BLOCK_0005_PART_01_OF_03` | Item 7. Management's Discussion and Analysis | Overview | management_discussion | True | Overview Macroeconomic factors, including changes in inflation and interest rates, resource and supply volatility, global economic and geopolitical developments, including unpredictable shifts in global tariff and trade policies, and the development and adoption of technologies a... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMZN_2025_10K_ITEM7_BLOCK_0006_CHUNK_0001` | Item 7. Management's Discussion and Analysis | General and Administrative | management_discussion | True | General and Administrative General and administrative costs in 2025 did not significantly change compared to the prior year. Other Operating Expense (Income), Net Other operating expense (income), net was $763 million and $4.6 billion during 2024 and 2025. The increase in 2025 wa... |
| 2 | `AMZN_2025_10K_ITEM8_BLOCK_0011_PART_02_OF_02` | Item 8. Financial Statements and Supplementary Data | Note 10 — | financial_statement_or_note | True | (3) Includes commissions and any related fulfillment and shipping fees, and other third-party seller services. (4) Includes sales of advertising services to sellers, vendors, publishers, authors, and others, through programs such as sponsored ads, display, and video advertising. ... |
| 3 | `AMZN_2025_10K_ITEM8_BLOCK_0011_PART_01_OF_02` | Item 8. Financial Statements and Supplementary Data | Note 10 — | financial_statement_or_note | True | Note 10 — SEGMENT INFORMATION We have organized our operations into three segments: North America, International, and AWS. We allocate to segment results the operating expenses “Fulfillment,” “Technology and infrastructure,” “Sales and marketing,” and “General and administrative”... |
| 4 | `AMZN_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_10` | Item 8. Financial Statements and Supplementary Data | Note 1 — | financial_statement_or_note | True | Note 1 — DESCRIPTION OF BUSINESS, ACCOUNTING POLICIES, AND SUPPLEMENTAL DISCLOSURES Description of Business We seek to be Earth’s most customer-centric company. In each of our segments, we serve our primary customer sets, consisting of consumers, sellers, developers, enterprises,... |
| 5 | `AMZN_2023_10K_ITEM7_BLOCK_0005_PART_01_OF_03` | Item 7. Management's Discussion and Analysis | Overview | management_discussion | True | Overview Macroeconomic factors, including inflation, increased interest rates, significant capital market and supply chain volatility, and global economic and geopolitical developments, have direct and indirect impacts on our results of operations that are difficult to isolate an... |

## common_meta_2025_ads_ai_capex

- Category: `common_financial`
- Filter: `META 2025`
- Query: For Meta fiscal 2025, how are advertising revenue growth and AI infrastructure capital expenditures connected in the 10-K?
- Expected signal: advertising revenue, AI infrastructure, capital expenditures
- Unfiltered dense top5 metadata matches target: 4/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `META_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Executive Overview of Full Year 2025 Results | management_discussion | False | Executive Overview of Full Year 2025 Results Our mission is to build the future of human connection and the technology that makes it possible. Our financial results and key Family metrics for 2025 are set forth below. Total revenue for 2025 was $200.97 billion, an increase of 22%... |
| 2 | `META_2025_10K_ITEM7_BLOCK_0008_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Revenue | management_discussion | True | Revenue The following table sets forth our revenue by source and by segment: [TABLE_START id=12 rows=8] Year Ended December 31, 2025 \| 2024 \| 2023 \| 2025 vs 2024 % change \| 2024 vs 2023 % change (in millions, except percentages) Advertising \| $ \| 196,175 \| $ \| 160,633 \| $ \| 131,9... |
| 3 | `META_2025_10K_ITEM7_BLOCK_0008_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Revenue | management_discussion | True | See Note 1 — Summary of Significant Accounting Policies in the notes to the consolidated financial statements included in Part II, Item 8, "Financial Statements and Supplementary Data" of this Annual Report on Form 10-K for additional information regarding changes in the estimate... |
| 4 | `META_2025_10K_ITEM7_BLOCK_0007_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | True | We recognize revenue from the display of impression-based ads in the contracted period in which the impressions are delivered. Impressions are considered delivered when an ad is displayed to a user. We recognize revenue from the delivery of action-based ads in the period in which... |
| 5 | `META_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_07` | Item 8. Financial Statements and Supplementary Data | Note 1. | financial_statement_or_note | False | Note 1. Summary of Significant Accounting Policies Organization and Description of Business We were incorporated in Delaware in July 2004. Our mission is to build the future of human connection and the technology that makes it possible. We report our financial results based on tw... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `META_2025_10K_ITEM7_BLOCK_0008_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Revenue | management_discussion | True | Revenue The following table sets forth our revenue by source and by segment: [TABLE_START id=12 rows=8] Year Ended December 31, 2025 \| 2024 \| 2023 \| 2025 vs 2024 % change \| 2024 vs 2023 % change (in millions, except percentages) Advertising \| $ \| 196,175 \| $ \| 160,633 \| $ \| 131,9... |
| 2 | `META_2025_10K_ITEM7_BLOCK_0005_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Developments in Advertising | management_discussion | True | In addition, competitive products and services have reduced some users' engagement with our products and services. We are investing in Reels and in AI initiatives across our products, including our AI-powered discovery engine to recommend relevant content, which we have already s... |
| 3 | `META_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_07` | Item 8. Financial Statements and Supplementary Data | Note 1. | financial_statement_or_note | False | Note 1. Summary of Significant Accounting Policies Organization and Description of Business We were incorporated in Delaware in July 2004. Our mission is to build the future of human connection and the technology that makes it possible. We report our financial results based on tw... |
| 4 | `META_2025_10K_ITEM1_BLOCK_0003_CHUNK_0001` | Item 1. Business | Revenue and Investments | business_description | False | Revenue and Investments We report financial results for two segments: Family of Apps (FoA) and Reality Labs (RL). Currently, we generate substantially all of our revenue from selling advertising placements on our family of apps to marketers, which is reflected in FoA. Ads on our ... |
| 5 | `META_2025_10K_ITEM7_BLOCK_0007_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | True | We recognize revenue from the display of impression-based ads in the contracted period in which the impressions are delivered. Impressions are considered delivered when an ad is displayed to a user. We recognize revenue from the delivery of action-based ads in the period in which... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `META_2025_10K_ITEM7_BLOCK_0003_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Executive Overview of Full Year 2025 Results | management_discussion | False | Executive Overview of Full Year 2025 Results Our mission is to build the future of human connection and the technology that makes it possible. Our financial results and key Family metrics for 2025 are set forth below. Total revenue for 2025 was $200.97 billion, an increase of 22%... |
| 2 | `META_2025_10K_ITEM7_BLOCK_0008_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Revenue | management_discussion | True | Revenue The following table sets forth our revenue by source and by segment: [TABLE_START id=12 rows=8] Year Ended December 31, 2025 \| 2024 \| 2023 \| 2025 vs 2024 % change \| 2024 vs 2023 % change (in millions, except percentages) Advertising \| $ \| 196,175 \| $ \| 160,633 \| $ \| 131,9... |
| 3 | `META_2024_10K_ITEM1_BLOCK_0001_PART_01_OF_02` | Item 1. Business | Overview | business_description | False | Item 1. Business Overview Our mission is to build the future of human connection and the technology that makes it possible. We build technology that helps people connect and share, find and build communities, and grow businesses. Our products enable people to connect and share wi... |
| 4 | `META_2025_10K_ITEM7_BLOCK_0008_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Revenue | management_discussion | True | See Note 1 — Summary of Significant Accounting Policies in the notes to the consolidated financial statements included in Part II, Item 8, "Financial Statements and Supplementary Data" of this Annual Report on Form 10-K for additional information regarding changes in the estimate... |
| 5 | `META_2025_10K_ITEM7_BLOCK_0007_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | True | We recognize revenue from the display of impression-based ads in the contracted period in which the impressions are delivered. Impressions are considered delivered when an ad is displayed to a user. We recognize revenue from the delivery of action-based ads in the period in which... |

## common_googl_2025_ads_cloud_capex

- Category: `common_financial`
- Filter: `GOOGL 2025`
- Query: For Alphabet fiscal 2025, compare Google advertising and Google Cloud growth with capital expenditure needs.
- Expected signal: Google advertising revenue, Google Cloud revenue, capex or technical infrastructure
- Unfiltered dense top5 metadata matches target: 4/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `GOOGL_2025_10K_ITEM7_BLOCK_0017_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Other Information | management_discussion | True | Other Information: 32. [TABLE_START id=45 rows=1] Table of Contents \| Alphabet Inc. [TABLE_END] • In 2025, we entered into definitive agreements to acquire Wiz, a leading cloud security platform, for $32.0 billion, and Intersect, a provider of data center and energy infrastructur... |
| 2 | `GOOGL_2025_10K_ITEM7_BLOCK_0001_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS Please read the following discussion and analysis of our financial condition and results of operations together with “Note about Forward-Looking Statements,” Part I, Item 1 "Business," P... |
| 3 | `GOOGL_2025_10K_ITEM8_BLOCK_0017_CHUNK_0001` | Item 8. Financial Statements and Supplementary Data | Note 15. | financial_statement_or_note | True | Note 15. Information about Segments and Geographic Areas We report our segment results as Google Services, Google Cloud, and Other Bets: • Google Services includes products and services such as ads, Android, Chrome, devices, Google Maps, Google Play, Search, and YouTube. Google S... |
| 4 | `GOOGL_2025_10K_ITEM7_BLOCK_0019_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Segment Profitability | management_discussion | True | Segment Profitability We report our segment results as Google Services, Google Cloud, and Other Bets. Additionally, certain costs are not allocated to our segments because they represent Alphabet-level activities. For further details on our segments, see Part I, Item 1 Business a... |
| 5 | `GOOGL_2025_10K_ITEM7_BLOCK_0021_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Cash Provided by Operating Activities | management_discussion | True | Cash Provided by Operating Activities Our largest source of cash provided by operations are advertising revenues generated by Google Search & other properties, YouTube properties, and Google Network properties. In Google Services, we also generate cash through consumer subscripti... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `GOOGL_2025_10K_ITEM7_BLOCK_0017_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Other Information | management_discussion | True | Other Information: 32. [TABLE_START id=45 rows=1] Table of Contents \| Alphabet Inc. [TABLE_END] • In 2025, we entered into definitive agreements to acquire Wiz, a leading cloud security platform, for $32.0 billion, and Intersect, a provider of data center and energy infrastructur... |
| 2 | `GOOGL_2025_10K_ITEM7_BLOCK_0001_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS Please read the following discussion and analysis of our financial condition and results of operations together with “Note about Forward-Looking Statements,” Part I, Item 1 "Business," P... |
| 3 | `GOOGL_2025_10K_ITEM8_BLOCK_0017_CHUNK_0001` | Item 8. Financial Statements and Supplementary Data | Note 15. | financial_statement_or_note | True | Note 15. Information about Segments and Geographic Areas We report our segment results as Google Services, Google Cloud, and Other Bets: • Google Services includes products and services such as ads, Android, Chrome, devices, Google Maps, Google Play, Search, and YouTube. Google S... |
| 4 | `GOOGL_2025_10K_ITEM7_BLOCK_0006_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Traffic Acquisition Costs Growth and Rate Changes | management_discussion | True | Traffic Acquisition Costs Growth and Rate Changes: We expect traffic acquisition costs ("TAC") paid to our distribution partners and Google Network partners to increase as our advertising revenues grow. Our overall TAC as a percentage of our advertising revenues ("TAC rate") has ... |
| 5 | `GOOGL_2025_10K_ITEM7_BLOCK_0021_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Cash Provided by Operating Activities | management_discussion | True | Cash Provided by Operating Activities Our largest source of cash provided by operations are advertising revenues generated by Google Search & other properties, YouTube properties, and Google Network properties. In Google Services, we also generate cash through consumer subscripti... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `GOOGL_2025_10K_ITEM7_BLOCK_0017_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Other Information | management_discussion | True | Other Information: 32. [TABLE_START id=45 rows=1] Table of Contents \| Alphabet Inc. [TABLE_END] • In 2025, we entered into definitive agreements to acquire Wiz, a leading cloud security platform, for $32.0 billion, and Intersect, a provider of data center and energy infrastructur... |
| 2 | `GOOGL_2025_10K_ITEM7_BLOCK_0001_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS Please read the following discussion and analysis of our financial condition and results of operations together with “Note about Forward-Looking Statements,” Part I, Item 1 "Business," P... |
| 3 | `GOOGL_2025_10K_ITEM8_BLOCK_0017_CHUNK_0001` | Item 8. Financial Statements and Supplementary Data | Note 15. | financial_statement_or_note | True | Note 15. Information about Segments and Geographic Areas We report our segment results as Google Services, Google Cloud, and Other Bets: • Google Services includes products and services such as ads, Android, Chrome, devices, Google Maps, Google Play, Search, and YouTube. Google S... |
| 4 | `GOOGL_2025_10K_ITEM7_BLOCK_0019_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Segment Profitability | management_discussion | True | Segment Profitability We report our segment results as Google Services, Google Cloud, and Other Bets. Additionally, certain costs are not allocated to our segments because they represent Alphabet-level activities. For further details on our segments, see Part I, Item 1 Business a... |
| 5 | `GOOGL_2023_10K_ITEM7_BLOCK_0001_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | True | ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS Please read the following discussion and analysis of our financial condition and results of operations together with “Note about Forward-Looking Statements,” Part I, Item 1 "Business," P... |

## deep_adbe_2025_arr_rpo_revenue_quality

- Category: `deep_financial`
- Filter: `ADBE 2025`
- Query: For Adobe fiscal 2025, what do Digital Media ARR and remaining performance obligations imply about subscription revenue durability?
- Expected signal: Digital Media ARR, remaining performance obligations, subscription/revenue visibility
- Unfiltered dense top5 metadata matches target: 3/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Overview of Fiscal 2025 | management_discussion | True | Due to the nature of certain offerings which contain cross-product integrations or benefits, revenue attributable to certain product entitlements may be recognized in either customer group. By viewing the business through this lens, we can more effectively execute our long-term g... |
| 2 | `ADBE_2025_10K_ITEM7_BLOCK_0004_PART_01_OF_03` | Item 7. Management's Discussion and Analysis | Overview of Fiscal 2025 | management_discussion | False | Overview of Fiscal 2025 For our fiscal 2025, we experienced strong demand across our Digital Media and Digital Experience offerings, driven by transformative and customer-focused product innovation. As we execute on our long-term growth initiatives, with emphasis on delivering va... |
| 3 | `ADBE_2025_10K_ITEM7_BLOCK_0006_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | In fiscal 2025, we categorized our products into the following reportable segments | management_discussion | True | In fiscal 2025, we categorized our products into the following reportable segments: • Digital Media —Our Digital Media segment provides products and services that enable individuals, teams, businesses, and enterprises to create, publish and promote their content anywhere and acce... |
| 4 | `ADBE_2025_10K_ITEM8_BLOCK_0004_PART_01_OF_02` | Item 8. Financial Statements and Supplementary Data | Consolidated Statements of Income | financial_statement_or_note | True | Consolidated Statements of Income for a reconciliation of consolidated gross profit to consolidated income before income taxes. We generally categorize revenue by geographic area based on where the customer manages their utilization of our offerings. Revenue by geographic area fo... |
| 5 | `ADBE_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_06` | Item 8. Financial Statements and Supplementary Data | NOTE 1. | financial_statement_or_note | False | NOTE 1. BASIS OF PRESENTATION AND SIGNIFICANT ACCOUNTING POLICIES Operations Adobe’s mission is to empower everyone to create. We build innovative platforms and tools that unleash creativity, productivity and personalized customer experiences. For over four decades, our innovatio... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Overview of Fiscal 2025 | management_discussion | True | Due to the nature of certain offerings which contain cross-product integrations or benefits, revenue attributable to certain product entitlements may be recognized in either customer group. By viewing the business through this lens, we can more effectively execute our long-term g... |
| 2 | `ADBE_2025_10K_ITEM7_BLOCK_0004_PART_01_OF_03` | Item 7. Management's Discussion and Analysis | Overview of Fiscal 2025 | management_discussion | False | Overview of Fiscal 2025 For our fiscal 2025, we experienced strong demand across our Digital Media and Digital Experience offerings, driven by transformative and customer-focused product innovation. As we execute on our long-term growth initiatives, with emphasis on delivering va... |
| 3 | `ADBE_2025_10K_ITEM8_BLOCK_0004_PART_01_OF_02` | Item 8. Financial Statements and Supplementary Data | Consolidated Statements of Income | financial_statement_or_note | True | Consolidated Statements of Income for a reconciliation of consolidated gross profit to consolidated income before income taxes. We generally categorize revenue by geographic area based on where the customer manages their utilization of our offerings. Revenue by geographic area fo... |
| 4 | `ADBE_2025_10K_ITEM7_BLOCK_0006_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | In fiscal 2025, we categorized our products into the following reportable segments | management_discussion | True | In fiscal 2025, we categorized our products into the following reportable segments: • Digital Media —Our Digital Media segment provides products and services that enable individuals, teams, businesses, and enterprises to create, publish and promote their content anywhere and acce... |
| 5 | `ADBE_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_06` | Item 8. Financial Statements and Supplementary Data | NOTE 1. | financial_statement_or_note | False | NOTE 1. BASIS OF PRESENTATION AND SIGNIFICANT ACCOUNTING POLICIES Operations Adobe’s mission is to empower everyone to create. We build innovative platforms and tools that unleash creativity, productivity and personalized customer experiences. For over four decades, our innovatio... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `ADBE_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_03` | Item 7. Management's Discussion and Analysis | Overview of Fiscal 2025 | management_discussion | True | Due to the nature of certain offerings which contain cross-product integrations or benefits, revenue attributable to certain product entitlements may be recognized in either customer group. By viewing the business through this lens, we can more effectively execute our long-term g... |
| 2 | `ADBE_2025_10K_ITEM7_BLOCK_0004_PART_01_OF_03` | Item 7. Management's Discussion and Analysis | Overview of Fiscal 2025 | management_discussion | False | Overview of Fiscal 2025 For our fiscal 2025, we experienced strong demand across our Digital Media and Digital Experience offerings, driven by transformative and customer-focused product innovation. As we execute on our long-term growth initiatives, with emphasis on delivering va... |
| 3 | `ADBE_2025_10K_ITEM7_BLOCK_0006_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | In fiscal 2025, we categorized our products into the following reportable segments | management_discussion | True | In fiscal 2025, we categorized our products into the following reportable segments: • Digital Media —Our Digital Media segment provides products and services that enable individuals, teams, businesses, and enterprises to create, publish and promote their content anywhere and acce... |
| 4 | `ADBE_2024_10K_ITEM7_BLOCK_0004_PART_03_OF_03` | Item 7. Management's Discussion and Analysis | Overview of 2024 | management_discussion | True | While our revenue and earnings are relatively predictable as a result of our subscription-based business model, the broader implications of these macroeconomic events on our business, results of operations and overall financial position, particularly in the long term, remain unce... |
| 5 | `ADBE_2023_10K_ITEM7_BLOCK_0004_PART_01_OF_03` | Item 7. Management's Discussion and Analysis | Overview of 2023 | management_discussion | True | Overview of 2023 For our fiscal 2023, we experienced strong demand across our Digital Media and Digital Experience offerings, driven by our innovative product roadmap. As we execute on our long-term growth initiatives and deliver product innovation, we have continued to experienc... |

## deep_snow_2025_consumption_rpo_customer_metrics

- Category: `deep_financial`
- Filter: `SNOW 2025`
- Query: For Snowflake fiscal 2025, how do consumption revenue, remaining performance obligations, and customer count metrics support or weaken revenue visibility?
- Expected signal: consumption model, RPO, customer count metrics, revenue visibility
- Unfiltered dense top5 metadata matches target: 4/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `SNOW_2025_10K_ITEM1A_BLOCK_0003_CHUNK_0001` | Item 1A. Risk Factors | We may not have visibility into our future financial position and results of operations. | risk_disclosure | False | We may not have visibility into our future financial position and results of operations. Customers generally consume our platform by using compute, storage, and/or data transfer resources. Unlike a subscription-based business model, in which revenue is recognized ratably over the... |
| 2 | `SNOW_2025_10K_ITEM8_BLOCK_0001_PART_07_OF_12` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | ________________ (1) For the fiscal years ended January 31, 2025, 2024, and 2023, respectively, approximately 65 %, 67 %, and 71 % of cost of product revenue represented third-party cloud infrastructure expenses incurred in connection with the customers’ use of the Snowflake plat... |
| 3 | `SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Acquiring New Customers | management_discussion | True | Acquiring New Customers We believe there is a substantial opportunity to further grow our customer base by continuing to make significant investments in sales and marketing and brand awareness. Our ability to attract new customers will depend on a number of factors, including the... |
| 4 | `SNOW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_12` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | [TABLE_START id=27 rows=21] Fiscal Year Ended January 31, 2025 \| 2024 \| 2023 Revenue \| $ \| 3,626,396 \| $ \| 2,806,489 \| $ \| 2,065,659 Cost of revenue \| 1,214,673 \| 898,558 \| 717,540 Gross profit \| 2,411,723 \| 1,907,931 \| 1,348,119 Operating expenses: Sales and marketing \| 1,672,09... |
| 5 | `SNOW_2025_10K_ITEM8_BLOCK_0001_PART_02_OF_12` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | Critical Audit Matters The critical audit matter communicated below is a matter arising from the current period audit of the consolidated financial statements that was communicated or required to be communicated to the audit committee and that (i) relates to accounts or disclosur... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Acquiring New Customers | management_discussion | True | Acquiring New Customers We believe there is a substantial opportunity to further grow our customer base by continuing to make significant investments in sales and marketing and brand awareness. Our ability to attract new customers will depend on a number of factors, including the... |
| 2 | `SNOW_2025_10K_ITEM1A_BLOCK_0003_CHUNK_0001` | Item 1A. Risk Factors | We may not have visibility into our future financial position and results of operations. | risk_disclosure | False | We may not have visibility into our future financial position and results of operations. Customers generally consume our platform by using compute, storage, and/or data transfer resources. Unlike a subscription-based business model, in which revenue is recognized ratably over the... |
| 3 | `SNOW_2025_10K_ITEM7_BLOCK_0002_PART_01_OF_03` | Item 7. Management's Discussion and Analysis | Overview | management_discussion | False | Overview We believe that a cloud computing platform that puts data and artificial intelligence (AI) at its core will offer great benefits to organizations by allowing them to realize the value of the data that powers their businesses. By offering rich primitives for data and appl... |
| 4 | `SNOW_2025_10K_ITEM8_BLOCK_0001_PART_07_OF_12` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | ________________ (1) For the fiscal years ended January 31, 2025, 2024, and 2023, respectively, approximately 65 %, 67 %, and 71 % of cost of product revenue represented third-party cloud infrastructure expenses incurred in connection with the customers’ use of the Snowflake plat... |
| 5 | `SNOW_2025_10K_ITEM1A_BLOCK_0015_CHUNK_0001` | Item 1A. Risk Factors | Seasonality may cause fluctuations in our remaining performance obligations or in customer consumption. | risk_disclosure | False | Seasonality may cause fluctuations in our remaining performance obligations or in customer consumption. Historically, we have received a higher volume of orders from new and existing customers in the fourth fiscal quarter of each year. As a result, we have historically seen highe... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `SNOW_2025_10K_ITEM1A_BLOCK_0003_CHUNK_0001` | Item 1A. Risk Factors | We may not have visibility into our future financial position and results of operations. | risk_disclosure | False | We may not have visibility into our future financial position and results of operations. Customers generally consume our platform by using compute, storage, and/or data transfer resources. Unlike a subscription-based business model, in which revenue is recognized ratably over the... |
| 2 | `SNOW_2025_10K_ITEM8_BLOCK_0001_PART_07_OF_12` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | ________________ (1) For the fiscal years ended January 31, 2025, 2024, and 2023, respectively, approximately 65 %, 67 %, and 71 % of cost of product revenue represented third-party cloud infrastructure expenses incurred in connection with the customers’ use of the Snowflake plat... |
| 3 | `SNOW_2025_10K_ITEM7_BLOCK_0003_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Acquiring New Customers | management_discussion | True | Acquiring New Customers We believe there is a substantial opportunity to further grow our customer base by continuing to make significant investments in sales and marketing and brand awareness. Our ability to attract new customers will depend on a number of factors, including the... |
| 4 | `SNOW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_12` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | [TABLE_START id=27 rows=21] Fiscal Year Ended January 31, 2025 \| 2024 \| 2023 Revenue \| $ \| 3,626,396 \| $ \| 2,806,489 \| $ \| 2,065,659 Cost of revenue \| 1,214,673 \| 898,558 \| 717,540 Gross profit \| 2,411,723 \| 1,907,931 \| 1,348,119 Operating expenses: Sales and marketing \| 1,672,09... |
| 5 | `SNOW_2023_10K_ITEM7_BLOCK_0002_PART_01_OF_03` | Item 7. Management's Discussion and Analysis | Overview | management_discussion | False | Overview We believe in a data connected world where organizations have seamless access to explore, share, and unlock the value of data. To realize this vision, we deliver the Data Cloud, a network where Snowflake customers, partners, developers, data providers, and data consumers... |

## deep_panw_2025_platformization_billings_rpo

- Category: `deep_financial`
- Filter: `PANW 2025`
- Query: For Palo Alto Networks fiscal 2025, how does platformization affect billings, revenue visibility, or remaining performance obligations?
- Expected signal: platformization, billings or deferred/RPO/revenue visibility
- Unfiltered dense top5 metadata matches target: 3/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `PANW_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_21` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | [TABLE_START id=38 rows=50] CONSOLIDATED STATEMENTS OF CASH FLOWS (In millions) Year Ended July 31, 2025 \| 2024 \| 2023 Cash flows from operating activities Net income \| $ \| 1,133.9 \| $ \| 2,577.6 \| $ \| 439.7 Adjustments to reconcile net income to net cash provided by operating act... |
| 2 | `PANW_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_21` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | Item 8. Financial Statements and Supplementary Data [TABLE_START id=30 rows=0] [TABLE_END] Index To Consolidated Financial Statements [TABLE_START id=31 rows=8] Page Reports of Independent Registered Public Accounting Firm (PCAOB ID: 42 ) \| 58 Consolidated Balance Sheets \| 61 Con... |
| 3 | `PANW_2025_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | General | business_description | False | Item 1. Business General Palo Alto Networks, Inc. is a global cybersecurity provider and our vision is a world where each day is safer and more secure than the one before. We were incorporated in 2005 and are headquartered in Santa Clara, California. Our mission is to be the cybe... |
| 4 | `PANW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_21` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | Because of its inherent limitations, internal control over financial reporting may not prevent or detect misstatements. Also, projections of any evaluation of effectiveness to future periods are subject to the risk that controls may become inadequate because of changes in conditi... |
| 5 | `PANW_2025_10K_ITEM1_BLOCK_0016_CHUNK_0001` | Item 1. Business | CORPORATE RESPONSIBILITY | business_description | False | CORPORATE RESPONSIBILITY Our Corporate Responsibility (CR) strategy supports our company's purpose of a safe and secure world, and is informed through many inputs, including our business strategy and objectives, ongoing stakeholder engagement, investor and customer interests, ben... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `PANW_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_21` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | Item 8. Financial Statements and Supplementary Data [TABLE_START id=30 rows=0] [TABLE_END] Index To Consolidated Financial Statements [TABLE_START id=31 rows=8] Page Reports of Independent Registered Public Accounting Firm (PCAOB ID: 42 ) \| 58 Consolidated Balance Sheets \| 61 Con... |
| 2 | `PANW_2025_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | General | business_description | False | Item 1. Business General Palo Alto Networks, Inc. is a global cybersecurity provider and our vision is a world where each day is safer and more secure than the one before. We were incorporated in 2005 and are headquartered in Santa Clara, California. Our mission is to be the cybe... |
| 3 | `PANW_2025_10K_ITEM1_BLOCK_0007_CHUNK_0001` | Item 1. Business | THREAT INTELLIGENCE AND ADVISORY SERVICES | business_description | False | THREAT INTELLIGENCE AND ADVISORY SERVICES • Customer Support. Global customer support helps our customers achieve their security outcomes with services and support capabilities covering the customer's entire journey with Palo Alto Networks. This post-sales, global organization ad... |
| 4 | `PANW_2025_10K_ITEM1_BLOCK_0015_PART_02_OF_02` | Item 1. Business | MANUFACTURING | business_description | False | Listen & Engage. We aim to foster engagement and help employees feel connected to our mission and values. Through our comprehensive approach, we use in-person and virtual channels to provide a regular flow of information to and between employees and leadership. These channels inc... |
| 5 | `PANW_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_21` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | Because of its inherent limitations, internal control over financial reporting may not prevent or detect misstatements. Also, projections of any evaluation of effectiveness to future periods are subject to the risk that controls may become inadequate because of changes in conditi... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `PANW_2025_10K_ITEM8_BLOCK_0001_PART_05_OF_21` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | [TABLE_START id=38 rows=50] CONSOLIDATED STATEMENTS OF CASH FLOWS (In millions) Year Ended July 31, 2025 \| 2024 \| 2023 Cash flows from operating activities Net income \| $ \| 1,133.9 \| $ \| 2,577.6 \| $ \| 439.7 Adjustments to reconcile net income to net cash provided by operating act... |
| 2 | `PANW_2024_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | General | business_description | False | Item 1. Business General Palo Alto Networks, Inc. is a global cybersecurity provider with a vision of a world where each day is safer and more secure than the one before. We were incorporated in 2005 and are headquartered in Santa Clara, California. We empower enterprises, organi... |
| 3 | `PANW_2025_10K_ITEM8_BLOCK_0001_PART_01_OF_21` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | Item 8. Financial Statements and Supplementary Data [TABLE_START id=30 rows=0] [TABLE_END] Index To Consolidated Financial Statements [TABLE_START id=31 rows=8] Page Reports of Independent Registered Public Accounting Firm (PCAOB ID: 42 ) \| 58 Consolidated Balance Sheets \| 61 Con... |
| 4 | `PANW_2025_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | General | business_description | False | Item 1. Business General Palo Alto Networks, Inc. is a global cybersecurity provider and our vision is a world where each day is safer and more secure than the one before. We were incorporated in 2005 and are headquartered in Santa Clara, California. Our mission is to be the cybe... |
| 5 | `PANW_2023_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | General | business_description | False | Item 1. Business General Palo Alto Networks, Inc. is a global cybersecurity provider with a vision of a world where each day is safer and more secure than the one before. We were incorporated in 2005 and are headquartered in Santa Clara, California. We empower enterprises, organi... |

## deep_amd_2024_segment_mix_margin_inventory

- Category: `deep_financial`
- Filter: `AMD 2024`
- Query: For AMD fiscal 2024, how did segment mix and gross margin change, and what inventory or supply-chain signals matter?
- Expected signal: segment revenue mix, gross margin, inventory or supply-chain signals
- Unfiltered dense top5 metadata matches target: 4/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMD_2024_10K_ITEM7_BLOCK_0004_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Results of Operations | management_discussion | True | Results of Operations Additional information on our reportable segments is contained in Note 4 – Segment Reporting of the Notes to Financial Statements (Part II, Item 8 of this Form 10-K). Our operating results tend to vary seasonally. Historically, our net revenue has been gener... |
| 2 | `AMD_2024_10K_ITEM7_BLOCK_0001_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS The following discussion should be read in conjunction with the Consolidated Financial Statements as of December 28, 2024 and December 30, 2023 and for each of the three years in the per... |
| 3 | `AMD_2024_10K_ITEM7_BLOCK_0001_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Gross margin, as a percentage of net revenue, was 49% for 2024, compared to 46% in 2023. The increase in gross margin was primarily due to a favorable shift in revenue mix with higher Data Center and Client revenues, lower Gaming revenue, partially offset by the impact of lower E... |
| 4 | `AMD_2024_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | BUSINESS | business_description | False | ITEM 1. BUSINESS Cautionary Statement Regarding Forward-Looking Statements The statements in this report include forward-looking statements within the meaning of the Private Securities Litigation Reform Act of 1995. These forward-looking statements are based on current expectatio... |
| 5 | `AMD_2024_10K_ITEM8_BLOCK_0001_PART_03_OF_03` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | [TABLE_START id=17 rows=45] Year Ended December 28, 2024 \| December 30, 2023 \| December 31, 2022 (In millions) Cash flows from operating activities: Net income \| $ \| 1,641 \| $ \| 854 \| $ \| 1,320 Adjustments to reconcile net income to net cash provided by operating activities: Depr... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMD_2024_10K_ITEM7_BLOCK_0004_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Results of Operations | management_discussion | True | Results of Operations Additional information on our reportable segments is contained in Note 4 – Segment Reporting of the Notes to Financial Statements (Part II, Item 8 of this Form 10-K). Our operating results tend to vary seasonally. Historically, our net revenue has been gener... |
| 2 | `AMD_2024_10K_ITEM7_BLOCK_0001_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS The following discussion should be read in conjunction with the Consolidated Financial Statements as of December 28, 2024 and December 30, 2023 and for each of the three years in the per... |
| 3 | `AMD_2024_10K_ITEM7_BLOCK_0001_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Gross margin, as a percentage of net revenue, was 49% for 2024, compared to 46% in 2023. The increase in gross margin was primarily due to a favorable shift in revenue mix with higher Data Center and Client revenues, lower Gaming revenue, partially offset by the impact of lower E... |
| 4 | `AMD_2024_10K_ITEM8_BLOCK_0019_PART_01_OF_02` | Item 8. Financial Statements and Supplementary Data | NOTE 18 – | financial_statement_or_note | True | NOTE 18 – Contingencies Litigation and Other Legal Matters As of December 28, 2024, there were no material legal proceedings. 85 Table of Contents The Company is a defendant or plaintiff in various actions that arose in the normal course of business. With respect to these matters... |
| 5 | `AMD_2024_10K_ITEM1A_BLOCK_0015_CHUNK_0001` | Item 1A. Risk Factors | Uncertainties involving the ordering and shipment of our products could materially adversely affect us. | risk_disclosure | False | Uncertainties involving the ordering and shipment of our products could materially adversely affect us. We typically sell our products pursuant to individual purchase orders. We generally do not have long-term supply arrangements with our customers or minimum purchase requirement... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMD_2024_10K_ITEM7_BLOCK_0004_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Results of Operations | management_discussion | True | Results of Operations Additional information on our reportable segments is contained in Note 4 – Segment Reporting of the Notes to Financial Statements (Part II, Item 8 of this Form 10-K). Our operating results tend to vary seasonally. Historically, our net revenue has been gener... |
| 2 | `AMD_2024_10K_ITEM7_BLOCK_0001_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | ITEM 7. MANAGEMENT’S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS The following discussion should be read in conjunction with the Consolidated Financial Statements as of December 28, 2024 and December 30, 2023 and for each of the three years in the per... |
| 3 | `AMD_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Results of Operations | management_discussion | False | Gross Margin Gross margin of 50% increased by 1% compared to 49% in 2024, primarily due to product mix, partially offset by approximately $440 million of net inventory and related charges associated with the U.S. government export control on AMD Instinct™ MI308 Data Center GPU pr... |
| 4 | `AMD_2024_10K_ITEM7_BLOCK_0001_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Gross margin, as a percentage of net revenue, was 49% for 2024, compared to 46% in 2023. The increase in gross margin was primarily due to a favorable shift in revenue mix with higher Data Center and Client revenues, lower Gaming revenue, partially offset by the impact of lower E... |
| 5 | `AMD_2024_10K_ITEM1_BLOCK_0001_CHUNK_0001` | Item 1. Business | BUSINESS | business_description | False | ITEM 1. BUSINESS Cautionary Statement Regarding Forward-Looking Statements The statements in this report include forward-looking statements within the meaning of the Private Securities Litigation Reform Act of 1995. These forward-looking statements are based on current expectatio... |

## deep_nvda_2025_supply_chain_customer_risk

- Category: `deep_financial`
- Filter: `NVDA 2025`
- Query: For NVIDIA fiscal 2025, what are the supply-chain manufacturing concentration risks and how do they interact with customer concentration?
- Expected signal: supplier/manufacturing concentration risk and customer concentration
- Unfiltered dense top5 metadata matches target: 2/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_01_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations The following discussion and analysis of our financial condition and results of operations should be read in conjunction with “Item 1A. Risk Factors,” our Consolidated Financial Statemen... |
| 2 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_03_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | True | Macroeconomic Factors Macroeconomic factors, including inflation, interest rate changes, capital market volatility, global supply chain constraints, tariffs, and global economic and geopolitical developments, may have direct and indirect impacts on our results of operations, part... |
| 3 | `NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_02_OF_03` | Item 1A. Risk Factors | Risks Related to Demand, Supply, and Manufacturing | risk_disclosure | False | We continue to increase our supply and capacity purchases with existing and new suppliers to support our demand projections and increasing complexity of our data center products. With these additions, we have also entered and may continue to enter into prepaid manufacturing and c... |
| 4 | `NVDA_2025_10K_ITEM7_BLOCK_0007_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Concentration of Revenue | management_discussion | False | Concentration of Revenue We refer to customers who purchase products directly from NVIDIA as direct customers, such as AIBs, distributors, ODMs, OEMs, and system integrators. We have certain customers that may purchase products directly from NVIDIA and may use either internal res... |
| 5 | `NVDA_2025_10K_ITEM1A_BLOCK_0001_CHUNK_0001` | Item 1A. Risk Factors | Item 1A. Risk Factors | risk_disclosure | False | Item 1A. Risk Factors The following risk factors should be considered in addition to the other information in this Annual Report on Form 10-K. The following risks could harm our business, financial condition, results of operations or reputation, which could cause our stock 13 Tab... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_03_OF_03` | Item 1A. Risk Factors | Risks Related to Demand, Supply, and Manufacturing | risk_disclosure | False | Dependency on third-party suppliers and their technology to manufacture, assemble, test, or package our products reduces our control over product quantity and quality, manufacturing yields, and product delivery schedules and could harm our business. We depend on foundries to manu... |
| 2 | `NVDA_2025_10K_ITEM7_BLOCK_0007_CHUNK_0001` | Item 7. Management's Discussion and Analysis | Concentration of Revenue | management_discussion | False | Concentration of Revenue We refer to customers who purchase products directly from NVIDIA as direct customers, such as AIBs, distributors, ODMs, OEMs, and system integrators. We have certain customers that may purchase products directly from NVIDIA and may use either internal res... |
| 3 | `NVDA_2025_10K_ITEM1A_BLOCK_0001_CHUNK_0001` | Item 1A. Risk Factors | Item 1A. Risk Factors | risk_disclosure | False | Item 1A. Risk Factors The following risk factors should be considered in addition to the other information in this Annual Report on Form 10-K. The following risks could harm our business, financial condition, results of operations or reputation, which could cause our stock 13 Tab... |
| 4 | `NVDA_2025_10K_ITEM1_BLOCK_0005_PART_02_OF_03` | Item 1. Business | Our current competitors include | business_description | False | On January 15, 2025, the USG published the “AI Diffusion” IFR in the Federal Register. After a 120-day delayed compliance period, the IFR will, unless modified, impose a worldwide licensing requirement on all products classified under Export Control Classification Numbers, or ECC... |
| 5 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_01_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations The following discussion and analysis of our financial condition and results of operations should be read in conjunction with “Item 1A. Risk Factors,” our Consolidated Financial Statemen... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_01_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | False | Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations The following discussion and analysis of our financial condition and results of operations should be read in conjunction with “Item 1A. Risk Factors,” our Consolidated Financial Statemen... |
| 2 | `NVDA_2025_10K_ITEM7_BLOCK_0001_PART_03_OF_04` | Item 7. Management's Discussion and Analysis | Item 7. Management's Discussion and Analysis | management_discussion | True | Macroeconomic Factors Macroeconomic factors, including inflation, interest rate changes, capital market volatility, global supply chain constraints, tariffs, and global economic and geopolitical developments, may have direct and indirect impacts on our results of operations, part... |
| 3 | `NVDA_2023_10K_ITEM1A_BLOCK_0001_CHUNK_0001` | Item 1A. Risk Factors | Item 1A. Risk Factors | risk_disclosure | False | ITEM 1A. RISK FACTORS In evaluating NVIDIA, the following risk factors should be considered in addition to the other information in this Annual Report on Form 10-K. Purchasing or owning NVIDIA common stock involves investment risks including, but not limited to, the risks describ... |
| 4 | `NVDA_2024_10K_ITEM1A_BLOCK_0012_PART_02_OF_02` | Item 1A. Risk Factors | disadvantage NVIDIA against certain of our competitors who sell products that are not subject to the new restrictions or may be able to acquire licenses for their products. | risk_disclosure | False | Finally, our business depends on our ability to receive consistent and reliable supply from our overseas partners, especially in Taiwan. Any new restrictions that negatively impact our ability to receive supply of components, parts, or services from Taiwan, would negatively impac... |
| 5 | `NVDA_2024_10K_ITEM7_BLOCK_0002_PART_01_OF_04` | Item 7. Management's Discussion and Analysis | Recent Developments, Future Objectives and Challenges | management_discussion | False | Recent Developments, Future Objectives and Challenges Demand and Supply, Product Transitions, and New Products and Business Models Demand for our data center systems and products surged in fiscal year 2024. Entering fiscal year 2025, we are gathering customer demand indications a... |

## deep_amzn_2025_liquidity_leases_commitments

- Category: `deep_financial`
- Filter: `AMZN 2025`
- Query: For Amazon fiscal 2025, what liquidity, lease obligations, and purchase commitments could affect free cash flow?
- Expected signal: liquidity/cash flow, lease obligations, purchase commitments
- Unfiltered dense top5 metadata matches target: 2/5

### Dense Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMZN_2025_10K_ITEM8_BLOCK_0008_PART_01_OF_03` | Item 8. Financial Statements and Supplementary Data | Note 7 — | financial_statement_or_note | True | Note 7 — COMMITMENTS AND CONTINGENCIES Commitments The following summarizes our principal contractual commitments, excluding open orders for purchases that support normal operations and are generally cancellable, as of December 31, 2025 (in millions): [TABLE_START id=59 rows=10] ... |
| 2 | `AMZN_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_04` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | [TABLE_START id=35 rows=36] Year Ended December 31, 2023 \| 2024 \| 2025 CASH, CASH EQUIVALENTS, AND RESTRICTED CASH, BEGINNING OF PERIOD \| $ \| 54,253 \| $ \| 73,890 \| $ \| 82,312 OPERATING ACTIVITIES: Net income \| 30,425 \| 59,248 \| 77,670 Adjustments to reconcile net income to net ca... |
| 3 | `AMZN_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | False | Cash provided by (used in) financing activities was $(11.8) billion and $9.7 billion in 2024 and 2025. Cash inflows from financing activities resulted from proceeds from short-term debt, and other and long-term-debt of $5.1 billion and $25.0 billion in 2024 and 2025. Cash outflow... |
| 4 | `AMZN_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_10` | Item 8. Financial Statements and Supplementary Data | Note 1 — | financial_statement_or_note | True | Note 1 — DESCRIPTION OF BUSINESS, ACCOUNTING POLICIES, AND SUPPLEMENTAL DISCLOSURES Description of Business We seek to be Earth’s most customer-centric company. In each of our segments, we serve our primary customer sets, consisting of consumers, sellers, developers, enterprises,... |
| 5 | `AMZN_2025_10K_ITEM7_BLOCK_0007_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | False | 29 Table of Contents Guidance We provided guidance on February 5, 2026, in our earnings release furnished on Form 8-K as set forth below. These forward-looking statements reflect Amazon.com’s expectations as of February 5, 2026, and are subject to substantial uncertainty. Our res... |

### Hybrid Qwen Filtered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMZN_2025_10K_ITEM8_BLOCK_0008_PART_01_OF_03` | Item 8. Financial Statements and Supplementary Data | Note 7 — | financial_statement_or_note | True | Note 7 — COMMITMENTS AND CONTINGENCIES Commitments The following summarizes our principal contractual commitments, excluding open orders for purchases that support normal operations and are generally cancellable, as of December 31, 2025 (in millions): [TABLE_START id=59 rows=10] ... |
| 2 | `AMZN_2025_10K_ITEM7_BLOCK_0004_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | False | Cash provided by (used in) financing activities was $(11.8) billion and $9.7 billion in 2024 and 2025. Cash inflows from financing activities resulted from proceeds from short-term debt, and other and long-term-debt of $5.1 billion and $25.0 billion in 2024 and 2025. Cash outflow... |
| 3 | `AMZN_2025_10K_ITEM8_BLOCK_0002_PART_01_OF_10` | Item 8. Financial Statements and Supplementary Data | Note 1 — | financial_statement_or_note | True | Note 1 — DESCRIPTION OF BUSINESS, ACCOUNTING POLICIES, AND SUPPLEMENTAL DISCLOSURES Description of Business We seek to be Earth’s most customer-centric company. In each of our segments, we serve our primary customer sets, consisting of consumers, sellers, developers, enterprises,... |
| 4 | `AMZN_2025_10K_ITEM7_BLOCK_0007_PART_01_OF_02` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | True | Income Taxes Our effective tax rate is subject to significant variation due to several factors, including variability in our pre-tax and taxable income and loss and the mix of jurisdictions to which they relate, intercompany transactions, the applicability of special tax regimes,... |
| 5 | `AMZN_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_04` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | [TABLE_START id=35 rows=36] Year Ended December 31, 2023 \| 2024 \| 2025 CASH, CASH EQUIVALENTS, AND RESTRICTED CASH, BEGINNING OF PERIOD \| $ \| 54,253 \| $ \| 73,890 \| $ \| 82,312 OPERATING ACTIVITIES: Net income \| 30,425 \| 59,248 \| 77,670 Adjustments to reconcile net income to net ca... |

### Dense Qwen Unfiltered Top5

| Rank | Evidence ID | Section | Subsection | Type | Table | Preview |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | `AMZN_2024_10K_ITEM7_BLOCK_0007_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | True | [TABLE_START id=30 rows=11] Year Ended December 31, 2023 \| 2024 Net cash provided by (used in) operating activities \| $ \| 84,946 \| $ \| 115,877 Purchases of property and equipment, net of proceeds from sales and incentives \| (48,133) \| (77,658) Free cash flow \| 36,813 \| 38,219 Equ... |
| 2 | `AMZN_2025_10K_ITEM8_BLOCK_0008_PART_01_OF_03` | Item 8. Financial Statements and Supplementary Data | Note 7 — | financial_statement_or_note | True | Note 7 — COMMITMENTS AND CONTINGENCIES Commitments The following summarizes our principal contractual commitments, excluding open orders for purchases that support normal operations and are generally cancellable, as of December 31, 2025 (in millions): [TABLE_START id=59 rows=10] ... |
| 3 | `AMZN_2023_10K_ITEM7_BLOCK_0006_PART_02_OF_02` | Item 7. Management's Discussion and Analysis | Income Taxes | management_discussion | True | [TABLE_START id=30 rows=11] Year Ended December 31, 2022 \| 2023 Net cash provided by (used in) operating activities \| $ \| 46,752 \| $ \| 84,946 Purchases of property and equipment, net of proceeds from sales and incentives \| (58,321) \| (48,133) Free cash flow \| (11,569) \| 36,813 Eq... |
| 4 | `AMZN_2024_10K_ITEM8_BLOCK_0008_PART_01_OF_03` | Item 8. Financial Statements and Supplementary Data | Note 7 — | financial_statement_or_note | True | Note 7 — COMMITMENTS AND CONTINGENCIES Commitments The following summarizes our principal contractual commitments, excluding open orders for purchases that support normal operations and are generally cancellable, as of December 31, 2024 (in millions): [TABLE_START id=60 rows=10] ... |
| 5 | `AMZN_2025_10K_ITEM8_BLOCK_0001_PART_03_OF_04` | Item 8. Financial Statements and Supplementary Data | Item 8. Financial Statements and Supplementary Data | financial_statement_or_note | True | [TABLE_START id=35 rows=36] Year Ended December 31, 2023 \| 2024 \| 2025 CASH, CASH EQUIVALENTS, AND RESTRICTED CASH, BEGINNING OF PERIOD \| $ \| 54,253 \| $ \| 73,890 \| $ \| 82,312 OPERATING ACTIVITIES: Net income \| 30,425 \| 59,248 \| 77,670 Adjustments to reconcile net income to net ca... |
