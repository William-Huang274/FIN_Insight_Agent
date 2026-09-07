# FIN 0.1.3 S1：DELL 外源候选裁决、Evidence Gate 与增量 current Pack

日期：2026-08-22
状态：外源 R2、候选审查和 Evidence Gate 已完成；current Pack 晋升、S2 重编译与动态单单元仍待执行。

## 本轮目的

按 Owner 冻结顺序，将 DELL 七命题在 AI-free 内源执行后的真实 residual needs 继续走完外源来源阶梯、候选裁决和 Evidence Gate。不能把搜索结果数量、抓取成功或自动候选直接当作 Evidence，也不能在 current Runtime 尚未消费新 Pack 时宣称检索完成。

## R2 外源阶梯结果

- 正式 attempt：`dell-external-ladder-r2`。
- 43 个查询单元：28 个不可变 replay，15 个 fresh Tencent WSA Standard provider call；0 retry、0 model call。
- 生成 39 个原文 shortlist、35 个有效 capture、18 个 source object、19 个确定性 candidate proposal。
- 三个原先标作 provider failure 的响应实际是带 `RequestId` 的 `Pages: null` 正常零结果，而非传输故障。Runtime 已改为区分成功零结果、缺失字段和显式 Error。
- 后续任何 provider 解析失败现在同时保存原始响应 capture 和 typed failure capture，避免 telemetry 只留下失败标签而丢失可审计正文。

公开结果：`configs/retrieval/fin_ia_0_1_3_s1_dell_external_source_ladder_result_v1_1.json`。
私有 terminal：`data/workbench_private/fin_0_1_3_s1_dell_external_source_ladder/dell-external-ladder-r2/terminal_result.json`。

## 19 条自动候选的业务裁决

本轮没有照单全收：

- 接受或用同一 capture 中更好的原文替换 12 条。
- 拒绝 7 条：两条 Microsoft 电信／Azure 内容没有 Dell 关系边；三条同源重复；两条只有标题、导语或重复机制。
- 额外从已保存 capture 中补出两条自动选择器漏掉的材料：Dell 官方 Northwestern Medicine 客户案例，以及一个明确标为翻新渠道样本的 XE9680 H200 固定配置。
- 两个过长候选被缩成同一不可变 source segment 内、人工明确选择且不超过 1,600 字符的证据表面，避免后续 reviewed anchor 只能锚定整篇长段。

候选审查最终形成 14 条 capture-bound candidate；此阶段仍为 candidate，不具备 Evidence 或 NumericFact 权威。

## Evidence Gate 结果

- predecessor Pack：29 Evidence、14 residual gaps。
- 新增 14 Evidence：2 条 Dell issuer-direct fact，12 条行业／渠道／媒体 bounded context。
- successor Pack：43 Evidence，其中 20 条 direct、23 条 bounded context。
- 6 个 gap 被收窄，0 个被关闭；Dell 精确 ASP、公司单位销量、专属供应分配、良率、产能释放时点和估值等仍保持显式边界。
- 行业预测必须保留预测身份；渠道配置不得冒充 Dell 标准配置或成交价；媒体材料不得产生 Dell exact NumericFact 或 AI 利润因果权威。

私有 successor：`data/workbench_private/fin_0_1_3_s1_dell_external_source_evidence/dell-r2/successor/pack.json`，payload digest `82ea1defba982308afb8af94cce85ce4e00167ded17602199e90f01215d06129`。

## 结构修复

历史 `public_context_evidence` 会把所有外源都硬编码为 ecosystem read-through，无法正确区分 Dell 自己的产品／客户事实和行业材料。本轮新增通用的外源候选审查与 Evidence Gate：

- 每一条自动 proposal 必须有接受、替换或拒绝决定；
- 替换只能来自同一不可变 source object 的精确片段；
- trusted media 的独立来源数量从实际 source family 推导，不能由调用方伪造；
- Dell issuer-direct 与 bounded ecosystem context 使用不同 Evidence role；
- gap 关闭必须另有独立 closure receipt，本 Gate 只能收窄；
- 所有 Evidence 保留 proposition、slot/facet、speaker、subject、期间、来源用途和 numeric boundary。

同时，current Pack 原子晋升器已支持只替换一个案例并按 digest 保留其余案例。过去必须三案一起重放的限制会造成无意义的 MU/NVDA 重跑和新旧指针漂移；现在单案 successor 也必须同步更新 Pack、workspace、reviewed anchor、readiness、binding policy、binding receipt 和 runtime registry，不能手工改一个 JSON 指针。

## 验证

- 外源候选／Gate、来源阶梯、runner capture 与 current Pack promotion 定向测试：`29 passed`。
- 0 模型调用；Gate 阶段 0 网络调用；没有新增 NumericFact、qualified-human、S1 或发布权威。

## 下一步与边界

1. 将本轮实现、计划和公开 R2 结果形成干净提交并推送。
2. 从干净提交生成兼容 current Pack promotion 的 product-successor projection，并用 43 Evidence Pack 重做 DELL ProductReadiness。
3. 零调用签发并执行 DELL 单案 current Pack 原子晋升；MU/NVDA 与留出案例保持原 digest。
4. 重新编译 S2 的派生值、区间、情景与 typed gaps。
5. 只有 task-relative `EvidencePackReadiness` 通过，才签发一个 DELL 动态单单元；否则继续停留在最早责任层，不用模型 live 掩盖资料／绑定问题。

本记录不宣称 S1 通过、公开信息完整、DELL 完整研究合格、动态 Agentic Research 完成或 S3/S4/S5 获得接受。
