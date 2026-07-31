# 464｜FIN 0.1 S4-T06 Sub2API 停放与 DeepSeek 主线重定基线

日期：2026-07-29

## 结果

按用户指示，S4/T06 主线已从 Sub2API/gpt-5.5 strict-schema canary 轨道切回项目既有 DeepSeek 轨道。

- Provider：DeepSeek
- model：`deepseek-v4-pro`（Pro，不是 Flash）
- base URL：`https://api.deepseek.com/beta`
- credential：仅确认 `DEEPSEEK_API_KEY` 当前进程存在；未读取、输出或持久化值
- T06 产品任务：MU HBM fresh exact R2 execution and paired assessment

Sub2API 的 HTTP 401、plain HTTP 和 standalone raw-client contract 缺失被保留为外部可恢复轨道，不再阻断 DeepSeek 上的 MU T06。醒目恢复入口为：

`docs/project_os/STRICT_SCHEMA_TRANSPORT_API_HANDOFF.zh-CN.md`

## 为什么可以恢复 DeepSeek 主线

strict server-side JSON Schema 能提高结构遵循率，但不是金融真实性的最终 owner。项目当前仍保留：

- typed judgment atoms；
- 本地 material number/period/unit/sign/entity/ID/lineage 唯一 owner；
- deterministic rendering；
- 独立 L1 fail-closed semantic validation；
- atomic terminal truth。

DeepSeek 历史 exact-live 已证明 HTTPS Provider 链路和 6-node/12-call/9-Artifact 物化路径可达。DELL R11 的问题是首个 Provider 输出违反 numeric narrative 合同，本地 gate 正确阻断，并非 DeepSeek credential、网络或 transport 失效。

因此本次不是把 L1 降级，也不是宣称 DeepSeek 已解决模型遵循问题；只是把“server-side strict schema”从 T06 必选入口改回可选 transport 增强。

## 阶段边界

- T05：R11 后诚实阻断，不启动 R12；未通过、未 owner accepted、DELL R2 未证明。
- T06：只进入 MU 的零调用准备阶段。
- 本轮未签发 MU admission，未执行模型/Provider/network/source/tool 调用，未创建 Run/Artifact，未 paired 或 owner acceptance。
- S4 pass、S5、release、production 继续 blocked。

## 下一步

`S4-T06-MU-DEEPSEEK-MAINLINE-FRESH-EXACT-ADMISSION-PREPARATION-AND-ZERO-CALL-PROOF`

该项只应复用既有 MU Case Pack、shared runtime 和 DeepSeek runner，先证明 exact input/profile/binding/identity/digest 一致；不得复制 DELL 的逐轮 patch 历史，也不得在 proof 内签发或消费 admission。
