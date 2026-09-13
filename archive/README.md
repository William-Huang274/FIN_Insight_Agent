# Historical source / 历史源码恢复

FIN 0.1.3 的一次性实验、淘汰实现和原 `archive/versions/` 文件已于 2026-09-13 清出当前代码树。历史未删除或改写；运行时不得依赖归档。

The active tree contains maintained product code. Retired experiments and the former archive tree are preserved in Git history, outside the current source tree.

- Immutable commit: `7b8287ab6c4d0af5dec82800f3fd2fa9ef0d4773`.
- Archive tag: [`archive/fin-0.1.3-before-cleanup-20260913`](https://github.com/William-Huang274/FIN_Insight_Agent/tree/archive/fin-0.1.3-before-cleanup-20260913).
- [Retention policy and changes / 清理说明](../docs/architecture/repository/frozen_cleanup.zh-CN.md).
- [Verified removal manifest / 核验清单](../docs/architecture/repository/frozen_cleanup_manifest.json).

Use a separate directory to inspect or replay old code:

```bash
git fetch origin tag archive/fin-0.1.3-before-cleanup-20260913
git worktree add --detach ../FIN_Insight_Agent-frozen-013 7b8287ab6c4d0af5dec82800f3fd2fa9ef0d4773
git show 7b8287ab6c4d0af5dec82800f3fd2fa9ef0d4773:scripts/data_retrieval/run_dell_report_internal_chain_ceiling_r13.py
```

旧工作日志中的相对路径按该日志的原提交解释；恢复后的资格脚本可能需要原始私有数据、当时依赖和单独调用授权。不要在当前工作区复制回来批量执行。标签不含私有数据、凭据或本机运行状态，也不是生产 release。

The archive is a source snapshot, not a runnable private-data bundle or production release. Historical failures remain failures. External archival copies were checked against the original Git blobs before removal; hashes are recorded in the manifest.
