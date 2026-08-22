# FIN 0.1.3 S1：DELL 可观察输入与 S2／S3 派生输出归属纠正

日期：2026-08-23
状态：零调用结构修复和全仓回归通过；clean commit／push 与 AI-free R3 待执行。

## 为什么不能直接把 43 条 Evidence 映射到 R2

R2 已让 12 个 EvidenceRequest 都拥有显式材料范围，但逐命题审阅发现，其中四类 `product_intent` 不是能从来源中直接找到的材料，而是下游研究产物：

- `unit-volume sensitivity range` 属于 S2 区间估算；
- `bounded PVM scenario` 属于 S2 价格—数量—组合桥；
- `supplier cost share sensitivity` 属于 S2 价值池敏感性；
- `observable invalidation threshold` 属于 S3 研究者设定的 What-Would-Change。

另外三个以 `boundary` 命名的意图会诱导审阅者用 `boundary_only` 填满材料门，重复制造免责声明，而不是寻找可观察的客户关系、供应分配和价值归因输入。R2 保持为不可变诊断，不能直接用于 current promotion。

## 结构修复

- 保留 v1.0 程序及 R2 结果不变，新建 v1.1 程序。
- S1 的 hard material axes 只保留可观察来源输入：公司／行业销量、价格和配置、客户部署、供应关系、产能、利润与成本代理、当前反方信号。
- 新增显式 `stage_output_handoffs`：S2 接收销量区间、PVM 与价值池敏感性；S3 接收失效阈值与 WWC。
- 下游派生输出不得反向成为 S1 EvidencePackReadiness 的必填 Evidence。
- 非时间型 metric 在 S1 只作为检索上下文；S2 typed conflict 仍硬阻断，但 S2 typed gap 不再冒充 S1 资料缺失。

## 验证

- 定向：`41 passed`。
- 全仓：`1033 passed`，仅两条既有 SWIG deprecation warning。
- Python compileall、active baseline `200 Python／8 frontend／5 detectors／28 Runtime／0 forbidden`、repository secret scan `7,618 files／0 findings` 和 `git diff --check` 均通过。
- 0 模型、0 网络、0 Provider、0 Candidate promotion。

## 下一步

1. 完成 compile／baseline／secret／diff 门并 clean commit／push。
2. 使用 v1.1 程序执行唯一一次 `dell-proposition-internal-r3`。
3. 再把 43 条 Evidence 绑定到 R3 的真实 MaterialRequirement IDs，编译 polarity 与 integrated readiness。
4. readiness 通过后才允许 current promotion 与 S2 recompile；动态单单元仍没有 authority。
