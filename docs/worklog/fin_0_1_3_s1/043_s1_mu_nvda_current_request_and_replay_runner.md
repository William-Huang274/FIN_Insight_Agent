# S1 MU／NVDA 当前自然请求与统一回放入口

日期：2026-08-18

状态：`inputs_compiled / deterministic_scope_ready / clean_commit_and_CUDA_replay_pending`

## 为什么不是直接复制 DELL

DELL 使用过一次模型生成的自然材料 scope；MU／NVDA 没有等价、当前且可审计的模型 scope。若直接复制 DELL 词面，检索会被 Dell 业务结构污染；若从 qrels、历史命中或残余 gap 倒推，则会把答案泄漏进查询。

本轮只读取当前 Workbench catalog 中的研究问题、Case 身份与 as-of，以及 provider-neutral kernel 的 Evidence Slot、行业 Pack、facet 和金融本体，建立两套监督式自然开发请求。它们用于测 S1，不冒充 S3 模型自主规划。

## 两案覆盖

- MU：HBM 需求与转化、经营结果、利润获取、现金、产能执行、发行人反方和上下游周期反方；10 个候选 atom 中按统一策略选择 8 个，延后 guidance 与 pricing 辅助面。
- NVDA：数据中心需求与转化、经营结果、利润获取、主体供给执行、发行人反方、上下游反方和出口监管暴露；同样选择 8 个、延后 guidance 与 upstream-capacity 辅助面。

每条已选请求都由当前 ontology 确定性生成材料组，0 个需要额外模型 scope。产品意图中被标为 contextual 的部分只能帮助召回，不能自动成为 hard material axis。

## 工程收敛

没有创建 MU 和 NVDA 两套 runner。现有 canonical material-scope replay 增加统一 `current-replay` 入口；DELL 的不可变 R3 replay 保持原入口和合同。公开投影新增 deterministic-scope 计数语义和 fallback receipt digest，仍隐藏候选 ID。

## 验证与下一步

新输入合同、deterministic material scope 与公开投影测试，加上现有 material-scope／candidate-ceiling／runtime-binding 定向测试共 `31 passed`；全仓 `733 passed`。compileall、active baseline 165 Python／8 frontend／22 resources／0 forbidden、JSON／JSONL、policy digest binding、diff check 与 7,209-file secret scan 均通过。下一步只能从干净提交分别执行 MU、NVDA 的零模型 CUDA／FP16 replay，保存私有完整候选和公开阶段诊断，再做跨案业务归因。
