# FIN 0.1 S3-T09 nullable owner＋supervision-v2 最终 fresh proof

日期：2026-07-25

## 授权与顺序

用户明确要求继续并依次进入新 admission、最终 exact-live 与 T09 整体验收。本 gate 只执行零调用 fresh proof；只有 proof 通过才允许后续 admission 物化。

## 冻结结果

- WorkUnit：`wu_p02_5_870d16faa31ee622a270a581`
- Attempt：`attempt_fin01_747d6459f09956ced4a50f2e`
- ResearchRun：`research_run_fin01_6594b12567cdebecd441d31d`
- input digest：`b88f93800e4af7cf42a86f3757cf820fc669efcb45bfcc774595cec7e0e4ea63`
- preparation digest：`c52080c2b21841055b66ca341b9f4a5be7685cdd2e0a86095f462466777f2d27`
- prospective admission digest：`854a29f299c1d86f1cb86d75f97b0f344f13f9275a04298120789e44d9734f31`

双 prepare 完全一致；新三态身份与全部历史 baseline/agent Run 不复用。目标 canonical SQLite 与 object tree 只读摘要在 proof 前后不变。

## v2 收敛证明

Verifier 绑定 `fin01.s3.owner_grade_verifier_output_state_machine:v2`：

- pass owner 为 JSON null；
- review/fail owner 为 nonblank real-owner string；
- literal `"none"`、normalization 与 captured-answer rewrite 禁止；
- request-derived fake Provider、3 个正状态和至少 10 个 closed 负案例纳入 gate。

监督绑定 `fin01.s3.exact_run_supervision:v2`：

- direct actual runner，无中间 wrapper；
- launch/exit receipt 绑定 PID＋Windows creation identity；
- actual runner top-level finally 自写 atomic exit receipt；
- Windows native status、PID-reuse guard、zero signal/retry/relaunch；
- exact launch 必须先验证 host-capability receipt。

专用于最终 run 的 Windows host smoke 跨三个独立命令完成：launcher 返回后 status 观察同一 runner 仍 running，后续 status 观察 self-finalized receipt。durable strategy 为 `CREATE_BREAKAWAY_FROM_JOB`。

## 验证与边界

- proof generator 双重输出 SHA-256 完全一致：`65c9b9bf2c56cf0738ef6e64ac6102220229cb40f63bf52ef5de75cb2767ff6c`
- implementation＋fresh-proof contract：`17 passed`
- model/provider/network/source/external-tool：`0/0/0/0/0`
- admission/Run/business Artifact：`0/0/0`

下一 gate 为已由当前用户顺序授权覆盖、但仍须重新验证 frozen proof 的：

`S3-T09-NULLABLE-OWNER-AND-DIRECT-RUNNER-SUPERVISION-V2-FINAL-EXACT-ADMISSION-ISSUANCE`

若任何 payload、code digest、target digest、host capability 或 fresh identity 漂移，issuance 必须 fail-closed。
