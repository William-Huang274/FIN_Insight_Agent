# FIN 0.1 S3-T09：live Artifact 与 paired baseline 只读决策

日期：2026-07-22

## 授权与边界

用户以“授权”只允许 `S3-T09-REPLACEMENT-LIVE-ARTIFACT-READ-ONLY-VALIDATION-AND-PAIRED-BASELINE-DECISION`。本轮未调用模型、Provider、来源网络或外部工具，未物化 deterministic baseline，未修改 canonical runtime、Case head 或 Human Review，也未进入 T10。

## Artifact 复核

只读 validator 对 exact WorkUnit、Attempt、ResearchRun 与九类 Artifact 重新从 canonical SQLite/Object Store 加载，并在前后比较数据库和对象树摘要。三态均为 succeeded，九类 Artifact、跨 Artifact manifest、六节点 receipt、input/input-head/Run/Attempt lineage 全部一致；Evidence fact=0、live promotion=false，Numeric 只有一条公司总量事实且明确禁止 segment/product attribution，Writer source/tool=0。

这部分结论为工程完整性 pass；它不等于 owner-grade 研究质量通过。

## 独立质量意见

machine verifier 报告四层 pass 且 issue=0，但独立复核确认四项漏检：

1. Value Specialist 先在 Judgment 层作出确定性的 Data Center revenue-capture 表述，Writer 又无候选/假设限定地传播；当前没有 promoted Evidence 或 segment/product Numeric fact 授权该表述。
2. Lead 用 “all cells are in non-fact states” 描述三 Cell，但 Value Cell 明确有一条 company-total Numeric fact；应区分“终态未闭合”与“没有事实”。
3. Writer 把 Graph hypothesis 译为“图表假设”，降低领域精度。
4. WWC 仍是自由文本，未形成 source/metric/threshold/time 的可领取研究任务合同。

因此 owner-grade disposition=`repair_before_final_acceptance`，新增 RC-P36-037。当前 Agent 证明了边界纪律和结构化产物能力，但不能据此声称 product material gain 或 junior analyst dogfood acceptance。

## Paired baseline 搜索

只读扫描 `.codex_runtime` 下 11 个 canonical 数据库，没有查询错误，摘要前后不变。相同 Case + input-head 只有两条 Agent profile Run：旧 r1 failed、output-v2 replacement succeeded；`fin01.execution_profile.p36_local_deterministic:v1` 的 terminal candidate 为 0。T08 deterministic proof 的 Case、input-head 和 DecisionSurface 均不同，禁止复用。

所以 RC-P36-036 被确认：当前没有可用于 material-gain comparison 的 distinct same-input terminal deterministic Run。按照上一任务冻结的边界，本轮停在决策，未自动物化 baseline。

## 验证

- exact live 只读 validator：pass；目标 canonical database/object tree 与全部 11 个搜索数据库摘要前后不变。
- current-state contracts：`39 passed`。
- 完整 T09 admission/repair/result/decision contracts：`48 passed`。
- Python compile 与 JSON/JSONL parse：pass。
- Project OS `repository_and_git_hygiene` scoped preflight：pass，open blocker=0（仅表示该收口 scope 可执行，不表示 broad full-chain blocker 已关闭）。
- 本轮新增差异 boundary-aware credential scan：0 命中；Git diff check：无错误。

## 下一步

唯一下一项为 `S3-T09-PAIRED-DETERMINISTIC-BASELINE-MATERIALIZATION-DECISION`，需单独授权。该项只允许零模型地审查 baseline identity、同输入合同、独立 Artifact 与防替代边界；不得在同一步物化 baseline，也不得执行 Agent rerun、Human Review 或 T10。

复演命令：

```powershell
python scripts/releases/validate_fin_ia_0_1_s3_t09_replacement_artifacts_and_baseline.py --runtime-root .codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1 --search-root .codex_runtime
```
