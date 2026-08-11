# FIN 0.1.2 S4-T07 入口、reviewer 身份与任务边界决策

日期：2026-08-05
状态：`entry pass / authenticated reviewer identity blocked / T07-A safe`

## 问题

T06-C 已生成 DELL、MU、NVDA 的 exact T07 handoff，但其自身明确声明 authenticated reviewer identity、qualified Human Review 和 NVDA R3 均为 false。T07 不能只给前端增加一个“接受”按钮，否则任何调用者都能通过自报 header 冒充 qualified reviewer。

## 审计结果

- current API 从 `X-Fin-Current-Actor` 和 `X-Fin-Case-Permissions` 直接构造 principal。
- current 前端固定声明 `current_internal_operator` 与 read/request-repair permission，没有 qualified-review permission。
- 历史 P24/B04 real-human 路径验证 `action_source`、reviewer role 和 session ID 的内容，但没有可信 IdP、服务端签发 session 或 credential 验证。
- 因此旧路径可以作为 acceptance 表单和 manifest 设计参考，不能作为 authenticated identity 实现复用。

登记 `RC-P36-129`：这是 T07 项目内身份/权限边界缺口，不是 DeepSeek、研究结果、T06 control plane 或数据来源失败。

## 处置

T07 重新有界拆分：

1. `T07-A`：零调用生成 NVDA exact reviewer packet、audit replay、review burden 与 bounded why/gap/WWC；不写 Human 决策。
2. `T07-B`：实现经用户确认的 authenticated reviewer session 与 append-only decision event。
3. `T07-C`：真实 reviewer 查看 exact NVDA packet 后明确接受或退回；成功接受才建立 bounded NVDA R3。

推荐 FIN 0.1.2 内部 dogfood 采用 bounded server-issued opaque review session：管理员离线签发，credential 只返回一次，控制库只保存 digest；绑定 reviewer identity/role、expiry、revocation、case/manifest/handoff digest 和 accept/return permission。明文 credential、签名密钥不得进入 Git、telemetry、capture、Artifact 或工作日志。生产 OIDC/SSO 不塞入当前 T07，留待 S5/后续安全范围。

备选 B 是现在接 OIDC/企业 IdP，安全语义更强但会扩大基础设施并阻断 0.1.2 内部里程碑。备选 C 是继续用聊天显式 Owner 决策；它可作为反馈证据，但 qualified review 和 NVDA R3 必须保持 false。

## 验证

- decision materializer：pass
- T07 entry/identity contract and mutation：`9 passed`
- model/provider/network/financial-source calls：`0/0/0/0`
- Human acceptance、NVDA R3、business truth writes：`0/false/0`
- decision digest：`974eea932ec755eba88e32389b13142b4e192578a32b8b5a883bf1d7aac00068`

## 边界与下一步

当前只成立 `S4-T07 entry=pass`。T07 engineering、authenticated reviewer identity、qualified Human Review、NVDA R3、T08、S5 和 release 均未成立。身份安全范围待用户确认，但安全工作 `T07-A` 可先继续；T07-B/C 不得提前启动。

下一项：`FIN-0.1.2-S4-T07-A-NVDA-EXACT-REVIEWER-PACKET-AUDIT-REPLAY-BURDEN-AND-BOUNDED-EXPLANATION-ZERO-CALL-IMPLEMENTATION`。
