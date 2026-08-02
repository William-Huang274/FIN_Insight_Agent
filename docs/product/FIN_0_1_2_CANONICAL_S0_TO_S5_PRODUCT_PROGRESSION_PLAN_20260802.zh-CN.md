# FIN 0.1.2 合并后统一 S0–S5 产品推进计划

日期：2026-08-02
状态：`current canonical plan / S0 clean qualification authorized not executed / S1-S5 not started`

## 1. 为什么重新建立本计划

FIN 0.1.1 已完整经历第一轮 S0–S5，并在 S4 暴露共同 Runtime、模型边界、跨案例迁移和验收节奏被混在一起的问题。FIN 0.1.2 原本就是把这些问题重新分配到新的 S0–S5 后完成第二轮产品迭代。

后续把多个 S0 测试失败分别编号为 FIN 0.1.3 和 FIN 0.1.4，错误地把测试尝试当成产品版本。用户已明确纠正：原 0.1.3 的实现和原 0.1.4 的规划全部并回 FIN 0.1.2；失败证据保留，但当前产品版本恢复为 FIN 0.1.2。

## 2. 当前产品真值

- FIN 0.1.1：冻结的第一轮内部 honest-block 基线；
- FIN 0.1.2：当前唯一开发版本，正在重新完成 S0；
- 原 FIN 0.1.3：FIN 0.1.2 S0 的历史 recovery/proof attempts，不再是当前产品版本；
- 原 FIN 0.1.4：未执行的 S0 改进提案，不再是当前入口；
- FIN 0.2：继续是 Earnings Review Alpha，定义不变；
- FIN 0.1.2 当前没有新增用户可见能力，release qualified=false。

合并使用当前累计代码，不回滚原 0.1.3 已实现资产，也不继承其未成立的 proof pass。

## 3. S0–S5 的简单分工

| 阶段 | 用大白话描述的目标 | 通过条件 | 不在本阶段处理 |
| --- | --- | --- | --- |
| S0 可靠基础 | 当前代码在本机和干净目录中使用同一批已登记资源稳定运行，不靠隐藏文件、旧账本或机器路径碰巧通过 | 当前代码/资源/配置清单一致；本机测试通过；一个干净环境通过；最终两个独立目录复现一致；RC-P36-090–096 关闭或得到诚实边界 | DeepSeek 质量、真实金融结论、三案例产品验收 |
| S1 三案例确定性链 | 不调用模型也能让 DELL、MU、NVDA 走同一条 6/12/12/9 链 | 三案结构、数字、日期、身份、来源和失败留存可重算；mutation/permutation/跨案污染全绿 | 用 fixture 结果冒充模型或产品质量 |
| S2 模型边界 | 用少量真实调用确定 DeepSeek 可以可靠生成什么，哪些表面必须由本地程序掌管 | 对改变的合同家族做有界 canary；确定主线模型、允许的 judgment atoms、降级/本地接管边界和成本 | 三案 full-chain、逐字段 live 修补 |
| S3 单案例产品锚点 | 当前 Runtime 上的 NVDA 生成完整可追溯九件套并对分析师有增益 | exact-live 成功；独立 L1 通过；paired assessment 和 owner acceptance 成立 | DELL/MU 迁移 |
| S4 跨案例与工作台价值 | 同一冻结 Runtime 迁移到 DELL/MU 并保持 NVDA，工作台可审阅、修订和追溯 | DELL/MU R2、post-transfer NVDA、NVDA R3、三案回归和 Workbench dogfood 达标 | 在 S4 重做共同 Runtime 或模型基础合同 |
| S5 发布判断 | 团队能够复现、回滚并诚实签发或阻断内部候选 | RG1–RG5、证据清单、代码/配置 manifest、回滚和用户价值结论完整 | 用仓库可恢复性代替产品质量 |

## 4. 问题分配规则

发现问题后先问：它是否会使当前阶段目标不成立？

- 会：留在当前阶段修复，保留失败 attempt，以新 attempt 重验；
- 不会：记录明确 owner，传递到负责它的后续阶段；
- 不确定：先做最小只读/零调用定位，不立即扩展范围；
- 同类失败反复出现：暂停并重新审查当前阶段设计，不自动创建新产品版本。

失败测试、proof 或 run 不再自动冻结 FIN 0.1.2，也不自动创建 FIN 0.1.3。新产品版本只在完整迭代结束/战略终止，或产品范围与兼容性发生实质变化并经用户批准时建立。

## 5. 已有资产的处理

直接保留并重验：共同 Runtime 合同、十个 consumer、三案例 fixture/full-fake、capture/terminal result、RuntimeResourceRegistry、六类 reference role、typed environment 和 hermetic runner 的通用部分。

需要修复后再用：当前状态投影、manifest 与 current test ownership、proof control plane、版本专用 runner，以及旧 active suite 对 mutable backlog/next action 的绑定。

只保留历史、不再作为当前入口：0.1.2/0.1.3/0.1.4 的失败 authority、一次性预算、no-v4 版本冻结决定和 0.1.4 current projection。

## 6. 当前执行入口

版本合并、计划、新起点、只读资产审计和 S0-04 本地零调用集中修复已经完成；上一基线为 current suite=`95 passed`、全部 S0 compatibility=`147 passed`、三案例零模型链=`31 passed`。S0-05 已完成独立零调用资格授权决定，并新增 fail-closed runner 门禁：旧清单或无摘要绑定的清单不能启动真实资格运行，清单、current projection、固定输出目录和 clean/synced Git 条件任一漂移都会在创建 package 前失败。

当前下一项是：

`FIN-0.1.2-S0-FRESH-CLEAN-ENVIRONMENT-QUALIFICATION-EXECUTION-AND-CLOSEOUT`

下一项只允许执行一次已冻结的 fresh clean-environment qualification，并在同一结果上做证据复核与 RC-P36-090–096 处置；当前 attempt/package 计数仍为 0，S0 尚未通过。模型、Provider、网络、真实业务链和产品 Artifact 均未授权。
