import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";

export type WorkbenchLocale = "zh-CN" | "en";

type WorkbenchLocaleValue = {
  locale: WorkbenchLocale;
  setLocale: (locale: WorkbenchLocale) => void;
  copy: (zhCN: string, en: string) => string;
  formatDateTime: (value: string) => string;
  labelToken: (value: string) => string;
  localizeFixtureText: (value: string) => string;
};

const STORAGE_KEY = "finsight-workbench-locale";

const TOKEN_LABELS: Record<string, [string, string]> = {
  accepted: ["已确认", "Accepted"],
  accept_fixture_preview: ["已确认演示结论", "Fixture outcome accepted"],
  admit_fixture_writer_preview: ["可生成演示结论", "Fixture writing admitted"],
  cancelled: ["已取消", "Cancelled"],
  candidate: ["候选证据", "Candidate"],
  completed: ["已完成", "Completed"],
  context_only: ["仅作背景", "Context only"],
  created: ["已创建", "Created"],
  demand_signal: ["需求真实性", "Demand signal"],
  revenue_capture: ["价值与利润捕获", "Revenue capture"],
  thesis_counterevidence: ["反证与结论边界", "Thesis counterevidence"],
  server_oem_orders: ["服务器厂商订单", "Server OEM orders"],
  server_oem_margin_cash: ["服务器厂商利润与现金", "Server OEM margin and cash"],
  advanced_packaging_capacity: ["先进封装产能", "Advanced packaging capacity"],
  hbm_supply_pricing: ["HBM 供给与定价", "HBM supply and pricing"],
  semicap_capex_cycle: ["半导体设备资本开支周期", "Semicap capex cycle"],
  export_policy_risk: ["出口政策风险", "Export policy risk"],
  customer_concentration: ["客户集中度", "Customer concentration"],
  fixture_internal: ["内部演示", "Internal fixture"],
  financial_analyst: ["财务分析师", "Financial analyst"],
  high: ["高", "High"],
  industry_analyst: ["行业分析师", "Industry analyst"],
  legacy_authority_retained: ["沿用既有权限", "Legacy authority retained"],
  low: ["低", "Low"],
  material_claim: ["核心结论", "Material claim"],
  medium: ["中", "Medium"],
  not_compiled: ["尚未生成", "Not compiled"],
  not_prepared: ["尚未准备", "Not prepared"],
  optional: ["可选证据", "Optional evidence"],
  pending: ["待处理", "Pending"],
  queued: ["排队中", "Queued"],
  rejected: ["已排除", "Rejected"],
  repair_completed: ["已完成来源补充", "Source repair completed"],
  repair_requested: ["已请求来源补充", "Source repair requested"],
  required: ["必需证据", "Required evidence"],
  retrieval_exhausted: ["当前来源未覆盖", "Source route exhausted"],
  risk_reviewer: ["风险复核员", "Risk reviewer"],
  return_for_repair: ["退回补充证据", "Returned for evidence repair"],
  returned: ["已退回", "Returned"],
  running: ["进行中", "Running"],
  shadow_created: ["研究已创建", "Research created"],
  supply_chain_analyst: ["供应链分析师", "Supply-chain analyst"],
  metadata_fixture_compiled: ["演示候选已整理", "Fixture candidates prepared"],
  exact_local_facts_computed: ["本地精确事实已复算", "Exact local facts computed"],
  internal_draft_awaiting_senior_r2: ["内部底稿待 Senior R2", "Internal draft awaiting senior R2"],
  candidate_preview_ready: ["候选预览已准备", "Candidate preview ready"],
  internal_analysis_preview_ready: ["内部分析预览已准备", "Internal analysis preview ready"],
  not_reviewed: ["尚未复核", "Not reviewed"],
  object_bm25: ["披露原文检索", "Disclosure retrieval"],
  gold_fact_sql: ["精确事实库", "Exact fact store"],
  research_graph: ["研究关系图", "Research graph"],
  typed_gap: ["来源缺口", "Source gap"],
};

