# FIN 0.1.3 S1-08 腾讯云 WSA Query-only replacement 权限

日期：2026-08-08

阶段：`013-S1-08`

归属问题：`RC-P36-157-fin-0-1-3-s1-08-operational-provider-and-candidate-coverage-insufficient`

## 1. 用户决定与边界

用户创建了新的腾讯云子账号 API Key，并明确要求按已经讨论的方案继续。网页登录强制改密与 API Key 鉴权是两条独立路径，因此本次不等待控制台登录完成。

本次只批准一个 replacement Attempt：固定 DELL semantic query、wire body 仅含 `Query`、1 provider/network、0 retry/model/document/Evidence。成功或失败均 materialize terminal 后停止；不自动增加第三次尝试、三案 comparator、SourceHunter integration 或 production promotion。

## 2. 零调用工程

- R1 runner/result/assessment 保持不改写；新增独立 successor support 与 runner。
- compiler 只允许 `request_body_fields=[Query] / optional_fields=[]`。
- `Mode/Site/FromTime/ToTime/Cnt/Industry/Freshness/Deeplinks` 的任何 mutation 在 transport 前拒绝。
- safe request 与 SDK request 使用同一个编译对象；凭据、签名和 Authorization 永不进入 capture。
- authority 绑定 R1 result/assessment、provider profile、normalizer、support、runner 与 zero-call proof 的 SHA/digest。

## 3. 验证与当前状态

- compile：通过；
- targeted contract：`15 passed`；
- Project OS replacement scope：`pass / 0 blocker / 0 contract error`；
- authority/binding dry validation：通过，编译 request body 只有 `Query`；
- provider/network/retry/model/document/Evidence：`0/0/0/0/0/0`；
- authority：`issued_unconsumed`。

当前下一项只是在 clean commit 上消费这一条 authority。新 Key 同样已在聊天截图中明文出现，测试后必须删除并重建；没有任何凭据写入仓库或工作记录。
