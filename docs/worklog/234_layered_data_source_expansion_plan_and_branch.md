# 234 Layered Data Source Expansion Plan And Branch

## Prompt

用户要求把下一阶段五层数据源扩容方案落成文档，并把此前主线更新的脚本、文档 staged，然后从当前状态 fork 一个新分支做下一阶段。

## Decision

下一阶段不以“接更多数据源”为目标，而以分层数据合同和证据边界为目标。数据源按五层推进：

1. SEC / earnings / transcript：主证据。
2. 市场数据和一致预期：估值和预期差。
3. 行业数据：sector-depth。
4. 供应链 / 客户 / 供应商数据：relationship graph。
5. 新闻 / 公告 / GDELT / Common Crawl：线索发现。

计划文档放在 `docs/architecture/`，因为它是下一阶段架构路线，不是单次实验日志。

## Work Completed

- 新增 `docs/architecture/layered_data_source_expansion_plan.zh-CN.md`。
- 更新 `docs/architecture/README.md`，加入分层数据源扩容计划入口。
- 计划文档定义：
  - Tier 0 / Tier 1 / Tier 2 / Tier 3 公司池扩容。
  - 五层数据源的落地方式、schema、接入顺序和门控。
  - relationship edge 的类型、置信度、可引用边界。
  - 新闻线索不得直接升级为高置信结论。
  - 扩容后 S0 / S3 / market / industry / relationship / news / memo gate。

## Verification

- 本轮只新增/更新文档，未运行代码测试。
- 后续阶段开始前需要先确认 staged scope，再在新分支执行数据源 adapter / schema / eval 实现。

## Next Branch

计划从当前分支创建下一阶段分支：

`codex/layered-data-source-expansion`

## Safety Notes

- 不在文档中写入 API key、SSH 密码或私有 token。
- 免费新闻、网页、海运数据只作为线索或低/中置信证据，不直接当成真实客户/供应商事实。
- 没有商业一致预期源前，只能使用 `expectation_proxy`，不能在 memo 中写成真实 consensus。
