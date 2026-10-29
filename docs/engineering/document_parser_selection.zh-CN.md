# 资料解析与分块候选选型

状态：2026-10-29 完成资料清单盘点和上游文档调研；尚未安装或运行候选解析器，不构成解析质量或检索质量通过证据。

## 资料范围与统计口径

本次逐项读取并校验现有组织资格验证的 1,742 条冻结来源绑定，涉及 1,591 个不同 URL。它们不是 1,742 个唯一原始文件；相同 URL 可能对应不同保存版本、摘录或投影。范围不包含所有实时上传、个人空间资料，也不包含 SQL 财务事实行。

快照清单摘要：`72bad531a1ae3733c6e4751c2b54f872e7b408799e3e1d17c3b41332d77d37c7`。完整来源行、分类依据和原件路径保存在仓库外的 `parser-selection-inventory-r1` 记录中。

以下是不同统计维度，不能将各行相加当作总数：

| 维度 | 观察值 | 对选型的影响 |
| --- | ---: | --- |
| SEC 域名来源 | 1,107 | 包括 HTML、XML、接口和目录，不全是正文披露 |
| SEC 的 .htm/.html URL | 817 | 优先试原生 HTML/inline-XBRL 解析，无须先渲染为 PDF |
| 元数据或标题可识别的 SEC 10-K | 129 | 长篇正文、嵌套表格、脚注、排版表格是主样本 |
| 同口径 10-Q / 10-Q/A | 335 / 2 | 表格列期间、季度与累计期间需要区别 |
| 同口径 8-K / 8-K/A | 115 / 2 | 主文件与 Exhibit 业务角色不能混为一谈 |
| 同口径 20-F / 40-F / 6-K | 19 / 3 / 35 | 不能把 SEC 支持范围只验证为 10-Q |
| PDF 线索来源 | 123 | 来自 URL 路径、查询参数或解析器记录；未逐文件嗅探 MIME，可能含转录衍生件 |
| .json / .xml URL | 163 / 135 | 按对象、记录、XBRL context 处理，不能统一按字符拆分 |
| .md URL | 63 | README、模型卡等保留标题、代码、列表结构 |
| news_discovery 分类 | 70 | 新闻发现索引不能替代完整新闻正文 |

SEC form 识别有 527 条直接来自元数据、170 条补自标题，另 410 条未识别或不适用。标题分类只用于本次盘点，不可直接升级成运行态硬过滤条件。非 SEC 的 Annual report 没有归为 SEC 文件。

解析记录中有 762 条 `beautifulsoup_row_delimited_fallback`、165 条 `trafilatura`，711 条没有 parser 字段。缺字段不代表没有解析；后续需要补解析来源追踪。记录还包含 pypdf、PyMuPDF、逐页视觉转录。恢复完整的历史解析文本不等于已经恢复原 HTML DOM、PDF 几何或全部可见内容。

## 候选与使用位置

