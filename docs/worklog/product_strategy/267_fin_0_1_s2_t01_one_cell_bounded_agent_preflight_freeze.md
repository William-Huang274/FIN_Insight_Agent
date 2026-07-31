# FIN 0.1 S2-T01 单 Cell Bounded Real Agent 设计与预检冻结

日期：2026-07-20
状态：`accepted_after_independent_review / actual_execution_not_admitted`

## 问题与授权

用户要求先执行 S2-T01，并在完成后把 S1 以来已完成的程序切片文件及时 stage。当前任务只授权单 Cell 设计/预检冻结、确定性验证、项目 OS 更新和 path-exact staging，不授权 Profile 实现、model/provider/network/付费/商业数据、外部工具、Evidence promotion 执行、真实业务 Case mutation、Human Review、release 或 production。

## 决策

1. S2 只绑定 `NVDA:demand_authenticity_and_sustainability`；它与 Layer 4 `demand_signal` 是产品 Cell ID 与专业语义别名，不扩成两个 Cell。
2. 继续使用唯一 `Fin01ResearchRuntime` 和 existing RuntimeFacade/store，不复用 standalone 三-Cell DeepSeek runner，也不新建 Runtime/Registry/Writer/store/gate family。
3. T01 不签发 executable ProfileVersion。`bounded_agent_internal` 仅保留产品 Profile ID；exact Case/input、provider/model、calls/tokens/cost、egress、secret-safe preflight 和 Agent/Skill/Tool/Graph/Context/eval versions 全部作为执行 blocker。
4. 每份 exact execution admission 上限为 1 WorkUnit、1 Attempt、1 ResearchRun、0 retry。一次有新信息的 repair 必须获得新的 admission 并创建新 Run。
5. 首跑默认 local/repo-available official first，source network 关闭；Candidate/Graph edge 不是 Evidence，未来 promotion 仅限 exact run-scoped evaluation EvidenceVersion，不修改 live business Case head。
6. Writer 只消费 adjudicated material，source/tool calls=0；四层 verifier 不改写研究真相；Agent-vs-fallback 必须 exact-input parity、不同 Run、blind/semi-blind，并由 owner 指向 exact artifacts 说明实质增益。

## 已完成

- 新增机器合同 `configs/releases/fin_ia_0_1_s2_t01_one_cell_bounded_agent_preflight_v1_0.json`；
- 新增技术冻结 `docs/architecture/repository/FIN_0_1_S2_T01_ONE_CELL_BOUNDED_REAL_AGENT_PREFLIGHT_20260720.zh-CN.md`；
- 新增合同测试 `tests/contract/test_fin_0_1_s2_t01_one_cell_bounded_agent_preflight.py`；
- 将 program backlog 的 active slice 移到 S2，仅把 S2-T01 标为 accepted；S2-T02 pending，S2-T03 actual execution blocked，S3 保持 blocked；
- 更新 current context、handoff、capability/root-cause ledgers 和本 worklog/index。

## 独立复核与修复

首轮独立合同复核发现两项：

1. `1 WorkUnit / 1 Attempt / 1 Run` 未写明是“每份 exact execution admission”的上限，与允许一次 repair Run 的表达有歧义；
2. ReleaseContract v1.3 仍只准入 S1 fixture，但初稿没有把它和 API admitted types 明列为实际执行 blocker。

修复后合同明确 repair 需要新的 execution admission/Run，并要求真实执行前 supersede ReleaseContract v1.3、准入新 WorkUnit type；只更新 backlog 不能产生调用权限。未使用 fallback 掩盖问题。

## 验证与实际计数

- stable program source digests：`9/9`；
- 新 T01 合同 + S1-T06 closeout + historical three-cell freeze 隔离回归：`12 passed in 1.25s`；
- model/provider/network/external tool/Evidence promotion/真实业务 Case mutation/Human Review/release admission：全部 `0`；
- 未运行 provider preflight、模型推理、source network、browser、paid/full-chain 或真实 Case。

## 效果与剩余边界

产品能力增量是把 S2 的真实运行条件变成机器可检查的 fail-closed 合同；研究质量增量仍为 0，因为没有真实 Agent 输出。下一项是 S2-T02 zero-call Profile/runtime adapter 与 paired baseline implementation，需用户继续指令。S2-T03 首跑必须另获 exact Case/model/provider/network/budget/secret-safe admission；S3、RG1/RG3/RG4、release 和 production 均未解锁。

## Git 安全说明

按用户要求，Git postflight 用显式 63 路径清单暂存 FIN 0.1 program groundwork、S1-T01 至 T06 和 S2-T01 的已完成代码、合同、测试、技术文档与工作日志；清单与 staging 前全部 63 个 dirty paths 做 set equality 后才执行 `git add -- <exact paths>`。高置信 secret scan 为 0，最大文件约 494 KB，未纳入 runtime/generated/binary/private artifacts。首次 cached diff check 暴露 21 个新增 Markdown/test 文件的 trailing whitespace 或多余 EOF 空行；只对报错文件做机械规范化，并因 7 个 stable sources 的 bytes 变化同步刷新 backlog SHA-256，`contract_semantics_changed=false`。最终暂存区 63 个文件，unstaged=0、untracked=0；未使用 `git add .`，未提交、未推送、未清理用户文件。
