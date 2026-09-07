# 054 DELL 动态五单元正式零调用与范围门

日期：2026-08-17

## 结论

稳定五单元 runner 已从“工程回归通过”升级为“正式零调用与 Project OS 范围门通过”。这一步没有调用 DeepSeek、没有访问外部来源、没有晋升候选、没有发布产品结果。它只证明当前实现值得从干净同步提交签发一次新的 DELL 五单元 exact-once authority。

## 本轮实际关闭的问题

1. Project OS 过去只认识 fixed-Pack 和动态单单元，不认识五单元运行。现在新增一个严格的五单元决策入口，绑定五单元顺序、13 次最大模型／传输预算、0 retry、0 fallback、0 protocol switch、0 外部来源网络和 0 产品发布。
2. 五单元 runner 的 authority validator 仍读取旧字段 `dynamic_single_cell_L1_pass`，而正式单单元验收文件的真实字段是 `dynamic_single_cell_L1`。这会让任何真实五单元 authority 在模型调用前必然失败。现已修正，并由新的 formal gate 绑定。
3. `RC-S2-004` 仍然是真的：公开资料没有形成 AI server 产品收入到公司／分部利润的权威桥。本轮没有把它假装关闭，而是只允许一次保守五单元实验；模型可以得出不可推断，但不能正向归因。
4. `RC-S3-014/015` 的历史 monolithic 上下文和推理预算问题已由片段专属上下文、分析／交卷分离和失败隔离解决到足以执行一次完整案例，但这不等于自然内容质量通过。

## 正式证明

- 两个独立 pytest 进程分别 `59 passed` 和 `59 passed`，均为 0 模型／Provider／网络调用。
- 成功路径严格为 13 个模型节点：1 planner、5 analysis、5 strict submission、1 synthesis analysis、1 synthesis submission。
- 单单元失败时，五个单元仍全部尝试；只接受合法 Judgment，并跳过必须 5/5 才可执行的综合。
- 当前 S1／S2 五单元投影为 8 个请求、8 条已审 Evidence、106 个未审候选、10 个 typed gap、0 candidate promotion；五个 cell-local context 均存在。
- 该当前检索回放加载了本地 Qwen 检索 Runtime；它没有生成式模型、Provider 或外部网络调用，但本地 embedding query 次数在这次回放中未被单独计量，不能写成 local embedding 0。
- 旧 objective ID 的 planner 输出原样复用会 fail closed；正式 live 必须执行 fresh natural planner。
- proof 绑定 runner、动态 Runtime、五单元 Runtime、consumer 和三组测试的 SHA-256，代码漂移后不能继续沿用旧资格。
- Project OS 定向测试 `21 passed`；全仓 `413 passed`；compileall 通过；活动图 `133 Python / 8 frontend / 10 Runtime resources / 0 forbidden reference`；secret scan `6,765 files / 0 finding`。

## 进入真实运行的边界

下一步先把本轮变更形成干净同步提交，再生成唯一未跟踪 authority。真实运行使用 fresh DELL objective、当前 S1/S2、五个 cell-local RoleMethodPack／GraphContextPack 和 Chat primary profile；不复用旧 planner atoms，不预塞 transcript，不从未审候选补事实。

自然 live 完成后，必须分别检查：五单元身份／期间／来源／数值／因果 L1；每个单元的研究内容；跨单元综合；完整八维质量；与前一版同事实边界的 paired gain；qualified-human 内容验收。即使 13 个节点全部成功，也不能自动宣称 S3 通过。
