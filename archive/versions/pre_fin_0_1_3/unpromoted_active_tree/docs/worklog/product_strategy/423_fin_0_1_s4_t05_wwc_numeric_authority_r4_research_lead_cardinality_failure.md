# FIN 0.1 S4-T05：R4 Research Lead remaining-gaps cardinality 硬失败

日期：2026-07-27

## 权限与停止线

用户授权一直执行到 R4 exact-live 终态，并只在 coherent success 与九 Artifact 成立后做 paired assessment。唯一一次 launch 经 supervision-v2 发出；自动 retry、fallback、replay、relaunch、patch 与 rerun 均未授权。

## 执行结果

- admission digest：`45eef7b1...354b8b`
- Run：`research_run_fin01_9f2cc1412a2fd495db65b8b4`
- WorkUnit / Attempt / Run：`failed / failed / failed`
- Artifact：`0`
- orphan：`false`
- model / Provider / execution network：`10 / 10 / 10`
- input / output / total tokens：`48,397 / 6,589 / 54,986`
- estimated cost：`USD 0.02004878`
- Provider latency sum：`93,011 ms`
- capture / restricted readback：`10 / 10`
- retry / fallback / replay / relaunch / rerun：`0 / 0 / 0 / 0 / 0`
- paired assessment：未执行
- DELL R2：未证明

runner PID `17848` 自行完成 terminalization，exit code=0；supervisor 只读监控，monitor mutation 与 signal 均为 0。

## RC-P36-060 Live 结论

三个 Cell 的九个 Specialist segment 都返回 `ok/stop` 并通过本地校验，三个 WWC segment 都越过共享 authority policy。R3 的 WWC Numeric authority-source drift 没有复发。

RC-P36-060 可关闭为：

`closed_R4_live_path_positive_evidence_before_new_failure`

这只证明修复后的 WWC 路径，不证明完整 DELL 产品。

## 新的最早失败

第十次 Research Lead 调用返回合法 JSON、`finish_reason=stop`，但 `remaining_gaps` 超过闭合合同上限：

- request-visible cardinality：`1..4`
- validator cardinality：`1..4`
- failure：`s3_bounded_research_lead_v3_cardinality_above_maximum`
- content-free excess count：`4`
- inferred observed count：`8`

因此当前不是 Prompt Schema 与 Validator 漂移。模型直接输出没有遵守显式基数合同，本地 validator 按现行 L1 closed-output structure 正确 fail-closed。

新增：

`RC-P36-061-s4-research-lead-remaining-gaps-cardinality-nonconformance`

## 层级验收与序列边界

是否应把 `remaining_gaps` 超量继续视为硬结构失败，不能在这次已消费 execution 中临时决定。下一项零调用 disposition 需要比较：

- 保持 hard cardinality，选择更可靠的结构化输出或 Provider route；
- 让模型只产出 gap atoms，由本地确定性排序/组装到最多四项；
- 仅在明确修订 layered acceptance 合同后，把非关键 excess 转为质量 finding；
- blocked closeout。

本轮不静默删项、不修改合同、不切模型、不重跑，也不进入 S4-T06。此前后传的 deterministic task identity、完整 WWC taxonomy 与跨阶段 unified identity redesign 继续留在后续序列。

## 固化验证

- 新 R4 failure-result contract：`5 passed`
- 完整 S4 contract regression：`163 passed`
- JSON / JSONL parse：通过
- 下一零调用 disposition 的 Project OS scoped preflight：`pass`，open blocker=`0`

## 下一步

`S4-T05-DELL-WWC-NUMERIC-AUTHORITY-SURFACE-R4-FIRST-CREDIBLE-FAILURE-ROOT-CAUSE-DISPOSITION-DECISION`

该步骤需要独立授权，且必须是零模型调用。
