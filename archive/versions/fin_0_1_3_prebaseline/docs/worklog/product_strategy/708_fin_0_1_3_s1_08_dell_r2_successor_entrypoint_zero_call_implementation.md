# 708 — FIN 0.1.3 S1-08 DELL R2 successor entrypoint 零调用实现

日期：2026-08-08
阶段：`013-S1-08`
状态：`zero-call engineering pass / clean-commit preflight pending / no admission`

## 1. authority v1.0 的失败与纠正

successor 首轮测试没有进入 Runtime，而是在 admission issuance 前拒绝了 Q-H v1.0：其 `independent_proof_sha256` 实际填写的是 engineering proof 文件 SHA。语义决定没有变化，但机器绑定名实不符，因此 v1.0 记为 `superseded_unconsumed`；没有 admission、ledger reserve 或外部调用。

v1.1 分开记录 engineering proof SHA=`8c3a3129...edc1` 与 independent proof artifact SHA=`f107e9c6...1b22`。successor 只接受 v1.1。

## 2. successor 实现

- 新 admission/terminal schema、R2 contract、namespace 和 result path；不复用或覆盖 R1；
- admission 同时绑定 Q-H v1.1、independent proof canonical digest＋文件 SHA、engineering proof、v2 catalog、R1 terminal、implementation commit、nonce 和有效期；
- R1 terminal 不只比较声明 digest，还会移除附加 receipt/ref 后重算 terminal body，任何历史字段突变都在 issuance 前 fail closed；
- shared ledger 在 DNS 或 source fetch 前 reserve；runner 不再预解析 DNS，Codex synthetic range 仍由 transport 的严格 allowlist 控制；
- 单请求仍 `<=30s`，新增全案 300 秒 deadline wrapper；
- partial result、terminal capture、authority lineage 与 exact-once receipt 全部保留。

## 3. 零调用结果

- S1-08 focused/related=`52 passed`；
- compileall=`pass`；
- decision/proof/R1 mutation 均 fail closed；
- missing contact 在 ledger 前拒绝；
- fake R2 完整 terminal 且二次消费拒绝；
- network/model/provider/retry/admission=`0/0/0/0/0`。

下一步只允许把本实现提交推送，再从 clean commit 执行一次 successor zero-call preflight。通过前不得签发或执行 R2。
