# FIN 0.1 S0 至 S4-T05 全链路产品审计与后续安排

日期：2026-07-28
状态：`R11 new L1 / program-level pivot selected / release blocked`

> 2026-07-28 R11 后续裁决：最终零调用收敛包和三案 full-fake 已通过，但唯一计划内 R11 在首个 Specialist 返回触发新的 numeric narrative L1；随后 failure telemetry allowlist 漂移又造成临时 orphan，已零调用收口。按本文件冻结的 stop rule，不执行 R12。T05 付费执行序列以“未通过、未 owner accepted、项目级阻断”结束。未执行的 `S4-H01` 临时标签已撤销，不新增长阶段；严格 schema truth kernel、local material owner 与 atomic terminal core 统一归入 `S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER`。T06 尚未进入，该门禁只允许一个另行授权的 zero-call 实现包和至多一个另行授权的 single-node canary，任一失败即停。

## 1. 审计结论

FIN 0.1 已经不是“只有文档和 Demo”的项目。它具备 canonical Case/Run/Artifact、Workbench、Evidence/Numeric/Workpaper/Report/Trace、真实模型链、失败终态、成本与调用收据，以及一个 owner accepted 的 NVDA 三 Cell R2 结果。

但它也还不是“可以稳定迁移到不同公司”的 Internal Alpha。DELL R10 已证明同一 Runtime 可以完成 6 个逻辑节点、12 次 Provider 调用和 9 个 Artifact，并且相对确定性 baseline 有明显分析增益；可是 material numeric truth 和公司身份仍可在 machine Verifier 全绿时出错。因此当前最准确的产品定位是：

> `internal engineering alpha with one owner-accepted anchor case; not yet transfer-qualified`

S4-T05 不应继续无限修补。下一步只允许一个最终的合同收敛实现包和一次 DELL R11；如果 R11 再出现新的 L1 问题，应诚实阻断并做 program-level 裁决，而不是自动进入 R12。

## 2. S0 至 S4-T05 阶段表现

| 阶段 | 已证明 | 未证明 | 审计判定 |
| --- | --- | --- | --- |
| S0：Foundation / Program baseline | Point01 Foundation Alpha、canonical state、rollback、PRD 与 release ladder | RG1 operational qualification、production authority | 基础通过，运行发布风险仍开 |
| S1：One-Cell Fixture | Workbench→Runtime→Trace/Artifact 主线连通；142 tests；7 Artifacts | 真实 Agent 质量 | 通过，但只限 fixture |
| S2：One-Cell Real Agent | DeepSeek segmented-v4 终态成功；9 Artifacts；owner accepted material gain | 多 Cell 与跨 Case | 通过，形成第一个真实 Agent 价值证据 |
| S3：NVDA Three-Cell | coherent 9 Artifacts、paired comparison、NVDA R2 owner acceptance | 多 Case 迁移、R3、release | Anchor Case 通过，但收敛轮次明显过多 |
| S4-T01 至 T04 | DELL/MU Case Pack、方法合同、shared Runtime injection；DELL 11 条官方路线、22 条 Numeric | paid cross-case quality | 数据与运行时入口通过 |
| S4-T05 | R10 全链成功；Agent 新增 6 Claims、8 WWC、3 dependency、3 conflict、4 selected gaps | 数值真实性、DELL identity、DELL R2 | Runtime 成功，产品 L1 失败 |
| S5 | 无 | RG1-RG5、release candidate | 尚未开始 |

## 3. 当前真正的产品能力

### 已经可信

- canonical WorkUnit / Attempt / ResearchRun / Artifact 终态与 lineage；
- retry-zero、首错停止、typed failure envelope、restricted capture；
- DELL 官方 source-grounded input；
- 三 Cell Specialist、Lead、Writer、Verifier 全链可以完成；
- Agent 相对确定性 baseline 有实质 actionability 增益；
- NVDA 已有一份 owner accepted R2。

### 仍不可信

- material number 在进入模型、Writer 和 Verifier后的端到端一致性；
- Case identity 在所有标题、导出和交付字段中的一致性；
- DELL、MU、NVDA 三案共用一套合同而不泄漏或回退到 ticker-specific 常量；
- machine Verifier 独立承担真实性判定的能力；
- 多 Case owner review 时间与编辑价值；
- FIN 0.1 release qualification 和 production readiness。

