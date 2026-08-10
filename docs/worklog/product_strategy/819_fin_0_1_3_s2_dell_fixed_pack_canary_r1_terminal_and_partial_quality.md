# 819 — FIN 0.1.3 S2 DELL fixed-pack canary R1 terminal and partial quality

日期：2026-08-10

状态：terminal failed at call 6；no retry；partial outputs retained

唯一 DELL admission 已消费。direct baseline、Research Lead、demand、product、supply 三个 Specialist 成功；第 6 次 `financial_transmission_profit_and_cash` 请求在约 30.8 秒后收到 `RemoteDisconnected: Remote end closed connection without response`。失败请求 89,604 bytes，紧邻成功请求为 89,576–89,604 bytes，因此这次没有证据说明是确定性上下文容量超限。六次请求和响应（含失败）均先 capture，再 terminal；0 retry、0 fallback、0 tool/network research、0 business promotion。public result digest=`10223068d27217a26ba831acb7d48df6fd95f509027297e8af4fff31756d7aa2`。

这轮对 DeepSeek 也给出了新的正面证据。direct baseline 自然生成 8 个公司专属 section、32 个判断点（17 fact／7 bounded inference／3 hypothesis／5 gap）和 6 条 limitation；26 个判断带 Evidence alias、16 个判断显式引用 gap。Lead 正确拆成六个研究家族。已完成的三个 Specialist 分别形成 5／6／8 个 findings，并明确写出 Dell 订单与收入转化、AI 服务器 mix 对毛利的压力、客户集中、上游 GPU／内存／先进制造证据只能作 bounded read-through。相较历史占位句，内容已经具备真实投研语义。

但它仍不是合格研报。首先，链路没到 Synthesis、Draft、Red Team、Final 和 Verifier，因此无法做正式 Q1–Q8 或 paired acceptance。其次，Evidence Pack 本身没有市场时点估值、AI server 独立利润／现金、客户集中度、HBM/CoWoS 分配等资料；模型只能诚实保留 gap。第三，supply Specialist 虽然正确承认 Micron SSD／内存爬坡和 TSMC 制程收入不能证明 Dell 获得 HBM／CoWoS allocation，但这些证据对核心问题仍偏弱。

独立 deterministic review 对 direct baseline 给出 11 个 numeric-surface L1 和 1 个 uncited hypothesis。大多数不是明显假数，而是自然中文单位转换没有权威 trace，例如 source USD 16.132B 被写为 161.32 亿美元、USD 4,081M 被写为 40.81 亿美元；另有 55.6% 为模型自行计算的 mix share。正确修法不是禁止模型引用数字或放松验证，而是由 Harness 预编译 presentation aliases，并为 ratio/bridge 提供 deterministic formula ref。

下一步不能重跑全部 13 节点，也不能复用已消费 admission。需要先做一个零调用处置：是否允许新 successor 显式复用前 5 个 immutable captures，只授权失败节点和剩余 7 个节点；同时补 numeric presentation alias／formula trace。若采用 successor，跨 attempt lineage、累计预算和“无语义 retry”必须可验证。其余五案继续等待，不会被这次 DELL transport failure自动启动。
