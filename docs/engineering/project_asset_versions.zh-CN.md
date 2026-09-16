# 项目资料版本、差异与选版

本功能属于 0.1.4 的项目资产工作流。它支持比较保存内容、寻找已记录的直接依赖和明确选版进入新任务；不判断金融结论是否应修订，也不会启动研究模型。

## 用户流程

1. 在项目资料卡打开“版本、差异与关联成果”。现有独立上传各自视为初版；同名文件不会自动合并。
2. 在“上传新版本”前，选择“原资料修订”或“新增期间披露”，填写更新说明。性质是用户声明，不表示系统认定旧披露有错。上传成功保留旧文件和原有资料选择。
3. 选择基准和对照版本，查看正文增加、删除及原件校验值。保存时间是进入项目的时间，不替代披露日期。
4. 点击“查基准版本的关联任务与成果”，查看记录了此来源身份的任务和项目成果。未知记录单独提示；没有列出不能推断为不受影响。
5. 点击“选择此版本用于新研究”。版本页选版会替换当前选择中同组资料的版本；用户仍可在资料卡手动多选以研究版本差异。点击“用所选资料准备研究”，核对资料后保存新任务。任务副本和已确认报告始终保留原版本；撤销使用仍按既有权限机制限制后续读取。

SEC 页面中的“数据版本差异与关联成果”按项目与 CIK 分组，可比较同一公司的两个已完成、可用快照。失败刷新仍保留记录及以前版本。选择版本后，可在指标浏览区核对并准备新研究；比较本身只读取保存文件，不重新访问 SEC。

研究成果按原任务分组，沿用原生报告版本及审阅状态。需要修改时进入原任务人工编辑，再保存到项目；不通过“上传新版本”伪造原生报告修订。归档报告副本允许比较保存文本。

## 实现与兼容性

- 继续使用项目 SQLite、现有附件解析器及 owner / 原生任务权限检查。没有新增工作流、检索或数据库服务。
- `attachment_revisions(child,parent,root,sequence,change_kind,note)` 为追加表；只在首次上传修订时创建。版本关系与文件在同一 `BEGIN IMMEDIATE` 事务保存；每个 parent 只允许一个直接后继。并发或过期提交返回 409；解析、容量等错误不留下半份资料。
- 原有 `UPLOAD::` 身份、正文、摘要、引用和任务快照不改。列表新增 `created_at`（UTC）与 `digest`，项目列表补充 `version_info`。旧资料无需批量迁移。
- `POST /api/v1/projects/{project}/documents` 可选 `parent`、`change_kind`、`note` 查询参数；文件仍是有大小上限的原始请求体。没有自动重试；结果未知时先重新载入版本记录。
- `GET /api/v1/projects/{project}/assets/{kind}/{asset}/history` 返回同组元数据；`compare?other=...&offset=...` 比较已授权版本；`dependencies` 返回已记录的直接绑定。所有端点校验当前账户项目权限并设置 `no-store`。
- 文本对齐复用 Python `difflib`。SEC 比较使用精确 Decimal 解析与记录多重集合，保留 taxonomy、tag、unit、全部原始 observation 字段及重复次数；不同申报身份不合并。数值修改表现为旧记录移除、新记录增加；重新排序不产生观测变化。
- 依赖查询从当前账户已归档的任务中逐一核对原生 ownership，读取任务副本绑定；项目成果读取保存时的 `source_dependencies`。撤销后仍可查看依赖元数据，但不能读取被撤销正文或把受限报告下载出去。旧记录缺失来源范围或原生任务不可访问时标记未知，不泄露其他用户任务身份。
- 原生任务读取每项最多等待 5 秒；连接失败、超时或服务错误后，本次查询剩余任务标记不可核实，不对同一故障逐任务重试。项目内成果的本地绑定仍返回；服务恢复后由用户重新查询。

## 明确边界

- 每项目仍最多 12 份文件、总计 80 MiB、单份 20 MiB；每个版本各占一份额度。SEC 仍最多保留 12 次同步尝试。暂未提供清理、归档额度或自动同步策略。
- 文档仅比较已解析正文。扫描页、图片和表格布局不在范围内；含未识别页时提示。任一版本超过 300,000 字符或 8,000 行时不执行完整文本对齐；一般差异最多展示 2,000 行，截断会明确提示并保留原件下载。不能把“无文本差异”解释为“内容没有变化”。
- SEC 差异仅覆盖 `companyfacts` 原始观测，每页 50 类变化；披露目录、概念描述和金融语义影响不在此范围。原始校验值相同与观测相同分别呈现。
- 依赖是材料选择记录，不是逐主张引用图；不覆盖没有记录的历史来源、间接引用链或未归档到项目索引的任务。不自动修改旧报告，也不声称能定位受影响的具体金融判断。
- 工程验证使用真实 BFF / SQLite / 浏览器和合成文件、保存的合成 SEC 快照；研究执行服务是禁止模型 dispatch 的资格 fixture。这不是金融质量验证或生产重启验收。

## 验证入口

```bash
uv run --no-sync python -m pytest -q tests/test_project_asset_versions.py tests/test_project_library.py tests/test_project_report_assets.py tests/test_project_research_materials.py tests/test_project_sec_sources.py tests/test_project_asset_revocation.py tests/test_project_financial_facts.py tests/test_task_attachments.py tests/test_research_session_bff.py
```

在前端目录运行 `npm run typecheck`、`npm run build`。Windows 下项目浏览器配置使用仓库 `.venv/Scripts/python.exe`；设置新的隔离 `FINSIGHT_LOCAL_STATE_ROOT` 和 `FIN_PROJECT_VERSIONS_FIXTURE=1` 后运行 `npx playwright test --config playwright.project.config.ts project-versions.spec.ts project-library.spec.ts`。每次采用新目录，保留先前截图及失败证据。fixture 使用 5173 / 8767 端口，不复用其他运行服务，也不抓取 SEC 或调用模型。
