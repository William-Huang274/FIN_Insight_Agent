# 209 阶段收口：当前 runtime、案例与 PRD 对账

2026-09-11；FIN 0.1.3 / S3 不变。Owner 授权盘点、尝试恢复硬阻塞案例（含代为人工修订），再决定是否结项。本轮不是自动签发 S5 或发布新版本。

## 有界工作包及实际切片

1. 读取当前 Project OS、9月产品基线、原 PRD/发布分配与205/207/208实测证据；按题目而非窗口或重试计数。
2. 从正在运行的工作台读取22个研究窗口，检查现存报告、未完成原因和同题接续；对HPE、MSFT重新下载三格式并操作角色底稿历史滚动。
3. 用既有人工编辑入口修正NVDA单题的表述及NVDA/MU财年比较的过度限制；不用模型重跑。已真实保存两份v2、人工修改各1次，并保存个人研究记忆，三格式及角色历史验证通过。
4. 发现两份早期Dell档案502：native返回 `Graph 'dell_report_session' not found`。修复归属部署兼容层，不是DS知识问题。采用现有LangGraph旧schema的只读入口，拒绝恢复旧执行器；BFF及前端显示只读边界，不创建自研checkpoint读取系统、不修改旧数据。
5. 形成一份产品收口对账；已有对外技术报告和指标仍为实测详细依据。原PRD不删要求，历史失败不改绿；正式结项和未来范围由Owner决定。

## 原始证据

私有根 `D:/temp/fin209/`：`research-inventory.json` 是本轮写操作前目录；`live-research-summary.json` 是两份人工修改后的详情采样。22窗口含重复题/失败/三份空白或界面测试，不是22独立题。初次详情20个200、2个502。

- `hpe-delivery/`、`msft-delivery/`：现有复杂/自定义研究v2、人工2，各三格式实际下载与角色历史滚动。
- `nvda-manual/`、`pair-manual/`：真实UI人工操作回执；`nvda-delivery/`、`pair-delivery/`为更新后v2、人工1、三格式与角色历史。
- `editorial-checks.json`、两份 `*-decision.json`：预先准备的有限修订，核对保存的原始数值、期间、单位和算式。不改变原claims/source，不冒充独立模型核验。
- `*-readback.json`：早期Dell原始502/native404；归属旧图移除。原状态未覆写。
- `targeted.xml`：人工修订接续和sandbox26检查通过；`archive-tests.xml`：旧schema只读/禁止执行与相关API57检查通过。两组有重叠，不能相加为83个独立检查。
- 本轮首次sandbox检查人工抄错镜像digest，被固定镜像格式检查拒绝；按仓库操作文档的真实digest重试只读check通过，宿主/容器鉴权与目录匹配，0执行。不是新的产品sandbox故障。

本轮新增模型/embedding/rerank调用为0。Qwen公开28题的Top5指标重新由已保存结果计算一致；不是重新调用云API，也不算新盲测。

## 盘点纠错

205索引把MSFT指定专家旧题误写成利润/FCF。真实问题是Intelligent Cloud分部收入、营业利润率、产品组合；208新题才是CFO/现金资本支出/FCF。两题分别保留，不把后者替前者验收。NVDA/MU比较与NVDA单公司两年收入也是不同题。

截至初次盘点，HPE与MSFT现金题的旧失败均已有人工完成接续；NVDA旧失败有单Agent交卷，本轮补人工完成；比较题原过强结论本轮修订。Dell主报告v5、204综合题与MSFT分部报告v2已有输出但尚未整篇内容接受，不强行改为human_completed。语义核验/方法A/B实验的失败结果不属于待交付客户任务，不能人工改答案后宣布实验通过。

## 最终部署与回读

现有部署入口 `research_workbench build/up --no-build` 构建并加载 native镜像 `sha256:fcb1c95c8043472d2b5e297d5cabe16bc59527c5da5d475f7c6c4aaa9cfd1e10`。部署前确认busy线程0；保留PG/Redis卷，未动Owner的18796终端。18795通过原参数重启，父PID30152；TS与Vite通过，保留既有大chunk提示。

两旧档案现在200：`01a07515-e784-7480-b6b3-eb4105ca127b`恢复原v3报告，三格式下载成功；`01a07505-088c-7f63-8897-ad96deee2aee`恢复原始失败记录，没有报告则不补造。旧图复用schema读取且执行factory硬拒绝；真实旧会话POST返回409，前后native runs完全不变。1440/390实际页面显示只读说明、无人工修改按钮；初次提示横排影响标题布局已调整嵌入标题列并复验。

最终 `final-readback.json`：22/22窗口200、10窗口有报告、4窗口human_completed。这是存量窗口可读性，**不是22独立案例全通过**。`legacy-dell-delivery/`、`current-dell-delivery/`、`msft-segment-delivery/`补读原v3、主v5、分部v2及9个真实导出文件；连同前述4份报告，共7份报告×3格式=21个下载文件。没有将所有PDF/Word逐页重新做排版或金融内容审阅。

18165/18795/18806健康200，18796宿主/容器鉴权可用；18815身份资格BFF不在运行，双用户隔离为208历史证据，不称本机18795已开启生产登录。0付费新运行，原模型用量与失败不改写。

源码兼容修复与其测试作为工程提交；本文件、产品对账及索引为独立文档提交。正式产品结项不是日志或Git提交自行生效的操作。

工程提交 `297a5d70`。部署后再次验证18796宿主/native容器鉴权和目录匹配通过；PDF解析、DOCX包/XML及MD结构检查7份均通过（`export-structure-check.json`），不能替代逐页视觉或整篇金融审核。源码与文档在原开发分支推送，不合main、不发布tag。
