# Token Budget And Agent Information Economy Policy

token 策略不是单纯省钱，而是衡量 agent 架构是否把输入转化成有用判断。

## 核心指标

- token-to-rendered-claim yield；
- specialist useful-output rate；
- duplicate evidence transfer / prompt overlap；
- repair loop due to agent failure；
- required-item answer density；
- writer payload composition；
- low-value context ratio；
- paid-call fanout vs required-item coverage。

## 修复顺序

1. 先修 role-specific evidence selection。
2. 再修 specialist 激活策略。
3. 再修 pack projection / compression。
4. 再修 ClaimCard -> JudgmentCard / MemoLogicPlan 主输入。
5. 再修 writer/verifier prompt scaffold。
6. 最后再考虑模型切换或 paid full-chain。

## 不能接受的做法

- 简单砍 evidence 导致判断更浅。
- 用小模型替代但不修上下游结构。
- writer 收到 evidence dump 后靠模型自己总结。
- 用 full-chain 反复烧 token 找 deterministic bug。

## 通过口径

预算通过只说明“可跑”，不说明“质量通过”。真正 closeout 需要同时证明：

- 预算内；
- 信息重复低；
- required item 覆盖高；
- writer 输出不是模板化边界说明；
- evidence-to-thesis 链条可追踪；
- 失败能定位到最早 owned artifact 或外部边界。
