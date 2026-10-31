# 解析器原生输出接入契约

本阶段先保存维护中解析库提供的结构，再在其上做 FIN 适配。入口为 `scripts/engineering/native_document_capture.py`，输出 `fin_native_document_v1`。这是离线原生接入与兼容层；现有产品入库、章节树和预分块尚未全部切换为消费该契约。`--compare-fin` 明确运行原有独立分支，不把对照产物冒充新适配结果。

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

下一步在固定原生结果上接 FIN 章节与预分块适配，逐项记录字段使用、覆盖与不支持原因；优先使用原生分区和语法结构，同时延续原文恢复、来源身份、定位与签署边界修复。评估继续使用[文档结构质量协议](document_structure_quality_protocol.zh-CN.md)，不能把“原生字段已保存”当成“解析质量达标”。
