# 166 P38 Point 01 M5 Observability Operations

日期：2026-07-12

状态：`M5.8 deterministic temporary-store fixture pass`

`ObservabilityOpsService` 以 canonical event 为真源，提供 cursor stream、persistent trace span、threshold alert 和 admin read model。raw reasoning、prompt 和 secret 在持久化前拒绝或 redaction。专项测试与 runner `3 passed`、fixture `pass`；未调用外部 observability、worker/service、provider/tool 或下游 runtime。
