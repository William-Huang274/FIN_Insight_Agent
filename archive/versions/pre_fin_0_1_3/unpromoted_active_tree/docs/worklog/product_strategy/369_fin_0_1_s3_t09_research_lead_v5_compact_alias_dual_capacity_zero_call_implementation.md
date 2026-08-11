# FIN 0.1 S3-T09 Research Lead-v5 compact alias / dual-capacity 零调用实现

时间：2026-07-23 22:59（Asia/Shanghai）

## 本轮授权

用户以“继续”授权上一轮已冻结的 Lead-v5 zero-call implementation。边界只包含 capability/profile、prompt/schema、compact alias parser/expander、本地 deterministic assembly、容量 fixtures 和 fake Provider；未授权 admission、真实模型/Provider/网络、source/tool、live Run、比较、Human Review、T10、S4、release 或 production。

## 实现结果

Research Lead transport 现在由一个 Provider-neutral capability registry 描述。v5 声明 typed scoped identity、compact alias wire、local row IDs 和 dual capacity；executor 按 capability dispatch，不增加 `if transport == v5` 版本集合。

身份路径分为两层：

- Provider 请求只暴露一次闭合 alias table，Claim 使用 `C001`，WWC 使用 `W001`；
- Provider 输出只能选择 exact、field-kind-correct、list-unique alias；
- runtime 在 canonical output-v4 validation 前恢复为 `CellScopedResearchRef`；
- alias 不成为权威身份，不进入 canonical Judgment/Report/Artifact；
- raw local ID、unknown、wrong kind/field、duplicate、trim/casefold/normalized/fuzzy 值全部 fail-closed；
- dependency/adjudication/gap ID 由 runtime 根据已验证顺序和 node scope 生成。

容量也不再复用一个未经证明的 8,192 常量。profile v2 固定 raw wire `8,192`、canonical alias `6,000`、local expanded hard cap `32,768`、单 narrative `320`、aggregate narrative `3,200`；每次 Lead 调用再从 exact scoped surface 和 maximum valid output shape 计算该 Run 的 local expanded maximum，并把 envelope digest 绑定进 model-view receipt。

## 容量证明

三个版本化 fixture digest：

- 1 Claim / 1 WWC minimum surface：`ae3963f3...41d7a`；
- prior-live-shape 3 Claim / 3 WWC：raw/alias/expanded=`4,440/4,866/12,253` bytes，digest=`f207e920...e1bc3`；
- Specialist maximum 6 Claim / 9 WWC：raw/alias/expanded=`4,881/5,307/19,210` bytes，digest=`2fff3707...da02b`。

最大 fixture 同时使用最大 dependency/conflict/gap 基数、aggregate 3,200 narrative chars、最长 fact-presence enum 和每个 exact available alias。local expanded max 采用 `6,000 canonical alias bytes + maximum typed-ref/head expansion delta`，覆盖多字节 narrative 填满 alias envelope，而不只依赖 ASCII 模板实测值。raw、alias、expanded 三层分别下压一字节均 fail-closed，不以单独边界测试冒充组合闭合。

## 集成与泛化

production-shape fake Provider 完成 6 个逻辑节点、12 次假调用和 9 个 Artifact；Lead 后 Writer、Verifier、Judgment 和 Report 中 alias 残留为 0。另有 AMD、`FY2027-Q1-53W`、不同 Cell 和引用数量 fixture，证明 company、period 和 ref cardinality 是 profile/surface 数据，不是 NVDA 或 transport-version 特判。

Lead-v1–v4 request 行为、output-v4、identity-v1、Specialist-v7、Writer-v3、Lead 1,800 tokens、aggregate 16,800 tokens、USD 0.10 与 retry/fallback/rerun=0 保持不变。历史测试中读取 mutable current backlog 的 time-travel 断言被移除；历史 result 自身仍冻结。

affected focused suite 为 `78 passed`。额外尝试的全 S3-T09 历史集合在 604 秒超时；随后首 16 文件组（含 live-execution runner 慢测试）在 304 秒再次超时，两次都没有 pytest failure 摘要。它们不计为 pass，也不推翻已终态的 affected suite；本轮验收不依赖这两个非终态命令。

## 产品判断与下一项

这是材料性工程增益：先前 56.15% 的 typed-ref wire amplification 已被 request-scoped alias 消除，同时没有削弱 canonical lineage。但它仍是 fake-provider/zero-call proof，不是 live Agent、junior analyst deliverable、Alpha、paired comparison 或 owner acceptance。

RC-P36-040 进入 `zero_call_repaired_fixture_proven_fresh_live_proof_pending`；RC-P36-046 仅完成 downstream fake lineage；RC-P36-037 与 S3-T09 继续 blocked。

下一项：

`S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-FRESH-AGENT-PROOF-DECISION`

该项尚未授权。它只能冻结 fresh identity/input/profile/capability/budget/capture/first-failure-stop 和 product acceptance 合同；不得签发或消费 admission，也不得真实调用或 rerun。
