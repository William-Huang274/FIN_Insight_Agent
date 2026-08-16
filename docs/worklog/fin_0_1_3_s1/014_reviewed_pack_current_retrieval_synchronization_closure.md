# S1 reviewed Pack 与当前检索同步关闭

日期：2026-08-16
归属：FIN 0.1.3 / S1-C 与 S3 动态纵切交界
问题：`RC-S1-019-reviewed-pack-current-index-and-source-route-drift`

## 1. 业务上发生了什么

DELL 动态单单元已经能自己提出问题并调用 S1，但它查不到一份产品明明已经审过、Workbench 也能展示的 Dell Q1 FY2027 法说。结果是模型只能看到 SEC 文件，无法自然拿到订单、积压、供需和 AI server 利润边界等管理层原话。

这不是“模型没搜对”，也不是“Dell 网站又下载失败”。法说已经下载、解析、复核并进入 Evidence Pack；真正的问题是 Pack 和当前检索对象库分别维护来源清单，后者没有同步前者。

## 2. 为什么没有只补 Dell

修复前先对 DELL、MU、NVDA 的全部 reviewed source 做对象级回放。回放发现 TSMC Q2 2026 法说页也存在相同问题：它们在 DELL current Pack 中承担先进封装／供给背景，但不在 current object store 中。

因此本轮按结构问题处理：

- current snapshot 能读取组合 Pack 中每个 artifact 自己的私有对象根目录；
- Dell、TSMC 两份解析后的官方法说进入唯一 current source manifest；
- 路由按 Evidence Slot 限定 transcript，而不是给所有查询开放；
- 公司身份、关系方向、截至日、digest 和文件路径继续 fail closed。

## 3. 修复后的真实数据流

```text
已保存的官方 PDF / parsed document
  → current source manifest
  → 30 个父文档 / 1,841 个检索子对象
  → claim / metric-row / parent-context 对象编译
  → BM25 + Qwen 当前候选
  → reviewed source 精确 join
  → EvidenceResponse 或 typed gap
```

当前 1,841 个子对象中有 36 个法说页：Dell 14、TSMC 22。普通 DELL demand 请求已经能命中 Dell page 3，不需要把法说预先塞给 Agent。TSMC 页面只有在“谁供应谁／谁披露谁”的关系边界成立时才出现，不能冒充 Dell 自述或精确分配证明。

## 4. 验证结果

- 三案 reviewed source 对象级缺失：`0`
- 当前金融对象：`20,761`（claim `12,055`、metric row `7,500`、parent context `1,206`）
- 当前 snapshot digest：`d63aadd3cc9c0f5c140027d454179439263edd9bef145babd564438b15bdf44a`
- Runtime Registry：R12
- formal Truth Spine v1.4 digest：`816ad515f48bea559a54d874cdfaa76bf2dabe887a0c32067a90f59bc8ee2a82`
- 模型／Provider／外部网络调用：`0／0／0`
- 新 Evidence 晋升：`0`
- 全仓测试：`393 passed`
- active baseline：`131 Python／8 frontend／10 resources／0 forbidden refs`
- secret scan：`6,744 files／0 finding`
- 实现提交：`6c4e659275dd030576ba7bf41f6c0f189af9212a`，已推送

负向验证覆盖：候选顺序变化、未审候选文本注入、跨 Case、Pack 漂移、非法 promotion、gap-only thesis 升格、未绑定期间关系。它们均被拒绝。

## 5. 没有被这轮修好的问题

这轮只解决“已经审过的资料为什么查不到”。它没有证明候选排名已经足够好：很多合格 reviewed target 虽然进入对象库，仍可能没有排进每个查询的前列。也没有补齐 Micron prepared remarks、PIT 估值或产品收入—成本—利润桥。

所以状态是：

- `RC-S1-019`：关闭；
- S1 source/object synchronization：工程通过；
- S1 排序／Evidence Role 产品门：仍开放；
- DELL 五单元：尚未运行；
- S3：尚未通过；
- S4/S5：未进入。

## 6. 下一步

1. 有限 S2 回归：确认 transcript 的数字不会绕过 SQL/PIT/NumericFact 权威；
2. 为其余四研究单元迁移最小 RoleMethodPack 和本案即时 GraphContextPack；
3. 做五单元零调用复证，检查跨单元身份、期间、引用和 gap；
4. 资格门通过后执行 DELL 五单元自然动态案例；
5. 对完整底稿和报告做 L1、八维质量、paired gain 和 qualified-human 内容验收。

不能因为来源同步成功就提前宣布 S1 或 S3 通过。