// The P36 fixture is canonical English data. These replacements provide a
// read-only Chinese presentation without changing its artifact or digest.
const P36_FIXTURE_ZH_CN: Record<string, string> = {
  "<html lang=\"en\">": "<html lang=\"zh-CN\">",
  "Assess P36 AI infrastructure demand, value capture, bottlenecks, concentration, and counterevidence": "评估 P36 AI 基础设施需求能否转化为可持续的收入与利润，并识别价值捕获、瓶颈、集中度和反证",
  "Assess whether P36 AI infrastructure demand converts into durable revenue and profit capture, including bottlenecks and counterevidence.": "评估 P36 AI 基础设施需求能否转化为可持续的收入与利润，包括瓶颈和反证。",
  "P36 ten-cell fixture candidate profile": "P36 十单元内部演示研究",
  "NVIDIA data-center demand and revenue conversion": "NVIDIA 数据中心需求与收入转化",
  "Microsoft AI infrastructure capex context": "Microsoft AI 基础设施资本开支背景",
  "NVIDIA segment revenue candidate": "NVIDIA 分部收入候选证据",
  "TSMC advanced-packaging capacity context": "TSMC 先进封装产能背景",
  "Advanced-computing export-control counterevidence": "先进计算出口管制反证",
  "Server OEM orders structural fixture candidate": "服务器 OEM 订单结构化演示候选",
  "Server OEM margin and cash structural fixture candidate": "服务器 OEM 利润率与现金结构化演示候选",
  "Advanced packaging capacity structural fixture candidate": "先进封装产能结构化演示候选",
  "HBM supply and pricing structural fixture candidate": "HBM 供给与定价结构化演示候选",
  "Semicap capex and cycle structural fixture candidate": "半导体设备资本开支与周期结构化演示候选",
  "Export policy risk structural fixture candidate": "出口政策风险结构化演示候选",
  "Customer concentration structural fixture candidate": "客户集中度结构化演示候选",
  "No usable candidate": "无可用候选证据",
  "The bounded fixture route returned no candidate for this required evidence role.": "当前受限演示来源未返回满足此必需证据角色的候选项。",
  "Candidate metadata only; not a promoted fact and not current live filing content.": "仅为候选元数据；尚未提升为事实，也不是当前实时披露内容。",
  "Issuer-reported data-center growth and management discussion provide a bounded starting point for demand durability and recognized revenue.": "发行人披露的数据中心增长与管理层讨论，为分析需求持续性和已确认收入提供受限起点。",
  "Fixture structural slot only": "仅为演示结构槽",
  "Fixture-only candidate; promotion boundary is not in this contract.": "仅为演示候选；本合同不包含证据晋升。",
  "Accepted for internal fixture dogfood only; ten claims and explicit gaps are readable, with no sector-validity or release claim.": "仅接受用于内部演示试用；十项结论与明确缺口可阅读，不构成行业有效性或发布声明。",
  "Can the fixture profile preserve the demand-reality question for AI infrastructure demand and revenue conversion without making a live demand claim?": "在不声称真实需求结论的前提下，演示研究能否保留 AI 基础设施需求真实性及收入转化问题？",
  "Can the fixture profile preserve the value-and-profit-capture comparison without asserting an issuer, segment, or supply-chain outcome?": "在不声称公司、分部或供应链结果的前提下，演示研究能否保留价值与利润捕获比较？",
  "Can the fixture profile preserve an independent counterevidence question without claiming that a bottleneck or risk exists?": "在不声称瓶颈或风险真实存在的前提下，演示研究能否保留独立反证问题？",
  "Does the fixture profile structurally distinguish server OEM order signals from revenue conversion without asserting either outcome?": "演示研究能否在不声称任何结果的前提下，区分服务器 OEM 订单信号与收入转化？",
  "Does the fixture profile structurally separate server OEM margin and cash conversion questions without asserting profitability or cash facts?": "演示研究能否在不声称利润率或现金事实的前提下，区分服务器 OEM 利润率与现金转化问题？",
  "Does the fixture profile preserve an advanced-packaging capacity, bottleneck, and rent question without asserting supply or economics?": "演示研究能否在不声称供给或经济性结论的前提下，保留先进封装产能、瓶颈与超额收益问题？",
  "Does the fixture profile structurally cover HBM demand, supply, pricing, and concentration without asserting market conditions?": "演示研究能否在不声称市场状况的前提下，覆盖 HBM 需求、供给、定价与集中度？",
  "Does the fixture profile structurally separate semicap capex, cycle, and export readthrough questions without asserting a cycle position?": "演示研究能否在不判断周期位置的前提下，区分半导体设备资本开支、周期与出口传导问题？",
  "Does the fixture profile create a typed export-policy risk counterevidence slot without representing any policy as current or applicable?": "演示研究能否在不把任何政策视为当前有效或适用的前提下，建立结构化出口政策风险反证槽？",
  "Does the fixture profile retain a customer concentration and price-in question without assigning exposure, ranking, or valuation implications?": "演示研究能否在不赋予敞口、排序或估值含义的前提下，保留客户集中度与市场定价问题？",
  "AI infrastructure demand is appearing in company-reported data-center growth and customer deployment signals, but how durable is conversion?": "公司披露的数据中心增长与客户部署已出现 AI 基础设施需求信号，但这种转化能否持续？",
  "How much of the demand signal converts into reported revenue, gross profit, and operating income at the accelerator layer?": "在加速器环节，需求信号有多少转化为已披露收入、毛利润和营业利润？",
  "Which packaging, memory, equipment, working-capital, or policy constraints could falsify the simple demand-to-profit thesis?": "哪些封装、存储、设备、营运资本或政策约束可能推翻简单的需求到利润论点？",
  "Do server OEM order and backlog signals convert into reported shipments and revenue without timing distortion?": "服务器 OEM 订单和积压信号能否在不受时点扭曲的情况下转化为已披露发货与收入？",
  "Do AI server revenue signals convert into OEM margin and cash rather than inventory or working-capital pressure?": "AI 服务器收入信号能否转化为 OEM 利润率和现金，而不是库存或营运资本压力？",
  "Does advanced-packaging capacity remain a binding bottleneck, and who captures the resulting economics?": "先进封装产能是否仍是约束性瓶颈，相关经济收益由谁捕获？",
  "How tight are HBM supply, pricing, and customer concentration, and how durable is memory profit capture?": "HBM 供给、定价和客户集中度有多紧张，存储利润捕获能否持续？",
  "What does semiconductor-equipment demand imply for capex timing, cycle position, and export-policy read-through?": "半导体设备需求对资本开支时点、周期位置和出口政策传导意味着什么？",
  "Which current export restrictions could impair supply, market access, or recognized data-center revenue?": "哪些当前出口限制可能影响供给、市场准入或已确认的数据中心收入？",
  "How concentrated is recognized revenue, and what does that concentration change about durability and price-in risk?": "已确认收入的集中度有多高，这种集中度如何改变持续性和市场定价风险？",
  "Do not advance this fixture judgment when the structural demand slot is absent or is treated as a real demand observation.": "若缺少结构化需求证据槽，或该证据槽被误作真实需求观察，则不得推进此演示判断。",
  "Do not assign fixture value capture when its structural revenue slot is absent or is read as a promoted fact.": "若缺少结构化收入证据槽，或其被误作已确认事实，则不得判断价值捕获。",
  "Do not close the fixture thesis when the counterevidence slot is absent, untyped, or represented as live policy content.": "若反证槽缺失、未结构化，或被误作当前政策内容，则不得关闭演示论点。",
  "Do not infer an order or revenue result when the fixture-only server OEM order slot has no typed gap boundary.": "若服务器 OEM 订单演示槽没有结构化缺口边界，则不得推断订单或收入结果。",
  "Do not infer margin or cash conversion when the fixture-only slot is missing or its explicit gap is removed.": "若演示槽缺失或明确缺口被移除，则不得推断利润率或现金转化。",
  "Do not describe a capacity bottleneck or rent capture when only a fixture structural slot is available.": "仅有演示结构槽时，不得描述产能瓶颈或超额收益捕获。",
  "Do not infer HBM demand, supply, pricing, or concentration from a fixture candidate or its metadata address.": "不得从演示候选证据或其元数据地址推断 HBM 需求、供给、定价或集中度。",
  "Do not characterize capex, cycle, or export readthrough when only an unpromoted fixture slot is present.": "仅有未晋升的演示槽时，不得判断资本开支、周期或出口传导。",
  "Do not infer policy scope, timing, or commercial impact from a fixture policy metadata candidate.": "不得从演示政策元数据候选推断政策范围、时间或商业影响。",
  "Do not infer customer concentration, price-in, or investment implication from a fixture structural candidate.": "不得从演示结构候选推断客户集中度、市场定价或投资含义。",
  "Fixture-only structural judgment preserves the demand-signal role without a live demand conclusion.": "演示结构判断保留了需求信号角色，但不构成真实需求结论。",
  "Fixture-only structural judgment preserves the revenue-capture role without a live value-capture conclusion.": "演示结构判断保留了收入捕获角色，但不构成真实价值捕获结论。",
  "Fixture-only structural judgment preserves the counterevidence role without a live risk conclusion.": "演示结构判断保留了反证角色，但不构成真实风险结论。",
  "Structural fixture judgment only: the server OEM order role is present and makes no industry conclusion.": "仅作演示结构判断：已覆盖服务器 OEM 订单角色，不构成行业结论。",
  "Structural fixture judgment only: the server OEM margin-and-cash role is present and makes no industry conclusion.": "仅作演示结构判断：已覆盖服务器 OEM 利润率与现金角色，不构成行业结论。",
  "Structural fixture judgment only: the advanced-packaging role is present and makes no capacity or rent conclusion.": "仅作演示结构判断：已覆盖先进封装角色，不构成产能或超额收益结论。",
  "Structural fixture judgment only: the HBM supply-and-pricing role is present and makes no market conclusion.": "仅作演示结构判断：已覆盖 HBM 供给与定价角色，不构成市场结论。",
  "Structural fixture judgment only: the semicap capex-and-cycle role is present and makes no cycle conclusion.": "仅作演示结构判断：已覆盖半导体设备资本开支与周期角色，不构成周期结论。",
  "Structural fixture judgment only: the export-policy-risk role is present and makes no policy applicability conclusion.": "仅作演示结构判断：已覆盖出口政策风险角色，不构成政策适用性结论。",
  "Structural fixture judgment only: the customer-concentration role is present and makes no exposure or price-in conclusion.": "仅作演示结构判断：已覆盖客户集中度角色，不构成敞口或市场定价结论。",
  "P36 ten-cell fixture provides structural coverage only and does not state sector research conclusions.": "P36 十单元演示仅提供结构覆盖，不陈述行业研究结论。",
  "Executive answer": "核心回答",
  "Demand Signal": "需求真实性",
  "Revenue Capture": "价值与利润捕获",
  "Thesis Counterevidence": "论点反证",
  "Server Oem Orders": "服务器 OEM 订单",
  "Server Oem Margin Cash": "服务器 OEM 利润率与现金",
  "Advanced Packaging Capacity": "先进封装产能",
  "Hbm Supply Pricing": "HBM 供给与定价",
  "Semicap Capex Cycle": "半导体设备资本开支周期",
  "Export Policy Risk": "出口政策风险",
  "Customer Concentration": "客户集中度",
  "What would change": "什么会改变判断",
  "Remaining gaps": "剩余证据缺口",
  "Durability still requires subsequent-period confirmation.": "持续性仍需后续期间披露确认。",
  "Segment attribution is not inferred beyond the reported company facts.": "不得超出公司披露事实推断分部归因。",
  "Relationships do not prove causal bottlenecks; senior review must retain this gap.": "关系本身不能证明因果性瓶颈，Senior R2 必须保留该边界。",
  "The candidate set does not establish an exact AI-server order or backlog value.": "当前候选证据不能建立精确的 AI 服务器订单或积压金额。",
  "AI-server-specific margin, inventory, and cash conversion remain unseparated.": "AI 服务器特定的利润率、库存和现金转化尚未单独拆分。",
  "The evidence does not isolate CoWoS capacity or prove bottleneck rent capture.": "当前证据未单独识别 CoWoS 产能，也不能证明瓶颈超额收益。",
  "Exact HBM pricing and customer concentration are not established.": "精确 HBM 定价和客户集中度尚未建立。",
  "The current candidate set does not establish the present cycle position.": "当前候选证据不能确定现阶段设备周期位置。",
  "Policy applicability and quantified commercial impact require official-policy review.": "政策适用性和量化商业影响仍需官方政策复核。",
  "Direct-customer concentration cannot be treated as end-customer concentration.": "直接客户集中度不能等同于终端客户集中度。",
  "Internal deterministic analysis over real local candidates. The draft is not evidence promotion, senior R2 approval, operational qualification, or FIN 0.1 release admission.": "基于真实本地候选证据的内部确定性分析；该底稿不代表证据晋升、Senior R2 批准、运行资格或 FIN 0.1 发布准入。",
  "Artifact version": "交付物版本",
  "Canonical presentation digest": "标准呈现摘要",
};

