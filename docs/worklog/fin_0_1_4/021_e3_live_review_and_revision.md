# 021 · E3 有界真实复核与修订

2026-09-14；020后续，P1/P3。状态：真实初审未完整提交，未派发作者；资格方法工具遗漏已本地修正，不能当作无接线差异的产品效果对照。执行前固定：复用019原模型稿和所选原件，模型不接收宿主发现、020修正版或隐藏评测答案。新调用身份，仅测试独立复核与一次责任修订，不重跑原作者研究、Lead/Writer或完整研究链。

复用原生case reviewer、responsible_author_feedback、PaperRevision和revision_review_target；现有MCP工具读取已存来源/计算及所选上传全文，PG共享预算、SDK原生调用、CaseModelAudit保存原响应。资格文件薄接线，不新增运行引擎或付费恢复。

逐节点TokenBudgetBasis写入资格脚本和paid_preflight：初始Counter/Verifier各8请求24工具，作者至多10请求24工具，修订Counter/Verifier各6请求16工具，共最多38请求。初始及修订审阅每次6000输出tokens，作者8000；每次240000 UTF8 bytes、120秒、非思考Pro、无SDK重试。依据019原稿10主张、9块38975字符、两条已有计算、原作者6请求/max141265bytes，以及020本地接口资格；允许完整来源检查、明确发现/反驳、跨字段修订和提交反馈，不为费用静默删必答工作。

根预算8元、交付预留0.1元是异常停止边界，不是预计费用或账单硬上限。[官方中文价表](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)已搜索复核，空闲时段Pro输入未命中4.5/命中0.15/输出13.5元每百万tokens；日期/时段变化拒绝发送。页面直接抓取超时，搜索索引返回该官方表，不采用更旧英文价或旧预告。未知不重发，预算和所有失败保留。

退出：初审不完整则停止，不把不完整审阅偷偷转成完整责任反馈；无material finding则保留并由宿主检查漏报。只有完整初审的实际material finding进入一次作者修订，其后只复核改变范围，未解决依赖保留；不追加第二次作者修订、不原地改提示付费重跑。宿主最终审原稿/发现/完整修订/来源及费用，区分工程完成、局部纠错和全稿金融接受。单一公开开发样本，不作盲测、因果或普遍效果声明。

环境起点：Docker引擎未运行，默认C盘安装路径不存在；已定位现有CLI位于Z盘并启动对应Docker Desktop。恢复完成及本地真实SDK预检通过前不发送付费调用。不能无证据归因代理。

本地预检a1失败于MCP结构化输出裸dict返回注解；a2/a3定位到outline缺document_id，补充错误状态断言后修正，并按实际Pydantic返回使用model_dump。失败日志均保留。a4真实SDK MockTransport+原生reviewer+实际资料MCP通过，1 passed/1 deselected、41.20秒；全部9块目录可读、完整底稿进入第二次SDK请求、未完成语义检查显式提交。此时真实provider调用0。

Docker恢复：日志报`dockerInference`残留AF_UNIX端点不可访问，与[Docker问题527](https://github.com/docker/desktop-feedback/issues/527)一致。停止本次失败启动的Docker进程，将仅含运行端点的`C:/Users/hht13/AppData/Local/Docker/run`和`C:/Users/hht13/AppData/Local/docker-secrets-engine`分别改名保存为同父目录下`run.fin014-preserved-20260914-2111`、`docker-secrets-engine.fin014-preserved-20260914-2111`，由Desktop重建；未删除镜像、容器、卷或恢复出厂。之后WSL启动，daemon完成容器加载，但仍在初始化BuildKit。SIGUSR1诊断栈显示等待containerd snapshot Stat，暂无代理故障证据；不清理构建缓存来强行通过。

## 实际结果与接受范围

Docker随后完成BuildKit元数据初始化，第二次诊断栈已从cache init前进到ReleaseUnreferenced；约21:17容器API恢复，初始运行容器0。检查既有网络后使用未占用`10.247.120.0/24`，复用锁定原生资格镜像及PG。不是永久Docker修复或代理调整；保留临时端点目录。

真实attempt `.local/fin014/20260914_e3_live_review_a1`：工程pytest1通过/1 deselected、120.09秒，意思是有界流程按停止条件保存了结果，不是金融审阅通过。Counter/Verifier各8请求，合计16；输入306459、输出7752，共314211tokens，最大SDK载荷93186bytes。PG公开价估算888505 microCNY（0.888505元），held/unsettled均0。隔离服务已停止，原卷/费用/响应保留；作者及修订后复核请求0。

- 两者复查核心数值和计算，并读到公司销售增长所在S001；但没有指出C6原绑定缺该行，也未指出反证字段把阶段性判断写得过于确定。只核对数据真实存在没有完成主张级引用覆盖与解释强度审查，019语义负例不关闭。
- Counter保存一个advisory汇率发现，却把2024/2025各自列示的F/X影响直接相减为254百万美元，并解释为增长率/利润率变化因素；比较基准和利润率分母影响未核实，不将该建议接受为已证明纠错。
- Counter最后一轮提交`completion=complete`但仍有unresolved_data_requests，被实际schema拒绝，没有最终review；Verifier同类首次提交被拒，下一轮改为incomplete并保留检查。原生初审phase=case_review_incomplete，按预定规则停止，没有把未完成记录改为空或强行派发作者。
- 审阅把HTML解析最终核验、AWS更深因果归因列为必要未完成项。需要区分当前“只用所选公告”的任务验收和超出范围的研究限制；不能为了得到complete删除模型已记录的待查事项，也不能把所有旧稿免责声明自动当成当前阻塞。
- 本次存在资格接线缺陷：专用MCP server未注册工作台已有的get_research_method，而生产提示仍声明可用。Counter第一轮调用目录报invalid tool；Verifier没有调用方法。故这次不是方法完整送达下的效果检验，不把全部失败归因模型。已接入现有research_methods函数，未改方法内容；新本地a5 SDK预检实际读取counter方法全文→完整稿→提交incomplete，1通过/1 deselected、15.82秒，零额外付费。生产代码本包未改。

`qualification_executed.py`保持付费时原接线，摘要与paid_preflight一致；tracked资格脚本包含事后本地修复，二者明确区分。host_review.json保存宿主接受范围、用量和局限，counter_review_public.json/verifier_review_public.json为不含私有消息的可读审阅状态；原模型响应、原稿及未成功提交的内容不改写。代码编译/diff检查通过。

下一小包先对齐现有方法/工具的实际入口，采用一个新的、有明确材料错误和正确内容保留要求的有界开发案例，预先定义当前任务所需检查与范围外限制，再测复核者发现、误报及责任纠正；不增加复核平台，不因本次触顶直接加额度，不反复付费调整019。E3纠错未接受；E1/E2开放、E4/E5未实施，0.1.4未发布。
