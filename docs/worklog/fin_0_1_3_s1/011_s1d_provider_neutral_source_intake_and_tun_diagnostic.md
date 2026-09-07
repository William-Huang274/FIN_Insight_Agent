# S1-D 通用来源入库与 TUN 路径诊断

日期：2026-08-13

## 完成

- 建立一份 provider-neutral `Source Intake`：自动获取和人工官方 PDF 上传共用 route policy、私有不可变 raw CAS、manifest、PDF 验收和重复检测。
- `/operations` 已提供 route 选择、PDF 上传、一次自动获取和最近 attempt；研究产品面不会直接消费未晋升材料。
- PDF host／HTTPS／MIME／size／signature／EOF／encryption／page count／attempt identity 全部 fail closed；原始字节、Cookie、Authorization 和代理凭据不经 API 返回。
- 最终 47 个聚焦后端/合同测试、前端 typecheck、production build 和桌面/移动 6 个 Playwright 测试通过；active baseline 为 102 Python／8 frontend／10 Runtime resources、0 failure。
- 基于干净、已推送提交签发两 route／两网络尝试／零重试／零模型的 exact runner，并执行唯一 automatic live R1。

## 真实结果

- Dell：一次请求，约 45 秒后 `official_source_transport_timeout`，没有 HTTP status、PDF body、parse 或 Evidence。
- TSM：一次请求，约 45 秒后 requests transport exception；现有历史 capture 只保存为 `official_source_transport_error`，没有 HTTP status、PDF body、parse 或 Evidence。
- 两个域均解析到 `198.18.0.0/15` Fake-IP，实际路由均为 `okz / Meta Tunnel`；应用代理环境变量、Windows 用户代理和 PAC 均未启用。

## 业务解释

这不是 DeepSeek、检索排序或 PDF parser 的问题。当前本机在接触官方正文前就失败；Dell conversion/margin 与 TSM packaging 资料仍是诚实 typed gap。TUN 路径明确参与了失败，因此 requests、curl 与 Edge 不是独立网络对照；但本轮不能进一步区分“透明 TUN 映射/转发异常”和“代理出口被官方站点/WAF 拒绝”。

## 止损与下一步

- 不自动 R2、不轮换客户端、不增加 retry、不由项目代码修改用户代理配置。
- 最快解除内容阻塞的路径是从官方页面取得 PDF 后，经 Workbench 的已绑定 route 上传；上传成功仍只是 source，不是 Evidence。
- 若必须恢复自动获取，需由用户可见地做同 URL 的域名 DIRECT／临时关闭 TUN A/B，并另行签发网络权限。
- 取得合法 PDF 后才进入 parser、身份/日期绑定、对象编译、Evidence Gate、Evidence Pack 复编译和有限 S2 回归；这些完成前不得签发 S3 研究/报告调用。
