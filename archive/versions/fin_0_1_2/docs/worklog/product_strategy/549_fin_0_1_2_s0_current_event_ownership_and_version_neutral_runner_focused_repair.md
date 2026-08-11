# FIN 0.1.2 S0 current/event ownership 与版本中性 runner 聚焦修复

日期：2026-08-02

任务：在不创建新产品版本、不调用模型、不执行 clean-environment acceptance 的前提下，完成获批的 FIN 0.1.2 S0-04 聚焦修复，并把当前真相、历史事件和单次资格验证 attempt 的责任边界拆开。

结果：`S0-04 engineering pass / S0 not passed / clean-environment qualification pending / zero model calls`

## 1. 修复前事实

修复前 focused baseline 为 `62 passed / 3 failed`。三项失败都是 `current_projection_next_action_drift`：旧 0.1.3 projection 和测试在验证历史事件时重新读取今天的 backlog 与 ledger tail，因此旧事件会随当前下一步变化而失效。

这不是 DeepSeek、金融判断、Runtime L1 或三案例产品质量问题，而是 S0 测试和状态所有权设计错误。

## 2. 实现内容

- `hermetic_test_runner.py` 分别验证 immutable legacy event 与 current v2 projection；旧事件只校验当时的 identity、binding 和治理事实，不再读取 mutable current truth。
- current projection 使用版本中性 schema，只拥有 product version、stage、next action、execution authority；attempt/run/terminal 状态禁止进入该对象。
- 新增小型版本中性 attempt contract，只允许 `planned -> running -> passed|failed`，终态不可变，同 attempt 不重试，失败不创建产品版本。
- 新 current manifest 为五类 proof class 各选一个 owner，复用 29 项资源、六类 reference role、八类环境根和 DELL/MU/NVDA 零模型基线，不恢复完整 proof lifecycle mega-state-machine。
- 新 current reference registry 使用真正的版本中性 schema；loader 同时支持旧 immutable schema 与新 current schema，历史 registry 不改写。
- 历史兼容测试改为查找自己的 event row、decision-time binding 和 recorded digest，不再把 ledger last row 或 living docs 当成旧事件的组成部分。

## 3. 主动反思与纠偏

实现中一度尝试直接修改历史 reference registry 以加入当前 root file，随即发现这会违反 immutable history 规则并导致历史 policy digest 漂移。该修改被撤回，改为新增独立 current registry。

固化结果前又发现 current registry 的文件名和 ID 虽已版本中性，但 schema token 仍伪装成旧 0.1.3。该问题属于本轮根因，因此没有后传；loader 改为明确支持 legacy/current 两种 schema，并增加 current contract test。

## 4. 验证

- current manifest selected suite：`95 passed`；
- FIN 0.1.2/0.1.3 全部 S0 compatibility contracts：`147 passed`；
- DELL/MU/NVDA zero-model regression：`31 passed`；
- 历史文件和 recorded digest：未改写；
- credential/model/Provider/network：`0/0/0/0`；
- clean-environment package/attempt：`0`。

## 5. 产品和阶段真值

- FIN 0.1.2 S0-04：engineering pass；
- FIN 0.1.2 S0：未通过，RC-P36-090–096 仍 open；
- FIN 0.1.2 S1–S5：在合并后基线下尚未开始；
- FIN 0.1 release qualified：false；
- 用户可见金融研究能力增量：none；
- FIN 0.2 Earnings Review Alpha 定义：未改变。

## 6. 下一项

`FIN-0.1.2-S0-FRESH-CLEAN-ENVIRONMENT-QUALIFICATION-AUTHORITY-DECISION`

下一项只决定是否授权一次 fresh clean-environment qualification。当前 S0-04 权限不能直接执行该 runner；更不能读取凭据、调用模型、进入 S1、签发 release 或把本地全绿写成 S0 通过。
