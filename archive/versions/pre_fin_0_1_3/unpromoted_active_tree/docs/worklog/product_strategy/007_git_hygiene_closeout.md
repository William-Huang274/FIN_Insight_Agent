# Git Hygiene Closeout

日期：2026-06-28

## 范围

用户要求做一次 Git hygiene closeout，目标是在不漏已实现功能和文件的前提下，把长期累计的代码、脚本、测试、文档和可审计 JSON manifest 收口到当前分支。

本次 closeout 覆盖：

- R12-R49 累计的数据源扩容、L1/L2/L3 source lanes、exact slot、ProductIntelligenceGraph、Research Graph、RD0-RD7 数据底座、第二/第三层 acceptance gates、AI/Semis ProductEvidencePack 和 agent runtime wiring。
- R50-R53 产品/技术文档治理、B2B workbench PRD、collaborative agent graph、25 文档归档吸收、R53-R60 program 执行总控。
- 对应 `src/`、`scripts/`、`tests/`、`docs/` 和 `data/manifests/*.json` 合同型 summary/gate/registry/matrix 文件。

## Git Hygiene 决策

1. 不使用 `git add .`，按目录和文件类型精确 stage：
   - `.gitignore`
   - `docs/`
   - `src/`
   - `scripts/`
   - `tests/`
   - `data/manifests/*.json`
2. 新增 `.gitignore` 规则，忽略大规模 runtime row dumps、attempt ledgers、lineage JSONL、临时 `_tmp_*` 和 run logs。
3. 保留 JSON summary/gate/registry/matrix 进入 Git，因为这些文件是后续 deterministic tests 和 release audit 的合同输入。
4. JSONL 明细数据保留在本地工作区，不进入本次 Git commit；既有已跟踪 JSONL 不受 ignore 规则影响。
5. 本轮不重写历史、不 revert 用户或前序线程变更，只做 closeout 级别的最小修复。

## Closeout 修复

- 修复 `R26` second-layer acceptance gate 对 ProductRelationshipGraph summary 旧计数字段过度依赖的问题：gate 现在会从 `company_product_slots_v0_1.jsonl` 的真实 `family_id/family_name` 和 locator fields 补充判断。
- 修复 V1 source coverage closeout 兼容默认：V1 lane 在缺省 `industry_schema` 时按 `semiconductors_hardware` 运行，避免退到 generic schema 后漏掉 `technology_research_proxy` 等 V1 requirement。
- 清理一个旧 `__pycache__` permission 问题，避免 `python -m compileall` 被历史 `.pyc` 文件阻断。

## 验证

- Secret scan：覆盖 `src/`、`scripts/`、`tests/`、`docs/`、`data/manifests` 和 `.gitignore`；只发现 env var 名称、redacted/unit-test examples 和代码标识，没有真实密钥。
- `git diff --cached --check`：通过。
- `python -m compileall -q src scripts`：通过。
- 先跑失败修复回归：`tests/test_r26_layer_acceptance_gates.py` + `tests/test_v1_source_coverage_closeout.py`，`4 passed`。
- Staged test set：当前 staged 的 `106` 个 test files 全部通过，`844 passed`。

## 后续规则

从 R53 之后恢复小切片开发：

1. 每个 release slice 先写需求单和 gate。
2. 代码、脚本、测试、docs、generated contracts 分组 stage。
3. 大规模 runtime 明细进入 artifact/object store 或本地 ignored 区，不直接进 Git。
4. 每轮 closeout 必须记录 dirty status、secret scan、diff check、compile/test 结果和未提交缺口。
