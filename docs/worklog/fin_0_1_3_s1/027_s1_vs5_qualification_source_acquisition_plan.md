# FIN 0.1.3 S1 VS5 资格来源获取计划

日期：2026-08-18

状态：`source_routes_frozen_before_capture / source_outcomes_not_yet_parsed / S1_not_qualified`

## 1. 本轮只做什么

本轮复用同一个 capture-first 官方来源引擎，获取预注册的 7 个 source targets：Costco FY2024/FY2025 10-K、JPMorgan FY2025 10-K、Caterpillar FY2025 10-K、Novo Nordisk FY2025 20-F、Shell FY2025 20-F、腾讯 FY2025 官方年报 PDF。

SEC 路线只访问已经绑定的 `www.sec.gov` filing URL；腾讯路线只访问已经绑定的 `static.www.tencent.com` PDF。原始响应必须先进入内容寻址私有存储，之后才允许解析。网页或 PDF 本身在 Evidence Gate 前都只是 source，不是 Evidence。

## 2. 为什么新增通用入口

旧捕获实现能够复用，但 schema 和命令名分别绑定 `S1-B`、`S1-D`。继续复制 `VS5` runner 会扩大一次性脚本债务。因此本轮只给同一引擎增加 provider-neutral 的通用 plan/result schema 和一个通用 CLI；旧 plan 继续兼容，未来新的官方来源任务不再复制 stage-specific runner。

## 3. 资格边界

- route IDs 必须与预注册 source target IDs 完全一致；
- 每条路线的网络尝试不得超过预注册上限；
- 不允许 broad web search、凭据、Cookie 或运行时标签；
- source capture 可以失败并保留 typed transport failure，但不得用未注册来源偷偷补齐；
- 本步骤 0 次模型调用，且尚不运行向量或重排；后续 learned retrieval 仍强制 `CUDA + FP16`，禁止 CPU fallback。

## 4. 下一步

先提交并推送本计划和通用 capture 入口，再执行一次新的 immutable capture attempt。捕获结果将决定解析路线，但不得反向修改已预注册的案例、门槛或隐藏执行次数。
