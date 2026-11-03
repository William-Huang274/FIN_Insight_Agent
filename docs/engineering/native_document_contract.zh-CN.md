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

## 10. 后续适配与补充的共同规则

上述未知级别修复已在 `9c1f6cd1` 完成全部 734 份统一复验，工程完整性与兼容审计通过；质量边界见[总库状态](library_identification_status.zh-CN.md)。下一阶段以[解析问题登记与处理范式](document_parsing_residuals.zh-CN.md)为剩余问题来源，不继续以无报错作为发布依据。

- 来源身份、原生输出、统一结构、章节/逻辑表、预分块、原件质量检查分层留据；先消费原生能力，再按结构族补充。原位置、原始角色和采用后的角色分开，兼容旧树不提升为正确树。
- 类型由文件格式和用途共同决定。6-K、附件、13F、门户、新闻、RSS、数据接口、图像式 HTML 不共用单一章节成功标准；没有 Part/Item 不等于异常。
- 新路线必须承接已核实的旧修复或明确记录冲突。当前网页新候选未复用旧基线中 27 份 `verified_original_heading`，这是待修复兼容缺口；原件/基线摘要核验后复用原关系，不能无依据推断到其他正文。
- 边界映射失败须区分上游原生范围错误、合法短/空分区、交叉引用、容器跨界与定位歧义；不能强制选择第一个候选。表格结构与财务语义分别验收。
- 个例修正只绑定原件摘要及局部坐标，记录依据、依赖版本、适用范围与失效条件；不建立公司或题目特判。模型辅助须另有明确范围和预算，不能直接改写原文或财务事实。
- 历史诊断与当前版本重评分开。未知级别、短标题、层级跳跃只是线索；每条诊断绑定输入/检测器版本及处理状态，不将旧提示当作本版新测错误数。
- 待实施的统一流程须支持受影响阶段重算、幂等恢复、失败保留、有限用途与新版本发布；这些是后续合同，不代表生产已接入。局部通过后仍要完成完整受影响范围复验，并按原件质量协议审核未触发提示的材料。

## 11. 原件证据修复与独立路线补充

`document_structure_repairs.py` 和 `document_role_repairs.py` 在冻结结果上做有据修复，不重新生成原件或原生捕获。签署边界要求唯一完整原容器中的 SIGNATURE(S) 标题及紧邻完整法律声明，支持 registrant/registrants；局部范围到下个非日期标题结束。修正后的章节关联保留旧路径和原依据，不修改原生分区成员，也不将原生 TOC 错误标记为已消失。单位标签必须是完整、可核对的原容器文本；6-K 月份还须有共享封面父容器的 Form 6-K 证据。两者保留原文、降为上下文或封面字段，不作后续正文父章节，不自动将单位分配给最近表格。

网页适配承接同一来源摘要的旧原容器。完整文本仅有一个候选时建立原 DOM 定位，多个匹配保留歧义；表格不靠压平文本证明单元格关系。旧主标题只有原容器身份、文本及非导航角色一致才恢复。原 HTML 与原生 XML 坐标仍分别保留；定位部分正文不等于验证全部正文覆盖。

Markdown 嵌入 HTML 使用本地 lxml 子树，保留节点属性、文本/尾文本、显式标题层级、物理表格单元格/跨度与图片引用，坐标限定在原 Markdown 行区间内。原 raw 文本不改写，表内标题不提升为正文章节，HTML 与单位上下文不混入普通正文分块。局部 DOM 结构不证明浏览器版式、图片用途或财务表归属。

`pdf_native_structure.py` 单独保存 PyMuPDF 原生字形跨度、字体、行方向、页内坐标、旋转变换、绘图面板及有框表候选；不将候选合并成已核实读序，不执行 OCR。`structured_source_contract.py` 按 RSS、13F、Companyfacts、申报目录等模式提供记录定位和用途合同；未知数组、行情、通用 API 包装仍需各自数据集契约。原始数值不强制转浮点，记录计数不代表事实或期间正确。

PyMuPDF 2.0 的表格接口默认 `use_layout=True`，安装本地 layout 扩展后会调用其版面模型。本路线显式关闭该选项，并用禁止 layout hook 的测试验证整个页面读取路径；旧接口若存在无法显式关闭的活动 hook 则报错，不默许调用。使用本地 AI 的版面路线可以另行资格验证，但必须记录模式、模型/资源依赖与质量证据，不能标成纯规则。首轮 PDF 开发产物误写的 `model_calls=0` 已由独立纠正记录撤销；旧证据保留，不混入关闭模型后的统一复验。

