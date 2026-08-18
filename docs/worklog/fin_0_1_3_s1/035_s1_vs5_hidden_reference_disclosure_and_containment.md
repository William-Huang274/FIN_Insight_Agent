# S1 VS5 hidden reference 意外披露与隔离处置

日期：2026-08-18

状态：`incident_contained / existing_hidden_references_not_blind / no_hidden_execution / replacement_independent_adjudication_required`

## 发生了什么

在 COST R2 已冻结失败后，为查找仓库中是否已有 Evidence Set／temporal pair 合同，执行了一次范围过宽的递归 `rg`。搜索范围显式包含 `eval_sets`，输出因而带出了 JPM／CAT test-frozen 与 NVO／SHEL／腾讯 heterogeneous-holdout reference 的部分标签行和业务说明。

没有执行这些案例，没有生成 successor hidden input，没有读取 hidden candidate／result，也没有根据标签修改代码、阈值或 COST R1／R2。但“实现者上下文已经看过 expected outcome”本身就足以破坏盲评资格，不能用“没有运行”掩盖。

## 立即处置

1. 现有两个 hidden reference 文件保持字节不可变，不删除、不重标、不继续读取；
2. 其资格状态改为 `ineligible_for_blind_qualification`；未获 Owner 后续决定前也不自动转成开发集；
3. COST R3、现有 test-frozen 和 holdout execution 全部禁止；
4. 根目录新增 `.rgignore`，普通递归搜索不再遍历这两个标签目录；这只是防误触，不冒充安全边界；
5. 机器 disposition 绑定两个现有文件的摘要和污染状态；测试只核对路径与摘要，不解析标签内容。

## 后续正确形态

新的 qualification program 仍可在 FIN 0.1.3／S1 内建立，不需要创建产品版本。但 blind expected outcomes 不应继续提交到活动 Git 树：

- Git 只保存不含答案的 case/source preregistration、reference digest/access policy、candidate freeze receipt 和事后 public projection；
- expected outcomes 保存在 private untracked 或外部受控位置；
- 实现 Agent 在 candidate 冻结前不能接收标签；
- reference 必须由独立 qualified human，或 Owner 明确授权的上下文隔离评审流程生成；
- 当前 Codex 可以继续用 COST 与既有开发案例做零调用合同／mutation，但不能冒充 replacement blind adjudicator。

## 产品影响

这不是检索产品能力退化，也不改变 COST R2 的 15/20 失败；它改变的是评测可信度。现有 hidden set 即使未来跑出全绿，也只能算 disclosed regression，不能支撑“跨行业泛化通过”。S1 资格与完整真实链继续 blocked。

## 工程复证

- hidden isolation 定向测试：8 passed；
- 全仓：633 passed；
- compileall：通过；
- active baseline：155 Python／8 frontend／16 Runtime resources，0 forbidden reference；
- secret scan：7,134 files，0 finding；
- 普通 `rg` 对 qualification references 的搜索只返回 valid-temporal 文件，不再遍历 test-frozen／holdout 目录。
