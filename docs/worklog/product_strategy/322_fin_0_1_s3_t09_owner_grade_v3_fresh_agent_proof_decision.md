# FIN 0.1 S3-T09 owner-grade v3 fresh Agent proof decision

日期：2026-07-22

## 结果

用户只授权本轮 fresh output-v3 Agent proof 决策。本轮冻结了全新的 exact identity、input digest、prospective admission、DeepSeek route、预算、零复用与首错停止合同；没有签发或消费 admission，没有调用模型、provider、网络、来源或工具，也没有创建 Agent Run、执行 paired comparison 或写入 Human Review。

决策状态为 `pass_fresh_v3_exact_proof_contract_decided_admission_issuance_pending_separate_authority`。下一项是 `S3-T09-OWNER-GRADE-V3-FRESH-EXACT-ADMISSION-ISSUANCE`，仍需用户单独授权，而且只能签发、不能执行。

## 精确身份与输入

- execution identity：`fin01-s3-t09-three-cell-deepseek-owner-grade-v3-live-validation-r1`
- WorkUnit：`wu_p02_5_7c9d8f72c8ceed8cb8e77d58`
- Attempt：`attempt_fin01_ac510b41a2d9d4a955960179`
- ResearchRun：`research_run_fin01_b939a453b921cb5bcf3c2edf`
- input digest：`dba3d25144edfd0f7411d638b964deba8bab70406fb33b3bfca7c16be6bcf06e`
- preparation digest：`fa95fcbfb777273634141e58769adaa351073d700190bfd7c6f5bc857855815f`
- prospective admission：`fin01-s3-t09-three-cell-deepseek-owner-grade-v3-exact-admission-r1`
- prospective admission digest：`5f8db7ff2eef2b8ea06c8c95b21c32dec57432b34888a9cf6c5990af3d4b4459`

以上身份与旧 failed Agent Run、output-v2 succeeded Agent Run、exact deterministic baseline Run 均不同。Agent 继续使用相同 Case/version、DecisionSurface、as-of、input-head 和三 Cell；baseline body、artifact 和结论不进入 provider input，避免答案泄漏。

## Provider 与预算复核

保留 DeepSeek `deepseek-v4-pro`，目的是只改变 output-v3 合同而不同时改变 provider，从而能区分“合同修复是否泛化”和“换模型带来的差异”。这不代表 DeepSeek 已原生满足严格 schema：当前 transport 只使用 `json_object`，closed v3 schema、Candidate/Evidence/Numeric authority、semantic fidelity 与 false-green guard 仍由本地 validator fail-closed。

预算固定为三个 Specialist 各 2200、Lead 1200、Writer 1400、Verifier 1000，aggregate 10200 output tokens；semantic/provider/network calls 上限均为 6，USD 0.10，transport attempt=1，retry=0。首个 parse、schema、semantic 或 length failure 必须 terminal stop，禁止自动修补、fallback 或 rerun。

执行进程还有一个硬前置条件：`LLM_GATEWAY_TRANSPORT_RETRIES=0`。本轮环境中该变量未满足，因此本轮只完成决策；未来即便签发 admission，也必须在独立 execution authority 下重新 fail-closed 校验。

## 安全与验证

`prepare_fin_ia_0_1_s3_t09_owner_grade_v3_fresh_agent_proof_decision.py` 将 canonical runtime 复制到 disposable clone，两次编译结果完全一致，clone execution counts 不变。prospective admission 通过现有 v3 schema 和 factory construction；provider callback 若被触发会立即失败，实际触发次数为 0。

目标 canonical database SHA-256 仍为 `46ba35b8dd1b65fb3980470ebeed00dc38c9e17f1576876291c2659bb94edc9f`，object tree SHA-256 仍为 `00ac740b53c91c032b221453cf9269c5748a7fbcf5802bbc239a8e34ae21ea75`，逻辑快照不变。

本轮新决策与直接依赖为 25 passed；其余 S3-T09 合同先得到 50 passed 和 6 个仅因 current backlog 已推进而陈旧的断言，修正这些当前状态断言后逐个 6/6 通过，合计 81 个 T09 tests 均有通过结果。Python compile、JSON/JSONL parse、diff check 与新增内容的明文 key 扫描通过。

## 产品边界

本轮没有产生新的研究事实、Evidence、财务指标或 Alpha，也没有证明 repaired v3 能被真实模型稳定满足。fresh Agent 的 comparison artifact 在生成时仍会标记为 pending；真正 paired comparison 必须在另一个只读步骤中独立绑定 fresh terminal Agent Run 与已物化 deterministic baseline。RC-P36-037 继续阻断 S3-T09、T10、S4、release 和 production。