## 4. 为什么会“修来修去”

问题不是单一模型不遵循，而是系统长期把以下职责分散在不同版本和模块：

- 输入 schema；
- Provider-visible model view；
- Prompt schema；
- 本地 validator；
- fake Provider；
- Artifact assembler；
- Verifier projection；
- Workbench/Report delivery projection。

S2 和 S3 通过增加 transport/profile 版本逐步收敛，但没有同步把“一个 material field 只有一个 owner”贯彻到所有消费者。S4 换公司后，旧 S3/NVDA 假设便依次从 evidence role、Claim identity、Numeric membership、capacity、lineage、title 和 numeric rendering 暴露出来。

这说明当前主矛盾已经从“模型能不能跑”转为：

> 同一事实、身份和结构是否由唯一确定性合同拥有，并被所有节点消费。

## 5. 过程效率审计

S4-T05 从 R1 到 R10 共经历 10 次执行或启动尝试，其中 8 次产生付费 Provider 调用：

- Provider calls：70；
- total tokens：400,866；
- estimated cost：USD 0.12464695–0.15471250；
- 最终 R10 Runtime 成功，但 owner-grade L1 失败。

成本金额本身不大，真正的问题是研发反馈周期：很多错误本可通过 cross-stage deterministic mutation fixtures 在付费运行前发现。

治理表面也已经膨胀：

- 审计前 295 份 release JSON；加入本审计机器产物后为 296 份；
- 139 份 S3-T09 JSON；
- 69 份 S4-T05 JSON；
- 300 个 contract test 文件；
- 443 份 product-strategy worklog；
- 12,904 行 `bounded_agent_executor.py`；
- Specialist v1–v8、Research Lead v1–v6 同时存在。

这些资产提升了可追溯性，但当前已反过来增加状态漂移、重复字段和误读风险。

## 6. 当前产品风险排序

1. **L1 数值真实性**：精确 Numeric row 未完整进入 model view/Verifier，模型仍生成具体值，本地只检查 ref membership。
2. **L1 Case identity**：DELL 报告标题被本地代码写死为 NVDA。
3. **状态主账本漂移**：S3 已关闭，但 active backlog 的 `current_truth` 仍写 S3 in progress；root-cause ledger 的 blocker flag 未按后续实链证据收敛。
4. **exact-live 代替集成测试**：多轮付费运行逐层发现 schema/adapter/lineage 问题。
5. **单体与多版本负担**：主 executor 同时承载历史版本、当前组装、验证、telemetry 和 delivery projection。
6. **release slice 不可审阅**：当前 branch 有大规模跨阶段暂存，不是可回滚的 release candidate slice。

## 7. T05 最终收口

下一项仍沿用已经冻结的两个合同，不新增一套全节点架构：

- `fin01.s4.case_numeric_authority_projection_and_deterministic_rendering:v1`
- `fin01.s4.case_delivery_identity_projection:v1`

零调用实现必须一次覆盖：

- S4 flat 与 legacy Numeric row 归一；
- Provider 只选 numeric alias 与定性判断原子；
- 本地唯一渲染 material value/period/operator/unit/scale/sign；
- 每个 numeric-capable node 后与 Artifact commit 前独立重算；
- title 和所有 entity-bearing delivery fields 从 case-local identity 派生；
- Prompt schema、validator、fake Provider、telemetry 来自同一 policy；
- DELL/MU/NVDA 正例和 wrong value/period/unit/sign/ticker/cross-Cell 负例；
- 三案 full-fake 均达到 6 nodes / 12 callbacks / 9 Artifacts；
- legacy S2/S3 regression 不回退。

以下内容不再进入 T05：

- dependency/conflict/gap 的通用原子化；
- 整体 executor 重写；
- provider/model 矩阵；
- Writer 风格与叙事密度优化；
- MU、NVDA 新执行；
- release/production work。

## 8. 后续顺序

### 8.1 最后一个 T05 implementation bundle

完成上述两个合同与三案 mutation matrix。零 Provider 调用。

### 8.2 唯一计划内 DELL R11

只有 zero-call proof 通过后才签发 fresh admission，并执行一次 exact-live：

- L1 pass 且 Agent 继续优于 baseline：进入 owner acceptance，关闭 T05；
- 只有 L2/L3/L4 finding：登记后关闭 T05，不因普通质量债继续循环；
- 出现新的 L1：停止，不自动执行 R12；由用户决定 blocked、scope swap 或独立 shared-runtime hardening。

