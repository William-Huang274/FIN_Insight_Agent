# FIN 0.1.2 S4-T05-B DELL 通用交付表面与 paired readiness

时间：2026-08-05
状态：`RC-P36-120 closed / L4 pass / paired readiness pass / formal paired and Owner pending`

## 为什么留在 T05-B

DELL 的唯一 Agent exact-live 已成功，独立 L1/L2 也已通过；失败只发生在最终本地交付层：内部 scope/period token、重复币种、英文 limitation 和 final preview 未绑定 Verifier。该缺口属于 T05-B 产品表面，不是 DeepSeek/Provider 故障，也不需要第二次 live。RC-P36-119 的 WWC 语义质量仍按原决定后传 T08–T10/S5，没有塞回本轮。

## 实现与审计纠偏

T04 renderer 的主体逻辑已经可复用，真正锁死 DELL 的是 NVDA-only case check、合同名和 `pass_NVDA` Verifier identity。此次没有复制一套 renderer，也没有改写 immutable exact result；既有 T04 公共入口保持原输出，新建 T05 current-case 受控后继，封闭支持 DELL/MU/NVDA，并显式绑定：

- input company、manifest ticker、各 Artifact input digest；
- workpaper/verification entity identity；
- 所有 Artifact 的 `s4_case_runtime.case_ticker`；
- Numeric row `entity_ref`、报告标题、preview case 与 local verifier case；
- preview digest、Verifier digest 与 source report/judgment digest。

泛化过程中发现一个早于 L4 的隐藏差异：DELL 的 WWC 可以引用本地已验证的派生毛利率/营业利润率，而旧 NVDA surface 只把 input authority 中的原始 Numeric 视为可用。处理方式不是放宽到全局 Numeric，而是只增加“同 Cell、已进入已验证 Numeric projection”的引用集合；unknown、cross-cell 和 cross-case 仍 fail closed。

## 零调用结果

从 immutable DELL exact result 重新物化后：

- preview digest=`46e4766db4c149a8871da00eae370da7409f24e21c24045081a2d4a7f30d291c`；
- 三 Cell Evidence/authority coverage=`3/3`；
- `__company_total__`、`FY2025-FY`、重复币种和未本地化 limitation=`0`；
- case identity=`pass_DELL`；
- final preview 与 local Verifier digest 双向绑定；
- exact result SHA 仍为 `b4edc0927e958b812c5e5dd04d982defa97e64255d24e3a569e5311b78f5dd32`；
- model/Provider/network/source/external tool/exact rerun=`0/0/0/0/0/0`。

同一 input digest/head 已物化一条不同 Run、不同 Artifact 的零调用 deterministic authority-inventory baseline。Agent=`9 Artifacts`，baseline=`1 Artifact`，runs distinct，状态为 `ready_for_formal_paired_assessment`；本轮没有把 readiness 冒充 formal paired，也没有执行 Owner decision。

DELL/MU/NVDA 同一 renderer fixture、cross-case、runtime identity、Numeric identity、input lineage、preview/verifier digest 和 pair binding mutation，以及冻结 NVDA T04 输出不漂移，focused=`17 passed`。

## 当前产品边界

RC-P36-120 已关闭，DELL L4 通过；但 DELL current R2 仍为 false，因为正式 paired L1–L4 和 Owner acceptance 尚未执行。T05-C MU 继续 blocked。下一项限定为零模型的正式 paired assessment 与 Owner decision；通过并由用户接受后，才能关闭 T05-B 并进入 T05-C。

`FIN-0.1.2-S4-T05-B-DELL-FORMAL-PAIRED-L1-L4-ASSESSMENT-AND-OWNER-DECISION`
