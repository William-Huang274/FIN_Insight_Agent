# 启动和使用 FinSight

## 启动工作台

安装 Git、Python 3.10+ 和 Docker Compose。从仓库根目录执行：

```sh
python scripts/deployment/initialize.py
docker compose up -d --build
```

进入[项目工作台](http://127.0.0.1:8765/workspace/projects)，创建项目并填写问题。默认服务仅监听本机。初始化会生成数据库连接及凭据加密密钥。部署时一起备份私有设置、密钥和数据卷。升级时沿用同一组设置。

## 发起研究

多人工作区可使用本地 Keycloak 登录。在已初始化的仓库中运行以下命令，信任本次生成的 `.secrets/identity/tls/ca.pem` 后打开 [HTTPS 工作台](https://localhost:18866/workspace)。点击注册，完成邮箱、账号和密码设置。登录后的「我的账户」用于维护身份资料，团队内的资料访问由组织、项目及空间角色管理。

```sh
uv run --locked --extra workbench-auth python scripts/deployment/initialize_identity.py
docker compose --env-file .env --env-file .secrets/identity/identity.env -f compose.yaml -f deploy/identity/compose.identity.yaml up -d --build --wait
```

在本机的 `.env` 配置原生服务所需的 LangSmith 访问和自有模型凭据。启用执行服务：

```sh
docker compose -f compose.yaml -f deploy/agent_server/compose.native.yaml up -d --build
```

打开[个人研究会话](http://127.0.0.1:8765/workspace/session)，设置问题、截止日期、附件和研究模式。保存准备草稿可先检查输入。正式启动研究会产生模型服务商费用。普通研究由研究者取证并形成稿件，再交给独立复核者。深度研究适合需要拆分专题、处理反证和汇总多条判断的问题。个人密钥在自己的账户下保存；可用模型以部署实际接入为准。已使用的个人研究模型包括 DeepSeek V4 Flash，组织原生运行可按授权配置 GPT-6.2 Sol high 与 DeepSeek Flash 的组合。

研究附件属于该会话。要让同一项目持续检索某份资料，应从项目资料入口上传，等待解析及索引发布，再通过资料库检索并打开原文。向量和重排服务需要另行配置。SEC 等数据源使用部署者自己的联系信息和 API 授权。详见[部署说明](../../deploy/agent_server/README.md)。

外部数据授权填写在私有 `.env`。SEC EDGAR 使用 `SEC_USER_AGENT` 或 `FINSIGHT_SEC_CONTACT_EMAIL` 标识请求者。Alpha Vantage、韩国 OpenDART、同花顺分别读取 `ALPHAVANTAGE_API_KEY`、`OPENDART_API_KEY`、`HITHINK_FINANCE_API_KEY`。这些是部署侧数据工具凭据，与个人研究页面保存的模型密钥分别管理。留空时相应的付费或受限接口不可用。

## 快捷验证

```sh
uv sync --locked --extra agent-runtime --extra workbench-auth --extra workbench-delivery
uv run --no-sync python -m scripts.dev.verify_public_checkout
```

此命令检查 HTTP 服务与未配置状态。要生成一份合成报告用于检查导出，可追加 `--output-directory .local/sample-report` 并使用尚未存在的目录。在 `apps/workbench/frontend` 运行 `npm ci` 和 `npm run build` 检查前端类型和生产构建。

组织连续研究支持由 GPT-6.2 Sol high 主持、按需调用 DeepSeek Flash 调查。管理员需要为指定组织、草稿和执行准备模型凭据及独立预算。工作台部署文档提供从公开配置开始生成私有设置、授权和检查预算的三条命令。通过检查后，在对应草稿的“模型组合”中选择。[组织模型组合部署步骤](../../apps/workbench/README.md#provision-the-optional-organization-model-combination)
