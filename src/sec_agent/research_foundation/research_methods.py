"""Small, answer-free method resources exposed through the existing MCP server.

This module selects packaged documents. It does not dispatch agents, grant tool
permissions, maintain a registry database, or read caller-supplied file paths.
"""
from importlib.resources import files


METHODS = {
    "lead": ("研究任务规划", "拆题、选择专家与依赖、根据结果补研究。"),
    "finance": ("增长、盈利与现金兑现", "可比口径、三表关联、目标完成要求与来源绑定计算。"),
    "industry_product": ("行业与产品传导", "需求、客户、架构、供货、竞争与财务影响。"),
    "counter": ("反证与替代解释", "检验主要判断、最强反证及可观察的改变判断条件。"),
    "writer": ("综合研究与可读交付", "判断驱动写作、必要图表、自由正文与局部修订。"),
    "verifier": ("研究与报告复核", "来源上下文、关键核算、因果与重要分析遗漏。"),
}

METHOD_TOOL_GUIDANCE = (
    "\nAnswer-free role methods are available through get_research_method. "
    "Call with no method_id for the compact catalog, then select relevant method IDs "
    "to read their content when needed. Methods are guidance, not case evidence, "
    "prewritten conclusions or extra permissions. Use the actual user question; "
    "prior workpapers and review opinions can be wrong."
)


def get_research_method(method_id: str = "") -> dict:
    """Return the catalog or one packaged method; never a local path."""
    if not method_id:
        return {"version": 1, "answer_free": True, "methods": [
            {"method_id": key, "title": title, "summary": summary}
            for key, (title, summary) in METHODS.items()
        ]}
    if method_id not in METHODS:
        raise ValueError("unknown_research_method: select an ID from get_research_method()")
    title, summary = METHODS[method_id]
    content = files("sec_agent.research_foundation").joinpath("methods", method_id + ".md").read_text(encoding="utf-8")
    return {"version": 1, "method_id": method_id, "title": title, "summary": summary,
            "content": content, "answer_free": True, "grants_authority": False}
