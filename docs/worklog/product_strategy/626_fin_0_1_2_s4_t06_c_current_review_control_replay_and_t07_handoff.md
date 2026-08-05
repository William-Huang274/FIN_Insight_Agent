# FIN 0.1.2 S4-T06-C current review-control、replay 与 T07 handoff

日期：2026-08-05
状态：`T06 pass closed / T07 entry ready / qualified review not executed`

## 问题与决策

T06-A/B 已让 DELL、MU、NVDA 的十类 current 研究资产进入 Workbench，但产品仍只能查看，不能把“退回补证”绑定到当前 exact version，也不能从持久化动作重建历史或判断是否可交给 T07 reviewer。

本轮没有复用 fixture review 来冒充 current Human Review。决定将业务真值与 review-control 分开：十个 current surfaces 继续只读；返修请求进入独立 append-only event log。T06 只证明机制与 handoff，不执行 qualified reviewer 接受/退回，不关闭真实 repair，也不执行 NVDA R3。

## 完成内容

- 新增内容寻址的 T06-C review-control 合同和 runtime resource registry。
- 新增 SQLite append-only event store/service：按 case 形成 hash chain，支持幂等、重启 replay 和 exact binding 复核。
- `return_for_repair` 强制绑定 manifest、case projection、target view digest 和 `surface:<surface>`；六类 typed reason 由本地确定 Evidence/Numeric/Lead/Writer/Verifier owner 与 resolution。
- 新增 GET review-control 与 POST return-request API；业务 projection API 仍为 GET-only。
- `/current` 新增返修控制、历史回放、open request、replay digest 和 T07 readiness 面板；明确显示 qualified review 尚未执行且归 T07。
- 空队列输出 `ready_for_qualified_review`；存在 open request 输出 `repair_required_before_qualified_review`。
- T06-A/B 历史测试改为 predecessor receipt + successor 语义，不再要求后继代码永远匹配旧 SHA。

## 发现并修复的治理问题

扩大回归前，T06-B 历史测试虽然已停止逐项比较旧 SHA，却仍调用旧 materializer。测试因此把 T06-B 历史记录按当前 T06-C 源码重新生成，破坏 immutable evidence。

已移除测试中的 materializer 调用，从 Git 精确恢复 T06-B record，并确认该文件 byte-equivalent、Git diff 为 0。T06-C 使用新的 successor record 引用 T06-B digest。RC-P36-128 原有四条债仍保持 open：三条 consumed MU fresh identity 和一条 T05 mutable-source SHA；没有借 T06-C 重写历史 T05 结果。

## 验证证据

- T06-A/B/C + 历史 Evidence/Workpaper/Deliverable focused：`36 passed`
- T06-C 专项：`7 passed`
- Chromium desktop/mobile：`8 passed`
  - 三案例、十视图、诚实 Graph empty、报告/quality 边界；
  - 返修 form 的 browser POST 使用拦截响应，仅验证 UI 状态变化，不写正式默认库。
- TypeScript：pass
- Vite production build：pass；保留 T06-B 已知的单 chunk >500KB 非阻塞 warning
- 扩大 T05→T06/Workbench：`158 passed / 4 failed`
  - 失败集合与 RC-P36-128 完全一致；
  - 新 T06-C regression=`0`。
- 默认 current DB：DELL/MU/NVDA 均 `event_count=0 / ready_for_qualified_review`，未制造正式返修。
- 实现记录：`configs/releases/fin_ia_0_1_2_s4_t06_c_current_review_control_and_t07_handoff_zero_call_implementation_v1_0.json`
- implementation digest：`c4990c2e188bc03fd071cf3939cbf3e6e68479bb30edf75140d73668298bd41a`

本轮模型、Provider、网络金融来源调用均为 0；accepted R2 business truth 写入为 0。仅测试临时 SQLite 写入和既有本地 Workbench control schema 初始化。

## 产品与工程结论

产品增量：用户已能在 current 产品面查看 exact 研究资产，并提交可审计、可回放、可阻断 reviewer handoff 的 typed 返修请求。

工程增量：current business projection 与 review-control 写入隔离；hash chain、exact digest、权限、actor、reason/surface、跨案和 idempotency 都有确定性回归。

尚未完成：authenticated reviewer identity、qualified Human Review、真实 repair completion/new exact version、NVDA R3、review burden、bounded explanation、T08、S5、release。当前 `current_internal_operator` 与权限 header 只是本地内部声明，不能晋升为 T07 reviewer authority。

## 下一步与建议

下一项限定为 `FIN-0.1.2-S4-T07-EXACT-QUALIFIED-HUMAN-REVIEW-NVDA-R3-AND-BOUNDED-EXPLANATION-ENTRY-DECISION`。先审计 reviewer 身份、权限、exact digest、accept/return 语义、repair closeout 与 NVDA R3 的最小证明，不能直接把 `current_internal_operator` 当 qualified reviewer，也不能以 T06 的空队列 handoff 冒充接受。

工程建议：RC-P36-128 的剩余四条测试债应继续作为有界 test-governance package 处理，但它们不应回塞 T07，除非出现 current product invariant 失败。
