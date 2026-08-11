# 877 FIN 0.1.3 clean worktree、代码生命周期与 Workbench cutover 边界

日期：2026-08-11

## 用户要求

Owner 明确禁止删除，允许移动、归档与重构；要求先确认代码和索引是否可看清，再以 FIN 0.1.3 当前进度建立干净基线。Workbench 应成为常驻开发、测试与产品验收平台，不能继续由一次性测试/release 脚本替代。旧实现只有在新功能完成产品切换后，才能按真实版本 lineage 归档。

## 已执行

- 已把全仓只读审计提交并推送至 `codex/layered-data-source-expansion`，提交 `87a8276fcb26aafab066bd42852759cffcb41b46`。
- 已创建 `D:/FIN_Insight_Agent_fin013_rebaseline` 和分支 `codex/fin013-clean-baseline`；它是 rebaseline 工作区，不是平行 Runtime。
- 对 2,172 个 tracked Python 建立 AST 归属图；387 个 `src` 文件被分为产品、运维、CLI/MCP、release-only、test、eval 和 unknown。
- 对 Workbench 做真实 import trace，观察 173 个仓库模块；确认 canonical、FIN 0.1.2 和 `r53_r60` 三代实现仍在一个入口共居。
- 初始 Workbench 选择性回归为 74 passed、3 failed；继续追到根因是 app 把测试数据根当成代码／合同根。分离 code root 与 data root 后，这三项已关闭。
- 在 clean worktree 发现共享 registry 的 CRLF/LF raw-byte 假漂移；13 个 registry 中 7 个受影响，均可证明只是换行传输差异。
- 确认 Workbench 仍把数据根绑定到代码根；同时仓库已有 `RuntimePathRegistry` 和 `FINSIGHT_DATA_ROOT`，应提升复用，不新增路径轮子。
- 已完成共享 newline-portable resource identity、31-resource current successor、Workbench/store/local-research/job-runner 路径切换和 product-side reviewer validator 晋升。
- 已将当前 projection/reviewer 测试从 ignored `.codex_runtime` 历史 attempt 解耦；历史 materializer 保留，未删除或改写。
- clean Workbench/current product 组合回归 `143 passed`；registry／shared-ledger／historical semantics `29 passed`。
- S4 T03、三案例 T05 transfer 和 DELL fresh-proof 相邻回归分别 `19 passed`、`8 passed`，确认共享数据根切换没有只修 Workbench 而破坏检索链。
- clean worktree 显式挂载 `D:/FIN_Insight_Agent/data` 后，NVDA 本地链 terminal success：三个研究单元 `6/6/6`，总计 `18 accepted / 13 rejected`；模型、Provider、live network 均为 0。
- 发现旧 S0-02 决策在首次 Git 提交时已有 3 条 source-binding birth drift；测试现按诞生提交的 Git blob 复核并保留缺陷，不再要求当前源码永远等于历史摘要。

## 决策

- 接受五类生命周期动作：keep、promote、merge、archive-after-cutover、quarantine。
- 禁止依据文件修改时间单独决定版本归属。
- Workbench 冻结为唯一常驻产品壳和产品级测试/人工审阅表面。
- 当前先处理两个 P0：portable text resource identity 和 Workbench code/data root separation。
- 批量归档必须等待消费者为零、successor 等价、产品回归通过和 redirect manifest 就绪。
- 暂停新的 DeepSeek live；仓库和 Workbench 基线通过后再恢复 S3。

## 当前结论

第一轮 clean baseline slice 为 engineering pass；这证明 clean worktree、Workbench 当前产品面和显式共享数据根可共存，但没有把 release-only 候选自动晋升为产品，也没有授权批量归档。

## 下一项

建立 route → application service → canonical runtime → resource 的 current consumer map，先裁决 13 个 unknown 与 99 个 release-only 候选的 promote／merge／quarantine，再选择一个 S1 纵切接入 Workbench。只有 successor 产品回归与内容门通过、旧消费者为 0 后，才执行第一批 Git rename 归档。
