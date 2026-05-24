# 122 - SEC Agent Interactive Constrained Prompt Port

## Summary
- 时间：2026-05-21
- 目标：给用户提供自由命题交互入口，但每轮回答必须经过 SEC 检索、BGE-M3 rerank、runtime exact-value ledger、Judgment Plan、Qwen9B synthesis 和 deterministic post-gates，而不是裸模型 chat。
- 状态：已完成本地与云端脚本部署；RTX 5090 云端 smoke 通过。

## Work Completed
- 新增脚本：
  - `scripts/cloud/sec_agent_interactive.py`
  - `scripts/cloud/sec_agent_interactive.sh`
- 入口命令：
  - `bash scripts/cloud/sec_agent_interactive.sh chat`
  - `bash scripts/cloud/sec_agent_interactive.sh ask "..."`
- 运行链路：
  1. 从 prompt 或 `/scope` 推断公司和年份；默认使用 `NVDA,MSFT,GOOGL,AMZN,META,AMD` 与 `2023,2024,2025`。
  2. 调用 `scripts/run_sec_benchmark_eval.py` 生成 `pipeline_context`，BM25/ObjectBM25 作为 candidate generators，BGE-M3 作为 final selector。
  3. 从检索到的 structured objects 动态生成 runtime exact-value ledger。
  4. 调用 `scripts/build_sec_benchmark_judgment_plan.py` 生成 runtime Judgment Plan。
  5. 调用 resident vLLM OpenAI server 上的 `qwen9b`，要求输出 JSON。
  6. 写出 benchmark-like artifacts，并调用 `scripts/run_sec_benchmark_post_gates.py` 做 deterministic gates。
- UX 修正：
  - post-gate 和 context 子命令 stdout/stderr 默认静默，失败时才打印诊断，避免交互界面被大段 JSON 刷屏。
  - `MAX_TOKENS` 默认提高到 `2400`，降低 JSON 被截断导致 `qwen_answer_ratio` 失败的概率。
  - runtime ledger 过滤低信号 `% of net revenue` / `% of revenue` 泛化百分比行。
  - `data_center/cloud/advertising/subscription` 等具体收入 family 优先于泛化 `revenue`。

## Cloud Smoke
- Run ID：`20260521_sec_agent_interactive_runtime_ledger_qwen9b_5090_smoke`
- Remote artifact：`/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260521_012901_f1a4d86d5f`
- Command profile：`TICKERS=NVDA YEARS=2025 EVIDENCE_TOP_K=1 OBJECT_TOP_K=1 MAX_CONTEXT_ROWS=24 RERANKER_TOP_K=24 LEDGER_MAX_ROWS=12 bash scripts/cloud/sec_agent_interactive.sh ask "..."`
- Result：
  - `gates ok=True`
  - pass gates：12
  - fail gates：0
  - `qwen_answer_ratio=1.0`
  - ledger rows：2
  - context rows：10
  - elapsed：80.92 sec

## Interpretation
- 该入口已经不再是裸 Qwen chat；用户自由 prompt 会经过工程约束链路。
- 该入口不是 reviewed-gold benchmark case：exact-value ledger 是从当前检索到的 structured objects 运行时构建，已做 deterministic gates，但没有人工 reviewed-gold 背书。
- 当前 BGE-M3 默认走 CPU，因为 resident Qwen9B vLLM server 已占用 RTX 5090 大部分显存；这是为了保持交互入口可以在 Qwen server 常驻时稳定运行。

## Follow-Up
- 如果后续要把该入口变成更稳定的 demo 服务，可以增加：
  - prompt scope 预览和确认模式；
  - cached context/ledger for repeated prompts；
  - top-k 与 latency presets；
  - runtime ledger quality report；
  - 对自由 prompt 的 structured case classifier。

## 2026-05-21 Update - Full 30 Scope And GPU BGE-First Mode
- 问题：初版默认 scope 是 AI 六家公司，适合低延迟 smoke，但不符合用户希望自由命题时覆盖全 30 家 SEC universe 的交互需求；同时 resident Qwen9B 占用大部分 RTX 5090 显存，导致 BGE-M3 默认只能 CPU rerank。
- 决策：
  - 将默认 `TICKERS` 改为 `ALL`，由 manifest 自动解析全 30 家 10-K 公司。
  - 保留 `/scope TICKERS YEARS` 用于缩小范围；新增约定 `/scope ALL 2023,2024,2025` 显式恢复全范围。
  - 增加 BGE-first 模式：每轮 prompt 先 stop Qwen server 释放显存，`BGE_DEVICE=cuda` 跑 retrieval/rerank/ledger/plan，随后自动 start Qwen server 做 synthesis。
