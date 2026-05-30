# FinSight Workbench 快速开始

Workbench 是 FinSight-Agent 的本地图形化工作台。第一版覆盖四个高频动作：导入运行 profile，检查当前数据源和索引是否足以支撑 Agent 链路，启动受控后台任务查看日志，以及检查已有 run 目录中的核心证据产物。

## 1. 安装依赖

```bash
pip install -r requirements.txt
```

Windows 本地如果没有可用的 `node` / `npm`，可以使用仓库脚本下载官方 LTS Node 到忽略目录 `.tmp_node`：

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

构建产物位于 `apps/workbench/frontend/dist/`，该目录不进入 Git。没有构建产物时，后端会回退到内置的无构建页面；有构建产物时，会优先服务 React/Vite 前端。

## 2. 启动 Workbench

在仓库根目录运行：

```bash
python scripts/workbench/start_workbench.py --port 8765
```

然后打开：

```text
http://127.0.0.1:8765/
```

前端开发模式可以另开一个终端：

```powershell
cd apps/workbench/frontend
npm run dev
```

Vite dev server 默认运行在：

```text
http://127.0.0.1:5173/
```

它会把 `/api` 请求代理到 `http://127.0.0.1:8765`，所以需要先启动 Workbench 后端。

## 3. 导入示例 Profile

页面默认使用：

```text
configs/sec_agent_full_source_demo.env.example
```

这个文件不包含真实 API key。导入后，Workbench 会显示：

- 模型路由和模型名称；
- `API_KEY_ENV` 环境变量名；
- source policy；
- manifest、BM25、ObjectBM25、source gap、market evidence 路径；
- market snapshot id 和 `as_of_date`。

如果本地没有私有 SEC 数据或索引，检查结果会显示 `warn`。这不是页面错误，而是在告诉你当前还缺哪些产物。

点击“保存 Profile”后，profile 会写入本地 SQLite：

```text
data/workbench_private/workbench.sqlite
```

该路径不进入 Git。页面刷新后可以从“已保存 Profile”区域重新加载。

## 4. 接入自己的数据

复制示例 profile 到本地忽略文件，例如：

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

真实 API key 不要写进 `.env` 样例或仓库文件，只在当前 shell 里设置：

```bash
export DEEPSEEK_API_KEY="<set-in-shell-only>"
```

Windows PowerShell：

```powershell
$env:DEEPSEEK_API_KEY="<set-in-shell-only>"
```

如果 Workbench 后端运行在 Windows，但希望完整 Agent 链路在 WSL 里执行，可以在本地 profile 里加入：

```text
WORKBENCH_EXECUTION_SHELL=wsl
WORKBENCH_WSL_DISTRO=Ubuntu-22.04
WORKBENCH_WSL_REPO_ROOT=/mnt/d/FIN_Insight_Agent
PY=/path/to/wsl/python
BGE_MODEL=/mnt/d/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/<revision>
BGE_DEVICE=cpu
```

Workbench 会把非密钥运行配置传给 WSL；真实 API key 仍只通过环境变量名透传。Windows 环境变量默认不会自动进入 WSL，因此 Workbench 会在启动 WSL job 时用 `WSLENV` 透传 `API_KEY_ENV` 指向的变量。WSL 里仍需要安装项目 Python 依赖，否则完整链路会在导入依赖阶段失败。

可以在 WSL 终端中运行仓库脚本创建项目专用环境：

```bash
cd /mnt/d/FIN_Insight_Agent
bash scripts/workbench/install_wsl_python_env.sh
```

脚本默认创建 `.tmp_wsl_venv`，该目录不进入 Git。也可以指定 WSL ext4 中的绝对路径，例如 `/home/<user>/venvs/finsight-workbench`。安装完成后，把脚本打印出的 `PY=...` 和 WSL 配置写入自己的本地 profile。

如果 WSL 不能直接访问 HuggingFace，需要把 reranker 模型放在 WSL 可见路径，并设置 `BGE_MODEL`。例如模型在 Windows 的 `D:\hf_cache\...` 下时，WSL 路径应写成 `/mnt/d/hf_cache/...`。

## 5. 运行本地 Smoke、单轮 Agent 和多轮 Session

“Agent 会话”区域有三个入口：

- “运行本地 Smoke”：不需要私有数据或 API key，只验证 Workbench 后台任务、状态持久化和日志读取是否正常。
- “启动单轮 Agent”：复用当前导入的 Profile，调用受控的 Agent 命令模式，例如 `ask-full-source-api`。
- “发送到当前 Session”：复用 `tenant_id / user_id / session_id` 调用 ContextManager 会话 CLI，适合测试多轮追问和上下文恢复。

页面里的“本次运行 API key”只随本次请求发送给后端子进程，不写入 profile、SQLite 或仓库文件。你也可以继续用 shell 环境变量方式设置 key；两者二选一即可。当前后端会把 key 放进子进程环境，WSL 模式下通过 `WSLENV` 传给 Linux 进程，不会把 key 拼进命令行参数。

完整任务在 Windows 本地通常需要 Git Bash/WSL 或 Linux 环境，因为当前主链路仍复用 `scripts/cloud/sec_agent_interactive.sh` 和 ContextManager CLI。如果只想验证工作台本身，先跑本地 Smoke；如果要跑完整 SEC/8-K/市场快照链路，需要先准备对应数据产物、索引、BGE reranker 模型路径和模型 API key。

任务启动后，页面会显示：

- job id、任务类型和状态；
- `system` 事件；
- 子进程 stdout 日志；
- 失败时的错误摘要。

如果完整 Agent 输出中包含 `[artifacts] <run_root>`、`run_root:`、`sec_agent_state:` 或 LangGraph JSON 里的 `run_root`，Workbench 会在校验目录存在后自动把该目录记录到 job 上。之后从运行列表重新打开这个 job 时，可以直接看到对应的 artifact index。

同样的日志也可以通过 API 读取：

```text
GET /api/runs/{job_id}
GET /api/runs/{job_id}/events
GET /api/runs/{job_id}/events/stream
```

## 6. 查看已有运行产物

如果本地已有一次 Agent run，可以在“运行产物”区域输入 run 目录，例如：

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

缺失项会显示为缺失或警告，便于判断这次运行停在哪个阶段。

## 7. 当前边界

第一版 Workbench 已能导入 profile、检查数据源 readiness、运行轻量后台 smoke、启动受控单轮 Agent job、发送多轮 session turn、查看 session 列表和 turn 历史，并检查已有 run 目录中的核心产物。当前多轮入口仍是 ContextManager CLI 的受控封装；后续会继续补更强的中断恢复验证和 eval runner 页面。
