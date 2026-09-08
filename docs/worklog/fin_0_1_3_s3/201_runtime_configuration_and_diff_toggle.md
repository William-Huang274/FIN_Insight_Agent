# S3/201 · 可执行研究配置与差异收起

日期：2026-09-08。产品仍 FIN 0.1.3，当前报告 v5 待 Owner 审阅。

Owner 指出 200 的配置只是文件与浏览器草稿，明确要求编辑后后端生效；截图的收不起区域实际是研究图的报告 diff，上轮误修资料面板。此次在原 S3/S4 完成运行配置接线与修复，不扩大到任意代码工作流编辑，不开始 Hermes/公开发布。

采用：已安装 LangGraph SDK Assistants（`_async/assistants.py` create/get/search），原生数据库保存每次独立配置快照，原生线程 metadata 选择版本，原生 run config 固定实际方法内容。没有新配置数据库、锁、工作流引擎。模型与审查沿已有 LangChain create_agent、LangGraph StateGraph、MCP v2。

可编辑范围：六项方法全文、十角色方法绑定、专家及责任修订并行 1/2、双审查 parallel/counter_first/verifier_first。原生图实际改变审查边；两个角色各自读取资料、不传 sibling messages。保存不会启动模型；应用后下一运行采用；旧保存版本不覆盖，重新选择旧版本可回退。模型预算/工具权限/必需复核不可从此入口解除。

研究图 diff 增加顶部切换和底部收起/焦点返回，隐藏时保留已加载内容；新报告版本重置。报告历史与修订列表原有可读对照继续保留。

## 分阶段验证与执行记录

- 35 原有后端检查通过；新 native review 顺序、独立消息、配置隔离、Assistants 写入/应用/防外部改写、create_agent 系统提示及真实 MCP 方法读回共 7 通过。
- 近邻检查 40 passed / 7 skipped（本地归档材料依赖未满足，不算通过）。
- 浏览器 A1 10 passed / 3 failed：新增配置下拉对旧测试服务返回的空对象缺少防护，导致新研究页崩溃。保留 `D:/temp/fin-studio-runtime-a1/results`；已修边界校验，待 A2。
- 原生 API 新镜像已构建，确认无运行中任务后重载，PG/Redis 与原数据保留。BFF8793 PID41524；旧8766未重启。

## 有界真实消费验证的 TokenBudgetBasis

Owner 已授权前端接后端时 1–2 个真实小操作，并允许真实模型调用；S3/199 已做一次目标修订。本次只追加一次短问，验证编辑后的 Skill 进入实际模型请求与输出，展示真实运行界面；不是重跑完整研究。

- 节点目的：现有 quick_writer，解释报告已存的现金流/利润口径并输出简洁回答。
- 输入规模：既有问题、紧凑底稿目录与当前公开会话；报告按需回读；原 Writer 方法约千字，新增只要求短问使用“结论／限定”两段。没有扩大数据范围。
- 必需输出：简短中文结论、相关期间/口径/非回款率限定，按需要引用已保存来源；报告不重写。
- schema burden：现有 read_current_report、只读数据工具、submit_case_answer；沿已资格 Flash 原生工具循环。
- materiality/quality risk：不能将比值当回款率或使用旧 claim 因果陈述；不自动接受报告、不把界面成功称财务审阅通过。
- comparable evidence：S3/190 已有 SQL/calculator 短问 3 调用、28776 tokens、估0.019796元；本任务真实上下文可能更大，不承诺该成本。
- reasoning profile：deepseek-v4-flash / thinking disabled / low。
- 运行容量：保留现有 quick_writer 10 model calls / 32 tool calls、max_input_characters350000、max_output_tokens8000、timeout240s、单次transport；新增方法最多原文+2000字符的服务端限制并非扩大模型输入上限。
- stop/truncation：沿已有 fail_closed_no_partial_promotion / fail_before_transport，无重试/fallback。仅一次请求，预计0.02–0.2元；如失败或未知用量先审计，不为追绿自动重发。实际费用单列。

