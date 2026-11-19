# 启动和使用 FinSight

## 启动工作台

安装 Git、Python 3.10+ 和 Docker Compose。从仓库根目录执行：

```sh
python scripts/deployment/initialize.py
docker compose up -d --build
```

进入[项目工作台](http://127.0.0.1:8765/workspace/projects)，创建项目并填写问题。默认服务仅监听本机。初始化会生成数据库连接及凭据加密密钥。部署时一起备份私有设置、密钥和数据卷。升级时沿用同一组设置。

## 发起研究

只在本机单人使用时，可直接看下方「启动原生研究服务」。多人登录需要 uv 和 Docker Compose 2.24.4 或更高版本。

多人工作区可使用本地 Keycloak 登录。在已初始化的仓库中运行以下命令，信任本次生成的 `.secrets/identity/tls/ca.pem` 后打开 [HTTPS 工作台](https://localhost:18866/workspace)。点击注册，完成邮箱、账号和密码设置。登录后的「我的账户」用于维护身份资料，团队内的资料访问由组织、项目及空间角色管理。

```sh
uv run --locked --extra workbench-auth python scripts/deployment/initialize_identity.py
docker compose --env-file .env --env-file .secrets/identity/identity.env -f compose.yaml -f deploy/identity/compose.identity.yaml up -d --build --wait
```

**启动原生研究服务。** 在私有 `.env` 填写 `LANGSMITH_API_KEY`。个人研究使用的 DeepSeek 密钥在工作台「个人模型密钥」中保存。单用户本机部署使用以下命令。

```sh
docker compose -f compose.yaml -f deploy/agent_server/compose.native.yaml up -d --build
```

**已启用多人登录时**，请在同一目录改用以下组合命令，并从 HTTPS 工作台进入「新建个人研究」。后续启动保持相同的环境文件、配置文件和 Compose 项目名。

```sh
docker compose --env-file .env --env-file .secrets/identity/identity.env -f compose.yaml -f deploy/agent_server/compose.native.yaml -f deploy/identity/compose.identity.yaml up -d --build --wait
```

单用户部署可直接打开[个人研究会话](http://127.0.0.1:8765/workspace/session)，设置问题、截止日期、附件和研究模式。保存准备草稿可先检查输入。正式启动研究会产生模型服务商费用。普通研究由研究者取证并形成稿件，再交给独立复核者。深度研究适合需要拆分专题、处理反证和汇总多条判断的问题。个人密钥在自己的账户下保存；可用模型以部署实际接入为准。已使用的个人研究模型包括 DeepSeek V4 Flash，组织原生运行可按授权配置 GPT-6.2 Sol high 与 DeepSeek Flash 的组合。

研究附件属于该会话。要让同一项目持续检索某份资料，应从项目资料入口上传，确认正文可查找。组织研究可选用已发布并关联到项目的文件版本，直接用 BM25 搜回原文。向量和重排服务需要另行配置。SEC 等数据源使用部署者自己的联系信息和 API 授权。详见[部署说明](../../deploy/agent_server/README.md)。

外部数据授权填写在私有 `.env`。SEC EDGAR 使用 `SEC_USER_AGENT` 或 `FINSIGHT_SEC_CONTACT_EMAIL` 标识请求者。Alpha Vantage、韩国 OpenDART、同花顺分别读取 `ALPHAVANTAGE_API_KEY`、`OPENDART_API_KEY`、`HITHINK_FINANCE_API_KEY`。这些是部署侧数据工具凭据，与个人研究页面保存的模型密钥分别管理。留空时相应的付费或受限接口不可用。

组织连续研究支持由 GPT-6.2 Sol high 主持、按需调用 DeepSeek Flash 调查。管理员需要为指定组织、草稿和执行准备模型凭据及独立预算。工作台部署文档提供从公开配置开始生成私有设置、授权和检查预算的三条命令。通过检查后，在对应草稿的“模型组合”中选择。[组织模型组合部署步骤](../../apps/workbench/README.md#provision-the-optional-organization-model-combination)

## 知识库与检索配置

**先用原文试一次关键词检索。** 在启用多人身份和原生执行的部署中，加载[组织检索的 Compose 配置](../../deploy/organization/README.md)。登录后将项目文件版本发布到组织空间，关联项目并选入研究准备单。准备执行后，打开「检索本次研究资料」，搜一个原文中出现的词，点「读取原文」。BM25 可直接读取绑定资料，外部检索调用为零。若看不到入口，先检查组织检索是否启用、执行是否已准备；若没有命中，核对选定的版本和正文。项目文件查找目前不覆盖图片或扫描页中的文字。

**按需开启语义检索。** 导出执行获准使用的文本，准备文档向量，发布、校验并登记索引，再在新的准备单中选用该检索版本。在私有 `.env` 中设置 `FINSIGHT_ORGANIZATION_QUERY_EMBEDDING=qwen` 及 `QWEN_API_KEY` 可为新查询生成向量。对具备完整分块索引的版本，可另设 `FINSIGHT_ORGANIZATION_RERANK=qwen`。按组织部署指南执行 `fin up -d` 应用设置。嵌入服务会收到待嵌入的文本，重排服务会收到查询与授权候选段落，这些操作可能产生费用。上传文件本身不会触发付费向量化。[生成、登记与选用索引的命令](../../deploy/organization/README.md#publish-a-release)

## 快捷验证

在仓库根目录使用 uv 和 Python 3.11（公开 CI 使用的版本）执行以下命令。

```sh
uv sync --locked --extra agent-runtime --extra workbench-auth --extra workbench-delivery
uv run --no-sync python -m scripts.dev.verify_public_checkout
```

看到 `Workbench HTTP smoke check passed.` 表示本地测试客户端已验证健康端点，以及缺少服务时就绪端点按预期返回 503。这一步无需启动 Docker 或填写模型密钥。要生成一份合成报告用于检查导出，可追加 `--output-directory .local/sample-report` 并使用尚未存在的目录。在 `apps/workbench/frontend` 运行 `npm ci` 和 `npm run build` 检查前端类型和生产构建。