- 新入口：
  - CPU/常驻 Qwen 模式：`bash scripts/cloud/sec_agent_interactive.sh chat`
  - GPU BGE-first 模式：`bash scripts/cloud/sec_agent_interactive.sh chat-bge-first`
  - 单次 GPU BGE-first：`bash scripts/cloud/sec_agent_interactive.sh ask-bge-first "..."`
- 云端检查：
  - `python -m py_compile scripts/cloud/sec_agent_interactive.py` 通过。
  - `bash -n scripts/cloud/sec_agent_interactive.sh` 通过。
  - `--print-config` 确认默认 `tickers=ALL`。
- 注意：未主动停止用户当前前台 CPU BGE 任务；旧进程需要用户 `Ctrl-C` 后重启新入口才会使用更新后的默认 scope 和 BGE-first 策略。

## 2026-05-21 Hotfix - BGE-First Device Propagation
- 问题：`chat-bge-first` 虽然停掉了 Qwen server，但实际传给 `run_sec_benchmark_eval.py` 的仍是 `--context-reranker-device cpu`，所以 stage 1 仍然跑 CPU BGE，并且 `_run_context` 子进程输出被 capture，用户界面看起来像卡住。
- 根因：`sec_agent_interactive.sh` 中 `BGE_DEVICE=cuda` 在 process-substitution 子 shell 内设置，没有传播到 parent shell 的 Python 进程。
- 修复：
  - wrapper 在 BGE-first 模式下显式传 `--bge-device "$BGE_DEVICE"`。
  - Python 侧在 `--bge-first` 且未指定 `--bge-device` 时默认使用 `cuda`。
  - stage 1 输出改为 `rerank on <device>`，context 子进程改为 streaming，便于看到加载和完成状态。
  - stdout 设置 line buffering，避免远程非交互执行时子进程 JSON 抢在父进程阶段日志之前输出。
- 清理：终止了用户前台遗留的 CPU BGE `run_sec_benchmark_eval.py` 进程；确认 GPU 显存释放后再测试。
- 验证：
  - `python -m py_compile scripts/cloud/sec_agent_interactive.py` 通过。
  - `bash -n scripts/cloud/sec_agent_interactive.sh` 通过。
  - 云端 `ask-bge-first` 小范围 smoke 显示 `[1/5] ... rerank on cuda`，完成 retrieval 后自动拉起 Qwen server。
- Caveat：小范围 smoke 为了速度设置了 `MAX_TOKENS=900`，Qwen 输出被截断后走 ledger repair，因此 post-gates 未全绿；这只验证 BGE-first 启动与设备传参，不作为质量 run。正常交互保留默认 `MAX_TOKENS=2400`。

## 2026-05-21 Hotfix - Full30 Free Query Contract And Ledger Control
- 问题：用户在全 30 家 scope 下自由提问“AI 行业从 2023 到 2025 年的发展”时，链路完成了 SEC retrieval、BGE-M3 rerank、runtime ledger、Judgment Plan 和 Qwen 调用，但 Qwen 输出退化为 ledger fallback 风格，混入 AMAT/CSCO/META 等不相关或低信号 ledger 行，post-gates 失败：
  - `answer_ledger_gate_pass`
  - `v2_semantic_contract_gate_pass`
  - `answer_vs_judgment_plan_gate_pass`
  - `qwen_answer_gate_pass`
- 根因：
  - 自由 prompt 没有先被收束成稳定的 query contract，full30 会把非 AI 暴露公司和低信号表格一起送入计划。
  - runtime ledger 接受了地理收入、销售/营销费用、收购会计、成本类等低信号行。
  - Judgment Plan 对全 30 家问题过宽，Qwen9B 输出 JSON 容易被截断或偏离 top drivers。
  - caveat gate 需要结构化 caveat specs，旧版字符串 caveat 不利于 deterministic normalizer 自动补齐。
