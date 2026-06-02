from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .job_runner import CommandSpec
from .profiles import WorkbenchProfile


class DataBuildParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    flag: str
    label: str
    required: bool = False
    kind: str = "string"
    default: str | None = None
    multiple: bool = False
    description: str = ""


class DataBuildStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    family: str
    label: str
    description: str
    script: str
    parameters: list[DataBuildParameter] = Field(default_factory=list)
    output_parameters: list[str] = Field(default_factory=list)
    timeout_hint_s: int = 300


class DataBuildCommandPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    label: str
    args: list[str]
    cwd: str
    missing_required: list[str] = Field(default_factory=list)
    bundle_artifact_updates: dict[str, str] = Field(default_factory=dict)
    bundle_field_updates: dict[str, str] = Field(default_factory=dict)


def data_build_catalog() -> list[DataBuildStep]:
    return list(_DATA_BUILD_STEPS.values())


def get_data_build_step(step_id: str) -> DataBuildStep | None:
    return _DATA_BUILD_STEPS.get(step_id)


def build_data_build_command(
    *,
    repo_root: str | Path,
    step_id: str,
    values: dict[str, Any],
    profile: WorkbenchProfile | None = None,
    dry_run: bool = False,
) -> tuple[CommandSpec, DataBuildCommandPreview]:
    step = _require_step(step_id)
    args, missing_required = _build_args(step, values, dry_run=dry_run)
    python = profile.runtime.python if profile else sys.executable
    command_args = [python, "-u", step.script, *args]
    env_overrides = profile.to_runtime_env() if profile else {}
    cwd = Path(repo_root).resolve()
    spec = CommandSpec(
        args=command_args,
        cwd=cwd,
        env_overrides=env_overrides,
        label=f"data-build:{step.step_id}",
    )
    preview = DataBuildCommandPreview(
        step_id=step.step_id,
        label=step.label,
        args=command_args,
        cwd=str(cwd),
        missing_required=missing_required,
        bundle_artifact_updates=source_bundle_artifact_updates(step.step_id, values),
        bundle_field_updates=source_bundle_field_updates(step.step_id, values),
    )
    return spec, preview


def source_bundle_artifact_updates(step_id: str, values: dict[str, Any]) -> dict[str, str]:
    mapping = {
        "sec_build_manifest": {"output": "manifest_path"},
        "sec_build_bm25_index": {"output_dir": "bm25_index_dir"},
        "sec_build_object_bm25_index": {"output_dir": "object_bm25_index_dir"},
        "sec_merge_source_gaps": {"output": "source_gap_path"},
        "market_build_evidence_pack": {"output": "market_evidence_path"},
    }
    result: dict[str, str] = {}
    for value_key, artifact_key in mapping.get(step_id, {}).items():
        value = values.get(value_key)
        if not _is_blank(value):
            result[artifact_key] = str(value).strip()
    return result


def source_bundle_field_updates(step_id: str, values: dict[str, Any]) -> dict[str, str]:
    if step_id not in {"market_normalize_snapshot", "industry_download_source_snapshot"}:
        return {}
    result: dict[str, str] = {}
    as_of_date = values.get("as_of_date")
    if not _is_blank(as_of_date):
        result["as_of_date"] = str(as_of_date).strip()
    return result


def _build_args(step: DataBuildStep, values: dict[str, Any], *, dry_run: bool) -> tuple[list[str], list[str]]:
    args: list[str] = []
    missing_required: list[str] = []
    for parameter in step.parameters:
        value = values.get(parameter.name, parameter.default)
        if _is_blank(value):
            if parameter.required:
                missing_required.append(parameter.name)
            continue
        if parameter.kind == "bool":
            if _truthy(value):
                args.append(parameter.flag)
            continue
        if parameter.multiple:
            for item in _list_values(value):
                args.extend([parameter.flag, item])
            continue
        args.extend([parameter.flag, str(value).strip()])
    if dry_run and _supports_dry_run(step):
        args.append("--dry-run")
    return args, missing_required


def _require_step(step_id: str) -> DataBuildStep:
    step = get_data_build_step(step_id)
    if step is None:
        raise ValueError(f"unsupported_data_build_step: {step_id}")
    return step


def _param(
    name: str,
    flag: str,
    label: str,
    *,
    required: bool = False,
    kind: str = "string",
    default: str | None = None,
    multiple: bool = False,
    description: str = "",
) -> DataBuildParameter:
    return DataBuildParameter(
        name=name,
        flag=flag,
        label=label,
        required=required,
        kind=kind,
        default=default,
        multiple=multiple,
        description=description,
    )


