# FIN 0.1.2 S0 fresh clean-environment qualification 资格授权决定

日期：2026-08-02

任务：消费用户“继续”，完成 `FIN-0.1.2-S0-FRESH-CLEAN-ENVIRONMENT-QUALIFICATION-AUTHORITY-DECISION`；只签发一次未来 clean-environment qualification 权限，不在本项创建 package、启动 attempt、读取凭据或调用模型。

结果：`authorized once / not executed / S0 not passed / zero external calls`

## 1. 决策前事实

- S0-04 已有本地 engineering pass：current=`95 passed`、S0 compatibility=`147 passed`、三案例 zero-model=`31 passed`；
- RC-P36-090–096 仍需 clean package 与双 disposable directory 的真实证据，不能靠本机测试关闭；
- Project OS authority preflight 通过，missing/blocker=`0/0`，受限证据 digest=`e5c8288a...ce5d`；
- 计划输出目录、`.failed` 与 `.partial` 均不存在，clean qualification attempt/package 计数为 0。

## 2. 本轮主动发现并修复的问题

审阅 runner 时发现：旧 manifest 虽声明 `manifest_is_clean_environment_authority=false`，真实 CLI 却没有消费该字段；只要传入 `--output-root` 仍可能开始运行。这意味着授权当时只是文档声明，不是代码门禁，属于 S0-05 当前责任，不能留给后续阶段。

本轮增加了小型 fail-closed 边界：

- 真实 host qualification 必须由带 authority binding 的 manifest 启动；fixture/历史读取仍兼容；
- authority decision、manifest 和 current projection 通过去循环的 canonical projection digest 互相绑定；
- 固定 attempt ID、唯一离仓 output root、五项 source digest、version-neutral attempt contract、branch、clean worktree、HEAD=upstream 和 engineering-base ancestry；
- 任何摘要、路径、状态或 Git 条件漂移，都在创建 output/staging 目录前终止；
- 授权不包含凭据、模型、Provider、网络、业务链、自动 retry/replacement、S1 或 release。

为了不改写已经摘要绑定的 S0-04 snapshot，新增 current manifest R2.1 和 current projection R2；旧 R2/v2.0 文件继续保留当时的 engineering-pass/pending-authority 历史事实。另一个旧版本合并测试仍把 v2.0 路径写死并读取今天的 backlog/ledger，本轮将它改为从唯一 current backlog 指针解析 projection，避免再次制造 mutable-current drift。

## 3. 验证与边界

- 初始相邻回归：`21 passed / 4 failed`；四项失败是历史 mini manifest 缺新字段的兼容问题，已改为“字段缺失即未授权”，不修改旧文件；随后 `25 passed`；
- authority guard、旧清单拒绝、固定 output、manifest mutation：`4 passed`；
- authority 与相邻边界组合：`15 passed`；
- current R2.1 manifest selected suite：`99 passed`；
- current FIN 0.1.2/0.1.3 S0 compatibility：`151 passed`；
- superseded FIN 0.1.4-entry 合同仍可见为 `3 failed / 1 passed`，失败原因是它要求 living docs 和 ledger 尾行恢复已撤销的 0.1.4 current truth，因此不属于 current gate，也未被篡改为全绿；
- DELL/MU/NVDA zero-model regression：`31 passed`；
- strict JSON/JSONL validation：通过；
- credential/model/Provider/network/business calls：`0/0/0/0/0`；
- qualification attempts/packages：`0/0`。

以上只证明“只有冻结授权能启动资格运行”，不证明 clean package 已通过。RC-P36-090–096、S0、S1 entry、产品验收和 release 均未关闭。

## 4. 下一项

`FIN-0.1.2-S0-FRESH-CLEAN-ENVIRONMENT-QUALIFICATION-EXECUTION-AND-CLOSEOUT`

下一项应在本提交推送后、worktree clean 且 HEAD=upstream 时，只执行冻结的一个 attempt。成功后检查双 disposable parity、完整 capture/readback 与问题逐项证据，再决定 S0 closeout；失败则保留 `.failed` 结果，禁止原 attempt 重试和自动 replacement，先做项目级根因处置。