批次驱动分别为 `run_document_repair_qualification.py`、`run_native_record_layout_qualification.py`。输入清单、父产物及实现摘要冻结，成功与失败分开保存；前者验证块文本、表格/原 XML/源行和引用，后者对结构化对象重新核原件，对 PDF 逐页保存状态。`audit_document_repair_results.py` 复核文本产物摘要与唯一原件分母。

PDF 资源中断后使用 `resume_pdf_native_qualification.py` 显式接续：先验证输入、工作程序版本、完整回执、页序及每页摘要；只复用完整成功原件，旧不完整尝试原样保留，新尝试进入新目录。每份开始前检查可用内存与磁盘，单份超时保留日志。该能力是离线资格脚本的恢复，不代表产品上传或索引发布流程已经接通。

上述路线仍分别输出工程状态与 `quality_pass=false`。原件完整性、候选结构、经原件审核的结构和可发布结果是不同状态；财务主体、期间、单位适用范围、修订及 SQL/XBRL 关联在领域层另行验收。

资格入口使用参数提供私有路径，产物不进入 Git。inventory 的逐行记录包含 `original_id`、`lane`、已冻结产物目录以及 `existing_baseline`/`existing_baseline_sha256`；manifest 提供只读原件库和来源身份。运行前准备 lxml、psutil、已验证版本的 PyMuPDF 及各路线既有资格依赖；不由脚本在线安装或下载模型。

```text
python scripts/engineering/run_document_repair_qualification.py --inventory <inventory.jsonl> --output <new-text-dir>
python scripts/engineering/audit_document_repair_results.py --root <new-text-dir> --output <audit.json>
python scripts/engineering/run_native_record_layout_qualification.py --manifest <manifest.json> --inventory <inventory.jsonl> --lane structured --output <new-record-dir>
python scripts/engineering/run_native_record_layout_qualification.py --manifest <manifest.json> --inventory <inventory.jsonl> --lane pdf --output <new-pdf-dir>
python scripts/engineering/resume_pdf_native_qualification.py --manifest <manifest.json> --inventory <inventory.jsonl> --previous <interrupted-pdf-dir> --output <continuation-dir>
python scripts/engineering/audit_native_record_layout_results.py --root <completed-dir> --inventory <inventory.jsonl> --lane <pdf-or-structured> --output <audit.json>
```

内存有限时串行安排文本复验、结构化合同重算与 PDF。结构化重算需要解压/反序列化原对象，不与 PDF 批次叠加；完成后的文件身份核对不等于新的原件质量抽样。资源暂停允许在同身份下接续，解析失败和超时仍先定位原因、保留原尝试；改动工作程序后必须另建版本，不能沿用旧成功表格候选凑成统一通过。

## 12. 短章节的原容器序列消歧

原生分区可能提供完整章节文本和有效目录锚点，却没有子节点。此时不能把重复的短正文随意分配给章节。`native_section_alignment.py` 仅在下列证据同时成立时补充定位：明确的 Item 编号；唯一匹配的完整标题块；每个完整原容器只落在一个原件目录范围；原容器顺序严格前进且不重叠；块序列全文与原生章节全文相同。下一标题限定序列边界，表格、部分文本、多候选和原生归属冲突均拒绝。旧候选位置保留，新增采用位置另记依据。

该规则不包含公司、年份、题号、None 或 Reserved 特判，也不把未知标题级别补成固定级别。它不解决被拆开的标题原容器、错误的原目录范围、排版表、正文被标为普通文本的标题，亦不证明旧唯一定位一定正确。发现旧定位落到目录同名文字时，要另外核验并保存有据修正，不能为了兼容而把它称为正确。

`qualify_sec_sequence_alignment.py` 对参数提供的冻结范围重新适配，再应用既有签署和角色修复，并与最新修复产物对照：原文本、块数、表格、源容器、已有单位/封面角色、唯一定位/归属和签署证据必须保持。新增位置、块归属和新获得块的分区分别计数；这些是工程增量，不是识别准确率。清单必须给出 `id`、`title`、`artifact_path`、`artifact_sha256`，每份成功产物都有回执、原生捕获和父产物摘要。串行子进程限制内存驻留；资源暂停只在相同代码、输入和产物摘要下恢复，失败目录保留并要求诊断。

