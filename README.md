# FinSight Agent — FIN 0.1.3

**从研究问题到可追问报告的金融研究工作台。** 当前动态研究实现位于下方开发分支；本页所在的 `main` 保留历史固定 Evidence Pack 基线，两者的启动方式与能力范围不同。

[查看当前产品与代码](https://github.com/William-Huang274/FIN_Insight_Agent/tree/codex/fin013-dell-s1-s2-product-bridge) · [架构与技术分工](https://github.com/William-Huang274/FIN_Insight_Agent/blob/codex/fin013-dell-s1-s2-product-bridge/docs/public/architecture.zh-CN.md) · [运行与验证](https://github.com/William-Huang274/FIN_Insight_Agent/blob/codex/fin013-dell-s1-s2-product-bridge/docs/public/quickstart.zh-CN.md) · [English](README.en.md)

当前开发实现包括动态多 Agent 研究、MCP 数据与计算工具、交叉审查、报告追问/修订、任务上传和来源绑定的四格式导出。真实前端发起的 Dell 案例已走过九个研究面并产出报告候选；最终内容与完整产品验收仍在进行，不能视作无人辅助一次成功或生产发布。具体实测范围和局限见[当前证据说明](https://github.com/William-Huang274/FIN_Insight_Agent/blob/codex/fin013-dell-s1-s2-product-bridge/docs/public/sharing-scope.md)。

`main` 中的历史工作台把 DELL、MU、NVDA 三个案例的公司身份、研究截至日和经复核 Evidence Pack 做不可变绑定，展示已接受/被拒证据及来源边界。以下命令仅运行这一历史基线；动态研究请使用上方分支及运行说明。

## main 历史工作台入口

- 研究产品：`http://127.0.0.1:8765/workspace`
- 运维控制台：`http://127.0.0.1:8765/operations`
- 健康检查：`http://127.0.0.1:8765/api/health`
- 当前案例 API：`/api/v1/research-cases`

旧 `/current`、`/next`、`/tasks` 和 `/cases` 只保留永久重定向；旧产品 API 返回带替代路径的 HTTP 410。历史代码和证明位于 `archive/versions/`，不会被当前应用加载。

## 启动 main 历史基线

```powershell
python -m pip install -r requirements.txt

cd apps/workbench/frontend
npm ci
npm run build
cd ../../..

python scripts/dev/run_workbench_backend.py --host 127.0.0.1 --port 8765
```

仓库不分发三份 reviewed Evidence Pack 的私有对象。只启动代码时，案例目录仍可读，但三个详情入口会明确显示“证据对象未挂载”，`/api/readiness` 返回 typed HTTP 503。要验收完整案例，请把包含 `workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/zero-call-r1/objects` 的数据根挂载为 `data/`，或在启动前设置 `FINSIGHT_DATA_ROOT`。凭据只放环境变量，禁止写入 Git。

## 验证 main 历史基线

```powershell
python scripts/engineering/verify_active_baseline.py --pretty
python scripts/engineering/build_archive_redirect_index.py --check
python -m pytest -q
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
