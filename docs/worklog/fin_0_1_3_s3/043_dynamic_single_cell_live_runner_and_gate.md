# 043 S3 动态单单元 live runner 与范围门

日期：2026-08-16
状态：实现与范围门通过；真实 live 尚未执行

## 这一步解决什么

formal v1.2 已证明受控 atoms 可以贯通当前 S1/S2、EvidenceResponse、动态三片段、终态 Judgment 和 deliverable，但它没有调用模型。下一步必须让 DeepSeek 从自然用户问题开始，而不是继续把固定 Pack 或控制答案喂给模型。

本轮新增一个稳定入口 `scripts/research/run_s3_dynamic_single_cell_live.py`。它不是新的 attempt 专用 runner，后续 attempt 只更换 authority、Run/Attempt ID 和输出路径；核心执行入口不复制。

真实纵切顺序为：

1. DeepSeek 自然 planner 读取绑定的 DELL 问题，输出 planner atoms；
2. 本地编译器校验并按预算选择最多 8 个 EvidenceRequest；
3. 当前产品 `ResearchRetrievalService` 真实执行 S1 hybrid 候选检索和 S2 NumericFact；
4. 当前 reviewed Pack 只按精确 lineage 重新选择 Evidence，未审候选保持 `needs_human_review`；
5. 共用动态 Runtime 收窄 Claim／Narrative Authority；
6. DeepSeek 分别完成 thesis、mechanism、counterargument／WWC 的分析与严格交卷；
7. 本地只校验和确定性组装，不替模型写观点；
8. 完整请求、响应、参数、usage 和失败位置进入私有 capture，公开结果只保留摘要、digest 与引用。

## 工程中发现并关闭的问题

- 零调用证明原先自己拼装动态投影，live 若再复制会形成两套语义；现已抽成 `src/sec_agent/research/dynamic_research_runtime.py`，旧 formal v1.2 回放的三案业务结果和 mutation 完全不变。
- runner 最初在错误层级读取 `plan_digest`，等同于没有真正校验“本地编译计划”和“产品服务执行计划”是否一致；现改为 `controlled_plan.compiled_plan.plan_digest` 精确相等，缺失也 fail closed。
- 非思考交卷 profile 最初用错 GA validator 节点名，会在 0 调用资格检查时被拒绝；现复用 fixed-Pack 已验证的 `contract_submission_non_thinking` 节点合同，没有新建 DeepSeek 特殊分支。
- 当前 S1/S2 服务错误和 reviewed Pack 服务错误会物化为 typed terminal result，不会只在控制台消失。

## 验证

- 全仓：`379 passed`。
- compileall：通过。
- 活动图：`131 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`。
- secret scan：`6,707 files / 0 finding`。
- 当前 DELL controlled service 实测：编译与执行 `plan_digest` 相同，8 个请求，58 个 NumericFact；该检查执行本地 Qwen，不调用生成模型或外网。
- 实现提交：`db97f9bfbd7af99713a498bf89bb6c4134f26c90`，已推送。

## live 范围

范围决策只批准一次 DELL `value_capture` SEC-only 动态纵切，预算为 1 次 planner、3 次分析、3 次非思考严格交卷，共最多 7 次模型调用；0 retry、0 fallback、0 外源网络、0 candidate promotion。

`RC-S1-019` 继续保持 open：已审 Dell transcript 仍不在当前检索对象／路由中。本次禁止把 transcript 静默预喂给 S3。它可以诚实暴露“当前资料不足”，但不得因此声称五单元、高质量动态研报或 S3 已通过。

## 下一步

1. 将本范围决策与 Project OS 同步到 clean/synced 提交。
2. 执行完整 Project OS preflight。
3. 以新 Run/Attempt ID 签发唯一 authority。
4. 执行一次 live，并先做 L1 与内容质量审计；根据最早责任层决定是进入最小 S1 同步修复，还是迁移五单元。
