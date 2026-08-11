# FIN 0.1.2 S3-T03：NVDA exact-live 有条件权限与 runner 缺口

日期：2026-08-03

## 结果

本项完成零调用权限裁决：未来最多一次当前 NVDA primary exact-live 获得有条件授权，但权限尚未生效，真实执行没有开始。本轮未读取或探测凭据，未签发或持久化 admission，未调用模型、Provider 或执行网络，也未创建业务 Run/Artifact 或写 live case head。

clean worktree 与 upstream 均绑定在 `bba8df9690742d1903fe608d5cb2279760664af0`。tracked input=`906111dd...c953`、v1.3 production binding、Pro preview Claim/WWC＋local Fact、`6 nodes / 12 logical interactions / 9 Provider calls and captures / 3 local Fact receipts / 9 success Artifacts`、9-call/60k-input/10k-output/USD 0.06/900-second/retry-zero 合同均保持。

## 为什么不能直接运行

fresh identity 复编译首先暴露了一个合同矛盾：T02 tracked `input_digest=906111…c953` 不只是业务输入摘要，其中还包含由 execution identity 派生的 Research Run 与 Artifact refs。使用本次拟定的 `fin012-s3-t03-nvda-primary-r1` 复编译，同一 case/head/source 得到 `input_digest=b9cc74…e085`。因此旧 manifest 的“完整 digest 必须匹配”与 T03 的“必须 fresh identity”目前无法同时满足。测试按真实结果失败，没有通过改断言掩盖。

T02 的失败测试证明可捕获异常返回时，执行器能够在内存中保留已完成的 local receipts 和 Provider captures，并把它们交给 Runtime 的失败终态。但本次审计确认，Provider capture 目前先追加到 executor 进程内 state，Runtime 只有在执行返回或异常传播后才统一 `FAIL_RESEARCH_RUN` / `COMPLETE_RESEARCH_RUN`。若进程在 Provider 返回后、Runtime 接管前退出，最后一份模型可见请求和 assistant 输出仍可能丢失。

仓库也没有 FIN 0.1.2 S3-T03 专用的 single-use issuer 和 supervised runner，尚未证明 timeout、supervisor exit、post-provider downstream failure 均可从耐久 capture readback 形成 typed terminal，且不会留下 orphaned Run。identity-bound input 与 durable runner 两项合并登记为 `RC-P36-106`，归 S3-T03 执行控制；它不是 DeepSeek、Provider、金融真值或 S0–S2 回归。

## 有条件权限边界

- 未来 primary formal attempt 上限仍是 1；每次调用 transport attempt=1，retry/fallback/provider hopping/prompt-only retry 均为 0。
- source network、外部工具、live case head write、失败输出业务晋升均为 0。
- 只有成功完整九件套才能进入 S3-T04；失败必须保存 request/output/receipt/capture/typed terminal 后停止。
- 当前只授权下一项零调用 runner/原子留存/终态监督 preflight；不得顺带读凭据、签发 admission 或执行 exact-live。
- preflight 通过只让 conditional authority 具备资格，仍需用户新的续行指令才可签发和启动真实 attempt。

## 产品风险提示

当前 exact input 只有价值 Cell 存在可晋升数值 Fact；需求与瓶颈 Cell 的证据不足必须诚实保持 empty-Fact/cannot-infer。这会让首版研究产品偏稀疏，但不是放宽 L1 门禁或伪造结论的理由，应在 S3-T04 作为产品质量与用户价值问题评价。

## 验证

Project OS 以唯一允许的下一 scope 运行，`status=pass / open blockers=0`。S3 StagePlan、T02 production integration 与本 T03 authority 共 `14 passed / 0 failed`；其中 fresh identity 输入连续两次复编译 byte-equivalent，并稳定重现 `906111…` 与 `b9cc74…` 不同。JSON strict parse、Python compile 与 `git diff --check` 通过。测试环境明确清除 `DEEPSEEK_API_KEY`，真实 credential/model/Provider/network 调用为 0。

## 下一步

`FIN-0.1.2-S3-T03-NVDA-FRESH-IDENTITY-INPUT-BOUNDARY-BOUND-RUNNER-ATOMIC-CAPTURE-TERMINAL-SUPERVISION-AND-ZERO-CALL-PREFLIGHT-MINIMUM-IMPLEMENTATION`

目标是在不改写 T02 历史 manifest 的前提下，分离稳定业务输入摘要与 fresh identity execution envelope，并一次性补齐执行控制与证据耐久性；不改模型合同、不扩大 Agent surface、不进入逐字段修补。
