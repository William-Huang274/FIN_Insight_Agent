# FIN 0.1.3 S3 DELL 最小 Planner Canary R1

日期：2026-08-13
状态：`terminal_failed_no_retry / business_plan_materially_valid / execution_budget_contract_failed`

## 目的与权限

本次只测试 DeepSeek Pro 能否把 DELL 开放式研究问题拆成受控 planner atoms。授权为 1 次模型调用、1 次 transport attempt、0 retry、0 fallback、0 外源检索、0 报告生成。模型无权写公司身份、截至日、来源、引用、事实或数字；S2 数据库仍是唯一精确数值权威。

## 终态

- Provider HTTP 200，finish reason=`stop`；
- exact JSON 解析通过，objective ID 正确；
- 10 个 atoms，超过本次 objective 的 8 个上限，故 `compile_research_plan` 以 `research_planner_atom_budget_invalid` 终止；
- 没有 retry、fallback、字段修补、手工裁剪或确定性 S1/S2 successor；
- token usage：prompt=1,165，completion=734，total=1,899。

## 业务审计

失败不是“模型完全不会规划”。自然输出做到：

- DELL 身份 10/10 正确，没有跨案例实体；
- 5/5 required slots 全覆盖；
- 10/10 facet 均来自允许列表；
- 所有 metric ID 均为当前 canonical ID，且与 query family 兼容；
- 需求／积压、转化持续性、当期业绩、指引、定价组合、增量利润、现金、营运资本、主体反方和上下游反方均有公司特定 intent。

直接失败只有一项：模型把每个 required slot 的两个 facet 都选入，共 10 条，没有遵守 `maximum_atoms=8`。这既是自然指令遵循失败，也暴露当前合同把“研究提案范围”和“实际执行预算”混成一个硬门。8 条上限属于成本／调度控制，不是身份、事实或数值安全；但本次 authority 已明确把它设为停止条件，因此不能追认或把 10 条手工删成 8 条继续执行。

## Capture

- 本机 capture：`.codex_runtime/model_runs/fin_0_1_3_s3/dell_planner_canary/FIN013-S3-DELL-PLANNER-CANARY-R1/ATTEMPT-01/`
- model-visible request digest：`456c70157eeda20ce83ca2f87795b8925036ad2b78cea4e47238e468ba5e49a0`
- provider response digest：`1686b3585c07776eb42b859391f2e56a20ac70099d48a2796f501e1c66cada10`
- request capture file SHA256：`58f21af657f0d043997b8e963b796bc3421ab550334d089295ba3249aca53a76`
- response capture file SHA256：`30c0f045ed35735a5e894062a8da8d753587eaf07c6330ef5898b6ba64204248`
- terminal result file SHA256：`5477d390a47d8ecb42bd13b8ffb57abdf8014fc054c52883fc4f13d1a777333f`
- 凭据、Authorization 与 provider private reasoning 均未保存。

## 下一项

不签发 R2。先做一次零模型结构处置，明确分离：

1. `proposal ceiling`：模型最多可提出多少合格研究原子；
2. `execution budget`：本地 scheduler 最终执行多少 EvidenceRequest；
3. required-slot 覆盖与 secondary facet 的确定性优先级／舍弃理由；
4. 身份、日期、来源、数值和外部调用预算继续保持硬失败。

处置后必须先做 fake/mutation 和保存响应 replay，再另行判断是否值得新的自然 canary；当前 R1 永久保持 failed。
