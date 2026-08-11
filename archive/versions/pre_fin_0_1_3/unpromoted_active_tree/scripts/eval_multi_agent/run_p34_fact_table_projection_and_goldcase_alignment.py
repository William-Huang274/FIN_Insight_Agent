from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.langgraph_orchestrator import _render_memo_answer  # noqa: E402
from sec_agent.p34_lane_quality_runtime import (  # noqa: E402
    DEFAULT_LIVE_ROUTE_ATTEMPT_REPORT_PATH,
    DEFAULT_P33_LIVE_BACKFILL_PATH,
    build_ai_semis_scoped_writer_payload,
)


DEFAULT_ALIGNMENT_JSON = REPO_ROOT / "docs/project_os/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.json"
DEFAULT_ALIGNMENT_MD = (
    REPO_ROOT / "docs/internal/vnext_20260610/p34_ai_semis_goldcase_rag_availability_alignment_v0_1.zh-CN.md"
)
DEFAULT_PREVIEW_MD = (
    REPO_ROOT / "docs/internal/vnext_20260610/p34_fact_table_projection_preview_v0_1.zh-CN.md"
)


def main() -> int:
    state = build_ai_semis_scoped_writer_payload()
    rendered = _render_memo_answer(_preview_memo(state), bounded=False, state=state)
    DEFAULT_PREVIEW_MD.write_text(_preview_md(rendered), encoding="utf-8")

    alignment = build_alignment_audit(state)
    DEFAULT_ALIGNMENT_JSON.write_text(json.dumps(alignment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DEFAULT_ALIGNMENT_MD.write_text(_alignment_md(alignment), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": alignment["status"],
                "preview_md": str(DEFAULT_PREVIEW_MD.resolve()),
                "alignment_json": str(DEFAULT_ALIGNMENT_JSON.resolve()),
                "alignment_md": str(DEFAULT_ALIGNMENT_MD.resolve()),
                "full_chain_run": False,
                "paid_llm_run": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_alignment_audit(state: Mapping[str, Any]) -> dict[str, Any]:
    live = _load_json(DEFAULT_LIVE_ROUTE_ATTEMPT_REPORT_PATH)
    p33 = _load_json(DEFAULT_P33_LIVE_BACKFILL_PATH)
    p33_metrics = p33.get("metrics") if isinstance(p33.get("metrics"), Mapping) else {}
    fact_blocks = [block for block in state.get("analyst_fact_table_blocks") or [] if isinstance(block, Mapping)]
    fact_rows = [row for block in fact_blocks for row in block.get("rows") or [] if isinstance(row, Mapping)]
    rows_by_quality: dict[str, int] = {}
    for row in fact_rows:
        quality = str(row.get("value_quality") or "unknown")
        rows_by_quality[quality] = rows_by_quality.get(quality, 0) + 1

    return {
        "schema_version": "fin_insight_p34_ai_semis_goldcase_rag_availability_alignment_v0_1",
        "created_at": _utc_now(),
        "status": "goldcase_aligned_to_current_rag_and_route_availability_before_full_chain",
        "scope": {
            "case_id": str(state.get("case_id") or ""),
            "lane": "AI/Semis",
            "full_chain_run": False,
            "paid_llm_run": False,
            "purpose": (
                "Align the AI/Semis humanmade gold case to what the current RAG/SQL/Milvus manifests and P34 "
                "live source-route runtime rows can actually support before any true full-chain eval."
            ),
        },
        "current_data_availability": {
            "indexed_row_count": p33_metrics.get("indexed_row_count"),
            "indexed_ticker_count": p33_metrics.get("indexed_ticker_count"),
            "p33_goldset_live_ready_row_count": p33_metrics.get("live_runtime_ready_row_count"),
            "p34_slot_count": (live.get("metrics") or {}).get("slot_count"),
            "p34_attempted_slot_count": (live.get("metrics") or {}).get("attempted_slot_count"),
            "p34_accepted_runtime_row_count": (live.get("metrics") or {}).get("accepted_runtime_row_count"),
            "p34_typed_gap_count": (live.get("metrics") or {}).get("typed_gap_count"),
            "analyst_fact_table_block_count": len(fact_blocks),
            "analyst_fact_table_row_count": len(fact_rows),
            "analyst_fact_rows_by_value_quality": rows_by_quality,
        },
        "important_boundary": {
            "rag_retrieval_role": (
                "The current P34 scoped writer case is a source-route/runtime-row replay, not a Milvus/rerank-driven "
                "full-chain retrieval run. RAG/Milvus remains the broader discovery and retrieval substrate, but this "
                "case intentionally tests whether accepted source-route rows can be made analyst-ready."
            ),
            "sec_parser_boundary": (
                "The issue found here is not that SEC/8-K table parsing is globally broken. Some P34 rows come from "
                "official press releases/pages and current live-route adapters still preserve them as context_summary "
                "instead of extracting every numeric table cell. Standardized SEC/XBRL/ledger rows remain usable where "
                "already materialized, but this scoped case cannot assume numbers not present in accepted runtime rows."
            ),
        },
        "goldcase_alignment_decisions": [
            {
                "goldcase_requirement": "Product / architecture judgment",
                "current_support": "Supported by official/spec rows for NVDA GB200 NVL72, AMD MI300X/MI355X, Google TPU and A4X/GB200 deployment surface.",
                "allowed_answer": "Can compare product capability, architecture, bandwidth/memory, benchmark proxy and deployment/adoption path.",
                "not_allowed": "Cannot infer SKU revenue, ASP, shipment, supplier allocation or market share.",
                "goldcase_status": "supported_with_boundary",
            },
            {
                "goldcase_requirement": "DELL AI server financial quality",
                "current_support": "Supported for orders/shipments/backlog and ISG baseline visibility, but not AI server gross margin, GPU pass-through, attach rate or backlog conversion.",
                "allowed_answer": "Can state demand/revenue visibility is stronger than generic server demand.",
                "not_allowed": "Cannot conclude AI server growth is high-quality profit until margin bridge rows are parsed or disclosed.",
                "goldcase_status": "attempt_backed_gap_for_margin_quality",
            },
            {
                "goldcase_requirement": "Hyperscaler capex read-through",
                "current_support": "Supported as demand-pool context from MSFT/GOOGL/META/AMZN rows.",
                "allowed_answer": "Can discuss demand-pool strength and supplier-capture conditions.",
                "not_allowed": "Cannot turn capex into NVDA/DELL/ASML/LRCX revenue, allocation, backlog or order exact.",
                "goldcase_status": "supported_context_not_supplier_capture",
            },
            {
                "goldcase_requirement": "Semicap read-through",
                "current_support": "Supported by TSM/ASML/AMAT/LRCX rows as mechanism context.",
                "allowed_answer": "Can separate advanced node, lithography, materials engineering and HBM/process-intensity read-through.",
                "not_allowed": "Cannot claim AI-specific bookings, backlog, shipments, customer allocation or China exposure exact unless parsed from issuer rows.",
                "goldcase_status": "supported_with_deeper_parser_boundary",
            },
            {
                "goldcase_requirement": "Market price-in / capital feedback",
                "current_support": "Only bounded fixture/market context is present in this scoped case.",
                "allowed_answer": "Can say recommendation-quality judgment is constrained by missing valuation/positioning/flow evidence.",
                "not_allowed": "Cannot output buy/sell strength, real-time crowding, complete options positioning, borrow cost or price-in conclusion.",
                "goldcase_status": "bounded_gap_until_market_pack_runtime_rows_exist",
            },
        ],
        "quality_eval_update": {
            "new_required_pre_full_chain_checks": [
                "Every memo writer payload must include analyst_fact_table_blocks or explicitly explain why the case has no tableable facts.",
                "Eval must separate retrieval path: SQL/Milvus/RAG, source-route live attempt, existing manifest row, or deterministic fixture.",
                "Each goldcase required item must map to available/runtime, context_summary, attempt_backed_gap, commercial_gap, or not_in_current_rag_scope.",
                "Writer output must render fact tables before required-item boundary language.",
                "A true full-chain eval cannot pass if a goldcase requirement is absent from RAG/route availability but still demanded as exact output.",
            ],
            "blocked_until_user_approval": [
                "true_full_chain_eval",
                "paid_model_comparison",
                "case_expansion_release_eval",
            ],
        },
    }


def _preview_memo(state: Mapping[str, Any]) -> dict[str, Any]:
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else {}
    judgment_state = judgment.get("judgment_state") if isinstance(judgment.get("judgment_state"), Mapping) else {}
    return {
        "response_language": {"language": "zh-CN"},
        "memo_profile": {"profile": "deep_research", "rendered_claim_max": 6, "rendered_dimension_max": 6},
        "answer_status": "deterministic_no_paid_preview",
        "direct_answer": (
            "当前 AI/Semis 链条的可用证据支持一个有边界的正向研究判断：AI 基建需求池是真实存在的，"
            "NVDA GB200/Blackwell、AMD MI300X/MI355X、Google TPU/A4X 和 DELL PowerEdge 路径能够说明产品能力、"
            "替代压力与采用表面；但这还不能自动转化为 DELL 高质量利润、NVDA/DELL 订单 allocation、"
            "semicap AI-specific backlog 或 market price-in 结论。报告应先用数据表说明已有锚点，再判断哪些链条成立、"
            "哪些只是 proxy，最后把 DELL margin bridge 和市场定价列为会改变判断的关键缺口。"
        ),
        "memo_logic_plan": state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {},
        "dimension_analyses": judgment_state.get("dimension_judgments") or [],
        "memo_claims": (state.get("verified_judgment_plan") or {}).get("supported_claims")
        if isinstance(state.get("verified_judgment_plan"), Mapping)
        else [],
        "investment_implications": [
            "当前更适合把 AI/Semis 写成有边界的正向研究 workpaper，而不是 recommendation：产品与需求证据支持主线，但利润质量和 price-in 仍未闭环。",
            "DELL 的关键不是 AI server 需求是否存在，而是 backlog 转化、GPU pass-through 和 ISG margin 是否证明收入质量。",
        ],
        "what_would_change_view": [
            "如果 DELL 披露 AI server mix、gross margin、attach economics 或 backlog conversion 改善，DELL 质量判断可以上调。",
            "如果 hyperscaler capex 下修、AMD/TPU 替代扩大、NVDA supply delay 或 semicap bookings/backlog 滞后，主线应降权。",
        ],
        "monitoring_items": [
            "跟踪 DELL AI server orders / shipments / backlog / ISG margin。",
            "跟踪 NVDA GB200、AMD MI300X/MI355X、Google TPU/A4X 的部署、配置、benchmark 和供应链约束。",
            "跟踪 ASML/AMAT/LRCX 的 bookings/backlog、China exposure、HBM/advanced packaging 相关披露。",
        ],
        "evidence_gaps_but_actionable": [
            "AI server gross margin、GPU pass-through cost、customer mix、SKU revenue/ASP/shipments 和 market positioning 仍需 deeper parser 或商业 tracker。",
        ],
    }


def _preview_md(rendered: str) -> str:
    return (
        "# P34 Fact Table Projection Preview v0.1\n\n"
        "本预览为 no-paid deterministic projection，不调用 LLM，不跑 full-chain。目的只验证 P34 accepted runtime rows 是否能以 analyst-ready fact table 进入最终 surface。\n\n"
        + rendered
        + "\n"
    )


def _alignment_md(alignment: Mapping[str, Any]) -> str:
    availability = alignment["current_data_availability"]
    lines = [
        "# P34 AI/Semis Goldcase 与当前 RAG/Route 可得性对齐 v0.1",
        "",
        "本文件用于在 true full-chain eval 前校准 goldcase：不能要求 agent 输出当前 RAG/SQL/Milvus/route 尚未形成 runtime row 的 exact 数据。",
        "",
        "## 当前可得性",
        "",
        f"- Indexed rows: `{availability.get('indexed_row_count')}`；tickers: `{availability.get('indexed_ticker_count')}`。",
        f"- P34 slots: `{availability.get('p34_attempted_slot_count')}/{availability.get('p34_slot_count')}` attempted；accepted runtime rows: `{availability.get('p34_accepted_runtime_row_count')}`；typed gaps: `{availability.get('p34_typed_gap_count')}`。",
        f"- Analyst fact tables: `{availability.get('analyst_fact_table_block_count')}` blocks / `{availability.get('analyst_fact_table_row_count')}` rows。",
        f"- Value quality: `{availability.get('analyst_fact_rows_by_value_quality')}`。",
        "",
        "## 关键边界",
        "",
        f"- RAG/Milvus 角色：{alignment['important_boundary']['rag_retrieval_role']}",
        f"- SEC/parser 边界：{alignment['important_boundary']['sec_parser_boundary']}",
        "",
        "## Goldcase 对齐决策",
        "",
    ]
    for row in alignment["goldcase_alignment_decisions"]:
        lines.extend(
            [
                f"### {row['goldcase_requirement']}",
                "",
                f"- 当前支撑：{row['current_support']}",
                f"- 允许回答：{row['allowed_answer']}",
                f"- 不允许回答：{row['not_allowed']}",
                f"- 状态：`{row['goldcase_status']}`",
                "",
            ]
        )
    lines.extend(
        [
            "## 评测体系更新",
            "",
            "true full-chain eval 前新增检查：",
            "",
            *[f"- {item}" for item in alignment["quality_eval_update"]["new_required_pre_full_chain_checks"]],
            "",
            "仍需用户认可后才能执行：",
            "",
            *[f"- `{item}`" for item in alignment["quality_eval_update"]["blocked_until_user_approval"]],
            "",
        ]
    )
    return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
