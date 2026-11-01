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

## 6. 标题表格内的目录锚点

原件对照发现，一类短章节的目录锚点位于标题表格首单元格中，而 FIN 保留的是完整标题表格。直接要求整容器位于锚点之后，会排除真实的 Item 标题，尤其是 Reserved、Not applicable 等短章节。

适配现在只对已有完整原件依据、唯一定位且标为 `section_heading_container` 的标题表格修正起点。该表必须完整结束于当前分区终点之前，表内不得存在另一分区起点；普通数据表、跨分区表格、重复锚点均不得借此扩展。原生边界不覆盖，另存 `native_boundary_adjustments`，记录原起点、适配起点与原容器身份。没有公司名称或题目特判。

`diagnose_native_section_coverage.py` 逐一记录未关联块的原生分区、方法、原生正文摘要和边界。原生分区名与实际正文不一致也属于问题，例如签署分区只返回 Table of Contents，不能为了提高关联数量强制绑定。该诊断不把原生分区数当作原件金标数，也不提供识别准确率。

2026-11-01 在同一份冻结计划的 64 个原件上完成离线复验，未重新解析或调用模型。33 份 SEC 中，3 份原件的 46 个完整标题表格恢复归属；此前 18,245 个唯一归属全部保持不变。有块关联的原生分区从 269/288 增至 280/288，关联块从 18,245 增至 18,291，未决标题记录从 1,709 降至 1,663。33 份 SEC 的内容、表格、原定位与原容器账本继续守恒，7 份 Markdown 原文分区可完整还原。

剩余 8 个未关联分区中，3 个签署分区的原生正文只有目录标签；另 5 个仍无法建立完整块的唯一归属，包含短保留章节、其他信息及两个原生正文相同的财务报表/附件分区。后两者需核对是否属于交叉引用，不能凭相同正文强制选择父章节。上述诊断只覆盖未关联分区，不代表其他已关联分区全部正确。7 份无可靠原生范围的 SEC 仍保留旧树；网页、PDF 的待适配状态与完整库分母不变。既有修复未覆盖，产品产物未切换，章节 Precision/Recall 继续留空。

## 7. 分层扩量与错误检查

扩量不要求当前解析器解决全部资料。适配结果作为候选保存，原件、既有修复结果及失败证据继续保留；只有受审范围达到质量协议要求后才讨论产品选择。单份边界歧义不得阻止其他适用原件运行。换库、调整参数或 FIN 适配都使用相同的源先验审核维度，不以库的自评分替代验收。

`build_native_structure_expansion_plan.py` 从完整绑定账本按唯一原件分组，逐份读取并核对基线摘要。相同原件的冲突路线、冲突基线、缺失文件均留在清单，标记为待修复，不静默挑一个版本。既往运行状态只作上下文，不授予通过或跳过复验的资格。

```powershell
python scripts/engineering/build_native_structure_expansion_plan.py --bindings <all-bindings.jsonl> --prior-results <prior-qualification/summary.json> --output <new-plan-directory>
```

生成全部原件清单、缺原件来源清单、SEC/Markdown 可执行计划和分层计数；计划可交给既有 `run_native_structure_qualification.py`。执行前应核对输出盘容量，逐份串行运行并保留回执；空间不足不以缩小最终分母替代全量范围。

| 路径 | 扩量阶段 | 自动检查与原件审核重点 |
| --- | --- | --- |
| SEC | 已适配路径扩大到适用原件 | 原生分区和原 DOM、正文/完整表格守恒、边界冲突；核对标题角色、交叉引用、签署和正文归属 |
| Markdown | 已适配路径扩大到全部适用文本 | 源行还原、token 与章节、表格单元格；核对元数据、代码、嵌入 HTML 和表格显示语法 |
| 网页 | 先补原生正文到统一结构的消费，再扩量 | 空提取与页面用途、主标题、导航/评论混入、正文遗漏；提取到文字不自动代表找到文章 |
| PDF | 先接成熟版面输出，再扩量 | 页码/坐标、表格单元格、读序与方向；视觉核对无框表、卡片、多栏、表头和脚注 |
| JSON/XML | 保持结构化路径独立验收 | 原记录、字段、来源及模式身份，不用章节指标衡量结构化数据 |

错误检查分两层：自动检查负责摘要、内容保留、引用有效性、范围冲突和执行失败；原件审核负责漏标题/假标题、父子关系、正文归属、表格角色、读序和遗漏。自动检查没有发现问题的原件也要进入审核。每项发现记录原件定位、旧/新输出定位、发生层（原件/解析器/统一表示/章节/预分块）、严重程度和复验结果，沿最早错误层修复。

首次全库扩量计划实际核对 1,742 条绑定、1,187 个原件的基线：734 SEC、19 Markdown、84 网页、45 PDF、305 JSON/XML；另有 409 条缺原件来源。540 个原件无当前诊断，647 个有诊断，两组均保留审核要求。753 个 SEC/Markdown 原件具备候选适配输入条件，表示可启动处理，不表示已执行或质量合格。该计划只读既有原件和基线，不改产品选择。

随后完成全部 19 份 Markdown 模型卡的原生捕获、章节及预分块，输入使用上述冻结计划，未调用模型。19 份源行分区均可完整还原，执行失败为零；原生语法含 222 个标题、23 张表、19 个前置元数据块。16 份原件含 65 个嵌入 HTML 块，继续标记结构待解析；9 份含表格，需要核对单元格与原行，不能用源文保留替代表格正确性。该批是该路径全量工程复验，不是独立质量保留集，也不代表这些结构全部识别正确。

## 8. 网页原生结构消费及批量运行保护

