# FIN 0.1 S4-T05 R8 typed failure envelope 与 exact-live 结果

日期：2026-07-28

范围：`S4-T05-DELL-R7-TYPED-POST-PROVIDER-FAILURE-ENVELOPE...` → R8 fresh proof / admission / exact-live

结论：failure observability 修复通过；R8 在更早的第三 Cell assembly byte-budget invariant 终止，未形成九 Artifact。

## 完成内容

- executor 持有共享 lifecycle observation，累计 usage receipts、restricted captures、observed counts 与 completed logical node receipts；
- adapter conversion、profile Artifact ref binding、profile validation 与 trace recording 不再把成功 Provider 账本降格成普通 `ValueError`；
- canonical failure allowlist 接纳 `fin01.bounded_agent.post_provider_failure_envelope:v1` 的 closed phase/code 和 safe node receipts；
- 原有 typed validator telemetry 在升级 envelope 时保留，不记录 raw provider body、private reasoning、credential、exception message 或 stack；
- historical R7 failure/admission/Run 不重写。

## 零调用验收

- focused implementation + historical disposition：`10 passed`；
- R8 proof/issuance：`2 passed`；
- fault path：12 usage receipts、12 restricted captures、6 completed logical nodes；
- canonical injected failure：0 business Artifact、0 retry；
- success fake：6 logical nodes、12 callbacks、9 exact Artifact types。

## R8 fresh proof 与 issuance

- WorkUnit：`wu_p02_5_34aab4541ef5fba6786e7f11`
- Attempt：`attempt_fin01_1ad5b38f49ed8b397c622be1`
- ResearchRun：`research_run_fin01_5c760354a6d2b009e5ce8acb`
- admission digest：`8c27de13be01652599ae656235d2b9f4168d9d1fbf51ad833de69011ac44c100`
- exact input digest：`affb9eb031b9b8f85573fc7077f69a09b35e88a3ab6687dcd85f921b68b983a0`

临时 clone 双 prepare 与 create-app 前后 execution counts 相等，Provider callback=0，目标 fresh identity 全部 absent。Project OS 与 exact runner preflight 通过，credential 只检查 presence，未输出或持久化值。

## exact-live terminal truth

- canonical：`failed / failed / failed`
- Artifact：0
- orphan：false
- model/provider/network：`9 / 9 / 9`
- input/output/total tokens：`41669 / 4613 / 46282`
- estimated cost：`USD 0.01407779`
- usage/capture/restricted readback：`9 / 9 / 9`
- retry/fallback/replay/relaunch/rerun：`0 / 0 / 0 / 0 / 0`
- supervision exit code：0，typed unhandled failure：null

九个 Specialist segments 都是 `status=ok`、`finish_reason=stop`。第三 Cell `bottleneck_counterevidence_and_what_would_change` 在 Provider 三段完成后的本地 assembly 阶段，以：

`s3_bounded_segmented_specialist_assembly_invalid:...:s3_bounded_specialist_output_byte_budget_exceeded:...`

fail-closed。Lead、Writer、Verifier 未调用。

## 处置边界

本轮证明 RC-P36-064 的 observation ownership 修复生效：canonical failure 保留 9 receipts、9 restricted captures、2 completed logical nodes 和 exact phase/code，不再出现 R7 的空 observation。

新登记 `RC-P36-065-s4-R8-bottleneck-specialist-assembled-output-byte-budget-exceeded`。当前证据没有持久化 exact assembled byte count，也没有证明是模型不遵循、合同固定开销、叙事密度或 capacity drift，因此不能直接扩容、截断或再跑。

由于没有 coherent successful nine-Artifact Run：

- paired assessment 未执行；
- owner acceptance 不具备资格；
- DELL R2 未证明；
- S4-T06 未进入。

下一项仅限零调用 root-cause disposition。dependency/conflict 全面原子化、Writer/Verifier atomization、general taxonomy 与 cross-provider matrix 继续传递到 S4-T10→S5，不重新塞回 T05。
