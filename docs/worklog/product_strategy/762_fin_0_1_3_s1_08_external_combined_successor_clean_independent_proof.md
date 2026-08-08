# 762 — FIN 0.1.3 S1-08 external combined successor clean independent proof

日期：2026-08-09

## 结果

clean/synced commit `3aa510d386c8a2e9bebe576cfa0f6986025cc9de` 已在两个独立 Git archive、两个 fresh Python process 中复证：

- 每份 archive 的 successor 专项测试均为 `14 passed / 0 failed`；
- 两份 archive 都重新运行 zero-call materializer；
- 重物化 plan SHA 均为 `3add3a9a...01cc03`，proof SHA 均为 `15ccbd3c...040e`；
- 两边结果互相相同，也与 commit 中不可变文件相同；
- provider／network／model／document／Evidence／embedding／rerank／admission=`0`。

临时 archive 保留在 `.codex_runtime/fin013_s1_08/external_combined/clean-proof-8c5d67cc17`，该目录被 Git 忽略，不是产品输入或正式证据位置；正式证据是受 Git 管理的 clean-proof JSON。

## 处置

v1.1 successor 由 working-tree engineering pass 晋升为 `clean_independently_proven`。这仍不代表 official route 已重新到达来源，也不代表 Firecrawl 额度恢复；本项不签发 admission，不执行 live。

下一项限定为 `S1_08_EXTERNAL_COMBINED_RECOVERY_AUTHORITY_DECISION`：只判断是否基于本 proof 签发一次有界 recovery authority。内源 exact／BM25／dense／graph、qrels、BGE／fusion／rerank 仍按已冻结顺序排在外源 closeout 之后。
