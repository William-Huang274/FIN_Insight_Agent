# 721｜FIN 0.1.3 S0-04G Typed Blocker State、RunScopeRegistry 与 R3 下游复证

日期：2026-08-08

阶段：`013-S0-04G`

结论：`pass`；RC-P36-156 可关闭，唯一下一项为零调用 P2D；DELL R3 仍未签发或执行。

## 1. 这次真正修复了什么

旧 Project OS 只把五个固定 `status` 字符串视为开放 blocker。描述性 `open_*` 状态会在 scope 匹配前被跳过，任意拼写的 run scope 也没有注册表校验，因此曾出现账本明明禁止、preflight 却报 pass 的 fail-open。

本轮加入：

- `BlockerState` 五态：`open / mitigated_open / blocked_external / closed / superseded`；
- `RunScopeRegistry v1_0`：canonical scope、owner stage、operation class、父子关系和可执行属性；
- 未知 state、未知或 non-executable scope、registry version 漂移、owner 不匹配、父级循环、post-adoption lineage 缺失全部 fail-closed；
- `v2_191` 以前的历史自由字符串保持不可变，只通过 exact alias 或 unknown-full-chain-open 兼容读取；
- core 与 compact preflight 同时输出 registry、scope resolution、contract errors 和 blocker count，diagnostic override 不能越过合同错误。

## 2. 实施中发现并纠正的计划矛盾

S0-04G 必须修改 `src/sec_agent/project_os_preflight.py`，但旧 P2C proof 把整个 `src/scripts/configs/runtime` 固定在 `d713eb66`。如果只宣称“旧 proof 继续有效”，新的 R3 runner 会在 Runtime-tree drift 门禁失败；如果直接排除治理文件，又会削弱既有证据。

因此没有放宽门禁，而是在同一个 S0-04G 包内增加一次有界下游兼容复证：旧 P2C 文件 SHA、v3 SourceHunter implementation bindings 全部保留，新 proof 只接受八个明确变化文件，并把 R3 successor 改绑到新 proof v1.1。这是共享合同变更的必要兼容性证明，不是另起一个产品阶段或 live Attempt。

## 3. 验证结果

- 本地 focused：`85 passed / 0 failed / 0 skipped`；
- clean Git archive＋fresh Python process：`85/0/0`；
- 其中 typed preflight unit=`12`、production scope contract=`3`、原 S1-08 suite=`70`；
- immutable restricted inputs：R1 request objects=`19`、R2 content objects=`2`，前后不变；
- predecessor P2C SHA=`fc8fd944...f443c55`；
- v1.1 proof SHA=`7ae6f46f...bd2f1e`，result digest=`e8d48fc6...a00617`；
- network/model/Provider/retry/formal admission/live=`0/0/0/0/0/0`；
- direct R3 scope 仍被 RC-P36-157 阻断。

## 4. 产品与研究能力边界

本轮只修共享权限治理。它没有提高爬取召回、增加来源、产生 Evidence、运行 DeepSeek、改善研报内容或完成用户验收。DELL 最近真实基线仍是 `16 network / 1 unique source / target-in-pool 0`。

## 5. 下一步

1. append-only 关闭 RC-P36-156，并把 RC-P36-157 投影为只允许 P2D；
2. 执行一次零调用 `S1_08_V3_DELL_R3_EXACT_LIVE_ISSUANCE_AUTHORITY_PROJECTION_DECISION`；
3. P2D 只能核对 v1.1 proof、当前 tree、运行时 contact presence、16-call budget 与 no-R4 stop rule，不能在同一项签发或执行 live；
4. 后续独立 Attempt 才能签发并执行唯一 DELL R3。若 candidate ceiling 再失败，停止 R4，转 Provider acquisition 或 Internal Alpha source-scope 产品决策。
