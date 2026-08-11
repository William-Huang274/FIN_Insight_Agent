# FIN 0.1.3 S1 Dell official-source recovery fresh authority

- 日期：2026-08-10
- implementation commit：`7663afb20f0d1a05cb89f6c33974687edee937d4`
- run：`fin013_s1_dell_official_recovery_93f80e015a85e086ee57`
- authority digest：`76be7744478f3c0e50896965fe8c9a03f53f3dafd183e34a2edac7ec6135140d`
- expires：`2026-08-11T14:15:29Z`
- 当前状态：issued unconsumed

## 权限边界

本 authority 精确绑定 policy、clean proof、runner、source compiler、official transport、object store 与 shared admission ledger。它只允许：

- Dell Q1 FY27 official transcript exact URL 经 managed reader 一次；
- Micron Q3 FY26 official Prepared Remarks exact URL 经 managed reader 一次；
- capture-first 保存完整中介响应，再由本地规则裁决；
- 总 network ceiling=`2`、每路 timeout=`45s`、retry/model=`0/0`。

它不允许重抓 Alpha Vantage、TSMC 或旧 predecessor，不允许 broad search、自动 replacement、推荐、业务 Artifact 晋升或 release。Project OS preflight=`pass／0 blocker`；签发过程没有网络或模型调用。

## 下一步

提交并推送 authority 后，runner 先在 clean/synced branch 做 file binding、proof、expiry、Project OS、attempt-root 和 exact-once ledger 预检。通过后只消费一次。若 Dell 三个片段未全部 materialize，`core_research_ready=false` 并停止；不能另签第二份 authority 自动补跑。
