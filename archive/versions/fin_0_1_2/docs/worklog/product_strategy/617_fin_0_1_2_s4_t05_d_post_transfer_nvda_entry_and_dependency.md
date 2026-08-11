# FIN 0.1.2 S4-T05-D post-transfer NVDA 入口与依赖审计

时间：2026-08-05

状态：`zero-call entry/dependency pass / Search reuse / fresh live not authorized`

## 本轮目标

用户在 T05-C MU Owner acceptance 后要求继续。本轮只处理 T05-D 入口、资产复用边界、当前 input 重编译和零调用全链复证；不访问外部来源，不调用 DeepSeek，不签发或消费 admission。

## 资产分类

- 直接复用：T03 NVDA current Search terminal、8 份 raw capture、T04 Evidence Pack；三者 as-of 和 content digest 均未漂移。
- 仅作历史锚点：T04 R3 exact-live 与 Owner acceptance；它们证明 pre-transfer NVDA R2，不能冒充 post-transfer 结果。
- 本轮重证：当前 T05 Agent input、lineage、9-call capacity、两套 fresh Runtime 的 capture/terminal/9 Artifact 全链。
- 后续 fresh live：最多一次 post-transfer NVDA DeepSeek exact-live，之后才是 verified surface、formal pair 和显式 Owner acceptance。
- 明确后传：RC-P36-119/122、Human Review/R3、Workbench、S5 与 release。

## 审计发现与修复

T05-A 正确保留 NVDA legacy six-slot lineage；但 shared exact-execution wrapper 只读取 DELL/MU 的 `S4_T04_source_grounded_input`。若不修复，NVDA 会在 Provider 之前失败。该问题登记并关闭为 RC-P36-123：exact wrapper 现在按冻结 case-family 选择 lineage slot，同时仍强制匹配本案 current Evidence digest。没有放宽金融事实、identity、citation 或 lineage 校验，也不是模型/Provider 问题。

## 证明结果

- current case=`fin012-s4-t05-nvda-current-evidence-34ecb73ab7539e5156bd`；
- Agent input=`75fa19a8…9216`；
- 两个 fresh zero-call Runtime normalized result 相同；
- 每套=`9 Provider callbacks / 3 local Fact receipts / 9 captures / 9 Artifacts`；
- 输入容量=`85,614 / 108,000`，最大单次=`15,678`，余量=`22,386`；
- 聚焦和相邻回归=`18 passed`；
- source/model/Provider/admission/exact-live/业务 Artifact=`0/0/0/0/0/0`。

post-transfer NVDA R2 仍为 false。下一项是 `FIN-0.1.2-S4-T05-D-POST-TRANSFER-NVDA-FRESH-AGENT-PROOF-CAPACITY-AND-ADMISSION-AUTHORITY-DECISION`；它只决定是否允许后续签发一次 fresh admission，不自动调用 DeepSeek。
