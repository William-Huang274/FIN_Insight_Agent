# 751 — FIN 0.1.3 S1-08 Provider portfolio 与 production search 边界决策

日期：2026-08-08

## 决策

停止继续按“单个 broad Web Search Provider 必须同时满足一手目标召回、Provider 日期、低延迟、低成本和来源多样性”轮测供应商。该假设与 PRD 的职责划分冲突：search 负责发现 candidate，原文 capture、本地日期裁决和 Evidence Gate 才拥有金融权威。

选择 official-first、role-specific portfolio：

1. SEC、issuer IR feed/sitemap、official-domain bounded discovery 负责 known primary source；
2. Firecrawl 只进入 discovery-only shadow implementation 候选，依据是同矩阵找回 `5/6` frozen case-slot target；它仍不是生产 Provider、事实源或日期权威；
3. Tencent standard 因同矩阵 `0/6` 保持 diagnostic-only；
4. 百度／阿里采购和 live 比较暂停，先证明组合路由、capture、本地日期与 Evidence Gate 能形成完整候选链；
5. provider date 仅是 locator telemetry；本地 capture-backed publication-date decision 仍是 portfolio/Evidence 硬门。

历史 Firecrawl/Tencent result、assessment 和 scoring contract 全部保持 immutable。本决策只 supersede “一个 Provider 必须包办所有层级后才可考虑任何 role integration”的假设，不放宽 target-in-pool、capture-first、relationship、canonical identity、Evidence promotion 或 Writer no-source。

## 本轮调用与能力边界

provider/network/model/document/Evidence=`0/0/0/0/0`。没有接入 Firecrawl、没有签发 live、没有购买或测试新 Provider、没有关闭 S1-08。

下一项：`S1_08_OFFICIAL_FIRST_SOURCEHUNTER_PORTFOLIO_AND_DISCOVERY_SHADOW_ZERO_CALL_IMPLEMENTATION`。它只允许用 immutable captures 和三案 fixture 实现/回放 route planner 与 SearchQualityCard；通过后才另行决定一次 combined-route live proof。

## 验证

- 决策合同专项：`5 passed`；
- Firecrawl 历史合同与新边界组合专项：`16 passed`；
- S1-08 全组：`205 passed / 3360 deselected`；
- Project OS：已完成的 post-Tencent decision scope=`blocked`，新零调用 implementation scope=`pass`；
- JSON/JSONL、decision digest、历史 scoring SHA、`git diff --check` 与本轮新增内容凭据扫描均通过。

完整回归最初发现一条旧测试仍把已完成的 post-Tencent decision 当作 current next；该测试已改为同时验证旧 decision fail-closed 与新 implementation 可执行，没有删除门禁或篡改历史运行证据。
