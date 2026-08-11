# FIN 0.1.3 严格主线重定基验收与迁移程序

日期：2026-08-11

状态：执行中；尚未授权归档或发布

机器合同：`configs/repository/fin_0_1_3_strict_mainline_rebaseline_acceptance_v1_0.json`

## 1. 为什么这不是普通代码整理

当前仓库的问题不是单纯“文件太多”，而是候选 proof、历史版本产品面、当前 Workbench、运维控制台和 release attempt 同时留在活动路径。它们各自可能有价值，但没有共同满足“谁是主线、谁消费谁、谁可归档”的退出条件。继续只增加一个新 service 或搬一批文件，会形成第五套表面。

本程序把用户要求翻译为一个可验证终点：FIN 0.1.3 形成唯一活动产品主线；有效历史能力被迁入主线或显式保留；被替代实现只有在消费者归零后才进入可追溯归档；最终从 `main` 工作树重新证明，而不是只在候选分支自证。

## 2. 当前事实

- 当前候选分支相对 merge-base 有 510 个独有提交；`origin/main` 也有 20 个独有提交。
- `main` 的独有工作包含 Workbench 运行维护、部署、压力测试、A6 检索与 Agent eval 以及公开架构文档；其中 4 个补丁已以不同提交身份进入候选分支，其余需要逐项裁决。
- Workbench 同时存在 `/current`、`/tasks|cases`、`/next`、`/legacy` 四套产品表面；另有运维功能混在旧根应用中。
- 第一条版本中立 S1 Evidence Pack API 已能真实读取 DELL、MU、NVDA，但没有 typed Case subject 和 UI consumer。
- 历史 P36、FIN 0.1.2、`r53_r60`、release-only runner 和大量 attempt tests 仍有活动引用，尚不具备安全迁移条件。
- 私有数据约 74 GiB，只允许通过明确 DataRoot 挂载复用；不得复制进新工作树伪造便携性。

## 3. 新基线的产品形态

### 3.1 两个入口、两种责任

- `/workspace`：唯一研究产品入口。展示当前 Case、证据、底稿、报告、审阅与 lineage；首个冻结能力是 DELL／MU／NVDA 的已审核只读 Case＋Evidence Pack。
- `/operations`：常驻运维控制台。负责 profile、source bundle、run、eval、trace、maintenance 和部署诊断；它不能冒充研究事实或产品验收。

旧 `/current`、`/next`、`/legacy` 只允许在迁移期作为显式兼容入口，最终必须重定向、410 或归档；不得继续拥有独立业务 Runtime。

### 3.2 有界承诺

本次重定基承诺“清晰、真实、可追溯的内部研究 Workbench”，不借代码整理顺便宣称：任意新公司全自动研究、完整估值与目标价、生产多租户、商业实时行情或无人审核发布。尚未完成的 PRD 能力进入显式 backlog，不允许以半接线按钮留在主产品面。

## 4. 唯一 Case 与 Evidence 绑定

活动 Case 必须具有 `entity_id`、`issuer_id`、法定名称、ticker、exchange 和 as-of。Case 与 Evidence Pack 通过独立 binding 绑定 case version、subject digest、pack case key、artifact digest、payload digest 和审核状态。

以下快捷方式永久禁止：

- 从用户 query 文本猜 ticker；
- 从 target ID 前缀猜披露主体；
- 把固定多公司 preview 绑定到任意 Case；
- 只按相同 ticker 就接受 cross-case artifact；
- UI 自己拼接数据路径或读取 release attempt 文件。

## 5. 活动代码边界

活动产品代码只允许依赖版本中立的 application service、domain contract、runtime port 和注册资源。`fin_0_1_2_*`、`p36_*`、`r53_r60_*`、R1/R2/R3 runner、admission、authority 和 terminal result 不得从活动 Workbench import graph 进入。

长期目录意图如下：

```text
apps/workbench/
  backend/
    api/                 # 产品 API 和运维 API 分组
    application/         # 版本中立 use cases
    domain/              # Case、Evidence、Review 等合同
  frontend/vite/src/
    product/             # /workspace
    operations/          # /operations
src/sec_agent/
  runtime/               # provider-neutral execution/control ports
  research/              # 检索、证据、判断、写作能力
  workbench/             # 运维基础设施
archive/versions/
  fin_0_1_1/
  fin_0_1_2/
  fin_0_1_3/attempts/    # 只读历史，不进入活动 import graph
```

该树是迁移目标，不是要求一次机械重命名所有模块。每次移动前必须先证明替代消费者存在、旧消费者为零，并生成 redirect manifest。

## 6. `main` 的语义整合

不能在最后使用 blanket `ours` 或 `theirs` 解决冲突。20 个独有提交按以下方式裁决：

1. patch-equivalent：记录已经由哪个新提交吸收；
2. current-superceded：证明当前实现覆盖原能力，保留测试或迁移说明；
3. promote：把仍有效且版本中立的能力移入新主线；
4. archive-history：只具有历史／报告价值的材料进入版本归档；
5. reject-with-reason：与安全、真实性或新边界冲突时显式拒绝。

每个冲突文件必须有上述一种 machine-readable disposition。Git 合并只负责建立祖先关系，不能替代语义审计。

## 7. 严格验收门

必须全部通过：

1. `main` 独有语义完成裁决；
2. `/workspace` 成为唯一研究主入口，`/operations` 与研究事实隔离；
3. DELL／MU／NVDA typed Case 与 digest-bound Pack 绑定通过 cross-case mutation；
4. 真实 UI 消费 current Case API，展示业务含义、不能推断的边界、引用和 gaps；
5. P36、FIN 0.1.2、`r53_r60` 产品消费者归零；
6. 所有移动都有 redirect manifest，历史失败证据不改写；
7. 活动 import graph 不再含版本／attempt 模块；
8. clean worktree 只通过 RuntimePathRegistry 或 fixture 读私有数据；
9. backend import、frontend build、活动测试、API integration、UI smoke、secret scan、zero-old-ref 全通过；
10. 三案人工业务可读性检查通过；
11. PRD、TECH、Project OS、代码图和归档表一致；
12. tag/freeze 后合并 `main`，并从 `main` 工作树重新运行验收和 push。

任何 required gate pending/failed 时，不得以“新基线”“FIN 0.1.3 冻结”或“main 已收口”对外描述。

## 8. 执行切片

1. 冻结本程序和差距账；
2. 提前整合 `main` 独有语义；
3. 建立 typed Case、Pack binding、产品 API 和 `/workspace`；
4. 把当前 Evidence、review、deliverable 消费逐步迁到版本中立服务；
5. 旧消费者归零后迁移历史代码／测试／文档；
6. 完整工程和业务验收；
7. 更新文档、冻结、tag、合并并推送 `main`。

每一切片单独提交、测试和记录。失败留在本切片修复；不会因为一次 proof 失败创建新版本，也不会以继续写 attempt runner 代替产品修复。

## 9. 当前停点

本文件只完成严格终点和迁移顺序的冻结。尚未归档、未改变产品路由、未调用模型、未复制数据，也未合并 `main`。下一项是对 `origin/main` 的独有提交建立逐项语义 disposition，并先吸收仍有效的 Workbench／Runtime 能力。
