# WorkBuddy 12-case 语义与结构化轨迹复审

日期：2026-07-11

状态：`pass`。含义：semantic_and_structured_trajectory_review_completed_not_pack_promotion。

## 总结

- Case：12。直接晋升 WorkBuddy pack：`0`。
- Pack candidates：20；retain with independent evidence：4；redesign then pack：16。
- 全部 12 个 case 的数值表格单元格均未提供 claim-local citation；source list 与数值 claim 分离。
- 复审读取最终 HTML 与结构化 tool input/output、error、sequence 和 token metadata；未读取或复制 raw reasoning/generation spans。

## 系统性发现

- 12/12 reports have zero claim-local links in numeric table cells; detached source lists cannot support claim-level review.
- Multi-step tool activity is present, but no subagent/handoff execution or claim-to-observation lineage is visible in any case.
- WebSearch-heavy cases consume result snippets without source-open verification; structured financial queries also lack row/source lineage in final reports.
- Material scale and category errors recur: roughly 10x market-cap errors, product revenue annualization errors, and acquisition value/ARR confusion.
- Cross-case consistency is not governed: S04 says Target comparable sales were not disclosed while T01 correctly uses 5.6% from the same quarter.
- Artifact syntax checks occur after writing, but semantic, numeric, citation, chart-data, and narrative-consistency verification does not.
- Task lists are planning aids, not subagents; completion states can coexist with hidden output errors or a terminal agent trace error.
- High cached context reduces marginal token cost but does not prove information efficiency; useful claim yield and duplicate-context rate were not controlled.
- Report-type structures are often useful, but the current claims, rankings, probabilities, valuations, and company scores cannot be inherited.
- No WorkBuddy report is eligible for direct pack promotion; only independently corroborated and redesigned mechanisms are candidates.

## Case 裁决

| Case | Sector | Type | Decision | Severity | Semantic | Evidence | Numeric | Tool grounding | Repair |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| WB-S01 | technology_software_services | company_comparison | redesign | high | 4 | 1 | 1 | 1 | 1 |
| WB-S02 | banks_financials | company_comparison | redesign | high | 4 | 2 | 2 | 2 | 1 |
| WB-S03 | healthcare_pharma_medtech | company_comparison | improve | medium_high | 5 | 3 | 2 | 2 | 1 |
| WB-S04 | retail_consumer | company_comparison | redesign | critical | 4 | 1 | 1 | 2 | 1 |
| WB-S05 | energy | company_comparison | redesign | critical | 5 | 2 | 1 | 1 | 1 |
| WB-S06 | utilities_power | company_comparison | improve | high | 5 | 2 | 2 | 1 | 1 |
| WB-S07 | industrials | company_comparison | redesign | critical | 5 | 2 | 1 | 2 | 1 |
| WB-S08 | cybersecurity | company_comparison | redesign | critical | 4 | 2 | 1 | 1 | 1 |
| WB-T01 | retail_consumer | earnings_event_update | improve | medium_high | 5 | 3 | 3 | 2 | 2 |
| WB-T02 | healthcare_pharma_medtech | valuation_price_in | reject_as_reference | critical | 4 | 2 | 1 | 2 | 2 |
| WB-T03 | auto_mobility | policy_shock | redesign | critical | 5 | 2 | 1 | 1 | 1 |
| WB-T04 | cybersecurity | counter_thesis | improve | high | 5 | 2 | 1 | 1 | 1 |

## 逐案发现

### WB-S01 - redesign

语义：Product adoption to ARR/RPO/revenue/margin/FCF is a useful SaaS mechanism；Many values are labeled verified without claim-local primary evidence；Cross-company ARR/ACV/NRR definitions are not normalized and some product metrics appear incomparable；Company scoring and valuation conclusions outrun evidence quality

轨迹：Twelve broad WebSearch calls but no source-open verification；No structured financial tool or subagent handoff；Report was written without post-write research or semantic repair；Cumulative context is large relative to unverifiable claim output

可保留候选：SaaS product-adoption to financial-capture mechanism；Seat versus consumption pricing distinction；SBC/FCF and sales-efficiency counterchecks

必须改进：Normalize ARR/RPO/NRR definitions and periods；Require issuer-first product KPI slots and numeric trace；Separate reported AI revenue from adoption proxy

