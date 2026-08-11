# 858 — FIN 0.1.3 S2 numeric natural canary exact-live 终态与语义审计

日期：2026-08-11

状态：唯一 DeepSeek Pro canary 已消费并 formal failed；无重试；根因是 exact-surface 词形误拒

## 实际运行

execution authority commit `75003348...c739c` 推送后，正式 runner 从 clean/synced HEAD 再次 preflight 通过并 exact-once 消费 v1.1 admission。DeepSeek Pro 返回 `stop` 和合法 JSON；调用=`1 provider / 1 model / 0 retry`，usage=`3,110 input / 554 output / 3,664 total`，latency=`6,864 ms`。request、完整 response capture、terminal 和 shared-ledger receipt 均已原子保存，原始内容只留 private Workbench runtime。

formal terminal 为 `contract_validation / natural_node_canary_required_presentations_missing`，result=`c5eec16d...3b49`。该失败不可改标，admission 已消费且没有第二次调用。

## 真实业务表现

模型使用了 E022 作为 Dell 直接披露，引用 AI orders `$24.4B`、AI server revenue `$16.1B`、backlog `$51.3B` 和 customer count 四个正确 NUM ref；E018 被正确限制为 HPE read-through，E023 被限制为未量化的 pull-forward 风险。它还明确说订单／backlog 不是无条件收入，不能推断取消率、线性兑现、Dell 已出现同等订单消化，也没有 ASP／margin bridge。没有自由算术、估值、推荐、错实体、错期间、错单位或无依据金额。

失败只来自一个英语词形：policy 要求逐字 `customer count surpassed 5,000`，模型写成 `customer count surpassing 5,000`，同时引用了正确 customer-count NUM ref。只在离线副本中把 `surpassing` 换成 `surpassed`，其他字段和文字完全不动，全部后续角色、数字和 boundary gate 即通过，validation=`624a3277...a47`。因此它既是模型没有逐字复制 canonical surface 的轻微形式偏差，也是项目把无经济意义词形差异升级为 hard L1 的验收误拒；不是实质研究错误。

## 处置边界

formal terminal 继续 immutable failed，代码未改、Provider 未重跑、业务 Artifact 未晋升。下一项只允许零调用的 provider-neutral 处置：模型继续选择 NUM ref 和判断语义，本地负责语法化展示或受控 presentation equivalence；必须用保存 capture 及 negation、below-threshold、entity、period、unit mutation 证明不会放宽真实财务门禁。禁止增加 DeepSeek 专用短语白名单，也不因此运行完整 DELL。

公开结果 digest=`ca579cb5...d3bd`；模型运行记录=`reports/model_runs/20260811_fin_0_1_3_s2_dell_numeric_natural_node_deepseek_pro_canary_r1.md`。
