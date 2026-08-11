# P38 Point 01：P01-G2 final baseline execution 前置核验 fail-closed

日期：2026-07-17

状态：`P01_G2_FINAL_BASELINE_EXECUTABLE_BRIDGE_REFREEZE_PENDING_INDEPENDENT_REVIEW`

## 目标与授权

total reviewer 已精确批准 candidate manifest/package/preflight/gate：

- manifest：`bda9f0abb3efb56b65ab1868982ed92a677df62d1e8dc6eed6a6660e250fa1e4`
- candidate：`bba3ce4bc30467b4997e2be71803e8bf01608411dae6dc0a27a60f6a02ac75f9`
- preflight：`e9c24dae75f2ecc9f50c431365ad3ec8f2efbdc37ee06297977d730dbb2e643b`
- gate：`755c2decbe0aaf808d19f0e4a13e076ebc5e4b95afbb91a09a1dd5c814235c33`

授权只允许为 `m2-a1-ai-semis-input` / `p01-baseline-separated-input` 创建一份 fresh、single-use authority/receipt 并执行一次 baseline；任何执行前 mismatch 必须 fail-closed。

## 只读核验结果

candidate 的 canonical validator 为 `pass`；四个 digest 可重算，candidate input count、Git-index match 和 working/index match 均为 `100`；fixed approval DB SHA-256 仍为 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`。

但 production-path compatibility 未通过：

1. 将 candidate 交给 `execution_package_contract()` 返回 `execution_package_schema_invalid`。candidate 不是 M2A1 v2.10 execution-package schema。
2. 唯一 P01 production runner [run_point01_p01_g2_1_execute_tranche.py](D:/FIN_Insight_Agent/scripts/engineering/run_point01_p01_g2_1_execute_tranche.py) 将 package、v2 family 和 authority issuance 固定为 historical P01/v2.10 artifacts，不能注入 candidate four-digest binding。
3. historical v2.10 package 的真实 `_verify_index_and_working_inputs()` 返回 `execution_git_index_hash_mismatch:configs/engineering_handoff/point01_m2_a1_adversarial_input_corpus_v1_1.json`。这正是 candidate 重新冻结、而旧 execution package 尚未重冻的 8 项 drift 之一。

没有为绕过这个分层契约冲突而新建 runner、修改 frozen candidate input，或复用 historical receipt。

## 计数与边界

- human approval / admission / receipt / namespace / runtime / baseline：全部 `0`
- negative case：`0`
- network / tool / model / provider success：全部 `0`
- fixed approval DB：仅 SHA-256 读取，前后不变；没有 fixed/business write 或 legacy authority change。

因此这不是业务 baseline failed，也没有 consumed receipt；独立审计已将它校正为 authority 创建之前的 **P1 当前主链兼容性阻断**。

## 后续决策

最小 bridge repair/refreeze 已获授权并完成，候选四件套未改写：

- bridge manifest=`d7904fb4ec7da8578abd7d47914c5ce073fa55d7035e6c58703ca29829525a6d`；
- outer baseline-only executable package=`06a3ef6b5f1d8677e79e81676131ae3b8e83fcd87f9ccaeb9ed911100360f879`；
- read-only bridge preflight=`0ad2c6f8e5c3d157dc0cf2adbbe7d7fadf1f8f894be4c755e2e33cd8e8fad659`；
- bridge gate=`cf35d48b1200d1d3b7df661add38335f89f77a6158d1115a6bcf1df4244a2b38`；
- derived inner v2.10 package=`4ca222da5dd5ab7991d258d49eb30a377e6c8f82e1a0885d8912567324d3d5e8`。

该 bridge 严格保持 P01 schema，新增的仅是 `candidate_bound_baseline_only_v2_10` mode；历史 baseline+negative mode 和 v2.10 lifecycle 不放宽。内层包使用 candidate 的 100 项 current staged hashes，更新 runtime-input canonical digests 与 namespace，真实 `preflight_exact_execution(..., admission=None)` 仅返回预期 `package_admission_required`。新 runner 要求 `--executable-package` 和 expected digest，不再固定 historical P01/v2 package；未来执行仍只能调用既有 v2.10 production kernel。三项 negative 都是 disabled/not-authorized。

本工作点只生成静态 bridge artifacts：human approval/admission/receipt/namespace/runtime/baseline/negative/network/tool/model/provider/fixed-business write 都为 0。不得在独立审核前签发 authority 或消耗最后一次 baseline。
