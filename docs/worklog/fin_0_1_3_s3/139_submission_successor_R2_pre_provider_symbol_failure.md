# FIN 0.1.3 S3 submission successor R2 调用前 symbol failure

时间：2026-08-23

状态：`R2_authority_consumed / zero_provider / import_seam_repaired / fresh_successor_required`

## 发生了什么

R2 已跨过上一轮 SessionEvent 接缝，但在准备第一个 Demand workpaper strict submission 时，runner 使用了 `SPECIALIST_WORKPAPER_SUBMISSION_TOOL_NAME`，却没有在文件顶部导入该常量。Python 因 `NameError` 终止。

- 0 次新 Provider／DeepSeek 调用；
- 0 次新 S1/S2、retrieval、外源网络、Candidate promotion、retry 或 fallback；
- capture root 尚未创建，证明失败发生在 dispatch 前；
- R1 predecessor、六轮 S1/S2 和八份原始草稿均未改变；
- R2 authority、capture/private/public/run/attempt identity 全部视为 consumed，不得复用。

公开失败结果：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_submission_successor_live_result_v1_1.json`，result digest=`225029ab807ca1071ba38d0177f4d2d1aa87986354f348edc8671e7c16dc5127`。

## 最早责任层与修复

最早责任层是 S3 runner 的静态名称绑定，不是 DeepSeek、S1/S2、信源或研究内容。新增 submission 代码时，常量名称被误留在 `if __name__ == "__main__"` 的 `SystemExit` 之后，既不会执行，也不会成为 import；现有 compileall 只能查语法，定向测试也没有执行到该 live 分支。

修复：

- 在正式 import block 引入该常量；
- 删除 main guard 后的不可达残留名称；
- 增加模块导入回归，明确绑定实际 tool name；
- 用 `pyflakes` 检查 runner 和测试的未定义名，并清理同文件一个无行为用途的旧变量；
- 重新运行 targeted、full repository、active baseline 和 secret scan 后，才允许 fresh proof／authority。

验证结果：module/runner targeted `13 passed`；`pyflakes` pass；全仓 `1125 passed, 2 warnings`；active baseline pass；secret scan `7,753 files / 0 findings`。

此修复只关闭调用前名称接缝，不证明自然 workpaper、Lead、L1 或内容质量。