### 8.3 S4-T06 MU

复用同一冻结合同，目标是证明 transfer，不复制 T05 的十轮过程。默认一条 exact-live；最多允许一次独立授权的 blocker disposition。

### 8.4 S4-T07 NVDA

验证新合同不破坏已接受的 NVDA 主线，并判断是否具备 R3 candidate，而不是恢复 NVDA 特判。

### 8.5 S4-T08 至 T10

统一比较：

- L1 mismatch 数；
- cross-case identity leakage；
- Agent 对 baseline 的增益；
- owner edit/time value；
- 调用、token、cost、latency；
- Workbench 可审性与 trace 完整性。

完成 Human review、ledger reconciliation 和 S5 carry-forward。

### 8.6 S5

只做 Internal Alpha release candidate：

- RG1–RG5；
- exact artifact/config/test manifest；
- coherent Git commits 与 rollback；
- release 或 honest blocked decision。

不宣称 production readiness。

## 9. 当前决定

本节的审计时点决定已由 R11 实际结果按同一 stop rule 执行并 supersede。

R11 后冻结的一个 zero-call implementation bundle 已完成并消费上限。当前唯一下一项：

`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-FRESH-ENGINEERING-PROOF-AND-PROVIDER-CAPABILITY-BINDING-DECISION`

产品裁决为 `pivot`：

- T05 不是成功关闭，而是 R11 新 L1 后诚实阻断；
- 不允许 R12，也不以新名字复跑同一合同；
- 不把未解决的 truth contract 带入 MU T06；
- 这是 T06 readiness 门禁，不是 T05 延长、不是新 H01 阶段，也不代表已经进入 MU T06；
- truth kernel 只产 aliases/enums，material numbers、period、unit、sign、scope、identity 和 lineage 全由本地确定性 owner 渲染并独立复核；
- 可选叙事与 canonical truth 分离。无效叙事只能成为受限 rejected candidate 和 L3 finding，不能阻断已成立的 truth kernel，也不能伪装成原始 Provider 输出；
- 唯一 zero-call implementation bundle 已完成：DELL/MU/NVDA 均以 fake Provider 达到 6 nodes、12 callbacks、9 logical Artifacts；strict truth-kernel 每 Case 3 次严格 schema 调用，后续 9 次保留既有链；
- wrong alias、跨 Case alias、numeric mutation、extra text、missing capability 均在首个 Artifact 前 fail-closed；strict alias 绑定 Case numeric projection digest，不能用 `N001` 跨 Case 重放；
- registered 与 unknown/secret-like failure extension 均证明 atomic `failed/failed/failed`，保留 12 receipts/captures、0 Artifact、1 attempt；unknown 正文不持久化；
- 既有 S2/S3 admission digest 与 T05 numeric/identity 路径保持兼容；focused=`18 passed`，四文件回归=`52 passed`，真实 model/provider/network/admission/Run/business Artifact 均为 0；
- zero-call bundle 上限已消费，禁止自动第二修复包、逐字段补丁和 DELL R12；
- 下一项只允许独立 engineering proof 与 exact Provider capability/credential binding 决策，不允许 credential probe、canary、admission 或 MU T06 执行；之后最多一个另行授权的 single-node strict-schema canary。canary 失败即停，不 retry、不 provider hopping、不 full-chain；通过后才能另行申请 MU T06 exact execution。

### 2026-07-28 fresh engineering proof 与 capability binding 结果

独立复核确认冻结代码 binding 全部匹配，focused 两次均为 `18 passed`，组合回归 `52 passed`；但 DELL/MU/NVDA 三案 strict schema 均在 counterevidence alias array 使用 `uniqueItems`。OpenAI 官方当前 `gpt-5.6-sol` 模型页证明 Responses、Chat Completions 与 Structured Outputs 的 model-level 能力，Structured Outputs 指南却只把 `minItems/maxItems` 列为受支持的 array 约束，没有把 `uniqueItems` 列入已支持子集。因此 prospective `openai:gpt-5.6-sol` 只能作为 model-level candidate，不能签成当前 request-level capability binding。

