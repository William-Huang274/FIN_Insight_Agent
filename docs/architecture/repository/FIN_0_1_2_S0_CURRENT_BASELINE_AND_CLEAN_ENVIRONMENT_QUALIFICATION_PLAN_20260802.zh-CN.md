# FIN 0.1.2 S0 当前基线与干净环境验收计划

日期：2026-08-02
状态：`S0-04 engineering pass / S0-05 clean qualification authorized not executed`

产品计划：`docs/product/FIN_0_1_2_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260802.zh-CN.md`

## 1. S0 只回答什么

S0 只确认当前代码、配置、Prompt、fixture、测试和原始运行记录在本机与干净目录中可复现。这里的 clean-environment acceptance test 只是 S0 验收手段，不是独立产品、版本或复杂治理平台。

## 2. 新起点

以当前累计代码 HEAD 为基础，不回滚原 0.1.3 实现。S0 当前状态是“实现资产存在但最终验收未通过”，不是从零开始，也不是继承历史 proof pass。

当前已知 S0 问题为 RC-P36-090–096。它们全部留在 FIN 0.1.2 S0；模型质量、真实研究结果和 Workbench 用户价值不进入本阶段。

## 3. 执行顺序

### S0-01 版本与当前状态归并

已完成。恢复 FIN 0.1.2 为当前产品版本；原 0.1.3/0.1.4 仅保留为历史修复与提案；建立单一 current projection 和 supersession mapping。

### S0-02 当前代码资产盘点

已完成只读初审。详细结果见 `FIN_0_1_2_S0_CURRENT_CODE_ASSET_AUDIT_20260802.zh-CN.md`。

### S0-03 Owner 审核（已完成）

用户以“继续”批准保留、修复和退出当前入口的分类，并授权严格限于本地零调用 S0-04 集中修复。

### S0-04 集中修复（工程通过）

已完成一轮按根因分组的修复：

1. 当前状态与历史事件分权：历史测试只验证当时发生的事件，current projection 独立表达今天的版本和下一步；
2. 简化 clean-environment runner：不把产品版本、用户授权和一次测试运行编织成复杂硬编码状态机；
3. 统一当前资源和引用入口：复用已实现的 29 项资源、六类引用和八类环境路径，但建立版本中性的 current manifest；
4. 清理测试归属：S0 只收当前基础测试，S1 三案例逻辑作为依赖回归，不让旧 closeout 测试拥有 mutable truth；
5. 修复 RC-P36-090–096 的最早责任代码，并给每类根因增加确定性回归。

本地验证结果为：current manifest selected suite=`95 passed`，FIN 0.1.2/0.1.3 全部 S0 兼容合同=`147 passed`，DELL/MU/NVDA 零模型链=`31 passed`。这些结果只建立 S0-04 engineering pass；尚未执行干净环境 package、双目录比较或 S0 closeout。

如果实现中发现新问题，先判断阶段归属。S0 问题修在 S0；S1–S5 问题只登记后传。不会自动增加产品版本。

### S0-05 本机与干净环境验收

资格授权已完成，但尚未启动 attempt。授权只覆盖一个固定 ID、固定 manifest、固定 current projection 和固定离仓输出目录的零模型 qualification；runner 会在输出创建前校验 authority digest、投影摘要、source bindings、clean worktree、HEAD=upstream 和 engineering-base ancestry。旧 manifest 缺少 authority 时只能作为历史证据读取，不能启动真实资格运行。

顺序为：

1. 当前核心单元/合同/mutation 测试；
2. 本机 import、collection、三案例 full-fake 和失败留存；
3. 一个干净目录完整运行；
4. 最终两个相互独立目录运行并比较业务语义；
5. repository readback 和原始失败证据留存检查；
6. S0 closeout 与 RC-P36-090–096 逐项处置。

失败 attempt 永久保留。允许在定位根因、完成修复并添加回归测试后用新 attempt ID 重验；禁止不改任何条件直接碰运气重跑。

## 4. 简化后的通过标准

S0 通过必须同时满足：

- 当前生产模块能导入，当前测试能收集；
- 所需资源均来自 Git tracked 或明确带 digest/type/reason 的受控入口；
- `.git`、`.codex_runtime`、未跟踪文件和宿主绝对路径不能成为隐藏依赖；
- DELL/MU/NVDA 零模型链保持基础回归，但不在 S0 声明产品质量；
- 失败仍先保存完整安全 capture 和 terminal result；
- 两个独立目录得到一致的业务语义结果；
- 历史 event、当前 projection 和运行 attempt 三类真值互不冒充；
- RC-P36-090–096 关闭，或有经用户接受且不影响 S0 目标的明确外部边界。

## 5. 停止和反思规则

- 同一失败原因未修复前不重跑；
- 连续出现同一根因说明修复无效，回到最早责任代码；
- 连续出现新的不同 S0 缺陷时，先向用户报告 S0 设计可能仍不完整，再修改计划；
- 不因测试失败新建产品版本；
- 不为了测试全绿降低资源、身份、数字、日期、引用或原始证据标准；
- 执行过程中必须遵守 `docs/project_os/senior_assistant_collaboration_policy.zh-CN.md`，主动指出不合理需求和规划。

## 6. 本计划没有授权的动作

S0-04 本地零调用实现与确定性回归已完成，S0-05 仅授权一次后续 clean-environment qualification；当前未创建或执行 package，也未完成证据 closeout。凭据读取、DeepSeek/OpenAI/Sub2API 调用、业务网络、exact-live、DELL/MU/NVDA 产品验收、自动 retry/replacement、tag、release 或 production 仍未授权。
