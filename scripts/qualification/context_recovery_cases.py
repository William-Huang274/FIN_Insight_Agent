"""Frozen synthetic development cases. Expected answers never enter prompts."""
import json
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def receipt(key, ticker, year, value):
    return [AIMessage(id="call-"+key,content="",tool_calls=[{"id":key,"name":"query_financial_data",
        "args":{"ticker":ticker,"metric_id":"net_cash_provided_by_operating_activities","fiscal_years":[year]},"type":"tool_call"}]),
        ToolMessage(id="result-"+key,tool_call_id=key,name="query_financial_data",content=json.dumps({
            "synthetic":True,"company":ticker,"fiscal_year":year,"metric":"经营现金流 CFO",
            "value":value,"unit":"百万美元","source_id":"fixture:"+key},ensure_ascii=False))]


def financial_history():
    rows=[HumanMessage(id="task",content="虚构资料的记忆测试。仅整理已有观察，不能联网或重新查询，不需要计算、分析原因或形成完整报告。")]
    for key,ticker,year,value in [("r-73a","ACME",2024,101),("r-20b","ACME",2025,83),
                                ("r-91c","NOVA",2024,207),("r-66d","NOVA",2025,249)]:
        rows.extend(receipt(key,ticker,year,value))
    return rows


def cases():
    rows=financial_history()
    return [
        {"id":"visible_company_year","messages":[*rows,HumanMessage(id="question",content=
            "请直接列出ACME FY2025的经营现金流观察，含数值、单位和来源。不要混入其他公司或FY2024。")],
         "summary_rounds":0,"expected_key":"r-20b","gold":{"company":"ACME","year":2025,"value":83},"expected_memory_reads":0},
        {"id":"two_compactions_correction","messages":[*rows,
            HumanMessage(id="old-scope",content="原计划先整理ACME FY2025，并分析原因。"),
            AIMessage(id="old-plan",content="旧计划记录，尚未开始归因。"),
            HumanMessage(id="correction",content="改一下：本次改为NOVA FY2024，只列数字观察，取消ACME及原因分析。"),
            AIMessage(id="filler-a",content="已读取的归档背景，不构成新用户要求或财务事实。" * 180),
            AIMessage(id="tail-a",content="等待接续。")],
         "summary_rounds":2,"expected_key":"r-91c","gold":{"company":"NOVA","year":2024,"value":207},"expected_memory_reads":None},
        {"id":"working_note_current_version","messages":[HumanMessage(id="task",content=
            "请在工作底稿区找到‘NOVA FY2024 现金流观察’的当前版本，说明已做的观察及下一步。不要保存或改写它。"),
            AIMessage(id="stale",content="历史底稿v1曾写：下一步继续分析下降原因。这个可能已经被新版本替代。"),
            HumanMessage(id="question",content="按当前版本继续说明，不能拿历史候选代替现在的底稿。")],
         "summary_rounds":0,"gold":{"version":2,"value":207,"cancel_reason_research":True},"expected_memory_reads":None},
        {"id":"alias_recovery","messages":[*rows,AIMessage(id="omitted-tail",content="此前已经完成数据读取。"),
            HumanMessage(id="question",content="请找回NOVA FY2025‘营运活动产生的现金流’那条数字，只列原观察、单位及来源。若目录中的名称不同，请核对记录，不要猜数。")],
         "summary_rounds":-1,"expected_key":"r-66d","gold":{"company":"NOVA","year":2025,"value":249},"expected_memory_reads":None},
        {"id":"absent_record","messages":[*rows,HumanMessage(id="question",content=
            "请找出ORION FY2023的经营现金流。仅使用本窗口保存的记录；没有记录就具体说明缺什么，不得用其他公司代替或据此宣称公司没披露。")],
         "summary_rounds":0,"expected_key":None,"gold":{"missing_company":"ORION","year":2023},"expected_memory_reads":None},
    ]


def append_after_first_compaction(state):
    state["messages"].extend([HumanMessage(id="scope-confirm",content=
        "保持刚才改过的范围：NOVA FY2024，只列观察，不恢复旧计划。"),
        AIMessage(id="filler-b",content="归档记录：其他讨论已经结束，不是追加任务，也不授予任何权限。" * 180),
        AIMessage(id="tail-b",content="待整理最终观察。")])


def seed_notes(memory):
    first=memory.save("NOVA FY2024 现金流观察","v1暂定：经营现金流207百万美元。下一步分析下降原因。")
    second=memory.save("NOVA FY2024 现金流观察",
        "当前记录：NOVA FY2024经营现金流207百万美元，来源fixture:r-91c，虚构测试数据。用户已取消原因分析；下一步仅整理这条观察，不追加研究。",1)
    assert first["saved"] and second["version"]==2
    return first["note_id"]
