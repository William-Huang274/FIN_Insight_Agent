# 827 — FIN 0.1.3 S1 DELL 定向补源 authority

日期：2026-08-10

状态：fresh authority issued_unconsumed

clean/synced commit=`49b33afb559d1de85885051876ef51f80c780caf`；clean proof=`823685fc0946bd22f1d183fa83a103dc9f234199f1fa52233e1e24b60cd99f8d`；Project OS scope `FIN_0_1_3_S1_DELL_TARGETED_SOURCE_SUPPLEMENT_EXACT_ONCE` preflight=`pass／0 blocker`。

唯一 Run=`fin013_s1_dell_targeted_source_e7d77ba0d1824fc2a6e4`，authority digest=`e9b3819562ef02590efd3669cec3e41cd1ab6175c85ea02ffa60f6e42f0a1d46`，有效期 24 小时。权限只允许四个已绑定 route 各一次：Dell Q1 FY27 earnings transcript、Micron Q3 FY26 earnings slides、TSMC Q1 2026 transcript、Nasdaq DELL 2026-08-06 historical row。

预算为 `4 source network／0 retry／0 fallback／0 Provider search／0 model／0 business promotion`。每个请求和响应必须先进入受限 capture store；本地 parser/anchor 之后才允许形成 source material。第三方证据仍为 bounded read-through，市场行仍为 independent PIT。

签发没有访问网络或模型。下一步必须先提交并推送 authority，再运行一次 preflight，随后 exact-once 消费。任何 transport、parser、anchor 或 expected-fragment gap 都保留为 terminal 结果并停止，不自动重试或进入 DeepSeek。
