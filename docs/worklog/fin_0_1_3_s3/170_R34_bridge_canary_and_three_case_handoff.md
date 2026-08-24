# S3 工作记录 170：R34 产品桥 canary 与三案例交接

日期：2026-08-25

状态：`R1_failure_preserved / R2_zero_call_canary_pass / natural_and_product_acceptance_open`

## 1. R1 不可变失败

R1 在两轮 current runtime 已运行后，于 mutation assertion 终止，未生成预期 public/private
result。独立 failure assessment 保留 attempt、implementation commit、failure stage 和未创建
输出事实。最早责任层是 S3 Harness 的过期测试预期，而不是模型业务判断、S1 资料或 S2 bridge。

旧预期要求未覆盖完整时的 proposed `stop_sufficient` 抛异常；current controller 的正式语义是
保留 proposal 作为模型判断记录，同时编译 effective `stop_no_progress`。修复后正反两面都被
断言：proposal 不得被悄悄重写，effective decision 也不得提前终止为 sufficient。

## 2. R2 canary 实际通过范围

R2 证明 current R34 的两轮 deterministic single-unit loop、反馈改变计划、graph hypothesis-only、
checkpoint/resume、workpaper contract 和 S2 bridge projection 一起工作。13 个顶层 checks 与
6 个 mutation checks 全部通过；公开 digest `9cbdc308...b9fa5`。

它使用 fixture request/reflection，调用数为 `0 model / 0 provider / 0 network / 0 paid`。因此只
证明 Harness 与 current data/control plane，不证明自然 Agent 的规划、反思或写作质量。

## 3. 三案例交接

fresh R34 三案例回执从同一 current registry 读取 DELL、MU、NVDA；三个 actionable-state
evaluation 全通过，且没有 candidate promotion 或 public-gap authorization。DELL 五个动态 cell
能看见 typed control context；MU/NVDA 只做 current Pack/readiness/actionability 泛化验证，没有
虚构新补源或重物化相同 Pack。

R17 的 fresh independent content review 继续有效，qualified human、完整 S3 acceptance、产品
验收、publication 和 release 仍为 false。下一步只有在本轮 immutable commit 的全新只读审计
无 material finding 后，才可讨论后续自然单元；本记录本身不授权 live 或 R18。
