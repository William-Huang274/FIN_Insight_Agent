# 813 — FIN 0.1.3 S2 fixed-pack successor runtime implementation

日期：2026-08-10

状态：working-tree implementation passed；clean independent proof pending

第 5 步没有复用旧 Experiment A。旧实验只有 DELL／MU／NVDA、33 条 Evidence，并把模型输出锁进过窄的数字表面合同；本轮 successor 直接消费当前六份 immutable Pack，共 84 条 Evidence 和 126 个显式 gap。28 条 rejected item 不进入模型输入。DELL／MU／NVDA 带审定原始文本；ORCL／ASML／ANET 只有结构化 Metric 和审定 claim，因此后续报告深度必须连同输入密度一起解释，不能把差异全部记到 DeepSeek。

新的模型／Harness 分工为：模型可见、分析和引用 source-bound exact numbers，负责经济机制、反证和叙事；Harness 保留公司身份、期间、币种、单位、关系方向、Evidence alias、numeric surface 检查和最终晋升权。Harness 不是“把模型句子超级拼装成研报”，模型仍写完整报告；但任何未绑定 Evidence 的数字、未知 alias 或证据角色越权只会保留为 raw finding，不能进入产品 Artifact。

同一冻结输入上建立两条可比较路径：一次 direct-model report baseline；以及 Lead、六个研究家族 Specialist、跨单元综合、初稿、红队、终稿和 Verifier。每案恰好 13 次调用来自这些角色，不是人为设定的质量指标；未来研究单元若有充分证据可扩展到 8 个，但不能靠增加调用数掩盖 Evidence Pack 缺口。

当前零调用验证覆盖六案 `6 × 13` 完整 fake chain、request/capture-first、exact-once admission、同输入 digest、provider 中断 terminalization、case/date/source-material/capacity/rejected-item mutations、未知 alias 与无依据数字。focused tests=`15 passed`；真实网络、DeepSeek、外部工具和业务晋升均为 0。

下一步先提交并推送实现，再从 clean commit 生成独立六案 zero-call proof。proof 通过后只签发一次 DELL fixed-pack canary；不会直接烧六案 campaign。DELL 若出现 transport/空输出等 L1 就停止；若只是结构或内容 finding，完整 13 节点仍保留，随后做 L1/L2 与 Q1–Q8 诊断，再决定其余五案。动态 Agentic Research 是另一个实验，仍等待 RC-P36-168 和外源 source-route 质量处置。
