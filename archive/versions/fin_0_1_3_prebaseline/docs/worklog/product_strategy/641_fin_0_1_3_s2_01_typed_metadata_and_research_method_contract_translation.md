# 641 — FIN 0.1.3 S2-01 typed metadata 与研究方法合同翻译

日期：2026-08-06
阶段：`013-S2-01`
结论：`engineering_pass / contract_translated / fixture_proven`；下一项 `013-S2-02`

## 1. 入口审计发现

S1 已经提供 current Numeric、official semantic Evidence、Graph 与 governed retrieval pack，但旧 Agent surface 有两个项目内缺陷：

1. `specialist_llm._compact_pack_metadata` 对所有非集合 scalar 先执行 `str()`，使 `line_item_count` 从 int 变成 string；同一路径也会抹掉 bool/decimal 的合同语义。旧 Fundamental Agent 回归稳定复现为 `4 passed / 1 failed`。
2. 旧 0.1.2 judgment atom 看似结构化，仍允许 Provider 自由生成 `direct_answer_atom`、`counterevidence_atom` 和 `boundary_atom`。这解释了为什么 schema 能通过而 DELL/MU/NVDA 仍出现通用 Claim：模型自由文本面没有被公司专属机制合同约束。

因此 S2-01 不能只修一处 Python 类型，也不能直接继承旧 exact-live acceptance。

## 2. native scalar metadata 合同

新增共享机器可读策略与投影/校验实现：

- 明确允许的 count 字段保持 native int，bool gate 保持 native bool；
- `required_slot_recall` 等显式 ratio/score 字段使用 canonical decimal string；
- 未登记 numeric/bool fail-closed omission，不再因为文本短就静默字符串化；
- financial value 不进入通用 metadata 合同，继续由 Numeric authority 或本地 alias 管理。

真实 `tests/test_financial_statement_analysis.py` 现在 5/5 通过，`line_item_count` 为 int。

## 3. 三案研究问题与方法合同

只读消费 S1-05 current decision，将 DELL、MU、NVDA × 三个代表性 Cell 编译为 9 个请求：

- 26 个 current Evidence alias；
- 2 个 honest typed-gap alias；
- 18 个公司专属 mechanism choice；
- 18 个 what-would-change choice。

每个 request 都包含本案 decision question、method steps、Evidence/gap/mechanism/WWC alias 和同源 Provider output contract。Provider 只返回 epistemic state、direction、confidence 与 request-local alias；不能返回 raw number、date、identity、Claim/Artifact ID 或自由 narrative。本地继续拥有事实值、单位、日期、identity、ordering、lineage 和最终渲染。

这不是把最终产品固定为三个 Cell。当前三 Cell 只用于 S2 代表性合同与 node 评测；动态 10–20 Cell DecisionSurface 仍归 S3-01。

## 4. 验证

- 聚焦 S2-01＋旧 Fundamental Agent：`11 passed`；
- current S0–S2 active suite：`87 passed / 1 historical event-time assertion deselected`；
- 9/9 fake Provider output 通过同源 validator；
- mutation：跨案 mechanism alias、额外 raw numeric 字段、string/int/bool/decimal 类型伪装、S1 authority/legacy BM25 回退均 fail closed；
- model/provider/network/source/business run：`0/0/0/0/0`。

扩大运行整个 legacy Specialist suite 得到 `60 passed / 3 failed`。三项失败均发生在本次 metadata compactor 之前：单测显式传入的 source rows 被仓库当前 Product Intelligence autoload 数据抢占，导致 role source family、public-web row 和 product row 选择发生环境依赖。该问题登记 RC-P36-138，归 S2-02 的上下文 precedence/test isolation；本轮没有通过关闭真实 autoload 或修改无关 selector 来制造全绿。

## 5. 产品增量与未完成项

产品增量仍是内部 Agent 输入能力，而不是用户可见报告升级：系统现在能把 current 三案证据翻译为公司专属的研究选择面，不再强迫模型在通用句式与自由长叙事之间二选一。

仍未证明：

- representative Specialist/Claim/Lead 节点真实消费该合同；
- DeepSeek 自然输出能遵守并产生实质增益；
- 55k–58k 上下文的 yield/cost 已收敛；
- 动态 DecisionSurface、八维内容质量、Workpaper/Report、Human acceptance 或 release。

下一项 `013-S2-02` 先关闭 RC-P36-138，规定显式 current governed pack 相对 repository/environment autoload 的优先级并恢复 hermetic node fixture；随后做代表性节点零调用 runtime injection proof，再根据预注册 Rubric 决定一次有界自然输出 canary。不得直接跑旧 full-chain。

## 6. 主要文件

- `src/sec_agent/prompt_metadata_contract.py`
- `src/sec_agent/s2_research_contract_program.py`
- `src/sec_agent/specialist_llm.py`
- `configs/runtime/fin_ia_0_1_3_repair_closeout_s2_research_question_method_contract_policy_v1_0.json`
- `configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json`
- `configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_active_test_suite_successor_v1_0.json`
- `tests/contract/test_fin_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation.py`
