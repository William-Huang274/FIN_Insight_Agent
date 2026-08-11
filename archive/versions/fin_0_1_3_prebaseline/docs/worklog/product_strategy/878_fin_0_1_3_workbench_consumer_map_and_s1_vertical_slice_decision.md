# 878 — FIN 0.1.3 Workbench 消费者总图与第一条 S1 产品纵切

日期：2026-08-11

## 用户目标

在不删除代码的前提下，把仓库从“机器或许能读、用户和后续 Agent 难以找到主干”的状态收敛为可维护基线；先看清 Workbench 路由、服务、Runtime、资源和测试消费者，再晋升一条真实 S1 能力，避免继续复制 runner。

## 新发现与主动纠偏

最初计划考虑复用 `/cases/{case_id}/local-research-preview`。进一步审计证明该路径是固定 P36 多公司十单元 preview，而 Case contract 没有 ticker/entity identity。若继续复用，会让 case-aware 的 URL 掩盖 non-case-aware 的业务语义，形成新债务。

因此改为版本中立的 current research Evidence Pack API。纠偏没有改变用户目标，也没有扩大到新检索、模型或 UI 重写。

## 已完成

- 盘点 109 个 FastAPI route，并按 frontdoor、router、service、Runtime、resource、frontend consumer 和生命周期归组。
- 明确 `/current`、`/tasks|cases`、`/next`、`/legacy` 四套产品表面及各自真实状态。
- 修复 `/next` 已有前端但后端缺 SPA fallback 的直接访问缺口。
- 对 13 个 unknown 文件逐一裁决：9 个 package root、1 个动态 test helper、3 个 quarantine 候选。
- 审计 S1 generalization、DELL vertical、six-case candidate 和 local Evidence Pack 候选。
- 新建 `ResearchEvidencePackService` 与两条只读 API。
- 新建 33-resource clean-baseline successor registry，不改写历史 31-resource registry。
- 真实挂载原仓库 private data，DELL=`15 Evidence/16 gaps`、MU=`16/13`、NVDA=`14/13`，三案 HTTP 200。
- 新增权限、unknown case、digest mutation、source binding、raw material isolation 和 real route tests。

## 真实业务表现

- DELL 已能表达“AI 订单和收入同季披露可观察转换”，同时保留取消率、交付周期和 backlog 明细缺口。
- MU 能使用 Dell 服务器订单作为需求旁证，但明确禁止把该金额直接归因给 Micron。
- NVDA 能使用下游系统订单作为独立旁证，但不虚构 GPU 金额或交付节奏。
- 三案都保留先进封装容量／分配等真实 residual gaps。

这比旧 preview 的固定模板更接近真实金融研究控制面，但还不是动态研究或完整报告。

## 验证

- 新 Evidence Pack、registry 与 `/next` changed-surface 合同：`23 passed`；其中新
  Evidence Pack 与 registry 合同为 `18 passed`。
- 原 private data 三案 read-only mount：3/3 HTTP 200，Pack digest 与 source binding 全通过。
- 真实 model/provider/live-network：`0/0/0`。
- 文件删除／批量移动：`0/0`。

扩大回归另有两组诚实保留的既存债务：

- Workbench／VT4 快照：`201 passed / 8 failed`。失败位于旧前端文本契约、VT4 fixture
  状态与 legacy rollback fallback，没有进入新增 router/service。
- S1 历史候选快照：`28 passed / 1 skipped / 11 failed / 9 errors`。失败主要来自旧
  candidate/index 测试把 private artifacts 硬绑定到 checkout-local `data`，而干净工作树
  只通过显式 DataRoot 挂载复用原数据。

本轮不复制私有数据、不改旧测试语义来制造全绿。路径债务登记为
`RC-REPO-002`，在对应候选晋升到产品 Runtime 时迁移；它不阻断已经使用
`RuntimePathRegistry` 的第一条 S1 产品 API。

## 决策

第一条 S1 纵切记为 `product_api_promoted_ui_pending`，不能记为 FIN 0.1.3 产品切换完成。只有 typed Case subject、Case-to-Pack binding、一个真实 Workbench UI consumer、三案内容可读性检查和旧 preview consumer=0 后，才允许降级或归档固定 P36 preview。

## 下一步

`ADD_TYPED_CASE_SUBJECT_AND_CASE_TO_CURRENT_RESEARCH_PACK_BINDING_THEN_CONNECT_ONE_WORKBENCH_EVIDENCE_VIEW_WITHOUT_REBUILDING_RETRIEVAL`

具体先做 typed entity/ticker contract 与显式 pack binding，再让一个 Workbench Evidence 页面消费新 API。S2/S3、FIN 0.1.2 和 legacy 迁移依次后置；不新增专用 runner，不自动恢复 DeepSeek live。