| 优先级 | 候选 | 拟验证职责 | 边界与选择理由 |
| --- | --- | --- | --- |
| 第一轮 | [EdgarTools](https://github.com/dgunning/edgartools) | SEC HTML 文档对象、章节/表格和 XBRL 接入 | 比通用 PDF OCR 更贴合最大来源族；必须验证原文定位、inline 数值和排版表格，不假定自动解决金融语义 |
| 第一轮对照 | [Datamule](https://github.com/john-friedman/datamule-python) / [doc2dict](https://github.com/john-friedman/doc2dict) | SEC HTML/XML 的层级、表格和字典输出 | 独立比较同批原件；仅试本地解析，不引入下载服务或付费数据集；各格式映射成熟度不同 |
| 现有路径改进 | [Trafilatura](https://github.com/adbar/trafilatura) | 新闻、公司公告、访谈网页的正文及结构提取 | 已有使用记录；检查是否过早输出纯文本、误删表格或混入评论/导航。发现页与正文页分开 |
| PDF 第一轮 | [PaddleOCR PP-StructureV3](https://github.com/PaddlePaddle/PaddleOCR) | 中文/英文 PDF 的版面、阅读顺序和表格 | 与既有 Docling 候选作对照；按需启用模块，先测少量页的峰值内存，不并行加载多个模型栈 |
| PDF 对照候选 | [MinerU](https://github.com/opendatalab/MinerU) | 复杂版面、表格、扫描件的结构输出 | 先明确固定版本的本地后端与资源需求；许可证含 Apache 2.0 以外附加条件，不把仓库可见等同无条件可用 |
| 局部诊断工具 | [pdfplumber](https://github.com/jsvine/pdfplumber) | 可选中文字 PDF 的字符坐标、线框、表格及可视化核查 | 适合验证错列、漏行、读序，不是复杂扫描件的一站式解析器 |
| 财务事实配套 | [Arelle](https://github.com/Arelle/Arelle) | XBRL/iXBRL 事实、context、单位与校验 | 配合 SQL 事实和原始表格建立可核对关系；不是正文分块器，不把相同数值当唯一关联键 |
| 分块层候选 | [Chonkie](https://github.com/feyninc/chonkie) | 结构内的句子/递归/token 长度控制 | 只能在恢复结构后试；不承担修复丢失的表头、主体或读序。语义/模型分块不默认全量启用 |
| 以后按需 | [Unstructured](https://github.com/Unstructured-IO/unstructured) | 增加 Word/PPT/邮件等格式时的通用 element 接口 | 当前核心痛点是 SEC 与复杂表格；开源包与厂商托管模型效果分开验证 |
| 暂不做主依赖 | [sec-parser](https://github.com/alphanome-ai/sec-parser) | SEC 语义树设计参考或离线对照 | 当前 README 明确声明停止维护，不作为新生产依赖 |
| PDF 后备 | [Marker](https://github.com/datalab-to/marker) | Markdown/JSON、表格等转换对照 | 暂不与多个 PDF 栈同时引入；代码和模型许可分别核查，默认关闭可选外部 LLM |

EdgarTools 当前[升级文档](https://edgartools.readthedocs.io/en/latest/upgrade/6.0/)说明以 `filing.parse()` / `edgar.documents.parse_html()` 取代旧解析接口，并披露文本输出会截断超过 500 字符的表格单元格。适配应验证结构化内容与完整原件，不直接把展示用 `.text()` 输出当权威原文；实施前固定实际测试版本。

Datamule 的[Document 文档](https://john-friedman.github.io/datamule-python/datamule-python/portfolio/document/)描述字典、层级元组和表格输出，也明确不同格式的映射覆盖不同。应测试本地输入，不用付费云端预解析结果冒充开源解析能力。

Trafilatura 的[参数文档](https://trafilatura.readthedocs.io/en/latest/corefunctions.html)提供保留表格、格式、链接与元数据的选项，不同输出格式保留程度不同。保留完整原 HTML 和抽取结果，正文去噪不能抹掉用于证明金融事实的部分。

PP-StructureV3 的[官方文档](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)说明版面、表格及多栏阅读顺序等模块。MinerU 当前[许可证](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)另有商业门槛及在线服务标识条件。Marker 当前 README 分列代码与模型许可；正式试用必须锁定版本及全部权重的许可，不能沿用旧博客的许可结论。

## FIN 保留的薄适配职责

按原件类型选择解析器，输出统一结构记录：原件摘要、解析版本、节点类型、层级、DOM/页面位置、完整正文、表格单元格及附属关系。原件缺失时标记可验证能力下降，不能用历史纯文本重建的“表格”冒充原始结构。

正文按小节与段落拆分；超长表格按行组拆分，并携带表头路径、期间、单位和表格身份。附属上下文与独立候选区分，不能靠邻接关系占用前十。普通表格若无可靠主体依据，保留未知，不能让模型猜主体再写入事实层。

SQL/XBRL 关联至少检查来源/申报版本、实体及维度、指标、期间、单位、数值与精度；同数值匹配不足以建立归属。既有源 ID 和引用身份保持可回读，新解析作为新派生版本发布。正文变化的块才进入后续向量差异核验，不立即全库重生成。

## 首轮资格验证计划

先准备 24 份原件：12 份 SEC HTML、6 份 PDF、4 份网页/Markdown、2 份 XML/JSON。均分为开发与冻结新资料两组，按原始来源隔离；同 URL 的投影/版本不得跨组。SEC 包含 10-K、10-Q、8-K/附件，PDF 包含中文、复杂表格和演示/转录。旧失败样本用于开发，新资料才用于独立资格。

先验证解析与分块，再为通过者运行同题检索对照：

1. 审核样本中非噪声正文、数值、负号、小数、单位和期间无静默丢失；所有派生块可回到原件。
2. 分别统计数据表/排版表格角色、表头/单位/脚注归属、阅读顺序错误率，不能只检查字符覆盖。
3. 记录每千节点的人工/模型介入量、失败分流原因、耗时、峰值内存与新增向量输入量。批次连续通过不等于全库已通过。
4. 相同问集与相同检索配置对比 Precision@10、nDCG@10、必要证据覆盖和附属上下文；先做解析消融，不能同时换重排模型掩盖归因。
5. 记录代码/权重版本与摘要；小批次失败先修通用适配，不能加公司/题目黑名单。结构低置信异常才交模型辅助；按任务另定输入规模与预算，禁止全量未知成本生成。

这次调研无候选库安装、无模型请求、无索引替换、无服务重启。以上优先级来自资料分布与官方接口说明，实际采用以原件资格验证和独立检索对照为准。