const WorkbenchLocaleContext = createContext<WorkbenchLocaleValue | null>(null);

export function WorkbenchLocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<WorkbenchLocale>(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved === "en" || saved === "zh-CN" ? saved : "zh-CN";
  });

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const value = useMemo<WorkbenchLocaleValue>(() => ({
    locale,
    setLocale(nextLocale) {
      window.localStorage.setItem(STORAGE_KEY, nextLocale);
      document.documentElement.lang = nextLocale;
      setLocaleState(nextLocale);
    },
    copy: (zhCN, en) => locale === "zh-CN" ? zhCN : en,
    formatDateTime(value) {
      const parsed = new Date(value);
      return Number.isNaN(parsed.valueOf())
        ? value
        : parsed.toLocaleString(locale === "zh-CN" ? "zh-CN" : "en-US", {
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
        });
    },
    labelToken(value) {
      const normalized = value.trim().toLowerCase();
      const known = TOKEN_LABELS[normalized];
      if (known) return locale === "zh-CN" ? known[0] : known[1];
      const label = value.trim().replace(/[._-]+/g, " ");
      return label || (locale === "zh-CN" ? "暂无" : "Unavailable");
    },
    localizeFixtureText(value) {
      if (locale !== "zh-CN") return value;
      return Object.entries(P36_FIXTURE_ZH_CN).reduce(
        (localized, [source, translated]) => localized.replaceAll(source, translated),
        value,
      );
    },
  }), [locale]);

  return <WorkbenchLocaleContext.Provider value={value}>{children}</WorkbenchLocaleContext.Provider>;
}

export function useWorkbenchLocale(): WorkbenchLocaleValue {
  const value = useContext(WorkbenchLocaleContext);
  if (!value) throw new Error("WorkbenchLocaleProvider is required");
  return value;
}
