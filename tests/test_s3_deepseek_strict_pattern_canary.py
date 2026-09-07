from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import scripts.research.run_s3_deepseek_strict_pattern_canary as runner
from sec_agent.providers.chat_completions import ChatCompletionToolStepResult


def _provider_step(tmp_path: Path, atom: str) -> ChatCompletionToolStepResult:
    return ChatCompletionToolStepResult(
        status="completed_exact_once_tool_step",
        provider_id="deepseek",
        model="deepseek-v4-pro",
        content="",
        reasoning_content="",
        tool_calls=(
            {
                "id": "call-strict-pattern",
                "type": "function",
                "function": {
                    "name": "submit_safe_financial_atom",
                    "arguments": json.dumps(
                        {"safe_atom": atom}, ensure_ascii=False
                    ),
                },
            },
        ),
        finish_reason="tool_calls",
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        request_capture_ref=str(tmp_path / "request.json"),
        response_capture_ref=str(tmp_path / "response.json"),
        request_digest="a" * 64,
        response_digest="b" * 64,
        private_reasoning_fields_redacted=1,
    )


def _prepare(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[Path, Path, Path]:
    authority_path = tmp_path / "authority.json"
    profile_path = tmp_path / "profile.json"
    private_root = tmp_path / "private"
    public_path = tmp_path / "public.json"
    capture_root = tmp_path / "captures"
    authority = {
        "schema_version": runner.AUTHORITY_SCHEMA,
        "implementation_commit": "a" * 40,
        "known_boundary": "provider transport qualification only",
    }
    authority_path.write_text(json.dumps(authority), encoding="utf-8")
    profile = json.loads(
        (
            ROOT
            / "configs/providers/fin_ia_0_1_3_deepseek_v4_pro_ga_"
            "contract_submission_non_thinking_strict_beta_profile_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    paths = {"profile_ref": profile_path}
    output = {
        "capture_root_ref": "captures",
        "private_output_root_ref": "private",
        "public_result_ref": "public.json",
        "run_id": "STRICT-PATTERN-TEST-R1",
        "attempt_id": "STRICT-PATTERN-ATTEMPT-01",
        "product_publication": "forbidden",
    }
    values = {authority_path: authority, profile_path: profile}
    monkeypatch.setattr(runner, "_json", lambda path: values[path])
    monkeypatch.setattr(
        runner,
        "_validate_authority",
        lambda *_args, **_kwargs: (paths, output),
    )
    destinations = {
        "captures": capture_root,
        "private": private_root,
        "public.json": public_path,
    }
    monkeypatch.setattr(runner, "_resolve", lambda ref: destinations[str(ref)])
    monkeypatch.setattr(runner, "_relative", lambda value: Path(value).as_posix())
    monkeypatch.setattr(runner, "_sha", lambda _path: "f" * 64)
    return authority_path, private_root, public_path


def test_strict_pattern_canary_uses_beta_projection_and_redacts_public_atom(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, private_root, public_path = _prepare(monkeypatch, tmp_path)

    def execute(**kwargs):
        tool = kwargs["tools"][0]
        parameters = tool["function"]["parameters"]
        assert tool["function"]["strict"] is True
        assert "$defs" not in parameters
        assert parameters["properties"]["safe_atom"]["$ref"] == "#/$def/t"
        assert "pattern" in parameters["$def"]["t"]
        return _provider_step(
            tmp_path,
            "公司层面价值获取存在支撑但产品利润桥仍不完整",
        )

    result = runner.run(authority_path, executor=execute)

    assert result["status"] == "completed_deepseek_beta_strict_pattern_qualified"
    assert result["acceptance"]["deepseek_beta_endpoint_accepted_schema"] is True
    assert result["execution"]["model_calls_attempted"] == 1
    assert result["safe_atom_digest"]
    rendered_public = public_path.read_text(encoding="utf-8")
    assert "公司层面价值获取存在支撑" not in rendered_public
    assert (private_root / "full_result.json").is_file()


def test_strict_pattern_canary_keeps_invalid_surface_as_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    authority_path, _, public_path = _prepare(monkeypatch, tmp_path)

    result = runner.run(
        authority_path,
        executor=lambda **_: _provider_step(
            tmp_path,
            "该结论来自 10-Q 且仍需进一步验证",
        ),
    )

    assert result["status"] == "terminal_failed_no_retry"
    assert result["failure"]["code"] == "strict_pattern_safe_atom_invalid"
    assert result["execution"]["retries"] == 0
    assert public_path.is_file()
