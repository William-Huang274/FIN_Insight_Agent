# 066 Reviewed claim anchor 与五单元 claim-surface successor 门

日期：2026-08-17

## 结论

R4 后的零调用处置没有继续逐字段修 DeepSeek，也没有放宽金融 L1。它修正了一个项目自己的证据投影错误：真实、已复核的 Dell 历史毛利率原句存在于来源长文后部，但当前模型视图只给来源开头，因此模型无法同时看见“人工摘要说了什么”和“官方原文究竟怎么说”。

当前工程门已通过，允许在干净、已推送提交上签发一次新的 DELL 五单元 exact-once successor。该权限不等于自然结果通过，更不等于 S3、泛化、Workbench 发布或 release 通过。

## 实现内容

1. 新增 reviewed claim anchor catalog。每个 claim anchor 绑定 case、target、Evidence、source record、source text digest、item digest、字符区间和 anchor digest；任一漂移都在模型调用前拒绝。
2. Workbench Evidence Pack 对 claim 使用精确 anchor，对其他对象保留原有有界前缀；不把全局字符上限随手放大。
3. current consumer 只在 anchor 被复核时把精确原句和 anchor receipt 给模型；凭据、未审全文和 Provider 私有 reasoning 均不进入该表面。
4. 动态 Claim Surface 新增一个期间绑定的发行人历史方向关系。它允许复述 FY2026 Q3 的 Dell 公司披露，但明确禁止跨期外推、独立因果、产品利润／毛利、ASP、数量、PVM 或利润分配。
5. submission projection 从已保存分析草稿中确定性移除 URL、内部 alias、filing ID、日期、数字、货币、百分比和 verbal numeric band；保留模型叙事，不生成任何替代结论。
6. Evidence use 唯一性从“同一 Evidence 全报告只能出现一次”修正为“同一 Evidence＋同一 role 只能出现一次”。同一来源可一处支持历史陈述、另一处限制外推，但不能重复堆叠同一种角色。
7. 没有让 Harness 根据 Evidence role 自动生成 `judgment_status` 或 `inference_authority`。R4 证明模型可能在文字中作出支持性结论，却只把来源标成 limit；自动推导状态会隐藏这种冲突。状态继续由模型提交，本地合同继续独立校验。
8. 旧 fixed-Pack 回放显式冻结在原 v1.0 Evidence projection；当前产品使用 v1.1 anchor projection。旧实验 digest 不因当前产品升级而漂移。

## 零调用结果

- 当前 DELL base dynamic input digest：`5c6b0bd2339bbcc84043f4b3dccacb9243f02916480164795f5be0e576aafcc1`；
- claim-surface input digest：`d8e915accf9d819c9e838802c8cdd852fd539b09ab0d88d5ccabddf57f1b438b`；
- 目标 Evidence：`EV::5388E016C17032C1`；
- 目标对象：`DELL_2026_10Q_ITEM2_BLOCK_0011_PART_04_OF_05_CLAIM_CA0D3EC4`；
- reviewed anchor digest：`497279ac1832a19dd24f32e44c83acc329ef071adfdaf5223061ce8f851fcc1c`；
- DELL／MU／NVDA anchor 数量：11／2／8；
- runner 专门测试：9 passed；
- current consumer、dynamic truth spine、claim surface、five-cell、bounded-loop、Workbench 与 readiness 联合回归：184 passed；
- model／Provider／外部网络／candidate promotion：0／0／0／0。

负向测试覆盖 target／source／item／期间／区间漂移、跨案例引用、未归属强因果、重复 Evidence＋role、旧 fixed-Pack digest 漂移、旧单元草稿误复用，以及五单元不足 5/5 时禁止综合。

## 新 live 的真实含义

新 attempt 复用 R4 已证明的自然 planner 和 current S1/S2 controlled plan，不重新检索或制造证据；但五个单元分析与 Judgment 全部重跑，避免让旧草稿在新证据表面下冒充 fresh 分析。最大 12 次调用：5 analysis＋5 submission＋1 synthesis analysis＋1 synthesis submission，0 retry／fallback／protocol switch／外源网络。

成功只表示形成可供验收的五单元报告。随后仍必须独立检查：身份、期间、数值、引用和因果 L1；逐单元研究深度；跨单元综合；八维绝对内容质量；与既有结果的 paired gain；qualified-human 内容验收。通过这些门以后，才允许进入 MU、NVDA 与异质留出案例泛化。

## 尚未关闭

- `RC-S2-004`：当前期产品收入到分部／公司利润、毛利和现金的 typed bridge 仍缺；
- DeepSeek strict Beta 的复杂 `pattern` 不能作为金融语义权威，本地 Validator 仍是最终门；
- 当前 anchor 证明精确来源可见，不证明模型会自然作出正确判断；
- 本轮未增加 Evidence，也未改善 S1 residual gaps、PIT 估值或外源来源覆盖。

## 全仓复证与历史边界

- 完整仓库回归为 `463 passed`；Python compileall、active baseline `135／8／11／0` 与 secret scan `6815／0` 均通过。
- 历史 fixed-Pack runner 不再无条件读取当前 v1.1 投影，而是先按 policy 绑定的 base digest 选择视图；只有明确匹配原摘要时才使用 v1.0，其他运行继续使用 current v1.1。历史结果因此可重复审计，但不会被改写成当前产品结果。
- Project OS 将历史 decision 的 artifact validator 与当前 scope allowance 分开。R3/R4 旧 decision 仍可验证其不可变输入、capture 和 profile，但旧 exact-once identity 不再是当前执行权限；当前唯一 scope 为 `one_DELL_dynamic_five_cell_claim_surface_successor_exact_once`。
