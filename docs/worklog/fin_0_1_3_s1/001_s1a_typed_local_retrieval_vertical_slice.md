# S1-A 类型化本地检索纵切工作记录

日期：2026-08-12

## 决策

不复活旧 29GB dense/Milvus 链。先修查询前的金融语义合同和真实产品消费者，因为零改动尸检确认当前活动主干只有建索引、没有查询到 Workbench 的链。

## 执行与反思

1. R1 用 9 个宽 slot 查询生成候选，工程硬约束通过，但业务复核发现通用财务段落仍主导榜单。不能以“lane 非空”代替研究相关性，R1 留作失败 capture。
2. R2 增加 anchor 与标题权重，仍暴露一个 slot 同时承担多个问题的竞争。
3. R3 将 9 slot 拆为 17 facet，保留 subject/related owner 公平预算和候选业务边界。
4. DELL/MU/NVDA 同核心迁移通过；MU reviewed target 为 0，反而明确证明历史 candidate store 缺最新 supplemental objects，不能把它包装成 ranking pass。
5. 加入 Workbench 检索候选页，使用户能看到查了什么、为何入选、哪些只是行业背景、哪些来源角色确实缺失。

## 不变边界

- 0 模型、0 网络、0 dense、0 rerank。
- 候选不是 Evidence；当前 reviewed Pack 没有被替换。
- S1 尚未完成；下一步归属 S1-B source/object，而不是 S2/S3 或新版本。

## 收口验证

- 当前检索快照可重复构建，结果 digest 为 `83bf94be824d6c8906cea17baba78e6ad4a2e98c97a7809bdbef953d5e88ad25`。
- 完整 Python suite：48 passed。
- 前端 TypeScript typecheck 与 Vite production build：通过；真实检索页 Chromium E2E：3 passed。
- 活动基线图：65 个 Python 文件、7 个前端文件、4 个运行资源、3 个 detector；旧消费者引用与未解析 import 均为 0。
- Workbench 产品投影不包含 reviewed/qrel 命中标记；候选始终标记为 `candidate_not_evidence`。
- 全仓 secret scan：6,243 个文件，0 finding。
