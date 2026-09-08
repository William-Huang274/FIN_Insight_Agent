# 202 · 前端阶段性交付后的公开仓库整理

日期：2026-09-08；产品仍为 FIN 0.1.3，Dell 报告 v5 待审阅。Owner 要求整理 GitHub 展示、中英文措辞、代码命名、外部测试脚本和真实产品截图。本轮授权公开产品界面与当前代码，不发布完整报告、原始资料或正式产品 release；Hermes 后置。

## 实施

- 中英文首页改为产品流程、真实截图、零模型验证、架构和验证范围；中文别名保留导航，避免副本漂移。
- 更新中英文快速开始、导览、架构、分享边界和工作台/脚本/测试说明。修正旧只读、唯一后端、当前v4等误导；历史v4渲染页数保留为历史证据。
- 通用 research_workbench CLI 委托原已测部署，不改变Compose身份、凭据派生、卷或旧模块兼容性。没有批量改图ID和金融合同。
- 外部源码检查复用pytest和现有导出器；公开Playwright只启动Vite/合成API，不依赖旧BFF或私有数据，加入现有CI。增加中英文Bug模板。
- 四张真实截图为起始页、研究地图、配置、运行记录；1600×1000，共418697字节。没有生成模型、数据替换或完整私有正文发布。

## 本地验证

- verify_public_checkout：34 passed，19.49s；四格式合成导出，0模型。D:/temp/fin-public-check-a1。
- 独立公开Playwright：13 passed，1.8m，覆盖1440/1024/390；只启动Vite4183。初次shell找不到npm，尝试bundled npm路径也不存在；随后直接执行同包Playwright CLI成功。该环境路径问题不是测试失败。
- TypeScript/Vite通过，保留已有bundle大小和zod注释警告。
- 活动基线pass，无unresolved；公开Markdown相对链接82项，无缺失。
- 截图A1捕获起始动画中间态，A2等待任务加载并由Playwright结束有限动画；0页面异常、0写入。两次输出保留，发布选D:/temp/fin-public-showcase-a2。
- 通用部署CLI --help通过，未重建原生服务，未新增模型调用。

## 发布与后续

远端检查时为main和两个history分支，无开放PR。当前分支承载已完成前端修改；通过GitHub PR检查后合并当前代码与展示面，再删除临时远端分支，保留历史提交。GitHub最终状态在完成后补录。

产品增量为实际界面介绍与试用路径；工程增量为通用CLI、公开检查入口、截图工具和CI接入；无新增paid研究证据；文档与治理为本轮主要交付。Owner内容审阅、旧claim意见、跨公司完整研究与生产资格不由仓库整理关闭。

## 独立检出与首轮CI

独立检出83f70745：全新.venv按文档uv锁安装127包，34检查48秒通过、四格式导出；没有复制.env、数据库或旧报告。GitHub PR #5 首轮34216728226：3080通过、817跳过、1失败；依赖与容器通过。唯一失败是旧首页组件断言，进一步发现旧Evidence Pack UI组件缺入口。恢复明确兼容地址/workspace/evidence-packs，保留新首页ResearchSession，更新对应旧浏览器测试的路由与首页预期，未删除其证据/操作控制台覆盖。7项基线定向检查通过。首轮CI和本地日志D:/temp/fin-showcase-ci-a1.log保留。

默认全浏览器A1：15通过/1失败，390px测试在移动导航返回前点开目标页面板，后到的路由提交关闭了面板。测试改为确认目标报告窗格已可见再点击，保留产品交互断言，没有扩大timeout或增加重试。失败trace/screenshot保存在D:/temp/fin-public-default-browser-a1-failure。历史Evidence Pack组件按需lazy加载，不增加常规研究首页的历史组件下载。

修复后默认浏览器A2：16项通过（1.3分钟），包含旧证据页、操作控制台与新首页/三宽度研究交互；TypeScript/Vite再次通过，旧组件独立lazy chunk。中英文README均已通过GitHub Markdown API渲染，各4图、2表、1折叠区。发布载体为[PR #5](https://github.com/William-Huang274/FIN_Insight_Agent/pull/5)；最终主线提交、检查与合入时间以该原生PR记录为准，保留首轮失败，不把静态日志当Git控制面。
