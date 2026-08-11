# FIN 0.1.2 S3-T02：NVDA 生产 Runtime 接入与零调用产品就绪

日期：2026-08-03

## 结果

S3-T02 已工程通过，未访问凭据、未调用模型或 Provider、未执行真实网络、未写业务 Run/Artifact 或 live case head。RC-P36-105 已关闭到生产接入层；S3-T03 exact-live 仍未授权。

本轮没有改写 S2 v1.2 或 S1 历史 `6/12/12/9`。新增独立 v1.3 source/binding、v9 specialist transport、当前 NVDA v4 Fact candidate profile、tracked exact input manifest 和内容寻址 resource registry。production admission compiler 原子绑定 v4 profile、v9、Claim/Task/WWC、数字/identity、Lead v6、Writer v3、capture-v2 和 9-call/10k-output/USD 0.06 上限，避免调用方依赖一个偶然“够新”的历史 admission。

## 产品链路变化

- 三个 Specialist 的 Fact 交互不再调用 Provider，由本地确定性 candidate selector、renderer 和 terminal calibration 完成，并各自产生 typed receipt。
- Claim 与 WWC 仍是 Pro preview 的 request-local alias/closed-enum surface，再由本地校验、选择、ID/引用展开和最终渲染。
- Research Lead、Memo Writer、Verifier 可组织判断或生成 finding，但不能拥有重要数字、日期、案例身份、ID、lineage 或最终 L1 真值。
- 当前 NVDA exact input 绑定 case/head/source/input 和六段 lineage digest；该 manifest 明确不是 admission、paid proof 或历史 Artifact 晋升通道。

## 验证与开发中发现的问题

当前 exact input 的 full-fake 成功得到 `6 nodes / 12 logical interactions / 3 local Fact receipts / 9 Provider calls / 9 captures / 9 Artifacts`。需求、价值、瓶颈三 Cell 中，只有价值 Cell 当前具有可晋升数值 Fact；其余两个 Cell 诚实形成 empty-Fact/cannot-infer，而 Candidate/Graph monitoring refs 不会被提升成 Fact。

实现过程中暴露并在 T02 内收口了四类项目问题：

1. 旧 fake 把 DELL/MU 语义硬编码进 Lead，不能用于当前 NVDA；改为请求驱动的 Claim/WWC 原子与动态 Lead summary，没有放宽生产门禁。
2. production compiler 起初没有原子绑定 v4 research profile 和全部 mandatory policy；现由同一个 compiler 一次完成。
3. 最终三 Cell Manifest/Trace 起初没有显式 interaction topology；现写入精确 6/12/3/9/9/9。
4. 多个历史测试把 T01/S4 时点的代码哈希或全局 next action 当成永远不变的当前状态；历史文件与 digest 保留，测试改为区分 immutable audit baseline 与后续正式阶段实现演进。

Mutation 证明 binding digest 漂移、tracked input query 漂移和 Lead 直接生成数字均 fail closed。Lead 失败路径保留 3 个 local Fact receipts、7 个 Provider captures、3 个 completed specialist receipts 和 typed terminal result，失败内容不可晋升。

验证结果：S3 focused=`8 passed`，适用 S1/S2=`80 passed`，历史 S4 功能与治理回归=`43 passed`，合计 `131 passed / 0 failed`。`ruff` 在当前环境未安装；`py_compile` 与 `git diff --check` 通过。

## 边界与下一步

本轮只证明生产集成和零调用产品就绪，不证明 DeepSeek 自然输出、研究质量、当前 NVDA R2、paired 增益、Owner acceptance、release 或 production。内存 prospective admission 为 disabled，未持久化、未签发、未消费。

唯一下一项是：

`FIN-0.1.2-S3-T03-NVDA-EXACT-LIVE-EXECUTION-AUTHORITY-DECISION`

该项必须先零调用重验 clean code、tracked input digest、v1.3 binding、fresh identity、retry-zero、9-call/USD 0.06 预算、capture-first failure retention 和 source/business write 禁令；用户另行续行前不得读取凭据或执行 exact-live。