拒绝继承：verified labels based on search snippets；unsupported moat scores；cross-company ranking from non-comparable metrics

### WB-S02 - redesign

语义：Deposit franchise to funding cost/NIM/NII/credit/CET1 is the correct bank ontology；Wells Fargo asset-cap mechanism is stale after the June 2025 removal；Quarterly, annual and estimated figures are mixed without period lineage；Primary-source clickthrough is absent despite many exact values

轨迹：Financial tools and methodology skills were used, but shell-query rows are opaque in the report；No official filing/source-open verification；No semantic reconciliation after gathering；Task completion does not establish bank metric comparability

可保留候选：Bank balance-sheet and credit transmission chain；Deposit beta and asset-liability sensitivity cells；CET1/capital return and fee-income diversification cells

必须改进：Add bank metric ontology and period normalization；Bind regulatory changes and enforcement status by as-of date；Separate reported, estimated and calculated NIM/credit figures

拒绝继承：stale regulatory constraints as current mechanism；unlabeled annual/quarterly mixing；letter-grade rankings without trace

### WB-S03 - improve

语义：Clinical/regulatory/access/supply/prescription/revenue separation is strong；Official links are present but exact figures remain detached from citations；USD conversion, product estimates and annualization need program trace；Valuation price-in discussion is descriptive rather than executable

轨迹：Combines finance tools and six searches but does not open and reconcile each primary source；No parser/numeric verification step；No post-write evidence repair；No specialist handoff despite multiple domains

可保留候选：Healthcare milestone and commercialization mechanism；Patient-demand to recognized-revenue funnel；Supply/API/fill-finish and reimbursement constraints；Clinical versus commercial evidence separation

必须改进：Bind trial endpoint, approval and label claims to primary documents；Add currency/product revenue normalization；Route valuation to deterministic engine

拒绝继承：estimated product panels as exact facts；probability labels without calibration；valuation conclusions without executable trace

### WB-S04 - redesign

语义：Traffic/ticket/price/mix/inventory/margin is the right retail mechanism；Report has zero external links；It incorrectly says Target comparable sales were not disclosed; official Q1 release reports 5.6%；Cross-case contradiction with T01 proves no shared accepted-fact memory；Several Costco and inventory values are estimates without row lineage

轨迹：Nine opaque financial queries and no WebSearch/source-open verification；No conflict check against official earnings release；Artifact validation is syntax-only；No repair after factual inconsistency

可保留候选：Retail sales decomposition；Inventory/promotion/gross-margin transmission；Alternative profit pools such as ads, membership and marketplace

必须改进：Issuer filing/release must precede aggregator data；Create shared accepted fact and contradiction check；Separate comp sales, total sales and new-store/non-merchandise contribution

拒绝继承：zero-source report with exact numbers；false disclosure-gap claim；star ratings and ranking without evidence gate

### WB-S05 - redesign

语义：Volume/realized price/differential/unit cost/capex/FCF is a strong energy mechanism；Market caps are about 10x overstated；Scenario probabilities and cash-flow sensitivities are unsupported calculations；Current-event and hedge/MTM claims are not bound to filings；Estimated sustaining capex and breakevens are presented too confidently

轨迹：Eleven searches and no source-open verification；No structured numeric program for oil-price sensitivities；No post-write research or challenge；Syntax validation does not test chart assumptions

可保留候选：Energy price-to-cash transmission；Realized price versus benchmark/differential/hedge distinction；Sustaining versus growth capex；Integrated downstream/chemical cycle offset

必须改进：Use filing-based production/cost/capex facts；Execute scenario model with assumptions and reconciliation；Add reserve and project lineage

拒绝继承：current market cap and valuation rows；untraceable scenario probabilities；unsupported OCF/FCF sensitivity tables；estimated breakeven as exact fact

### WB-S06 - improve

语义：Load to approved project/capex/rate base/ROE/EPS/cash financing is a strong utility mechanism；Regulated versus merchant distinction is decision-useful；Many load pipeline, fuel mix, debt and ROE values are estimated or jurisdiction-specific without docket lineage；Valuation and data-center price-in claims lack reproducible calculations

轨迹：Twelve searches but no direct source-open verification；No regulatory docket or EIA structured tool；No numeric financing/credit model；No post-write repair

