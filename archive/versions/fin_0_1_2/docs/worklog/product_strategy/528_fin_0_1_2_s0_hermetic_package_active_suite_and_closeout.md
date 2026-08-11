# 528 — FIN 0.1.2 S0 hermetic package、active suite 与 closeout

日期：2026-07-31

## 问题

S0-T01 只定义了五类 proof semantics 和 active-suite manifest；实际 runner 尚未消费 manifest。RC-P36-085 仍缺 exact dependency inventory、typed per-test terminal result、完整 stdout/stderr 与双 disposable parity；RC-P36-086 仍有历史事件测试绑定 mutable current backlog 的残留。

## 决策

- package 使用 manifest-selected dependency closure，不把全部历史仓库当作当前 suite 依赖；
- 仓库文件、显式外部证据与测试输出统一进入 SHA-256 对象库；
- 两个独立 disposable root/进程必须产生相同语义投影；
- historical audit failure 可见但不隐式阻断 current release，current/release failure 必须阻断；
- immutable event 测试不再读取 current active slice/current next；这些断言集中到 current-projection 测试；
- 零调用 package 不生成业务 Artifact，也不授权 S4 产品证明。

## 实现

- 新增 `src/sec_agent/hermetic_test_capture.py`：记录每个 pytest node 的 setup/call/teardown outcome、完整 stdout/stderr 和 detail；
- 新增 `src/sec_agent/hermetic_test_runner.py`：dependency closure、内容寻址对象库、显式 Python environment inventory、credential env removal、双 disposable execution、current/historical gate 投影与 repository readback；
- 新增 `scripts/engineering/run_fin_0_1_2_s0_active_suite.py`；
- active manifest 已真正迁移到 runner，并绑定 0.1.1 recovery package 与 S0 preflight package；
- T10、S5、0.1.1 freeze 三个 immutable event 文件中的 mutable backlog 断言已迁移到 S0 current-projection 测试；历史产品真值、status、count 和 source binding 未放宽。

## 验证

- focused runner/governance/result：`10 passed`；
- final host manifest-selected suite：`24 passed`；
- preflight package：888 repository files、2 external dependencies、双 root 各 25 passed、parity pass；
- final package：890 repository files、6 external dependencies、双 root 各 24 passed、parity digest=`27dc2d7496218ef8b2a2d3d049a64852e3b73d5b51901cdf0f70bda480ca12e8`；
- final verification SHA-256=`4ba00673331abf7b0eabf51aa125765817315b9811b818215a39e3c5e0622b0c`；
- final package path=`D:/FIN_Insight_Agent_recovery/packages/fin_0_1_2_s0_hermetic_active_suite_final_20260731T2135+0800_head_cee47c2a`；
- credential/model/Provider/business network/admission/Run/business Artifact/release candidate=`0`。

两个早期 over-broad 全仓 package 在工具命令超时后继续终态化；测试本身 25 passed、parity pass，但因为运行期间工作树继续被本轮修复修改，`repository_unchanged_during_run=false`，因此两个 package 都正确标记为 `failed`，未作为通过证据。另一次 1 秒包装器终止未形成 package。未删除这些记录。

## 结果与边界

RC-P36-085/086 在 FIN 0.1.2 S0 范围关闭，S0=`closed_G4_G5_pass`。生产十消费者的实际迁移仍属于 S1 deterministic vertical；DELL/MU R2、post-transfer NVDA 和 qualified-senior R3 仍属于 S4，FIN 0.1 release qualification 仍为 false。

下一项：`FIN-0.1.2-S1-REALISTIC-THREE-CASE-DETERMINISTIC-VERTICAL-STAGE-PLAN`。
