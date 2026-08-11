# 881 — FIN 0.1.3 typed Case／Pack 绑定与主研究工作区纵切

日期：2026-08-11

状态：工程通过；旧消费者切换与归档仍待完成

## 本次交付

新增版本中立 `ResearchWorkspaceService`。DELL、MU、NVDA 每个案例现在明确绑定：

- `entity_id`、SEC issuer ID、法定名称、ticker、exchange 与 as-of；
- case ID 与 case version；
- Case subject digest；
- Pack case key、S1 result digest、artifact digest 与 payload digest；
- `identity_and_digest_bound` 状态和独立 binding digest。

跨案例替换 artifact／payload、错误权限、错误产品模式、未知 Case、日期或内容漂移均 fail closed。API 为：

- `GET /api/v1/research-cases`
- `GET /api/v1/research-cases/{case_id}`
- `GET /api/v1/research-cases/{case_id}/evidence`

新增真实 `/workspace` React 消费者，直接展示公司身份、研究问题、Evidence 业务含义、claim boundary、来源链接、不可变摘要与 residual gaps。它不展示假报告按钮，也不声称当前 Pack 是完整投资报告。`/operations` 已建立入口，但旧运维页面与旧产品代码的彻底拆分属于下一切片。

## 验证

- workspace／registry 合同：`21 passed`
- Workbench 相邻回归：`53 passed`
- TypeScript：`tsc --noEmit` 通过
- Vite production build：通过
- 模型／Provider／live network：`0／0／0`

构建仍产生约 `614 kB` 的单一 JS chunk 警告。根因不是新 workspace 本身，而是旧 `/current`、`/next`、fixture UI 和 r53 运维 UI 仍由同一个 `main.tsx` 静态导入。这被保留为下一切片必须消除的活动消费者证据，不能通过调高 chunk warning 隐藏。

## 下一步

把 `/operations` 收敛成版本中立运维消费者；让 `/current`、`/next`、`/legacy`、Point02/03 与 r53 产品消费者归零；完成 redirect manifest 后才移动对应代码与测试。
