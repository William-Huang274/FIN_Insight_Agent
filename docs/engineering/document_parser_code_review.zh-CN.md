# 文档解析角色问题：开源实现核查

本轮针对首轮试审暴露的封面章节、搜索标题、导航正文、Markdown 表格与元数据问题，阅读实际调用路径并运行小范围离线对照。结论属于源码研究和本地探针，不是新解析方案已集成或全库资格通过。保持原件、既有修复、冻结样本与当前产品服务不变。

本地依赖为 EdgarTools 5.62.1、Trafilatura 2.2.0、markdown-it-py 4.2.0；mdit-py-plugins 未安装。以下 GitHub 链接固定至核查时提交，与本地安装版分别记账；没有自动升级依赖。远端 10 个源码文件的 blob SHA 均与固定提交复核一致。

## 1. SEC：应区分标题候选与业务分区

EdgarTools 的 `Document.sections` 确实调用 `HybridSectionDetector`，并不是一个未使用的辅助类。当前源码按目录锚点、交叉引用索引、heading、pattern 的顺序尝试，再做验证。heading 路径也要求 `header_info.is_item`，不会直接把所有粗体 heading 变成 SEC Item。

- [Document.sections 调用路径](https://github.com/dgunning/edgartools/blob/3931b22077eee1e0d2b77a8c5a61ab415d51ae0b/edgar/documents/document.py#L904)
- [HybridSectionDetector 与分区验证](https://github.com/dgunning/edgartools/blob/3931b22077eee1e0d2b77a8c5a61ab415d51ae0b/edgar/documents/extractors/hybrid_section_detector.py#L74)
- [heading 到 Item 的筛选](https://github.com/dgunning/edgartools/blob/3931b22077eee1e0d2b77a8c5a61ab415d51ae0b/edgar/documents/extractors/hybrid_section_detector.py#L618)

它仍使用格式、样式、上下文和表单规则，不是完全依靠模型。关键是分层：排版 heading 是候选，表单业务分区有单独的约束与输出。

本地冻结产物提供了直接证据：Super Micro 7 月 21 日、Lumentum 8 月 11 日、Lumentum 7 月 30 日的 `parser_sections` 分别已有 3、3、2 个正确分区名称；FIN 章节树却有 9、9、8 个根节点。原生结果标记 method=pattern、confidence=0.7、validated=false；0.7 是程序分值，不是实测准确率，也不能据此宣称分区内所有内容正确。

现有适配保存了 `parser_sections`，但主要从平铺块的 heading 重建树，只在部分恢复逻辑中使用原生分区。下一步应优先验证并接入原生 Part/Item/签署范围，保留原 DOM/节点身份与方法依据，再在分区内部组织小标题。缺失或冲突的分区继续标未知，不能以一个白名单过滤掉所有未识别内容；原生 offset 也不能未经核对就当作 FIN 块索引或原 HTML 字符位置。

## 2. 网页：正文抽取与页面用途必须分开

Trafilatura 的标题提取有多层退路，最后会尝试首个 H2。当前主线的正文流程也有扩大提取范围的后备阶段；精度模式会限制部分扩大范围行为。FIN 现有对照入口固定使用 `favor_recall=True`。

- [extract_title](https://github.com/adbar/trafilatura/blob/43ca3d4d656d7a5495708f1fca159cdbd5715b5d/trafilatura/metadata.py#L336)
- [正文提取及后备流程](https://github.com/adbar/trafilatura/blob/43ca3d4d656d7a5495708f1fca159cdbd5715b5d/trafilatura/core.py#L165)

在本地 Trafilatura 2.2.0 上，复用 Amazon 同一份捕获原件和 FIN 的 XML 参数，仅改变模式：召回模式、默认模式均给出标题 Site Search 与 609 字符导航文本；精度模式返回 None。这证明参数选择会影响此次错误，但不证明全站切精度模式就能解决问题。空输出需分辨非文章、内容未抓到、动态页面与解析失败，不能自动认作成功，也不能立刻用全页文本补成正文。

Mozilla Readability 提供独立算法对照：检查可见性、界面 role/class，累计段落内容信号，并用链接密度降低候选区域得分；不是仅凭 H1/H2。其测试对比期望正文 DOM、文本与元数据，值得复用这种验收组织方式。此次只读源码，未声称 Readability 已在本库通过。

- [Readability 界面区域过滤](https://github.com/mozilla/readability/blob/ab4027a8b37669745016869a37a504727992b2ba/Readability.js#L1070)
- [段落与链接密度评分](https://github.com/mozilla/readability/blob/ab4027a8b37669745016869a37a504727992b2ba/Readability.js#L1260)
- [期望 DOM 和标题测试](https://github.com/mozilla/readability/blob/ab4027a8b37669745016869a37a504727992b2ba/test/test-readability.js#L133)

建议保留 Trafilatura，增加正文模式与发现页用途的明确适配，并以 Readability 作独立对照。目录页保留可追溯链接与页面元数据，不进入文章章节树。两种算法一致也不是正确性的证明，仍需原件样本核对；真实文章的遗漏率必须同时验收。

## 3. Markdown：直接复用语法解析，而非继续手写切分

markdown-it-py 的 GFM 表格规则输出 table/thead/tr/th/td token，处理管道转义、分隔行、列对齐，并保存块及行的 `token.map`。mdit-py-plugins 的 front matter 插件在表格规则之前处理文件起始元数据，输出独立的隐藏 token 及行范围。

- [GFM 表格规则](https://github.com/executablebooks/markdown-it-py/blob/6f586542653a56d2ee8549a0dccfaa6ba5ebe14a/markdown_it/rules_block/table.py)
- [前置元数据插件](https://github.com/executablebooks/mdit-py-plugins/blob/519953da0a394a92534bc27580f4e7415462df44/mdit_py_plugins/front_matter/index.py)

本地未安装新包，仅用已有 markdown-it-py 对 PAR 原件运行 `MarkdownIt('commonmark').enable('table')`：得到 1 个表格、2 个表头单元格、3 行正文共 6 个单元格，表格源行区间为零基半开区间 [4,9)。同时确认：没有 front matter 插件时，许可证行会按 Setext 语法变成标题。因此需要整套配置与薄适配，不是只改一个依赖名称。

表格语法会按表头列数补空单元格或忽略多余列；这符合显示语法，却不能默认为财务内容守恒。适配时保留原行、原始列数及异常，核对 token 与原文覆盖；`token.map` 也不是精确单元格字节坐标。front matter 插件只提供元数据块，后续若解析 YAML 仍应使用安全加载方式并保留原文。

## 4. Docling：参考角色分层，不能当成万能判断器

Docling HTML backend 把 HTML title 元数据放在 FURNITURE 层，正文属于 BODY；提供表格跨度与富单元格结构，也避免将表格/列表内部的标题直接用于初始正文层判定。它展示了可以复用的文档对象设计。

- [title、BODY/FURNITURE 与初始层](https://github.com/docling-project/docling/blob/764b5d4dc22b03ea87afd4c2207f510300b27a5b/docling/backend/html_backend.py#L949)
- [heading 处理](https://github.com/docling-project/docling/blob/764b5d4dc22b03ea87afd4c2207f510300b27a5b/docling/backend/html_backend.py#L2769)
- [表格网格及跨度](https://github.com/docling-project/docling/blob/764b5d4dc22b03ea87afd4c2207f510300b27a5b/docling/backend/html_backend.py#L2041)

但其可选家具层推断也使用“首个合格标题前”的启发式，不能保证搜索 H2 或 SEC 封面一定正确。此次不为这几个问题全量迁移 Docling，也未运行其解析。先参考角色分层，PDF/复杂版面沿既有工具对照继续验收。表格网格正确不等于已识别公司、期间、单位及财务归属。

## 决策与验证顺序

1. SEC 优先做原生 sections 与原件范围的适配对照，检查封面假章节是否消失，既有主章节、签署边界、正文和表格是否保留；不能只减章节数量。
2. Markdown 接成熟 token 输出和前置元数据插件，覆盖普通表格、转义管道、代码块、缺列/多列、Setext 标题及源位置回读。
3. 网页分别验证文章、目录和动态捕获不足，比较 Trafilatura 精度模式与独立提取器。去掉导航的同时检查正文遗漏，不采用全库统一删标签的办法。
4. 原件摘要、原坐标、章节归属、预分块覆盖和质量状态由 FIN 薄适配统一；财务事实身份继续单独负责。先在冻结开发样本复测，再扩展无当前提示样本和其他格式；旧结果不得覆盖。

源码快照索引、固定提交/文件 SHA、原生分区对照及本地模式探针保存在 Git 外的本轮代码研究证据目录。未调用模型，未生成向量，未修改服务或隔壁分支。阶段状态为“源码核查与小探针完成，集成尚未实施”。
