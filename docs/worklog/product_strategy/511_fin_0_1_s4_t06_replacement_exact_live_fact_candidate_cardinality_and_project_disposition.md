# 511｜FIN 0.1 S4-T06 replacement exact-live Fact candidate cardinality 与项目级处置

## 结论

按用户冻结顺序完成了独立 fresh zero-call 复证、唯一 replacement admission 签发与受监督 MU exact-live。复证通过，三案例 deterministic full-fake 各为 `6/12/12/9`；真实 live 在第 4 次调用终止，最终为 `failed/failed/failed`、`1 node / 4 calls / 4 captures / 0 Artifacts`。

本轮不进入第二次 replacement 或 R8/R9，也不做逐字段补丁。一次性项目级处置已经完成：Fact candidate generation 从模型权限中移出，后续由共享 Runtime 的本地确定性 planner 先形成最多 6 个 request-local 候选；模型只做有限枚举判断，本地再选择最多 3 个并渲染。

## 根因

第四次 DeepSeek Pro 输出：

- native JSON 与顶层 key 正确；
- `finish_reason=stop`；
- 3,696 UTF-8 bytes，低于 4,800-byte 上限；
- 22 个 `fact_atoms`，对应请求暴露的全部 22 个合法 support aliases；
- 请求明确声明 `provider_candidate_maximum=6`。

所以这一次既有模型数量指令不遵循，也有项目鲁棒性缺口。只把最大值写在 prompt/JSON 请求里，无法让金融 L1 依赖获得足够稳定性；候选池大小必须在调用前由本地系统控制。

## 运行证据

- result：`configs/releases/fin_ia_0_1_s4_t06_mu_wwc_stable_top3_replacement_r1_exact_live_failure_result_v1_0.json`
- disposition：`configs/releases/fin_ia_0_1_s4_t06_mu_fact_candidate_pool_local_bounding_project_level_disposition_v1_0.json`
- runtime result：`.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t06_mu_wwc_stable_top3_replacement_r1_live_execution_result.json`
- restricted failure capture digest：`8c27b67bb82a7bb4717d2963cda9bc796a9adabc4d2db096aff20b2689f740a2`
- tokens：`23,862 / 1,855 / 25,717`
- cost：USD `0.00845999`
- retry/fallback/replay/relaunch/rerun：`0/0/0/0/0`

四份 exact model-visible request 与 assistant final output 均由 capture-v2 内容寻址保存；公开结果不含 raw assistant text、凭据或私有推理。失败输出未进入业务 Artifact。

## 验证

- 新 result/disposition/capture/canonical-state focused：`5 passed`
- WWC implementation + deterministic planner 邻接行为：`32 passed / 1 deselected`
- 完整组合原始结果：`32 passed / 1 failed`；唯一失败是历史 phase-snapshot 测试仍要求 backlog 停在“独立复证”，不属于 Runtime 行为回归。该测试字节已被已消费 live admission 的 proof binding 冻结，因此未追改历史文件。
- JSON、backlog JSON 与两份 Project OS JSONL：全部可解析
- successor authority scope Project OS preflight：`pass / open blockers 0`
- Git staged paths：仍为历史基线 `799`，本轮未 stage、commit、push

## 阶段状态

- `S4-T06 engineering_pass=true`
- `S4-T06 live_product_pass=false`
- `S4-T06 closed=false`
- paired assessment / owner acceptance：不具资格
- `S4-T07`：未进入
- `RC-P36-080`：仍开放，未得到 9-Artifact L1 live proof
- `RC-P36-084`：开放，Fact candidate pool 必须本地有界化

## 下一项

`S4-SHARED-RUNTIME-DETERMINISTIC-FACT-CANDIDATE-POOL-PLANNER-SEPARATE-AUTHORITY`

它是共享 Runtime 的结构任务，不是继续在 T06 加一轮字段修复。本处置不授权实现或新的 live。
