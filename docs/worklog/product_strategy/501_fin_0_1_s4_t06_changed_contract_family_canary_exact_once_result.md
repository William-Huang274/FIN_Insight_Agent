# FIN 0.1 S4-T06 changed-contract 三家族 canary exact-once 结果

日期：2026-07-30

## 结论

exact-once canary 已按 authority 执行并在 Claim 家族首错终止。Fact 家族通过，Claim 家族未形成任何 scope-compatible candidate，WWC 未调用。T06 继续 blocked。

这不是 full-chain、R7、九 Artifact、paired assessment 或 owner acceptance。

## 执行前证明

- Project OS：`pass / open blockers 0`
- 凭据：存在，值未输出或持久化
- result/state/capture identity：执行前均不存在
- worst-case projected cost：USD `0.01222132 < 0.03`
- runner、authority、fresh proof、implementation 合同：`27 passed`
- retry/fallback/replay/provider hopping：`0/0/0/0`

## 真实结果

### Fact

- Provider status / finish：`ok / stop`
- input/output/total tokens：`3983 / 272 / 4255`
- cost：USD `0.00196924`
- atoms：`5`
- raw UTF-8 bytes：`972`
- compiled wire：pass
- local deterministic assembly：pass

### Claim

- Provider status / finish：`ok / stop`
- input/output/total tokens：`3300 / 88 / 3388`
- cost：USD `0.00151206`
- native JSON：成功
- local selector：无 scope-compatible candidate
- terminal code：`s4_compiled_claim_atom_no_valid_scope_compatible_subset`

### WWC

未调用；Claim 是首个可信失败，authority 要求立即停止。

总计 model/provider/network/transport=`2/2/2/2`，input/output/total tokens=`7283/360/7643`，cost=USD `0.00348130`，captures=`2`。

## 审计与边界

两份 `fin01.runtime.provider_interaction_audit_capture:v2` 均在本地 validation 前原子保存，并通过 capture digest readback。capture 保存 exact model-visible request 与 final assistant output；未保存 credential、Authorization/header、Cookie、raw Provider envelope 或私有推理。公开 result 不含原始请求或输出。

没有 canonical WorkUnit/Attempt/Run/Artifact 写入，没有业务内容晋升，没有 paired、owner 或 T07。

Fact 的自然合同遵循已有正证据。Claim 的失败不是 transport、finish_reason 或 JSON 解析问题，但当前还不能判定是模型选择、deterministic seed、eligibility 规则还是编译合同边界导致；必须由下一项零调用 disposition 对 restricted capture 与 selector 逐层对账。不得直接补跑 WWC 或进入 R7。

## 证据

- result：`configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries_exact_once_execution_result_v1_0.json`
- result SHA256：`410051c4dc94eb94c8d2f06fbc601e57dfc5b8e759cb6a938bbc17d99d7ae9bb`
- runner：`scripts/releases/run_fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_output_canaries.py`
- runner SHA256：`6559c2ff6bc080fddc49e8fd3346d447d2f8509f57f2a7f3ae50c800040fdb93`
- runner test SHA256：`c2da5db8b233fb6acaabdcd61637582ef4c8c5baf7770c10abc1d4bdc32096bd`
- result test SHA256：`857fd1c861360c0869e232fbb6e4344da84d3a834c424127475229c0c6483235`
- result + runner + authority + fresh proof + implementation：`30 passed`
- restricted capture root：`.codex_runtime/s4_t06_mu_changed_contract_family_single_node_canaries_exact_once_r1/captures`
- next disposition Project OS preflight：`pass / open blockers 0`
- preflight ref：`.codex_runtime/s4_t06_mu_changed_family_canary_post_result_disposition_preflight.json`
- preflight SHA256：`cd4fce3a7a6d65ace77854f661daa39a6ba087d83546c49a38f7c8c533a743f9`

Git 仍为 `codex/layered-data-source-expansion`，ahead 5，工作树存在大量历史 staged、unstaged 与 untracked 混合变更。本项不暂存、不提交、不推送，避免混入用户既有工作。

## 下一项

`S4-T06-MU-CHANGED-CONTRACT-FAMILY-SINGLE-NODE-NATURAL-OUTPUT-CANARIES-POST-RESULT-DISPOSITION-DECISION`

下一项只做零调用根因/范围处置，禁止 retry、字段补丁、WWC 单独补跑、R7 admission、formal exact-live 或扩大 T06。
