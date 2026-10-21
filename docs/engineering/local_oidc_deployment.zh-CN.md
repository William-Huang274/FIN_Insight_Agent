# 本机 OIDC 与组织身份验收

本部署为独立本机验收环境。Keycloak 提供真实账号、授权码与 PKCE；BFF 使用既有 Authlib / PyJWT 验证签名、issuer、audience、有效期，再将 issuer + sub 映射为稳定身份。Java 接收 BFF 签名委托并维护组织、项目和成员权限。登录成功不自动获得组织或资料权限。

## 部署合同

- `scripts/deployment/local_identity.py` 生成独立 Compose、realm、客户端、两名本机账号及 TLS 文件；拒绝覆盖已有身份目录，不启动服务。
- 固定 Keycloak 26.7.3 镜像摘要，PostgreSQL 16.15；数据位于专用命名卷。使用 `start` 和 HTTPS，不使用 `start-dev`。
- 默认身份入口 `https://localhost:18443`，realm `finsight`；应用入口 `https://localhost:18866`。
- 客户端 `finsight-workbench` 只开放授权码流程，要求 PKCE S256；关闭密码直连、隐式授权、服务账号和自行注册。回调精确为应用 origin 下的 `/auth/callback`，无通配符。
- access token 的 `finsight-api` audience 通过 Keycloak mapper 明确设置。BFF Cookie 使用 HttpOnly、Secure、SameSite=Lax，最长五分钟。
- 本机验收账号的邮箱使用保留的 `example.invalid` 域，未验证，不启用邮件发送或邮箱密码找回。
- TLS 使用本机验收 CA，只将证书加入当前用户信任库。签发私钥不落盘，服务证书有效期 90 天；到期前重新签发并显式替换信任。Python 的 `SSL_CERT_FILE`、Node 的 `NODE_EXTRA_CA_CERTS` 指向此 CA，不关闭 TLS 校验。
- 端口只绑定 `127.0.0.1`。Java/BFF 内部接口仍采用现有 loopback 签名委托；不得将其直接暴露公网。

参考维护方的 [容器部署说明](https://www.keycloak.org/server/containers)、[hostname 配置](https://www.keycloak.org/server/hostname)和 [realm 导入行为](https://www.keycloak.org/server/importExport)。已存在 realm 的启动导入不会覆盖数据库配置；更新账号和客户端应使用正常管理接口，不能通过删库重建实现。

## 复现与凭据边界

1. 在仓库外准备仅当前用户和 SYSTEM 可访问的父目录。Windows 使用目录 ACL；Unix 使用 `0700`。生成器的输出目录必须不存在。
2. 检查候选端口与 Docker 子网无冲突，运行 `python scripts/deployment/local_identity.py --private-root <绝对新目录>`。可用参数指定两个端口和独立子网。
3. 检查生成的 `identity-manifest.json`；使用独立 Compose 项目名、其 `compose.env` 和 `compose.yaml` 启动。不得复用已有研究服务的项目或数据卷。
4. 将 `tls/ca.pem` 加入当前用户证书信任，保存 manifest 中的 thumbprint，以便准确撤销。本地密码、客户端 secret、session secret 和 TLS 私钥均留在受限目录，不提交 Git、不输出日志。
5. BFF 加载 `bff-env.private.json` 中的生产身份配置，以正常 `apps.workbench.backend.app:app` 入口提供 HTTPS。Java 使用独立数据库、独立委托密钥，研究执行和报告动作开关在入口验收期间关闭。
6. 保留真实运行源版本、JAR/前端摘要、端口、进程与卷清单。仅启动登录/业务服务不能填写“整个研究部署已完成”。

浏览器复现入口为 `apps/workbench/frontend/e2e/oidc-live-login.mjs`。显式配置 `FINSIGHT_PUBLIC_ORIGIN`、`FIN_OIDC_CREDENTIALS_FILE`、新的仓库外 `FIN_OIDC_EVIDENCE` 和 `NODE_EXTRA_CA_CERTS`。脚本仅接受约定的本机验收 origin；通过网页输入账号密码，不能用测试 Bearer 或拦截接口代替登录。重启后提供 `FIN_OIDC_RECOVERY_RESULT` 指向先前结果，会核对同一批账号和项目，不创建替代记录。

检查失败时只保存检查点和错误类型；不保存浏览器 storage state、Cookie、access token、授权码或带密码的 trace。重启后必须先确认 discovery 和业务服务 ready，再发起复验。

## 2026-10-21 结果

- 真实 Keycloak / HTTPS BFF / Spring Boot / PostgreSQL 的浏览器验收 **9 个检查通过**：错误密码、真实授权码登录和安全 Cookie、创建组织/项目、第二身份隔离、显式成员授权、刷新身份不变、跨站退出拒绝、本应用退出及非法 callback 拒绝。
- 仅重启自建身份服务、身份库和业务库后，**2 个恢复检查通过**：两名用户的稳定身份不变，同一项目及成员权限仍存在；正常项目页可见两位成员。
- 部署生成器与既有认证定向回归 **25 项通过**，不是 25 个真实 SSO 场景。
- 浏览器未拦截 API，TLS 校验开启，**0 次模型调用**。第一轮错误提示定位器不匹配、缺少本机账号邮箱、Node 请求客户端未加载 CA 和重启尚未 ready 的失败均保留，修复后复验；不计作产品通过证据。

证据位于仓库外 `normal-deployment-r1/oidc-browser-r5` 与 `oidc-restart-r2`，各有 `result.json`。首轮成功截图过早处于加载页；以重启复验等待项目标题后的 `project-after-restart.png` 为实际页面证据。

## 当前限制和回退

“退出工作区”清除当前应用会话，不代表注销 Keycloak 全部 SSO 会话。再次进入授权流程可能使用尚有效的 SSO；当前未实现全局登出、后台会话撤销或账号禁用后的即时应用 Cookie 撤销，已有应用会话最多保留五分钟。项目/资料权限仍按每次业务请求核验，不能用此会话期限替代权限撤销检查。

本批未验证公网域名、企业目录同步、MFA、HA、灾备或负载容量。已有研究部署没有切换。后续已完成专用 Agent Server 及一份历史披露的组织发布/索引准备冒烟，范围见[独立候选的正常运行栈记录](java_python_release_candidate.zh-CN.md)；S2 检索质量和真实模型研究仍不能由登录或单资料冒烟推定通过。

回退只停止本次专用 Compose/进程，保留账号库、业务记录和卷；不执行 `down -v`。如取消本机服务，按 manifest thumbprint 移除当前用户对应 CA，不能批量清空证书库。保留私有文件的访问控制；重新准备必须使用新目录，不覆盖已产生的身份和凭据。
