# FIN 0.1.1 / 0.1.2 版本谱系与发布节奏决策

日期：2026-07-31
更新：2026-08-02（0.1.2/0.1.3/0.1.4 合并纠偏）
状态：`accepted_product_lineage / FIN_0_1_2_current_S0_rebaseline / FIN_0_2_definition_preserved`

## 1. 产品大方向不变

```text
FIN 0.1 bounded internal research workflow
  -> FIN 0.2 Earnings Review Alpha
  -> FIN 0.3 Review & Memory Beta
  -> FIN 0.4 Cross-sector Beta
  -> FIN 0.5 Enterprise Pilot
```

FIN 0.1.1 和 FIN 0.1.2 是 FIN 0.1 内部产品迭代。产品版本必须表达一轮完整产品承诺，不能用于给一次测试、proof 或修复尝试编号。

## 2. 当前版本定义

| 版本 | 当前定位 | 状态 |
| --- | --- | --- |
| FIN 0.1.1 | 第一轮 S0–S5 内部工程基线 | frozen internal honest block；NVDA 有历史锚点，DELL/MU 与 release 未通过 |
| FIN 0.1.2 | 把 0.1.1 在 S4 膨胀的问题重新分配到新 S0–S5 的完整第二轮产品迭代 | 当前唯一开发版本；S0 rebaseline in progress；release=false |
| FIN 0.2 | Earnings Review Alpha | 定义不变；不得接收 FIN 0.1 未完成的共同 Runtime 债务 |

历史上名为 FIN 0.1.3 的提交、配置和工作日志，现统一解释为 FIN 0.1.2 S0 recovery/clean-environment acceptance attempt family。历史上名为 FIN 0.1.4 的内容只有未执行规划入口，现解释为 FIN 0.1.2 S0 improvement proposal。旧文件和失败证据保持不可变，但二者均不再是当前产品版本或 next action。

机器权威：`configs/releases/fin_ia_0_1_2_version_consolidation_and_current_rebaseline_v1_0.json`。

## 3. FIN 0.1.1 的冻结语义

FIN 0.1.1 保存第一轮 S0–S5 的真实结果：

- NVDA historical S3 R2 和 owner evidence；
- DELL/MU 真实 transfer diagnostics，但各自 R2 未通过；
- post-transfer NVDA、NVDA R3 与三案同时通过未成立；
- S4 以 honest block 关闭，S5 以 decision-only honest block 关闭；
- 完整失败、成本、恢复包、commit/rollback 与 evidence inventory 可追溯；
- `FIN_0_1_release_qualified=false`。

冻结 0.1.1 的原因是第一轮已经实际走过 S0–S5，而 S4 暴露的共同问题证明早期阶段规划不足；它不是因为单个测试失败而被换号。

## 4. FIN 0.1.2 的完整使命

FIN 0.1.2 从 S0 重新验证但不从零重写：

- S0：当前代码、资源、合同、capture、测试和干净环境可复现；
- S1：DELL/MU/NVDA 三案例 deterministic 6/12/12/9；
- S2：DeepSeek Flash stable/Pro preview 的能力边界与本地接管面；
- S3：在 frozen evidence 上完成 NVDA current exact-live 九件套、paired、final delivery review 和 owner disposition；S3 不验收 F05 Agentic Search；
- S4：自然 Case、public/local Agentic Search、Evidence Gate、Agentic Research、DELL/MU transfer、post-transfer NVDA、当前 Workbench 与 exact Human Review；
- S5：F01–F15 evidence inventory、RG1–RG5、复现、回滚和 release decision。

完整当前计划：`docs/product/FIN_0_1_2_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260802.zh-CN.md`。

2026-08-04 的 PRD 能力对账确认：RAG、Agentic Search 和 Agentic Research 原本就是 FIN 0.1 bounded release scope，不是统一后置到 FIN 0.2；FIN 0.1.1 只有 scoped/historical evidence，没有完整 product acceptance。修正后的 feature/stage 分配见 `docs/product/FIN_0_1_1_0_1_2_PRD_CAPABILITY_ALIGNMENT_AND_S0_TO_S5_REBASELINE_20260804.zh-CN.md`。

## 5. 历史 0.1.3/0.1.4 合并语义

合并不回滚代码、不删除文档，也不把历史失败改成通过：

- RuntimeResourceRegistry、六类 reference role、typed environment、proof policy、三案例 fixture 和 capture/terminal result 可以按当前 digest 复用；
- 历史 host/formal proof 失败继续有效；
- 原 0.1.3 的 no-v4 与原 0.1.4 的新版本入口不再有当前效力；
- product version、S-stage、contract version 与 run/attempt 必须分开；
- 修复后重验使用新的 attempt ID，不使用新的产品版本号。

## 6. 修复和版本变化规则

1. 当前阶段问题在当前阶段修；后续阶段问题登记后传；
2. 失败 attempt 不可改写，但根因修复后可用新 attempt 重验；
3. 禁止无变化盲目重跑；
4. 同类失败反复出现时重审阶段设计，不自动升级产品版本；
5. 只有完整 S0–S5 迭代完成/战略终止，或产品范围、兼容性发生实质变化并经用户批准，才讨论下一个 FIN 0.1.x；
6. FIN 0.2 入口仍要求 FIN 0.1 Runtime 和 exact artifact 主线稳定。

## 7. 当前顺序

```text
FIN 0.1.1 frozen historical baseline
  -> FIN 0.1.2 S0 current baseline review and repair
  -> FIN 0.1.2 S1 deterministic three-case
  -> FIN 0.1.2 S2 model boundary
  -> FIN 0.1.2 S3 NVDA anchor
  -> FIN 0.1.2 S4 transfer and Workbench value
  -> FIN 0.1.2 S5 release decision
  -> FIN 0.2 Earnings Review Alpha
```

当前下一项：

`FIN-0.1.2-S0-CURRENT-BASELINE-AUDIT-OWNER-REVIEW-AND-REPAIR-AUTHORIZATION`

在 Owner 审核之前，不实现 S0 修复、不运行 clean-environment acceptance、不读取凭据、不调用模型或 Provider。
