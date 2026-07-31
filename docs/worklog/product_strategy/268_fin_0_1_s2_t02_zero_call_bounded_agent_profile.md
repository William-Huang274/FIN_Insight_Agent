# FIN 0.1 S2-T02 Zero-call Bounded Agent Profile

日期：2026-07-20
状态：`accepted_after_independent_review`

## 授权与目标

用户授权先完成 S2-T02，只有通过才进入 T03。T02 必须保持 model/provider/network/external tool/付费/商业数据/真实业务 Case mutation 为 0，并把 `bounded_agent_internal` 接到已有 `Fin01ResearchRuntime`，不能新建并行 runner 或用 historical three-cell 脚本替代。

## 实现结果

- 新增 `BoundedAgentAdmission`、exact single-cell input pack、executor port 和九类 typed artifact contract；
- API schema 可以识别 `bounded_agent_internal_entry`，但默认应用的 `ExecutionService` 仍返回 403；只有显式注入 admission + executor 的同一 Runtime 才动态准入；
- bounded WorkUnit 复用已有 scheduler/facade，形成唯一 WorkUnit → Attempt → ResearchRun → Run-scoped events → immutable ArtifactVersion 链路；
- paired deterministic baseline 与 Agent profile 使用同一 Case/version/as-of/source preview/analysis/input digest，但必须是不同 ResearchRun；
- zero-call contract probe 不作研究质量声明；forced failure 只落一个 failed Run、0 artifact、0 retry、无 deterministic fallback；
- existing deterministic 与 fixture-shadow profiles/API 行为保持兼容。

## 独立复核

首轮成功测试因 bounded trace event 未加入 facade allowlist 而 terminal failed。修复仅扩展同一 Run-scoped trace owner 的 bounded event allowlist，没有绕开 Runtime。随后 T02 三项测试全部通过，并与 S1-T02 至 T06、S2-T01 联合复核为 `22 passed in 40.23s`。

实际计数：model=0、provider=0、network=0、external tool=0、source network=0、真实业务 Case mutation=0、release admission=0。

## 效果与边界

T02 关闭了“bounded profile 没有产品主线执行入口”和“paired baseline 不同输入”的工程缺口，但没有产生真实 Agent 信息增益。T03 仍必须绑定 exact evaluation Case/input/provider/model/call/cost/secret-safe admission；默认应用继续 fail closed。
