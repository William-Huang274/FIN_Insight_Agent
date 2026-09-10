import json

import pytest

from scripts.qualification.judge_prepared_claims import prepare_packet, validate_review, messages_for


def seed():
    return {"question": "Compare periods", "focused_review": {"title": "Company",
        "targets": [{"id": "T1", "quote": "statement", "context": "Original statement."}],
        "source_records": {"S1": {"value": 12, "period": "2025"}}},
        "expected": "DO NOT SEND", "private_reasoning": "DO NOT SEND"}


def judgment():
    return {"target_id": "case1/T1", "verdict": "supported", "proposition": "statement",
        "evidence_establishes": "record", "source_ids": ["S1"], "public_reason": "supported",
        "suggested_text": ""}


def test_preparation_preserves_records_and_never_feeds_labels_or_reasoning():
    original = seed()
    packet = prepare_packet([original])
    assert packet["cases"][0]["source_records"] == original["focused_review"]["source_records"]
    assert "DO NOT SEND" not in json.dumps([m.content for m in messages_for(packet)])
    assert validate_review(json.dumps({"judgments": [judgment()]}), packet)


@pytest.mark.parametrize("rows", [[], [judgment(), judgment()], [{**judgment(), "target_id": "other"}],
    [{**judgment(), "source_ids": ["not-observed"]}], [{**judgment(), "suggested_text": "invented fix"}],
    [{**judgment(), "verdict": "needs_revision"}]])
def test_incomplete_cross_source_or_unjustified_edits_rejected(rows):
    with pytest.raises(ValueError):
        validate_review(json.dumps({"judgments": rows}), prepare_packet([seed()]))


def test_source_namespaces_do_not_cross_cases():
    other = seed()
    other["focused_review"]["source_records"] = {"S2": {"value": 99}}
    rows = [judgment(), {**judgment(), "target_id": "case2/T1", "source_ids": ["S1"]}]
    with pytest.raises(ValueError, match="outside_target_case"):
        validate_review(json.dumps({"judgments": rows}), prepare_packet([seed(), other]))


def test_sdk_length_exception_preserves_raw_reasoning_partial_content_and_billed_usage(tmp_path):
    from openai import LengthFinishReasonError
    from openai.types.chat import ChatCompletion
    from scripts.qualification.judge_prepared_claims import save_exception_completion
    raw = ChatCompletion.model_validate({"id": "captured", "created": 1, "model": "test",
        "object": "chat.completion", "choices": [{"index": 0, "finish_reason": "length",
        "message": {"role": "assistant", "content": '{"judgments":', "reasoning_content": "PRIVATE TRACE"}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}})
    outcome = save_exception_completion(LengthFinishReasonError(completion=raw), tmp_path)
    assert outcome["total_tokens"] == 130 and outcome["usage_reported"]
    assert outcome["status"] == "truncated_no_promotion"
    saved = json.loads((tmp_path / "provider-completion.private.json").read_text(encoding="utf-8"))
    assert saved["choices"][0]["message"]["reasoning_content"] == "PRIVATE TRACE"
    assert "PRIVATE TRACE" not in json.dumps(outcome)
