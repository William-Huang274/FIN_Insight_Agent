# FinSight Workbench 快速开始

Workbench 是 FinSight-Agent 的本地工作台。它不是独立的新链路，而是把现有 CLI、配置、运行日志和产物检查包装成一个更容易操作的界面。第一版主要覆盖：导入运行配置、检查数据是否就绪、启动后台任务、跑单轮或多轮研究、查看已有运行产物。

## 1. 推荐启动方式

先安装 Python 依赖：

```bash
pip install -r requirements.txt
```

Windows 本地推荐直接使用封装脚本：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/workbench/run_workbench.ps1 -InstallNode
```

这个脚本会做四件事：

- 创建本地工作台数据目录 `data/workbench_private/`。
- 如果本机没有 `npm`，并且传入了 `-InstallNode`，会把官方 LTS Node 下载到 `.tmp_node/`。
- 安装并构建 Workbench 前端。
- 启动同源后端和网页入口。

启动后打开：

```text
http://127.0.0.1:8765/
```

如果已经安装好 Node/npm，可以省略 `-InstallNode`。如果只想启动后端并使用内置静态页面，可以加：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/workbench/run_workbench.ps1 -SkipFrontendBuild
```

WSL、Linux 或 macOS 可以用：

```bash
bash scripts/workbench/run_workbench.sh
```

## 2. 手动启动方式

下面是排障和开发时的手动步骤。

先安装 Python 依赖：

```bash
pip install -r requirements.txt
```

Windows 本地如果没有 `node` / `npm`，可以用仓库脚本下载官方 LTS Node 到忽略目录 `.tmp_node`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/workbench/install_node_local.ps1
```

脚本会输出 `NODE_HOME`。在当前 PowerShell 会话中把它加入 PATH：

```powershell
$env:Path = "<NODE_HOME>;" + $env:Path
```

然后安装前端依赖并构建：

```powershell
cd apps/workbench/frontend
npm install
npm run build
cd ../../..
```

构建产物位于 `apps/workbench/frontend/dist/`，该目录不进入 Git。没有构建产物时，后端会回退到内置页面；有构建产物时，会优先使用 React/Vite 前端。

## 3. 启动 Workbench

在仓库根目录运行：

```bash
python scripts/workbench/start_workbench.py --port 8765
```

然后打开：

```text
http://127.0.0.1:8765/
```

如果要做前端开发，可以另开一个终端：

```powershell
cd apps/workbench/frontend
npm run dev
```

Vite 开发服务默认运行在：

```text
http://127.0.0.1:5173/
```

它会把 `/api` 请求转发到 `http://127.0.0.1:8765`，所以需要先启动 Workbench 后端。

## 4. 导入配置

页面默认读取：

```text
configs/sec_agent_full_source_demo.env.example
```

这个文件不包含真实 API key。导入后，Workbench 会展示：

- 模型路由和模型名称。
- `API_KEY_ENV` 环境变量名。
- 来源策略。
- SEC 清单、BM25、ObjectBM25、source gap、市场证据路径。
- 市场快照编号和 `as_of_date`。

如果本地没有私有 SEC 数据或索引，检查结果会显示警告。这不是页面错误，而是在告诉你当前缺哪些数据产物。

点击“保存配置”后，配置会写入本地 SQLite：

```text
data/workbench_private/workbench.sqlite
```

该路径不进入 Git。页面刷新后可以从“已保存配置”区域重新加载。

导入配置后，建议在“数据包”区域点击“从当前配置生成数据包”。数据包会把 SEC 清单、BM25、ObjectBM25、8-K 缺口和市场证据路径整理成一个可读对象。后续页面优先展示数据包名称、公司数、来源组合和截至日期，展开后才看原始路径。

## 5. 构建本地数据

“数据构建”区域提供一组白名单步骤，避免用户在网页里手写任意命令。第一版支持：

- 下载 SEC 10-K / 10-Q 原文。
- 生成 SEC manifest。
- 切分 SEC 文本。
- 生成 EvidenceObject。
- 构建 BM25 索引。
- 构建 ObjectBM25 索引。
- 下载 8-K 业绩稿。
- 生成 8-K manifest。
- 合并 source gap。
- 下载 Yahoo / FMP 市场行情快照。
- 生成市场事件窗口。
- 补充 FMP 估值字段。
- 规范化市场快照、构建 catalog、计算 analytics、生成 market evidence pack、校验市场快照。
- 下载行业来源快照。

使用方式：

1. 选择一个构建步骤。
2. 填写必填路径或筛选条件。
3. 点击“预览命令”，确认脚本和参数。
4. 如果希望任务成功后更新数据包，勾选“任务成功后回填数据包”并选择目标数据包。
5. 点击“提交后台任务”，在运行日志里看 stdout 和状态。

下载类步骤默认建议先 dry-run，确认会抓哪些文件后再取消 dry-run 正式执行。生成类步骤不支持 dry-run，会直接按参数写入目标产物。

当前会自动回填数据包的步骤：

- `sec_build_manifest`：回填 SEC manifest。
- `sec_build_bm25_index`：回填 BM25 索引目录。
- `sec_build_object_bm25_index`：回填 ObjectBM25 索引目录。
- `sec_merge_source_gaps`：回填 source gap。
- `market_build_evidence_pack`：回填 market evidence pack。
- `market_normalize_snapshot` 和 `industry_download_source_snapshot`：回填数据包截至日期。

dry-run 任务不会回填数据包。

## 6. 接入自己的数据

复制示例配置到本地忽略文件：

```bash
cp configs/sec_agent_full_source_demo.env.example .env
```

然后把 `.env` 中的路径替换成自己的产物：

