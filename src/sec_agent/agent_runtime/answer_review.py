"""Version-bound, opt-in challenges to a previously delivered answer."""
import json
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PREFIX = 'finsight.answer-review.v1\n'


class Challenge(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    artifact: Literal['answer', 'report'] = 'answer'
    version: str = Field(pattern=r'^[0-9a-f]{64}$')
    quote: str = Field(max_length=4000)
    offset: int = Field(ge=0)
    question: str = Field(max_length=2500)


def version(body):
    return sha256(body.encode('utf8')).hexdigest()


def target(command, messages, session_id, *, report=None, report_version=None):
    selected = Challenge.model_validate_json(command[len(PREFIX):])
    if not selected.quote.strip() and (selected.quote or selected.offset or not selected.question.strip()):
        raise ValueError('answer_review_requires_passage_or_version_question')
    if selected.artifact == 'report':
        from langchain_core.messages import AIMessage
        from .research_graph_contracts import canonical_sha256
        # Bind the persisted complete artifact, never its conversational summary.
        if not report or canonical_sha256(report) != selected.version:
            raise ValueError('selected_report_version_unavailable')
        author = next((m for m in reversed(messages) if m.type == 'ai' and
                       m.additional_kwargs.get('harness_session_id')), None)
        if not session_id or author is None or author.additional_kwargs['harness_session_id'] != session_id:
            raise ValueError('selected_answer_author_session_mismatch')
        body = report['narrative_markdown']
        if not body.startswith(selected.quote, selected.offset):
            raise ValueError('selected_answer_passage_changed')
        return selected, AIMessage(content=body, additional_kwargs={
            'harness_session_id': session_id, 'report_version': report_version,
            'report_title': report['title'], 'report_digest': selected.version,
            'citation_bindings': report.get('citations', {})})
    for msg in reversed(messages):
        if msg.type != 'ai' or not isinstance(msg.content, str) or version(msg.content) != selected.version:
            continue
        if not session_id or msg.additional_kwargs.get('harness_session_id') != session_id:
            raise ValueError('selected_answer_author_session_mismatch')
        if not msg.content.startswith(selected.quote, selected.offset):
            raise ValueError('selected_answer_passage_changed')
        return selected, msg
    raise ValueError('selected_answer_version_unavailable')


class Edit(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    before: str = Field(min_length=1)
    after: str


class Response(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    reason: str = Field(min_length=1)
    edits: list[Edit]


def apply_response(body, raw):
    raw = raw.strip()
    if raw.startswith('```json\n') and raw.endswith('\n```'):
        raw = raw[8:-4]
    response = Response.model_validate_json(raw)
    spans = []
    for edit in response.edits:
        if body.count(edit.before) != 1 or edit.before == edit.after:
            raise ValueError('answer_revision_original_not_unique_or_unchanged')
        start = body.index(edit.before)
        spans.append((start, start + len(edit.before), edit.after))
    end = len(body)
    for start, stop, replacement in sorted(spans, reverse=True):
        if stop > end:
            raise ValueError('answer_revision_overlapping_edits')
        body = body[:start] + replacement + body[stop:]
        end = start
    if not body.strip():
        raise ValueError('answer_revision_empty')
    return body, response.model_dump()


def author_input(selected, message, review, *, current_report_version=None, recovery_command=None):
    from .quantitative_prose import metric_definition_checks, bound_claim_checks, sentences
    # A historical answer may predate the current checks. Assess the selected
    # version on read; keep deterministic observations separate from the opinion.
    from .source_references import HANDLE
    passage = selected.quote or message.content
    checks = metric_definition_checks(passage)
    evidence = {}
    bindings = message.additional_kwargs.get('citation_bindings', {})
    checks.extend(bound_claim_checks(message.content,
        {s for s in sentences(message.content) if not selected.quote or selected.quote in s or s in selected.quote},
        {k:v['source'] for k,v in bindings.items() if isinstance(v.get('source'),dict)}))
    for handle in dict.fromkeys(HANDLE.findall(passage)):
        source = bindings.get(handle, {}).get('source', {})
        fields = {k: source[k] for k in ('title', 'publication_date', 'expression',
                  'value_decimal', 'result_unit') if source.get(k) is not None}
        if fields:
            evidence[handle] = fields
    task = '处理所选历史版本的局部异议。独立判断，可接受、部分接受或反驳。核对必要依据，保留仍成立的判断。返回 JSON 对象，reason 解释处置理由和仍成立的主要判断，edits 为 {before, after} 列表。before 必须是此版本唯一的逐字原文，包括 Markdown；可修改受影响的关联段。无需修改时返回空列表。新依据使用工具的准确引用句柄。'
    if selected.artifact == 'report':
        task = ('根据独立复核及必要补证，重新判断原问题的答案，再更新当前报告。复核不是标准答案，接受、部分接受或反驳均须依据。'
                '编辑范围由判断变化决定：事实纠正可只改相关段落；核心解释改变时重新组织标题、摘要、论证顺序和结论，不预设保留旧结构。'
                '复用仍成立的材料、计算和内容，通过 edit_research_report 按当前版本分批保存；增量保存是写入方式，不是研究或改稿范围限制。'
                'original_answer 是被复核的历史版本；当前稿可能已局部修改，以 current_report 和读取工具为准。准确引用身份保持不变，新依据使用工具的引用句柄。'
                '完成后用 deliver_current_report 交付实际保存的版本，最后简述哪些判断及其依据改变、哪些仍成立。'
                '无需修改时也说明理由并交付当前版本；收到复核意见不等于报告已通过独立复核。')
    return json.dumps({'task': task,
        **({'current_command': recovery_command} if recovery_command else {}),
        **({'current_report': {'version': current_report_version,
            'readback': {'tool': 'read_current_report', 'arguments': {}},
            'meaning': 'Already saved revisions remain authoritative; the historical review target is not a replacement draft.'}}
            if selected.artifact == 'report' and current_report_version is not None else {}),
        **({'report_version': message.additional_kwargs['report_version'],
            'report_title': message.additional_kwargs['report_title']} if selected.artifact == 'report' else {}),
        'revision_preview': {'tool': 'check_quantitative_changes', 'arguments': 'edits: [{before, after}]',
                             'purpose': '预览改后文字与同稿其他相关表述，可据原文自行决定是否修改。'},
        **({'runtime_observations': checks} if checks else {}),
        **({'cited_receipt_fields': evidence} if evidence else {}),
        'selected': selected.model_dump(), 'original_answer': message.content, 'independent_review': review}, ensure_ascii=False)
