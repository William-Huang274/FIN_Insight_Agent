# 811 — FIN 0.1.3 S1 residual-gap external live runner

日期：2026-08-10

状态：zero-call engineering pass；clean commit／preflight／authority pending

本轮把 12 个已冻结 SearchIntent 接入现有 capture-first 官方抓取、Trafilatura／日期解析和腾讯 SearchPro 标准版 locator。执行顺序是每家公司先抓 1 个官方 IR 发现入口；入口没有足够相关的官方文档时，才调用腾讯在允许域内找 URL；选中的官方文档重新抓取并解析。腾讯 passage、provider date 和 score 只保存在私有审计对象中，公开结果只保留规范 URL、标题、provider rank 和本地筛选分；无任何 Evidence promotion 或 Writer citation。

六案 full-fake 模拟了 6 个 discovery fetch、2 个供应侧 locator calls 和 8 个 official document fetch，共 16 个网络动作。12／12 intents terminal 为 `candidate_ready_for_local_readjudication`；off-domain locator、未来发布日期、预算漂移、authority/file binding 漂移、重复执行和系统性 Provider 拒绝均 fail closed。供应侧材料仍按 evidence owner 官方 host 限定，不能因研究主体是 DELL／NVDA 就误接任意站点。

真实网络尚未启动，凭据也未读取。相关 residual／official-source／Tencent normalizer／capture-replay 回归=`48 passed`。额外扩到已消费的历史 Tencent R4 套件时为 `53 passed / 1 stale historical assertion failed`：旧断言把当前 Project OS scope preflight 等同于一次性 execution authority；后续账本已经允许新的 S1 scope，而 R4 的重复消费仍由 immutable result／runner exact-once gate 拒绝。该历史治理测试归原 Project OS 测试债处理，不改变本轮 runner 结论，也不在 S1 外源补源中扩张修复。下一步是在 clean/synced commit 上重新运行零调用 preflight，签发一份 24 小时、exact-once、最多 30 network、0 retry／model／embedding／rerank／Evidence 的 authority；然后才执行一次 live。真实结果只生成 Candidate material，仍需 Codex 本地内容重裁决才能成为 Evidence Pack successor。

clean/synced implementation commit=`ef01fa4100cfacbb59bc1778a1547bb299dae6dd` 的 fresh preflight 已 pass，Project OS open blocker=`0`，preflight digest=`0b4177a5...cdf8`。唯一 authority=`fin013-s1-residual-external-admission-33a611a244bcaf407843` 已签发、未消费，authority digest=`06f00464...a82d`，有效期至 `2026-08-11T07:27:40Z`；签发阶段 network／credential read／Provider／model／Evidence 均为 0。下一动作只能是在 authority 与 source commit 干净同步后 exact-once 执行一次，失败不自动补跑。

唯一 live 已消费并 terminal：`17 network = 6 discovery + 5 Tencent locator + 6 official documents`，retry/model/embedding/rerank/Evidence=`0/0/0/0/0`。12 个意图全部终态，但 `candidate ready / date-or-content gap / typed gap = 0/2/10`。DELL 返回企鹅号转载与支持/登录页而非 IR；MU 选中带 Italian filter 的新闻列表/SSD 页面；NVDA 需求误选 Annual Meeting、供应查询返回驱动与第三方财经页；ORCL 退化为 Financials 首页；ASML 发现正确的 Q2 2026 results 页面却在正文抓取时失败；ANET 只抓到脚本/导航占主导的 Financial Info 外壳。Provider `site:`／多域约束没有可靠生效，generic page 的少量词重合又被浅层 selector 高估。

失败 capture 全部安全保存并与 request 绑定，但 transport failure 只保留通用 code，没有保存可审计的 safe cause class／HTTP subtype。因此本轮不能把失败猜成 timeout、TLS 或断连中的任何一种。该可观测性缺口单独登记，禁止借此自动重跑。下一项只做本地 readjudication：逐条拒绝/保留 Candidate，预计不会新增 Evidence；现有本地 Pack 和 raw gaps 保持 immutable。
