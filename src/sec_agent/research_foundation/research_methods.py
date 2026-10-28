"""Small, answer-free method resources exposed through the existing MCP server.

This module selects packaged documents. It does not dispatch agents, grant tool
permissions, maintain a registry database, or read caller-supplied file paths.
"""
from importlib.resources import files
from hashlib import sha256
import re


METHODS = {
    "report_processing": ("新报告定位、提取与更新", "先查已有结构化记录，按原页表头与附注调整提取方案，校验口径并交接更新；区分读取与入库权限。"),
    "research_orientation": ("总题初步研究与首批专题", "按实际资料形成初步判断和证据触发的派工依据，在专题执行前停止。"),
    "research_loop": ("从问题到解释", "增长来源、信息价值与观察后的认识更新。"),
    "scenario_sensitivity": ("情景与关键变量", "驱动模型、变量联动、敏感性及盈亏阈值。"),
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
    "counter": ("竞争解释与因果辨识", "需求与库存、结构变化、竞争解释及判别信息。"),
    "writer": ("投研底稿与报告写作", "回答研究问题，解释经营机制与意义；关键依据、可读论证和局部修订。"),
    "verifier": ("研究与报告复核", "来源上下文、关键核算、因果与重要分析遗漏。"),
}

REPORT_PROCESSING_TOOL_GUIDANCE = (
    " For report extraction or changed table layout, report_processing explains locating "
    "relevant sections through get_research_method. "
    "then read original context including headers, units and footnotes. Reuse verified "
    "structured facts and exact source IDs; previews are not extraction input. "
    "Follow returned child node IDs and context_readbacks for bounded source text; "
    "parent_locator_bound is a broader evidence location, not an exact quotation. "
    "A missing vector index is an execution failure, not missing disclosure. "
    "Read tools do not ingest, execute parsing scripts or publish database updates."
)

FIRST_METHODS = ("research_loop", "counter", "scenario_sensitivity", "writer",
                 "finance", "cloud_infrastructure", "macro_valuation")


def _resource(method_id):
    return files("sec_agent.research_foundation").joinpath("methods", method_id + ".md").read_text(encoding="utf-8")


# One maintained instruction body, shared by conversation, authors and reviewers.
BASIC_RESEARCH_GUIDANCE = "\n" + _resource("agent_guidance").strip() + "\n"
METHOD_TOOL_GUIDANCE = (
    "\n可选研究方法（不是必经步骤或额外权限）：\n"
    + "\n".join(f"{key}：{METHODS[key][0]}；{METHODS[key][1]}" for key in FIRST_METHODS)
    + "\n通过当前接口的 get_research_method 或 request_method 按需读取。"
    "空method_id返回目录；选method_id读全文，section可选返回目录中准确的章节标题。"
    "方法是教学资源而非本案证据；已加载内容可直接使用，所需章节退出后可按同一入口回读。\n"
)


def select_method_section(method: dict, section: str = "") -> dict:
    """Select an exact H2 from a packaged or host-frozen method; no path access."""
    if not section:
        return method
    content = method.get("content", "")
    blocks = re.split(r"(?m)(?=^## )", content)
    chapters = {b.splitlines()[0][3:].strip(): b for b in blocks if b.startswith("## ")}
    if section not in chapters:
        raise ValueError("unknown_method_section: choose an exact section title from this method")
    selected = blocks[0] + chapters[section]
    return {**method, "content": selected, "selection": section,
            "resource_digest": sha256(content.encode()).hexdigest(),
            "content_digest": sha256(selected.encode()).hexdigest()}


def get_research_method(method_id: str = "", section: str = "") -> dict:
    """Return the catalog or one packaged method; never a local path."""
    if not method_id:
        if section:
            raise ValueError("method_id_required_for_section")
        return {"version": 2, "answer_free": True, "methods": [
            {"method_id": key, "title": title, "summary": summary,
             "sections": get_research_method(key)["sections"]}
            for key, (title, summary) in METHODS.items()
        ]}
    if method_id not in METHODS:
        raise ValueError("unknown_research_method: select an ID from get_research_method()")
    title, summary = METHODS[method_id]
    if method_id == "financial_quality":
        # Preserve the historical method/step IDs, with one source for teaching.
        content = select_method_section(get_research_method("finance"), "财务质量与日期桥接")["content"]
        content += "\n兼容旧任务章节引用（非执行顺序）：步骤 F1：断言；步骤 F2：可比性；步骤 F3：归因；步骤 F4：金额桥；步骤 F5：现金；步骤 F6：更新。\n"
    else:
        content = _resource(method_id)
    revision = re.search(r"版本：(\d+)", content)
    result = {"version": 2, "method_id": method_id, "title": title, "summary": summary,
              "content": content, "answer_free": True, "grants_authority": False,
              "content_version": int(revision.group(1)) if revision else None,
              "resource_digest": sha256(content.encode()).hexdigest(),
              "sections": re.findall(r"(?m)^## (.+)$", content),
              "readback": {"tool": "get_research_method", "arguments": {"method_id": method_id}}}
    return select_method_section(result, section)


def research_writing_guidance(stage: str) -> str:
    """Project the relevant brief from the same packaged method as the tool.

    Examples and handoff details remain available on demand. This changes
    guidance, never task scope, tool rights or submission checks.
    """
    headings = {"workpaper": "专题底稿行文", "report": "综合报告行文"}
    if stage not in headings:
        raise ValueError("unknown_research_writing_stage")
    content = get_research_method("writer")["content"]
    sections = {}
    for block in content.split("\n## ")[1:]:
        title, _, body = block.partition("\n")
        sections[title.strip()] = body.strip()
    return "\n\n".join(sections[title] for title in (headings[stage], "共同写作原则"))
