"""Reviewed teaching editions; evidence and caller-owned methods are never filtered.

The host binds the admitted model during tool execution. A frozen/custom method
is eligible only if its complete content equals the packaged legacy edition.
Both editions and their digests remain addressable in persisted tool receipts.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from hashlib import sha256
from importlib.resources import files

_model = ContextVar('research_method_input_model', default=None)


@contextmanager
def method_model(model):
    token = _model.set(model)
    try:
        yield
    finally:
        _model.reset(token)


def project_method(method, model=None):
    from sec_agent.agent_runtime.research_input_policy import input_policy
    from .research_methods import METHODS, get_research_method
    if input_policy(model if model is not None else _model.get()) == 'explicit_v1':
        return method
    if 'method' in method:  # Preserve the upstream MCP transport receipt.
        return {**method, 'method': project_method(method['method'], model)}
    identifier = method.get('method_id')
    if identifier not in METHODS or 'content' not in method:
        return method
    original = get_research_method(identifier)
    if method['content'] != original['content']:
        return method  # An explicitly frozen/custom edition is not ours to replace.
    path = files('sec_agent.research_foundation').joinpath('methods_judgment', identifier + '.md')
    if identifier == 'financial_quality':
        from .research_methods import select_method_section
        finance = project_method(get_research_method('finance'), model)
        content = select_method_section(finance, '财务质量与日期桥接')['content']
        content += '\n兼容章节：F1断言；F2可比性；F3归因；F4金额桥；F5现金；F6更新。\n'
    elif path.is_file():
        content = path.read_text(encoding='utf-8')
    else:
        return method  # Reviewed technical resources retain their original edition.
    import re
    sections = re.findall(r'(?m)^## (.+)$', content)
    if sections != original['sections']:
        raise ValueError('judgment_method_section_compatibility')
    revision = re.search(r'版本：(\d+)', content)
    return {**method, 'content': content, 'input_profile': 'judgment_v2',
            'content_version': int(revision.group(1)) if revision else None,
            'base_resource_digest': original['resource_digest'],
            'resource_digest': sha256(content.encode()).hexdigest()}


def bind_method_tool(tool, model):
    """Bind each agent's own identity, including concurrently executing children."""
    if tool.name != 'get_research_method':
        return tool
    from functools import wraps
    updates = {}
    if tool.func:
        @wraps(tool.func)
        def run(*args, **kwargs):
            with method_model(model):
                result = tool.func(*args, **kwargs)
                return project_method(result, model) if isinstance(result, dict) else result
        updates['func'] = run
    if tool.coroutine:
        @wraps(tool.coroutine)
        async def arun(*args, **kwargs):
            with method_model(model):
                result = await tool.coroutine(*args, **kwargs)
                return project_method(result, model) if isinstance(result, dict) else result
        updates['coroutine'] = arun
    return tool.model_copy(update=updates)
