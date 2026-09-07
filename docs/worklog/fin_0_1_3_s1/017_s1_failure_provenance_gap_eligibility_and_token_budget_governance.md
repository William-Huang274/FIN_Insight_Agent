# 017 S1 故障归责、gap 资格与 Token 预算治理

日期：2026-08-17

状态：`owner_direction_accepted / documentation_complete / runtime_not_implemented`

## Owner 更正

Owner 要求下一版 S1 标准范式必须明确分开：

1. 本地 chunk／向量库／SQL／对象处理问题；
2. 内外源明明可取得，但检索、排序、联网工具或模型没有执行到位；
3. 免费公共信息确实不存在后形成的 gap。

同时，从现在起每个节点 token 预算都必须有任务和质量依据，不能只按省钱／速度设置。

## 本轮完成

- PRD 新增 16.40，把三类故障归责、gap 举证门和第一修复包定义为产品要求；
- S1 技术范式新增 `FailureProvenanceRecord`、`GapEligibilityReceipt`、CandidateDecision 全账本、capture-bound 晋升和 TokenBudgetBasis；
- Project OS 全局 token policy 改为 repository-wide active policy，并在 `AGENTS.md` 加入跨上下文强制规则；
- FIN 0.1.3 当前计划冻结 DELL 三命题第二轮和 MU／NVDA 等价动态链，不授权全量索引重建或模型 full-chain；
- RC-S1-020 的下一实施范围由“Owner 待决”更新为“方向已接受、Runtime 待实现”。

## 为什么先做这个包

当前 DELL 不是简单“搜不到”：128 个候选中 111 个没有完成审查，动态晋升为 0，Pack 已有材料也可能因 slot／facet binding 丢失。若先换 Embedding 或扩 broad search，会产生更多无法解释去向的候选，却不会形成更可靠 Evidence。

第一修复包先建立一份逐命题账：系统知道要证明什么、已有何种支持／反方／桥、候选为什么被接受或拒绝、缺口属于哪个责任层。之后的第二轮检索才有明确目的和停止条件。

DELL 三条命题用于验证三个不同业务面：

- working-capital：本地对象／SQL／binding 是否能把已有资料交到正确命题；
- issuer-counter：发行人资料的 query／ranking／Evidence admission 是否闭合；
- upstream-counter：跨公司关系方向、生态来源和外源补证是否闭合。

DELL 闭环后，MU／NVDA 必须从自然问题重新执行同一核心，以检查它是否为通用范式而非 DELL case patch。

## Token 预算新口径

每个节点在签发前记录任务、输入规模、必交付项、schema、materiality／质量风险、同类历史 usage、reasoning profile、安全余量和失败语义。分析、分类、写作和严格交卷使用不同依据；预算不足必须分批、显式延期或 typed 终止。成本和延迟继续记录，但不能换取静默删题或把“没执行”写成业务 gap。

## 边界

- 0 Runtime／索引／Pack／模型／Provider／网络／source promotion／live；
- 没有改写 DELL／MU／NVDA 历史结果；
- 没有宣称 S1、S3 或 FIN 0.1.3 通过；
- RC-S3-043 继续独立存在，S1 增加资料不能关闭模型忽略已见事实的问题。

## 复证

- Project OS paid-run preflight tests：`31 passed`；
- `full_chain_preflight_checklist.json` 与三份 JSONL 账本解析通过；
- active baseline：138 Python／8 frontend／11 Runtime resources／0 forbidden reference；
- repository secret scan：6,870 files／0 findings；
- `git diff --check` 通过；
- 0 code／Runtime／模型／Provider／网络调用。

## 下一门

先把本文合同收敛为有界实现和确定性 fixture：CoverageState、candidate 全账本、binding、capture-bound promotion、gap eligibility 与 token authority receipt。工程门通过后，才执行 DELL 三命题第二轮；随后才判断 MU／NVDA 动态纵切与 S1 product gate。
