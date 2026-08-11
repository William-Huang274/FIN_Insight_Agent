# 848 — FIN 0.1.3 S2 selected-Evidence 数字共编 clean proof

日期：2026-08-11

状态：双 clean archive／fresh process 零调用复证通过；自然模型与产品验收未执行

## 这次真正证明了什么

提交 `73efd2c8323bf1bec2737137fbc89b97d6b5b836` 的两个独立 Git archive 各自在一个全新 Python 进程中读取同一份临时、摘要绑定的六案 Evidence Pack。两份 worker 输出逐字节一致，DELL／MU／NVDA／ORCL／ASML／ANET 的 candidate、stable fact、presentation、formula、冲突和三类节点视图与已冻结实现结果完全相同。

DELL successor 仍保留 27 份 raw source 的私有审计摘要，但模型输入中没有 `source_text` 字段，也没有已知原始长句。最终本地门在两个干净进程中都证明：合法 `NUM` 展示可以通过；`$4.1 billion` 错语义、`$43,842 million` 错单位和把 `437.65` 收盘价写成目标价都会在 semantic Verifier 已 pass 的情况下继续 hard fail。跨案例身份污染和缺少表格父级口径也 fail closed。

全过程 model／provider／network／source／retry=`0／0／0／0／0`，凭据环境变量被清除，临时私有输入没有写入仓库，两个临时目录在结果物化前已删除。

## 为什么有一个失败尝试

R1 在第一个 clean worker 汇总结果时停止。原因不是数字共编 Runtime 或任何案例失败，而是证明脚本从错误层级读取 `ambiguity_downgraded_count`，随后预检又发现 `presentation_receipt_count` 同样应从 typed summary 读取。R1 已以独立失败工件保留；只修 proof reader 后，以新提交和新 attempt ID 执行 R2。没有隐藏失败，也没有重跑模型或数据源。

## 业务含义与边界

现在可以说：这套“已选证据 → 数字候选 → 权威事实／展示 → 分层节点视图 → 最终本地门”不是只在当前工作目录偶然成立，六案例在干净代码和新进程中可重复。RC-P36-170 的项目侧结构修复因此进入 `clean proof passed`。

仍不能说：DeepSeek 自然输出已经遵守新输入面、DELL 报告已修好、研究内容质量已再次提升、Owner 已接受或 FIN 0.1.3 可发布。下一项只能先做一次零调用的最小自然节点 canary authority decision；是否实际调用模型、是否值得跑 DELL 全链，必须继续分开决定。

机器结果：`configs/releases/fin_ia_0_1_3_s2_selected_evidence_numeric_candidate_cocompilation_clean_independent_proof_v1_0.json`。
