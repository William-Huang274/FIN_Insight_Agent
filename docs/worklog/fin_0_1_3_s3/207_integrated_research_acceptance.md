# 207 · 人工完成、混合检索与跨主题记忆验收

2026-09-11 Owner 授权执行；FIN 0.1.3 不变。前序 206 已完成部署。207 当前为实现已通过本地检查、真实资格待执行。

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

## 207 实现切片（真实验收前）

- 产品：现有报告人工审阅 interrupt 接直接编辑报告/角色底稿、原文差异和人工次数，完成后留在可多轮恢复的 human_review 节点；原始失败/审查不覆盖。自动完成区按服务端 phase 分类。文件选择器现代化。底稿画廊同时列最新人工正文和历史原件。
- 工程：人工入口校验基础版本、引用绑定、任务内底稿 ID、用户确认；数据/工具故障不能靠按钮转绿。LangGraph 原生 checkpoint/Store 持久化，不新造流程。长期记忆按 owner 保存 report checkpoint + 研究要求版本，四区域分别回读；只做目录/精确指针，不称已完成语义长期记忆。
- 原文 RAG：现有 BM25 + LangChain InMemoryVectorStore + Qwen text-embedding-v4/qwen3-rerank + DiskCache。先过滤当前文档范围。显式准备索引，搜索最多查询向量/重排各一次；未准备时明确退回 BM25，不隐式全文付费。失败/未知请求不自动重发。缓存有输入规模/用途/风险等逐调用依据。
- 已检验：共享后端 86 passed（与前次65等重叠，不累加）；人工节点6项验证原checkpoint不变、修改版本递增、无模型调用、陈旧/非法引用拒绝。前端5项浏览器检查含1440/390人工编辑和完成区；修复移动端checkbox被flex压为零。TypeScript/Vite通过，保留既有大bundle提醒。Project OS interactive preflight通过，非全产品通过。
- 尚未计入：部署、真实旧复杂题、新连续多主题问答、真实Qwen检索质量、长期跨窗口模型回读。至本记录无207付费调用。
- 开发验收材料：D:/temp/fin207/hpe-source-nodes.json（只读提取旧上传原文，396叶节点/762向量切片约111万字符）与hpe-rag-queries-a1.json（6个公开开发问题/目标页，非盲测）。预计77个批量embedding请求以及每问题至多2个检索请求；真实统计以缓存回执为准。索引写入本项目working-memory/source-rag，原年报/旧任务不修改。
