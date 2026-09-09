# 205 HPE 原候选局部修复 TokenBudgetBasis

2026-09-09，FIN 0.1.3 / S3，延续 Owner 已批准的复杂题根因修复。不是新产品版本、不是 HPE a3 全链路运行。

- 节点目的：让原 DeepSeek Flash 依据原候选与实际观察修复 SubmitWorkpaperAction。原 Q4 第24轮有两条 numeric_fact / not_applicable 冲突，不能由后台自动改标。
- 输入规模：原 progress 817,620 字符、35观察。按原候选引用与计算操作数来源选择完整原始条目，去除完全相同的观察副本；不摘要原文，不携带私有推理。原候选9,899字符、原任务2,298字符。调用前 prepare-only 写入实际输入并测量；实际字符数记入 request.json，不能冒充 tokens。
- 必要输出：一份完整原生 SubmitWorkpaperAction，保持原6条 claim 标识、计算与限制，按证据纠正分类/引用/精确引文。不能靠删除困难判断取得通过。
- Schema负担：只提供既有提交工具，无工具执行。host context_digest 使用明确标注的诊断绑定，不伪造原 checkpoint 绑定。
- 质量风险：格式通过不保证金融语义正确；使用现有 _submission_errors 检查全部原观察中的来源、权威等级、精确引文、计算回执及冲突。归档语义投影缺完整 artifact_digest，因此不宣称完整 notebook/receipt 验证或正式入库。
- 对照证据：HPE a2 Q4原始最后提交失败；全题 a2 已51调用、2,140,450 tokens。此次只允许1次诊断调用，无自动重试、无整题重跑，不计作题目成功。
- reasoning profile：deepseek-v4-flash，thinking enabled / effort low。max_output_tokens 16,000，为完整候选/schema和推理预留空间，不作为必用额度。
- 停止：SDK timeout480秒，transport max_retries=0；截断、传输/校验失败均保留输出与用量，不解析截断结果为成功，不隐式追加调用。后续必须基于具体新证据决策。
- 成熟栈：沿用已有 compare_review_model_once 资格脚本、ChatDeepSeek SDK、原生 Pydantic schema 和 LangSmith。没有增加执行引擎或研究状态机。

产品验收仍要求新运行的端到端报告、失败可见性、引用与财务语义检查。局部诊断不能替代这些检查。

## a1结果与a2依据

a1真实1调用，12,151输入＋11,358输出＝23,509 tokens，87.447秒。Schema与已有引用检查通过，但模型把6条claim改成5条，退回完成日期/无形资产寿命等必要内容，因此`next_action_invalid`，原件保留在D:/temp/fin205-hpe-submission-repair-a1。不能登记为整题或局部修复通过。

新增只读证据：原35观察实际包含67个不同PASSAGE标识。HPE原候选多条不同断言只引用同一购买价表中的短语；短语匹配不等于支持整条断言。已读PDF物理134页有完成日期，135页有融资方式/Networking归属/替代股权奖励，136页有寿命/摊销和测量期调整。它们已在原观察中，不是外部信息缺口。

a2只允许新增1次诊断：把上述原观察的4个精确PASSAGE标识作为显式补充输入，入口验证均属于原attempt；保留原全文、引用标识和所有6个claim_id，纠正无增发即无稀释的过强推断。沿用同模型/输出上限/timeout/无自动重试。它是有新证据的输入修正，不覆盖a1、不扩到整题重跑；a2后无论结果均先检查再作后续决定。

## a2结果与下一项工程

a2输入48,697字符（逐原始条目去重，未摘要）；真实调用18,373输入＋16,000输出＝34,373 tokens，117.199秒。输出达到上限，finish_reason=length，0完整工具调用，原始响应保留，未将截断内容提升为成功。两次合计57,882 tokens、按既有2026-09-07价格场景估算¥0.2382345，不是账单。

停止追加付费调用；先完成局部修订工程。采用环境已有jsonpatch 1.33（补直接依赖、uv lock），用标准RFC 6901指针和RFC 6902 test/replace，FIN只限定可改的底稿字段、准确基线及claim身份，修改后运行原Schema/来源/计算校验。ReviseWorkpaperAction只在已有被拒底稿时允许，不能修改context绑定或接受报告、不能删掉困难claim来过关。初次提交与广泛重写仍使用原工具。

此新增工具的下一次付费资格仍需按具体待修字段/原文规模测量输出Schema负担；本次只做零模型SDK/ToolNode确定性资格，不凭“输出更短”推断财务准确率或整题节费。
