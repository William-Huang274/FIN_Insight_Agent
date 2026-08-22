# 059｜DELL 外源阶梯 R2 结构 successor 工程门

日期：2026-08-22

阶段：FIN 0.1.3 / S1 外源补源（R2 尚未执行；CandidateDecision、Evidence Gate、S2 successor 与 S3 均未授权）

## 为什么不能直接重跑

R1 的 28 次搜索调用全部成功，失败主要发生在本地来源身份、跳转、预算、候选切片和残余查询覆盖。重新付费跑同一批查询既不会修复这些问题，也会破坏 exact-once 与失败可追溯性。因此 R2 必须复用 R1 的不可变 locator／原始响应，只对 R1 没有覆盖的供应链、价格／配置、销量和价值池残余问题增加定向查询。

## 本轮完成的结构修复

1. **同源来源家族**：注册表 host、显式安全别名和受约束子域编译为同一 `source_family_id`。`dell.com → www.dell.com` 等同源跳转不再误拒，抓取预算也不再重复计算。
2. **来源权威与查询意图分离**：query tier 只表达本次寻找哪类材料；原文的 speaker、source class、role 与 claim use 由受审注册表决定。与当前来源路线不相容的返回结果在抓取前保留明确 rejection，不再沿用错误 tier。
3. **块级候选窗口**：候选中心块必须同时包含公司／产品 scope anchor 和命题 material signal；上下文只能在中心块通过后有限扩展。整页导航、页尾推荐与隐私条款不能再借正文其他位置的弱词重合进入 proposal。
4. **原始日期恢复**：除 ISO meta／JSON-LD 外，可从带 `date/publish/news-time` 标记的原网页节点恢复 `June 22, 2026` 一类可见发布日期；Provider 日期仍无权单独建立 PIT。
5. **有界残余覆盖**：R2 编译 28 条 R1 replay 加 15 条 fresh provider query。新增查询逐来源覆盖 CDW／SHI／渠道配置报价、SAM 公共采购、IDC／TrendForce 销量、Micron／TSMC／TrendForce／EE Times 供应、Next Platform／ServeTheHome／渠道／Fortune 价值池。渠道报价只能作为 asking-price／configuration proxy，不能冒充 Dell 成交价或供应商分成。

successor spec：`configs/retrieval/fin_ia_0_1_3_s1_dell_external_source_ladder_successor_spec_v1_0.json`

spec digest：`3c7fd556e88d0753d3c603ff5cf44e289a672050aa4d3a879c3a038487fec74a`

effective plan digest：`d4191bedceea6e86666225b7222dc3c88dbd66f7a02faeeef4767f3503892378`

## 零调用证明

- 使用真实 R1 private terminal、28 份 locator bundle 及文件 SHA 回放：28 条全部 replay，Provider 调用为 0；模拟的 15 条 residual query 才产生 15 次调用。
- 使用真实 R1 `rejected_final_url` capture 证明：同源 root→www 原始响应可在 0 网络下重新资格化；文件 SHA、HTTP 2xx、最终 host 与来源家族任一不符都会 fail closed。
- mutation 覆盖：root／www 共用一份 family quota；行业查询返回 Dell 官方页不会被误标为行业来源；导航尾部不能越过块级 identity＋material 门；可见英文日期可恢复。
- 定向 `21 passed`；全仓 `1020 passed`（仅 2 条既有 SWIG warning）；compileall、diff check、active baseline `200 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`、7,603-file secret scan／0 均通过。
- 本轮 0 模型、0 网络、0真实 Provider、0 Candidate 晋升。

## 当前权限与下一项

该结果只说明 R2 的本地执行结构值得进入一次 fresh formal attempt，不说明新增来源有用，也不说明 Evidence Pack 已经就绪。下一项只能在 clean／synced commit 和 fresh Project OS preflight 后执行一个 `dell-external-ladder-r2`：28 条历史 locator replay，最多 15 条 fresh Tencent 查询，原始页面优先复用 R1 capture，只有未捕获路线才进行网络访问，0 retry、0模型。

R2 完成后必须先按业务语义解释每个命题“找到了什么、为什么拒绝、还缺什么”，再进行 CandidateDecision 与 Evidence Gate。任何未执行路线、本地解析／排序失败或预算耗尽都不得写成 public-information gap；动态单单元仍未授权。