本门禁决定为 `block_before_canary`：不读取凭据、不执行 canary、不签 admission、不进入 MU T06，也不把删除一个关键词包装为第二个自动修复包。新增 RC-P36-070，current next=`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-POST-PROOF-PROGRAM-SCOPE-REPLACE-OR-STOP-DECISION`，需另行授权一次性决定停止或 program-level scope replace。T05、DELL R2、S4、S5 与 release 状态均不提升。

### 2026-07-28 post-proof program scope-replace 决策

一次性决策选择 `scope_replace`。这不是继续扩展 T05，也不是给已消费的实现包追加字段补丁，而是重新划定 program contract owner：

- semantic truth-kernel、本地 validator、Prompt、fake Provider 与 mutation rubric 由同一 versioned owner 生成；
- exact Provider wire 经过显式 supported-subset compiler，只使用官方文档列明的结构关键字，不发送 `uniqueItems`；
- numeric 与 counterevidence alias 的唯一性、Case scope、enum、material rendering 与 L1 recomputation 继续由本地硬校验，任何重复或污染仍在 Artifact 前失败；
- 最多一个需另行授权的 replacement zero-call bundle，失败即停且无第三包；通过后 fresh proof 与最多一个 single-node canary 仍各需单独授权。

当前 next=`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SERVER-SUBSET-CONFORMANT-REPLACEMENT-MINIMUM-ZERO-CALL-IMPLEMENTATION`，尚未授权。RC-P36-070 未关闭，S4-T06 未进入，DELL R12、provider hopping、credential probe、canary、admission 与 MU 均禁止。

### 2026-07-29 replacement zero-call implementation 结果

唯一 replacement bundle 已完成。产品 L1 标准没有因 Provider schema 子集而降低：服务端只接收受支持结构 schema，本地继续拥有 alias uniqueness、Case scope、material rendering、identity 与独立 L1 recomputation。

DELL/MU/NVDA 的 server schema 均不含 `uniqueItems`；duplicate numeric/counterevidence alias 等负例仍在业务 Artifact 前硬失败，三案 full-fake 保持 `6/12/12/9`。focused=`33 passed`、shared-runtime 回归=`61 passed`，真实调用与执行写入均为 0。

该结果只到 `runtime_injected + fixture_proven`，不是 live binding 或 T06 transfer。current next=`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-REPLACEMENT-FRESH-ENGINEERING-PROOF-AND-PROVIDER-CAPABILITY-BINDING-DECISION`，需另行授权；只允许独立复算与 request binding 决策，不自动读取凭据、canary、admission 或 MU。

### 2026-07-28 replacement fresh proof 与 request binding 结果

独立复算通过：六个冻结 code/test binding 全部匹配，聚焦套件连续两次均为 `33 passed`；DELL/MU/NVDA server schema 只含冻结 compiler allowlist，object 全字段 required、`additionalProperties:false`，server 不含 `uniqueItems`，而本地 semantic uniqueness hard check 保持。

OpenAI 官方当前 `gpt-5.6-sol` 模型页确认 Responses 与 Structured Outputs 支持；Structured Outputs 指南确认本项目 exact wire 与 schema subset。由此 model-level capability 和 documented request-schema compatibility 均成立，但本轮未读凭据、未调用 Provider，所以 endpoint acceptance 与 live binding 仍未证明。

产品门禁只前移到 `single-node canary authority decision eligible`。T05 仍 blocked/not owner accepted，T06 未进入，DELL R12 禁止。current next=`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SINGLE-NODE-STRICT-SCHEMA-CANARY-AUTHORITY-DECISION`，需另行授权；该下一项只决定 canary 权限，不执行 canary。

### 2026-07-28 single-node canary authority 结果

已授权未来执行一次 exact-once provider-contract canary，但本轮没有调用 Provider。canary 只使用 DELL Demand truth-kernel 的一份 `/responses` strict-schema request，最大 1 次调用/transport attempt、512 output tokens、USD 0.05；不执行后续 Specialist segments、Research Lead、Writer、Verifier，不建立 WorkUnit/Attempt/Run，也不产生业务 Artifact。

成功只把 documented request binding 提升为 live provider capability evidence，不代表 DELL R2、MU T06 或产品质量通过。任何 preflight、credential presence、endpoint/model、schema、transport、parse 或 local semantic failure都立即停止，不 retry、不 provider hopping、不 full-chain、不自动 repair。

current next=`S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SINGLE-NODE-STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION`，已由 authority record 授权但尚未开始；T06 仍未进入。
