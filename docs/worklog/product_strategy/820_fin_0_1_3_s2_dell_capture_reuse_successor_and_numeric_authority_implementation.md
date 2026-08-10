# 820 — FIN 0.1.3 S2 DELL capture-reuse successor 与数字权威实现

日期：2026-08-10

状态：working-tree engineering pass；clean independent proof 待 committed/synced 运行

本项按 Owner 冻结顺序原地处理 RC-P36-169/170，没有重跑 DELL 已成功的前 5 个节点，也没有创建 FIN 0.1.4。新合同逐一校验 R1 public result、private terminal、6 份 request/response capture 和五个 usable output digest；第 6 个失败 capture 保留为审计证据，明确 `promoted_as_usable_output=false`。successor 只包含失败节点和其后 7 个节点，新增 Provider ceiling=`8`；连同 predecessor 已发生的 6 attempts，累计 ceiling=`14 attempts`，逻辑链仍是 `13 nodes`。

数字控制面新增 13 个 DELL source numeric facts、对应的原始/十亿美元/亿美元展示表面及 4 个确定性公式：AI server revenue / ISG revenue、ISG operating margin、FCF / CFO、adjusted FCF / CFO。模型可以读取并引用这些数字，但 final point 必须以 `numeric_refs` 绑定允许表面；未知值、错表面、错期间和无 ref material number 继续 L1 fail closed。Harness 只编译换算和公式，不生成 thesis 或研报段落。

successor runtime 从不可变 bundle 初始化 5 个 prior outputs，只向 Provider 发 8 个新请求；每份新响应 capture-first，receipt 同时记录 successor call index 和 logical node index 6–13。terminal 同时保存 predecessor/successor/cumulative usage、失败旧 capture、13-node materialization、same-evidence=true、same-input-pair=false 和 no-promotion。Provider failure fixture 证明只新增一次 capture 后 terminal，0 retry。

当前 focused tests=`28 passed`（核心 successor、相邻 fixed-pack、clean worker、live authority/public boundary），真实 Provider/model/network=`0`。下一步必须先提交并推送实现，再由两个 fresh process 在 scrubbed credential、socket blocked 条件下读取真实 R1 captures，分别完成 8-node fake chain并逐字节比较。clean proof 通过后才可登记 Project OS projection、签发一次 8-call authority 并执行 successor exact-live。

公平性边界：新增 numeric authority 改变 Agent model-visible digest，因此旧 direct baseline 只作诊断参考，不是 formal paired baseline。successor 成功也只能先进入独立质量审计；如内容值得正式比较，后续需另行授权一次相同增强输入的 direct baseline。