```text
python scripts/engineering/qualify_sec_sequence_alignment.py --plan <frozen-selection.jsonl> --captures <existing-capture-root> --adapted <previous-sec-adapted-root> --output <new-qualification-dir>
```

局部消歧回归与全 SEC 统一版本验收分开报告。未经过本次重新适配的原件继续保留前一版，不用多个版本的成功数拼成同版全库通过。

本地串行资格运行建议在启动 Python 前设置 `OPENBLAS_NUM_THREADS=1`、`OMP_NUM_THREADS=1`、`MKL_NUM_THREADS=1`，并在资源记录中保存环境值。解析路径的间接 NumPy 导入可初始化不必要的线程池；一次诊断中，导入后线程数从 27 降到 4，专用提交内存从约 792 MiB 降到 53 MiB。同一真实原件的文档、预分块和回执逐字节相同；工作集峰值仅从约 129 MiB 降到 125 MiB，不能把提交内存差值称作释放的物理内存。该证据只说明本机依赖与输入下的运行资源变化，不是解析吞吐或质量成绩，也不替代逐份内存门禁。

## 13. 完整标题单元与范围冲突

`source_heading_units.py` 在已保存的原生捕获和修复结果上恢复逻辑标题，不重新下载、解析或生成向量。物理块、块序号、原文和原表格不改写；一个标题单元可指向多个原物理块。目录展示使用完整原容器文字，组成片段保留为结构记录，不进入普通正文拼组。片段只获得 `verified_heading_unit_component`，不冒充完整原容器的唯一定位。

采用条件包括：原件目录范围可定位；范围内第一个完整 Item 容器与原生 Item 身份一致；该编号的原容器唯一；原件有标题/样式或被目录引用的短容器依据；输出片段能按原顺序精确还原完整文字。已有完整原定位可以直接证明位置；否则必须由两侧已唯一定位的完整正文夹定位置，且不能与其他已确定正文位置冲突。普通完整标题只允许标点周边空白差异，不以全局去空格拼出字词。目录、链接和表内候选不充当正文标题的独立依据。

修正旧目录错位时保存旧位置和状态，不能仅因旧字段写着 unique 就保留已被原件否定的选中位置。原件显示文字、逻辑标题身份、物理块身份和原生分区身份分别保存。原生 `native_section_binding` 不改写：新增原容器标题证据不等于旧解析库的范围问题已消失。

范围消费有更严格的边界：共享目录范围记录全部 section 身份，不选一个作为唯一归属；同一标题对应多个分区身份则暂缓采用。正文归属与已有其他原生分区冲突、或需要抛弃未定位旧小标题时，保留原归属并记录 `source_heading_scope_deferrals`。延伸到文件末尾的 Item 范围不能自动覆盖后面的签署、附录和索引。此前有完整签署证据的节点和块路径受独立兼容检查保护。

`qualify_source_heading_units.py` 为所有计划原件保存输入/原生捕获/输出摘要及逐份回执，未发生修复的原件也在分母中。每十份回收一次串行工作进程，保留内存/磁盘门禁、600 秒工作组超时和失败日志；代码变化另起批次，失败目录不隐式重试。仅资源暂停可以在相同身份核验后接续。

`audit_library_structure_selection.py` 对全库选用账本重核唯一原件及绑定分母、文本结构合同、完整标题消费、PDF 每页摘要/合同及结构化记录的历史证据摘要。输出逐原件状态、逐条未决清单和各路线版本；仍保留缺原件绑定。标题绑定数、结构提示数、原生内容守恒和原件识别准确率必须分开报告。

标题恢复之后必须再执行 `heading_parent_conflicts.py` 的父级兼容阶段：当原生分区的 Part 与原件前置标题推导的 Part 冲突时，不直接选择任何一方。保留完整 Item 标题、两份冲突依据和旧路径，撤销未证明的父级及依赖它的绝对级别，正文继续指向已有 Item/小标题。一个典型原因是较近的 Part 标题被上游标成普通段落，导致仅看“已识别标题”会越过它；后续须修复原件角色与父级证明，不能拿前一个 Part 凑数。全库审核会拒绝仍然选中冲突父级的候选。

此阶段核对全部 SEC 输入；无变更文件保留已有字节并记录同一兼容阶段的回执，有变更才另存文件。分阶段实现摘要、原输入摘要和父回执串联保存，不把前一阶段的部分运行拼成最终通过。旧候选及资源中断保留，父级兼容阶段也支持只对资源暂停做同身份接续。

