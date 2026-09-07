# 058 DELL 动态五单元 R2 部分完成与分析预算失败

日期：2026-08-17

## 结果

R2 正确复用了 R1 的自然 Planner 和当前 S1/S2，没有重新检索、重新构造 NumericFact 或补入新 Evidence。它实际尝试 7 次模型调用，需求质量和经营表现两个单元完成“分析草稿＋严格交卷”并通过本地合同；价值获取、现金转换和反方证据三个单元都在分析阶段用尽 8,000 completion token，因此综合没有执行。

这不是网络问题。三个失败响应均为 HTTP 200：价值获取和反方单元的 8,000 token 全部消耗在推理，未形成可见正文；现金转换使用 7,286 token 推理，只留下被截断的草稿。0 retry、0 fallback，R2 结果和 capture 保持不可变。

## 已经证明的业务内容

- 需求质量：模型没有把 backlog 直接等同未来收入，明确保留提前锁货、客户准备度和订单到出货非线性。
- 经营表现：模型只在公司整体层面判断收入、利润和现金改善，明确拒绝把利润改善直接归因于 AI 服务器；并用毛利率下降、营业利润率上升提示规模／经营杠杆替代解释。
- 两个局部判断没有发现新的金融 L1，但三个单元和综合未完成，正式五单元 L1 与八维内容质量均不能评分。

## 根因

分析与交卷虽已分离，但分析请求仍携带严格交卷 schema、重复的 Evidence/Numeric 目录和完整的补源路由诊断。它们对形成研究判断并非都必要，却与 DeepSeek 的隐藏推理共享同一 8,000-token 输出预算。R2 因而暴露的是同一个结构问题，不是三个字段错误，也不是 S1/S2、Skill、图谱或金融 Validator 失败。

公开结果还有一个非阻断语义问题：`execution.current_S1_S2_executed=false/reused=true` 是正确的，但 acceptance 中名为 `current_S1_S2_EvidenceResponse_executed` 的字段因复用结果存在而写成 true。R2 不修改，后续版本须区分“结果可用”和“本轮执行”。

## 下一处置

1. 为分析阶段编译真正紧凑的 cell-local 视图，不移除事实、数值关系、方法、图上下文或 typed gap，只去掉交卷 schema、重复目录和过度路由诊断。
2. 建立通用的部分节点恢复：复用 R2 已验证的需求和经营判断，只执行价值、现金、反方三组分析／交卷及两次综合，最多 8 次新调用。
3. 用 R2 immutable request 做零调用等价性、长度、跨 cell/case、引用和 gap mutation；不靠一次 live 猜修复是否正确。
4. 分析节点复用现有 16k GA max-thinking profile，严格交卷仍为 2k non-thinking；不改变金融合同、不增加 Evidence、不手工改模型观点。
5. 新 successor 若再出现同类全新容量失败，不自动进入第三次加预算，而转为模型/profile/动作面决策。

## 边界

R2 不是五单元通过，也不是完整研报。MU、NVDA、留出案例、qualified-human、S3 acceptance、Workbench 发布和 release 仍未授权。
