# FinSight-Agent 演示入口

[English version](sec_agent_demo_entrypoints_v1.md)

这份文档只讲怎么体验项目，不展开架构细节。架构说明见 [架构文档入口](../architecture/README.md)，自有数据准备见 [自有数据快速接入](../deployment/local_custom_data_quickstart.zh-CN.md)。

## 公开仓库能直接做什么

公开仓库包含源码、测试、配置样例、评测合同和文档，但不包含私有数据、索引、运行产物或 API key。因此，克隆后可以直接做的是结构检查和本地合同检查；完整投研链路需要用户自己准备数据产物和模型路由。

公开仓库保留：

- `src/`、`scripts/`、`configs/`。
- `tests/`、`eval_sets/`、`docs/`。
- 小型测试夹具和不含凭据的配置样例。

保持私有或被 Git 忽略：

- `data/raw_private/`、`data/processed_private/`、`data/indexes/`、`data/models_private/`。
- `eval/`、`reports/quality/`、`reports/demo/`、`reports/logs/`。
- `.env`、API key、SSH 密码、供应商令牌和临时运行文件。

## 本地结构检查

这是克隆仓库后最先跑的检查。不需要 API key，也不需要私有 SEC 或市场数据。

```powershell
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py --timeout-s 600
```

如果只想快速检查本地合同，可以跳过主链路、压力检查和耗时分析：

```powershell
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py `
  --skip-main-chain-case-suite `
  --skip-context-load-smoke `
  --skip-latency-profile
```

输出会写到 `reports/quality/resume_closeout/`，该目录不会提交到仓库。

## 配置完整链路

完整链路需要三类前置条件：

1. SEC / 8-K / 市场快照等本地数据产物。
2. BM25、ObjectBM25、可选 BGE 等检索或重排索引。
3. API 模型路由，例如 DeepSeek 或其他 OpenAI-compatible 接口。

API key 只通过环境变量注入：

```bash
export LLM_BACKEND=deepseek
export MODEL_NAME=deepseek-v4-pro
export API_KEY_ENV=DEEPSEEK_API_KEY
export DEEPSEEK_API_KEY="<set-in-shell-only>"
```

复制配置模板到被 Git 忽略的 `.env`：

```bash
cp configs/sec_agent_full_source_demo.env.example .env
```

然后把 `.env` 里的清单、索引、市场快照和模型路由路径替换成本地路径。

## 单轮演示

单轮入口适合演示“一个问题从检索到备忘录”的完整链路。

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh ask-full-source-api \
"结合 SEC 10-K、最新 10-Q、8-K 业绩新闻稿和最近三个月市场快照，比较 NVDA、AMD、MSFT、AMZN、GOOGL 的 AI 基本面、管理层解释、市场反应和估值分歧。"
```

运行完成后，重点检查：

- 是否生成查询合同和研究范围。
- 是否真实触发 SEC 检索、ObjectBM25 和 BGE 重排。
- 是否生成数值台账和覆盖检查。
- 最终备忘录是否带来源边界和市场快照日期。
- 运行目录里是否有状态、台账和可检查产物。

## 多轮会话演示

多轮入口适合演示上下文复用、范围收缩、证据追问和已保存结果检查。

```bash
SEC_AGENT_PROFILE_ENV=.env bash scripts/cloud/sec_agent_interactive.sh session-full-source-api
```

会话内常用命令：

```text
/state
/context
/answer
/exit
```

可以这样体验多轮能力：

1. 第一轮生成一个公司比较或行业主题备忘录。
2. 第二轮要求“只保留 NVDA 和 AMD”或“只展开风险部分”。
3. 再追问某个数值、某条证据或覆盖缺口。
4. 用 `/state` 和 `/context` 检查系统是否复用了正确的会话状态和证据。

## 已保存运行检查

如果已经有完整链路运行目录，可以把它交给就绪检查器，检查产物是否齐全。

```bash
python scripts/eval_context/evaluate_sec_agent_resume_closeout_readiness.py \
  --saved-full-source-run-dir eval/sec_cases/outputs/<run>/<case> \
  --require-full-source-artifacts \
  --timeout-s 900
```

这个检查不会替代人工阅读备忘录，但可以帮助确认状态文件、覆盖矩阵、数值台账、市场快照边界和关键产物是否存在。

## 当前边界

- 完整链路质量取决于用户提供的数据产物和索引质量。
- 市场快照是离线数据，不是实时行情。
- 行业和关系数据支持研究假设，不等于已确认合同或客户事实。
- JSON 会话存储适合演示、开发和单进程评测；多用户服务需要替换为数据库、Redis 或带锁状态存储。
- 校验器负责挡住越界和缺证结论，但不会自动补足上游没有检索到的事实。
