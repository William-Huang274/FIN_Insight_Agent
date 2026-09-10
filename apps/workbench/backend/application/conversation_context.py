"""Public navigation over canonical checkpoints; no copied memory store."""
from collections import Counter
from langchain_core.messages import convert_to_messages
from sec_agent.agent_runtime.context_navigation import checkpoint_index
from sec_agent.agent_runtime.model_context import RequestSummaryMiddleware


def context_messages(state):
    return convert_to_messages(state.get('values', {}).get('messages', []))


def context_status(state, harness='native'):
    values = state.get('values', {})
    messages = context_messages(state)
    record = values.get('request_summary') or {}
    failure = values.get('request_summary_failure')
    projected = RequestSummaryMiddleware.projected_messages({**values,'messages':messages}) if messages else []
    return {
        'regions': dict(Counter(r['region'] for r in checkpoint_index(messages))),
        'original_message_count':len(messages), 'projected_message_count':len(projected),
        'summary_count':record.get('count', 0),
        'summary_status':'unavailable' if harness=='hermes' else 'failed' if failure else 'limited' if record.get('count',0)>=2 else 'active',
        'summary_text':(record.get('message') or {}).get('content',''),
        'original_history_retained':True,
        'notice':('Hermes 原生会话保存并支持原文回读；自动压缩尚未启用。下方目录展示工作台已保存的公开消息；工具可读取 Hermes 会话原文。接近输入上限时请使用交接入口。'
            if harness=='hermes' else '摘要只用于定位与接续，原始消息、数字凭证和来源独立保留。每个窗口最多自动摘要两次；失败不自动重试。'),
        'failure_notice':'本次摘要未成功，未采用残缺内容。上一有效视图和原文保留，可核对后继续或交接到新窗口。' if failure else None,
    }
