# FIN 0.1.2 S4-T05-B DELL Search fresh proof 与 admission authority

日期：2026-08-05

结论：DELL current Search 的 fresh zero-call engineering proof 与 admission authority decision 已通过；只允许下一步签发 Search admission。本轮没有签发 admission、访问真实来源、调用 DeepSeek 或建立 DELL R2。

T05-B 的执行顺序作了必要纠正。Agent exact input 必须绑定真实 Search terminal 编译的 current Evidence Pack，因此 Search 和 Agent admission 不能在同一时点决定。子序列固定为 Search proof/authority、Search issuance、Search live、Evidence Pack/Agent input、Agent proof/authority、Agent live/L1/paired/Owner；这不改变 FIN 0.1.2 或 S4/T05 范围。

两个独立 disposable root 都从 current DELL 三份 EvidenceRequest 启动，生成不同 Run/Attempt，normalized 结果一致。三 Cell accepted/rejected=`6/9、6/0、6/3`；每次 `1` 个模拟官方来源请求、`6` 次真实本地 BM25/SQL/Graph、`8` 个 capture、`18` 个 accepted candidate，真实 source/model/provider/cost/业务 Artifact 均为 0。CIK、三份 request digest、HTTPS locator/allowlist 与 `2 source / 8 local / retry 0 / fallback 1 / 300s / model/provider/cost 0` 预算已精确校验。

审计在签发前发现 DELL IR fallback 指向直接 PDF，而冻结共享 parser 只解析 HTML anchor。若不处理，主 SEC 路径可用但 fallback 名存实亡。为不破坏已内容寻址冻结的 T03 NVDA runner 和 T05-A bindings，新建 T05 case-aware successor：DELL direct PDF 只在官方 HTTPS allowlist、content-type 与 PDF magic 均正确、Last-Modified 可解析且不晚于 as-of 时形成官方 identity；request/response 继续在解析前保存。非 PDF、缺日期、未来日期和跨案例 admission mutation 均 fail closed。

focused 实现测试在决策物化前为 `7 passed / 1 deselected`。下一步仅签发一份 fresh DELL Search admission；Search exact-live 仍需之后单独执行，且必须固定单一 runtime root。有效来源没有合格结果时保留 typed gap；项目内 source/adapter/parser/capture/budget 故障则终止，不自动第二次搜索。Agent admission、DeepSeek、paired、Owner、MU 与 post-transfer NVDA 都未授权。
