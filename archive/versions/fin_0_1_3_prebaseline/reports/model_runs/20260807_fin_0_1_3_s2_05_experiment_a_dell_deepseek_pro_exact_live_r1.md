# FIN 0.1.3 S2-05 Experiment A DELL DeepSeek Pro exact-live R1

- Run ID：`fin013_s2_05_exp_a_dell_9af8699f8f545103d2be`
- 时间：`2026-08-07 00:49:46 +08:00`
- 类型：`same-evidence / raw model-only / exact-live inference`
- 状态：`terminal_failed_no_retry`
- Provider / model：`deepseek / deepseek-v4-pro`
- Git：`a3f2edf8f62a74f87dc45a56edefcdb19f5c1989`，clean/synced
- 输入：S2-04 冻结 DELL blind input；无工具、无 MCP、无 hidden Gold
- 入口：`scripts/releases/run_fin_ia_0_1_3_s2_05_experiment_a.py`
- Policy：`configs/runtime/fin_ia_0_1_3_s2_05_experiment_a_runtime_policy_v1_0.json`

## 结果

唯一 admission 被 shared ledger exact-once 消费。DeepSeek Lead 调用正常返回 JSON，`finish_reason=stop`、transport attempt=`1`；原始响应先 capture，再进入本地校验。Lead 形成 6 个公司专属 mandatory-family 研究单元，但在 question/why-material/stop-condition 中出现本地认定的 unbound numeric surface，运行在 `lead_planning` 阶段以 `experiment_a_unbound_numeric_surface` 终止。

- 调用 / capture：`1 / 1`
- tokens：`2604 input / 1162 output / 3766 total`
- 估算成本：`USD 0.0035378`（policy ceiling rates，非账单）
- retry / fallback / second run：`0 / 0 / 0`
- Specialist / synthesis / Writer / Verifier：均未执行
- business Artifact / correction / corrected candidate / evaluator access：`0 / 0 / 0 / 0`
- terminal digest：`8f9729b0…9c0c`
- capture secret pattern scan：pass

## 根因判断

这是混合根因，不应简化为“模型不行”：

1. DeepSeek 确实引入冻结输入中没有的假设阈值，例如 backlog 取消 `>20%`、延后 `12` 个月、`top 3` 客户风险、内存成本 `+10%` 和利润率 `<3%`，违反当前“所有数字必须来自输入”的明示合同。
2. 项目 classifier 也有假阳性：自然写法 `$51.3B/$24.4B` 被当前正则截成 `51/24`；输入中的数值和 `percent` unit 分字段保存，输出自然写成 `36.7%/55.5%` 时无法与 allowlist 对齐。
3. 当前合同把“证据事实数字”和“研究计划的情景/停止阈值”使用同一个硬门禁，无法表达研究 Lead 合理提出待验证阈值的需求。

因此登记 `RC-P36-141`。本次失败不支持对 DeepSeek 的整体研究能力下结论，因为后续 Specialist、综合、Writer、Verifier 和 hidden rubric 均未到达。

## 治理结论

该 run 保持 immutable，不补写、不 replay、不晋升。DELL 第二次运行、MU/NVDA、supervisor correction 均未授权。下一项只允许零调用处置：分开事实数字 authority 与显式 hypothetical planning threshold，修复 suffix/unit classifier，并用本次 capture 和 mutation 证明边界后再决定是否值得 replacement live。
