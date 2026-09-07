# 114｜protected remap 完整交卷被拒与定向 patch 边界

## v1.1 replacement 的真实结果

- 运行：`FIN_0_1_3_S3_DELL_MULTI_AGENT_PROTECTED_REPORT_REMAP_REPLACEMENT_20260821`；实现提交：`f3a54f1e90230a35812a33989564edc1e0fc912c`。
- 一个 Writer-only logical node 共执行两个有界 contract attempt；零 analysis、continuation、upstream Agent、repair、Evaluator、network 和 Candidate promotion，scope 合规。
- 两次 Provider 响应均为完整 Tool Call，`finish_reason=tool_calls`。第一份 usage 为 `41,266 / 6,263`，第二份为 `47,623 / 6,202`；12,000-token profile 已解除首次运行的 arguments 截断。
- 两次提交仍被 `multi_agent_report_model_text_unprotected_surface` 拒绝，因此没有 draft、rendered report 或可追认的 L1 结果。legacy report 继续为 `financial_truth_L1_pass=false`。

## 离线逐字段回放

笼统错误码实际同时承担了“受保护表面违规”和“字段长度越界”。逐字段回放没有发现数字、URL、内部 alias 或单位进入本轮 model prose；真正的第一个失败是字符上限：

- executive thesis：`1,460 / 1,449`，旧硬上限 `900`；
- demand section：`1,031`，旧硬上限 `900`；
- value section：`910`，旧硬上限 `900`；
- cash section：`1,226`，旧硬上限 `900`；
- counter section：`920`，旧硬上限 `900`。

把旧长度硬门仅用于诊断性放宽后，两次完整 payload 还共同暴露五个引用绑定问题：executive thesis 选择了不属于所选 claim 的 relation；Counter section 使用了 Supply claim；一条 Demand gap 没有 gap ref；一条 Value gap 和一条 WWC 使用了 Operating claim。第二次 attempt 还把一个 gap ref 写成了不存在的近似 ID。

第二次 attempt 只修改 executive thesis 和一个 gap ref，其他错误保持不变。原因不是 feedback seam 没执行，而是反馈只给出一个笼统 code，没有字段路径、实际长度、错误引用或允许范围；模型只能盲改。

## 最早责任层与下一边界

本轮阻断属于 S0 Harness／S3 terminal contract feedback，不属于 S1 数据、S2 NumericFact、上游六 Specialist、Lead、Evaluator、网络或 Provider 截断。

下一步不得再次重写整份四万字符输入，也不得由 Harness 手工删段或替模型选择研究引用。结构修复必须：

1. 将叙事推荐长度与安全容量硬门分开；超出推荐长度进入内容质量 finding，只有低于最低长度、超过安全容量或出现受保护表面才 hard fail。
2. 一次返回所有可修复字段的 path、错误类别、offending refs 和 path-scoped allowed refs。
3. 复用第二份完整 immutable payload，只允许一个新的 Writer reference-patch successor 修改失败字段的引用集合；model text 和全部通过字段保持 digest-bound immutable。
4. 先用两份真实 capture 做零调用 replay／mutation；通过完整工程门、clean commit／push、fresh preflight 和新 authority 后，才允许该有界 successor。

即使 patch 成功，仍须独立金融事实 L1、八维内容质量、与 legacy report 的语义保真／paired comparison 和 qualified-human 边界审查。S1、S3、泛化、Workbench 与 release 继续为 false。
