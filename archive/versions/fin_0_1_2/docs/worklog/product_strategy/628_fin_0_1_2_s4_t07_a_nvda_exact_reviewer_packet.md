# FIN 0.1.2 S4-T07-A NVDA exact reviewer packet

日期：2026-08-05
状态：`engineering pass / reviewer packet ready / T07-B next`

## 用户授权与阶段边界

用户明确接受 T07 身份方案 A：FIN 0.1.2 内部 dogfood 使用服务端签发的有界 opaque reviewer session。该授权允许依次实现 T07-A 审核包和 T07-B 会话机制，但不授权 Codex、自动化或测试会话代替真实审核人完成 T07-C，也不自动建立 NVDA R3。

## 本轮发现与修正

T06 产品面已显示 NVDA 有 `1 dependency / 2 conflicts / 4 Lead gaps`，但只暴露数量，没有暴露可审核的具体内容。核验 immutable exact result 后确认这些内容位于已通过校验的 `bounded_agent_judgment` 业务 Artifact，而不是受限 Provider capture；因此该缺口属于 T07-A 审核可用性，不应错误推给 T07-B 身份认证。

T07-A 新增内容寻址、NVDA-only、GET-only reviewer packet。它精确绑定 current projection manifest、NVDA case projection、十个 view、review-control replay 和 exact T07 handoff；覆盖 15 Evidence、3 Numeric、3 typed product gaps、3 research cells、6 Claims、9 what-would-change、1 cross-cell dependency、2 unresolved conflicts、4 Lead gaps、final report、safe audit trace、quality findings 与五项人工审核 checklist。

review burden 只记录项目数量，不在真人操作前虚构审核时长。所有 checklist 状态均为 `pending_human_review`；packet 明确记录 authenticated session、qualified review、review decision、NVDA R3 均为 false。

## 安全与产品边界

- 模型、Provider、网络、金融来源调用：`0/0/0/0`。
- accepted R2 business truth 写入：0。
- raw capture、Provider output、credential、header、private reasoning 暴露：0。
- DELL/MU reviewer packet：未开放；T07 当前只处理 exact NVDA。
- open return request 会使 packet fail closed，不能掩盖 repair blocker。
- T07-A 不是 authenticated identity，也不是 Human acceptance 或 NVDA R3。

## 验证

- T07-A focused contracts：`5 passed`。
- T06-A/B/C + T07 entry + T07-A adjacent regression：`39 passed`。
- materializer `--check`：pass。
- Python compile：pass。
- 旧 T06 OpenAPI 测试改为验证旧路由仍是后继路由集合的子集；没有修改 T06 业务真相或历史记录。

## 下一步

T07-A engineering pass。下一项是已经获批的 `T07-B bounded internal server-issued reviewer session`：仅允许离线 admin issuance、一次显示 opaque token、digest-only store、qualified reviewer allowlist、expiry/revocation、exact NVDA manifest/case/handoff binding，以及 append-only authentication/decision events。T07-C 继续等待真实用户操作。
