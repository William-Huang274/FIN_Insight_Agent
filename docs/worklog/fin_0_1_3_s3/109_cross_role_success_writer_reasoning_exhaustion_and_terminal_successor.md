# 109｜跨角色审查成功、Writer 推理耗尽与终端 successor

日期：2026-08-21

范围：FIN 0.1.3／S3／DELL Multi-Agent Preview

结论级别：真实 live 失败证据＋零调用结构修复；尚未形成最终报告或 S3 验收

## 1. 本轮真实运行到底完成了什么

本轮从六角色 Evaluator checkpoint 之后开始，没有重跑 Specialist plan、Lead plan、六份 workpaper、Lead coordination 或三条已完成 repair。实际新增并完成：

1. 一次跨角色一致性审查；
2. 一次 Writer 分析调用的部分输出。

跨角色审查形成有效提交，`report_may_proceed=true`。它没有发现需要回流给角色 Agent 的 material conflict，只留下五条非阻断 finding 和三条“无活动冲突、但写作时必须保留边界”的说明。主要边界包括：

- 公司整体现金不能写成 AI 专属现金；
- Q1 FY27 毛利率变化不能借用较早期间的 AI mix 机制做因果归因；
- NVIDIA、TSMC、Micron 等上游披露必须保留 speaker attribution，不能升级为 Dell 公司事实；
- backlog 定义不能被改写为已经实现的收入或确定性需求；
- 缺少公开阈值时不能由 Writer 发明阈值。

因此，六角色内容审查和跨角色一致性层已经自然越过。当前失败不是“多 Agent 没跑起来”，也不是 S1 没资料或 S2 数字冲突。

## 2. Writer 为什么失败

Writer 请求获得 Provider HTTP 200 和完整响应。实际 usage 为：

- prompt：`19,482` tokens；
- completion：`16,000` tokens；
- reasoning：`15,436` tokens；
- 可见草稿：`2,328` 字符；
- finish reason：`length`。

草稿已经给出报告标题、执行摘要，并开始第一节，但尚未完整交付 sections、remaining gaps、what would change 和 confidence statement。Runtime 按合同将其保存为私有分析片段，没有把半份草稿晋升成正式 Artifact。

最早责任层是 S0/S3 的任务 profile：上游研究、反方和跨角色判断已经完成，Writer 此时承担的是“忠实压缩和编纂”，却仍使用 `thinking=max`。约 97% completion token 被隐藏推理占用，导致可见报告被截断。这不是增加资料或再次运行六角色可以解决的问题。

## 3. 为什么 non-thinking continuation 不会降低研究质量

本轮没有把研究 Agent 改成 non-thinking。高推理仍保留在：

- 六个专业角色的研究与 repair；
- Lead coordination；
- 角色内容审查和跨角色一致性判断。

Writer continuation 只能读取：已验证的跨角色审查、已保存的 Writer 草稿、缺失输出清单和原权威视图。它不得新增事实、Evidence、NumericFact、引用、因果机制或研究结论；只能完成尚缺章节，再进入同一严格 report submission 合同。因此这是“完成已经作出的研究决定”，不是“用低推理替代研究”。

## 4. 零调用结构实现

新增 provider-neutral 终端恢复合同：

- `CrossRoleEvaluationCheckpoint`：冻结已经完成的跨角色审查和全部 finding；
- `AnalysisFragmentCheckpoint`：冻结 Writer 原请求／响应、2,328 字草稿、完成／部分／缺失字段、usage 和 digest；
- terminal `SuccessorExecutionFrontier`：只允许一个 Writer continuation logical node；
- Writer continuation profile：`thinking=disabled`、`max_tokens=12,000`、`retry=0`；
- strict submission 仍独立执行，Harness 只校验和绑定，不补写研究观点。

禁止事项：六角色审查重跑、跨角色审查重跑、role repair、外源网络、Candidate promotion、半稿业务晋升、第二次 continuation、S1/S3/人工/发布自签。

零调用 fake 路径证明：

- 新 Writer logical node：1；
- analysis continuation：1；
- strict submission：1；
- 上游模型节点、网络、Candidate promotion：0；
- report contract：通过。

六类 mutation 均被拒绝：跨角色 checkpoint digest 漂移、Writer fragment digest 漂移、半稿晋升、上游重跑预算、thinking-enabled Writer profile、语义仍不完整的 continuation。

## 5. 当前真实能力与未完成项

已证明：六角色研究底稿可被独立审查；跨角色一致性审查能保留公司／期间／归因边界；失败节点可被精确 checkpoint 并只续跑终端消费者。

未证明：自然 Writer continuation 成功、最终报告 L1、八维内容质量、paired gain、qualified-human 验收、S1/S3 通过、跨案例泛化、Workbench publication 或 release。

下一步只允许：完整仓库门 → clean commit／push → fresh Project OS preflight → 全新 authority → 一次 Writer terminal successor live。若自然 continuation 仍失败，不重跑上游，也不再扩大同一 Writer profile；转为 Writer 模型／profile 或报告编纂职责的项目级选择。

## 6. 完整工程门

最终工程门全部通过：

- 全仓：`925 passed`，仅两条既有 SWIG deprecation warning；
- Python `compileall`：通过；
- Workbench：TypeScript typecheck 与 Vite production build 通过；
- active baseline：`185 Python / 8 frontend / 5 detectors / 27 Runtime / 0 forbidden`；
- archive redirect index：`6,059` 条，check 通过；
- configs：`785` 份 JSON 可解析；
- Project OS：完整门执行时 `8` 份 JSONL／`888` 行可解析；追加最终 root-cause 与 capability 状态后为 `890` 行，仍全部可解析；
- secret scan：`7,507` files／`0` findings；
- `git diff --check`：通过。

pnpm 包装器曾因工作区安全策略拒绝未批准的 `esbuild` 安装脚本；这不是前端代码失败。未修改依赖或供应链策略，改用仓库已经安装并锁定的 Node／TypeScript／Vite 文件执行同一 typecheck 和 build，二者均通过；包装器临时生成的 lock/workspace 文件已清理。

当前工程状态只允许 clean commit／push、fresh preflight 和一次 terminal Writer successor，不构成自然 Writer 或产品内容验收。

## 7. 第一次 fresh preflight 的人类边界漂移

clean／synced commit `01a302ca...` 上第一次 fresh preflight 的全部机器检查均通过，并正确投影 `maximum_new_model_nodes=1`、六份角色审查复用、一次跨角色审查复用和一次 Writer continuation。但 `known_boundary` 仍沿用普通 generic successor 文案，写成“允许后续 evaluation／repair／conditional Writer，同时禁止 analysis continuation”。它与机器 scope 相反，因此没有用于签发 authority。

RC-AR-027 的修复不是放宽权限，而是让 human projection 从 terminal frontier 的实际数字生成：明确只允许一次 non-thinking Writer continuation＋strict submission，并禁止所有上游 Agent、repair、Evaluator、第二次 continuation 和半稿晋升。新增测试同时拒绝旧模板文字。第一次 preflight 保持只读诊断，不追认为有效签发依据。

修正后的定向 Project OS 测试为 `59 passed`，随后全仓再次为 `925 passed`；compileall、Workbench typecheck／production build、active baseline `185／8／5／27／0`、archive redirect `6,059` 和 7,507-file secret scan／0 均通过。追加 RC-AR-027 与 capability 状态后 Project OS 为 8 份 JSONL／892 行。下一步必须先形成并推送第二个干净提交，再运行第二次 fresh preflight。
