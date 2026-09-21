"""Small, answer-free method resources exposed through the existing MCP server.

This module selects packaged documents. It does not dispatch agents, grant tool
permissions, maintain a registry database, or read caller-supplied file paths.
"""
from importlib.resources import files


METHODS = {
    "report_processing": ("新报告定位、提取与更新", "先查已有结构化记录，按原页表头与附注调整提取方案，校验口径并交接更新；区分读取与入库权限。"),
    "research_orientation": ("总题初步研究与首批专题", "按实际资料形成初步判断和证据触发的派工依据，在专题执行前停止。"),
    "research_loop": ("研究问题与动态回环", "从总题生成研究义务，依据新观察展开或收口。"),
    "semiconductor_systems": ("半导体与算力系统竞争", "同任务规格、软件生态、采购采用与财务兑现。"),
    "model_compute_demand": ("模型效率与算力需求", "同质量任务、训练推理边界、效率与使用量情景。"),
    "manufacturing_capacity": ("制造、封装与内存供给", "工序瓶颈、有效产能、库存及资本周期。"),
    "cloud_infrastructure": ("云与算力租赁经济性", "使用、合同、容量与利润现金的连接。"),
    "software_platforms": ("模型、软件与互联网商业模式", "按收费模式分析采用、变现和服务成本。"),
    "power_projects": ("电力、机房与项目兑现", "按有效许可、合同、建设和现金期限研究。"),
    "financing_ownership": ("融资与机构持仓", "数量、市值、资本承诺和风险传导分开。"),
    "financial_quality": ("经营、利润与现金质量核查", "按交易和三表定位异常，不靠概念口号。"),
    "macro_valuation": ("宏观传导与市场隐含要求", "历史版本、业务暴露、反向估值及敏感性。"),
    "lead": ("研究任务规划", "拆题、选择专家与依赖、根据结果补研究。"),
    "finance": ("增长、盈利与现金兑现", "可比口径、分部与产品边界、三表关联及来源绑定计算。"),
    "industry_product": ("行业与产品传导", "需求、客户、架构、供货、竞争与财务影响。"),
    "public_observations": ("公开调查、新闻转述与研究线索", "原始证据链、题目分母、抽样范围、转述核对和可检验的商业假设。"),
    "survey_analysis": ("问卷与调查结果分析", "专门处理调查设计、统计口径、可比变化与有条件的联合推断；不承担商业综合。"),
    "counter": ("反证与替代解释", "检验主要判断、最强反证及可观察的改变判断条件。"),
    "writer": ("综合研究与可读交付", "判断驱动写作、必要图表、自由正文与局部修订。"),
    "verifier": ("研究与报告复核", "来源上下文、关键核算、因果与重要分析遗漏。"),
}

REPORT_PROCESSING_TOOL_GUIDANCE = (
    " For a new/revised report, missing extraction or changed table layout, first call "
    "get_research_method(method_id='report_processing'). Locate relevant sections, "
    "then read original context including headers, units and footnotes. Reuse verified "
    "structured facts and exact source IDs; previews are not extraction input. "
    "Read tools do not ingest, execute parsing scripts or publish database updates."
)

METHOD_TOOL_GUIDANCE = (
    "\nAnswer-free role methods are available through get_research_method. "
    "Call with no method_id for the compact catalog, then select relevant method IDs "
    "to read their content when needed. Methods are guidance, not case evidence, "
    "prewritten conclusions or extra permissions. Use the actual user question; "
    "prior workpapers and review opinions can be wrong. "
    "For a source/authority correction, check the affected source and relevant method, "
    "not just the old qualifier. Not separately disclosed does not mean not achieved; "
    "management saying a target was met is not an independently reported numeric result. "
    "Keep speaker, date and metric basis distinct across sources; similar wording alone "
    "does not prove comparability. Flag a linked error in supposedly correct reference "
    "text instead of propagating it for consistency."
    " Before the first substantive financial judgment, load the relevant role method "
    "unless its full content is already in this run's context. Apply it to the actual "
    "question; do not merely mention that it was read. Prefer catalog financial "
    "metrics to hand-entered formulas, and reuse their exact NumericFact IDs. "
    "Publish a concise evidence-to-conclusion explanation, alternatives and missing "
    "checks; this is an analysis rationale, not a request to reveal private reasoning."
) + REPORT_PROCESSING_TOOL_GUIDANCE


def get_research_method(method_id: str = "") -> dict:
    """Return the catalog or one packaged method; never a local path."""
    if not method_id:
        return {"version": 2, "answer_free": True, "methods": [
            {"method_id": key, "title": title, "summary": summary}
            for key, (title, summary) in METHODS.items()
        ]}
    if method_id not in METHODS:
        raise ValueError("unknown_research_method: select an ID from get_research_method()")
    title, summary = METHODS[method_id]
    content = files("sec_agent.research_foundation").joinpath("methods", method_id + ".md").read_text(encoding="utf-8")
    return {"version": 2, "method_id": method_id, "title": title, "summary": summary,
            "content": content, "answer_free": True, "grants_authority": False}
