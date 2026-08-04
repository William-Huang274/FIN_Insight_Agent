# FIN 0.1.2 S4-T04 R2 post-Verifier budget capacity failure

时间：2026-08-04

R2 在 clean/synced `3125c7e6` 上 exact-once 消费，classifier 假阳性没有复发。六个 Specialist 段、Lead、Writer、Verifier 共 9 次 DeepSeek Pro 调用全部 `finish_reason=stop` 且为合法 JSON；三 Cell 各形成 2 claims/3 WWC，Lead 为 1 dependency/2 conflicts/3 gaps，Writer 为 6 renderings，Verifier 四层均报 pass 并给出 `accept_for_internal_review`。

正式 terminal 仍为 failed：累计输入 63,419 tokens 超过 execution envelope 固定的 60,000 上限。Verifier 本次输入 19,726 tokens，是最大单节点；capture-first runner 已保存第九份输出，随后在把 Verifier 交还 Artifact assembly 前以 `node_envelope_accounting / s3_bounded_node_envelope_accounting_failed` 终止。总 output=3,096，cost=USD 0.0302808，provider latency sum=46,459 ms，9 captures、3 local Fact receipts、0 formal Artifacts、0 retry/fallback/R3。

受限零模型 replay 在临时目录中证明同一 9 份输出可通过现有 schema、lineage、identity、numeric 和九件套组装；diagnostic artifact digest=`05c02591…f62`，0 canonical/business write，不能反向晋升或改写 R2。正式 L1、paired L1–L4、Owner acceptance、current NVDA R2 均未成立。

新增 RC-P36-117：admission preflight 没有对 current Evidence 的累计请求尺寸和 Verifier view 做容量证明。下一步只能先做零调用 capacity/verifier-view 处置，不能根据已观测的 63,419 直接随意抬 cap，也不能自动 R3。
