# S3 fixed-Pack 第一层：真实 repair 与内容验收

时间：2026-08-16

## 真实运行结果

clean/synced `78a2e13b...` 通过 Project OS 后，只执行了 R7 被拒绝的 counter／WWC repair。DeepSeek 在一次非思考调用中返回一个 Tool Call：`finish_reason=tool_calls`、prompt `6,357`、completion `530`，0 retry／fallback／外源／embedding／协议切换。R7 前六个模型节点按摘要复用，没有重跑。

模型把原来的“低毛利 AI 服务器占比、其他分部组合或一次性因素驱动公司毛利率回落”改成了明确的不可归因表述：公司毛利率回落与产品盈利达标可以并存，但当前证据不能把回落确定为 AI 服务器占比或其他单一因素导致。因果 guard、三片段合同和终态 Judgment 全部通过；Harness 没有改字或替模型选择结论。

## L1 与内容判断

L1 通过：公司／期间／Evidence／NumericFact／same-quarter relation 均正确，未把 gap 当事实，未把管理层产品目标写成审计利润，也未建立不存在的 AI server→分部／公司利润桥。

单单元适用维度为 `21/24`。它比旧 R2 的诊断 `18/24` 更安全且更聚焦，但不是严格同输入 A/B；精确可比的是 R7→repair：同一输入、同一 thesis/mechanism 和同一 Tool 合同，只修正被拒绝的因果越界。

仍有三条非阻断 finding：mechanism 的自然语言因果方向略倒置；WWC 应进一步指向产品收入／成本／利润桥，而不只观察公司毛利率方向；固定 Pack 只有一条直接法说 Evidence 和一条同口径数值关系，不能证明动态检索或报告级来源广度。

## 阶段处置

fixed-Pack Layer One 关闭。这表示“给定合格资料时，DeepSeek 能形成受约束、可纠错且不越过金融事实边界的单单元 Judgment”；它不计作 Agentic Research，也不是五单元研报。

下一步进入动态 Research Truth Spine 的零调用工程门：EvidenceRequest 必须真实执行 S1，返回 EvidenceResponse／typed gap；S2 返回 NumericFact／bridge authority；S3 只重裁决受影响单元。完成 replay、mutation、capture-first 和三案例隔离前，不签发动态 live。
