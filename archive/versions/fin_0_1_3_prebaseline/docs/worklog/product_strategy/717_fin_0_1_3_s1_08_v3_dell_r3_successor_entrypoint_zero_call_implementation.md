# 717 — FIN 0.1.3 S1-08 v3 DELL R3 successor entrypoint 零调用实现

日期：2026-08-08
阶段：`013-S1-08-P2B`
状态：`zero-call engineering pass / clean commit preflight pending`

## 1. 目标与边界

本轮只实现 `S1_08_V3_DELL_R3_SUCCESSOR_ENTRYPOINT_ZERO_CALL_IMPLEMENTATION`。目标是把已经条件批准的 R3 权限变成一个可在后续 clean proof 中独立核验的执行入口；本轮不签发正式 admission、不访问来源、不执行 live，也不进入 ranking、MU/NVDA、DeepSeek 或 S3。

起点为 clean/synced `5f3654d62cc68eeabfc741579fa8a7b9a241d29c`，scoped Project OS preflight=`pass/open blocker 0`。直接 R3 live scope 在实现前后均被 RC-P36-156/157 阻断。

## 2. 复用边界与工程判断

旧 R2 module/runner 已被历史 clean proof 和 immutable terminal 绑定 source SHA，不能为了抽象复用而修改。否则会破坏旧证据链。因此 R3 使用独立 schema、module、runner、namespace 和 result path，只复用稳定的 candidate Runtime、capture-first adapter、object store 与 shared admission ledger。

这是一项有界重复，不是建立新的通用 successor 框架。当前只有 R3 一个新消费者，过早抽象会扩大共享控制面；若后续出现第二个同合同 successor，再在 S0/S5 评估通用化。

## 3. 实现内容

新增 R3 admission/terminal：

- admission schema=`fin_ia_0_1_3_s1_08_dell_r3_search_admission_v1_0`；
- terminal schema=`fin_ia_0_1_3_s1_08_dell_r3_search_terminal_v1_0`；
- contract=`fin_0_1_3.S1_08.DELL_current_search_R3:v1`；
- candidate contract 强制为 v3 relationship-budget contract；
- namespace/result 与 R2 分离。

admission 同时绑定 authority decision、immutable R2 result/evaluation、v3 independent proof、v3 catalog、proof 中全部 implementation source SHA、未来 clean preflight、R3 runtime/runner SHA 与 clean implementation commit。任一 object digest、file SHA、source map、commit 或预算漂移均 fail closed。

收口审计发现，把上述九组对象与 SHA 在 issue、校验、runner 和测试间逐项传递会形成新的维护迷宫。因此在不改变任何权限和预算的前提下，统一为 typed `R3AuthorityInputs`；admission 与执行端消费同一个绑定包。执行前还同时核对磁盘 catalog 的 byte SHA 与解析后 canonical object，避免“内存批准对象正确、实际执行文件已漂移”。这不是抽象成通用 successor 框架，只是消除 R3 内部重复参数面。

执行顺序为：纯本地 source/binding/contact/transport/ledger-path 校验 → shared ledger reserve → adapter/source network → partial/terminal object → shared terminal receipt。第一轮测试后发现 non-live transport 校验曾位于 reserve 后，会无意义消费 admission；已前移并增加回归，未发生正式 admission 或外部调用。

## 4. 验证

- focused R3 successor：`7 passed`；
- 全部 S1-08 contract：`70 passed`；
- compileall：pass；
- decision/R2/proof/catalog/source mutation：fail closed；
- catalog 仅增加空白造成的 byte drift：在 shared reserve 前拒绝；
- missing contact、non-live transport：均在 shared reserve 前拒绝；
- fake v3 exact-once：terminal 使用 v3 candidate contract、slot starvation=`0`、第二次消费拒绝；
- 旧 R2 runtime/runner SHA 与历史 clean preflight 保持一致；
- formal admission/network/model/provider/retry/live=`0/0/0/0/0/0`。

机器证据：

`configs/releases/fin_ia_0_1_3_s1_08_v3_dell_r3_successor_entrypoint_zero_call_implementation_v1_0.json`

## 5. 仍未完成与下一步

当前只是 working-tree engineering pass。尚未从 clean Git archive/fresh process 证明 R3 source SHA、依赖和完整合同，也没有生成可供正式 admission 绑定的 clean preflight artifact。

下一项固定为：

`S1_08_V3_DELL_R3_SUCCESSOR_CLEAN_ZERO_CALL_PREFLIGHT`

必须先提交并推送本实现，再从 clean commit 做 fresh proof。preflight 通过后仍需单独推进 Project OS allowlist 和一次 exact-live issuance；本轮不能直接运行 R3。
