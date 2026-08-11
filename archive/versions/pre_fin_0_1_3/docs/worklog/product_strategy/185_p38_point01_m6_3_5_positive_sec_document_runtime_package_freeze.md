# 185 P38 Point 01 M6.3/M6.5 Positive SEC Document Runtime Package Freeze

日期：2026-07-13

> 该初版 package 已被 parser audit supersede；不得用于 receipt registration 或 live send。请以 [186 parser repair/refreeze](186_p38_point01_m6_3_5_parser_repair_refreeze.md) 的 v2 package digest 和状态为准。

## 审批与目标

用户批准：

```text
approve_m6_3_5_single_sec_document_positive_retrieval_parser_pilot_only
execution_state = package_build_authorized_live_send_pending_exact_digest_bound_receipt
```

本轮只实现并冻结 package，不执行 live send。

固定目标为 NVIDIA/NVDA 10-K：CIK `0001045810`、accession `0001045810-25-000023`、路径 `/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm`。固定 selector 为 Consolidated Statements of Income、In millions, except per share data、Revenue、Year Ended January 26, 2025。

reviewer 提供的 expected value/unit-scale 被视为 blind oracle：不写入 runtime policy、EvidenceRequest、tool plan、HTML parser、candidate selection 或失败修补；只可在未来一次真实结果产生后由 reviewer 对照。

## 已实现

- 新 fixed-store global one-shot approval policy 和人类 receipt template；旧 M6.2 receipt 与旧 User-Agent 使用授权均不可继承。
- exact `www.sec.gov/Archives/edgar/data/` client：单 GET、无 redirect/retry/fallback、无 directory listing/web search。
- M5.4 admission 在 prepare 后、send 前重验；M5.5 reservation 只允许一个 tool call。
- durable `prepared -> send_authorized -> send_started -> terminal` receipt。`send_started` crash 只能 reconciliation 为 `outcome_unknown`，不可重发。
- raw HTML 只在进程内解析，canonical store 只保存 source digest、table coordinate、selector 和 unpromoted candidate/parser/fact/trace lineage。
- selector 失败只写 `attempt_budget=0` typed terminal stop；成功主路径不写 RepairTicket，SourceHunter 未准入。

## Package freeze

```text
package_ref:      point01-m6-3-5-nvda-10k-positive-retrieval-parser-package-v1
package_digest:   8bf39724fb50d8b9fa66a2f4b99167798089b03bbfe534b03849b95b773877ea
manifest_digest:  3d7fc60fa130a3d48784b47d1d309c58c28b60d882fecce97e824ecb442acfa5
scope_digest:     da47cba16d622ce1ffb90caf5d67a4f622e27bb776f4a994774d93e75a18c877
```

human receipt template 不包含在 package hash 中，避免填入 nonce/expiry/digest 后自我失效。

## 验证

```text
python -m pytest tests/contract/test_point01_m6_3_5_positive_sec_document_execution.py tests/contract/test_point01_m6_3_5_positive_sec_document_pilot_design.py -q
# 10 passed

python scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot.py
# package_frozen_live_send_pending / external_call_count=0

$files = Get-ChildItem tests/contract -Filter 'test_point01_m6_*.py' | Select-Object -ExpandProperty FullName; python -m pytest $files -q
# 70 passed

python -m pytest tests/contract/test_point01_sqlite_store.py tests/contract/test_point01_runtime_facade.py -q
# 28 passed
```

未运行：live SEC GET、approval receipt registration、raw document persistence、Evidence promotion、Writer、Domain Judgment、M6.7、provider/model、full-chain、业务 Case mutation 和 legacy authority change。

## 下一步

总 reviewer `william（003）` 必须用上述 exact package/manifest/scope digests、新 one-shot nonce 和未来 UTC expiry 登记 fixed-store receipt，并再次确认本次 receipt 专属的 process-local `SEC_USER_AGENT` 使用范围。登记完成后仍须单独请求 live send；本 package 不自动发送。
