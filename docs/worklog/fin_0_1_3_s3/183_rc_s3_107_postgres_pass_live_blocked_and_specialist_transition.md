# RC-S3-107 PostgreSQL 通过、live 阻断与 Specialist 主线过渡

## 1. 本轮裁决

Owner 已明确要求停止把 K0–K6 继续扩写成新的协议工程。本轮只允许完成一次 PostgreSQL 资格验证和一个有限的 live 收口窗口；无论 live 结果是否通过，都要保留事实并回到 Dell 单 Specialist、真实模型和后续 multi-agent 纵切。

因此，`RC-S3-107` 不因本记录被宣告关闭。它继续阻断生产级自动重试、distributed exactly-once 与完整恢复能力声明；但不再阻断一次受控的 single-Specialist paid shadow。该 shadow 仍必须先有独立的 `PaidExecutionOwnerDecision` 与 task-specific `TokenBudgetBasis`，只允许一次启动、无 silent retry/fallback；任何 unknown outcome 都必须停止并转人工，不得自动重建远端 run。

## 2. 已完成的实现和数据库资格验证

主实现提交为 `845b45e0725aa2570e1335d14f387656c7422f44`。它复用现有 LangGraph Agent Server、FIN PostgreSQL identity repository 和 LangSmith，没有引入第二套 queue、backend 或 agent framework；新增 FIN-owned `PENDING / DISPATCHED / ORPHAN / RECONCILED` remote-create lifecycle、operator-only recovery disposition、唯一 pending 约束、v1.0→v1.1 installer/readiness 和 K0–K6 资格器。

最终冻结值：

- SQL 002 normalized SHA-256：`ddfb86ba54fcc6ca53af28fbf379511603863305496cf1690d552a953aee6b13`；
- v1.0 catalog SHA-256：`55e3fb20718a060605dd713bea5be7e063bd1afaf7bd460d6041a63eb13a7892`；
- v1.1 catalog SHA-256：`31c314f1d0d17cd91e252d4733a0eba35ae5725e85e56685a63081ba552f7bad`；
- PostgreSQL：16.15；catalog：268 rows；schema owner：`fin_runtime_migrator`。

真实 PostgreSQL 资格验证通过 absent→v1.1、exact v1.0→v1.1、v1.1 no-op、restart readiness、旧行兼容、final-binding 冲突拒绝、权限隔离、并发唯一 PENDING，以及 lifecycle 1、ActionAttempt 13、RecoveryCase 17、RecoveryDisposition 11、permission 2 组负例。生产样例持久化到 `PENDING→DISPATCHED→ORPHAN→RecoveryCase→DO_NOT_RETRY`；没有模型、HTTP 或外部研究调用。

作者分离只读审计在 live 前对 production/SQL/qualifier/harness 报告 `P0=0/P1=0`，并独立得到 `190 passed`。随后 live 暴露了审计未发现的 JSON 边界阻断，因此该审计只保留为实现静态/定向证据，不能外推为 K0–K6 live PASS。

## 3. live 收口窗口的不可变结果

三份 attempt 均在 Z 盘原位保留，不覆盖、不删除、不改写：

1. `rc-s3-107-a1-20260904t101822z`：`rc_s3_107_compose_config_failed`。Docker Compose 根据首个 compose 文件目录寻找默认 `.env`，没有读取仓库根 `.env`。没有创建容器，也没有执行 K 场景。
2. `rc-s3-107-a1-20260904t103039z`：`rc_s3_107_compose_start_failed`。镜像构建完成，Redis healthy；PostgreSQL 初始化因本地 bootstrap password 不满足部署脚本的 URL-safe 合同而退出。没有执行 K 场景。
3. `rc-s3-107-a1-20260904t104009z`：`rc_s3_107_runtime_case_contract_invalid`。Agent Server、PostgreSQL、Redis 均 healthy，LangSmith metadata 为 HTTP 204 且 `n_runs=0`；资格器在 K0 的远端调用前，把 JSON 中的 date/datetime string 和 authority list 交给 strict Python-mode `model_validate`，导致 canonical `date`、`datetime`、`tuple` 全部拒绝。没有 scenario receipt，不能形成任何 K0–K6 PASS。

前两项只做了最小启动修复并分别提交：`2fb8e25dcfb9fc750877cf24e2596b4cdcec3b56` 显式固定仓库 `.env` 且用内存临时角色密码；`1ab5af7e00d148413e4e9e7c08a59bbc12259f7a` 将隔离 qualification 的 bootstrap password 也纳入一次性、互异、URL-safe 内存凭据。用户 `.env` 未修改，密码未输出、未落 artifact。

第三项的最早责任层已经确定为资格器跨进程 JSON 反序列化，不是 Dell 数据、S1/S2、代理、Docker daemon、PostgreSQL lifecycle SQL 或 Agent Server 健康问题。未来如果重开该门，应使用 Pydantic JSON mode（例如对 canonical JSON bytes 使用 `model_validate_json`）并创建新 attempt；本轮按 Owner 硬停线不再修补或第四次运行。

准确结论为：

`POSTGRES_LIFECYCLE_V1_1_PASS_BOUNDED / LIVE_STACK_HEALTHY / K0_K6_NOT_QUALIFIED / QUALIFIER_JSON_BOUNDARY_BLOCKED / RC_S3_107_OPEN_BUT_NARROW_SHADOW_TRANSITION_OWNER_APPROVED`

## 4. 回到产品主线后的回归

锁定仓库 `.venv` 中只运行受影响范围：

- `tests/test_dell_specialist_agentic_graph.py` 与 `tests/test_dell_specialist_agentic_composition.py`：`30 passed in 4.17s`；
- 七个 S1/S2/MCP/data composition 测试文件：`103 passed in 11.60s`。

没有重复全仓回归。该证据只说明当前 fixed-Q1 scripted Specialist 与既有真实本地 Evidence/Finance MCP 数据组合没有被 RC-S3-107 改动破坏；provider/model/DeepSeek/paid calls 仍为 0，不证明 autonomous Specialist、multi-agent、报告或产品验收。

## 5. 下一合法动作

1. 复用现有 `DeepSeekStructuredAgentAdapter`、canonical `ActionAttempt`、Agent Server 与 LangSmith；禁止新增 provider SDK、direct-invoke production fallback 或第二套 runtime。
2. 把当前 fixed-Q1 Specialist 接入唯一 serving graph，保留真实 S1/S2 MCP、typed feedback、source-bound submission 与 fail-closed 数据合同。
3. 冻结 single-Specialist shadow 的 `PaidExecutionOwnerDecision` 和 `TokenBudgetBasis`：用途、实际输入规模、必需输出/schema、质量风险、可比较运行证据、reasoning profile、超时与停止条件都必须逐项写明；不得反推一个任意低 token/调用上限。
4. 只运行一次真实 DeepSeek Specialist shadow；保留 raw response、host validation、tool/action、LangSmith trace、token/耗时和 terminal receipt。失败不静默重试。
5. 只有该 shadow 证明模型能根据真实工具反馈自主规划和修正，才扩展 Lead 动态 DAG、并行 Specialists、Counter 定向回派、Verifier 与最终 Dell 报告。