- 修复：
  - 增加 `plan` / `--plan-only` 预览入口，用于先打印 query contract、scope、facets、metrics。
  - AI 自由命题仍保留 full30 retrieval scope，但 planner 只把核心 AI exposure universe 收束到 13 家：
    `NVDA, AMD, AVGO, AMAT, MU, INTC, QCOM, MSFT, GOOGL, AMZN, META, ADBE, SNOW`。
  - AI task 的 `task_type` 改为 `ai_industry_financial_trend`，避免 semantic contract gate 误要求回答覆盖全部 30 家。
  - `MAX_TOKENS` 默认提升到 `4000`；Qwen prompt 限制最多 4 个 decision drivers 和 5 个 key points。
  - 对 interactive Judgment Plan 做 compact payload：AI full30 只给 top drivers、有限 metric/evidence ids 和 compact caveats。
  - runtime ledger 过滤低信号 rows：地理收入、sales/marketing、cost、acquisition/goodwill/intangible、R&D percentage、非 percent gross margin、非 capex proxy 等。
  - AI task runtime ledger 只保留 AI focus ticker，并限制总行数、每 ticker 行数和每 evidence object 行数。
  - 增加 AI focus structured supplement，从 structured object index 中补入高置信 segment revenue rows，尤其是 NVIDIA `Compute & Networking` / data center 类收入，避免 BGE top context 漏掉核心指标。
  - required caveats 改为结构化 specs，保证 deterministic normalizer 能补齐：
    - `SEC-only evidence boundary.`
    - `AI exposure differs by company; segment labels are not always directly comparable.`
    - `Precise values must come from runtime Exact-Value Ledger only.`
- 验证：
  - 本地 `python -m py_compile scripts/cloud/sec_agent_interactive.py` 通过。
  - 本地 `bash -n scripts/cloud/sec_agent_interactive.sh` 通过。
  - 云端同样完成 py_compile 和 shell syntax check。
  - 云端 `plan` 预览确认 full30 scope 与 AI focus13 contract。
  - 云端 ledger rebuild 确认 NVIDIA 行已补入，例如 `NVDA 2025 data_center_revenue NVIDIA 计算与网络分部收入 116,193（百万美元）`。

## 2026-05-21 Cloud Run - Full30 AI Free Query Hotfix
- Run ID：`20260521_sec_agent_interactive_full30_ai_free_query_hotfix`
- Prompt：`你看完这些财报之后你有什么感觉，尤其是AI行业从2023到2025年的发展，结合相关公司的财报指标谈谈你的看法`
- Command profile：`TICKERS=ALL YEARS=2023,2024,2025 bash scripts/cloud/sec_agent_interactive.sh ask-bge-first "..."`
- Remote artifact：`/root/autodl-tmp/FIN_Insight_Agent/eval/sec_cases/outputs/interactive_sec_agent/20260521_024409_b38c717195`
- Remote log：`reports/logs/sec_agent_interactive_full30_ai_hotfix_r2.log`
- Result：
  - `gates ok=True`
  - pass gates：12
  - fail gates：0
  - `qwen_answer_ratio=1.0`
  - ledger rows：16
  - context rows：360
  - elapsed：233.97 sec
- Output quality notes：
  - Qwen 输出已从 ledger fallback 恢复为可解析的 constrained answer。
  - 回答使用 runtime ledger 中的 AMZN AWS、META R&D、NVDA data-center proxy、AMAT gross margin 等指标组织观点。
  - caveats 已按 required specs 出现在答案中，post-gates 全绿。
  - 该 run 后又补了 NVIDIA 指标名展示修正，把 `Compute & Networking` 的中文展示改为 `NVIDIA 计算与网络分部收入`，避免 named-fact sanitizer 把英文 segment label 替换成泛化占位。该展示修正已做 py_compile 和 ledger rebuild 检查，但尚未重新跑一次完整 Qwen synthesis。

## Current Status
- 当前交互入口已经可以支持用户自由命题，同时走完整工程约束链路：
  SEC retrieval -> BGE-M3 rerank -> runtime exact-value ledger -> deterministic Judgment Plan -> Qwen9B synthesis -> deterministic gates。
- 对全 30 家、2023-2025、AI 行业趋势这个宽问题，最新完整云端 run 已全绿。
- 仍不是最终生产态：
  - full30 + BGE-first 单轮约 4 分钟；
  - runtime ledger 是运行时构造，不等同 reviewed-gold；
  - 需要继续做 cached retrieval / cached ledger 和更正式的 free-query planner 评测。

