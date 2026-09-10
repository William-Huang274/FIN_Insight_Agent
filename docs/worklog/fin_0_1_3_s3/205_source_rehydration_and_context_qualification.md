# 205：原任务回读、交付边界与上下文组件资格

日期：2026-09-09。所属仍为 FIN 0.1.3 / S3；本记录不创建产品版本，也不把失败升级成通过。

## 范围与结论

> 后续实证更正：[原始推理诊断与三档对照](205_reasoning_trace_diagnostics.md)发现第五次调用的计算工具当时已被runtime提前关闭；“未形成纠正凭证”不能仅归为模型执行弱。已修保留倒数第二次纠错窗口，局部回放通过，真实高/max并未稳定改善参数/语义；完整审查仍未通过。

> 2026-09-10 原始推理字段复查更正（优先于下方旧归因）：用户追问后，实际读取 `D:/temp/fin205-hpe-search-review-a1/model-context.private.jsonl` 的五条 response。均保存 `additional_kwargs.reasoning_content`（合计 29,346 字符），事件配置均为 Flash / thinking enabled / low。模型在发工具前已正确理解亏损符号与预期分母，但实际第一条工具参数仍写成减去正数 437；收到结果后，返回的推理文本明确识别了自身公式错误。因此旧表述“模型未核对结果”过强，应区分“已识别错误”与“未补齐可验证纠正”。第二条工具确认分母 2627，但没有新增正确覆盖率的工具计算；模型继续以原候选及自行运算支持约 80.4%，准备 complete / 无发现，最后提交仍是无效 JSON。80.4% 本身不是本例算术错误，缺陷是工具参数与其解释不一致，以及错误识别后未形成完整纠正凭证。推理文本还反复讨论未勾稽事项，最终却准备空未决项；能定位判断到执行/完成状态的脱节，不能据此证明模型的内部因果机制或推广到全部 CFO/FCF 错误。只记录高层诊断，不复制私有推理正文到仓库。此次为已有证据复查及文档更正，0 新模型调用、0 源码/部署增量，金融验收仍未完成。

Owner 要求继续第一、第二步，集中定位全链路原因、采用成熟栈并实施必要自研。承接 [全链路审计](205_hpe_full_chain_root_cause_audit.md)，本轮完成原生恢复后的精确回读、归档来源检索、工具能力对齐和提交约束的工程切片，执行一个 HPE 已保存修订单元及同一真实长历史的两个上下文接续臂。没有再跑完整 HPE，也没有回写原产品窗口。

**工程故障与模型质量必须分开。** HPE 最新局部复核仍未正式提交，并出现模型解释与刚返回的计算结果不一致；两组上下文均能回读原计算，但最终提交未通过。因此复杂研究的金融验收、第一步整体验收和 Hermes 完整适配仍未完成。本记录交付的是可复现的诊断、已实现的通用修复与完成执行的组件对照，不是可用 HPE 报告。

## 1. 已集中定位的共同原因

| 故障位置 | 实际证据 | 本轮处置与边界 |
|---|---|---|
| 专家恢复后读记录身份失配 | HPE 原始 43 个成功读请求，在新 invocation 下按新 ID 查找为 0；44 条观察其实仍在 | 原生 state 保留每个历史 turn 的 invocation 对应关系，43→43 可达，原件不改。不是新增事件库 |
| 模型可见工具与执行权限不一致 | 关闭修订实验时仍向模型提供/推荐 ReviseWorkpaperAction | 从同一个 allowed_actions 生成模型工具列表，禁用工具不再成为死路；SDK 实际 payload 回归 |
| 已读材料只能整段携带或逐个翻读 | HPE/MSFT 来源已归档却缺关键词定位入口 | SQLite FTS5 查询当前任务的来源视图，返回精确 source_id、窗口 offset，继续沿既有 reader 回读 |
| 审查承认未完成却形式上通过 | 旧复核正文提及未核实事项，默认空未决列表令结构合法 | 所有新 case/report review 提交强制 completion 与未决列表一致；旧持久记录仍兼容，不回填通过 |
| 来源别名被当成判断编号 | 两臂均把真实操作数来源 P01:S045 判为未知 claim | 提交器按 reader 的精确来源目录解析，保留来源权威性；未知或缩写 ID 不猜测替换 |
| 诊断文本与证据引用混用 | 原生回答在错误分析中提到未绑定 NUMFACT 和缩写 PASSAGE::WEB；Hermes 回答也提到后者 | 保留既有 Markdown AST 边界：错误中的标识可用 code 表示，金融主张仍须真实引用。新增工具说明；没有按句意手写例外或删除失败答案中的内容 |
| 模型解释与工具结果不一致 | HPE 第一计算返回约 1.20479，之后却把它描述为约 80.4% 且称全部算术已核实 | 判为金融质量失败，保留原计算和原回答；不写 HPE 专用正负号规则，不以 schema 合法代替语义核验 |

