# FIN 0.1 S3-T09：DeepSeek 三 Cell exact live execution

日期：2026-07-22

## 执行结果

用户以“继续”授权已签发 admission 的唯一一次 exact live execution。真实执行前，假 Provider 首先暴露 canonical failure-code 命名空间缺口；该 owned blocker 以零真实调用修复并回归通过。随后 Project OS scoped preflight 为 pass/open blocker=0，exact runner preflight 再确认 identity、input digest、credential、retry=0、预算与空 execution state 均符合 admission。

admission 消费后，第一位 Demand Specialist 发出一次 DeepSeek 请求。输入为 8,973 tokens；模型输出正好达到节点 1,400-token cap，`finish_reason=length`。本地 closed-output adapter 因截断以 `s3_bounded_node_output_truncated` fail-closed，没有尝试解析或提交不完整研究产物，也没有继续剩余五个节点。

最终 WorkUnit、Attempt、ResearchRun 全部为 `failed`，Artifact=0，event=7，orphaned Run=false。真实 model/provider/network calls=`1/1/1`，transport attempts=1，output=1,400 tokens，latency=18,813 ms，estimated cost=`USD 0.00512125`；retry/fallback/rerun/source network/external tool/live Case head write 均为 0。终态后的 inspect 没有新增调用。

## 判断与边界

这次失败不是此前反复出现的 JSON shape 问题，也不是 API 认证、限流或 canonical 终态问题。Provider 正常接收并生成，只是 admission 给首节点的闭合输出容量不足。最早的 owned root cause 记为 RC-P36-035：第一位 Specialist 的 8.9k input、要求的闭合结构与 1.4k output cap 不匹配。

S3-T09 的“完整、可重建三 Cell Artifact”验收未通过，因此 T09 仍 failed，T10/S4/release/production 继续 blocked。consumed identity 不得复用。current next=`S3-T09-FIRST-NODE-TRUNCATION-ROOT-CAUSE-AND-REPAIR-DECISION`，需要单独授权；该 decision 只应零调用比较“收缩输入/输出合同”和“提高节点与总预算”，不自动签发或执行 replacement admission。
