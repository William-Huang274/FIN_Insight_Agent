# 解析器原生输出接入契约

本阶段先保存维护中解析库提供的结构，再在其上做 FIN 适配。入口为 `scripts/engineering/native_document_capture.py`，输出 `fin_native_document_v1`；`native_document_adaptation.py` 已在离线资格路径中消费 SEC 分区和 Markdown token，生成章节关联与预分块。现有产品入库尚未切换。`--compare-fin` 明确运行原有独立分支，不把重新解析的对照产物当成已包含全部既有修复的基线。

## 1. 原生能力承接范围

| 路径 | 承接内容 | 不得隐含的结论 |
| --- | --- | --- |
| EdgarTools | 完整公开节点字段及父子关系；Part/Item/签署分区的字段、延迟正文和表格；标题、完整单元格与跨行跨列、嵌套节点；元数据、统计、原 HTML、XBRL facts | 原生 confidence、validated、warnings 原样保存，不等于结构或财务语义通过 |
| Trafilatura | `bare_extraction().as_dict()` 全部字段；正文与评论 XML、属性、链接、图片引用和元数据；显式 balanced/precision/recall 模式 | 提取成功不等于文章正文正确；空输出明确记录，不用全页文字填补 |
| Markdown | CommonMark + 原生表格规则 + front matter 插件；全部 token、子 token、属性、环境、源行范围和原文 | token 行范围不是单元格字节坐标；表格语法可能忽略多余列，原文继续保留 |
| Datamule / doc2dict | 层级字典、完整元组、列式元组、文本、Markdown、公开文档字段；表格对象原始值、前后说明、脚注 | 表格接口失败不能当“没有表格”；数值未自动变成已核验 SQL 事实 |

“完整”限定为上述文档解析公开数据面。下载、搜索、相似度/NLP、可视化、数值 DataFrame 转换和模型调用不属于本次接入范围。PDF、Readability、Docling 沿既有独立资格路线推进，本脚本没有声称已接完这些库。Markdown 插件按当前原件类型配置，不默认启用所有可选语法。

原生图引用只在一次产物内有效，不取代已有来源 ID、数据库 ID、引用 ID 或原位置。章节 offset 仍保持上游含义，不擅自解释成 FIN 块索引。表格保存完整 `Cell.content`，不使用可能截断长单元格的展示文本作为权威存储。

## 2. 原生结果与兼容适配分别留存

`native` 保存原生值；`compatibility_adaptations` 保存有明确输入输出契约的适配。当前 Datamule 5.0.2 / doc2dict 0.7.3 组合的层级元组为六字段，但 Datamule 表格接口按四字段解包；说明字段还存在字符串与字典的格式差异。原生错误保留在 `capability_errors`，进程返回码为 2（部分接入），不伪装原生成功。

兼容层保留六字段原文及角色/位置依据，只向独立的 Datamule 表格视图提供它预期的前四字段和说明对象，继续调用上游表格构造器。原对象、包源码与原始文件均不改写。未知元组形状拒绝适配；适配失败另记错误。表格与脚注的财务适用范围仍需核验。

未知公开字段类型会明确失败，不使用 `default=str` 静默丢失结构。存储记录源 SHA256、解析器版本、实际加载模块的源码摘要、选项、实现摘要和输出摘要。`read_capture()` 校验产物摘要、来源摘要、图引用与 token 范围，供后续适配直接读取固定结果，避免再次运行解析器产生另一份输入。

## 3. 可复现运行

在隔离解析环境安装 `scripts/engineering/requirements-native-parsers.txt`；不升级正在运行的产品环境。依赖文件固定本次直接依赖版本，传递依赖仍由环境解析，实际版本/模块摘要以产物为准，因此它不是跨平台完整锁文件。

```powershell
python scripts/engineering/native_document_capture.py --manifest <frozen-manifest.json> --id <original-sha256> --route edgartools --compare-fin --output <new-output-directory>
```

manifest 使用全库结构检查的 `database` / `jobs` 契约。脚本只读查询成功捕获，解压后复核来源摘要，禁用普通外网 socket 连接；不调用下载或模型接口。输出目录必须不存在。输出为 `native.json.gz`、可选的 `fin-comparison.json.gz` 和 `receipt.json`；生成物保存在 Git 外。返回码 0 表示本次接口承接完成，1 表示执行失败，2 表示有公开原生能力失败，均不代表文档质量认证。

测试入口：

```powershell
python -m pytest -q tests/test_native_document_capture.py tests/test_document_structure_audit.py tests/test_source_structure_contract.py tests/test_chapter_refinement.py
```

## 4. 2026-10-31 小范围真实原件证据

8 份唯一原件，9 次接入（其中一份额外跑 Datamule）；全部来自已参与诊断的冻结范围，**不是独立质量保留集**。

