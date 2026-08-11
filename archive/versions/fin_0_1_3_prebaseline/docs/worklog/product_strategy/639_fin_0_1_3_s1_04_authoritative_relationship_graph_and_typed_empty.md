# 639 — FIN 0.1.3 S1-04 authoritative relationship Graph 与 typed empty

日期：2026-08-06
阶段：`013-S1-04`
结论：`S1-04 engineering_pass`，`S1` 尚未关闭，下一项 `013-S1-05`

## 1. 本轮纠正了什么

FIN 0.1.2 Workbench 把 DELL、MU、NVDA 三案关系图统一投影为 typed empty。该结果可以作为历史产品状态保留，但不能继续当成 current 事实，因为 S1-03 已保存并解析的官方来源中存在明确命名关系：

- MU 官方年报将 Samsung Electronics 与 SK hynix 列为竞争者；
- NVDA FY2026 官方 release 明确提到 Meta 合作，以及 AWS、Google Cloud、Microsoft Azure、Oracle Cloud 对 Vera Rubin 的部署计划；
- DELL 当前 bounded official source 只有未命名客户、供应商与 channel 描述，没有足够证据建立具名边。

因此本轮不是“给三案都凑图”，而是把可证明关系晋升为边，把不可证明关系保留为诚实空图。

## 2. 实现结果

新增单一 versioned Graph policy、确定性 compiler/validator、release materializer 和 mutation suite。compiler 只读消费 S1-03 的 content-addressed captures、parser 结果与 S1-02 current date authority，不发起网络或模型调用。

current 结果为：

- MU：2 条 `competitive_landscape` edge；
- NVDA：1 条 `strategic_partnership` edge 与 4 条 `official_deployment_event` edge；
- DELL：1 个 typed empty，且 `source_exhaustion_proven=false`；
- 合计 7 条 approved edges、1 个 honest typed-empty case。

每条边都绑定：case/issuer、受控实体 registry、完整官方 statement、publication/as-of、source capture digest、parser digest、rule digest 和 claim boundary。编译器固定：

- `relationship_fact_only=true`；
- `financial_fact_authority=false`；
- `model_authored=false`。

所以“Meta 与 NVIDIA 有官方合作关系”可以成为关系事实，但不能被模型直接转换成收入、利润、订单规模或因果结论。

## 3. Fail-closed 边界

mutation 覆盖并拒绝：

- 跨案例 issuer/target 污染；
- 未注册或错误实体；
- future publication date；
- capture/parser/rule digest 漂移；
- required explicit statement 缺失；
- 明明存在 required relationship 却强制 typed empty；
- 把 Graph edge 标成 financial fact authority。

DELL typed empty 只表示本轮有界来源没有形成合格具名关系，不表示全网或全部官方档案已穷尽。

## 4. 验证

- S1-04 focused：`6 passed`；
- FIN 0.1.3 current active S1 suite：`70 passed / 1 historical event-time assertion deselected`；
- release materializer 重复执行 byte-identical；
- model/provider/network/source/business run：`0/0/0/0/0`。

被显式排除的唯一历史节点仍要求旧 S0-02 decision 永远绑定 living Project OS 当前字节，是已知 event-time 断言，不是 S1-04 回归。历史 decision 与 test 均未改写。

## 5. 产品与阶段边界

本轮没有修改旧 0.1.2 Workbench 三案空图，也没有把 current Graph 接入 Agent 或 UI。原因不是回避产品问题，而是按阶段归属处理：

- S1-04 负责证明 Graph 数据与 typed-empty 真实性；
- S1-05 负责证明检索能否召回并有效利用这些 Evidence/Graph；
- S3 负责 Agent 消费和八维研究内容质量；
- S4 负责 current 产品表面投影与真实用户验收。

因此 S1-04 的工程通过不等于研究报告内容已改善、三案例产品已重验或 FIN 0.1.3 可发布。

下一项严格是 `FIN-0.1.3-013-S1-05-RETRIEVAL-EVIDENCE-USEFULNESS-EVAL-AND-S1-CLOSEOUT`。
