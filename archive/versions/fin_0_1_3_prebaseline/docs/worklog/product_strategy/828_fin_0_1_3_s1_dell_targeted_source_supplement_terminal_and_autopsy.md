# 828 — FIN 0.1.3 S1 DELL 定向补源终态与零网络尸检

日期：2026-08-10

状态：exact-once terminal completed with typed gaps；下游模型未进入

## 做了什么

唯一 Run `fin013_s1_dell_targeted_source_e7d77ba0d1824fc2a6e4` 消费了 authority `e9b3819562ef02590efd3669cec3e41cd1ab6175c85ea02ffa60f6e42f0a1d46`。运行严格使用 `4 source network／0 retry／0 fallback／0 Provider search／0 model`，所有请求、响应或失败先进入受限 immutable capture，再做本地解析与 Evidence Gate。admission ledger 已 terminal，result digest=`0c590dc1ca8c9be512b30100c94d9b63a5e0a2d0bfcf2b05355715d32534c73a`。

本地五条官方记录全部通过：HPE 旧订单消化与需求不均、HPE 内存短缺及 AI 订单验收延长、SMCI AI GPU 增长／ASP／毛利、Microsoft AI 基础设施资本开支、Micron HBM 先进封装 2027 起步。这些材料补充客户需求、竞争、资本开支与供应时点，但只是 counterparty/competitor bounded read-through，不能改写为 Dell 特定订单、分配或利润事实。因此 DELL Evidence 从 15 增至 20，gap 仍为 16。

## 四条真实路线发生了什么

1. Dell Q1 FY27 法说：`official_source_transport_failed`，0/3 fragment。它是 issuer 自身订单、backlog、供需和利润纪律的 required route。
2. Micron Q3 FY26 slides：`official_source_transport_failed`，0/2 fragment。
3. TSMC Q1 2026 法说：官方 PDF 返回 HTTP 200、268,542 bytes，PDF parser 成功生成 65,259 字符正文；但配置把 `CoWoS`、`main supply`、`enough capacity` 要求为同一 fragment。首次命中位置跨度 18,170 字符，加窗口至少约 18,770 字符，超过 4,000 字符 hard ceiling，故本地 `dell_targeted_source_fragment_size_invalid` fail closed。这不是来源缺失，而是把两个不同问答段错误编译成一个证据片段。
4. Nasdaq DELL 2026-08-06 historical row：`official_source_transport_failed`，0/1 fragment。它是 independent point-in-time valuation required route。

三个 transport failure 的 immutable envelope 只保存 generic outer code，没有 DNS、TLS、timeout、remote disconnect 或 HTTP subtype；因此本轮不能诚实声称具体网络原因。该可观测性缺口继续归 RC-P36-168，不允许靠猜测补写。

## 为什么没有继续跑 DeepSeek

外部计划 fragment=`0/7`，Dell issuer route 与 Nasdaq PIT 两个 hard gate 均缺；`successor_pack_ready_for_zero_call_input_compilation=false`、`deepseek_exact_live_authorized=false`、`business_artifact_promoted=false`。用 20-item 半补源 Pack 继续跑报告，只会把来源缺失和模型分析能力混成一个实验，无法回答“新增信息是否改善判断”，所以按既定 stop rule 终止。

## 后续边界

- 不自动重试四条 route，不签发第二次 source authority。
- TSMC 使用现有 immutable capture 做零网络 replay；修复方向是同源多 fragment／Evidence group，不是扩大单片字符上限。
- Dell／Micron／Nasdaq 先补 provider-neutral sanitized transport cause envelope，并评估等价官方 HTML／IR mirror／合格来源 adapter；任何新网络运行都要 clean proof 与全新 authority。
- 第 4 步 enriched input compile、第 5 步 DeepSeek report comparison 均未进入；这不是 DeepSeek 失败，也不是新报告质量结论。

公开终态：`configs/releases/fin_ia_0_1_3_s1_dell_targeted_source_supplement_result_v1_0.json`。

## 2026-08-10 后续勘误

零网络读取同一 TSMC capture 后确认，上文“两个不同问答段／应拆为多 fragment”的归因不成立。`CoWoS` 有 4 次、`enough capacity` 有 3 次、`main supply` 有 1 次；旧 selector 只取各自第一次出现，才形成 18,170 字符跨度。同一 CoWoS 问答中三类锚点的最小连贯跨度仅 233 字符。修复改为枚举全部 occurrence 并选择 bounded 最小覆盖窗口，最终 excerpt 912 字符、4,000 上限不变。历史 exact-live 终态不改写；根因由后续 worklog 829 和 RC-P36-173 新 projection supersede。