| 原件范围 | 实测承接结果 |
| --- | --- |
| 三份 8-K | 分区分别为 3、3、2；分区延迟正文/表格、节点关系与状态保留 |
| 一份 Amkor 10-Q | 2,270 个原生节点、12 个分区、44 个表格对象、1,032 个原生 XBRL fact 条目；未据此声称每个分区边界正确 |
| PAR Markdown | 1 个前置元数据块、1 张表、2 个表头单元格与 6 个正文单元格；许可证未变成标题 |
| WeVis Markdown | 1 个前置元数据块、9 个标题、3 张表，17 个表头单元格与 321 个正文单元格 |
| Amazon / AMD 网页 | 各保留 21 个原生字段；Amazon 仍输出 Site Search，作为已知页面用途误判继续保留 |
| Super Micro Datamule 对照 | 原生表格接口报错留存；兼容视图恢复 4 个表格对象，数量不能与另一解析器的排版表格数直接比较准确率 |

所有产物通过摘要回读；8 份唯一原件的旧 FIN 块文本与此前冻结结果逐块一致。这支持既有正文恢复未因本次新入口被覆盖，不是完整角色/章节质量证明。此轮单文档进程含旧分支对照的峰值工作集约 82–261 MiB，不能外推全库常驻内存。没有向量生成、召回评测、付费模型调用或服务切换。

首轮接入后的章节与预分块消费实现见第 5 节。评估继续使用[文档结构质量协议](document_structure_quality_protocol.zh-CN.md)，不能把“原生字段已保存”当成“解析质量达标”。

## 5. 原生结果消费与分层扩量

`native_document_adaptation.py` 读取固定原生产物，不重新调用解析器。SEC 基线须优先使用冻结审核计划中的实际修复产物及 SHA256；重新运行旧解析入口不能替代该基线。扩量时实际发现两份原件重新解析后的块划分与冻结结果不同，因此增加了明确的基线输入和原生路径一致性核对。路径不一致时禁用节点路径匹配，保留原树或使用有原件依据的目录边界，不按相似文字猜测位置。

- **SEC 节点分区**：依据 SectionNode 的真实成员关系，结合完整块文本或表格单元格的一致性，关联既有正文。保留分区内部已修复的小标题。未决标题另存 `unscoped_chapter_tree`，其内容和既有路径仍可追溯；没有任何可靠原生范围时直接保留原树。
- **SEC 目录分区**：原生延迟正文不提供子节点，不能用空节点代表没有正文。现已接入维护中 `SECSectionExtractor` 的公开边界对象，保存锚点及原 DOM 位置。只有完整原容器位于唯一边界内时才建立对应；重复锚点、跨边界容器、无法定位的内容保留未决。未把原生 offsets 当成块索引。
- **Markdown**：语法 token 驱动章节、表格与源行分区。按原文顺序重建可恢复全部文本，包括分隔空白和元数据。代码作为代码候选；嵌入 HTML 作为待结构解析内容，不能一律当成排版垃圾丢弃。表格显示语法的补列/截列仍需要原行核查。
- **预分块**：沿已接入的章节关联组织完整句子；表格独立保留。元数据和空白不进入正文组合；代码与未解析 HTML 不混进正文组。上述内容均保存在账本中。

```powershell
python scripts/engineering/native_document_adaptation.py --capture <native-capture-directory> --baseline-artifact <frozen-repaired-artifact.json.gz> --baseline-sha256 <sha256> --output <new-directory>
python scripts/engineering/run_native_structure_qualification.py --manifest <manifest.json> --plan <frozen-plan.jsonl> --output <new-qualification-directory>
python scripts/engineering/audit_native_adaptation_results.py --directory <qualification-directory> --output <integrity.json>
python scripts/engineering/build_native_structure_coverage.py --bindings <all-library-bindings.jsonl> --results <qualification-directory/summary.json> --output <new-full-coverage-directory>
```

批量工具可以用 `--reuse-captures <prior-captures-directory>` 复用已核验原生产物；不会重复解析来消耗资源。输入、代码、来源摘要不一致拒绝继续。生成物保存在 Git 外；全库账本保留现有产品产物选择，不自动发布候选结果。

本次扩量的冻结范围为 **64 份原件**：33 份 SEC、7 份 Markdown/文本运行章节及预分块适配；9 份网页保留原生输出、网页适配待接；5 PDF、5 JSON、5 XML 保留既有路线。33 份 SEC 的文本、表格与原定位字段以及原容器账本逐份守恒，7 份 Markdown/文本的原文分区可完整还原。7 份 SEC 没有建立可靠原生范围，明确保留原树，不算章节识别改善。

本轮 288 个原生分区中，269 个至少关联到一个块；这不是章节 Recall，也不证明整个分区的正文归属正确。未决标题、未对应块和原生警告继续保留。初始直接重跑旧解析的对照轮已被“固定修复基线”复验替代，不混合两轮的结果作为同版结论。

最终验收继续覆盖 **1,742 条来源绑定 / 1,187 个可关联原件**，409 条缺原件来源单列。64 份只是适配扩量范围，且此前参与过诊断，不是独立保留集。当前没有章节 Precision/Recall 或全库结构质量通过结论。后续需继续扩展网页/PDF原生结构、解决未决范围，并按原件独立审核标题角色、父子层级、读序与遗漏，包含没有报错的资料。
