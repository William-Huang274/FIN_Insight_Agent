"""One scoped information/data toolkit, exported by the existing research MCP.

Provider implementations, wire names, authorization and receipts stay native.
This is composition and discoverability, not another execution/search layer.
"""
import json
from pathlib import Path
from typing import Literal

from langchain_core.tools import tool
from .conversation_agent import GrantedTool

CAPABILITIES = {
    'read_public_source': ('information', '跨地区网页搜索、SEC/公司原件、政府网站与已保存原文',
        'auto 使用现有搜索栈；可显式选 bing_china/bing/github/baidu/bilibili 与语言。搜索摘要不是已读原文；源站可限流或返回无关结果。'),
    'read_legislation': ('information', '美国 Congress 官方法案、程序动作、文本版本',
        '先定位法案，再列版本并按返回入口读全文；不是新闻或所有国家的法律搜索。'),
    'search_korean_disclosures': ('information', '韩国 OpenDART 韩文/英文申报目录',
        '按公开日期和公司代码查目录，再读原件；不是韩国行情或已读取全文。'),
    'read_regional_disclosures': ('information', '台湾 TWSE 公司目录与当前重大讯息',
        '历史时点只可用当前身份定位，不把当前公告快照当历史档案。'),
    'read_market_prices': ('data', '带时间、交易时段与分页的市场 OHLCV',
        '记录实际延迟、区间与单位；价格本身不能识别原因。'),
    'query_hithink': ('data', '同花顺官方 A股、指数、基金、期货、期权与标的定位',
        'catalog→describe→call 使用六域原生 schema；不供应新闻研报全文。历史版本限制以回执为准。'),
    'query_public_data': ('data', 'AKTools/AKShare 多供应商公共数据与东方财富资讯发现',
        'search→describe→data，先检查接口来源及参数；当前表不自动成为历史可见的金融事实。'),
}


def source_tool_guidance(names):
    available = [name for name in CAPABILITIES if name in names]
    if not available:
        return ''
    intro = ('\n公开资料与数据由同一个研究 MCP 提供，分 information 与 data 两组。'
             '使用 discover_source_tools 查看当前授权目录或某个工具的准确参数，再直接调用对应工具。'
             if 'discover_source_tools' in names else '\n当前公开资料与数据工具：')
    return intro + '\n' + '\n'.join(f'{name}：{CAPABILITIES[name][1]}。' for name in available) + (
        '\n网页搜索和原文读取使用 read_public_source；auto 复用现有搜索栈，'
        '也可明确选择 bing_china/bing/github 等入口和地区语言。'
        '按研究范围选择当地语言、机构或产品名称，不以英语索引代表全球。'
        '只发送公开检索词，保留研究截止日；搜索摘要、目录和当前数据不自动成为已读原件或历史事实。'
        '收到官方 API 或原件导航时沿准确入口读取；访问失败要与不存在区分，依据反馈换可用路径。'
        '各工具完整结果沿现有 read_saved_result 回读，不需要重新搜索已成功取得的材料。\n')


def source_catalog(grants):
    bound = {g.tool.name: g for g in grants if g.tool.name in CAPABILITIES}

    @tool(response_format='content_and_artifact')
    async def discover_source_tools(group: Literal['all', 'information', 'data'] = 'all', tool_name: str = ''):
        """Discover this task's authorized information/data tools in one MCP.
        Call without tool_name for the grouped catalog, or supply a returned name
        for its exact native input schema. Then call that tool directly. Catalog
        presence means configured, not guaranteed live availability. Sources,
        cutoffs, errors and saved receipts remain with the native tool.
        """
        if tool_name:
            grant = bound.get(tool_name)
            if grant is None:
                out = {'status': 'unavailable_tool', 'available_tools': list(bound)}
            else:
                out = {'status': 'ok', 'tool': tool_name, 'group': CAPABILITIES[tool_name][0],
                       'description': grant.tool.description,
                       'input_schema': grant.tool.tool_call_schema.model_json_schema()}
        else:
            out = {'status': 'ok', 'groups': ['information', 'data'], 'tools': [
                {'tool': name, 'group': category, 'purpose': purpose, 'limits': limits,
                 'configured': name in bound}
                for name, (category, purpose, limits) in CAPABILITIES.items()
                if group == 'all' or group == category],
                'usage': 'Use local-language queries where relevant; inspect originals. '
                         'Configured does not mean live reachability or sufficient coverage. '
                         'Unavailable channels do not imply that a market has no information.',
                'not_integrated': ['MediaCrawler authenticated community content', 'EDINET API', 'J-Quants']}
        return json.dumps(out, ensure_ascii=False), out

    return GrantedTool(discover_source_tools, 'read', '当前授权信息/数据能力目录及原生参数')


def source_tools(*, thread_id, run_id, method_digest, cache_root, research_as_of=None,
                 paid_search=None, sec_user_agent=None, imported_navigation=None, congress_api=None):
    """Only called after the host admits public-source access for this task."""
    from .conversation_web import public_web_tool
    from .market_prices import market_price_tool
    from .regional_disclosures import regional_disclosure_tool
    from .legislation import legislation_tool
    from .public_data import public_data_tool
    from .hithink_data import hithink_data_tool
    from .korean_disclosures import korean_disclosure_tool
    root = Path(cache_root)
    grants = [
        public_web_tool(thread_id=thread_id, run_id=run_id, method_digest=method_digest,
            cache_root=root/'public-source-cache', research_as_of=research_as_of,
            paid_search=paid_search, sec_user_agent=sec_user_agent, imported_navigation=imported_navigation),
        market_price_tool(thread_id=thread_id, cache_root=root/'market-observations', research_as_of=research_as_of),
        regional_disclosure_tool(thread_id=thread_id, cache_root=root/'regional-disclosures', research_as_of=research_as_of),
        legislation_tool(thread_id=thread_id, cache_root=root/'legislation-observations', research_as_of=research_as_of, api=congress_api),
    ]
    grants.extend(g for g in (public_data_tool(research_as_of=research_as_of),
        hithink_data_tool(research_as_of=research_as_of), korean_disclosure_tool(research_as_of=research_as_of)) if g is not None)
    return [source_catalog(grants), *grants]
