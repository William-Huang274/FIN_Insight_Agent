# FinSight Agent — FIN 0.1.3

FinSight Agent 当前是一套可审计的本地金融研究工作台基线。它把 DELL、MU、NVDA 三个案例的公司身份、研究截至日和经复核 Evidence Pack 做不可变绑定，并在浏览器中明确展示可用证据、被拒证据、来源边界和剩余缺口。

当前版本刻意不把未来能力包装成已完成产品：它不是开放式 Agentic Research、实时行情终端或自动发布研报系统。动态规划、内外源补检、模型综合和完整报告仍属于 FIN 0.1.3 后续产品路线，只有通过对应研究质量验收后才能晋升。

## 当前入口

- 研究产品：`http://127.0.0.1:8765/workspace`
- 运维控制台：`http://127.0.0.1:8765/operations`
- 健康检查：`http://127.0.0.1:8765/api/health`
- 当前案例 API：`/api/v1/research-cases`

旧 `/current`、`/next`、`/tasks` 和 `/cases` 只保留永久重定向；旧产品 API 返回带替代路径的 HTTP 410。历史代码和证明位于 `archive/versions/`，不会被当前应用加载。

## 本地启动

```powershell
uv sync --locked

cd apps/workbench/frontend
npm ci
npm run build
cd ../../..

uv run --locked python scripts/dev/run_workbench_backend.py --host 127.0.0.1 --port 8765
```

Python 依赖只在 `pyproject.toml` 人工维护，并由 tracked `uv.lock` 固定；不要另建手工 requirements 文件。

仓库不分发三份 reviewed Evidence Pack 的私有对象。只启动代码时，案例目录仍可读，但三个详情入口会明确显示“证据对象未挂载”，`/api/readiness` 返回 typed HTTP 503。要验收完整案例，请把包含 `workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects` 的数据根挂载为 `data/`，或在启动前设置 `FINSIGHT_DATA_ROOT`。凭据只放环境变量，禁止写入 Git。

## 验证当前基线

```powershell
uv run --locked python scripts/engineering/verify_active_baseline.py --pretty
uv run --locked python scripts/engineering/build_archive_redirect_index.py --check
uv run --locked python -m pytest -q
```

前端验证：

```powershell
cd apps/workbench/frontend
npm run typecheck
npm run build
```

## 代码结构

```text
apps/workbench/        唯一浏览器产品与运维组合根
src/                   当前稳定领域、数据与运行时模块
scripts/               受控数据构建、启动和基线治理入口
tests/                 当前基线测试；不递归执行 archive
configs/runtime/       三个当前运行时资源和注册表
configs/repository/    当前活动图、生命周期和验收合同
docs/                  PRD、当前技术图、质量标准和 Project OS
archive/versions/      不可执行的版本历史与逐文件重定向索引
data/                  本地/挂载数据根；私有内容不进入 Git
```

详细边界见 [当前代码图](docs/architecture/repository/FIN_0_1_3_CURRENT_BASELINE_CODE_MAP_20260811.zh-CN.md) 和 [当前上下文包](docs/project_os/current_context_pack.zh-CN.md)。

## 数据与研究边界

- 当前公开基线不包含私有数据、API key、模型 capture、生成索引或报告运行产物。
- SEC、8-K、市场和行业脚本只负责受控数据准备；运行脚本不等于对应数据已完整可用。
- Evidence 只有通过身份、日期、来源和 digest 绑定后才能被当前 workspace 展示；当前三份 Pack 尚无结构化数值项，不能据此声称数值事实能力已完成。
- 历史失败保持不可变，但不能作为当前能力或发布通过的证据。

English: [README.en.md](README.en.md)
