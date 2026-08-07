# 705 — FIN 0.1.3 S1-08 质量优先 SourceHunter × Capture Replay 零调用实现

日期：2026-08-08
阶段：`013-S1-08`
状态：`zero-call engineering pass / clean-commit independent proof pending / live not authorized`

## 1. 问题与实现判断

R1 暴露的不是四个互不相关的小 bug，而是同一个 candidate-generation 质量面没有共同合同：已有五类 evidence role，但没有成为带来源族、时效窗口、最低候选和停止条件的 Evidence Slot；locator 仍主要依赖关键词；抓取后没有正文研究角色门；异常时 formal partial result 只在整案返回后形成。

本轮按用户批准的 `S1-08Q-A..G` 一次性实现，没有启动 replacement live，也没有接触模型。

## 2. 完成内容

1. `Q-A`：建立 DELL R1 restricted manifest，精确引用 19 个 request capture digest/object key；Git 中不保存 raw body、headers 或 runtime contact。另建脱敏 portable fixture。
2. `Q-B`：`EvidenceSlot` 将五类研究目标编译为 required、source families、route ladder、currentness window、minimum candidate 和 stop condition。
3. `Q-C`：v2 catalog 以 provider-neutral capability 声明 SEC、IR、structured IR、本地 market 和 external site search。SEC、IR、本地 market 可运行；structured IR 尚无 feed/sitemap locator adapter，external site search 尚无运营 Provider，两者明确 `route_unavailable`，不冒充已实现能力。
4. `Q-D`：fetch 前统一处理 source family、path、title、form、date、as-of、slot fit、tracking query 和 canonical dedupe。Microsoft Outlook/Store/Surface/diversity/governance 等噪声被拒绝；SEC current filing 按质量/时效优先，2022/2023 stale filing 不进入 fetch。
5. `Q-E`：fetch 后再检查正文长度、Evidence Role、subject identity 和 commerce surface；成功 HTTP 不再自动成为 candidate。Web 文本仍不拥有 exact numeric authority。
6. `Q-F`：`RemoteDisconnected`、reset、abort、broken pipe 统一为 `official_source_connection_terminated`；candidate generation 每个 attempt 产生 content-addressed checkpoint，unexpected adapter failure 返回带既有 candidate、attempt、gap 和 count 的 partial result。
7. `Q-G`：真实 restricted store audit、sanitized replay、三案例 full-fake、noise/date/duplicate/transport/partial mutation 与效率门合并验证。

## 3. 结果

- actual R1 request objects verified=`19/19`；raw/headers emitted=`false/false`；
- replay request terminal classification=`19/19`，unpaired after repair=`0`；
- known navigation noise fetch=`0`；
- stale filing selected when newer eligible exists=`0`；
- Evidence Role candidate-or-typed-gap=`5/5`；
- qualified-document yield 达到 `>=0.5`；
- current successor budget=`<=16 network / 1 document per query / 0 model/provider/retry`；
- focused tests=`37 passed`；materializer byte-identical；
- live/model/provider/network/retry/admission=`0/0/0/0/0/0`。

工程 proof：`configs/releases/fin_ia_0_1_3_s1_08_quality_first_sourcehunter_capture_replay_zero_call_proof_v1_0.json`。

## 4. 没有完成与下一步

这只证明历史 R1 和确定性 fixture 上的结构修复，不证明 fresh live target-in-pool、外部站点可达、真实来源覆盖或研究报告质量。尤其 structured feed/sitemap locator 与 external/site-search Provider 仍不存在，产品当前仍不能宣称结构化 IR discovery 或广域 Web Search。

下一步先在 clean commit 的 disposable archive/fresh process 中独立复证。同一输出、测试和 restricted manifest binding 都成立后，才进入 `S1-08Q-H` DELL R2 replacement authority decision；不得自动签发或执行。
