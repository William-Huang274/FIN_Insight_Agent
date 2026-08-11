# FIN 0.1.2 S0 phase-aware test topology 与 typed dependency 实现

日期：2026-08-02

任务：消费用户“继续”，执行 `FIN-0.1.2-S0-PHASE-AWARE-TEST-TOPOLOGY-AND-TYPED-TEST-DEPENDENCY-COMPILER-MINIMUM-ZERO-CALL-IMPLEMENTATION`。本项只做 S0 测试基础设施与零调用工程证明，不执行 formal qualification、模型、Provider、网络或业务链。

结果：`structural engineering pass / formal clean qualification authority pending / FIN 0.1.2 remains S0`

## 1. 实现结果

- 新增单一机器注册表 `fin_ia_0_1_2_s0_test_execution_contract_registry_v1_0.json`，固定五个 phase、10 个 selected modules、六类 typed dependency resolver 和 gating 规则；
- 新增 `test_execution_contract.py` 编译稳定 execution plan/digest，并对 unknown/duplicate phase、duplicate/mixed module、unknown bundle、历史 gate 升级和 policy drift fail closed；
- runner 在 registry 存在时只把 `disposable_current_gate` 的 3 个模块与 typed closure 物化；host preflight、historical audit、post-run attestation 分开运行和出 terminal result；
- Python closure 可解析普通 import、relative ImportFrom 和 lazy `import_module` registry，不再靠 `src/tests` 全目录前缀；current projection binding/source_paths、Runtime registry、reference roles、immutable events、fixtures 均由 typed resolver 负责；
- 新增 `repository_test_resource`，selected disposable tests 的直接非 Python repository read 显式携带 bundle ID；静态审计拒绝绕过 helper 的 ROOT read；
- pytest `--basetemp` 固定到每个 disposable temporary root 的专用子目录；URI 在 filesystem pattern 前被识别，双转义 Windows repr 只影响 semantic projection，raw capture 保持字节不变；
- candidate manifest R2.2 明确为 engineering candidate、没有 formal authority，`repository_prefixes=[]`。

## 2. 实现中暴露并一次修掉的结构问题

工程 full-chain 不是一次即绿，但失败都在同一个 compiler/topology 范围内，因此没有拆成新版本或逐文件补丁：

1. package builder 的二次 contract readback 没复用 compiler 的 phase filter；统一后 host/historical test source 不再回流 disposable；
2. Python closure 首版漏掉 lazy import registry；改为解析相对 module 字符串；
3. 随后发现普通 relative ImportFrom 也未闭合；补成通用 package-relative module resolution；
4. semantic path 验收缺少真实 `fixture://` 和 escaped Windows repr mutation；补齐 URI-first scan masking 与 semantic-only separator normalization，未知 escaped host path 仍 fail closed。

这些都属于 S0-07 的同一 typed compiler 合同，不是金融 Runtime、DeepSeek 或产品分析质量问题。

## 3. 验证

- phase registry、mutation、typed helper、projection closure、synthetic two-disposable/separate-result full-chain：`10 passed`；
- 三案例、Runtime resources、semantic parity、reference-role host compiler、version consolidation 回归：更新前 `75 passed`；
- 最终 semantic URI/escaped-path suite：`13 passed`；
- 最终工程 full-chain r6：784 tracked files、0 explicit/per-file allowlist；host preflight=`31 passed`；两套 disposable 各=`58 passed`，collection error=0，unknown absolute path=0；semantic parity=true；post-run attestation=pass；repository unchanged=true；
- historical audit=`23 passed / 1 finding`。唯一 finding 是旧 R2.1 authority 事件已由历史失败 attempt 消费，因此不能继续声称“未消费”；它被完整保留但不阻断 current candidate；
- credential/model/provider/network/business calls=`0/0/0/0/0`。

受限工程证据：`.codex_runtime/fin_0_1_2_s0_phase_aware_engineering_fake_full_chain_r6/verification.json`，SHA-256=`00a7730b41615c351ff1468fffe43e9269dedebc18d6e1d60c9c245feceb457a`。它不是 formal qualification evidence，不能晋升为 S0 pass。

## 4. 状态与边界

RC-P36-090/091/093/094/095/097 均进入 `engineering_repaired_formal_reproof_pending`，本项不关闭 full-chain blocker。RC-P36-092/096 保持 closed。FIN 0.1.2 仍在 S0，S1-S5 未开始，FIN 0.2 定义不变。

下一项：

`FIN-0.1.2-S0-PHASE-AWARE-CLEAN-ENVIRONMENT-QUALIFICATION-AUTHORITY-DECISION`

该 decision 需另行授权；只有绑定 committed candidate、clean/synced HEAD 与新 exact manifest 后，才可签发一次 formal qualification。当前不得直接执行、重跑旧 authority、读取凭据、调用模型/Provider/网络、进入 S1、打 tag 或发布。