前次跨用例审计中的 HPE 与 MSFT 任务重建，以及简单 NVDA/MU 的过度编排，仍按原责任阶段处理。不能把所有 token 消耗都归因于压缩，也不能用这次局部修复宣称问题覆盖充分性已经解决。

## 2. 已采用与暂缓的技术栈

| 技术 | 决定 | FIN 保留的责任 |
|---|---|---|
| LangGraph checkpoint / 原生 state + LangChain create_agent / ToolNode | 继续采用；恢复、循环、工具反馈、并发不另造引擎 | 同任务身份、来源目录、研究交付与未决事项 |
| SQLite FTS5 / BM25 / highlight | 已接入归档来源搜索，内存索引限定当前已授权 case 视图；数值来源、Unicode offset、隔离已测 | 精确 source_id/offset、原文与权威边界；无结果不等于未披露 |
| Deep Agents 的外置与按需回读方式 | 借鉴方法，未引入整套 harness | 使用本项目已有不可变来源和工具 artifact，不另做通用文件系统/摘要服务 |
| Hermes 官方既有摘要投影 | 完成同历史的受限回读比较；仍不作为默认 runtime 或记忆权威 | 原始记录仍留在原生 checkpoint；摘要只替换请求前缀，不能替换财务事实 |
| Pydantic / 原生工具 schema | 已用于要求明确完成状态、反馈错误 | 不能证明金融语义或保证供应商总返回合法 JSON |
| DeepSeek strict tools beta | 暂缓全局切换，尚未发起 beta 调用 | 官方要求所有字段 required、禁止 additionalProperties；现有操作数字典/撤回理由字典及部分约束不能直接原样切换，需独立 wire schema 资格 |

