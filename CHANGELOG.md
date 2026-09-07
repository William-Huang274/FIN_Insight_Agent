# 产品版本与迭代记录

本文件记录产品能力变化。FIN 产品版本、S0–S5 成熟阶段、合同 schema、报告版本与执行 attempt 分开编号；测试失败和报告改稿不会自动产生新产品版本。

## FIN 0.1.3 — 当前研究候选（2026-09-08）

状态：实现与开发资格证据可审阅；Owner 内容/产品验收待完成，尚非正式产品 release。

- 从历史固定 Evidence Pack 展示推进到可发起的动态多 Agent 研究：Lead 任务 DAG、九研究面、交叉审查、责任修订、综合与报告。
- 采用 LangGraph / Agent Server / PostgreSQL / Redis / MCP / LangSmith；FIN 保留研究合同、来源权威与薄适配。
- 增加短问答与深度追问、运行意见交接、停止、局部修订、原生版本与差异、文档图片上传及按需缓存视觉工具。
- 请求内清理旧工具输出，checkpoint/artifact 保留全文证据，按 ID 回读并复用已保存 CALC；自动摘要资格 HOLD，默认关闭。
- 全原生 run 分页累计 token、缓存、模型耗时和估费；保留未知结果，区分同名调用在不同 run 的身份。外部导入修订费用单列。
- 同一报告导出 MD / PDF / Word / PPT；计算表达式及操作数、来源与期间保留，PPT 图表可编辑。
- `--fresh-only` 可不挂载旧报告/专家答案启动新研究服务；仍需原始资料、凭据和配置。历史源码工作台缺私有证据时显式返回 readiness 503。

报告迭代：Dell v1–v3 及其失败/修订证据保留；当前 v4 含 54 处引用、3 张图表，经过宿主开发审阅和四格式渲染，等待 Owner 审阅。它包含模型修订及宿主修正，不代表无人辅助一次成功。NVIDIA/Micron 新问题是同一工作区内的有界问答资格，不是新增两家公司完整研究验收。

当前能力、复现与限制：[README](README.md)、[运行说明](docs/public/quickstart.zh-CN.md)、[证据说明](docs/public/sharing-scope.md)。详细执行事实保留在 [S3/190 工作日志](docs/worklog/fin_0_1_3_s3/190_dell_cost_external_and_interactive_delivery.md)。Hermes 评估不属于这次交付。

### 同版本历史基线

FIN 0.1.3 早期 main 是固定三案例 Evidence Pack 工作台；它证明只读证据展示与来源边界，不证明动态研究。历史代码与文档保存在 Git 和 `archive/versions/`。当前研究实现的合入属于同一产品迭代推进，不额外编造 0.1.4 或“已发布”状态。

## FIN 0.1.1 — internal honest-block（2026-07-31）

既有标签 `fin-0.1.1-internal-honest-block`，提交 `b1f216d0`，提交说明为冻结 internal honest-block 基线。保留当时失败边界与内部基线含义；本记录不追认其为完整产品成功发布。

## v0.1.0 — resume demo（2026-05-26）

既有标签 `v0.1.0-resume-demo`，提交 `ac692bcc`，提交说明为 SEC agent v0.1 resume demo。它是历史简历演示基线，不代表当前架构或能力。

未发现对应发行标签的版本不补造发布记录。公开分支收口应保留 main 与有真实基线意义的历史分支；删除临时开发引用前保全其提交，不重写既有失败历史。
