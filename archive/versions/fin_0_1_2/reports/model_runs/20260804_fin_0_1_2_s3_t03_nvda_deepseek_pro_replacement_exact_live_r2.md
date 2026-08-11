# FIN 0.1.2 S3-T03 NVDA DeepSeek Pro replacement exact-live R2

- Status: `terminal_success_S3_T03_L1_pass_S3_T04_owner_reject`
- Execution identity: `fin012-s3-t03-nvda-replacement-r2`
- Admission: `fin012-s3-t03-nvda-replacement-exact-admission-r2`
- Admission digest: `1fd4c49be86c25079f0108f79d38e2832a102a9d6df91e3f0e2771a5f1cb3be0`
- Provider/model: `deepseek / deepseek-v4-pro`
- Base URL: `https://api.deepseek.com/beta`
- Input: frozen internal NVDA dogfood, as-of `2026-07-21T00:00:00Z`
- Complete input digest: `40625b4385cc97998bea6b9cd1e928dd49ac60f9078a3a884eb9581a53d48272`
- Stable business input digest: `a19743ffdaa63319a5381262adc9c5b04751abadc9bc4781561c1aa905b744fc`
- Expected topology: `6 logical nodes / 12 logical interactions / 3 local Fact receipts / 9 Provider calls and captures / 9 Artifacts on success`
- Hard ceiling: `9 calls / 60,000 input tokens / 10,000 output tokens / USD 0.06 / 900 seconds`
- Transport: `1 attempt per call / retry 0 / fallback 0 / provider hopping 0`
- Source network / external tools / live case-head writes: `0 / 0 / 0`
- Supervision: parent claim before child launch; capture-first local persistence; typed terminal on first credible failure.
- Stop rule: any new L1 after this replacement closes S3-T03 as honest-blocked. No third exact or second repair bundle.

## Authority

- Fresh admission authority: `configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_admission_authority_decision_v2_0.json`
- Issuance: `configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_fresh_exact_admission_issuance_v1_0.json`
- Execution authority: `configs/releases/fin_ia_0_1_2_s3_t03_nvda_replacement_exact_live_execution_authority_decision_v1_0.json`

## Result

- Terminal: `success`; business-promotable runtime result.
- Calls/captures/local receipts/Artifacts: `9 / 9 / 3 / 9`.
- Usage: `56,613 input / 2,296 output tokens`; estimated cost `USD 0.02662417`; wall clock `61.687s`.
- Retry/fallback/replay/relaunch: `0 / 0 / 0 / 0`.
- Result: `.codex_runtime/fin012-s3-t03-nvda-replacement-r2/execution-result.json`, SHA-256 `7f430356295c558f5158898d069905c3ce6d02b2585e87676c9252ebd5a3568c`.
- Independent L1: pass. NVDA identity and support refs passed; gross margin `74.99%` and operating margin `62.42%` independently recomputed.
- Paired product assessment: limited Agent gain, sparse `1/3` factual-cell coverage, L4 delivery fail. Owner rejected current NVDA R2; S3-T03 closes pass, S3-T04/S3 close honest-blocked.

Credentials, Authorization headers, cookies, Provider private reasoning and raw Provider response were excluded from persistence. No third exact or runtime repair was authorized.
