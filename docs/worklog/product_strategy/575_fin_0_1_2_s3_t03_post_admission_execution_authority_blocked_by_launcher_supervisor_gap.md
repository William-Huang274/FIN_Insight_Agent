# FIN 0.1.2 S3-T03：post-admission execution authority 与 launcher/supervisor 缺口

日期：2026-08-03

## 结果

用户以新的“继续”授权 execution authority decision。Project OS 对 `FIN_0_1_2_S3_T03_exact_live_execution` 返回 pass/open blockers 0；已签 admission 与 issuance 字节、digest、fresh runtime root、retry-zero、预算和 credential presence-only 均重新核对。`DEEPSEEK_API_KEY` 只检查存在性，未读取、输出或持久化值，也未 probe Provider。

本轮没有签发真实执行权。代码审计发现 `fin_0_1_2_s3_t03_exact_live_runner.py` 只提供 `execute_bound_s3_t03` 与 `finalize_supervisor_exit` 两个库函数，没有命令入口、admission-bound child entrypoint、DeepSeek transport 装配或父进程 launch/wait/timeout/exit supervision。现有 supervisor proof 是测试代码直接调用 terminal recovery，不是实际父进程在子进程异常退出后的自动行为；仓库其他非测试 Runtime 也没有消费这两个函数。

该缺口登记为 `RC-P36-107-fin-0-1-2-s3-t03-bound-live-launcher-and-parent-supervisor-entrypoint-gap`，归 S3-T03 执行控制。它不是 DeepSeek、Provider、金融真值或业务输入问题，不重开 S0–S2，也不使已签 admission 失效。

## 边界

- admission 仍为 issued/unconsumed；runtime root 与 execution identity 仍未 claim；
- credential presence check=`1`，credential value/provider probe=`0/0`；
- supervisor/child/model/Provider/network/Run/Artifact/paired/Owner=`0`；
- 不修改模型 surface、业务 input、财务合同或 S3 的 T01–T04 结构；
- 只允许一个后续零调用 launcher/supervisor 收敛包，无自动第二包。

## 验证

- 首次组合回归为 `24 passed / 1 failed`：历史 issuance 测试错误地要求全局 backlog 永久停在旧 authority action；按精确合法后继修正生命周期断言后，新权限裁决、runner preflight 与 admission issuance 最终为 `25 passed`；
- JSON/JSONL 严格解析通过；
- Project OS 对后继零调用 implementation scope：`pass / open blockers 0`；
- Project OS 对 exact-live scope：按预期 `blocked / RC-P36-107`；
- Python compile、Git diff check 与定向 secret scan 通过。

## 下一步

`FIN-0.1.2-S3-T03-NVDA-BOUND-EXECUTION-LAUNCHER-PARENT-SUPERVISOR-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION`

该项需新的用户续行。通过后才可另行授权 exact-once 消费当前 admission；不能在实现项同轮调用 DeepSeek。
