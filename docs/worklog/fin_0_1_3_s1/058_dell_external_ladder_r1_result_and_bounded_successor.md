# 058｜DELL 完整外源阶梯 R1 结果与有界 successor

日期：2026-08-22
阶段：FIN 0.1.3 / S1 外源补源（R1 不可变；CandidateDecision、Evidence Gate、S2 successor 与 S3 均未授权）

## R1 实际做了什么

R1 绑定 clean commit `9362640b895fb70fe6fc1323c87251368c391d86`，按七命题、四类来源执行 28 个 Tencent WSA Standard locator 查询；28/28 成功，得到 250 个 locator。随后只从受审来源注册表选择 22 条原文路线，使用 capture-first、0 retry 下载并保留完整请求／响应或 typed failure。全程 0 模型调用、0 Candidate 晋升。

公开结果：`configs/retrieval/fin_ia_0_1_3_s1_dell_external_source_ladder_result_v1_0.json`。

## 业务结果

- 客户需求：找到 Dell 客户案例、IDC 行业需求材料与其他客户／行业候选；6 条入选原文中 4 条抓取成功，3 个对象可编译，形成 5 条待审候选。它们能补行业需求和个别部署背景，但尚不能证明 Dell 总体销量或订单持续转换。
- PVM：TrendForce 行业金额／台数关系形成 1 个对象、2 条待审候选，只能作为行业桥接输入，不能替代 Dell 的价格、销量与配置组合桥。
- 反方：The Register 关于 Dell AI 服务器需求／利润约束的材料被抓取，但旧片段打分把网页尾部噪声混入候选；当前 2 条 proposal 不得晋升。
- 价格／配置：抓到 Dell 产品、搜索和新闻页，但 3 条抓取结果均未形成可用 dated object；没有得到可观察成交价格区间或可复算配置篮子。
- 销量：抓到 Dell InfoHub，但发布日期未解决；没有获得 Dell AI server units 或可信区间。
- 供应链：3 条入选路线均未形成对象；NVIDIA 页面因 `nvidia.com → www.nvidia.com` 被错误拒绝，Dell IR 路线超时，且单一 NVIDIA 查询没有覆盖 Micron／TSMC。
- 价值池：35 个 locator 中 0 条进入原文 shortlist。返回结果包含少量可能有用的技术媒体／渠道报价，也包含大量低质量站点；旧注册表与查询没有形成可审的 BOM／报价／供应商价值分配候选池。

## 数量结果

- Provider 查询：28 成功 / 28，总 locator 250；
- shortlist：22 条，覆盖 6/7 命题、11 个精确 host；
- 原文：10 captured、11 个同源跳转误拒／其他拒绝、1 timeout；
- 编译：5 个 source object、9 条 deterministic proposal、1 parse rejected、4 publication-date unresolved；
- Evidence promotion、public-information gap、EvidencePackReadiness、dynamic single-unit authority：全部为 0／false。

这些数字只说明路线执行到了哪里，不能说明资料质量合格。尤其 9 条 proposal 中存在网页尾部噪声，不能自动进入 Evidence。

## 最早责任层

R1 不是“搜索 API 完全没用”，也不是 DeepSeek 失败。最早问题仍在 S1 本地外源控制面：

1. 同一受审来源家族的 root／`www` 跳转被 exact-host allowlist 错误拒绝；Dell、NVIDIA、Microsoft、TrendForce 均有真实样本。
2. root／`www` 又被当成两个 domain 计算抓取额度，造成 Dell 实际拿到双份域预算。
3. 查询 tier 被误当成结果来源 tier；行业查询返回 Dell 官方页时，结果仍携带“行业来源”标签。来源权威必须由注册表决定，查询 tier 只表达搜索意图。
4. candidate proposer 对整段 2,400 字符文本做弱词重合，且错误丢掉 `dell/server` 等身份／产品锚点，导致语义无关网页尾部也入选。
5. 供应链的官方查询只锁定 NVIDIA，未分别执行 Micron／TSMC；价值池没有经过审查的技术媒体／渠道来源用途规则。它们是查询与来源覆盖缺口，不是公开信息 gap。
6. 无日期产品页被拒绝进入 point-in-time Evidence 是正确行为；successor 应寻找 dated announcement、采购日期、版本化页面或保留 typed unresolved，不能放宽时间权威。

## 有界 successor

R1 保持不可变，不重跑 28 个成功查询。R2 只允许：

- 将注册表 host、子域和安全的 `www` 别名编译成同一 source family，用同一 family 控制跳转和预算；
- 给来源注册表增加 allowed source tiers，拒绝“查询 tier 与真实来源用途”不一致；
- 改为段落／块级候选窗口，要求公司／产品身份锚点与多个 proposition-specific signal 同时成立；
- 零 Provider 调用重放 R1 locators，并仅重新抓取此前因同源 host 漂移误拒的原文；
- 对供应链、价值池及确实未覆盖的命题增加少量、逐来源定向的 successor query，不能重放全部 R1；
- 对 Next Platform、Fortune 及渠道／配置来源逐一审查 claim use 与权利，不能把随机网页批量加入注册表；
- 通过 replay、mutation 和 clean proof 后才执行一次 R2；R2 结果仍须人工可解释 CandidateDecision 与 Evidence Gate。

只有七命题材料达到当前任务的 EvidencePackReadiness，才可重编 S2 并签发 DELL 动态单单元。R1 不授权动态模型调用。
