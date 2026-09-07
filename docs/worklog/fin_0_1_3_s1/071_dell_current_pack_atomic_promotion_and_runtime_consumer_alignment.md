# S1 工作记录 071：DELL current Pack 原子晋升与 Runtime 消费者对齐

## 结果

- 通过已签发的零调用 authority，将 DELL current Pack 从 29 条 Evidence 原子替换为 capture-bound 48 条 Evidence successor；MU、NVDA、ORCL、ASML、ANET 按 predecessor digest 原样保留。
- current Runtime registry 从 R30 更新到 R31，Workspace、reviewed anchor catalog、binding receipt、binding policy 和 Pack result 同步切换到同一 composition。
- 执行期间为 0 network、0 provider、0 model、0 retry；没有复制私有对象，也没有把 bounded context 改写成 Dell direct Evidence。

## 消费者集成发现与处置

- 首次 Runtime 回归暴露了一个真实消费者 seam：Workbench 只识别“本轮显式 replacement”，没有识别“上一份 current composition 中已经晋升、这一轮按 digest retained”的 MU/NVDA。
- 这不是检索或模型失败，也不能通过放宽 pack binding 校验解决。当前 lineage projector 已区分 `replacement_in_current_composition` 与 `retained_from_predecessor_composition`；两类都继续校验 current artifact、payload 和 ProductReadiness digest。
- 历史 VS1/VS4 projection 仍只作为历史 lineage，不能冒充当前 Pack producer。
- S3 current consumer 已新增 reviewed `PUBLIC_WEB` 合同：Dell 官方网页只在 issuer-primary 条件下可作直接 Evidence，供应商、行业机构和可信媒体只能作为 bounded context；它们没有 Dell 精确数值或因果归因权限。
- 旧 consumer policy 遇到新来源时，只能省略“系统已知且 reviewed-anchor-bound”的来源类；未知来源、未知层级或未锚定材料继续 fail closed。历史 fixed-Pack 因而保持不可变，新 current consumer 则能显式消费新增来源。

## 当前边界

- DELL current Pack 现为 48 条 Evidence，但 14 个 residual gap 仍保留；本次晋升不等于 EvidencePackReadiness、S1 通过、NumericFact 完成或 S3 授权。
- 下一责任层是 S2：只把合格输入编译为派生值、区间和情景；Dell 精确 ASP、台数、专属 allocation 等仍必须保留 typed gap，不能用行业上下文填空。

## 验证

- Pack/Workbench/Runtime 第一组定向回归：`39 passed`；PUBLIC_WEB 与历史兼容/fail-closed 第二组定向回归：`12 passed`。
- 全仓回归：`1042 passed`，仅保留 2 条既有 SWIG deprecation warning。
- DELL current Pack：29 → 48 Evidence；14 → 14 residual gaps。
- current composition result digest：`4365dc769b47e56bd6fec2926d95490dfcd62217742449a9c0d1cdaa0dfe8f9f`。
