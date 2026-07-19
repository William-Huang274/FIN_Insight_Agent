# 184 P38 Point 01 M6.3/M6.5 Positive SEC Document Pilot Design

日期：2026-07-13

## 结论

已完成不触网的正向 document retrieval/parser pilot 设计冻结，状态为：

```text
design_frozen_pending_separate_human_execution_approval
```

这不是新的外部执行授权，也不重用已消费的 M6.2 metadata receipt。

## 严格范围

- 未来只能针对人工预先指定的单一 SEC Archives 文档：exact CIK、accession、primary document path、form、report period 和 table selector 缺一不可。
- 必须建立新的 fixed-store total-reviewer receipt，绑定新的 approval id、one-shot nonce、UTC expiry、positive-pilot package digest 和 document-locator scope digest；发送前原子消费。
- 单次读取仅允许 `www.sec.gov/Archives/edgar/data/`；目录浏览、web search、issuer/host 替换、retry 与 fallback 均禁止。
- 原始文档只能留在 isolated temporary store，不能进入 Git 或正式 Evidence store。

## 预期的唯一正向输出

若未来授权的读取和解析均成功，M6.3/M6.5 只能产生一个带 source digest、table coordinate、unit、scale、period 和 parent digest 的 unpromoted candidate/parser/fact/trace chain。它不可以 promotion、citation、Writer、Domain Judgment、M6.7 或 full-chain input。

M6.4 不在成功主路径虚构 RepairTicket；读取或解析失败只允许 `attempt_budget=0` 的 typed terminal stop，SourceHunter 仍未授权。

## 本轮验证

```text
python scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot_design_lint.py
python -m pytest tests/contract/test_point01_m6_3_5_positive_sec_document_pilot_design.py -q
```

两项均为本地设计校验：external/tool/parser/model/evidence-promotion count 均为 0。后续必须先完成 positive runtime package、生成 exact digest，并由总 reviewer 独立登记新 receipt；不得以之前已经 consumed 的 metadata receipt 续期或重放。
