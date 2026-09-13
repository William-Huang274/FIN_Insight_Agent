# 对外展示范围 / Evidence and sharing scope

2026-09-13 · FIN 0.1.3 frozen · [中文首页](../../README.md) · [English](../../README.en.md)

仓库已公开，FIN 0.1.3 已由 Owner 按本地 Internal Alpha 范围收口；0.1.4 尚为规划。报告内容版本分别保留人审状态，不能用产品收口代替所有历史报告接受。最新指标见[实测报告](technical-evaluation.zh-CN.md)；下文费用与 Dell v4/v5 记录是各自原时点的历史证据。

The repository is public. FIN 0.1.3 is closed as a local Internal Alpha; 0.1.4 remains planned. Report-specific review states remain independent of product closeout. See the [evaluation report](technical-evaluation.en.md) for the frozen scope; the cost batches and Dell v4/v5 records below retain their historical dates.

## 适合展示 / Suitable for review

- 源码、锁文件、合成测试、真实架构和可复现的交互。Source, locks, synthetic tests, architecture and reproducible interactions.
- 脱敏界面、请求级汇总、失败定位及修复证据；同时列样本和限制。Redacted UI, request summaries and failure/repair evidence, with sample scope and limits.
- 经 Owner 选定的报告节选及原始出处链接。Owner-selected report excerpts and original source links.

## 默认排除 / Excluded by default

凭据、用户上传、原始抓取正文、私有 SQL/索引、原始模型上下文/私有推理、完整 trace、个人求职资料和机器本地状态。不将 `.gitignore` 当作历史中没有秘密的证明。

Credentials, uploads, crawled bodies, private databases/indexes, raw model contexts/private reasoning, full traces, job-search material and host state are excluded. Ignore rules do not establish that history is free of secrets.

当前仓库未选定统一开源许可证；第三方组件各自的许可不等于授权重分发财务资料、图片或整份模型报告。依赖锁、CI 漏洞审计与许可证清单属于工程审查，不代替材料权利判断。

No repository-wide open-source license has been selected. Dependency licenses do not grant redistribution rights for source documents, images or reports. Lockfiles and CI vulnerability/license inventories support engineering review, not content-rights adjudication.

## 已执行证据 / Executed evidence

| 场景 / Scenario | 实际结果 / Result | 已知费用 / Estimated CNY |
| --- | --- | ---: |
| 原 Dell 九研究面 / Original Dell research | 265请求、264已知用量、17,060,539 tokens；包含失败、接续和修订，另1未知 / Includes failures and continuations, one unknown | 28.092715 |
| 步骤一集中整改 / Bounded context and local-edit repair | 6个fresh attempts、20调用、1,176,251 tokens；工具清理接续可用，摘要HOLD；非同题全质量节费率 / Not an equal-quality savings benchmark | 4.096831 |
| 报告修订 A2/A4/A5 / Report repairs | 责任作者与Writer/Verifier定向修订；全部用量已知，后续宿主核查另列 / Targeted model repairs plus separate host inspection | 6.729415 |
| 真实PDF/图片问答 / Actual PDF and image Q&A | A1计算参数限额失败；A2保存答案、6来源可读，复用视觉缓存；识别错误由PDF纠正，仍有措辞限制 / Failure retained; cached vision and a corrected OCR value | 0.162395 |
| NVIDIA短问答与修订 / NVIDIA short Q&A and correction | 13调用、269,970 tokens；表格取数可追溯，两次输出分别有单位错误；旧CALC回读工程问题已修 / Unit errors retained, saved-CALC retrieval repaired | 0.126237 |
| Micron有界深问 / Micron bounded deep Q&A | 11调用、594,559 tokens、19来源可读；主要取数/算术一致，但桥接与推断需宿主更正 / Source access and arithmetic inspected; semantic corrections required | 0.746894 |
| 八不同短问 / Eight distinct short questions | 8成功+2失败run、49调用、1,106,250 tokens、17来源全部可回读；百分点解释、部分引用和边界措辞仍需审阅 / Eight saved answers, two failures retained; semantic and citation caveats remain | 0.405444 |

