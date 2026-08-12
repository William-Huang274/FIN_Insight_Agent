# FIN 0.1.3 S1-B 当前金融对象库

日期：2026-08-12
状态：`engineering_pass_with_typed_gaps / S1_product_gate_open`

## 1. 本阶段实际解决了什么

S1-A 已经能把研究问题编译成 9 个 Evidence Slot / 17 个 facet，但它读取的是历史 candidate store。S1-B 把当前官方披露先保存为不可变 capture，再编译为“父文档 → 可检索子对象”，使查询、sparse、dense 和 rerank 后续共享同一批金融对象，而不是各自挑 chunk。

当前活动链为：

```mermaid
flowchart LR
    A["官方原始响应 / 历史语义对象 / PIT 行情"] --> B["不可变 capture 与 digest"]
    B --> C["SourceDocument parent"]
    C --> D["section / block / table child"]
    D --> E["typed 17-facet candidate runtime"]
    E --> F["Workbench 候选页"]
    F -. "尚未执行" .-> G["Evidence Gate / Evidence Pack"]
```

核心实现：

- `src/retrieval/financial_objects.py`：父子对象、raw SEC reparse、PIT 市场角色、旧 qrel alias crosswalk 和结构门。
- `src/ingestion/section_splitter.py`：处理 SEC 扁平正文中的 Item 边界，避免 Item 1A 吞入 Item 1B 等后续章节。
- `src/ingestion/official_source_capture.py`：HTTPS allowlist、capture-first、无凭据、字节/超时预算和不可变 attempt。
- `scripts/data_retrieval/build_current_financial_object_store.py`：唯一当前对象库构建入口。
- `scripts/data_retrieval/build_current_retrieval_snapshot.py`：让相同 17-facet 查询读取当前对象库，并把 qrel 只用于构建后评估。

## 2. 失败没有被抹掉

对象构建 R1 直接消费旧 flattened parsed text，产生最大 `202,705` 字符的单个 child，说明旧 parser 输出不能作为新对象边界。R1 保存在 `data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/attempts/r1_flattened_parsed_capture`；随后从同一 immutable raw SEC HTML 重新解析，才得到有界 section/block/table children。

官方补充源 live R1–R4 也分别保留：

- NVDA Q1 FY2027 10-Q 成功 capture，并进入当前对象库。
- Dell Q1 FY2027 transcript、Micron Q3 FY2026 prepared remarks 经官方 IR 页面确认真实存在，但当前产品 transport 在有界尝试中超时。
- R1 暴露隐藏 retry 计数不诚实，R3 暴露外层 timeout 与 retry 总预算不一致；当前 runner 已改成显式 transport、显式 retry ceiling、安全异常和不可变 attempt。R4 到停止线后不再追加轮试。

因此，Dell/Micron 不是“资料不存在”，而是当前产品 transport 未取得原始 PDF；它们归 S1-D 补源，不允许用搜索摘要冒充正文。

## 3. 当前工程结果

- 父文档：`28`
- retrieval children：`1,805`
- 来自 immutable current capture 的 children：`290`
- DELL / MU / NVDA / TSM children：`666 / 436 / 261 / 2`（另有 MSFT 关系背景 `440`）
- table children：`627`；不平衡表：`0`
- 最大 child：`8,449` 字符；超限 child：`0`
- 三案 17/17 lane 均非空，required source role 和身份/截至日硬约束均无失败。
- 旧 reviewed chunk 通过 evaluation-only lineage crosswalk 重定基，当前对象缺失为 `0`；旧 ID 不重新进入产品候选。

市场对象只证明三案 2026-06-24 PIT 行情链存在。它们缺 market cap、EV 和估值倍数，且早于 2026-08-06 research as-of，因此 `market_snapshot_is_not_valuation` 继续生效。

## 4. 业务审计：对象问题已收敛，排序问题尚未收敛

同一当前对象库下，reviewed target 进入候选池为 DELL=`6`、MU=`3`、NVDA=`4`。这不是研报质量分数，只用于把问题定位到对象覆盖或排序：

- DELL `cash_conversion` 第一名是“AI solutions 需求可能影响经营表现”的风险段，不是现金流或营运资本。
- MU `cash_conversion` 第一名是 GAAP/non-GAAP 对账表，不是现金转换机制。
- NVDA `demand durability` 第一名仍是 2024 年需求段；加入最新 10-Q 后 reviewed target 从前一快照的 `6` 降至 `4`，说明新鲜风险对象挤占了 lexical top-k，而不是最新文档没有进入库。
- DELL `policy` 第一名是直销与营销渠道描述，明显不是政策风险。
- relationship slot 常命中“同文出现/主题相关”，仍不能证明谁向谁采购、供应或分配。

这些问题属于 S1-C 的 sparse/dense/rerank 同候选比较。继续改父子对象或增加网页，不会自动让经济关系和现金机制排到前面。

## 5. S1-B 关闭边界与下一步

S1-B 记为工程通过但带 typed gaps；S1 整体仍未通过。下一项只做 S1-C：

1. 冻结这份 `1,805`-child store，sparse、dense 和 rerank 必须消费同一对象与同一 qrels。
2. 以具体业务错误衡量排序：旧期压新期、风险段冒充现金、主题共现冒充关系、通用股价风险冒充估值。
3. dense/rerank 只有在提高 required-slot target-in-pool 且不扩大错实体、错期和关系污染时才可进入 Runtime。
4. S1-C 后再由真实 residual gaps 驱动 S1-D；当前已知 S1-D 包括 Dell/Micron PDF transport、TSM 先进封装和新鲜估值数据。

当前不得宣称 Evidence Pack 已复编译、NumericFact、动态 Agentic Research 或研报内容质量通过。

## 6. 收口复证

- 活动基线：69 个 Python / 7 个前端文件，4 个 Runtime resources、3 个 detectors；旧版本和 attempt 活动引用为 0。
- Python：59 tests passed。
- Workbench：TypeScript 与 Vite production build 通过；无数据与真实数据挂载模式在桌面/移动端各 6/6 通过。
- 真实数据移动端第一次复证因长 lane ID/来源标签出现横向溢出而失败；当前消费者已允许有界换行，随后两种数据模式均通过。
- Secret scan：6,254 个文件、0 finding。
- 本阶段未调用模型；来源 live 仅限前述有界官方 capture R1–R4，达到停止线后未再轮试。
