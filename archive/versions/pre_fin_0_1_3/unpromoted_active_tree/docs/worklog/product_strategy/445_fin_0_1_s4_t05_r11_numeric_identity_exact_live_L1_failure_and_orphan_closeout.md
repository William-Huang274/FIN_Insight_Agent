# 445｜FIN 0.1 S4-T05 R11 numeric/identity exact-live 新 L1 与 orphan 收口

日期：2026-07-28

## 结果

按全链路审计冻结的顺序，最终 T05 零调用收敛包已完成：

- DELL/MU/NVDA full-fake 均为 `6 nodes / 12 callbacks / 9 Artifacts`；
- 数值投影、alias atom、本地确定性渲染、独立 L1 重算与案例本地身份 fixture 通过；
- fresh proof 双重一致；
- R11 admission 已 exact-once 签发并消费。

R11 没有通过。首个 Specialist Provider 返回在本地 numeric narrative gate 触发：

`s4_case_numeric_authority_provider_narrative_invalid`

模型在只允许 numeric alias 与定性判断原子的字段中仍生成了被禁止的数字型自由叙事。这是新的 L1 Provider 输出合同不遵循；本地 validator 在下游节点和 Artifact commit 前正确 fail-closed。

## 次级项目内缺陷

Executor 将本次 failure observation 记录为新的 `case_numeric_authority` telemetry family，但 canonical facade safe allowlist 未同步接受该 family，导致原始 `FAIL_RESEARCH_RUN` 被：

`research_run_failure_observation_not_secret_safe`

拒绝。Runner 自行 exit=1 后，WorkUnit / Attempt / ResearchRun 一度遗留为 `running / running / running`，登记为 RC-P36-069。

已使用精确 R11 identity、supervisor exit receipt、0 Artifact 与无 terminal event 前置条件执行 typed orphan closeout。收口结果：

- canonical terminal truth=`failed / failed / failed`；
- Artifact=0；
- closeout model/provider/network calls=`0 / 0 / 0`；
- retry/fallback/replay/relaunch/rerun=`0 / 0 / 0 / 0 / 0`；
- 未重建 usage receipt、Provider capture 或 raw output。

## 冻结规则执行

- R11 是唯一获准的后续 paid execution；
- 新 L1 已触发强制停止；
- 不启动 R12；
- 不做 paired assessment 或 owner acceptance；
- 不进入 T06、T07、T08–T10 或 S5；
- DELL R2=false，T05 未关闭。

RC-P36-067 的 zero-call fixture 仍成立，但本地数值渲染和独立 L1 重算未获 R11 live 证明；RC-P36-068 因链路在 Writer 前停止而 live-unobserved，不能视为失败或通过。

## 证据

- `configs/releases/fin_ia_0_1_s4_t05_dell_r11_numeric_identity_exact_live_execution_failure_result_v1_0.json`
- `.codex_runtime/fin01-s4-t05-dell-r11-numeric-identity-supervision-r1/exit_receipt.json`
- `.codex_runtime/fin01-s4-t05-dell-r11-numeric-identity-supervision-r1/typed_orphan_closeout_receipt.json`
- `scripts/releases/close_fin_ia_0_1_s4_t05_dell_r11_numeric_identity_orphan.py`

## 下一步

`S4-T05-DELL-R11-FIRST-SPECIALIST-NUMERIC-NARRATIVE-L1-AND-FAILURE-OBSERVATION-ALLOWLIST-ORPHAN-PROJECT-LEVEL-DISPOSITION-DECISION`

该项只允许零调用方案选择：更严格的服务端结构化输出、更小的 atom-only 模型表面、完全本地确定性组装、Provider/模型范围替换、共享 telemetry 注册/allowlist 硬化，或声明 T05 项目级阻断。任何实现都不能隐含授权 R12。