可保留候选：Utility load-to-rate-base mechanism；Regulated versus merchant operator split；Approval/interconnection/equipment/financing bottleneck cells

必须改进：Bind rate cases to jurisdiction/docket/effective period；Separate signed load, advanced discussion and speculative queue；Add debt/equity financing and credit trace

拒绝继承：aggregate load-interest as committed demand；untraceable fuel mix estimates；valuation premiums without scenario trace

### WB-S07 - redesign

语义：Orders/book-to-bill/backlog/cancellation/delivery/price-cost/cash is a strong industrial mechanism；Market caps are about 10x overstated；Backlog and book-to-bill values mix reported and inferred data；Cycle-stage labels and target-price scenarios are subjective without model trace

轨迹：Trace terminates with agent error despite completed artifact；Six searches plus financial queries but no claim-source reconciliation；No recovery event explains terminal state；Syntax check does not address numeric defects

可保留候选：Industrial order-to-cash mechanism；Backlog quality and cancellation cells；Aftermarket/service cycle stabilizer；Dealer/customer inventory separation

必须改进：Require reported versus inferred book-to-bill flags；Add backlog conversion and cancellation trace；Model price-cost and working-capital bridge

拒绝继承：market cap/valuation rows；subjective cycle labels as facts；price targets without valuation engine；artifact-complete equals trajectory-pass

### WB-S08 - redesign

语义：Module adoption to ARR/RPO/retention/SBC/FCF is useful；CyberArk acquisition/product metrics are category-confused；CRWD market cap and split-adjustment logic are materially wrong；Organic and acquired ARR are not consistently separated；Most citations are secondary and detached

轨迹：Twelve WebSearch calls and no source-open verification；Single task provides little decomposition；No numeric/category sanity gate；No post-write factual repair

可保留候选：Cybersecurity platform adoption mechanism；Organic versus acquired ARR requirement；SBC/GAAP/FCF quality cells；Outage and platform-concentration risk

必须改进：Normalize ARR and acquisition contribution；Bind module/adoption metrics to issuer evidence；Separate product coverage from financial contribution

拒绝继承：CyberArk value labeled as ARR；incorrect market cap/split adjustments；secondary-source rankings；module count as automatic retention proof

### WB-T01 - improve

语义：Pre-expectation/actual delta/one-off versus persistent/thesis revision is the strongest report-type structure；Target official operating facts are mostly aligned；Consensus expectations and price-reaction windows lack authoritative binding；Explicit data-gap surface is missing；Management statement source labels are not fully auditable

轨迹：Eleven searches but no source-open verification；TaskUpdate returned EPERM inside an ok span and later succeeded；Artifact receives syntax checks only；No post-write source or expectation reconciliation

可保留候选：Earnings event delta pack；Before-versus-after thesis table；Management explanation versus actuals；Monitoring panel with next catalyst

必须改进：Bind consensus vendor/as-of and reaction window；Separate GAAP/adjusted and one-time items；Always emit explicit gaps and unresolved expectation data

拒绝继承：consensus values without source/as-of；management quote labels without exact reference；forecast changes without executable model

### WB-T02 - reject_as_reference

语义：Facts versus assumptions and implied-expectation framing are useful；Mounjaro USD86.6B annualized is a material scale error versus official quarterly revenue around USD8.7B；Reverse-DCF sensitivity is not linked to an executable cash-flow model；Crowding claims rely on unavailable data while still influencing conclusions；Valuation outputs are not reproducible

轨迹：Only one WebSearch plus opaque finance queries；Memory Edit error is operationally repaired but research defects are not；No valuation calculation tool or formula trace；No post-write numerical audit

可保留候选：Facts-versus-assumptions table concept；Implied-expectation question；Fundamental-correct but return-limited scenario

必须改进：Move all valuation math to deterministic engine；Require share count/currency/period/unit binding；Treat crowding as commercial gap when data absent

拒绝继承：all current valuation outputs；reverse DCF without NumericProgramTrace；revenue annualization values；crowding heatmap without position data

### WB-T03 - redesign

语义：Policy authority ladder and transmission through footprint/sourcing/pricing/mix/capex is strong；GM market cap is about 10x overstated；Many current policy dates/rates and EPS sensitivities require official legal verification；Public statements are usefully separated from formal policy but evidence grades are not enforced；Explicit data-gap surface is missing

