# 本地运行与验证

2026-09-07 · [English](quickstart.en.md)

## 先区分两种复现

**仅源码/合成检查**不需要API key、真实财务资料、Docker或旧报告，可验证上传、分块、图表和导出。

```powershell
uv sync --locked --extra agent-runtime --extra external-search --extra workbench-delivery
uv run --no-sync python -m pytest tests/test_task_attachments.py tests/test_report_delivery.py -q
uv run --no-sync python -m scripts.qualification.research_delivery_smoke --output-directory D:/temp/finsight-delivery-smoke

cd apps/workbench/frontend
npm ci
npm run typecheck
npm run build
```

输出目录必须尚不存在，避免覆盖先前结果。生成文件明确是合成测试，不是Dell案例成绩。Word/PPT结构校验不能代替实际渲染；可用本机LibreOffice将它们转为PDF后检查各页。PDF导出本身不依赖Office。

**完整Dell复现**需要运营者已准备的私有资格数据与当前服务设置；当前不是“clone后一个命令下载全部语料”的公开发行包。不得伪造缺失数据或用旧答案填入新研究。现部署的可复现资产路径/版本在私有settings和源详设/S3工作日志记录。

## 完整服务部署

先安装Docker Desktop并确认引擎正常。确认代理时区分宿主`127.0.0.1`和容器网络；本机API请求不经环境代理。不要因网络报错删除Docker卷。

在仓库`.env`配置实际DeepSeek、LangSmith和PostgreSQL密码；不在命令行或日志打印值。Agent Server使用已固定镜像，LangSmith必须可用，无替代trace服务。Exa等现有外源接入配置遵循当前工具适配器；不能未试用便宣称可检索。

准备设置目录，其中`host-settings.json`/`container-settings.json`分别描述宿主和容器路径，固定原始数据挂载及既有报告兼容材料。当前BFF仍保留旧报告兼容入口，因此初始设置需要已保存的bundle/report绑定；这是尚未独立打包的私有case部署依赖，不是fresh模型输入。新研究父图不读取旧答案。

```powershell
# 替换为你已有的受控设置目录；以下命令不会启动模型任务。
uv run --no-sync python -m scripts.deployment.dell_report_workbench up --settings-directory D:/private/finsight-session --enable-research
uv run --no-sync python -m scripts.deployment.dell_report_workbench serve --settings-directory D:/private/finsight-session --enable-research
```

固定服务：工作台`127.0.0.1:8766`，Agent Server`127.0.0.1:18165`。源配置在`configs/research/runtime/research_session.json`，案例题目在`configs/research/cases/dell_growth_quality.json`。数据库/Redis归原生服务器；新提问不新建Compose项目、端口或volume。

## 操作

1. 新建研究，核对资料时点和估费；上传可选文件，再显式启动。坏文件保留草稿但不启动模型。
2. 看真实任务、依赖、调用/token/估费。并发2不代表只研究两面。可补充意见；在后续阶段的送达事件出现前不能假设模型已读。
3. 停止会保留已完成记录；未知付费用量不记零，不自动重发。运行失败后先查责任节点，不能整案无脑重跑。
4. 报告完成后检查来源和图表。模型审查意见可质疑；“人工确认”不会自动发布。短问答Flash与深度Pro为显式选择。
5. 导出MD/PDF/Word/PPT不调用模型、不改变报告，不代表内容被人工接受。PPT为可编辑图表/表格及分页内容，不是另一次LLM重写的演讲稿。

上传只保存任务副本：PDF、DOCX、MD、TXT、CSV、HTML、PNG/JPEG/WebP；单文件20MiB、单任务12份/80MiB，PDF200页、解压/文本量有上限。图片/扫描页按需发送给DeepSeek视觉模型，文字识别有误差。当前仅可信Owner本地文件，不对公网开放上传。

## 验收与排错

```powershell
uv run --no-sync python scripts/eval_multi_agent/run_project_os_full_chain_preflight.py --decision configs/research/runtime/research_session.json --pretty
uv run --no-sync python -m pytest tests/test_research_session.py tests/test_research_session_bff.py -q
```

上述是合同/接线检查，不是语义或生产认证。真实研究看相同thread/run的来源、底稿、最终报告、LangSmith与本地usage。不能把全账单解释为单次用户任务费用；试错、功能探针、完整研究、追问分别归账。价格按已知usage估算，账单为最终依据。

不要把旧8765固定Pack页面当成新8766研究入口。资料缺失、来源失败、schema问题和网络问题分别诊断；不通过清数据、弱化验证器或补假来源恢复“绿色”。