官方依据：[SQLite FTS5](https://www.sqlite.org/fts5.html)、[Deep Agents 上下文工程](https://docs.langchain.com/oss/python/deepagents/context-engineering)、[Hermes 压缩与缓存](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)、[LangChain 结构化输出](https://docs.langchain.com/oss/python/langchain/structured-output)、[DeepSeek strict tools](https://api-docs.deepseek.com/guides/tool_calls/)。

DeepSeek 官方还要求启用 tools 时保留此前 reasoning_content，不能为了节费直接丢弃这些协议字段；本次两臂统一关闭 thinking，并与同一份去私有推理的真实历史比较。不能把这一设置的费用直接套用到 HPE 开启 thinking 的审查。[Thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)

## 3. 完成执行的证据

### 零模型工程资格

- 原始 HPE a4：43 个读请求恢复后仍可命中；44 个观察、候选及输入原件不变。MSFT 两底稿 32 来源、HPE 一底稿 35 来源，各 5 个 FTS 命中均能精确回读。0 provider / 0 外源查询。`D:/temp/fin205-source-rehydration-a5/result.json`；探测脚本 `D:/temp/fin205-source-rehydration-a2.py`。
- 两个上下文臂分别经真实 create_agent + 脚本模型演练，4/4 原计算回读、0 错误、0 provider。`D:/temp/fin205-context-native-prepare-a5/` 与 `fin205-context-hermes-prepare-a5/`。这是工具接线资格，不是模型理解能力证明。
- 193 passed / 2 私有材料依赖 skipped：审查、恢复、来源、上下文和父图相关回归，JUnit `D:/temp/fin205-source-rehydration-tests-a1.xml`。最终来源别名修复后相关集另跑 115 passed / 2 skipped；既有 bare/source citation 边界 18 passed。存在重叠，不能把三组相加成独立测试数。compileall 与 diff whitespace 检查通过。
- 本轮早期离线探针的参数、旧字段名、Fake 模型退出设置错误保留在先前 attempt 中；最终准备资格通过才执行付费。原生付费臂 recursion_limit=25 提前结束；Hermes 臂改为 100，二者均最多 3 次真实模型调用。此差异限制严格对照结论，不能隐去。

### HPE 已保存局部修订复核

`D:/temp/fin205-hpe-search-review-a1/`，沿用 a3 作者修订，只复核比较口径、营业利润变化桥接及减值归属。5 次真实调用，91,714 tokens，估算 ¥0.1184432，未知 0。第六次因输入 100,486 字符超过已记录的 100,000 上限，在 transport 前阻断；未自动加额度。

已读目标及原文、执行两个来源绑定计算。第一式将带括号的亏损按正 literal 使用后，分母采用减法，工具如实返回 1.204791785510553337136337706788363。模型之后另算 2190 + 437 = 2627，却仍称上一覆盖率已核实为约 80.4%。这是模型未核对表达式经济含义与计算结果；不是计算器算错，也不能认作信息缺口。末次 submit_case_review JSON 不完整，未形成正式 review。公开输出和工具记录已保留，financial_acceptance=false。

正确费用汇总在 `metrics-a2.json`。同目录 `metrics.json` 是对扁平审计目录误用旧递归汇总脚本产生的零值，不得引用；原件保留并在本记录纠正。

### 同一长历史的原生 / Hermes 回读比较

固定源调用 `ac0b41ec-4e75-40e2-856d-99e8497eaab5`，约 42.3 万字符、四条已观察计算，双方完整原始 native messages/tool artifacts 保留。只有请求投影不同。两臂均 deepseek-v4-flash、thinking disabled、每次输出最多 6000、最多 3 次模型 / 8 次工具、无 transport retry；TokenBudgetBasis 与准备文件 digest 在各 manifest 中。资格入口：`scripts/qualification/context_rehydration_compare.py`。

| 指标 | 原生 tool-edit | 既有 Hermes 摘要 + 相同 reader |
|---|---:|---:|
| 真实调用 / 未知 | 3 / 0 | 3 / 0 |
| 输入 tokens | 199,547 | 159,783 |
| 输出 tokens | 3,859 | 4,222 |
| 合计 tokens | 203,406 | 164,005 |
| cache hit tokens | 100,736 | 118,784 |
| 本次接续估算费用 | ¥0.1706188 | ¥0.0864367 |
| 成功回读原计算 | 4/4 | 4/4 |
| 原回答中可检查的操作数值 | 10/10 | 10/10 |
| 付费执行正式提交 | 未通过 | 未通过 |

约少 19.4% tokens，价格差还包含缓存命中差异，不能直接解释为算法节费。**未包含既有 Hermes 摘要生成的历史成本**，不可作为完整生命周期净收益。样本仅一段历史；不是所有长任务、全 HPE 或 Hermes 完整执行器的结论。

首次回答逐项保留四个 CALC ID、公式、精确结果、十个操作数值及相应来源/期间说明。三条旧绑定缺少显式 verification 字段，两臂均保留 not_recorded 区别；Hermes 另加了自行算术“复核 ✓”，没有对应本次工具执行，不能当独立验证。两臂对旧提交错误的“尚未读取”解释也过强：该历史错误只证明来源无法解析，不充分证明因未读取导致。质量验收仍失败。

别名修复后，对两臂**原封不动**的已保存回答再做零模型绑定检查，P01:S045 的误判消失，但诊断段落中的未绑定/缩写引用仍拒收。没有修改答案再冒充通过，没有为失败启动第四次调用。结果与原候选在 `D:/temp/fin205-context-comparison-a2/`；真实执行分别在 `fin205-context-native-execute-a1/`、`fin205-context-hermes-execute-a1/`。

本轮共 **11 次真实请求 / 459,125 已知 tokens / 估算 ¥0.3754987 / 新未知 0**。延续前次同口径 205 台账为 504 次尝试、15,714,951 已知 tokens、估算 ¥16.1966933、历史未知 2；历史未知不计零、不重发。价格为既有带时段 CNY 估算器场景，不是供应商账单。上下文组件另有历史成本，未重复计入本轮增量。

## 4. 已收敛的下一责任边界

第一步下一验收对象是“一个已经保存的修订及其必要依赖，能产生与工具结果一致的正式复核”，而不是再启动 HPE 整题。应优先针对真实无效 JSON 响应资格供应商 strict wire schema，并用保存的计算/作者解释作为语义负例，检查总额与增量、符号、分母与归属；结构约束不得代替这个判断。当前没有证据支持继续给同一 flash 复核单元加轮数能解决质量问题。

第二步已有“完整原件保留 + 原任务读身份 + 归档检索 + 请求投影”的可执行切片。下一关是无效引用的正式交付与多历史质量验收，并把历史摘要成本纳入复用收益；在这之前 Hermes 维持组件资格状态，不替换 LangGraph，不开启全局强制压缩。

交付分类：工程增量为上述已测源码与原生工具集成；研究证据为 11 次有上限真实调用、两组失败原件与零模型回放；文档为本记录及 Project OS 更新。没有新增通过的完整投研报告，没有本轮 UI 改版，没有生产多租户或 sandbox 增量。

## 5. 部署与仓库

工程提交 `b3766a99`，分支 `codex/fin013-conversation-and-retrieval`。确认 native busy=0 后，使用既有 `scripts.deployment.research_workbench build` 与 `up --no-build`，均传入 `--enable-research --fresh-only`，重建原 Compose API；Redis/Postgres volumes 与旧窗口保持不变。首个 up 命令漏传 fresh-only，因配置没有旧 bundle_path 在 Docker 调用前停止；补齐同构建一致的选项后成功，没有改写 settings 或挂载另一份数据库。

实际运行镜像 `sha256:8dba19aff83ee4f2d90dfe6cfd430b3a30e905ab39ae7df898420e10751308a1`。容器内检查确认 SQLite FTS5 可用、search tool 已加载、历史 turn 身份字段存在、case/report 未决字段必填。`18165/ok`、`18795/workspace`、`18795/api/v1/research-session-config` 均 HTTP 200。18795 宿主 BFF 本轮无代码变化，无需重启。构建与 up 日志在 `D:/temp/fin205-context-build-a1.log`、`fin205-context-up-a1.log`、`fin205-context-up-a2.log`。没有因部署触发模型或续跑任何产品任务。

本轮只推送开发分支，不合并 main，不修改产品版本。私有模型历史、来源全文、真实候选、API 凭据与本地原始审计不进入 Git；Git 只包含源码、回归和证据说明。

## 2026-09-10 全部规划盘点

Owner要求收拢此前完整规划和未完成项。已把原五项/前端与展示、四组长提示词及A–F工作包的当前成果、缺口、依赖统一更新到[同一实施基线](../../product/CONVERSATION_RETRIEVAL_AND_DELIVERY_20260909.zh-CN.md#2026-09-10-全部规划收拢与未完成总表)，没有新增执行阶段或重定义验收。当前第一/第二步只是研究可靠性和上下文两条工作线，不能覆盖或替代知识库、Qwen、sandbox、多租户及公开收口。

只读远端核对main a7053972、开发5069d02e（本次文档提交前）、两个history，无tags；最新实现仍未合main。本次产品/工程增量为0，新增研究/模型调用为0；交付是当前状态核对和文档归并。旧记录保留，不把文档整理计作修复完成，不重试历史部署阻塞，不删除分支。检查仅相对链接存在性、diff与文档变更范围，不为文档修改运行模型或全仓测试。