这不是全部历史账单，不将不同时期开发批次相加冒充一轮研究成本。单价按调用时公开价格估算，账单为最终依据；未知用量保留，缓存缺项不记零。

This is not the complete historical invoice. Separate development batches are not one research-run cost. Estimates use recorded usage and applicable public pricing; unknown usage and unknown cache fields remain explicit.

历史 Dell v4 导出证据：10136正文字符、54引用、3图。宿主检查20项重要判断维度、21保存CALC及10附加算术；31算术一致，金融语义标记不自动晋升。MD/PDF/Word/PPT均来自原生版本；渲染PDF15页、Word20页、PPT44页，PPT完整出处与解释在讲者备注。v1–v3、失败及外部修订费用保留；v4不等于Owner接受。

Dell v4 has 54 citations and three charts. Host inspection covered twenty material-judgment dimensions and 31 arithmetic checks; arithmetic consistency does not establish financial validity. Native exports were rendered as PDF (15 pages), Word (20 pages) and PowerPoint (44 slides), with detailed PPT sources in speaker notes. Earlier reports and failures remain available; v4 is not Owner acceptance.

NVIDIA/Micron均为既有工作区内的新问题，不是两次独立全案或泛化benchmark。方法可供读取不等于模型实际消费，模型终审无重大意见不等于百分百正确。自动摘要保持关闭；没有承诺普遍省费率、P95、生产高可用或多租户安全。

最终本地只读演示已经录制，覆盖原生 v4、来源、历史版本差异、累计用量和图表，0模型调用。完整视频仍为Owner审阅材料；公开的[讲解路线](demo-and-engineering.zh-CN.md)不包含原始模型上下文。当前源码8,631文件敏感模式扫描无命中，历史17,354文本blob唯一命中为合成测试值；8个binary/large未纳入该文本扫描，不宣称全面安全或权利审计。

A read-only local recording covers native v4, sources, historical diffs, cumulative usage and charts with no model calls. The full video remains Owner-review material. Pattern scanning found no hits in 8,631 current files; the sole hit among 17,354 historical text blobs was synthetic test data. Eight binary/large blobs were outside that text scan; this is not a comprehensive security or rights audit.

NVIDIA/Micron are bounded new questions in an existing workspace, not independent full-company runs or a generalization benchmark. Available methods are not necessarily consumed. A clean model review is not perfect accuracy. Automatic summaries remain disabled; no general savings percentage, P95, production HA or multi-tenant security claim is made.

复现条件见[中文运行说明](quickstart.zh-CN.md) / [English quickstart](quickstart.en.md)。历史结果与失败见 [S3/190](../worklog/fin_0_1_3_s3/190_dell_cost_external_and_interactive_delivery.md)。Hermes 工作记忆适配及后续资格见最新评测，不再使用旧“未评估”作为当前状态。一次性代码按[冻结标签](../../archive/README.md)恢复。

## 当前前端展示 / Current frontend showcase

公开首页已展示研究起始、地图、配置、运行记录、公司资料库、财务查询及人工审阅报告的实际截图。图片保留各自拍摄日期与样本范围；资料库 60 文件截图早于冻结 70 文档计数。没有发布凭据、上传正文或私有思维链。来源和复拍方式见[图片说明](images/README.md)。

The public pages show actual research, Studio, activity, company-library, financial-data and human-reviewed report screens. Captions preserve capture dates and sample scope. The 60-document library screenshot predates the frozen 70-document count. Credentials, uploaded private material and private reasoning are excluded. See [capture notes](images/README.md).

最新真实增量：前端定向修订 v4→v5，272176 tokens、估1.436408元；配置编辑消费短问，2调用、43622 tokens、估0.085984元，报告未改。两批独立列示，不与上表混成一次研究费用。v5仍待人工审阅，旧引用措辞意见保留。上述v4页数和长录屏是历史证据，不改称v5输出。

Recent live increments: frontend-targeted v4→v5 revision, 272,176 tokens and estimated CNY1.436408; edited-method short Q&A, two calls and 43,622 tokens at estimated CNY0.085984, with the report unchanged. These are separate operations. Report v5 remains under human review with a known citation-wording finding. Earlier v4 page counts and recordings remain historical evidence.
