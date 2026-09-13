# 产品截图 / Product screenshots

以下图片来自实际运行的 FinSight v0.1.3 工作台，未使用生成式界面图或替换页面数据。界面为中文，中英文文档使用相同截图。
These images show the running FinSight v0.1.3 application. They are not generated mockups or substituted page data. Both language editions use the same Chinese interface screenshots.

| 图片 / Image | 内容 / Content | 日期 / Date |
| --- | --- | --- |
| research-start.png | 问题入口、模型与执行方式 / Questions, models and execution choices | 2026-09-08 |
| research-map.png | Dell 示例报告地图，报告仍待审阅 / Dell example report map, awaiting review | 2026-09-08 |
| research-studio.png | 角色方法与配置编辑 / Research methods and configuration | 2026-09-08 |
| research-runtime.png | NVIDIA/Micron 研究的保存活动 / Saved NVIDIA/Micron research activity | 2026-09-08 |
| company-library.png | 公司资料库 / Company document library | 2026-09-11 |
| financial-data.png | MSFT 财务数据筛选 / Filtered MSFT financial data | 2026-09-11 |
| hpe-reviewed-report.png | HPE v2，记录两次人工修改 / HPE v2 with two human edits | 2026-09-11 |
| msft-reviewed-report.png | MSFT v2，记录两次人工修改 / MSFT v2 with two human edits | 2026-09-11 |

资料库截图中的 60 份文档对应扩充前快照；2026-09-12 的计数为 70 份。财务截图显示筛选结果，并非整个数据集。
The library screenshot contains 60 documents from an earlier snapshot; the September 12 count is 70. The financial screen shows filtered results, not the entire dataset.

## 在本地重新截图 / Capture locally

安装前端依赖和 Playwright Chromium，在仓库根目录执行：
Install the frontend dependencies and Playwright Chromium, then run from the repository root:

```bash
node scripts/dev/capture_product_screenshots.cjs --base-url http://127.0.0.1:18793 --thread YOUR_THREAD_ID --output-directory .local/screenshots-01
```

截图脚本只接受本机地址并阻止写入请求。分享前需逐张检查，避免包含凭据、私有上传或不适合公开的研究资料。
The script accepts local URLs and blocks write requests. Inspect each image before sharing to exclude credentials, private uploads and restricted research material.
