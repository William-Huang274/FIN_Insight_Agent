# S3 Multi-Agent Preview：Project OS 决策与执行权限分层

## 1. 为什么第一次预检失败

第一次 DELL Preview authority 直接送入通用 Project OS preflight。该文件只描述实现提交、输入摘要、执行上限与输出位置，没有旧 fixed-pack 决策所需的 `case_key` 等项目级字段。预检器因此把新 execution authority 误判成旧 fixed-pack decision，并以 `project_os_decision_field_invalid:case_key` fail closed。

这次失败发生在执行前：模型、Provider、网络和付费工具调用均为 0，Preview Runtime 没有被证明失败。原 authority v1.0 及失败回执作为不可变证据保留，不补字段、不复用。

## 2. 根因与结构性修复

根因是两种权限被混成一份文件：

- Project OS scope decision 应回答：本轮为什么值得跑、允许跑到哪、哪些 stage／产品结论明确禁止；
- execution authority 应回答：在哪个干净提交上，用哪些摘要绑定输入、什么预算和什么唯一输出身份执行。

当前新增 Multi-Agent Preview scope decision schema。它绑定角色拓扑、研究目标、零调用 proof、Provider profile 和历史 R7 内容失败；要求六个专业会话、Lead 协调、FeedbackReceipt、checkpoint/resume、独立 Evaluator、条件式 Writer及逐节点 `TokenBudgetBasis`；同时禁止外源网络、Candidate promotion、S1／S3／泛化／人工／发布与 release 权限。

Live runner 的 authority schema 升级为 v1.1，并必须额外绑定已经过 Project OS 校验的 scope decision。scope decision 与 execution authority 对同一 topology、objective、proof、profile、历史 assessment 和 execution limits 必须完全一致，否则 fail closed。

## 3. 证据与边界

- v1.0 preflight failure：0 model／provider／network／paid call，authority reuse forbidden；
- scope decision 的 Project OS 定向测试覆盖正常通过、预算从 22 扩至 23 时 fail closed；
- Preview／Runtime／Project OS 定向回归共 45 tests、全仓 833 tests 通过；
- Python compileall、活动基线 `183 Python／8 frontend／5 detector／27 Runtime／0 forbidden`、7,359 文件秘密扫描和 diff check 通过；
- 尚未执行付费 Live，也尚未证明模型消费反馈、角色协调增益、内容质量、Writer 成稿或真正 Multi-Agent Live；
- RC-S1-049 仍属于 S1 动态召回，不因当前 reviewed-Evidence Preview 被掩盖。

## 4. 后续唯一顺序

1. 在干净、已推送提交上运行 committed scope decision 的 Project OS preflight；
2. preflight 通过后签发全新的 execution authority v1.1；
3. 只执行一次 DELL Multi-Agent Preview；
4. 按数据基建／Harness／Agent 编排与角色／模型判断／Evaluator 五个责任面评估结果，不把上游数据缺口归罪于 Agent。
