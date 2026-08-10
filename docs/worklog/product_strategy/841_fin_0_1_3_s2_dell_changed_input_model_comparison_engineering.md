# FIN 0.1.3 S2 DELL changed-input 模型比较工程包

- 日期：2026-08-10
- 状态：zero-call engineering pass；clean proof pending
- owner stage：S2
- run scope：`FIN_0_1_3_S2_DELL_FIXED_PACK_MODEL_COMPARISON`

## 为什么不能直接复用旧 successor

旧 successor 的用途是从旧 Pack 失败节点续跑，前五个模型节点属于旧输入。当前 corrected Pack 已由 `22` 条 Evidence 增至 `27` 条；若继续导入那五个旧节点，就无法判断 Dell/Micron 新增官方原文是否真正改善研究。新比较因此固定为全新 `13` 节点，旧模型输出只作比较基线，不进入任何新节点上下文。

工程审计同时发现，历史 Numeric authority 直接绑定 `E002/M013` 等当次排序别名。新增材料后 Evidence `E` 别名多数保持，但 Source Material `M` 别名重排；例如 Q1 FY27 业绩表从旧 `M013` 变为当前 `M024`。直接复用会把正确数字绑定到错误材料或 fail closed。这是 Harness 稳定身份缺口，不是 DeepSeek 输出问题。

## 本次实现

- 新输入先从 corrected Pack 重新编译全部 Evidence、Source Material、Gap 和当前别名；
- 历史数字声明只用来提供已经审核过的数字语义与公式，运行时先还原其稳定 `target_id/source_record_id`，再映射为本轮 E/M alias；历史 alias 本身不再拥有权威；
- Numeric authority 为 `15` 个 source-bound facts（原 13、TSMC `77%`、DELL 2026-08-06 收盘价 `437.65`）和 `4` 个本地公式；
- 单一收盘价仅是 point-in-time input，不授权估值倍数、公允价值、目标价或推荐；
- 新 case input digest=`063fbad0...f6a2`，旧 input digest=`f1f1945e...496d`，corrected Pack digest=`5ba1091d...9984`；
- fake 13 节点已得到 `13 request + 13 capture`，最大请求约 `135,111` 字符，低于 profile 的 `180,000`；旧 input digest 未进入请求，新补充的 Dell demand/backlog 与 Micron supply-tightness 对 Verifier 前所有研究节点可见；
- source/network/model/retry=`0/0/0/0`，未签发模型 authority，未产生或晋升报告。

## 验证和下一步

focused＋adjacent contract tests=`17 passed`，compile 与 `git diff --check` 通过。下一步先提交并推送当前工程包，再用两个 clean Git archive worker 只补水合两份 digest-bound private Pack，执行零模型 proof。只有 proof、Project OS、凭据存在性和容量同时通过，才签发一次 exact-once DeepSeek Pro authority；任何新 L1 或 terminal failure 都保留 capture 并停止，不自动 replacement。

