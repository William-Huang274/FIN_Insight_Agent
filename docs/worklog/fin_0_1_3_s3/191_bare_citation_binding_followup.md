# FIN 0.1.3：裸写来源 ID 的绑定与显示修复

日期：2026-09-08。Owner 在审阅停点再次要求继续，本切片按剩余质量问题推进；Hermes 仍后置，Owner 产品接受状态不变。

## 问题与修复

真实 Micron 保存计算追问写出 `CALC::4a85cb914387d99168e6501a`，但没有方括号，原 `answer_citations` 只捕获方括号引用，因此答案仅绑定两个 NUMFACT 操作数。工具已经要求正式引用，重复追加提示词没有修复输出到宿主的接缝。

复用现成 `markdown-it-py` 读取 Markdown 正文 token，保留 FIN 来源 ID 的轻量识别；裸写与方括号 ID 共用原观察/保存引用校验。未知 ID 不因裸写而绕过绑定；代码、URL和已有链接不被当作正文引用。完整旧方括号 ID 保持精确，不截成已知前缀。前端复用 `react-markdown`/remark树，仅为服务端已经绑定的ID生成引用按钮，代码/原链接保留；伪造或坏编码的claim链接不生成可点击来源。没有新执行、记忆、语义规则或引用数据库。

解析器原本属于workbench-delivery额外依赖；实际原生镜像缺失此包，故显式加入agent-runtime并更新锁文件。不能用宿主venv可导入代替部署资格。

## 已验证证据

- 真实旧回答与原已保存CALC绑定的零模型回放：基线58f84943只绑定2个NUMFACT；修后绑定原CALC＋2个NUMFACT，完整CALC与原记录相等，正文和原文件未改。证据 `D:/temp/fin-bare-citation-replay-20260908-a1/receipt.json`；隔离投影不写入原生历史。
- 定向Python：100 passed / 2 skipped，覆盖保存引用、原生checkpoint读回提交、未知裸ID、Markdown边界、旧版本/会话/来源。这里的scripted native模型是测试替身，0真实provider调用，不声称模型语义提升。
- TypeScript、Vite生产构建通过；1440/1024/390三宽度浏览器检查通过。实际裸CALC按钮可打开来源，代码中的同ID不被替换，近似ID不误绑定，伪造claim链接不崩溃。
- 当前候选7文件敏感模式扫描无命中，diff检查通过。原生镜像构建记录 `D:/temp/fin-bare-citation-native-build-20260908-a1.log`；完整CI和实际部署完成事实在后续记录补齐。

## 状态与边界

产品增量是引用可定位；工程增量是Markdown到既有来源合同的薄适配。上述是有界工程/回放证据，不是财务正确率或token节省率。旧问答原文和v4报告不改；已标注的单位解释、Micron桥接/因果判断、客户明细穷尽措辞仍属研究质量意见，不通过自动链接追认其正确。

GitHub本轮临时分支在合并后清理，保持公开main＋真实历史版本分支的展示要求。汇总状态见Owner审阅清单；Hermes未评估，无付费重跑。
