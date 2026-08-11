# FIN 0.1.2 S3-T03：bound launcher、parent supervisor 与零调用预检

日期：2026-08-03
状态：`engineering_pass / admission issued-unconsumed / exact-live not authorized`

## 本轮结论

用户以“授权继续”授权了唯一一个 S3-T03 零调用连接包。`RC-P36-107` 已关闭：现有 capture-first runner 不再只有库函数，而是接入了一个 admission-bound child command 和一个真实 parent launch/wait/timeout/exit supervisor。

这不是产品 run。当前 NVDA exact input 仍是内部 frozen dogfood fixture；没有产生自然 DeepSeek 输出、九件套、paired assessment、Owner acceptance 或当前 NVDA R2。

## 实现

- `apps/workbench/backend/application/fin_0_1_2_s3_t03_exact_live_runner.py`
  - 新增父进程原子 claim；
  - child 只允许把 exact matching `supervisor_claimed` 转为 `execution_claimed`；
  - 第二次 parent、unsupervised replay 或重复 child transition fail closed。
- `scripts/releases/run_fin_ia_0_1_2_s3_t03_nvda_supervised_exact_live.py`
  - 从 immutable issuance/manifest 重建 exact target；
  - 不导入测试 helper，使用生产 Case/Evidence/Research services 重建 frozen input；
  - child 内装配现有 DeepSeek gateway，强制 `max_transport_attempts=1`；
  - parent 只启动一个直接 child，记录 launch/exit receipt、stdout/stderr digest，执行 timeout/kill 和缺失 terminal 自动恢复；
  - `Popen` 或 launch-receipt 失败时终止已启动 child，并把已 claim identity 自动终态化；
  - `preflight` 模式启动真实本地 child，但 Provider callback=0；
  - `supervise` 模式必须加载之后单独签发的 execution-authority 文件，否则在 claim 前拒绝。

## 历史绑定处置

已签发 issuance 不可改写，其 zero-call proof 绑定签发时 runner SHA `fc09ffde…31c4a`。本轮 runner 因新增 parent-claim/child-transition 而变为 `449e5e6b…42869`。没有修改旧 issuance；新的 implementation record 明确登记受控后继关系，并要求未来 execution authority 同时绑定当前 runner 与 launcher SHA。

## 验证

- Python compile：pass。
- 新专项：`10 passed`。
- T02 production integration：`2 passed`。
- T03 conditional authority：`6 passed`。
- T03 fresh identity/capture-first runner：`11 passed`。
- issuance＋新监督器组合：`18 passed`。
- post-admission historical decision：`6 passed`。
- 新监督器、issuance 与 historical decision 组合：`24 passed`。
- CLI preflight：真实本地 child=`1`；exact input rehydrated=true；Provider callback/model/Provider/network=`0/0/0/0`；target runtime 前后 absent。
- fault injection：process launch failure、child exit 17 与 parent timeout 都自动物化 typed terminal；retry/fallback/replay/relaunch=`0/0/0/0`；凭据值不在日志、receipt 或结果中。

首次组合回归在 184 秒外层超时被工具终止，没有测试失败；随后按文件拆分后发现唯一失败是旧 issuance 测试把历史 runner SHA 当作永远等于 current bytes。该测试已改为同时保护旧字节不可变和受控后继存在，不放宽 runtime gate。

## 持久状态

- implementation：`configs/releases/fin_ia_0_1_2_s3_t03_nvda_bound_execution_launcher_parent_supervisor_zero_call_preflight_minimum_implementation_v1_0.json`
- current projection：`configs/runtime/fin_ia_0_1_2_current_program_projection_v2_27.json`
- admission：issued=true / consumed=false / execution=false
- target runtime root：absent
- model / Provider / execution network / business Run / Artifact：`0 / 0 / 0 / 0 / 0`
- `RC-P36-107`：closed
- S3-T03：executable supervised path engineering pass；execution 未开始

## 下一步

`FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AUTHORITY-DECISION-R2`

下一项只做零调用权限复核；不能同轮消费 admission 或调用 DeepSeek。权限通过后，真实 exact-live 仍需新的用户续行。
