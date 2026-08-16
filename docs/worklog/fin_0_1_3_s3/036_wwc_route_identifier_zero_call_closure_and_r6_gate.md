# FIN 0.1.3 S3 WWC 来源路线字段零调用闭环与 R6 gate

## 本轮目标

不删除或改写 FFJ-R5 的自然模型输出，在最早责任层修复 `10-Q` 被全局 no-digit 规则误判的问题，并证明修复没有放宽财务数字、引用、身份、因果或跨案例边界。

## 实际修改

1. `current_consumer` 新增 WWC `evidence_route` 专属校验器。它只识别 reviewed source policy 中注册的完整官方文件类型标识；允许清单由同一 policy 约束，policy 漂移会 fail closed。
2. thesis、mechanism、counterargument 等判断正文继续使用原有严格 no-digit／no-verbal-numeric 规则，没有获得表单编号例外。
3. 零调用 runner 绑定 FFJ-R5 result、failure assessment 与三份 submitted fragments，原样重建 Claim Authority、终态 Judgment 和 deliverable。
4. Project OS preflight 与 exact-live authority validator 新增 R6 successor 类型，明确绑定 R5 不可变失败、v1.6 proof、同一 Evidence Pack、同一 DeepSeek profile 和零重试预算。

## 复证结果

- clean implementation commit：`ac80d80498d1e8f60b8472efbf001c4775b7e006`。
- formal authority SHA：`6219dfce2c10c3dd9e22cd1a35024cc36ceff0c61f1b5c9fad2b975a319cbb3c`。
- formal result SHA：`6ce0899e49c5dbb42036d3febcc977506be0ee47c1f93bf2da29655941e4a252`；result digest：`d7667e8467c1195f2b80ba1bc73bec1527348dc86dbc7397f0be860e020b526f`。
- R5 原文回放终态 digest：`b8f09b70c95417c09588cdb09ea0535bea33efb238702c1ab41dc94607f94b80`；deliverable digest：`0993061bf295c83053779e1e3f78518cc047a1bb811cd637cf78f0eb63f106cf`。
- 两个 fresh process 字节等价；DELL／MU／NVDA full-fake 全通过，identity 与 Graph pollution 均为 0。
- `20%`、`2027`、未知 `12-Z`、URL 及判断正文中的 `10-Q` 全部 fail closed。
- 定向 gate 测试 `35 passed`，全仓 `355 passed`，compileall、active baseline `127／8／10／0` 与 secret scan `6,672／0` 通过；模型、Provider、网络、embedding、retry 和产品发布调用均为 0。

## 产品判断与边界

这次证明的是 R5 的失败属于本地字段职责混淆，而不是 DeepSeek 不遵循合同或金融判断越界。proof 不追认 R5，也不证明 fixed-Pack Layer One 已通过。下一步只允许在 clean push 与真实 preflight 后签发一个全新 FFJ-R6；R6 成功后仍需独立 L1、八维内容质量和 paired 验收，之后才能进入动态 Research Truth Spine。
