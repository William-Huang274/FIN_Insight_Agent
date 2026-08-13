# FIN 0.1.3 S1-D 通用来源入库与网络诊断合同

日期：2026-08-13
状态：`engineering_pass / automatic_path_blocked / operator_upload_ready / S1D_product_open / no_evidence_promotion`

## 1. 产品问题

Dell Q1 FY2027 与 TSM Q2 2026 transcript 已确认存在，但当前产品环境无法取得原始 PDF。继续为单站点轮换 requests、curl 或浏览器只会增加 transport 分支，不能形成可维护的金融来源能力。

本工作包建立一条共同的 `Source Intake`：无论文件来自自动适配器还是人工上传，原始字节、官方 URL、来源主体、发布日期、获取方式、内容类型、字节数和 SHA-256 都先写入私有不可变 capture，再进行 PDF、安全和身份验收。通过 Source Intake 只表示“可进入解析队列”，不表示已经成为 Evidence。

## 2. 两个 acquisition driver

### 2.1 自动来源适配器

- 输入只能引用已登记 route policy，不能让客户端提交任意 URL 或 host；
- 当前 driver 可复用有界 direct HTTP／browser download transport；未来第三方 source provider 也必须实现同一接口；
- 0 retry 为默认，HTTP、DNS、TLS、timeout、redirect、MIME 和内容失败必须形成 typed result；
- 只有 2xx、HTTPS allowlist、字节预算、PDF 签名和解析 sanity 同时通过时，才生成 `captured_ready_for_parse`；
- 失败响应仍保存在私有 capture，但不得进入对象库或 Evidence Gate。

### 2.2 人工官方 PDF 上传

- 操作员选择已登记 route，并同时提交官方 URL、发布日期、标题和 PDF；
- URL host 必须与 route policy 一致，文件必须是有效、未加密、页数大于零的 PDF；
- 上传字节和自动下载字节进入同一 CAS、同一 manifest 和同一重复检测；
- 人工上传不是事实晋升旁路，也不能把网页摘录、截图或手写文本包装成官方文件。

## 3. 私有对象与状态

每次入库尝试保存：

- `attempt_id`：一次获取动作的唯一身份，禁止覆写；
- `route_id / case_key / source_url / publication_date / title`；
- `acquisition_method / adapter_id`；
- 原始字节 CAS ref、SHA-256 和 size；
- declared MIME、detected MIME、PDF signature、page count 和 encryption state；
- `accepted / rejected / duplicate` 及 typed reason；
- 自动获取时的 HTTP status、final URL 与脱敏网络路径摘要。

原始 PDF 和失败页面只写入 `FINSIGHT_WORKBENCH_PRIVATE_ROOT/source_intake/`，不进入 Git。Git 只保存 policy、代码、测试和不含原文的结果摘要。

## 4. 网络/TUN 诊断边界

当前主机检查结果为：

- `HTTP_PROXY / HTTPS_PROXY / ALL_PROXY` 未配置；
- WinHTTP 为 direct，Windows 用户代理关闭；
- 活动接口包含 `okz / Meta Tunnel`；
- 两个官方域名均解析为 `198.18.0.0/15` Fake-IP，并经 `okz` 路由。

因此 requests、curl 与 Edge 虽是不同客户端，仍可能共享同一透明 TUN 出口。该事实证明“换客户端”不是独立网络对照，但不能单独证明 403 一定由代理出口造成。

Source Intake 只记录脱敏诊断：应用层代理是否存在、是否命中 Fake-IP、实际路由接口、DNS/TLS/HTTP 阶段和响应状态。它不会保存代理凭据、Cookie、Authorization、完整系统配置或外网出口 IP。若仍出现 403，下一步应在用户可见情况下比较同一 URL 的 TUN 路由与域名直连规则；项目代码不得擅自改代理软件配置。

## 5. API 与 Workbench

运维面提供：

- `GET /api/operations/source-intake/routes`：列出可用 route 和当前状态；
- `GET /api/operations/source-intake/attempts`：列出不含原始正文的入库记录；
- `POST /api/operations/source-intake/uploads/{route_id}`：以 `application/pdf` 原始 body 上传；
- `POST /api/operations/source-intake/automatic/{route_id}`：执行一次已登记、0 retry 的自动获取；
- `/operations` 显示上传表单、route 边界和最近 attempt，不在研究产品面直接展示未晋升材料。

## 6. 通过条件

工程门：

1. 合法官方 PDF 经自动和上传两条 driver 生成等价 manifest；
2. 错 host、HTTP URL、超限、伪 PDF、截断 PDF、加密 PDF、复用 attempt 和跨 route 身份均 fail closed；
3. 相同文件重复进入只复用 CAS，不复制原始字节；
4. API 不返回 raw bytes、Cookie、Authorization 或代理密钥；
5. 后端测试、前端 typecheck/build、Workbench E2E 和全量回归通过。

产品门仍保持开放：取得 PDF 后还需 parser、对象编译、Evidence Gate、Evidence Pack 复编译和 S2 依赖回归；只有这些完成，S3 才能消费。

## 7. 实现与真实 R1 结果

共同 intake、两条 driver、API 和 Workbench 消费者已实现。最终 47 个聚焦后端/合同测试、前端 typecheck、production build，以及桌面/移动 6 个 Playwright 用例通过。人工上传与自动 driver 的同字节回放会复用同一 raw CAS；伪造、截断、加密、超限、错 host 和重复 attempt 均 fail closed。

唯一 automatic R1 按两条 route 各执行一次，0 retry、0 模型、0 broad search：

- Dell 在取得 HTTP status 前约 45 秒 timeout；
- TSM 在取得 HTTP status 前约 45 秒发生 requests transport exception；
- 两案均为 0 PDF、0 parse、0 Evidence。

两域在执行时分别解析为 `198.18.1.43` 和 `198.18.1.44`，均落在 Fake-IP 段并经 `okz / Meta Tunnel`；显式应用代理、Windows 用户代理和 PAC 均未启用。因此“当前透明 TUN 路径参与失败”是已证事实，“具体是 TUN 映射/转发异常还是代理出口被站点/WAF 拒绝”仍未证明。

R1 还暴露出原 capture 对通用 Requests 异常分类不足：TSM 的具体异常类未被持久化，事后只能保守记为 transport exception。R1 保持不可变；successor 已用零网络 mutation 将 connect/read timeout、TLS、proxy、response stream、redirect、invalid URL、connection 和 generic request 分成安全 typed code，且不保存可能带敏感内容的异常消息。本修复不产生自动 R2 权限。

本合同不授权自动 R2 或修改代理设置。当前推荐顺序是：优先用已绑定 Workbench route 人工上传官方 PDF；若必须恢复自动获取，再在用户可见情况下对同一 URL 做 domain DIRECT／临时关闭 TUN 的单次 A/B。无论哪条 driver 成功，后续仍须经过 parser、对象编译、Evidence Gate、Pack 复编译和有限 S2 回归。
