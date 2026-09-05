# Dell Q1 R2：Docker 恢复、首次模型请求失败与对象封装修复

日期：2026-09-05。阶段仍为 FIN 0.1.3 / S3 / Dell single-Specialist qualification；没有扩大到 K0–K6 或完整 multi-agent。

## 结果先行

- 工程增量：Docker 恢复；R2 的 Agent Server / PostgreSQL / Redis 三容器 healthy；一次真实运行通过了 R1 曾失败的前置身份绑定并到达模型节点。
- 真实执行证据：DeepSeek POST `/chat/completions` 恰好 1 次，HTTP 400；成功模型轮次 0，S1/S2 工具动作 0，工作底稿和报告 0。LangSmith 可查询 6 个 trace records，其中 1 个失败 LLM span。
- 根因：FIN 将 `RootModel[SpecialistAction]` 生成的顶层 `oneOf` 直接作为函数参数，缺少 API 要求的 `type: object`。不是代理、密码、模型研究能力、检索或数据缺口。
- 修复：普通 Pydantic 对象封装 `{"action": <原有封闭动作联合>}`，随后解包给原 graph；没有放松动作、context、证据、权限或终态校验。修复仅获离线证据，没有付费复验。
- 产品增量：仍无可交付 Dell 研究报告；不能把网络恢复、schema 修复或测试通过称为纵切完成。

## 1. Docker 与代理现场

Windows 系统代理为 Owner 提供的 `127.0.0.1:6696`。宿主匿名探测：Docker Hub 经代理 HTTP 401（可达），直连超时；容器匿名探测：DeepSeek `/models` HTTP 401 / 0.183 s，LangSmith `/info` HTTP 200 / 0.846 s，没有调用模型。

原 Docker API 接受本地 pipe 连接但不响应。常规重启失败后，限定范围恢复暴露了 `dockerInference`、`docker-secrets-engine/engine.sock` 不可访问。前两次目录隔离未恢复；Owner 点击 Quit 后确认 Docker 进程全部结束，再将准确的两个 runtime-only 目录改名保留、创建并检查空目录，启动成功。没有重启 Windows、改代理、恢复出厂、删除镜像/卷/业务数据。旧容器保留为 stopped，没有主动重启 R1 运行。

最终额外保留目录：

- `C:/Users/hht13/AppData/Local/Docker/run.stale-20260905-cleanquit`
- `C:/Users/hht13/AppData/Local/docker-secrets-engine.stale-20260905-cleanquit`

