# 790 — FIN 0.1.3 三个留出案例 current-source clean independent reproof

日期：2026-08-09

阶段：S1／留出案例对象形状泛化复证

状态：通过；只准入 CandidateBundle-only sparse/dense manifest 重定基

## 结果

从已推送提交 `340c2314623f85969942b6b63940342dc744c165` 导出两个独立 Git archive。每个 archive 只复制公开 source result 精确引用的 ORCL、ASML、ANET 三份 response-capture object；运行时重新校验 capture file SHA、canonical digest、body SHA、字节数、final URL、capture-before-parse 和凭据缺失标志。

两个 archive 各由一个 fresh Python process 执行 Project OS preflight、table-preserving reparse、typed object admission、CandidateBundleV2 与 9 类 mutation，结果均为：

- committed result digest：`a2184a963597a4f2bc355faf1f911796ed12af8abe8f5e2f11c83b80f942603c`；
- reproduced result digest：两次均完全相同；
- projected bundles：ORCL／ASML／ANET=`27／13／27`；
- projected Slots：`8／5／7`；
- mutation：两次均 `9/9`；
- network／Provider／model／embedding／rerank／Evidence promotion：两次均 0。

公开 proof digest：`7c8403307e2c5997aa6ffa5a1772be8a9c7ddb805e8d1f9d70b94efd0e898676`。

## 处置

这关闭的是“当前工作区是否靠残留文件偶然通过”的问题，可以把 object-shape generalization 记为 engineering pass。下一步只允许建立新的 sparse／dense **manifest 和零调用 build contract**：输入必须是选定 CandidateBundle，不是全部自动 claims；历史索引继续只读；Ubuntu WSL Milvus qualification 可复用，但真实 BGE／Milvus 写入仍需在 manifest、依赖、目标目录和 exact-once terminal 合同冻结后另签 authority。

Evidence Pack、外源 residual supplement、DeepSeek 动态研究、研报内容质量和 qualified-human acceptance 均未完成，不能随本 proof 一起放行。