```text
python scripts/engineering/qualify_source_heading_units.py --plan <frozen-sec-selection.jsonl> --captures <capture-root> --output <new-sec-dir>
python scripts/engineering/heading_parent_conflicts.py --root <completed-heading-dir> --output <new-parent-checked-dir>
python scripts/engineering/audit_library_structure_selection.py --selection <prior-selection.jsonl> --inventory <original-inventory.jsonl> --bindings <binding-inventory.jsonl> --scope <scope.json> --root <prior-repair-root> --sec <completed-parent-checked-dir> --output <new-whole-library-audit-dir>
```

本规则不包含公司、财年、测试问题或 Reserved 特判。无原生分区的附件/表单、原件本身损坏、复杂表格和页面用途等仍沿各自类型处理；没有证据时不把它们统称为只能手工补丁。

## 14. 原件 Part 层级证明与共享范围复核

`source_part_hierarchy.py` 在完整 Item 标题已证明后，对其 Part 父级独立取证。`source_structure_contract` 保留的容器序列为原 DOM 前序；候选必须是完整的 `PART` 加合法罗马数字标签，排除物理表、表内标签、导航和内部链接，不要求它事先被上游判为标题。带 `Part` 的叙述句不能充当父级。

采用还需要原文中的最近 Part 与原生 Item 元数据一致、解析块能由已有精确原定位或前后完整容器夹定位置，且候选唯一。同一连续 Part 序列有重复标签时，可能是页眉；此时保留旧父级和全部候选，不将最近页眉提升为新章节。原生 Part 值只是交叉核对证据，不能单独决定父级。

证明成立后，章节树与块路径消费相同父节点；物理原文、块身份、原生归属和签署范围保留。冲突历史独立保存，只有证明成立的项才离开当前冲突清单。预分块重新读取修复后的章节路径，不把父级未知自动补成一个猜测值。已有未知子标题的绝对级别不因父级恢复而全部推断。

`qualify_source_part_hierarchy.py` 完整核验 SEC 父回执及输入/产物摘要，代码与依赖摘要冻结，串行运行，资源暂停同身份接续。新代码必须新目录复验；失败目录保留，不静默复用。`audit_library_structure_selection.py` 再独立重算 Part 证明，检查父级是否真正被章节树消费，并复核全库选用分母。

`audit_shared_section_ranges.py` 对全部 SEC 逐份检查共享范围，并回到原生捕获的 HTML 重新计算范围。候选仅按原容器观察分类：目录身份不在原生分区中、同 Item 多个分区身份、范围中未见全部声明 Item、重复 Item 容器、或存在可能拆分的不同 Item 容器。最后一类也不是自动批准拆分；正文里的引用和真实章节边界仍需分辨。每条保留全部分区身份、缺失身份、原容器及摘要，不选择唯一归属。

```text
python scripts/engineering/qualify_source_part_hierarchy.py --root <completed-heading-parent-dir> --output <new-part-qualification-dir>
python scripts/engineering/audit_shared_section_ranges.py --root <completed-part-qualification-dir> --captures <frozen-sec-captures> --output <new-shared-range-review-dir>
```

## 15. 原生范围与原件标题的独立关联

原生分区可能从标题后的首段正文开始，也可能只提供`proxy_summary`等内部身份。标题与正文范围分别取证：`source_section_title_links.py`核对完整原容器、唯一原生归属、Item编号或目录锚点；签署标题另以紧随其后的完整法定声明交叉证明。原容器在正文前时，原件文本流中间不得存在其他可见内容。目录同名项、重复锚点、多个位置或多重分区归属保留未决。

目录标题跨多个容器时，只有锚点文字和全部连续容器的完整token序列一致才合成逻辑标题；保留每段原文、容器位置和分区身份。注释和处理指令不提供可见正文，但它们后的可见文字仍进入相邻性检查。源原件摘要及原文位置可复算，持久化的`bound_source_title_link`状态不能替代重新证明。

此关联更新显示标题及独立标题定位，不移动原生范围、章节父子关系或正文归属。原始物理块与`pre_chunks`完整保留；`finalize_structure_prechunks`将已证实的完整标题块标为结构用途，保留章节引用，不混入普通正文组。混合物理表的标题不在此路线整体过滤，继续沿表内行级合同处理。

当前原件处理入口在既有容器、签署、Part及大小写修复之后消费本关联；全库审计会从原件重建所有证明，并检查最终预分块的结构用途。离线适配合同通过不代表产品发布或独立原件质量通过。
