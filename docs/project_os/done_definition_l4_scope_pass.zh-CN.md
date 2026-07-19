# L4 Scope Pass Definition

`L4_scope_pass` 的含义不是“整个系统已经生产可用”，而是该 slice 在自己的职责范围内达到了企业级可依赖标准。

## 不算通过

- 只实现最小 schema / contract。
- 只跑 1-2 个 smoke。
- 只生成有输出的 memo。
- 只靠 fallback/gate 避免坏输出。
- 只证明 mock artifact 通过，但真实运行路径未闭合。

## 算通过需要满足

1. 合同稳定：字段、状态、输入输出、错误类型可机器读取。
2. 可回放：关键 artifact、run id、source ref、code version 或 dirty-state 能追踪。
3. 可追责：能定位每个失败属于数据、parser、retrieval、agent planning、model provider、writer、renderer、eval、frontend 或外部边界。
4. root-cause-first：owned defect 已修复，gate 只作为回归保护。
5. deterministic tests：可用非 LLM 测试验证的部分已经验证。
6. 真实路径证明：该 slice 如果承诺 runtime / UI / data / LLM 路径，就必须跑对应路径，不用 mock 冒充。
7. 边界清楚：未完成项写入 source doc / ledger，不被 closeout 文案掩盖。

## 不同 slice 的例子

- Schema/backlog slice：字段稳定、状态机清楚、下游可读、旧状态不误导。
- Runtime spine slice：SQL audit、artifact refs、resume/replay、失败边界和回滚稳定。
- Workpaper slice：真实任务能产出可审阅、可批注、可复盘的底稿。
- Full product release candidate：需要跨 PRD、runtime、data/RAG、agent、Workbench、eval、ops 的综合验收。
