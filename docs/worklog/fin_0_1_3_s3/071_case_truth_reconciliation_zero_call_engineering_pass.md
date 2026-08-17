# 071 Case Truth reconciliation：零调用工程门通过

日期：2026-08-17

## 为什么需要这一层

DELL R7 已经能形成完整五单元报告，但 Operating 和 Counterevidence 把当前 Case 已经存在的 AI server revenue、orders、backlog 写成缺失，Synthesis 又把错误前提提升为跨单元 conflict。旧合同只能证明模型选择了合法 Evidence ref，不能证明“未披露／不存在”这一负面事实为真，也没有区分“本 cell 没看见”和“全 case 不存在”。

## 本轮实现

- 从当前 reviewed Evidence facet、NumericFact、NumericRelation、source-bound qualitative fact、typed gap 与 product-profit bridge boundary 编译完整 `CaseTruthPacket`；
- 每个 cell 单独记录可见事实、可见 gap、可见 bridge boundary 和本地不可见但全案已存在的事实；
- 模型只承担 semantic reconciliation：逐项映射 thesis、mechanism、counterargument、WWC 及 synthesis premise 的存在、缺失、本地不可见或未解决状态；它不能改写研究或创造事实；
- Harness 穷尽校验每个 material surface。漏项、未知 alias、跨 Case、错误 digest、把已存在事实写成缺失、把本地不可见写成已见都 fail closed；
- cell 与 synthesis 两级 receipt 都通过后，v1.1 report 才能物化。历史 v1.0 路径保持兼容；
- 完整本地权威包不发送给模型。紧凑模型视图按共享来源语义分组，并省略重复的 cell-hidden 列表，但绑定完整 packet digest。DELL 完整包约 `49,568` 字符，模型视图约 `26,671`，包含 15 个待分类 surface 的消息约 `33,092`。

## 正式证明结果

绑定 clean/synced implementation commit `2e56eb22d66bfb368684d9eea16ca73a19f5116b` 的 exact-once zero-call R1 通过：

- R7 三个 `asserted_absent_but_present_in_case` 精确检出；
- 产品到公司／分部利润桥的真实 typed gap 被合法保留；
- synthesis 基于 orders／backlog 假缺失制造的 conflict 被拒绝，且下游 synthesis gate fail closed；
- DELL／MU／NVDA 分别编译 61／49／55 个 presence alias，排列变化不改 digest；
- 跨 Case packet 复用失败关闭；异质工业留出保持 external owner、presence+gap coexistence 和 typed-gap-only absence；
- DeepSeek strict tool projection 没有削弱金融合同；
- 0 model、provider、network、embedding、retry、candidate promotion 或 publication。

全仓为 `484 passed`，compileall 通过，active baseline=`137 Python / 8 frontend / 11 runtime / 0 unresolved`，secret scan=`6,836 / 0`。

## 没有被证明的内容

fake semantic mapping 只证明本地判断器，不证明 DeepSeek 能自然、完整地识别十五个 surface。R7 没有被修复；DELL 五单元 L1/L2、八维、paired、qualified-human、MU/NVDA／留出泛化、S3 acceptance、Workbench publication 和 release 均为 false。

## 下一门

只签发一条低思考 natural semantic reconciliation canary：读取 R7 不可变 claim surfaces 与紧凑 Case Truth view，不修文、不生成报告、0 retry。它必须穷尽 15 个 material surface，识别三条 false absence，保留真实利润桥 gap，且不制造新错误。通过后才决定 Operating／Counterevidence／Synthesis 的最小 successor。
