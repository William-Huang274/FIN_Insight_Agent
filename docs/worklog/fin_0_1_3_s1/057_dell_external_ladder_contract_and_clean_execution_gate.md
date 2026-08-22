# 057｜DELL 完整外源阶梯合同与 clean execution gate

日期：2026-08-22
阶段：FIN 0.1.3 / S1 外源补源（CandidateDecision、Evidence Gate、S2 successor 与 S3 均未授权）

## 本轮目标

把 056 已确认的七类 DELL 研究缺口，从“内部候选不足”推进到一条可真实执行、可回放、不会把搜索摘要冒充证据的外源阶梯。该阶梯不是挑几个容易访问的官方页面，而是逐命题覆盖：主体／客户／供应商官方披露、行业机构与市场跟踪、产品／采购／渠道／客户部署、可信媒体／公开分析与反方。

## 已实现

1. 新增 provider-neutral 外源合同，验证 28 个查询单元、七命题覆盖、四类来源、关系方向、期望业务输出、来源注册表、公平抓取预算和 task-specific `TokenBudgetBasis`。
2. Tencent WSA SearchPro 标准版只作为 locator。每次请求先保存无凭据的安全请求，再保存原始响应，搜索摘要、provider score 和 provider date 均没有 Evidence、引用或数字权威。
3. URL 规范化移除跟踪和敏感查询参数，拒绝 credential URL、localhost、私网／保留地址；只有受审域名注册表中的结果才可进入原文抓取 shortlist。
4. shortlist 按 query、domain 和 global ceiling 公平轮转，避免单一 customer／domain 抢光预算；没有进入 shortlist 的结果保留明确拒绝原因。
5. 原文使用统一 capture-first 下载器，逐路保留请求、完整响应或 typed transport failure；0 retry、0 模型调用，部分失败不会抹掉其他成功来源。
6. 网页与 PDF 进入统一 candidate-only source object。发布日期必须从原始 HTML／PDF／URL adjudicate；provider 日期只能佐证，不能单独晋升。PDF 明确记录是否执行 OCR，当前通用 PDF 路径不冒充 OCR。
7. 原文片段按查询与 required output 生成确定性 candidate proposal，但仍须后续 CandidateDecision 与 Evidence Gate。PDF 与 HTML 现在经过同一个 bounded evidence gate，不会出现“PDF 抓到了却永远无法准入”的合同断缝。
8. 新 runner 要求 clean worktree、exact-once attempt 和新 public output，绑定 commit、计划 digest、私有 terminal result、provider receipts、original capture 和 public projection。

## 28 个查询的业务覆盖

每个命题各四条查询：

- 价格／配置：Dell 官方配置、行业 ASP／mix、渠道／采购报价、价格代理与替代反方；
- 销量：发行人 units／shipment、行业销量与份额、部署／采购数量、backlog conversion 反方；
- PVM：发行人收入与 mix、行业金额／台数分化、交易价格与数量代理、其他解释；
- 客户需求：客户官方预算／部署、行业需求持续性、具体部署案例、取消／集中度／提前采购反方；
- 供应链：NVIDIA／Micron／TSMC 官方供给、HBM／CoWoS 行业时点、渠道交期、分配与延迟反方；
- 价值池：Dell margin、BOM／供应商成本代理、产品／渠道交易代理、OEM 与上游价值分配反方；
- 反方／WWC：发行人风险、行业下行、部署取消／库存折价、跨来源 what-would-change。

## 当前验证

- 外源、网页／PDF、Evidence Gate 与 runner 定向测试：`16 passed`；
- 全仓：`1012 passed`，仅两条既有 SWIG deprecation warning；
- `compileall` 通过；
- active baseline verifier 通过，0 forbidden reference；
- repository secret scan：7,599 files，0 findings；
- 0 Provider／网络／模型调用。

## 仍未证明

- Tencent 当前标准版对这 28 条新查询的实际 locator 质量；
- 原文成功率、日期恢复率、HTML／PDF 解析率；
- 任何 candidate 的业务正确性与 Evidence admission；
- 七命题的 external route exhaustion 或 public-information gap；
- current Pack、S2 派生值／区间／情景、EvidencePackReadiness；
- DELL 动态单单元及后续多 Agent／Writer／泛化。

下一步先提交并推送本实现，使 formal run 绑定 clean commit；随后只执行一次 `dell-external-ladder-r1`。若搜索供应商或原文传输失败，保留失败并修最早责任层，不能把失败写成免费公开资料不存在。
