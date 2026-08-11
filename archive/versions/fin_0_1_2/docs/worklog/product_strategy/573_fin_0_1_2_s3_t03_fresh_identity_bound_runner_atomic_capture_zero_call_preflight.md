# FIN 0.1.2 S3-T03：fresh identity、capture-first runner 与零调用 preflight

日期：2026-08-03

## 结果

本项按既定边界完成，`RC-P36-106` 已在其所属 S3-T03 内关闭。没有改写 T02 历史 manifest，没有读取凭据、签发 admission、调用 DeepSeek/Provider/执行网络，也没有创建业务 Run 或 Artifact。

旧 T02 与新 T03 的完整 input digest 分别是 `906111…c953` 与 `b9cc74…e085`，差异来自 execution identity 派生的 WorkUnit/Attempt/Run、branch、context、graph 与 Artifact lineage。新增稳定业务投影只归一化这组实证字段，继续硬绑定 query、case/head、decision surface、accepted evidence、numeric input、Lead/Writer/Verifier 与 hard boundaries；两份投影 digest 均为 `a19743…4fc`，真实业务 mutation 会改变 digest。

## Runner

专用 runner 绑定 fresh envelope `5f0485…37f7`、v1.3 contract、单次身份和 `9 calls / 60k input / 10k output / USD 0.06 / 900s / retry 0`。它复用 S2 已有的内容寻址原子对象存储，不再造第二套证据后端。每个 final assistant output 连同完整 model-visible request、usage、finish reason、latency、transport count 和 allowlisted 参数先写 restricted capture，再交给本地 parse/validator。

凭据值、`api_key_env`、Authorization、Cookie、raw Provider response 与 private reasoning 永不进入 capture。成功链才返回 9 个非 canonical fake Artifacts；任何失败都清空业务 Artifact、生成 typed terminal 并阻止 promotion。capture store 自身不可用时不会伪称证据完整，而是写原子脱敏 execution-result 后 fail closed。

supervisor 不只读取 capture index，还会扫描受限内容寻址 namespace；因此子进程死在“capture 已落盘、index 尚未更新”的窗口时，最后一份 capture 仍能 readback、校验并进入 supervisor-exit terminal。

## 验证

成功、Lead validation failure、malformed first output、timeout、capture-store failure、abnormal child exit、index lag、budget mutation、single-use replay、envelope mutation 以及 query/evidence/numeric mutation均已覆盖。两个清除 API credential 的 fresh Python process 逐字节复现同一 envelope。T02 production、T03 authority 与新 runner applicable regression 共 `19 passed`。

本项只证明执行控制已具备签发资格，不是自然 DeepSeek 行为、current NVDA 九件套、R2、paired gain、Owner acceptance、release 或 production。

## 下一步

`FIN-0.1.2-S3-T03-NVDA-FRESH-EXACT-ADMISSION-ISSUANCE`

新的用户续行后，只签发一份逐字节绑定 fresh envelope 的 admission；签发不消费 execution identity、不调用模型。真实 exact-live 仍作为后续单独受监督动作。
