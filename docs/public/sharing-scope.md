# 数据、报告与评测范围 / Data, reports and evaluation scope

FinSight v0.1.3 是本地金融研究工作台预览版。公开截图展示实际界面；研究结论、报告版本与人工审阅状态分别保存。当前测量结果见[中文评测](technical-evaluation.zh-CN.md) / [English evaluation](technical-evaluation.en.md)。

FinSight v0.1.3 is a local financial research preview. Screenshots show the actual application; research conclusions, report versions and human review states are recorded separately.

## 仓库内容 / Repository contents

代码、配置示例、合成测试、评测方法和经过检查的界面截图用于说明产品实现。完整研究需要使用者配置原始资料、数据库与服务凭据；代码仓库不包含可直接运行全部研究的私有数据包。

The repository provides code, configuration examples, synthetic tests, evaluation methods and inspected screenshots. Full research requires configured source documents, databases and service credentials; a complete private research dataset is not bundled.

## 如何理解结果 / Reading the results

- 检索命中率对应指定问题和资料快照，不是答案正确率。Retrieval scores apply to the stated questions and corpus snapshot, not answer accuracy.
- 运行成本包含该批次的失败与恢复；缺失用量不按零计算。Run costs include failures and recovery within each measured batch; missing usage is not treated as zero.
- 人工修订报告展示协作交付能力，不能据此推断模型无需审阅。Human-amended reports demonstrate assisted delivery, not unattended model reliability.
- 算术校验与财务语义分别检查，因果、可比性及隐含假设仍需分析师复核。Arithmetic and financial interpretation are checked separately; analysts must review causality, comparability and assumptions.

示例资料库的 70 文档计数对应 2026-09-12。资料库截图拍摄于扩充前，画面中的 60 份文档对应较早快照。图片说明见[截图来源](images/README.md)。
The 70-document library count is dated September 12, 2026; the screenshot shows an earlier 60-document snapshot. See the [image notes](images/README.md).

## 数据与许可 / Data and licensing

凭据、私有上传、原始模型上下文和完整运行 trace 不随公开示例提供。仓库尚未选定统一开源许可证；第三方软件许可不自动赋予财务资料、图片和报告的再分发权。

Credentials, private uploads, raw model contexts and complete traces are not included in public examples. No repository-wide open-source license has been selected. Third-party software licenses do not automatically grant redistribution rights for financial documents, images or reports.

[运行说明](quickstart.zh-CN.md) · [Setup](quickstart.en.md)
