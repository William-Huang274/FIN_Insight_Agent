# R6 optional resume failure 与 R7 successor 零调用复证

## 结论

R6 没有调用 DeepSeek，也没有进入五角色返修。它在第一个角色 dispatch 前被本地 optional resume 接缝错误拦截：fresh run 合法传入空 manifest，但共用 helper 无条件调用了“必须非空”的 resume validator。R6 authority、public/private terminal 和 output identity 保持不可变并已消耗。

## 最早责任层

- 属于 S3 runner 的 capture-resume 组合接缝，不属于模型、S1/S2、信源、网络或金融内容。
- fresh execution 与 capture resume 共用入口，但空 manifest 应表示“没有可复用 capture，继续 Provider frontier”，不是非法输入。
- 原 terminal 调用数按成功返回的 `provider_steps` 统计；若将来 Provider 调用中途失败，可能漏记已请求的 attempt。现改为按当前 attempt prefix 下的 `provider_attempt_requested` SessionEvent 统计，包含失败 attempt 且排除 R5 历史事件。

## 有界修复与证明

- `_resume_capture_for_attempt(())` 现在返回 `None`；非空 manifest 仍逐 SHA、digest、tool、finish reason 和 reuse 状态 fail closed。
- R7 successor 零调用证明绑定 R6 authority/public/private digest，并分别让首个角色和 Lead 走到 fresh Provider executor seam；两者均不复用 R6 identity。
- 证明保持原范围：五个责任角色各 analysis＋strict submission，再做一个 Lead analysis＋strict submission，最多 12 次；0 S1/S2、retrieval、外源、promotion、retry、fallback，Writer 仍禁止。

## 证据

- R6 terminal：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_live_result_v1_0.json`
- successor proof：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_successor_zero_call_result_v1_0.json`
- R7 scope：`configs/research/evals/fin_ia_0_1_3_s3_dell_current_dynamic_multi_agent_content_repair_successor_scope_decision_v1_0.json`
- Runtime：`scripts/research/run_s3_current_dynamic_multi_agent.py`
- 测试：`tests/test_s3_dynamic_multi_agent_loop.py`、`tests/test_project_os_preflight.py`

## 尚未证明

R7 尚未签发或执行；五份自然返修、Lead 复核、独立 L1/L2、内容质量、Writer、S3、泛化和 release 都没有通过。
