# FIN 0.1 S2-T04 live Artifact 只读验收

## 问题与边界

用户要求继续 S2-T04。唯一 program backlog 将本任务限定为对 S2-T03 已关闭的同一 one-cell live Run 做 promotion、numeric、judgment、Writer 与四层 Verifier 验收；T05 Agent-vs-fallback material gain 和 owner product review、S3、release、production 均不在本轮权限内。T04 不签发 admission，也不调用模型、provider、source network 或外部工具。

## 实施

新增 `scripts/releases/run_fin_ia_0_1_s2_t04_validate_live_artifacts.py`，按 exact ResearchRun、Attempt、input digest 和 9 类 Artifact manifest 只读加载 canonical payload，并执行以下 fail-closed 合同：

- promotion 必须是 Run-scoped evaluation EvidenceVersion，finding refs 与 promoted candidate refs 完全一致，每条有 claim 和 boundary，禁止 live Evidence head promotion；
- numeric 必须保留 `demand_sustainability` typed gap、value=null 和明确 reason，禁止 unsupported precision；
- Specialist/Lead Judgment 必须消费 promoted evidence，保留 thesis、counter-thesis、remaining gaps 和 what-would-change；
- Workpaper 的 Evidence/Numeric/Judgment refs 必须绑定 exact canonical ArtifactVersion；
- Writer 必须 no-source/no-tool，所有 section refs 都在 promoted evidence 集合内，并保留 limitations；
- deterministic integrity、semantic fidelity、financial coherence、visual delivery 四层必须全部 pass，semantic/financial score 不低于 internal-review floor；
- trace 必须恰有 Specialist/Lead/Writer/Verifier 四张单 transport receipt；T05 owner review 和 material-gain acceptance 必须仍为未执行。

## 根因修复与结果

第一次 live inspection 内容合同通过，但复用 `CaseService.for_fixture_root` 会构造 `SQLiteCanonicalStore` 并执行 migrate，使 canonical SQLite mtime 变化。虽然 object 数量没变，这不足以证明严格只读。最早 owned root cause 是验收 loader 复用了可写 fixture 初始化路径；已改为 SQLite URI `mode=ro` + `pragma query_only` 直读，并在验收前后比较 canonical DB 与 object tree SHA-256。最终两者完全不变。

真实 Run 验收结果：9 个 Artifact；3 个 promoted candidate findings；numeric typed gap；Lead decision=accept；3 gaps；Writer 3 sections、3 limitations、3 evidence refs；四层 Verifier 全 pass，semantic/financial=`100/100`；本轮新增 model/provider/network/canonical business write=`0/0/0/0`。

收口验证：focused T04=`6 passed`；Gateway + S2-T01/T02/T03/T04 + Project OS=`103 passed`。

## 状态

S2-T04 pass。S2-T05 已解除依赖但仍需单独授权；本轮没有执行 owner review、接受 material gain、复用 consumed admission 或进入 S3。结果合同为 `configs/releases/fin_ia_0_1_s2_t04_live_artifact_validation_result_v1_0.json`。
