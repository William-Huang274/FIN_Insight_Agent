# 207 · 人工完成、混合检索与跨主题记忆验收

2026-09-11 Owner 授权执行；FIN 0.1.3 不变。前序 206 已提交，部署待实际核对。

## 单一实施顺序

1. 恢复真实服务；核对 206 部署。补齐按钮样式与根据服务端完成状态自动归档的研究工作区。
2. 角色→底稿层级接人工修改：保留原件、改后正文、版本、修改位置与次数；模型语义疑点交人处理。失败 run 不改写；新结果明确“人工修改 X 次后完成”，不得把未处理问题或引用/取数/工具故障伪装成功。复用 LangGraph checkpoint/interrupt 与既有版本化底稿；不另造工作流。
3. 资料 RAG 使用已配置 Qwen embedding/reranker 与 rank_bm25，复用标准缓存、原文定位/权限过滤；记录实际模型 ID、用量、缓存与回退。云端参数规模不作未经官方验证的断言。
4. 1–2 个旧复杂题（HPE，第二题从旧失败列表按现有资料可用性选择）各执行一次最新 runtime；简单 SQL、跨公司自由研究、普通问答在连续对话中覆盖范围更正、模型/模式切换、摘要前后精确回读。预检先于付费，使用新 attempt；遇同类模型金融语义缺陷转人工，不展开新一轮 judge 调参。
5. 完成题按 owner 归入长期记忆目录：用户偏好、研究结果/修订、原始数字回执分开保存，复用 Agent Server Store 和现有检索工具；索引指向固定版本。验证新窗口回读、过时记忆更正、跨用户拒绝和缺记录不猜测。

## 验收与费用边界

- 每个 paid authority 记录任务目的/规模/必需输出/schema/风险/对照证据/推理强度/停止行为；不为追绿反复整案重跑。无响应/未知费用不自动重发。
- 样本是开发验收，不宣称盲测准确率。比较 BM25 与混合召回的 Recall@k/MRR、引用回读正确性；长期记忆分别测偏好、公司/期间/数值/单位/新旧决定，不能只测回答成功。
- 状态分别记产品增量、工程检查、真实运行与未完成项。一次研究得到报告仍不等于所有金融语义正确。

## 已查明

- 206 部署诊断不充分：实际 Docker Desktop 位于 Z:/Docker/Docker；已恢复引擎，完成构建、部署和真实界面验收，详见 206 工作记录。用户明确要求先收尾该项，207 当前仍为规划。
- 当前工作底稿使用 Qwen+sqlite-vec，原始资料导航仍主要 BM25，二者不能混称 RAG 已全面接入。
- 图示 research_bundle_invalid_citations 属于工程校验问题，不能按模型语义疑点跳过。

## 技术依据

- LangGraph checkpoint/interrupt 用于同线程恢复，Store 用于跨线程 namespace 记忆：https://docs.langchain.com/oss/python/langgraph/persistence
- 现有 Qwen OpenAI SDK 适配器、rank_bm25、LangChain splitter、DiskCache 优先复用；价格按实际地域/模型核对：https://www.alibabacloud.com/help/en/model-studio/model-pricing
