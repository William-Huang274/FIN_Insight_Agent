"""Version-bound, opt-in challenges to a previously delivered answer."""
import json
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field

PREFIX = 'finsight.answer-review.v1\n'


class Challenge(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: str = Field(pattern=r'^[0-9a-f]{64}$')
    quote: str = Field(max_length=4000)
    offset: int = Field(ge=0)
    question: str = Field(max_length=2500)


def version(body):
    return sha256(body.encode('utf8')).hexdigest()


def target(command, messages, session_id):
    selected = Challenge.model_validate_json(command[len(PREFIX):])
    if not selected.quote.strip() and (selected.quote or selected.offset or not selected.question.strip()):
        raise ValueError('answer_review_requires_passage_or_version_question')
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


def author_input(selected, message, review):
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
    return json.dumps({'task': '处理所选历史版本的局部异议。独立判断，可接受、部分接受或反驳。核对必要依据，保留仍成立的判断。返回 JSON 对象，reason 解释处置理由和仍成立的主要判断，edits 为 {before, after} 列表。before 必须是此版本唯一的逐字原文，包括 Markdown；可修改受影响的关联段。无需修改时返回空列表。新依据使用工具的准确引用句柄。',
        **({'runtime_observations': checks} if checks else {}),
        **({'cited_receipt_fields': evidence} if evidence else {}),
        'selected': selected.model_dump(), 'original_answer': message.content, 'independent_review': review}, ensure_ascii=False)