## 2026-05-21 Hotfix - User-Facing Interactive Display
- 问题：full30 AI free-query run 虽然 `gates ok=True`，但终端输出直接打印内部审计字段 `metric_ids` 和 `evidence_ids`，导致用户看到的回答像 benchmark trace 而不是自然语言分析。
- 决策：artifacts 继续保留完整 `metric_ids` / `evidence_ids` 供 deterministic gates 和审计使用；终端交互层只展示用户可读内容。
- 修复：
  - `_print_answer()` 不再默认打印长 `metric_ids` / `evidence_ids`。
  - 新增 display formatter，将 metric ids 映射为短中文“依据数值”行，例如 `AMZN 2025 AWS (云业务收入): 128,725（百万美元）`。
  - 新增 SEC evidence 短引用，例如 `AMZN 2025 10-K Item 8`。
  - summary/key points/limitations 输出时清理裸 `INTERACTIVE_*` 内部 ID。
- 验证：
  - 本地 `python -m py_compile scripts/cloud/sec_agent_interactive.py` 通过。
  - 本地假数据渲染测试确认终端展示不再输出长 ID，artifacts 写出逻辑未改。

## 2026-05-21 Update - DeepSeek V4 Pro API Backend
- 目标：在保留本地 Qwen9B/vLLM 路线的同时，接入 OpenAI-compatible DeepSeek API，便于后续用更强模型测试同一套 SEC retrieval、BGE、ledger、Judgment Plan 和 gates。
- 实现：
  - `scripts/cloud/sec_agent_interactive.py` 新增 `--llm-backend qwen_vllm|deepseek|openai_compatible`。
  - DeepSeek 默认：
    - `BASE_URL=https://api.deepseek.com`
    - `CHAT_COMPLETIONS_PATH=/chat/completions`
    - `MODEL_NAME=deepseek-v4-pro`
    - `API_KEY_ENV=DEEPSEEK_API_KEY`
    - `REASONING_EFFORT=high`
    - thinking enabled unless explicitly disabled.
  - `scripts/cloud/sec_agent_interactive.sh` 新增：
    - `chat-deepseek`
    - `ask-deepseek`
  - API key 只从环境变量读取，不写入脚本、日志、worklog 或 model run ledger。
- 验证：
  - 本地 `python -m py_compile scripts/cloud/sec_agent_interactive.py` 通过。
  - 本地 `bash -n scripts/cloud/sec_agent_interactive.sh` 通过。
  - 云端已同步脚本；远端 py_compile 和 shell syntax check 通过。
  - 远端 `--print-config` 确认 DeepSeek backend 指向 `deepseek-v4-pro`，且只显示 `api_key_present=true`，不打印 key。
  - 极小 API smoke 在本地和云端均读超时，没有返回 401/404/400；接入路径已完成，但实际 API 响应需后续用更长 timeout 或服务侧状态继续验证。

## 2026-05-21 Follow-Up - DeepSeek API Timeout Root Cause
- 进一步诊断：
  - 本地 DNS/TLS/443 正常；无鉴权访问 `https://api.deepseek.com` 返回 401。
  - 带 key 调用 `/models` 成功，模型列表包含 `deepseek-v4-flash` 和 `deepseek-v4-pro`。
  - 带 key 调用 `/user/balance` 成功，确认 key 有效且余额可用。
  - 非流式 chat 在未显式禁用 thinking 时出现 `HTTP 200` 后只收到 1 byte，随后客户端读超时；控制台无消费符合“请求未完成”的表现。
  - 显式 `thinking: {"type": "disabled"}` 后：
    - `deepseek-v4-flash` 非流式/流式均约 1 秒返回。
    - `deepseek-v4-pro` 非流式/流式均约 1-2 秒返回。
- 结论：超时不是 key、余额、模型名或 path 错误；主要原因是 DeepSeek V4 默认 thinking enabled，短请求也可能长时间不完成。SEC 交互链路默认应关闭 thinking，必要时再手动打开。
- 修复：
  - DeepSeek backend 默认 `ENABLE_THINKING=0`。
  - API payload 默认发送 `thinking: {"type": "disabled"}`。
  - 只有用户显式 `ENABLE_THINKING=1` 时才发送 `thinking: {"type": "enabled"}` 和可选 `REASONING_EFFORT`。
  - 云端已同步；远端 config 确认 `enable_thinking=false`。
