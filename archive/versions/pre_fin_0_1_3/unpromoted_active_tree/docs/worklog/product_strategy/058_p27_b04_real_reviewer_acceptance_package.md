# P27 B04 Real Reviewer Acceptance Package

## 背景

P24/P26/P25 已把 B04 之外的主要技术 blocker 收敛掉，B04 目前不是“还缺自动化 gate”，而是确实需要真实 reviewer 完成产品验收。057 已经把 evidence 写入入口接到 Workbench，但 reviewer 仍缺少一份可执行验收包：要审什么、按什么顺序审、哪些 source id 要 closeout、哪些 task/artifact/trace 可以作为引用。

本轮目标是生成 P27 支撑包，让真实 reviewer 可以直接进入 Workbench 执行，而不是在 SQL/manifest 中人工找线索。

## 完成内容

- 新增 `src/sec_agent/r53_r60_b04_reviewer_acceptance_package.py`
  - 读取 P24 summary、human evidence requirements、defect closeout requirements。
  - 读取 runtime SQLite 中的 task / artifact / trace candidate refs。
  - 输出 reviewer step rows、template-only evidence rows、candidate refs 和人读报告。
  - 明确 `does_not_close_b04=true`，不写真实 reviewer evidence ledger。
- 新增 `scripts/engineering/build_r53_r60_p27_b04_reviewer_acceptance_package.py`
  - CLI 入口，支持传入 Workbench URL。
- 新增 `tests/test_r53_r60_b04_reviewer_acceptance_package.py`
  - 验证 P27 只生成 template-only rows。
  - 验证 template rows 不能被 `validate_real_reviewer_acceptance_evidence` 当成真实 evidence。
  - 验证 P27 不创建 P24 real reviewer evidence ledger。

## 运行结果

真实仓库构建：

- `package_status=ready_for_real_reviewer_execution`
- `b04_status_after_p27=open_product_acceptance_required`
- `human_evidence_requirement_count=5`
- `defect_closeout_requirement_count=8`
- `evidence_template_count=13`
- `review_step_count=5`
- `reviewer_candidate_ref_count=36`
- `real_reviewer_evidence_row_count=0`
- `full_chain_broad_eval_allowed=false`

生成产物：

- `data/manifests/r53_r60_p27_b04_reviewer_acceptance_package_v0_1.json`
- `data/manifests/r53_r60_p27_b04_reviewer_acceptance_steps_v0_1.jsonl`
- `data/manifests/r53_r60_p27_b04_reviewer_acceptance_evidence_templates_v0_1.jsonl`
- `data/manifests/r53_r60_p27_b04_reviewer_acceptance_candidate_refs_v0_1.jsonl`
- `docs/internal/vnext_20260610/r53_r60_p27_b04_reviewer_acceptance_package.zh-CN.md`

## 验证

- `python -m pytest tests/test_r53_r60_b04_reviewer_acceptance_package.py tests/test_r53_r60_product_acceptance_b04_gate.py tests/test_r53_r60_pre_full_chain_blocker_gate.py -q`
  - `11 passed`
- `python -m py_compile src/sec_agent/r53_r60_b04_reviewer_acceptance_package.py scripts/engineering/build_r53_r60_p27_b04_reviewer_acceptance_package.py tests/test_r53_r60_b04_reviewer_acceptance_package.py`
  - pass
- `python scripts/engineering/build_r53_r60_p27_b04_reviewer_acceptance_package.py --root . --workbench-url http://127.0.0.1:18080`
  - pass

## 边界

P27 不是产品验收完成，也不是 broad full-chain release gate。它只解决“真实 reviewer 如何执行 B04 验收”的操作性问题。B04 仍必须等真实 reviewer 通过 Workbench/API/CLI 录入完整 evidence 后，再重跑 P24/P21 才能关闭。
