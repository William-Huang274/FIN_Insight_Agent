# FinSight 0.1.3 正式收口

2026-09-12 · Owner要求结束本版迭代 · 收口形态：本地研究工作台 / Internal Alpha。

本文件是0.1.3最终范围入口，取代9月11日的待收口建议。产品迭代现已结束；原始完整PRD、S5生产发布及每份报告的内容验收未被追认通过。Python/前端包版本保留0.1.3，0.1.4目前只有规划。本次不合并main、不部署、不签发生产release。

## 交付与证据

| 范围 | 已交付 | 证据与限定 |
| --- | --- | --- |
| 研究工作台 | React/FastAPI界面，LangChain/LangGraph执行，checkpoint接续、角色底稿、版本化人工修订、来源与计算回读、多格式导出 | [208实测](../worklog/fin_0_1_3_s3/208_product_acceptance_and_external_evidence.md)；人工修订交付不等于模型全自动通过 |
| 研究编排 | 单Agent、指定专家、自由/完整研究，角色方向、目标、方法和审查顺序可编辑并实际进入运行配置 | 已有角色/受支持编排；不承诺前端任意编写图拓扑 |
| 数据与资料 | 最新案例快照70文档、66唯一URL、9253原文节点、12994向量块；五公司2274条财务观察；MU50条行情 | [210](../worklog/fin_0_1_3_s3/210_data_library_and_navigation.md)、[211](../worklog/fin_0_1_3_s3/211_ai_memory_investment_case.md)；不同统计单位不混算，原文不等于已核判断 |
| 检索资格 | BM25/Qwen向量与重排、缓存及精确来源定位；28条开放查询中的24正例Hit@5为23/24，BM25为12/24 | 这是1105块旧固定评测集，不是12994块最新资料的重测，更不是答案准确率 |
| 长对话与隔离 | 19真实用户回合含恢复/重启交接；OIDC/PKCE双用户39项检查、8并发读；4前端权限场景 | 历史局部资格，不是生产HA/安全认证/全面长上下文保真 |
| AI内存投研案例 | 四份原生底稿及七页分析师审阅报告，跨公司/技术/市场资料扩充 | 原Verifier不完整、Counter中断、native Writer未完成，不声称全链自动终审 |
| 模型与上下文诊断 | 原678万tokens按请求复盘，阶段索引/原文保留/显式笔记资格；Qwen Max/Plus与DS low/high的16调用固定资料比较 | 原文可达与最终可见已分开；有错误草稿时金融语义仍不稳，实验候选保持默认关闭 |

历史检索、恢复、身份与新数据规模各自保留分母与版本。完整口径见[公开实测报告](../public/technical-evaluation.zh-CN.md)、[指标JSON](../public/evaluation-metrics.json)与[简历证据](../public/resume-evidence.md)。

## 收口处置

- 停止在0.1.3中继续扩展主动研究方法库、制度自动更新、专家子任务与收敛策略。它们归入[0.1.4规划](fin_0_1_4_research_plan.zh-CN.md)。
- 保留全部失败、未知调用及人工修改历史。原AI内存case97请求/95用量已知/6780446已知tokens，未知2不重发；不能以收口清除失败。
- 上下文导航、生成式阶段整理与跨模型比较是资格证据；没有证明金融质量普遍提升，生产默认不采用这些候选。
- 尚未满足的产品承诺明确保留：无人审阅金融正确性、动态方法选取与更新、按期自主收敛、任意公司全链研究、生产运维，以及最终干净安装/备份恢复演练。生产运维与完整安装验收不自动挤入0.1.4核心研究范围。
- Owner本次授权版本收口，不等同逐份接受Dell、MSFT或其他历史报告内容；各产物原状态不变。

## 本次仓库整理与验证

9月12日先整理了 AI 内存资格目录；9月13日按 Owner 要求进一步清出一次性代码及旧兼容入口。现用 runtime 所需函数已抽到维护模块，历史实验与旧 `archive/versions/` 通过[冻结标签恢复](../../archive/README.md)。原包名 `sec_agent`、仍用的配置/数据/图 ID 和 SQL 迁移保留，避免破坏来源与部署身份。完整退出范围与验证见[213](../worklog/fin_0_1_3_s3/213_frozen_repository_cleanup.md)。

产品品牌统一为FinSight Agent；版本写作FIN 0.1.3 / FIN 0.1.4；Python分发名为`finsight-agent`。新当前文档采用小写、下划线与语言后缀；历史大写/日期文件原位保留并注明当前入口。详见[仓库与命名地图](../architecture/repository/naming_and_entrypoints.zh-CN.md)。

本次零模型检查：公开Python入口46 passed及合成导出；迁移相关12 passed；TypeScript与Vite build通过，保留第三方注释及大bundle告警；公共浏览器36场景通过（合成API，2.0分钟）。具体见[收口工作记录](../worklog/fin_0_1_3_s3/212_version_closeout_and_repository_cleanup.md)。这是当前开发环境检查，不冒充全新机器安装或真实模型投研重验。

本地raw数据、模型私有响应、SQLite、向量库、输出及临时资格目录保留在忽略路径；不上传、不为“干净”删除。Git可干净并不表示研究数据被清空。

## 后续入口

- [0.1.4自主研究规划](fin_0_1_4_research_plan.zh-CN.md)：唯一新版本规划，尚未实施。
- [当前上下文](../project_os/current_context_pack.zh-CN.md)：短接续入口。
- [211完整案例记录](../worklog/fin_0_1_3_s3/211_ai_memory_investment_case.md)：正反面研究证据。
- [9月11日盘点](FIN_0_1_3_STAGE_CLOSEOUT_20260911.zh-CN.md)：历史详细清单，不再表示等待Owner决定版本是否结束。
