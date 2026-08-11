# FIN 0.1.2 S2-T03 bound runner、原子 capture 与零调用 preflight

日期：2026-08-03
状态：`engineering pass / zero-call preflight pass / exact six-call authorized not started`

## 本轮完成

实现了 T03 专用 paired-canary runner，不修改 authority 已冻结的模型可见 compiler。runner 从 T03 RuntimeResourceRegistry 登记的 MU exact fixture 和 authority 读取输入，使用生产 `S3ThreeCellBoundedAgentInputPack` 与 numeric authority adapter 重建 compiler，并逐项匹配六个 call ID、model ref、request digest 与 equivalence digest。

共享 `FileCanonicalObjectStore` 改为同目录临时文件写入、flush/fsync、`os.replace` 与落盘 digest readback；已有相同对象也必须重新验证 digest。runner 在任何本地 semantic validation 前先把完整模型可见请求与最终 assistant text 写入受限内容寻址对象仓，随后才调用原 compiler materializer，并独立保存 terminal result。凭据、Authorization/header、Cookie、raw Provider envelope 与 private reasoning 不保存；execution summary 只含 digest/ref/status/usage。

`chat_completion` 新增向后兼容的显式 `max_transport_attempts`，T03 固定为 1，因此不会被全局 retry 环境变量扩大。execution identity 使用 exclusive create，重复运行会在 Provider 前拒绝。

## 验证

- focused runner/gateway/object-store 实现证据：`28 passed / 0 failed`；加入结果/投影闭环断言后最终 `30 passed / 0 failed`；
- T02 compiler、MU fixture、资源注册表、runner、gateway、object-store 组合实现证据：`61 passed / 0 failed`；加入闭环断言后最终 `63 passed / 0 failed`；
- Python compileall：pass；git diff check：pass；
- 六调用 fake：6 capture、6 terminal，且事件顺序逐调用均为 capture→validation；
- 首调用语义失败：记录失败并继续其余 5 个；
- 首调用 transport 失败：先保存 capture/terminal，再停止其余 5 个；
- capture、预算和重复 identity：fail closed；
- raw envelope marker、Authorization 与模拟 secret 不落盘；
- zero-call preflight：六个 digest 全匹配，最坏主成本估算 `USD 0.029058 < 0.06`。

credential/model/provider/network/business Run/Artifact=`0/0/0/0/0`。本轮没有测试 Flash 或 Pro 的自然能力，也没有选择主线模型。

## 问题处置与下一项

`RC-P36-101` 已按专用 runner、原子 capture-before-validation、typed terminal、显式单次 attempt 与 fault-injection 证据关闭。它从始至终是项目执行准备缺口，不是模型或 Provider 故障。

既有条件 authority 现已生效，当前唯一下一项为：

`FIN-0.1.2-S2-T03-MU-FLASH-STABLE-VS-PRO-PREVIEW-PAIRED-NATURAL-OUTPUT-CANARY-EXACT-SIX-CALL-EXECUTION`

执行只允许六个主调用，无 retry/fallback/provider hopping/prompt-only retry、无自动 replacement pair、无业务 Run/Artifact。六个 terminal/capture 完成或诚实 transport block 后才进入 T04。
