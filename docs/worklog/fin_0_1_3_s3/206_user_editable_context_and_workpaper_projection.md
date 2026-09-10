# 206 · 用户直接编辑研究要求与历史工作底稿投影

日期：2026-09-11
范围：FIN 0.1.3 S3 工作台前端、BFF 和现有 native/Hermes 运行时。
性质：产品与工程增量；无模型调用、无历史研究数据改写。

## 要解决的问题

HPE 研究现场把内部编排分支 ID（如 `Q1_ISSUER_TRUTH`）直接放进面向研究者的活动文本；“工作底稿”只查询持久记忆，因此历史 checkpoint 中已经提交或失败前保留的自然语言底稿看起来像不存在；用户能够通过聊天追加意见，却没有可版本化、直接编辑的研究范围入口。

## 实现

- 公共活动投影默认折叠包含内部 Q 分支标识的调度文字，只呈现可理解的阶段说明；内部标识保留在折叠的运行记录中，既不改变 Agent 图的 canonical ID，也不把它误作研究者需要操作的菜单。
- 读取研究 checkpoint 的 `case_papers` 和 `research_failed_workpapers`，仅投影责任角色、可读摘要、提交正文、判断、反证、改变条件与待核查事项。工具调用、原始模型推理、私有状态与执行 trace 不进入该投影。历史提交标记为只读原件。
- 工作底稿弹窗打开即展示卡片缩略图和责任角色；可编辑的持久底稿可直接编辑、版本冲突受保护、保存产生新版，不启动模型、不改写正式报告。模型协助修订降为可展开的次级入口。
- 新增“研究设置与记忆”菜单。用户直接编辑的研究要求存入既有 `WorkingMemory`，actor 为 `user_context`；保存不调用模型。后续 native 对话、Hermes 桥接、研究阶段 guidance 与 Dell 报告会话都会读取最新版要求。该要求被明确标注为范围/偏好/待核查假设，不是已核验事实，也不能授予工具或文件权限。
- 当前运行时仍拒绝保存，避免在单次 Agent 节点执行中途改变输入快照；停止或完成后保存的版本供下一次运行读取。这样保证用户意见可被采纳，但不伪造“本轮已重新推理”。

## 验证

- 后端：`78 passed in 26.32s`，覆盖研究会话、BFF、报告会话、对话 Agent、Hermes 工作记忆桥接与新增直接编辑/历史 checkpoint 底稿测试。
- 前端：TypeScript 无错误，Vite production build 成功；Playwright 7/7 通过，覆盖宽屏/窄屏的直接编辑、工作底稿展示与研究现场。
- 未产生 DeepSeek/Qwen/Hermes 付费调用；没有修改实际 HPE thread 数据。

## 剩余与部署

这项实现尚未加载进 Docker 原生运行时：本机 Docker Desktop Linux 引擎的命名管道不存在，`com.docker.service` 停止且当前会话无权启动该 Windows 服务。静态前端已完成 production build；Docker 引擎恢复后，应重新构建并 `up --no-build` 原生 API、重启 BFF，随后以现有 HPE thread 做只读 API 验证。不能把这个部署阻塞写成产品已验证。

### 2026-09-11 部署收尾：上述阻塞已解除

- 用户要求先完成 206 部署，再开展 207。实际 Docker 安装路径为 `Z:/Docker/Docker`；此前只检查常见 C 盘路径与 Windows 服务，诊断不充分。恢复引擎后已重新构建 `06648d22` 原生镜像并执行原 Compose 项目的 `up --no-build`，复用原 PostgreSQL/Redis 卷。三个容器均 healthy。
- 产品部署：18165 原生 API `/ok` 成功；18795 BFF 与生产前端已启动；18806 Hermes 已恢复，宿主机和原生容器访问其 `/health` 均为 200。四个运行时文件（user_context、conversation_agent、research_session_runtime、dell_report_session）的容器内容 SHA-256 与仓库一致。
- 真实界面证据：HPE `01a084e8-6088-7e10-a595-de82201e8020` 的底稿弹窗无搜索即显示两张角色卡片（收入、利润与现金／量价与产品组合），分别标识历史提交和未完成候选；可打开正文，原件只读。原始调度说明默认折叠。“研究设置与记忆”可打开且输入框可用。1440 宽屏与 390 窄屏检查通过，dialog 无横向溢出，pageerror 为 0。HPE checkpoint 未写入，旧失败状态保留。
- 实际编辑验收：创建独立且明确标识的“界面验收 206 · 无模型调用”空白对话 `01a08c72-0763-7ba2-8eb3-991e9cc5c927`，种入非研究测试底稿。真实浏览器验证要求保存→刷新→清空→刷新，清空后 user_context_prompt 为空；底稿直接保存新版→读取旧版原文。最终验收仅 3 次 PUT，无模型运行 POST。准备阶段 draft 创建接口明确返回 model_calls=0。
- 验收脚本最初两项失败属于测试同步/选择错误：菜单 GET 未完成即断言，以及选择首张卡片误选“我的研究要求”；改为等待加载和按测试底稿标题定位后通过。没有修改产品实现来迎合断言。所有试写仅在上述独立测试对话中。
- 工程增量：本次没有新增运行时代码；加载并核实已提交实现。没有 DeepSeek/Qwen 付费请求，没有借此重跑金融研究。Hermes 使用既有隔离依赖和 home，仍是已定义的工作底稿试用能力，不代表整体适配或长期记忆验收完成。
- 本地证据：`D:/temp/fin206-live-ui.cjs`、`fin206-live-edit.cjs`、`fin206-ui-receipt.json`、`fin206-live-edit-receipt.json`；截图 `fin206-hpe-workpapers.png`、`fin206-context-menu.png`、`fin206-hpe-mobile.png`。运行日志 `fin206-workbench.*.log`、`fin206-hermes-a2.*.log`。本机路径用于开发验收，不提交数据和服务凭据。

206 部署关闭；207 的旧复杂案例、人工作业闭环、长期记忆和混合 RAG 仍是下一工作包，不能计为本次完成项。