def _step(
    step_id: str,
    family: str,
    label: str,
    description: str,
    script: str,
    parameters: list[DataBuildParameter],
    *,
    output_parameters: list[str] | None = None,
    timeout_hint_s: int = 300,
) -> DataBuildStep:
    return DataBuildStep(
        step_id=step_id,
        family=family,
        label=label,
        description=description,
        script=script,
        parameters=parameters,
        output_parameters=output_parameters or [],
        timeout_hint_s=timeout_hint_s,
    )


def _supports_dry_run(step: DataBuildStep) -> bool:
    return step.step_id in {"sec_download_filings", "sec_download_8k_earnings"}


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple)):
        return not [item for item in value if not _is_blank(item)]
    return False


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _list_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


_DATA_BUILD_STEPS = {
    "sec_download_filings": _step(
        "sec_download_filings",
        "SEC",
        "下载 SEC 10-K/10-Q",
        "按配置下载 SEC 公司披露原文到本地私有缓存。",
        "scripts/data_sec/download_sec_filings.py",
        [
            _param("config", "--config", "配置 YAML", default="configs/sec_tech_universe.yaml"),
            _param("cache_dir", "--cache-dir", "SEC 缓存目录", default="data/raw_private/sec_filings"),
            _param("user_agent", "--user-agent", "SEC User-Agent"),
            _param("tickers", "--tickers", "股票代码"),
            _param("years", "--years", "年份"),
            _param("form_types", "--form-types", "文件类型", default="10-K,10-Q"),
            _param("limit", "--limit", "数量上限"),
            _param("allow_missing", "--allow-missing", "允许缺失", kind="bool"),
            _param("rate_limit", "--rate-limit", "SEC 访问限速"),
        ],
        timeout_hint_s=900,
    ),
    "sec_build_manifest": _step(
        "sec_build_manifest",
        "SEC",
        "生成 SEC 清单",
        "从 SEC 原文缓存和元数据生成 manifest JSONL。",
        "scripts/data_sec/build_sec_manifest.py",
        [
            _param("config", "--config", "配置 YAML", default="configs/sec_tech_universe.yaml"),
            _param("root", "--root", "SEC 缓存目录", default="data/raw_private/sec_filings"),
            _param("output", "--output", "输出清单", required=True),
            _param("years", "--years", "年份"),
            _param("tickers", "--tickers", "股票代码"),
            _param("categories", "--categories", "行业分类"),
            _param("form_types", "--form-types", "文件类型", default="10-K,10-Q"),
            _param("allow_missing_html", "--allow-missing-html", "允许 HTML 缺失", kind="bool"),
        ],
        output_parameters=["output"],
    ),
    "sec_build_chunks": _step(
        "sec_build_chunks",
        "SEC",
        "切分 SEC 文本",
        "把 SEC HTML 披露按章节切成可检索片段。",
        "scripts/data_sec/build_sec_chunks.py",
        [
            _param("manifest", "--manifest", "输入清单", required=True),
            _param("output", "--output", "输出 chunks", required=True),
            _param("years", "--years", "年份"),
            _param("tickers", "--tickers", "股票代码"),
            _param("items", "--items", "章节 item"),
            _param("target_words", "--target-words", "目标词数"),
            _param("overlap_words", "--overlap-words", "重叠词数"),
            _param("min_words", "--min-words", "最小词数"),
            _param("limit", "--limit", "文件上限"),
            _param("workers", "--workers", "并发进程数"),
        ],
        output_parameters=["output"],
        timeout_hint_s=900,
    ),
    "sec_build_evidence_store": _step(
        "sec_build_evidence_store",
        "SEC",
        "生成 EvidenceObject",
        "把 SEC chunks 转成统一证据 JSONL。",
        "scripts/data_retrieval/build_evidence_store.py",
        [
            _param("chunks", "--chunks", "输入 chunks", required=True),
            _param("output", "--output", "输出证据库", required=True),
        ],
        output_parameters=["output"],
    ),
    "sec_build_bm25_index": _step(
        "sec_build_bm25_index",
        "SEC",
        "构建 BM25 索引",
        "从 EvidenceObject JSONL 构建 BM25 文本索引。",
        "scripts/data_retrieval/build_bm25_index.py",
        [
            _param("evidence", "--evidence", "输入证据库", required=True),
            _param("output_dir", "--output-dir", "输出索引目录", required=True),
            _param("workers", "--workers", "工作线程"),
            _param("batch_size", "--batch-size", "批大小"),
            _param("progress_every", "--progress-every", "进度间隔"),
            _param("validate_schema", "--validate-schema", "校验证据 schema", kind="bool"),
            _param("cpu_workers", "--cpu-workers", "CPU worker"),
        ],
        output_parameters=["output_dir"],
    ),
    "sec_build_object_bm25_index": _step(
        "sec_build_object_bm25_index",
        "SEC",
        "构建 ObjectBM25 索引",
        "从结构化对象目录构建 ObjectBM25 索引。",
        "scripts/data_retrieval/build_object_bm25_index.py",
        [
            _param("structured_dir", "--structured-dir", "结构化对象目录", required=True),
            _param("prefix", "--prefix", "文件前缀"),
            _param("output_dir", "--output-dir", "输出索引目录", required=True),
            _param("record_mode", "--record-mode", "记录模式", default="compact"),
            _param("workers", "--workers", "工作线程"),
            _param("cpu_workers", "--cpu-workers", "CPU worker"),
            _param("batch_bytes", "--batch-bytes", "批字节数"),
            _param("progress_every", "--progress-every", "进度间隔"),
            _param("no_slim_jsonl", "--no-slim-jsonl", "跳过 slim jsonl", kind="bool"),
        ],
        output_parameters=["output_dir"],
    ),
    "sec_download_8k_earnings": _step(
        "sec_download_8k_earnings",
        "8-K",
        "下载 8-K 业绩稿",
        "下载公司 8-K 业绩新闻稿附件，并可输出缺口记录。",
        "scripts/data_sec/download_sec_8k_earnings.py",
        [
            _param("config", "--config", "配置 YAML", default="configs/sec_8k_earnings_pilot.yaml"),
            _param("cache_dir", "--cache-dir", "8-K 缓存目录", default="data/raw_private/sec_8k_earnings"),
            _param("user_agent", "--user-agent", "SEC User-Agent"),
            _param("tickers", "--tickers", "股票代码"),
            _param("years", "--years", "年份"),
            _param("after_date", "--after-date", "起始日期"),
            _param("limit", "--limit", "数量上限"),
            _param("missing_output", "--missing-output", "缺口输出"),
            _param("allow_missing", "--allow-missing", "允许缺失", kind="bool"),
            _param("rate_limit", "--rate-limit", "SEC 访问限速"),
        ],
        output_parameters=["missing_output"],
        timeout_hint_s=900,
    ),
    "sec_build_8k_manifest": _step(
        "sec_build_8k_manifest",
        "8-K",
        "生成 8-K 清单",
        "从 8-K 业绩稿缓存生成 manifest 和缺口记录。",
        "scripts/data_sec/build_sec_8k_earnings_manifest.py",
        [
            _param("config", "--config", "配置 YAML", default="configs/sec_8k_earnings_pilot.yaml"),
            _param("root", "--root", "8-K 缓存目录", default="data/raw_private/sec_8k_earnings"),
            _param("output", "--output", "输出清单", required=True),
            _param("years", "--years", "年份"),
            _param("tickers", "--tickers", "股票代码"),
            _param("categories", "--categories", "行业分类"),
            _param("allow_missing_html", "--allow-missing-html", "允许 HTML 缺失", kind="bool"),
            _param("gap_output", "--gap-output", "缺口输出"),
        ],
        output_parameters=["output", "gap_output"],
    ),
    "sec_merge_source_gaps": _step(
        "sec_merge_source_gaps",
        "8-K",
        "合并来源缺口",
        "合并下载阶段和 manifest 阶段的结构化缺口记录。",
        "scripts/data_sec/merge_sec_source_gaps.py",
        [
            _param("input", "--input", "输入缺口文件", required=True, multiple=True),
            _param("output", "--output", "输出缺口文件", required=True),
            _param("allow_missing_inputs", "--allow-missing-inputs", "跳过缺失输入", kind="bool"),
        ],
        output_parameters=["output"],
    ),
    "market_download_yahoo_chart": _step(
        "market_download_yahoo_chart",
        "Market",
        "下载 Yahoo 行情快照",
        "下载目标股票和基准的 Yahoo 日线行情，生成离线市场快照原始 CSV。",
        "scripts/market/06_download_yahoo_chart_snapshot.py",
        [
            _param("tickers", "--tickers", "股票代码"),
            _param("benchmark_tickers", "--benchmark-tickers", "基准代码", default="SPY,QQQ"),
            _param("tickers_config", "--tickers-config", "股票配置 YAML"),
            _param("range", "--range", "时间范围", default="3mo"),
            _param("interval", "--interval", "采样间隔", default="1d"),
            _param("snapshot_id", "--snapshot-id", "快照 ID", required=True),
            _param("output_dir", "--output-dir", "输出目录", default="data/processed_private/market/raw_snapshots"),
            _param("timeout", "--timeout", "请求超时"),
            _param("sleep", "--sleep", "请求间隔"),
            _param("fail_on_missing", "--fail-on-missing", "缺失时报错", kind="bool"),
        ],
        output_parameters=["output_dir"],
        timeout_hint_s=900,
    ),
    "market_download_fmp_historical": _step(
        "market_download_fmp_historical",
        "Market",
        "下载 FMP 历史行情",
        "下载 FMP 稳定日线行情。真实 API key 只通过环境变量名读取。",
        "scripts/market/09_download_fmp_historical_snapshot.py",
        [
            _param("tickers", "--tickers", "股票代码"),
            _param("benchmark_tickers", "--benchmark-tickers", "基准代码", default="SPY,QQQ"),
            _param("tickers_config", "--tickers-config", "股票配置 YAML"),
            _param("from_date", "--from-date", "开始日期"),
            _param("to_date", "--to-date", "结束日期"),
            _param("lookback_days", "--lookback-days", "回看天数", default="100"),
            _param("snapshot_id", "--snapshot-id", "快照 ID", required=True),
            _param("output_dir", "--output-dir", "输出目录", default="data/processed_private/market/raw_snapshots"),
            _param("api_key_env", "--api-key-env", "FMP key 环境变量", default="FMP_API_KEY"),
            _param("base_url", "--base-url", "FMP base URL"),
            _param("timeout", "--timeout", "请求超时"),
            _param("sleep", "--sleep", "请求间隔"),
            _param("fail_on_missing", "--fail-on-missing", "缺失时报错", kind="bool"),
        ],
        output_parameters=["output_dir"],
        timeout_hint_s=900,
    ),
    "market_build_events": _step(
        "market_build_events",
        "Market",
        "生成事件窗口",
        "从 SEC manifest filing dates 生成市场事件窗口输入。",
        "scripts/market/08_build_market_events_from_sec_manifest.py",
        [
            _param("manifest_paths", "--manifest-paths", "SEC manifest 路径", required=True),
            _param("output", "--output", "输出事件文件", required=True),
            _param("tickers", "--tickers", "股票代码"),
            _param("tickers_config", "--tickers-config", "股票配置 YAML"),
            _param("years", "--years", "年份"),
            _param("form_types", "--form-types", "文件类型", default="10-Q,10-K"),
        ],
        output_parameters=["output"],
    ),
    "market_enrich_valuation_fmp": _step(
        "market_enrich_valuation_fmp",
        "Market",
        "补充 FMP 估值",
        "给市场日线快照补充 FMP 估值字段。真实 API key 只通过环境变量名读取。",
        "scripts/market/07_enrich_market_snapshot_valuation_fmp.py",
        [
            _param("input", "--input", "输入行情 CSV", required=True),
            _param("output", "--output", "输出 CSV"),
            _param("snapshot_id", "--snapshot-id", "快照 ID", required=True),
            _param("tickers", "--tickers", "股票代码"),
            _param("tickers_config", "--tickers-config", "股票配置 YAML"),
            _param("benchmark_tickers", "--benchmark-tickers", "基准代码", default="SPY,QQQ"),
            _param("api_key_env", "--api-key-env", "FMP key 环境变量", default="FMP_API_KEY"),
            _param("base_url", "--base-url", "FMP base URL"),
            _param("valuation_endpoints", "--valuation-endpoints", "估值端点", default="key_metrics_ttm"),
            _param("timeout", "--timeout", "请求超时"),
            _param("sleep", "--sleep", "请求间隔"),
            _param("fail_on_missing", "--fail-on-missing", "缺失时报错", kind="bool"),
        ],
        output_parameters=["output"],
        timeout_hint_s=900,
    ),
    "market_normalize_snapshot": _step(
        "market_normalize_snapshot",
        "Market",
        "规范化市场快照",
        "把 CSV/JSON/JSONL 行情快照规范化为统一离线 market snapshot artifact。",
        "scripts/market/10_normalize_market_snapshot_fixture.py",
        [
            _param("input", "--input", "输入文件", required=True),
            _param("output_root", "--output-root", "输出根目录", default="data/processed_private/market/snapshots"),
            _param("snapshot_id", "--snapshot-id", "快照 ID", required=True),
            _param("as_of_date", "--as-of-date", "截至日期", required=True),
            _param("provider", "--provider", "数据来源", default="yahoo"),
            _param("tickers", "--tickers", "股票代码"),
            _param("benchmark_tickers", "--benchmark-tickers", "基准代码", default="SPY,QQQ"),
            _param("currency", "--currency", "币种", default="USD"),
        ],
        output_parameters=["output_root"],
    ),
    "market_build_catalog": _step(
        "market_build_catalog",
        "Market",
        "构建市场快照目录",
        "为市场快照 artifacts 构建 DuckDB catalog。",
        "scripts/market/20_build_market_snapshot_catalog.py",
        [
            _param("output_root", "--output-root", "市场快照根目录", default="data/processed_private/market/snapshots"),
            _param("catalog_path", "--catalog-path", "catalog 路径"),
        ],
        output_parameters=["catalog_path"],
    ),
    "market_compute_analytics": _step(
        "market_compute_analytics",
        "Market",
        "计算市场指标",
        "计算收益、波动、回撤、相对表现和事件窗口指标。",
        "scripts/market/30_compute_market_analytics.py",
        [
            _param("output_root", "--output-root", "市场快照根目录", default="data/processed_private/market/snapshots"),
            _param("snapshot_id", "--snapshot-id", "快照 ID", required=True),
            _param("bars", "--bars", "bars 文件"),
            _param("snapshot", "--snapshot", "snapshot 文件"),
            _param("output", "--output", "输出 analytics"),
            _param("window", "--window", "窗口", default="3m"),
            _param("benchmark_ticker", "--benchmark-ticker", "基准代码", default="SPY"),
            _param("tickers", "--tickers", "股票代码"),
            _param("events", "--events", "事件窗口文件"),
        ],
        output_parameters=["output"],
    ),
    "market_build_evidence_pack": _step(
        "market_build_evidence_pack",
        "Market",
        "生成市场证据包",
        "把市场快照和 analytics 压成 Agent 可消费的 market evidence rows。",
        "scripts/market/40_build_market_evidence_pack.py",
        [
            _param("output_root", "--output-root", "市场快照根目录", default="data/processed_private/market/snapshots"),
            _param("snapshot_id", "--snapshot-id", "快照 ID", required=True),
            _param("analytics", "--analytics", "analytics 文件"),
            _param("snapshot", "--snapshot", "snapshot 文件"),
            _param("output", "--output", "输出 evidence pack", required=True),
            _param("window", "--window", "窗口", default="3m"),
            _param("tickers", "--tickers", "股票代码"),
            _param("max_rows", "--max-rows", "最大行数"),
        ],
        output_parameters=["output"],
    ),
    "market_validate_snapshot": _step(
        "market_validate_snapshot",
        "Market",
        "校验市场快照",
        "校验市场快照、analytics 和报告是否满足主链路消费要求。",
        "scripts/market/50_validate_market_snapshot.py",
        [
            _param("output_root", "--output-root", "市场快照根目录", default="data/processed_private/market/snapshots"),
            _param("snapshot_id", "--snapshot-id", "快照 ID", required=True),
            _param("snapshot", "--snapshot", "snapshot 文件"),
            _param("analytics", "--analytics", "analytics 文件"),
            _param("window", "--window", "窗口", default="3m"),
            _param("report", "--report", "校验报告"),
        ],
        output_parameters=["report"],
    ),
    "industry_download_source_snapshot": _step(
        "industry_download_source_snapshot",
        "Industry",
        "下载行业来源快照",
        "下载并规范化行业来源 family 快照。外部 API key 仍通过环境变量读取。",
        "scripts/industry/10_download_industry_source_snapshot.py",
        [
            _param("contract", "--contract", "行业来源合同", default="configs/industry_data_api_contracts_v0_2.yaml"),
            _param("snapshot_id", "--snapshot-id", "快照 ID", required=True),
            _param("as_of_date", "--as-of-date", "截至日期", required=True),
            _param("output_root", "--output-root", "输出根目录", default="data/processed_private/industry/source_snapshots"),
            _param("timeout_s", "--timeout-s", "请求超时"),
            _param("sleep_s", "--sleep-s", "请求间隔"),
            _param("max_rows_per_series", "--max-rows-per-series", "单序列最大行数"),
            _param("skip_live", "--skip-live", "跳过实时下载", kind="bool"),
        ],
        output_parameters=["output_root"],
        timeout_hint_s=900,
    ),
}