轨迹：Thirteen searches with no source-open verification despite legal/policy sensitivity；Single task and no specialist/legal handoff；No scenario or EPS calculation trace；No post-write authority reconciliation

可保留候选：Policy authority ladder；Policy transmission graph；Statement-versus-law conflict panel；Company exposure by footprint/sourcing/product mix

必须改进：Official law/regulation first with effective-date and jurisdiction binding；Separate enacted/proposed/litigated/statement states；Use deterministic tariff/EPS bridge

拒绝继承：current policy facts based on search snippets；market cap rows；untraceable EPS sensitivity；probability-free scenario rankings

### WB-T04 - improve

语义：Hypothesis tree/support-versus-counterevidence/falsifier structure is the strongest counter-thesis pattern；Evidence quality labels are useful but not backed by claim lineage；Zero primary links and material valuation/category errors remain；Same-prompt source-domain Jaccard around 4.4% shows weak research reproducibility；Counterevidence sometimes relies on low-authority opinion

轨迹：Fourteen searches and no source-open verification；No source-independence or contradiction tool；No semantic repair after artifact creation；Repeated run changes source universe materially

可保留候选：Counter-thesis hypothesis tree；Support/counterevidence matrix；Falsifier and unavailable-data panel；Source independence requirement

必须改进：Require primary evidence for factual branches；Separate disproof from uncertainty；Add same-prompt material-claim repeatability gate

拒绝继承：current valuation/downside tables；evidence grades without lineage；opinion articles as disproof；structure stability as research stability

## Pack 候选

### universal_research_responsibility_skeleton_v0_1 - retain_with_independent_evidence

层级：`universal`；Owner：`TECH_01`；来源 cases：WB-S01, WB-S02, WB-S03, WB-S04, WB-S05, WB-S06, WB-S07, WB-S08, WB-T01, WB-T02, WB-T03, WB-T04。

计划内容：user judgment question；business mechanism；financial capture；price-in；counterevidence；what-would-change；gap disclosure

进入 pack 前：keep responsibilities rather than fixed headings；bind every cell to owner/evidence/stop rule

禁止继承：WorkBuddy headings；company rankings；report facts

### mechanism_to_financial_capture_archetype_v0_1 - retain_with_independent_evidence

层级：`universal`；Owner：`TECH_01_TECH_05`；来源 cases：WB-S01, WB-S02, WB-S03, WB-S04, WB-S05, WB-S06, WB-S07, WB-S08。

计划内容：operating signal；conversion mechanism；recognized financial outcome；cash/capital consequence；failure point

进入 pack 前：sector-specific metric ontology；evidence slot and numeric trace per edge

禁止继承：generic narrative arrows without evidence；proxy treated as revenue

### active_what_would_change_program_v0_1 - redesign_then_pack

层级：`universal`；Owner：`TECH_05_TECH_11`；来源 cases：WB-S03, WB-S05, WB-S06, WB-S08, WB-T01, WB-T02, WB-T03, WB-T04。

计划内容：hypothesis；threshold；current value；direction；evidence route；last checked；owner；action on breach

进入 pack 前：replace prose wish-list with executable monitor；keep outside main conclusion until triggered

禁止继承：unquantified trigger；unsupported probability

### counterevidence_falsification_program_v0_1 - retain_with_independent_evidence

层级：`universal`；Owner：`TECH_05`；来源 cases：WB-S02, WB-S03, WB-S05, WB-S06, WB-S07, WB-S08, WB-T04。

计划内容：main hypothesis；supporting evidence；counterevidence；source independence；disproof threshold；unresolved uncertainty

进入 pack 前：distinguish disproof from weak evidence；claim-local provenance and authority gate

禁止继承：secondary opinion as factual disproof；evidence grade without lineage

### gap_boundary_program_v0_1 - redesign_then_pack

层级：`universal`；Owner：`TECH_01_TECH_02`；来源 cases：WB-S01, WB-S02, WB-S03, WB-S04, WB-S05, WB-S06, WB-S07, WB-S08, WB-T02, WB-T04。

计划内容：typed gap；commercial gap；forbidden substitution；attempt history；impact on judgment；next action

进入 pack 前：do not infer source absence from retrieval failure；require explicit surface in every report type

