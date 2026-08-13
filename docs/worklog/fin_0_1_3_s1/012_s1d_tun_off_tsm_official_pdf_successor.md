# S1-D TUN-off A/B 与 TSM 官方 PDF successor

日期：2026-08-13

## 完成

- Owner 关闭 TUN 后签发两 route／两 attempt／0 retry／0 model 的 source-intake R2。
- TSM 官方 Q2 2026 transcript 取得 HTTP 200、22 页、1,450,799 bytes，raw digest=`3e21fe2d...fea453`；Dell 仍为 read timeout。
- 冻结 R2 result/disposition，并纠正诊断口径：执行为公网 DNS＋WLAN＋localhost 用户代理，不是完全 proxy-free direct。
- 新增共用 official PDF page parser、financial object compiler、Evidence Gate、reviewed Pack successor 和 exact zero-call runner；没有复制历史 attempt runner。
- 45 个相邻聚焦测试及 active-baseline import graph 通过；parser/gate mutation 覆盖 raw digest、空白 PDF、owner 污染、缺少 packaging/bottleneck 语义和 current-pointer 越权。
- 第一个 authority 因手写完整 Git SHA 错误，在任何 parse/output 前 fail closed；保留原 authority，v1.1 只修正 binding 后成功。

## 真实业务结果

- TSM transcript 第 10 页直接说明 packaging capacity 紧张到限制客户增长；第 20 页说明前后端 bottleneck、测试/封装短缺和针对瓶颈的 CapEx 调整。
- Gate 只接受这两页，Evidence owner 保持 TSM，DELL 只是消费该 ecosystem read-through；不授权 Dell-specific allocation 或因果归属。
- 私有 DELL successor Pack：Evidence 15→17，gaps 16→15，只关闭 advanced-packaging gap。
- 容量释放时点、TSM 向 Dell 的具体分配、Dell 自己的订单转化与 AI system margin 仍是 gap。
- S2 1,319 observations、12 metrics、SQLite digest 不变；新增 transcript 不可生成 NumericFact。
- 当前 Workbench Pack 指针没有切换；本轮是 successor candidate，不是产品发布。

## 结论与下一项

TUN 确实是原 TSM transport failure 的关键参与因素，但不是 Dell 的完整解释。S1-D 当前由“双源全阻断”收敛为“TSM 已完成、Dell 单一阻断”。

下一项限定为 Dell 官方 PDF 绑定 route 的人工入库。成功后必须复用相同 parser／对象编译／Evidence Gate／Pack successor，不得新增 Dell 专用脚本。Dell 完成前 `core_research_ready=false`，不得签发 S3。
