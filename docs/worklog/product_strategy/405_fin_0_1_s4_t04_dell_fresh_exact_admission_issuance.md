# FIN 0.1 S4-T04 DELL Fresh Exact Admission Issuance

日期：2026-07-26

## 结果

DELL source-grounded fresh exact admission 已原子签发，状态严格为：

- `issued=true`
- `consumed=false`
- `execution_started=false`

Admission：

- ID=`fin01-s4-t04-dell-fresh-exact-admission-r1`
- digest=`da035e71d9eee81e9c76c5243a396bafaacfc29cd1f01e66eb1a66b8b757a60f`
- file SHA256=`26739c9e21c58e42bd5c3ce761cd7f19a70bedeca5c4e96a3738e762ad806e76`

Issuance：

- ref=`configs/releases/fin_ia_0_1_s4_t04_dell_fresh_exact_admission_issuance_v1_0.json`
- SHA256=`d70d24ec684332abeec619b90d9c6ef463d169e17f83ef422d8f0cb43b350ec5`

本轮没有调用模型、Provider、网络或来源，没有创建 WorkUnit、Attempt、Run 或 Artifact，也没有执行 paired assessment 或 Human review。

## 预签发 Root Cause Repair

预签发审计发现：`prepare_s4_source_grounded_exact_input` 虽已存在，但实际 `_S3ThreeCellBoundedAgentAdapter` 与 exact runner preflight 仍固定使用 S3 planning input compiler。若直接签发，admission 会绑定 S4 input digest，但实际 dispatch 会走另一条输入构造路径。

该问题登记为 `RC-P36-057` 并在签发前关闭：

- `exact_live_s4_*` admission 在 Runtime 初始化时加载对应 S4 Case binding 与 source-grounded pack；
- actual dispatch 使用 `build_s4_source_grounded_bounded_agent_input`；
- dispatch 强制要求生成的 input digest 与 admission input digest 完全一致；
- exact runner clone preflight 对 S4 admission 使用 `prepare_s4_source_grounded_exact_input`；
- S3 历史 admission 继续走原路径。

这项修复保证 admission 绑定的不是“旁路 prepare 结果”，而是真实 execution dispatch 会消费的输入。

## Exact Binding

- Case=`case_7b5c2042bef3825b8df71a96`
- DecisionSurface=`p02_decision_surface_d31fd75b31ad8385e9d8376a:v1`
- input head=`97c9d6c09effa7293fe886d9d36e8a74a969e9a1dc3f8af2b435efbf1a08cebc`
- input digest=`3499c03470c5bec5168dc87a2974802869da389f2ef588f41021731828d09e96`
- preparation digest=`a293b64b958ea31f900173609e771ca3d5cfea21e693f9bb057a8e3d07e6f9e3`
- WorkUnit=`wu_p02_5_2ebc452430c3eac0db8de47c`
- Attempt=`attempt_fin01_87e5480ea908aff63ffe9e1f`
- Run=`research_run_fin01_2eced17671df87082b95db9a`

三类 execution identity 在签发前后均不存在于 canonical execution tables。

## Execution Envelope

- semantic/provider/network calls maximum=`12/12/12`
- max transport attempts per call=`1`
- retry budget=`0`
- maximum output tokens=`16,800`
- maximum total cost=`USD 0.10`
- source calls、external tools、live Case head writes=`forbidden`
- automatic retry/repair/fallback/rerun=`forbidden`
- first credible failure=`terminal fail-closed stop`

以上只是已签 admission 的执行上限，不构成 exact-live 授权或实际成本。

## 验证

- frozen proof generator 重新执行，decision 字节一致；
- source pack SHA256 与冻结值一致；
- Canonical logical digest=`ed53001e3a11a243e88daeba73c1127181ce96ac7095c119a1ba6a75dde1bffe`；
- exact runner 能加载 admission/issuance；
- clone runner preflight 重编译出相同 S4 input/preparation digest；
- S4 current suite（含新增 code-binding byte check）=`37 passed`；
- S2/S3 active-backlog compatibility tests=`18 passed`；
- S1 shared research runtime suite=`14 passed`；
- S2 bounded profile suite=`21 passed`；
- S2 exact admission 与 S3-T08 adjacent suite=`85 passed`；
- S3 historical exact runner=`5 passed`，historical admission issuance=`5 passed`；
- 本轮不重复计数的相关合同测试合计=`185 passed`；
- T05 Project OS full-chain preflight=`pass`，open blocker=`0`；
- admission 六个 exact code binding 均与当前文件字节 SHA256 相同；
- 相关 JSON/JSONL、Python compileall 与 plaintext credential scan 均通过；
- model/provider/network/source/WorkUnit/Attempt/Run/Artifact/Human=`0`。

## 下一步与边界

S4-T04 已通过。下一项为：

`S4-T05-DELL-EXACT-R2-EXECUTION-AND-PAIRED-ASSESSMENT-AUTHORITY-DECISION`

必须再次获得独立授权，才能 exact-once 消费 admission。只有一条 coherent terminal success 生成九 Artifact 后才允许 paired assessment；当前不认定 DELL R2、MU R2、NVDA R3、Human acceptance、S4 pass、S5、release 或 production。
