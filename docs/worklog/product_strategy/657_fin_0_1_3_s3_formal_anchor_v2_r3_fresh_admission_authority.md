# FIN 0.1.3 S3 formal Anchor v2 R3 fresh admission authority

日期：2026-08-06

## 结论

R3 的零调用入口审计通过，正式授权一个、且只有一个 fresh clean-head admission。尚未签发 admission，也没有发生模型、Provider、网络、来源或业务写入。

## 为什么现在可以再跑一次

- R2 的第五项失败已定位为本地“上游没有 gap 选项时无法表示诚实 cannot-infer”的合同缺陷，并已在 S3 原地修复；R2 本身保持失败，不改写、不重放。
- 项目 OS preflight 在 `R3_fresh_admission_authority_decision` scope 下无 override 通过，没有未处理 blocker 阻止本次有界决策。
- 九个请求仍是同一份 S1 governed Evidence Pack 经 S2 编译出的 source-frozen context；R3 不访问 SEC/IR，不重新检索，不把来源波动引入本轮。
- context 合计 24,586 字符，单项最大 4,202；调用数固定为 9，每项一次，输出最多 900 tokens，retry/fallback 均为 0。
- 同一 DeepSeek Pro 路由近期已有一次 v2 canary 和 R2 的五次 transport success。R2 是本地验证失败，不是连通性失败，因此不再额外烧一次 token 做重复 provider probe。

## 权限边界

- 只允许一个 R3 admission；最多 9 次 Provider 调用。
- 首个可信失败立即停止，并先保存 raw capture、parsed raw output 与 terminal result。
- 不自动签 R4，不做逐字段 live 修补循环。
- 只有 R3 九项全部成功，才可在零模型本地编译 Claim、Lead、Workpaper，并执行独立 L1/L2 与八维质量评估。
- 预算、连通性和结构测试通过，不等于产品内容质量、paired gain、qualified-human acceptance、S3 product proof 或 release。

## 证据

- `configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2_r3_fresh_admission_authority_decision_v1_0.json`
- `configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_v2_r3_authority_active_test_suite_successor_v1_0.json`
- `configs/releases/fin_ia_0_1_3_repair_closeout_s3_gapless_local_default_and_raw_terminal_disposition_v1_0.json`

下一步：提交并同步权限记录，然后签发并消费唯一 R3 admission。

## Preflight 测试命令更正

第一次 canonical 启动误把目录级 `tests/contract` 当成当前版本 suite，收集了 3,190 项历史合同，运行约 20 分钟后有界终止。该次没有测试失败，也没有进入 R3；它不计作 current canonical。当前 FIN 0.1.3 suite 的权威范围是 active suite 中冻结的 29 个文件、249 项测试，并单独 deselect 一条历史 event-time assertion。后续只按该权威集合执行。
