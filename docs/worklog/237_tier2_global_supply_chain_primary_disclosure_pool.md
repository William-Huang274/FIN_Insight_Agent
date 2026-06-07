# 237 Tier2 Global Supply Chain Primary Disclosure Pool

## Prompt

用户指出不能把 Samsung、Foxconn、SK hynix 等非美供应链龙头直接标成 source gap。美国龙头公司大量依赖全球供应链，非美上市公司的同口径年报、交易所公告、监管披露应当与美国本土上市公司公开披露同优先级处理。

## Reasoning And Decision

- 原先未纳入版本控制的 Tier2 草案写成 SEC-only，并把 Samsung Electronics、SK hynix、Hon Hai / Foxconn、CATL 放进 `external_source_gaps`。这会导致 AI 基建、半导体、EV、储能、消费电子等问题缺少真实上游/下游主披露。
- 口径修正为：SEC / EDGAR 公司继续走 SEC ingestion；非美上市公司如果有官方年报、交易所公告或监管披露入口，就进入 `global_public_disclosure` 主证据路径，不再作为 gap。
- 新闻、官网网页、GDELT、Common Crawl、私有公司页面仍是线索源，不能直接进入高置信关系图谱。

## Work Completed

- 新增 Tier2 供应链补充配置：
  - `configs/data_sources/tier2_supply_chain_supplements_v0_1.yaml`
- 新增 Tier2 manifest 构建器：
  - `scripts/data_expansion/build_supply_chain_supplement_manifest.py`
- 新增测试：
  - `tests/test_supply_chain_supplement_manifest.py`
- 更新 source family / ingestion profile：
  - `global_public_annual_report`
  - `global_public_interim_report`
  - `tier2_global_supply_chain_staging`
- 更新执行文档和 master checklist，明确非美公开披露是主证据，不是 source gap。

## Result And Evidence

构建命令：

```powershell
python scripts\data_expansion\build_supply_chain_supplement_manifest.py
```

结果：

- base Tier1：`505` 家。
- Tier2：`98` 家。
- Tier1 + Tier2：`603` 家。
- Tier2 SEC-download eligible：`83` 家。
- Tier2 global-public disclosure：`15` 家。
- 合并池 SEC-download eligible：`588` 家。

Tier2 全球公开披露池覆盖：

- 韩国 DART / 公司 IR：Samsung Electronics、SK hynix、LG Energy Solution。
- 台湾 MOPS / 公司 IR：Hon Hai / Foxconn、Quanta、Wistron、Delta Electronics。
- 中国 SZSE / CNINFO / 公司 IR：CATL。
- HKEX / 公司 IR：BYD。
- 日本 EDINET / 公司 IR：Panasonic、Tokyo Electron、Advantest、DISCO、Renesas。
- 欧洲公司 IR：Infineon。

验证命令：

```powershell
python scripts\data_expansion\audit_universe_tiers.py --manifest data\manifests\tier2_supply_chain_supplement_manifest.jsonl --expected-count 98 --summary-output data\manifests\tier2_supply_chain_supplement_audit_v0_1.json
python scripts\data_expansion\audit_universe_tiers.py --manifest data\manifests\tier1_plus_tier2_supply_chain_manifest.jsonl --expected-count 603 --summary-output data\manifests\tier1_plus_tier2_supply_chain_audit_v0_1.json
python -m pytest tests\test_supply_chain_supplement_manifest.py -q
```

验证结果：

- Tier2 manifest audit：pass，`98` 家，`15` missing CIK 但都为 `global_public_download_eligible=true`。
- Tier1+Tier2 combined audit：pass，`603` 家。
- 单测：`1 passed`。

## Follow-Up

- 下一步先实现 global public disclosure downloader/parser，而不是直接下载 SEC-only 数据：
  - KR DART business report。
  - TW MOPS annual / quarterly report。
  - JP EDINET annual securities report。
  - HKEX / SZSE / CNINFO annual and interim report。
  - EU official annual report profile。
- 下载和解析后，必须把这些证据落到与 SEC evidence 等价但来源分开的 typed chunks / evidence rows。
- R3/R4/R5 接关系图谱时，非美主披露里的客户、供应商、合同、风险和产能描述可以参与 relationship edge 候选，但必须保留 `source_family` 和 `disclosure_profile`。

## Safety Notes

- 没有写入 API key、SSH 密码或私有 token。
- Tier2 manifest 是小型公开公司池合同，不包含私有抓取数据或大规模原始文件。
- 非美披露入口 URL 只作为 source locator；后续引用必须指向实际报告或交易所/监管文件。