`native_web_adaptation.py` 消费已冻结的 Trafilatura 正文 XML，保存完整元素树字段、属性、链接、文本与尾文本。显式标题级别驱动候选章节，段落与列表沿原生顺序分块；表格保存完整 XML、单元格与原生跨行跨列字段，评论独立保留。元数据标题不自动提升为原件主标题，未知级别保留未知；此路径不新增财务事实。

原生 XML 路径只能证明在提取结果内的位置，不能冒充原 HTML 的定位。候选文档明确记录 `original_location_status=not_mapped_from_native_xml`、`page_purpose=unreviewed` 及原正文覆盖未验证。所有原生文本分区需可还原，既有修复基线通过摘要核对并单独保留，不用新候选覆盖。该机制检查“适配是否丢掉库的输出”，原库是否提取错正文、遗漏网页内容仍须对照原件审核。

```powershell
python scripts/engineering/native_web_adaptation.py --capture <capture-dir> --baseline-artifact <repaired-baseline.json.gz> --baseline-sha256 <sha256> --output <new-candidate-dir>
python scripts/engineering/audit_native_web_results.py --directory <web-qualification-dir> --output <integrity.json>
```

SEC 批量驱动增加 `--minimum-free-mib`（默认 2048）和 `--child-timeout-seconds`（默认 600）。开始每份前检查产物盘余量，超时保留部分日志及退出状态；不隐式重试存在但无完整回执的失败目录。汇总同时保留完整计划数、已处理数与未处理数。空间不足返回 3；单份失败不删除分母，不授予质量通过。工程审核把失败/未完成尝试列为发现，不能因其没有候选产物而漏报。

## 9. 部分原生范围与既有章节兼容

`native_structure_v2` 区分原生范围证据、既有章节关联和目录展示。未绑定到唯一原生范围的块继续保留旧章节关联及其必要祖先，标记 `chapter_binding_status=prior_scope_unverified`；该标记不授予正确性，也不将旧关联计入原生范围覆盖。已确认的原生范围优先，不能从旧路径继承另一原生分区。既有小标题、嵌入标题以及预分块的关联一同保留。无可用原生范围的整份资料仍走原有保留路径，不将其算作修复通过。

只有与已绑定标题块一致的旧章节才被新分区替代，替代关系写入 `chapter_replacements`；不再把分区内任意第一个正文块当成已识别标题。旧 Part 的标签可包含描述性后缀，8-K 的原生 Item 编号可能去掉小数点，适配按明确的编号对应处理，不含公司或题目特判。

原生 `title/name` 可能只是内部标识。显示标题优先使用分区内已绑定的标题块，记录 `title_binding` 的状态、块位置和关联依据；原生字段完整保留。无唯一标题时保留缺失/歧义状态，最多显示 Item 编号等标识性标签，不推断 Business 等未确认名称。

待核旧节点保存在 `chapter_tree`，标为 `navigation_status=compatibility_only`，不自动加入主目录 `outline`。目录应沿最近可见祖先连接；证据路径仍保留待核节点。此机制保留检查和回读信息，不把此前封面误报重新包装为主章节。使用候选结构的消费者必须区分导航与证据归属状态；本批尚未切换产品消费者。

`audit_native_chapter_compatibility.py` 对照固定旧轮次，核对修复基线身份、原生范围关联不变、待核旧关联未丢失及状态没有被提升为已核实。它与既有完整性审核配合使用，不替代原件标题、角色、层级和正文归属的质量审核。

2026-11-02 同版本复验覆盖此前六份审核材料及另选的 35 份材料，共 41 个原件。全部复用冻结捕获和修复基线，没有重新调用解析器或模型。41 份内容、表格和原定位守恒；31,785 个块中，13,172 个原生唯一归属保持不变，17,049 个块恢复了前轮清空的既有关联。恢复关联表示信息不再丢失，不表示旧归属已核实正确。314 个原生分区仍只有 306 个绑定到块，未用兼容关联虚增覆盖。

306 个有块分区中，229 个显示标题由绑定标题块提供，75 个仍没有唯一绑定标题，2 个存在标题歧义。另对四份扩展材料的 40 个绑定标题核对原 HTML DOM 文本，均一致；该检查验证标题文本对应，不测标题漏检或角色准确率。NextEra 的股东权益表恢复到既有财务报表路径并保留待核状态；其签署区旧路径仍位于 Item 6 下，不能称作签署边界修复。Arista 的标题恢复为原文 Item 名称；Dell 的十进制 Item 与原生去点编号兼容。

39 项相关测试通过。首次兼容审计把未确认占位编号 `Item 5` 与内部键同名误报为泄漏；修正审计分类并补回归后，复验无发现，原失败报告保留。最终工程审计和兼容审计均通过，原件识别质量指标仍未授予通过。该轮不是独立质量保留集，也不代替修复后全部 734 份 SEC 的统一适配复验。证据保存在本机资格产物 `native-parser-expansion-20261102/compatibility-41-r3`，包含完整性、兼容性及失败审计记录；程序使用参数传入路径，不依赖此机器目录。

随后扩至全部 734 份的首轮复验发现：7 份无原生范围的附件保留了未知标题级别 `None`，目录压缩隐藏祖先时直接进行层级减法导致异常。727 份产物通过内容守恒和兼容检查，但该批完整范围不通过，失败日志和原范围全部保留。修复只调整已知级别，未知级别继续保持未知，不填成层级 1 或按父节点猜测。无原生范围及隐藏祖先两类回归共同验证该约束；全范围应在修复后的统一版本重新执行，不能将不同版本的局部补测拼成全量通过。
