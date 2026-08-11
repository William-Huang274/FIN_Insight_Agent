# 666 — FIN 0.1.3 S2-05 Experiment A fresh admission authority 决策

日期：2026-08-07
类型：`experiment governance / admission authority / zero-call qualification`
状态：`DELL issuance authorized / not issued / execution not authorized`

## 1. 决策目标

在 S2-05 dynamic runner 工程通过后，判断能否开始 Experiment A 的真实权限签发。该判断只审计资格，不签发 admission、不消费 shared ledger，也不调用 DeepSeek。

## 2. 审计证据

- branch=`codex/layered-data-source-expansion`，audited HEAD=`3aab9f0d…483b`；tracked/untracked clean，upstream ahead/behind=`0/0`；
- runtime/policy/entrypoint/blind input/shared ledger/implementation manifest 的物理 SHA 重新核对一致；
- blind input canonical digest=`55b47486…61688`；
- dynamic runner preflight=`zero_call_preflight_ready_admission_not_issued`；
- focused runtime＋prior authority=`34 passed`，当前全部 FIN 0.1.3 S2 named=`95 passed`；
- DeepSeek credential 只确认存在，未读取、输出或持久化正文；
- `LLM_GATEWAY_TRANSPORT_RETRIES` 当前 unset，但 runner 每次显式传 `max_transport_attempts=1`，不存在隐式 retry；
- Provider/model 没有在本轮重新 probe；此前 DeepSeek Pro 成功运行和当前 credential presence 是现有资格证据。

## 3. 发现并关闭的权限存储风险

runner 要求 admission 绑定 execution Git HEAD。如果把 admission JSON 本身提交进 Git，提交会改变 HEAD，形成自指式失配。该风险不应留到真实调用才暴露。

处置不是放宽 Git binding，而是把 admission 作为运行权限写入 Git 已忽略的 restricted root：

`.codex_runtime/fin013_s2_05/authorities/DELL`

这样 admission 在签发时绑定 then-current clean/synced HEAD，并可在本机持久审计；它不是 source/config，不进入 Git，也不能保存明文凭据。shared ledger 必须位于 disposable case runtime 之外。

## 4. Authority 决定

允许下一步只签发一份 DELL admission：

- `admission_issuance_authorized=true`；
- `maximum_new_admissions=1`；
- `authorized_case=DELL`；
- consumption、exact-live、模型/Provider/网络/MCP calls 均未授权；
- MU/NVDA 与 automatic next-case 均未授权；
- admission 最长有效期四小时；
- issuance 必须在本 decision commit/push 后，从 clean/synced descendant 执行，并重新核对所有冻结 SHA 与 credential presence；
- issuance 本身 0 Provider/network probe。

DELL 只有在后续独立授权的 exact-live 形成 coherent raw success 后，才有资格判断 MU authority。首个 material failure 停止，不自动 patch、retry、rerun 或启动下一案。

## 5. 边界与下一步

本决定没有产生 admission，也没有测试 DeepSeek 的分析、反证、机制综合或写作质量。RC-P36-140 仍由 S1 拥有，但 Experiment A 为零工具实验，因此不阻断 DELL 签发。

机器决定：`configs/releases/fin_ia_0_1_3_s2_05_experiment_a_fresh_admission_authority_decision_v1_0.json`。

下一项：

`FIN-0.1.3-013-S2-05-EXPERIMENT-A-DELL-FRESH-EXACT-ADMISSION-ISSUANCE`