更早的 `run.stale-20260905-1434`、`run.stale-20260905-1436` 与 `docker-secrets-engine.stale-20260905-1436` 也保留。完整操作断点在 `D:/temp/fin_insight_r2_pre_codex_update_checkpoint_2026-09-05.md`。故障类别与 [Docker issue 460](https://github.com/docker/desktop-feedback/issues/460) 一致，但原始 API 挂起的全部原因仍未证明。

## 2. R2 唯一执行与不可变证据

- implementation baseline：`3844948327b12cc4bcafe00c10432f384ddb9402`。
- clean/pushed authority HEAD：`1f18f0febb7bd936b9efb9b90be2d7114955ebee`。
- authority：`configs/research/evals/fin_ia_0_1_3_s3_dell_q1_specialist_paid_shadow_r2_authority_v1_0.json`。
- execution：`20260905-dell-q1-specialist-paid-shadow-r2`。
- project / port：`finsight-dell-q1-paid-1c0ac6399a3c` / `18173`。
- server thread：`9ba89479-178c-5f50-b559-cb7fe19c4a13`。
- server run / LangSmith root：`01a07055-b8b5-73e0-8f25-8c1b937fdfee`。
- LangSmith LLM span：`01a07055-d584-75c0-84cd-0100cf3e8f0e`，project `fin-insight-dell-reference-vertical`。
- artifact root：`Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/q1_specialist_paid_shadow/attempts/20260905-dell-q1-specialist-paid-shadow-r2/`。

`failed-receipt.json` SHA-256：`950952f6b8fa0b3795cba6fb96814989f6d19799153009071d63fd976787e813`。
`model-call-events.jsonl` SHA-256：`83f2d9c7a6f53c09736e166931a6b4d360afbfbc8c6523d9b934df4cb4aa7778`。
R1 receipt SHA 仍为 `71796ef16d1a122368619b34a7c7f1308fa9c67701d67dac91723ebe5ca24c20`，未覆盖。

Compose build/up 200.516 s。首次模型语义输入 12,643 字符 / 12,789 UTF-8 bytes；DeepSeek V4 Pro，thinking disabled，max output 10,000 tokens，单次超时 240 s，无 transport retry。调用 385.449 ms 后被请求校验拒绝；`usage_available=false`，没有可报告的实际 token 或账单金额，不能将未知费用写成已核实的零。

只读 state 显示 `phase=ready_for_model_decision`、accepted model turns=0、tool actions=0、observations=0、`next=[model_decide]`、interrupts=0，remote run=`error`。外层 runner 因非合法终态报告 `paid_shadow_terminal_state_invalid`；这是下游症状，真正原因由 LangSmith 原始错误确定。

## 3. 根因及最小修复

修复 commit：`0c798101d7a14ff2b228fbc5c52e740ff20e60ae`。它不是 R2 运行时所用的 image/code baseline；后续付费资格必须重新绑定修复后的代码。

DeepSeek 原文：`Invalid schema for function 'SpecialistActionPayload': schema must be a JSON Schema of 'type: "object"', got 'type: null'.`

旧测试只检查动作名称、字段披露与解析，没有检查真实函数参数根类型；因此 scripted MCP qualification 不能证明 live provider 请求合法。已有成熟 LangSmith trace 找回了原始错误，不另建诊断平台。

修改仅位于 `src/sec_agent/agent_runtime/deepseek_structured_agents.py`：

1. `SpecialistActionPayload` 改为普通严格 Pydantic 对象，唯一字段 `action` 仍使用原 `SpecialistAction` 联合。
2. Prompt 明确这个对象外壳；live 返回与 saved-response replay 在适配边界解包，graph 输入和 receipt 输出摘要仍绑定原动作。
3. 不改 MCP 工具、资料范围、runtime 身份、SQL、预算、Provider SDK、重试或工作流。

## 4. 针对性验证与停止线

先新增根类型测试，在旧代码上得到 `1 failed`，准确复现 `None != object`。修复后运行：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_dell_deepseek_structured_agents.py tests/test_dell_specialist_agentic_composition.py tests/test_dell_specialist_agentic_graph.py tests/test_dell_specialist_paid_shadow.py tests/test_dell_q1_specialist_paid_shadow_runner.py -q
```

结果：`67 passed in 14.30s`。新增覆盖 object 根类型、四动作封闭联合、拒绝额外 runtime receipt/非法 action/坏 context digest，以及真实 ChatDeepSeek/OpenAI SDK 经 `httpx.MockTransport` 的请求序列化和响应解析。该测试使用假 key、关闭 tracing、无网络，是离线 transport fixture，不是第二次 DeepSeek 运行。

两处 Python compile、diff whitespace check、最新 ledger/postmortem JSON 解析和候选文件 secret-literal scan 通过。

没有重跑全仓测试、没有再次 build/up R2、没有 retry/resume/fallback，没有 R3 authority/execution，没有独立 reviewer 的新增结论。原 R2 image/container/receipt 不修改。修复撤销范围仅为 adapter 和对应测试；后续新运行必须从修复后的 clean/pushed baseline 使用新身份和新的 Owner 单次授权，不能重用 R2。

下一项真实产品工作仍是让同一 Q1 Specialist 完成真实工具决策与来源绑定底稿，然后才扩展 Lead、并行 Specialists、Counter、Verifier；本修复不改变这一完成定义。
