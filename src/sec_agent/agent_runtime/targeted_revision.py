"""FIN revision identity and baseline checks; execution stays in LangGraph."""
import hashlib
import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RevisionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    citation_id: str = Field(min_length=1, max_length=300)
    base_version: int = Field(ge=1)
    base_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    base_checkpoint: UUID


def report_digest(report):
    return hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_revision_target(values, target):
    if (values.get("report_version") != target.base_version
            or report_digest(values.get("report", {})) != target.base_digest):
        raise ValueError("修订基线已变化，请重新读取报告并核对意见；未调用研究模型。")
    binding = values.get("report", {}).get("citations", {}).get(target.citation_id)
    if not binding:
        raise ValueError("目标引用不属于这版报告；未调用研究模型。")
    if str(target.request_id) in values.get("handled_revision_request_ids", []):
        raise ValueError("这条修订请求已处理，请查看原运行；不会重复调用研究模型。")
    return binding


def targeted_feedback(values, target, message):
    binding = validate_revision_target(values, target)
    # The target statement and sources come from saved state, never a browser graph node.
    context = {"report_version": target.base_version, "citation_id": target.citation_id,
               "saved_claim": binding["claim"]["statement"],
               "source_ids": [s["source_id"] for s in binding["sources"]]}
    return ("针对已保存研究引用的修订请求。用户意见不是事实证据；核对当前报告正文及原始来源，"
            "原始引用主张可能早于正文修订。按既有责任修订流程处理，不承诺仅重跑一个节点；"
            "报告修订后须复核相关判断和共享依赖。\n目标："
            + json.dumps(context, ensure_ascii=False) + "\n用户意见：" + message)