```text
MANIFEST_PATH=...
BM25_INDEX_DIR=...
OBJECT_BM25_INDEX_DIR=...
SOURCE_GAP_PATH=...
MARKET_EVIDENCE_PATH=...
MARKET_SNAPSHOT_ID=...
MARKET_AS_OF_DATE=...
```

如果已经有一套数据产物，推荐先按下面的规则给它起一个稳定名称：

```text
<市场>_<主题或范围>_<公司数>_<来源组合>_<截至日期>_v<版本>
```

例如：

```text
us_ai_full30_sec8k_market_20260522_v1
```

然后在 Workbench 里从配置生成数据包并保存。这样之后调试链路时只需要认数据包名称，不需要反复确认每个文件路径。

真实 API key 不要写进仓库文件，只在当前 shell 里设置：

```bash
export DEEPSEEK_API_KEY="<set-in-shell-only>"
```

Windows PowerShell：

```powershell
$env:DEEPSEEK_API_KEY="<set-in-shell-only>"
```

如果 Workbench 后端运行在 Windows，但希望完整链路在 WSL 里执行，可以在本地配置里加入：

```text
WORKBENCH_EXECUTION_SHELL=wsl
WORKBENCH_WSL_DISTRO=Ubuntu-22.04
WORKBENCH_WSL_REPO_ROOT=/mnt/d/FIN_Insight_Agent
PY=/path/to/wsl/python
BGE_MODEL=/mnt/d/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/<revision>
BGE_DEVICE=cpu
```

Workbench 会把非密钥配置传给 WSL。真实 API key 仍通过环境变量名传递，不写进命令行参数。Windows 环境变量默认不会自动进入 WSL，因此 Workbench 会在启动 WSL 任务时用 `WSLENV` 传递 `API_KEY_ENV` 指向的变量。WSL 里仍需要安装项目 Python 依赖，否则完整链路会在导入依赖时失败。

可以在 WSL 终端里创建项目专用环境：

```bash
cd /mnt/d/FIN_Insight_Agent
bash scripts/workbench/install_wsl_python_env.sh
```

脚本默认创建 `.tmp_wsl_venv`，该目录不进入 Git。也可以指定 WSL ext4 里的绝对路径，例如 `/home/<user>/venvs/finsight-workbench`。安装完成后，把脚本打印出的 `PY=...` 和 WSL 配置写入自己的本地配置。

如果 WSL 不能直接访问 HuggingFace，需要把 BGE 模型放在 WSL 可见路径，并设置 `BGE_MODEL`。例如模型在 Windows 的 `D:\hf_cache\...` 下时，WSL 路径应写成 `/mnt/d/hf_cache/...`。

## 7. 运行任务

“智能体会话”区域有三个入口：

- “运行本地冒烟检查”：不需要私有数据或 API key，只验证 Workbench 后台任务、状态持久化和日志读取是否正常。
- “启动单轮研究”：复用当前导入的配置，调用受控命令，例如 `ask-full-source-api`。
- “发送到当前会话”：复用 `tenant_id / user_id / session_id` 调用上下文会话 CLI，适合测试多轮追问和上下文恢复。

页面里的“本次运行 API key”只随本次请求传给后端子进程，不写入配置、SQLite 或仓库文件。也可以继续用 shell 环境变量设置 key；两种方式选一种即可。WSL 模式下，后端会通过 `WSLENV` 把 key 传给 Linux 进程，不会把 key 拼进命令行参数。

完整任务在 Windows 本地通常需要 Git Bash、WSL 或 Linux 环境，因为当前主链路仍复用 `scripts/cloud/sec_agent_interactive.sh` 和上下文会话 CLI。如果只想验证 Workbench 本身，先跑本地冒烟检查；如果要跑完整 SEC / 8-K / 市场快照链路，需要先准备数据产物、索引、BGE 模型路径和模型 API key。

任务启动后，页面会显示：

- 任务编号、任务类型和状态。
- 系统事件。
- 子进程 stdout 日志。
- 失败时的错误摘要。

如果完整链路输出中包含 `[artifacts] <run_root>`、`run_root:`、`sec_agent_state:` 或图运行 JSON 里的 `run_root`，Workbench 会在确认目录存在后把该目录记录到任务上。之后从运行列表重新打开这个任务时，可以直接查看对应的产物索引。

同样的日志也可以通过 API 读取：

```text
GET /api/runs/{job_id}
GET /api/runs/{job_id}/events
GET /api/runs/{job_id}/events/stream
```

## 8. 查看已有运行产物

如果本地已有一次运行，可以在“运行产物”区域输入目录，例如：

```text
reports/quality/<run_id>
```

Workbench 会检查并摘要展示：

- `query_contract.json`
- `sec_agent_state.json`
- `runtime_evidence_coverage_matrix.json`
- `runtime_exact_value_ledger.json`
- `runtime_judgment_plan.json`
- `post_gates/sec_benchmark_post_gates_summary.json`
- `qwen/rendered_answer.md`
- `run_data_fingerprint.json`
- `run_performance.json`

缺失项会显示为缺失或警告，方便判断这次运行停在哪个阶段。

## 9. 当前边界

- Workbench 第一版已经能导入配置、检查数据是否就绪、运行轻量后台冒烟检查、启动单轮研究、发送多轮会话、查看会话列表和历史轮次，并检查已有运行目录中的核心产物。
- 数据构建第一版已经接入 SEC / 8-K / market / industry 的受控步骤，部分步骤成功后可以自动回填数据包字段。
- 多轮入口仍是上下文会话 CLI 的受控封装；后续可以继续补中断恢复验证和评测页面。
- Workbench 不保存真实 API key；需要用户通过本次请求或 shell 环境变量提供。
- 完整链路质量仍取决于本地数据产物、索引、BGE 模型和 API 模型路由。