禁止继承：generic data unavailable note；gap contradicted by official disclosure

### peer_comparison_report_type_pack_v0_1 - retain_with_independent_evidence

层级：`report_type`；Owner：`TECH_01`；来源 cases：WB-S01, WB-S02, WB-S03, WB-S04, WB-S05, WB-S06, WB-S07, WB-S08。

计划内容：shared mechanism rows；normalized peer metrics；company-specific deltas；comparability exceptions；relative price-in and counterevidence

进入 pack 前：same definition/period/unit；no score unless traceable rubric

禁止继承：star ratings；non-comparable metric ranking

### earnings_event_update_report_type_pack_v0_1 - redesign_then_pack

层级：`report_type`；Owner：`TECH_01_TECH_05`；来源 cases：WB-T01。

计划内容：pre-event expectation；actual versus consensus delta；one-off versus persistent driver；management explanation versus actuals；before/after thesis；reaction window；next monitor

进入 pack 前：bind consensus source/as-of；GAAP/non-GAAP reconciliation；explicit gap section

禁止继承：unsourced consensus；forecast rewrite without model

### valuation_price_in_report_type_pack_v0_1 - redesign_then_pack

层级：`report_type`；Owner：`TECH_01_TECH_04`；来源 cases：WB-T02, WB-S01, WB-S03, WB-S04, WB-S05, WB-S06, WB-S07, WB-S08。

计划内容：facts versus assumptions；implied expectations；scenario/sensitivity；multiple normalization；fundamental-right return-limited conditions；commercial positioning gap

进入 pack 前：deterministic valuation engine；share-count/currency/unit/period trace；market-data freshness

禁止继承：all WorkBuddy valuation outputs；reverse DCF without program trace；crowding without data

### policy_shock_report_type_pack_v0_1 - redesign_then_pack

层级：`report_type`；Owner：`TECH_01_TECH_05`；来源 cases：WB-T03。

计划内容：authority ladder；enacted/proposed/litigated/statement state；effective date/jurisdiction；transmission graph；company exposure；scenario and falsifier

进入 pack 前：official legal source first；deterministic exposure bridge；conflict between statement and fact

禁止继承：search snippet as law；public figure statement as fact；untraceable EPS impact

### counter_thesis_report_type_pack_v0_1 - redesign_then_pack

层级：`report_type`；Owner：`TECH_01_TECH_05`；来源 cases：WB-T04。

计划内容：hypothesis tree；support/counter matrix；source independence；falsifiers；data boundaries；residual uncertainty

进入 pack 前：primary-first factual branches；repeatability and contradiction gate

禁止继承：current cyber claims/valuation；opinion as disproof

### saas_ai_sector_pack_v0_1 - redesign_then_pack

层级：`sector`；Owner：`TECH_05`；来源 cases：WB-S01。

计划内容：adoption to ARR/RPO/revenue；seat versus consumption pricing；NRR/GRR；gross margin/inference cost；sales efficiency/SBC/FCF；platform competition

进入 pack 前：metric definition normalization；reported AI revenue versus proxy

禁止继承：current values and company scores

### banks_sector_pack_v0_1 - redesign_then_pack

层级：`sector`；Owner：`TECH_05`；来源 cases：WB-S02。

计划内容：deposit franchise/funding cost；NIM/NII sensitivity；loan growth/mix；credit cost/reserves；CET1/capital return；fee income

进入 pack 前：regulatory status freshness；bank metric/period ontology

禁止继承：stale WFC asset-cap thesis；current rankings

### healthcare_pharma_sector_pack_v0_1 - redesign_then_pack

层级：`sector`；Owner：`TECH_05`；来源 cases：WB-S03, WB-T02。

计划内容：clinical endpoint；approval/label；access/reimbursement；capacity/supply；prescription to revenue；R&D/capex/margin；LOE/pipeline

进入 pack 前：trial/regulatory primary binding；currency/product normalization

禁止继承：current estimates and valuation outputs

### retail_consumer_sector_pack_v0_1 - redesign_then_pack

层级：`sector`；Owner：`TECH_05`；来源 cases：WB-S04, WB-T01。

计划内容：traffic/ticket/price/mix/new stores；comparable versus total sales；inventory/promotion/gross margin；ads/membership/marketplace；working capital/FCF

