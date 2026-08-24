# S2 工作记录 010：Decimal 隔离与产品桥最终边界

日期：2026-08-25

状态：`numeric_runtime_isolation_pass / bridge_consumer_pass / PVM_product_profit_and_S2_qualification_open`

## 1. S2 当前实际能力

DELL quantitative program v1.1 保持 `38` 个 reported facts、`27` 个 deterministic derived
metrics、`2` 个 research estimates、`2` 个 scenarios 和 `9` 个 typed gaps。产品桥提供可精确复算
的 AI server revenue／ISG／company revenue 表面，并把 `13` 个 observations、`7` 个 derivations、
`4` 个 open gaps 交给动态 Agent；不凭桥接上下文创建新的 NumericFact。

## 2. 关闭进程级 Decimal 副作用

复核发现 `product_value_bridge.py` 在 import 时执行 `getcontext().prec = 36`。这会修改整个 Python
进程的 Decimal context，使无关模块的金融计算精度被静默改变。它属于 S2 数值运行时隔离缺陷，
不是一个可忽略的代码风格问题。

当前实现删除全局赋值，只在数值规范化和 ratio 公式内部使用 36 位 `localcontext()`。回归测试先
把调用者精度设为 29，再 import 产品桥，结果仍为 29；现有 bridge derivations 与摘要保持稳定。

## 3. PVM 与产品利润仍然 fail closed

当前公开输入没有 Dell 公司级 units、ASP、mix，也没有 AI 产品的成本／opex 归因。因此：

- bundle price 或采购配置不能冒充公司 ASP；
- 四套采购系统不能冒充 Dell 公司出货量或 share；
- 已公开的 Dell↔NVIDIA 合作不能推导私有 allocation；
- PVM contribution、AI product operating profit 和 product margin 继续为 `null`。

这说明 S2 的“事实→公式→typed gap→Agent handoff”链已经工作，但证据不足的经济桥没有被
捏造。`S2_pass=false` 与 product acceptance 保持 false。

## 4. R17 与下一门

R17 已有作者分离的 fresh independent content pass；它是 S3 Writer 内容审阅，不是 S2 数值
资格或 qualified-human 签字。没有 material finding，不开 R18。当前下一门是对整合后的 clean
commit 做全新只读审计；只有出现 material finding 才回到所属阶段开 successor。
