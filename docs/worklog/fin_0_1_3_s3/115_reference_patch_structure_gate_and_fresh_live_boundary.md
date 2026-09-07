# 115 — Protected report reference-patch 结构门与 fresh-live 边界

## 结论

v1.1 的失败已从笼统的 `model_text_unprotected_surface` 收敛为两类：5 个非阻断叙事密度 finding，以及 5 个 hard reference-binding finding。第三次全报告 remap 不再被授权。当前实现只允许对第二份完整 payload 做五路径引用补丁，正文和来源 Agent 不可修改。

## 实际回放

- base run：`FIN_0_1_3_S3_DELL_MULTI_AGENT_PROTECTED_REPORT_REMAP_REPLACEMENT_20260821`；
- base attempt：2；`finish_reason=tool_calls`；
- base payload digest：`e9e07169...e6f2b`；
- finding receipt digest：`36e50ec1...b7f1`；
- patch receipt digest：`400eb4c7...e485`；
- hard paths：executive、Counter section、Demand gap、Value gap、Value WWC，共 5 条；
- quality paths：executive 和四个 section 的建议密度越界，共 5 条；全部低于 2,400 字符安全容量。

## 实现

1. `audit_protected_report_draft` 一次编译完整 hard／quality finding，不再 fail-fast 丢失后续问题；
2. 推荐密度与安全容量分层，前者进入内容质量，后者继续 fail closed；
3. reference-patch Tool 只暴露五个目标路径的可选 refs；
4. patch 绑定 immutable base digest，禁止 `model_text`、来源 Agent 和未列出路径变化；
5. 同一通用 remap Runner 增加 reference-patch 模式，没有新增 attempt-only runner；
6. Project OS 新 v1.2 决策绑定 v1.1 authority／public／private failure、零调用 proof、专用 profile 和实现 SHA。

## TokenBudgetBasis

本节点不做研究或重写报告，只提交五个嵌套引用 patch：base payload 19,442 canonical 字符，模型可见消息 15,475 字符，其中 user message 15,261；Tool Schema 4,995 字符。金融引用错误风险为 high，最多允许一次合同反馈，因此使用 DeepSeek V4 Pro GA Chat、`thinking=disabled`、`max_tokens=4,000`、最多 2 个 contract attempts、transport retry 0。成本和延迟不是删减必需 patch 的依据。

## 零调用证明

真实 attempt 2 上的机械有效 patch 能通过完整 Validator，并保持 model text、来源 Agent 和未列出路径不变。正文注入、错误路径、未知 ref、跨角色 ref 和漏 gap 均被拒绝。该机械 patch 明确不是产品引用选择，也没有生成正式报告。

## 完整工程门

- 定向合同、Runtime 与 Project OS：`81 passed`；
- 全仓：`958 passed`，仅两条既有 SWIG deprecation warning；
- Python `compileall`：通过；
- Workbench TypeScript 与 Vite production build：通过；
- active baseline：`189 Python / 8 frontend / 5 detectors / 27 Runtime / 0 forbidden`；
- archive redirect index：`6,059` 条，check 通过；
- 机器可读资产：`811` 份 configs JSON、`8` 份 Project OS JSONL／`919` 行全部可解析；
- repository secret scan：`7,547` files／`0` findings；
- `git diff --check`：通过。

以上结果证明 reference-patch 复用了当前权威合同与通用 Runner，且没有破坏既有 S1／S2、Session／Feedback、五单元和 Workbench 路径；仍不证明自然模型会选择正确引用或最终报告内容合格。

## 后续边界

全仓工程门已通过。下一步只允许形成 clean／synced commit，再签发 fresh preflight 和新 authority，执行唯一一次 reference-patch exact-live。成功只产生待验收候选报告；必须继续做独立 L1、八维绝对内容质量、paired 保真与 qualified-human。S1、S3、泛化、Workbench publication 和 release 均保持 false。
