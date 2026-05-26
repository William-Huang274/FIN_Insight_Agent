# SEC Agent Demo 入口 v1

[English version](sec_agent_demo_entrypoints_v1.md)

## 公开仓库范围

保留在公开仓库：

- 源码：`src/`、`scripts/`、`configs/`。
- 小型测试和评测合同：`tests/`、`eval_sets/`、`docs/eval/`。
- 只包含路径和摘要的工程日志、模型运行账本：`docs/worklog/`、`reports/model_runs/`。
- 不包含私有披露文件、原始数据供应商输出和凭据的小型合成测试夹具。

保持私有或 ignored：

- SEC 原始数据和数据供应商结果：`data/raw_private/`、`data/processed_private/`。
- 搜索索引和模型缓存：`data/indexes/`、`data/models_private/`。
- 运行输出：`eval/`、`reports/quality/`、`reports/demo/`、`reports/logs/`。
- API key、SSH 密码、数据供应商令牌、`.env`、临时运行文件。

## 本地结构检查

这是公开仓库可直接运行的结构性检查入口。它使用本地测试夹具、确定性合同和非大模型主链路检查，不需要 API key。

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

更快的合同检查：

```powershell
python scripts/evaluate_sec_agent_resume_closeout_readiness.py `
  --skip-main-chain-case-suite `
  --skip-context-load-smoke `
  --skip-latency-profile
```

输出会写到 `reports/quality/resume_closeout/`，该目录被 Git 忽略。

## 完整数据演示

当运行环境已有私有 SEC / 8-K / 市场快照数据和模型 API key 时使用。API key 只通过环境变量注入；模型默认示例使用 DeepSeek，也可以通过 `LLM_BACKEND=openai_compatible`、`BASE_URL`、`MODEL_NAME` 和 `API_KEY_ENV` 切换到其他兼容接口。

```bash
export LLM_BACKEND=deepseek
export MODEL_NAME=deepseek-v4-pro
export API_KEY_ENV=DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY="<set-in-shell-only>"

bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"结合 SEC 10-K、最新 10-Q、8-K 业绩新闻稿和最近三个月市场快照，比较 NVDA、AMD、MSFT、AMZN、GOOGL 的 AI 基本面、管理层解释、市场反应和估值分歧。"
```

如果使用自己的数据源，把 `configs/sec_agent_full_source_demo.env.example` 复制到被 Git 忽略的 `.env`，修改其中的清单、索引、市场快照和模型路由路径，然后运行：

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"your research prompt"
```

完整的数据准备步骤见：[自有数据快速接入](../deployment/local_custom_data_quickstart.zh-CN.md)。

可选：运行完成后，把已保存的运行结果目录传给 readiness 聚合器，检查产物是否齐全：

```bash
python scripts/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

## 真实会话演示

用于双轮上下文管理演示。它会启动由会话记忆支撑的会话；后续追问复用同一个当前会话和证据引用。

```bash
export LLM_BACKEND=deepseek
export MODEL_NAME=deepseek-v4-pro
export API_KEY_ENV=DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY="<set-in-shell-only>"

bash scripts/cloud/sec_agent_interactive.sh session-full-source-api
```

会话内常用命令：

```text
/state
/context
/answer
/exit
```

## 演示叙事

第一版公开演示需要清楚展示这些边界：

- 用户问题是自由形式中文投研问题。
- 研究任务解析由受 schema 约束的 API 模型生成查询计划，再经过校验器检查。
- 多轮会话入口使用 OpenAI-compatible 工具/函数调用：模型选择高层工具，工具执行层（Tool Harness）负责真实执行、会话状态和产物引用。
- 研究任务解析器选择 SEC 10-K / 最新 10-Q / 8-K / 市场快照等证据层级。
- 工具链负责检索、财务数值台账构建、市场快照绑定、证据覆盖、分析框架、模型生成、规则校验和结果呈现。
- 后续追问复用会话记忆中的当前答案和证据引用，而不是启动无关的新运行。
- 结果呈现层明确标注 SEC 审计 / 未审计边界、公司发布的 8-K 边界，以及市场快照的 `as_of_date`。

## 当前非生产边界

- JSON-backed session state 适合演示和单进程评测，不适合多进程服务。
- 全信息源质量依赖私有数据和索引，但这些不会进入公开仓库。
- API 大模型输出速度由数据供应商和模型路由决定；P0 优化集中在非 LLM 的检索、台账、覆盖检查和会话开销。
- 市场快照是非实时数据，必须展示 `snapshot_id` 和 `as_of_date`。
