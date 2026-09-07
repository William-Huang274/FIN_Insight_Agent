# 021 S1 VS1 当前数字原生资料纵切

日期：2026-08-17
状态：`VS1_vertical_slice_integrated / S1_qualification_false / VS2_next`

## 一、为什么做这一轮

Owner 已批准从 VS1 开始连续执行。目标不是再写一份离线 schema 或一次性 runner，而是证明当前真实 source、对象、检索、reviewed Pack 和 Workbench 能否消费同一 canonical artifact spine，并让候选决策、命题 Coverage 和 gap 资格真正出现在产品面。

本轮严格不改变以下边界：

- 不调用模型或 Provider；
- 不访问网络；
- 不重建索引；
- 不自动晋升新 Evidence；
- 不把 DELL 单案例成功写成 S1 资格或完整产品链通过。

## 二、实际纵切

选择当前 DELL `pricing_and_mix` 命题，使用截至 2026-08-06 的正式 Runtime：

```text
11 类当前 source inputs
  → raw capture / parsed document
  → current financial objects / manifest / index
  → DELL EvidenceRequest / QueryFacetPlan
  → CandidateSet / CandidateRanking
  → persistent CandidateDecision
  → proposition CoverageState / GapEligibilityReceipt
  → task-relative Pack readiness
  → Evidence Pack service / Retrieval service
  → Workspace Evidence + Retrieval 页面 / frozen consumer probe
```

实现集中在一份 provider-neutral 模块 `src/retrieval/vertical_slice.py`。现有 producer 只经薄 adapter 生成 canonical envelope；没有复制现有检索器、Pack 或 Workbench。正式结果为 `configs/runtime/fin_ia_0_1_3_s1_vs1_vertical_slice_result_v1_0.json`，Runtime Registry 由 R13 升为 R14。

## 三、业务结果

当前查询返回 6 个候选：

- 第 5 位 Dell 官方 Q1 FY27 transcript page 4 与现有 reviewed Evidence 精确绑定，复用 capture-bound Evidence Gate，接受；
- 第 6 位 Dell 10-Q pricing/mix／margin 对象与 reviewed Evidence 精确绑定，接受；
- 前 4 位 10-K／10-Q 候选尚未存在于 reviewed Pack，只记 `needs_review`，不因排名较高而晋升；
- 现有 reviewed 8-K 与 transcript page 3 没被本请求召回，明确记录为 2 条 `reviewed_not_recalled`。

因此真实状态不是“检索成功”这一句，而是：

| 项 | 数量 | 业务含义 |
| --- | ---: | --- |
| accepted Evidence | 2 | 可以支持有边界的 pricing/mix 研究 |
| needs-review candidates | 4 | 相关但尚无 Evidence 权威 |
| reviewed-not-recalled | 2 | 资料已经存在，但当前查询／排序未把它们带回来 |
| unresolved gaps | 3 | ASP、PVM bridge、unit／volume 仍缺 |
| true public-information gaps | 0 | official／external supplement 尚未执行，不能声称公开资料不存在 |

这轮同时证明了一个不舒服但重要的事实：两条可用 Evidence 只排在第 5／6 位。VS1 证明账本和消费者接通，并没有证明排序质量足够；该问题继续归 VS3。

## 四、六类门

1. **局部与 mutation**：正式 result 校验、55-envelope coverage、候选排列变化、未来日期、跨案 scope、Pack drift、false-gap prevention 均通过。
2. **相邻合同**：Evidence Pack、Retrieval、Workspace API 的 Pydantic response 与相同 canonical projection 通过。
3. **真实纵切**：当前 DELL 私有 Pack、真实 raw PDF capture、current object／index 和真实 Workbench 全部参与；不是 fake-only。
4. **业务影响**：2／4／2／3 的决策和 gap 结果在产品面可见；没有使用 Recall 或网页数冒充充分性。
5. **跨案非回归**：MU／NVDA 继续可读取，且不会收到 DELL 的 canonical projection；未来日期与跨公司 mutation fail closed。
6. **迁移／回退**：新增的 policy/result 是 R14 中两个独立 digest-bound pointer；前序 Pack、object 和 index 不变，回退可移除两项 pointer 并恢复 R13 consumer 行为。

验证结果：新增／相关 Python 测试 18 项通过，相邻 Workbench／retrieval 测试 32 项通过；全仓 `505 passed`；Project OS＋foundation `41 passed`；compileall 通过；active baseline=`142 Python／8 frontend／13 Runtime resources／0 forbidden reference`；secret scan=`6,894 files／0 findings`；TypeScript typecheck 和 Vite production build 通过；Playwright 桌面＋移动完整套件 6 项通过，修复了移动端机器状态裸露与指标三列拥挤。

全仓回归曾首先暴露一处真实迁移缺陷：未加载 VS1 时，Evidence Pack service 仍输出 `canonical_spine: null`，导致业务内容未变但历史 fixed-Pack 的 projection digest 改变，旧 S3 授权正确 fail closed。最终实现改为：只有加载 VS1 Runtime 时才扩展新字段；legacy／frozen consumer 保持原字节级投影，当前 VS1 consumer 则获得显式 canonical projection。修复后历史授权测试与全仓回归同时通过，没有改写任何旧 authority 或 result。

`playwright-interactive` 要求的 `js_repl` 在当前任务未启用，因此没有伪称完成交互式持久会话；使用仓库正式 Playwright E2E 与截图复核作为替代。

## 五、没有关闭什么

- 扫描 PDF、OCR、复杂表格、跨页、脚注和修订／重述；
- sparse／dense／graph／SQL／official／external 的同 CandidateSet 增量与排序资格；
- 动态新候选的 capture-gate 晋升；
- Coverage 驱动的真实第二轮补证和 Coverage delta；
- valid／frozen test／新异质 holdout 与稳定性；
- S1、S3、完整研报、S4 或 release。

## 六、下一步

进入 VS2，用扫描 PDF／OCR／复杂表格／脚注／修订重述走同一条 spine。VS2 若改变 parser、object 或 index 合同，必须同时重放本轮 VS1；不得为 VS2 再造一套 runner 或等到 VS5 才做最终集成。