以上为调用前预算记录。真实运行结果如下；RC-S3-199 的旧 claim advisory 独立保持开放。

## 实际结果与最终接缝修复

- CUA 在真实8793界面编辑 Writer Skill，追加简短追问按“结论／限定”组织；保存配置 `42857090-55f8-43f3-aa79-be9905bc4f41`，摘要 `c2d02c243bd4d10689dd04a871f3622f4fdd1b67d576f6faea39f70edba00857`，名称“清晰短问 · 顺序审查”。并行数1、counter_first。同页面应用到219488任务，原生metadata回读一致。
- 前端 quick 问答实际执行 `01a08075-3c4e-7e72-a84b-8037fb26573a`，success，约14.973秒；2次Flash/43622 tokens（输入42874、输出748、缓存命中17024），已知估费0.085984元，未知0。没有后续paid重试。
- 两次私有请求均检查到新增方法文字（只导出布尔证明，不公开私有消息），回答确有“结论”“限定”；读取当前报告后提交答案。前后 report 对象完全一致、report_version仍5，只增加一问一答。此证据证明配置消费与闭环，不是财务语义独立验收；旧C9引用仍有advisory，未因页面通过而消失。
- `D:/temp/fin-studio-runtime-a1/consumption-proof.json` 记录实际消费、使用量及原生配置加载事件；baseline/final/progress-01保留。原审计在原 calls/thread/run 目录，不覆盖或删历史。
- 发现并修复专家路径的请求摘要接缝：不能在 provider adapter 外修改已生成请求，否则 RuntimeReceipt digest 与图校验不一致。改为在专家初始 L0 skill context 中绑定方法，再统一生成请求/摘要。带回执专家图实际执行通过。该发现未触发任何额外付费专家请求；此前短问不涉及该路径。
- 补充测试首次40通过/1失败为新增测试合成动作缺 context_digest，保留命令输出；补上标准动作字段后41通过（含原生专家图33项和配置8项）。原77后端通过/7本地材料依赖跳过，与41检查重叠不相加。旧材料依赖跳过不计成功。
- 最终完整前端A3：13通过，42.1秒；覆盖1440/1024/390、配置编辑保存应用回读、差异顶部/底部收起及零模型回放。A1失败原件保留；A2已有13通过40.6秒。
- 真实本地只读页面检查：保存配置回读、研究图diff三次展开/收起、真实历史事件暂停与定位；0写入、0浏览器异常，见A3/ui-proof.json。视觉复核后修正全局按钮样式覆盖节点网格，并补齐配置/短问角色中文名称；最后截图和相关回归见A4。

产品增量：可执行方法/编排编辑、明确生效范围、可收起差异与可操作运行记录。工程增量：原生Assistants/run配置、按运行MCP方法、真正原生审查顺序、专家请求摘要一致性。研究证据：一次真实短问消费；不等于全新九面重跑或所有角色paid验收。文档更新：本记录、前端总体方案、Project OS。剩余：Owner体验、旧claim advisory、GitHub阶段性整理；任意添加Agent代码/删除必需复核不在本编辑器范围。Hermes继续后置。

最终 A4：4 项相关浏览器回归通过（12秒），包含三宽度配置编辑及运行回放；最终真实截图及 `ui-proof.json` 在 `D:/temp/fin-studio-runtime-a4/`，真实diff三次收起、0页面异常/0写入。TypeScript通过，Vite构建通过；已有大bundle/zod注释提示未列为错误或已解决。专家接缝最终镜像已再次重载，镜像manifest `649685f7fb60cfd4006825562a1d0032763b0a34bd7a2e2bcca9918b060f8d28`，原PG/Redis保留，未追加paid。应用的配置版本在原生重启后读回一致。

本地代码提交：8599cba4（20 个代码/测试文件）；产品版本仍为 FIN 0.1.3，未推送远端。
