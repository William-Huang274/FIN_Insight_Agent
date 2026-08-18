# 051 S1 当前 Pack 消费者 lineage 统一

日期：2026-08-19

状态：`current_pack_retrieval_evidence_workbench_consistent / historical_vertical_preserved / S1_qualified=false`

## 晋升后暴露的真实集成问题

三案例当前 Pack 已经成功升级，但 Workbench 的 Evidence 页面读到新 Pack，Retrieval 页的 canonical spine 仍投影旧 VS4 supplement。用户会同时看到“29 条 DELL Evidence”和“旧纵切只生产 22 条”的两套当前事实。根因是 Pack 指针与 lineage 投影分别维护；旧 VS4 是合法历史记录，却被消费者继续当成当前 Pack 生产者。

## 修复

- 在 `src/retrieval/product_evidence_successor.py` 建立共享的 current successor lineage 投影；
- Evidence Pack 与 Retrieval 两个后端服务都读取同一 current Pack、ProductReadiness 和 successor binding；
- 旧 VS1／VS4 只保留为 `historical_vertical_lineage`，明确标记 `not_current_pack_producer=true`，不改写历史结果；
- Pack artifact、payload、ProductReadiness、case、digest 或 authority 任一漂移均 fail closed；
- Workbench 的“已接受 Evidence”改为当前精确绑定 reviewed Evidence 数量，不再把候选决策数误标成 Evidence；
- 当 successor 没有对旧纵切做等价召回复证时，“既有证据未召回”显示为“未复证”，而不是伪造一个 0。

## 复证

- Python 全仓：`780 passed`；
- TypeScript 类型检查与 Vite production build：通过；
- compileall、active baseline：170 Python／8 frontend／26 Runtime／0 forbidden；
- secret scan：7,304 files／0 findings；
- `git diff --check`：通过；
- 网络、模型、Provider、新向量执行：0。

## 下一责任层

Pack 晋升、候选追踪、Evidence 决策、产品就绪结果和 Workbench 消费已经成为同一条当前产品主线。S1 仍不能关闭：最早内部缺口转到请求级来源路线——行业、官方 IR、外源搜索等 source-role 需求还没有自动编译到可执行 adapter，也没有形成 requested／available／executed／exhausted 的同一收据。只有真实执行并穷尽的路线才有资格参与公开信息 gap 判断。
