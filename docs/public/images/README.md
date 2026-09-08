# Product screenshots / 产品截图

Actual FinSight FIN 0.1.3 application, captured 2026-09-08 at 1600×1000. Chinese UI; the English README uses the same images with English captions. No invented data, image generation or DOM content replacement.

| File | Surface |
| --- | --- |
| research-start.png | Question-first entry, execution/model selection and actual research navigation / 起始页与模式、模型选择 |
| research-map.png | Actual Dell v5 report overview, awaiting review / 报告地图 |
| research-studio.png | Standard role/Skill configuration editor / 原生配置编辑器 |
| research-runtime.png | Saved NVIDIA/Micron free-mode research activity, not a currently running simulation / 真实已完成自由研究的公开 Agent 活动流 |

The requested public selection excludes full report bodies, expanded original sources, uploaded documents, credentials and private model context. Short task suffixes and configuration digests are visible correlation identifiers, not credentials. Capture made no model calls and recorded zero page errors/blocked writes. The first capture caught the entry animation in progress; the selected second capture waits for task loading and finishes finite animations through Playwright's screenshot option.

The start/runtime images were refreshed in S3/203 from the actual deployed application; map/studio remain the reviewed S3/202 captures. Failed research attempts remain visible in the sidebar. Runtime prose is explicitly emitted public progress, not private reasoning. Local S3/203 capture receipt: `D:/temp/fin-activity-public-capture-a1/capture.json`.

Reproduce against a configured **local** workbench, with a new output directory:

```bash
node scripts/dev/capture_product_screenshots.cjs --base-url http://127.0.0.1:18793 --thread YOUR_THREAD_ID --output-directory .local/screenshots-01
```

Run from the repository root after installing frontend dependencies and Playwright Chromium. The script rejects non-local URLs and blocks non-read HTTP requests. Inspect every image before selecting new public screenshots. It does not sanitize arbitrary private content automatically.

本轮截图是 Owner 要求的产品界面展示，不发布完整研究报告或原始资料。复拍后仍须逐张检查内容；脚本只防止写入，不会自动判断素材是否适合公开。
