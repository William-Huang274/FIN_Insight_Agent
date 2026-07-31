# 397 FIN 0.1 S3-T09 layered Verifier exact admission issuance

日期：2026-07-25

## 授权与边界

用户授权连续完成 exact-live 并返回 T09 最终结果。当前 issuance 步骤允许：

- 签发 frozen prospective admission；
- 后续通过 supervision-v2 exact-once 消费；
- terminal success 后执行只读 layered T09 assessment 与配对比较。

不允许自动 retry、fallback、patch、replay、relaunch、rerun、Artifact 合成或
owner acceptance 代签。

## 零调用签发过程

第一次签发器 reprepare 在通用 issuance renderer 处以
`KeyError: claim_fact_link_live_acceptance_contract` 安全停止。没有 admission、
Run、Artifact、模型或网络调用。最早 faulty artifact 是 fresh proof assembler
漏带上一 layered proof 已冻结的 ClaimFactLink live acceptance contract。

修复后：

- fresh WorkUnit / Attempt / ResearchRun 不变；
- target DB / object tree digests 不变；
- prospective admission digest 不变；
- proof 新 SHA256：
  `4feb47c0fa30ece49c78dcb6106197e297d7c834be4151f498648813191cc08e`；
- issuance 内再次完整 reprepare，关键 sections 全部相等。

## 签发结果

- Admission ID：
  `fin01-s3-t09-three-cell-deepseek-layered-verifier-typed-ref-finding-disposition-exact-admission-r1`
- Admission digest：
  `fdc5dab0a6045dce123fdee897f337638eb297d961b514cd52e44f1cbf6ac7c2`
- 状态：issued / unconsumed / execution not started
- 历史 ResearchRun：23 个，全部 nonreuse
- retry budget：0
- maximum calls：12
- maximum cost：USD 0.10

绑定合同包括 typed Claim refs、ClaimFactLink、profile-v4、output-v4、
Specialist-v7、Lead-v5、Writer-v3、Verifier state-machine-v2、
supervision-v2、host capability receipt 与七个 exact code digests。

## 验证

- proof + issuance tests：`12 passed`
- Project OS issuance preflight：`pass`
- model / Provider / network / source / tool / supervisor / Run / Artifact：`0`

## 下一步

`S3-T09-LAYERED-VERIFIER-TYPED-REF-AND-FINDING-DISPOSITION-FRESH-EXACT-LIVE-EXECUTION-AND-T09-FINAL-ASSESSMENT`

只能通过 supervision-v2 exact-once 消费；首个可信失败即终止整个 live，
不重新签发或重跑。
