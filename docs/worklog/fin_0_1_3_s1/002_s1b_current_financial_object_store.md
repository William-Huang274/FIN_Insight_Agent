# S1-B 当前金融对象库工作记录

日期：2026-08-12

## 决策

不复活旧 ObjectBM25/Milvus 结果，也不让每条检索通道自行切 chunk。先建立一份 provider-neutral 父子金融对象库，让后续 sparse、dense、rerank 和 Evidence Gate 消费相同对象。

## 真实执行

1. 盘点 DELL/MU/NVDA、关系公司和 PIT 行情，区分“本地已有正文”“只有导航/说明”“官方存在但产品 transport 未捕获”。
2. 对象构建 R1 因 flattened SEC text 产生 `202,705` 字符 child 而 fail closed；保留失败后，改从原始 HTML capture 重解析 Item、段落和表格。
3. 用 evaluation-only alias crosswalk 将 16 个必要旧 qrel chunk 映射到当前语义对象；旧 chunk 不进入产品候选。
4. 官方有界补充 R1–R4 取得 NVDA Q1 FY2027 10-Q；Dell transcript 与 Micron prepared remarks 的产品 transport 仍超时，按停止规则转 S1-D。
5. 重新物化 28 parent / 1,805 child 的当前 store，并用同一 17-facet 查询生成 Workbench 快照。

## 结果与反思

- 对象结构门通过：627 个表对象无边界破坏，最大 child 8,449 字符，无超限对象；三案 current-object missing=0。
- 当前候选命中 DELL/MU/NVDA=`6/3/4`。NVDA 加入最新 10-Q 后从 `6` 降到 `4`，证明“资料更多”会加剧 top-k 竞争；不能再把 source coverage 和 ranking quality 混成一个数字。
- 具体错误是：DELL 现金槽排到 AI 需求风险、MU 现金槽排到 non-GAAP 对账、NVDA 需求槽仍由 2024 内容领跑、关系槽多为主题共现。这些归 S1-C，不继续修 S1-B。
- 市场 snapshot 只有价格/收益率且日期偏旧，不得写成估值。
- Workbench 挂载真实对象的移动端测试第一次出现 537px 内容宽度撑破 412px viewport；根因是长 lane ID 和来源标签不能收缩。当前产品消费者改为有界换行后，挂载/无数据两种模式均为桌面+移动 6/6。

## 最终复证

- active baseline：69 Python / 7 frontend / 4 Runtime resources / 0 历史活动引用。
- Python：59 passed；TypeScript 和 Vite build 通过。
- Playwright：无数据 6/6，挂载真实数据 6/6。
- Secret scan：6,254 files，0 findings。

## 阶段边界

S1-B 工程通过，不等于 S1 产品通过。下一步是冻结同一对象 store 做 sparse/dense/rerank 对照；Dell/Micron PDF transport、TSM 先进封装与新鲜估值数据留给 S1-D 定向补源。