进入 pack 前：issuer-first disclosure selector；shared fact contradiction gate

禁止继承：S04 Target disclosure claims；star ratings

### energy_sector_pack_v0_1 - redesign_then_pack

层级：`sector`；Owner：`TECH_05_TECH_04`；来源 cases：WB-S05。

计划内容：production/volume；realized price/differential/hedge；unit cost；sustaining/growth capex；reserve/project quality；FCF/dividend/buyback；integrated cycle offset

进入 pack 前：filing facts and executable commodity scenarios

禁止继承：all current market cap/scenario tables

### utilities_power_sector_pack_v0_1 - redesign_then_pack

层级：`sector`；Owner：`TECH_05`；来源 cases：WB-S06。

计划内容：load stage；interconnection/approval；capex to rate base；allowed ROE；EPS/cash/debt/equity；regulated versus merchant；equipment/fuel bottleneck

进入 pack 前：docket/jurisdiction binding；signed versus speculative load separation

禁止继承：interest pipeline as committed load；current valuation outputs

### industrials_sector_pack_v0_1 - redesign_then_pack

层级：`sector`；Owner：`TECH_05`；来源 cases：WB-S07。

计划内容：orders/book-to-bill；backlog quality/cancellation；delivery/price-cost；dealer/customer inventory；aftermarket；working capital/FCF

进入 pack 前：reported versus inferred flags；backlog conversion model

禁止继承：current market cap/targets/cycle scores

### cybersecurity_sector_pack_v0_1 - redesign_then_pack

层级：`sector`；Owner：`TECH_05`；来源 cases：WB-S08, WB-T04。

计划内容：module/platform adoption；organic/acquired ARR；retention/expansion；sales efficiency/SBC/GAAP/FCF；outage/platform concentration；bundling competition

进入 pack 前：ARR/category normalization；issuer-primary evidence；source-independent counterevidence

禁止继承：CyberArk/CRWD metrics；current valuation tables

### auto_policy_transmission_sector_delta_v0_1 - redesign_then_pack

层级：`sector_delta`；Owner：`TECH_05`；来源 cases：WB-T03。

计划内容：manufacturing footprint；parts/battery origin；tariff eligibility；pricing pass-through；product mix；localization capex

进入 pack 前：official tariff/legal state；company filing exposure；deterministic cost bridge

禁止继承：current policy and EPS numbers

### decision_surface_presentation_pack_v0_1 - redesign_then_pack

层级：`presentation`；Owner：`TECH_09`；来源 cases：WB-S01, WB-S02, WB-S03, WB-S04, WB-S05, WB-S06, WB-S07, WB-S08, WB-T01, WB-T02, WB-T03, WB-T04。

计划内容：answer-first summary；decision matrix；mechanism table；scenario panel；counterevidence panel；WWC monitor；source/gap panel

进入 pack 前：claim-local citations；artifact consistency graph；responsive/accessible charts；no nested unsupported dashboard numbers

禁止继承：current HTML facts；detached bibliography as provenance

## 全局拒绝模式

- Search-result snippets treated as accepted evidence without opening the source.
- Detached source bibliography used as a substitute for claim-level lineage.
- Verified/official labels without Evidence Gate promotion.
- Market cap, product revenue, acquisition value, unit, period or currency values without numeric sanity checks.
- Reverse DCF, target price, scenario probability or EPS sensitivity without executable NumericProgramTrace.
- Star scores, letter grades and ordinal company rankings without a versioned rubric and comparable inputs.
- Management/public-figure statements treated as facts when they conflict with formal evidence.
- TaskCreate/TaskUpdate lists represented as subagent collaboration or independent context.
- Artifact syntax success represented as semantic, numeric, citation or trajectory success.
- A completed HTML represented as a healthy trajectory when terminal or hidden tool errors exist.
- Same-prompt structural similarity represented as research reproducibility.
- Any WorkBuddy report fact, valuation or ranking copied into FIN runtime evidence or pack fixtures.

## 边界

本复审不是 FIN runtime pass、pack promotion、paid model run 或 full-chain。Pack candidates 只表示拟实现内容；必须经过 FIN schema、deterministic fixture、独立 rubric、Evidence/Numeric Gate 和 M3 shadow comparison。
