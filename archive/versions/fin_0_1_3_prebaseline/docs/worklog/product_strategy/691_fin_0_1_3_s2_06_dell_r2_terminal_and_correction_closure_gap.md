# 691 — FIN 0.1.3 S2-06 DELL R2 终止与 correction closure 缺口

日期：2026-08-07

状态：`R2 immutable terminal failed / shared campaign stopped / zero-call disposition required`

## 结果

用户明确授权后，在 clean/synced `85b3a8bb` 上签发唯一 DELL R2 admission 并 exact-once 消费。Supervisor、U3、U4 共 `3 calls / 3 captures`，全部 Provider transport=`ok/stop`；tokens=`11,509/1,668/13,177`，估算 `USD 0.009741`，retry/fallback=0。

SupervisorPlan v1.1 自然输出通过，证明 R1 的 RC-P36-147 非空 authority 合同漂移没有复发。运行随后在 `specialist:U4` 以 `experiment_a_unbound_numeric_surface` 形成可信 terminal；candidate/hidden score/business promotion=0，raw mutation=0，R3/MU/NVDA 均未执行。

## 共享根因

本轮不是单纯“模型又写错一个数字”。Supervisor 能看到完整 finding code/path，但交给 corrected node 的 `visible_correction_directive` 只包含 correction ID、action 和 authority aliases。U3 的 `DELL-CORR-023` 本意是修复空反证，输出仍为空反证，却被普通 Specialist validator 接受；说明运行时没有验证 assigned correction 是否关闭。

U4 的 `DELL-CORR-024` 同样没有传递“空反证”语义，输出继续为空反证；整节点重写又把方向性中个位数锐化为约 `5%`，并将只允许用于 `what_would_change` 的阈值放入其他叙事字段。后者是 DeepSeek 对明确 numeric semantics 的字段级不遵循，但项目用全节点自由重写修一个 L3 finding、又不检查 correction closure，放大了模型风险。

## 处置

登记 RC-P36-148：correction objective 语义在 Supervisor→node 边界丢失，且 post-node validator 只验普通输出合同，不验每条 correction 的关闭状态。按预注册 campaign 的共享缺陷停止规则，MU/NVDA 不启动；不得自动 R3，也不得逐字段补 Prompt 后再 live。

下一项限定为一个零调用结构处置：

- 将每条 correction 的 code、path、closure rule 与允许的 typed-unresolved 结果编译进 corrected-node request；
- 节点接受前逐条核验 correction closed/typed-unresolved，不能只通过 schema；
- 避免为局部 correction 全量重写已通过内容，或至少把重要数值表面收回 request-local alias＋本地确定性 renderer；
- 用 DELL/MU/NVDA full-fake 与 U3/U4 captured shapes 做 mutation，之后再单独决定是否还有一次项目级证明，不能自动执行。

机器结果：`configs/releases/fin_ia_0_1_3_s2_06_dell_r2_supervisor_terminal_and_correction_closure_disposition_v1_0.json`。
